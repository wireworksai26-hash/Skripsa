from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import auth_required, owned_thesis
from app.core.ratelimit import limit_user
from app.models.models import Citation, SectionVersion, ShareComment, Thesis, User
from app.services import insights, refs_io
from app.services.agents import documents
from app.services.agents.documents import GenerationError
import secrets

router = APIRouter(prefix="/theses", tags=["extras"])
activity_router = APIRouter(tags=["extras"])


def _gen_error(exc: GenerationError) -> HTTPException:
    return HTTPException(503, str(exc))


# ---------- halaman depan ----------


class FrontIn(BaseModel):
    abstract_id: str = Field(default="", max_length=4000)
    abstract_en: str = Field(default="", max_length=4000)
    keywords_id: list[Annotated[str, Field(max_length=100)]] = Field(default_factory=list, max_length=8)
    keywords_en: list[Annotated[str, Field(max_length=100)]] = Field(default_factory=list, max_length=8)
    preface: str = Field(default="", max_length=8000)


@router.post("/{thesis_id}/front-matter/generate")
async def generate_front(thesis: Thesis = Depends(owned_thesis), db: Session = Depends(get_db)):
    limit_user(thesis.user_id, "front-generate", 20, 60)
    try:
        data, provider = await documents.generate_front_matter(thesis, db)
    except GenerationError as exc:
        raise _gen_error(exc)
    thesis.front_json = data
    db.commit()
    return {"front": data, "provider": provider}


@router.put("/{thesis_id}/front-matter")
def save_front(payload: FrontIn, thesis: Thesis = Depends(owned_thesis), db: Session = Depends(get_db)):
    thesis.front_json = payload.model_dump()
    db.commit()
    return {"front": thesis.front_json}


# ---------- lampiran instrumen ----------


class AppendixItem(BaseModel):
    id: str = ""
    kind: str = "kuesioner"
    title: str = Field(max_length=200)
    intro: str = Field(default="", max_length=3000)
    items: list[Annotated[str, Field(max_length=1000)]] = Field(default_factory=list, max_length=60)


@router.post("/{thesis_id}/appendices/generate")
async def generate_appendices(thesis: Thesis = Depends(owned_thesis), db: Session = Depends(get_db)):
    limit_user(thesis.user_id, "appendices-generate", 20, 60)
    try:
        data, provider = await documents.generate_appendices(thesis, db)
    except GenerationError as exc:
        raise _gen_error(exc)
    thesis.appendix_json = data
    db.commit()
    return {"appendices": data, "provider": provider}


@router.put("/{thesis_id}/appendices")
def save_appendices(payload: list[AppendixItem] = Body(..., max_length=6), thesis: Thesis = Depends(owned_thesis), db: Session = Depends(get_db)):
    out = []
    for i, a in enumerate(payload[:6], start=1):
        d = a.model_dump()
        d["id"] = f"L{i}"
        d["items"] = [x.strip() for x in d["items"] if x.strip()]
        out.append(d)
    thesis.appendix_json = out
    db.commit()
    return {"appendices": out}


# ---------- impor/ekspor referensi ----------


class ImportRefsIn(BaseModel):
    text: str = Field(min_length=10, max_length=400_000)


def _ref_dict(c: Citation) -> dict:
    return {
        "title": c.title, "authors": c.authors or [], "publication_year": c.publication_year, "journal_name": c.journal_name,
        "volume_issue": c.volume_issue, "page_range": c.page_range, "doi": c.doi,
    }


@router.post("/{thesis_id}/citations/import")
def import_refs(payload: ImportRefsIn, thesis: Thesis = Depends(owned_thesis), db: Session = Depends(get_db)):
    limit_user(thesis.user_id, "import-refs", 10, 60)
    parsed = refs_io.parse_references(payload.text)
    if not parsed:
        raise HTTPException(422, "Tidak ada referensi yang terbaca. Gunakan berkas BibTeX (.bib) atau RIS (.ris).")
    existing = {c.title.strip().lower() for c in db.query(Citation).filter(Citation.thesis_id == thesis.thesis_id).all()}
    added, skipped = [], 0
    for r in parsed[:300]:
        if r["title"].strip().lower() in existing:
            skipped += 1
            continue
        existing.add(r["title"].strip().lower())
        c = Citation(
            thesis_id=thesis.thesis_id, doi=r.get("doi"), title=r["title"], authors=r.get("authors") or [],
            publication_year=r.get("publication_year") or 0, journal_name=r.get("journal_name"), volume_issue=r.get("volume_issue"),
            page_range=r.get("page_range"), pdf_url=r.get("pdf_url"), highlighted_snippet=r.get("highlighted_snippet") or "",
            source_database=r.get("source_database") or "Impor",
        )
        db.add(c)
        added.append(c)
    db.commit()
    return {"added": len(added), "skipped_duplicates": skipped, "citation_ids": [c.citation_id for c in added], "without_year": sum(1 for c in added if not c.publication_year), "without_authors": sum(1 for c in added if not c.authors)}


@router.get("/{thesis_id}/citations/export")
def export_refs(format: str = "bibtex", selected_only: bool = True, thesis: Thesis = Depends(owned_thesis), db: Session = Depends(get_db)):
    rows = db.query(Citation).filter(Citation.thesis_id == thesis.thesis_id).all()
    if selected_only and thesis.selected_ref_ids:
        rows = [c for c in rows if c.citation_id in thesis.selected_ref_ids]
    refs = [_ref_dict(c) for c in rows]
    if format == "ris":
        return Response(refs_io.to_ris(refs), media_type="application/x-research-info-systems", headers={"Content-Disposition": 'attachment; filename="rujukan.ris"'})
    return Response(refs_io.to_bibtex(refs), media_type="application/x-bibtex", headers={"Content-Disposition": 'attachment; filename="rujukan.bib"'})


# ---------- latihan sidang, kemiripan, riwayat versi ----------


class DefenseIn(BaseModel):
    question: str = Field(min_length=10, max_length=1200)
    answer: str = Field(min_length=1, max_length=6000)


@router.post("/{thesis_id}/defense/evaluate")
async def defense_evaluate(payload: DefenseIn, thesis: Thesis = Depends(owned_thesis), db: Session = Depends(get_db)):
    limit_user(thesis.user_id, "defense-evaluate", 20, 60)
    try:
        result, provider = await documents.evaluate_defense(thesis, db, payload.question, payload.answer)
    except GenerationError as exc:
        raise _gen_error(exc)
    return {**result, "provider": provider}


@router.get("/{thesis_id}/similarity")
def similarity(thesis: Thesis = Depends(owned_thesis), db: Session = Depends(get_db)):
    return insights.similarity_report(thesis, db)


@router.get("/{thesis_id}/sections/{section_code}/versions")
def section_versions(section_code: str, thesis: Thesis = Depends(owned_thesis), db: Session = Depends(get_db)):
    rows = (
        db.query(SectionVersion)
        .filter(SectionVersion.thesis_id == thesis.thesis_id, SectionVersion.section_code == section_code)
        .order_by(SectionVersion.created_at.desc())
        .all()
    )
    return [{"version_id": v.version_id, "reason": v.reason, "created_at": v.created_at.isoformat() if v.created_at else "", "content": v.content_markdown} for v in rows]


# ---------- tautan pembimbing ----------


@router.post("/{thesis_id}/share")
def create_share(thesis: Thesis = Depends(owned_thesis), db: Session = Depends(get_db)):
    limit_user(thesis.user_id, "share-create", 30, 60)
    if not thesis.share_token:
        thesis.share_token = secrets.token_urlsafe(24)
        db.commit()
    return {"token": thesis.share_token}


@router.delete("/{thesis_id}/share", status_code=204)
def revoke_share(thesis: Thesis = Depends(owned_thesis), db: Session = Depends(get_db)):
    thesis.share_token = None
    db.commit()


def _comment_out(c: ShareComment) -> dict:
    return {"comment_id": c.comment_id, "section_code": c.section_code, "author": c.author, "text": c.text, "resolved": c.resolved, "created_at": c.created_at.isoformat() if c.created_at else ""}


@router.get("/{thesis_id}/comments")
def list_comments(thesis: Thesis = Depends(owned_thesis), db: Session = Depends(get_db)):
    rows = db.query(ShareComment).filter(ShareComment.thesis_id == thesis.thesis_id).order_by(ShareComment.created_at.desc()).all()
    return [_comment_out(c) for c in rows]


class ResolveIn(BaseModel):
    resolved: bool


@router.patch("/{thesis_id}/comments/{comment_id}")
def resolve_comment(comment_id: str, payload: ResolveIn, thesis: Thesis = Depends(owned_thesis), db: Session = Depends(get_db)):
    c = db.get(ShareComment, comment_id)
    if not c or c.thesis_id != thesis.thesis_id:
        raise HTTPException(404, "Komentar tidak ditemukan")
    c.resolved = payload.resolved
    db.commit()
    return _comment_out(c)


# ---------- aktivitas menulis ----------


class GoalIn(BaseModel):
    daily_goal: int = Field(ge=50, le=5000)


@activity_router.get("/activity")
def activity(user: User = Depends(auth_required), db: Session = Depends(get_db)):
    return insights.activity_summary(db, user)


@activity_router.put("/activity/goal")
def set_goal(payload: GoalIn, user: User = Depends(auth_required), db: Session = Depends(get_db)):
    user.daily_goal = payload.daily_goal
    db.commit()
    return insights.activity_summary(db, user)
