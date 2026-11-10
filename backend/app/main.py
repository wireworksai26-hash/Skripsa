import asyncio
import logging
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.db import init_db
from app.routers import auth, charts, export, account, extras, research_data, share, structure, generate, imports, revise, visuals, pdf, rag, references, review, stats, templates, theses
from app.services.llm import LLMUnavailable, is_configured as is_llm_configured, status as llm_status
from app.services.scientific_api import unpaywall_enabled
from app.services.vectorestore import FAISS_AVAILABLE

log = logging.getLogger(__name__)
MAX_BODY_BYTES = 20 * 1024 * 1024
HEALTH_CACHE_SECONDS = 300

_health_cache: dict | None = None
_health_cached_at = 0.0
_health_lock = asyncio.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    from app.core import db as core_db
    from app.services import push

    task = asyncio.create_task(push.reminder_loop(lambda: core_db.SessionLocal())) if push.is_configured() else None
    try:
        yield
    finally:
        if task:
            task.cancel()


production = settings.environment.strip().lower() == "production"
app = FastAPI(
    title="SkripsiAI API",
    description=(
        "Backend multi-agent generator skripsi: Prompt Orchestrator, Campus Template Engine, "
        "Integrator API ilmiah publik (OpenAlex/Crossref/DOAJ/ERIC), multi-agent pipeline "
        "(Advisor → Examiner → Academic Writer → Quality Guardrail), RAG, dan ekspor DOCX."
    ),
    version="0.2.0",
    lifespan=lifespan,
    docs_url=None if production else "/docs",
    redoc_url=None if production else "/redoc",
    openapi_url=None if production else "/openapi.json",
)

allow_all_origins = "*" in settings.cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=not allow_all_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    raw_length = request.headers.get("content-length")
    if raw_length:
        try:
            if int(raw_length) > MAX_BODY_BYTES:
                return JSONResponse(status_code=413, content={"detail": "Permintaan terlalu besar"})
        except ValueError:
            return JSONResponse(status_code=400, content={"detail": "Content-Length tidak valid"})

    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
    if request.url.path.startswith(("/auth", "/share", "/theses")):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.exception_handler(LLMUnavailable)
async def llm_unavailable_handler(request: Request, exc: LLMUnavailable):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


app.include_router(auth.router)
app.include_router(account.router)
app.include_router(theses.router)
app.include_router(references.router)
app.include_router(generate.router)
app.include_router(review.router)
app.include_router(export.router)
app.include_router(rag.router)
app.include_router(charts.router)
app.include_router(pdf.router)
app.include_router(stats.router)
app.include_router(templates.router)
app.include_router(imports.router)
app.include_router(revise.router)
app.include_router(visuals.router)
app.include_router(extras.router)
app.include_router(extras.activity_router)
app.include_router(share.router)
app.include_router(structure.router)
app.include_router(research_data.router)


async def _probe_once(name: str, url: str, params: dict | None = None, headers: dict | None = None) -> tuple[str, int | str]:
    try:
        async with httpx.AsyncClient(timeout=10, headers={"User-Agent": "SkripsiAI/1.0"}) as client:
            res = await client.get(url, params=params, headers=headers)
            return name, res.status_code
    except httpx.HTTPError:
        return name, "unreachable"


async def _probe_scientific_apis() -> dict:
    if not unpaywall_enabled():
        return {}
    email = settings.polite_email.strip()
    probes = [
        _probe_once("OpenAlex", "https://api.openalex.org/sources", {"per-page": 1, "mailto": email}),
        _probe_once("Crossref", "https://api.crossref.org/works", {"rows": 0, "mailto": email}),
        _probe_once("DOAJ", "https://doaj.org/api/search/articles/test", {"pageSize": 1}),
        _probe_once("ERIC", "https://api.ies.ed.gov/eric/", {"search": 'keyword:"tes"', "format": "json", "rows": 1}),
    ]
    if settings.core_api_key:
        probes.append(
            _probe_once(
                "CORE",
                "https://api.core.ac.uk/v3/search/works/",
                {"q": "tes", "limit": 1},
                {"Authorization": f"Bearer {settings.core_api_key}"},
            )
        )
    return dict(await asyncio.gather(*probes))


@app.get("/healthz", tags=["meta"], include_in_schema=False)
def healthz():
    """Cek hidup ringan untuk platform hosting (tanpa memanggil API eksternal)."""
    return {"status": "ok"}


@app.get("/health", tags=["meta"])
async def health():
    global _health_cache, _health_cached_at
    now = time.monotonic()
    if _health_cache is not None and now - _health_cached_at < HEALTH_CACHE_SECONDS:
        return _health_cache
    async with _health_lock:
        now = time.monotonic()
        if _health_cache is not None and now - _health_cached_at < HEALTH_CACHE_SECONDS:
            return _health_cache
        api_status = await _probe_scientific_apis()
        _health_cache = {
            "status": "ok",
            "version": app.version,
            "llm_mode": "multi-penyedia" if is_llm_configured() else "tidak aktif (isi kunci API di backend/.env)",
            "llm": llm_status(),
            "rag": {"faiss": FAISS_AVAILABLE},
            "scientific_apis": api_status,
            "unpaywall": unpaywall_enabled(),
        }
        _health_cached_at = time.monotonic()
        return _health_cache
