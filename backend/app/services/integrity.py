"""Pemeriksaan akhir: kemiripan dengan literatur terbuka dan indikator gaya tulisan generik (mirip AI).

Keduanya INDIKATOR, bukan putusan:
- Kemiripan web memeriksa frasa dari draf terhadap teks lengkap karya akses terbuka di OpenAlex. Ini bukan Turnitin dan
  tidak menjangkau karya berbayar atau skripsi kampus.
- Gaya mirip AI dihitung dari pola statistik teks (variasi panjang kalimat, frasa klise, pembuka berulang, keragaman
  kata). Tidak ada detektor AI yang andal; tulisan manusia yang formal bisa tertandai, dan tulisan AI yang disunting
  bisa lolos. Hasilnya dipakai untuk menemukan bagian generik yang perlu ditulis ulang dengan kata sendiri.
"""

import asyncio
import math
import re
import statistics

import httpx

from app.core.config import settings
from app.models.models import Citation, Thesis
from app.services.agents.quality import paragraphs
from app.services.scientific_api import clean_doi

_CITE = re.compile(r"\([^()]*\d{4}[a-z]?\)|\[\d+(?:[,–-]\s*\d+)*\]|\[DATA[^\]]*\]")
_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"“(])")
_WORD = re.compile(r"[A-Za-zÀ-ÿ0-9']+")

STOCK = [
    # Inggris
    "furthermore", "moreover", "in conclusion", "it is important to note", "it is worth noting", "plays a crucial role", "play a crucial role",
    "a testament to", "delve", "tapestry", "multifaceted", "pivotal", "underscore", "in today's", "represents a critical", "in essence",
    "notably", "landscape of", "paramount", "holistic", "seamless", "in the realm of", "a myriad of", "navigate the",
    # Indonesia
    "penting untuk dicatat", "memainkan peran penting", "berperan penting", "di era digital", "dapat disimpulkan bahwa", "tidak dapat dipungkiri",
    "secara keseluruhan", "dengan demikian", "oleh karena itu", "selain itu", "lebih lanjut", "sangat krusial", "merupakan aspek yang",
    "seiring dengan perkembangan", "dalam konteks ini",
]
LABELS = [(60, "Tinggi"), (30, "Sedang"), (0, "Rendah")]
MIN_WORDS = 80

DISCLAIMER = (
    "Ini indikator gaya, bukan bukti. Tidak ada alat yang bisa memastikan sebuah teks ditulis AI; tulisan akademik formal sering "
    "tertandai dan teks AI yang disunting bisa lolos. Pakai hasil ini untuk menemukan bagian generik, lalu tulis ulang dengan "
    "pemikiran dan kata-kata Anda sendiri."
)


def _clean(text: str) -> str:
    t = _CITE.sub(" ", text or "")
    t = re.sub(r"(?m)^\s*(?:\d+[.)]|[-•*#]+)\s*", "", t)
    return re.sub(r"[ \t]+", " ", t).strip()


def _label(score: int) -> str:
    return next(name for floor, name in LABELS if score >= floor)


def section_ai_style(text: str) -> dict:
    clean = _clean(text)
    words = _WORD.findall(clean.lower())
    n = len(words)
    sentences = [s for s in _SENT.split(clean) if len(_WORD.findall(s)) >= 3]
    reasons: list[str] = []
    score = 0
    metrics: dict = {"words": n, "sentences": len(sentences)}

    lens = [len(_WORD.findall(s)) for s in sentences]
    if len(lens) >= 8:
        cv = statistics.pstdev(lens) / (statistics.mean(lens) or 1)
        metrics["sentence_cv"] = round(cv, 2)
        if cv < 0.30:
            score += 30
            reasons.append(f"Panjang kalimat sangat seragam (variasi {cv:.2f}); tulisan manusia biasanya lebih bervariasi.")
        elif cv < 0.38:
            score += 15
            reasons.append(f"Panjang kalimat cenderung seragam (variasi {cv:.2f}).")

    low = clean.lower()
    found = sorted({p for p in STOCK if p in low}, key=lambda p: -low.count(p))
    density = sum(low.count(p) for p in STOCK) * 100 / max(n, 1)
    metrics["stock_per_100"] = round(density, 2)
    if density >= 1.6:
        score += 30
        reasons.append(f"Banyak frasa penghubung/klise ({density:.1f} per 100 kata).")
    elif density >= 0.9:
        score += 15
        reasons.append(f"Cukup banyak frasa penghubung/klise ({density:.1f} per 100 kata).")

    if len(sentences) >= 8:
        openers = [" ".join(_WORD.findall(s.lower())[:2]) for s in sentences]
        top = max((openers.count(o) for o in set(openers)), default=0) / len(openers)
        metrics["opener_share"] = round(top, 2)
        if top >= 0.25:
            score += 15
            reasons.append(f"{round(top * 100)}% kalimat dibuka dengan kata yang sama.")

    if n >= 150:
        head = words[:250]
        ttr = len(set(head)) / len(head)
        metrics["ttr"] = round(ttr, 2)
        if ttr < 0.40:
            score += 15
            reasons.append(f"Keragaman kosakata rendah ({ttr:.2f}); banyak pengulangan kata.")

    paras = [len(_WORD.findall(p)) for p in paragraphs(clean) if len(_WORD.findall(p)) >= 20]
    if len(paras) >= 4:
        pcv = statistics.pstdev(paras) / (statistics.mean(paras) or 1)
        metrics["paragraph_cv"] = round(pcv, 2)
        if pcv < 0.20:
            score += 10
            reasons.append("Panjang paragraf hampir sama semua.")

    score = min(score, 100)
    return {"score": score, "label": _label(score), "reasons": reasons, "examples": found[:5], "metrics": metrics}


def ai_style_report(thesis: Thesis) -> dict:
    rows = []
    for s in sorted(thesis.sections, key=lambda x: [int(p) if p.isdigit() else 0 for p in x.section_code.split(".")]):
        text = s.content_markdown or ""
        wc = len(_WORD.findall(text))
        if wc == 0:
            continue
        base = {"code": s.section_code, "title": s.section_title, "imported": s.origin == "IMPORTED", "words": wc}
        if wc < MIN_WORDS:
            rows.append({**base, "score": None, "label": "Terlalu pendek", "reasons": [], "examples": [], "metrics": {}})
            continue
        rows.append({**base, **section_ai_style(text)})
    generated = [r for r in rows if r["score"] is not None and not r["imported"]]
    total_w = sum(r["words"] for r in generated)
    overall = round(sum(r["score"] * r["words"] for r in generated) / total_w) if total_w else None
    return {
        "sections": rows,
        "overall": overall,
        "overall_label": _label(overall) if overall is not None else None,
        "disclaimer": DISCLAIMER,
        "note": "Skor rata-rata hanya menghitung subbab yang ditulis agen; tulisan Anda sendiri ditampilkan terpisah.",
    }


# ---------------- kemiripan dengan literatur terbuka ----------------

MAX_QUERIES = 24
PER_SECTION = 3
PHRASE_WORDS = 10
_STOP = set("the of and to in a is that for with as on by this are be was were it from or an at which their they has have not can dan yang di ke dari untuk dengan pada ini itu adalah dalam sebagai oleh juga atau akan dapat serta bahwa para".split())


def candidate_phrases(text: str) -> list[str]:
    """Frasa 10 kata dari kalimat yang paling 'bermuatan' (banyak kata isi), tanpa penanda sitasi dan angka sela."""
    out = []
    for sent in _SENT.split(_clean(text)):
        toks = _WORD.findall(sent)
        if len(toks) < PHRASE_WORDS + 4:
            continue
        start = max(0, (len(toks) - PHRASE_WORDS) // 2)
        window = toks[start : start + PHRASE_WORDS]
        content = sum(1 for w in window if w.lower() not in _STOP and not w.isdigit())
        if content >= PHRASE_WORDS - 4:
            out.append((content, " ".join(window)))
    out.sort(key=lambda x: -x[0])
    return [p for _, p in out]


async def _query(client: httpx.AsyncClient, phrase: str) -> dict:
    params = {"filter": f'fulltext.search:"{phrase}"', "per-page": 3, "select": "id,display_name,doi,publication_year", "mailto": settings.polite_email}
    if settings.openalex_api_key:
        params["api_key"] = settings.openalex_api_key
    res = await client.get("https://api.openalex.org/works", params=params)
    res.raise_for_status()
    return res.json()


async def web_check(thesis: Thesis, selected: list[Citation], client: httpx.AsyncClient | None = None) -> dict:
    jobs: list[tuple[str, str, str, str]] = []  # (kode, judul subbab, asal, frasa)
    for s in sorted(thesis.sections, key=lambda x: [int(p) if p.isdigit() else 0 for p in x.section_code.split(".")]):
        if len(_WORD.findall(s.content_markdown or "")) < MIN_WORDS:
            continue
        for ph in candidate_phrases(s.content_markdown)[:PER_SECTION]:
            jobs.append((s.section_code, s.section_title, s.origin or "GENERATED", ph))
    if len(jobs) > MAX_QUERIES:
        step = len(jobs) / MAX_QUERIES
        jobs = [jobs[int(i * step)] for i in range(MAX_QUERIES)]
    if not jobs:
        return {"checked": 0, "matches": [], "errors": 0, "note": "Belum ada subbab yang cukup panjang untuk diperiksa."}

    sel_dois = {clean_doi(c.doi) for c in selected if c.doi}
    sel_titles = {re.sub(r"\W+", " ", (c.title or "").lower()).strip() for c in selected}
    sem = asyncio.Semaphore(4)
    own = client is None
    client = client or httpx.AsyncClient(timeout=20, headers={"User-Agent": "Skripsa/1.0"})

    async def run(job):
        async with sem:
            try:
                return job, await _query(client, job[3]), None
            except (httpx.HTTPError, ValueError) as exc:
                return job, None, str(exc)

    try:
        results = await asyncio.gather(*[run(j) for j in jobs])
    finally:
        if own:
            await client.aclose()

    errors = sum(1 for _, _, e in results if e)
    if errors == len(results):
        raise RuntimeError("OpenAlex tidak dapat dijangkau atau menolak permintaan. Periksa kunci OpenAlex di backend/.env.")
    matches = []
    for (code, title, origin, phrase), data, err in results:
        if err or not data:
            continue
        hits = data.get("results") or []
        if not hits:
            continue
        w = hits[0]
        doi = clean_doi(w.get("doi"))
        is_cited = bool((doi and doi in sel_dois) or re.sub(r"\W+", " ", (w.get("display_name") or "").lower()).strip() in sel_titles)
        matches.append(
            {
                "section": code,
                "section_title": title,
                "own_writing": origin == "IMPORTED",
                "phrase": phrase,
                "source_title": w.get("display_name") or "",
                "source_doi": doi,
                "source_year": w.get("publication_year"),
                "other_hits": max(0, int(((data.get("meta") or {}).get("count") or len(hits))) - 1),
                "in_your_references": is_cited,
            }
        )
    return {
        "checked": len(jobs),
        "errors": errors,
        "matches": matches,
        "note": "Kecocokan frasa 10 kata dengan teks lengkap karya akses terbuka. Frasa yang memang Anda kutip dan cantumkan di daftar pustaka wajar; selebihnya perlu diparafrasa dan disitasi.",
    }
