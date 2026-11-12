"""Editor struktur bab per proyek: tambah, hapus, ganti nama, urutkan, dan beri tingkat 3 (2.1.1) pada subbab.

Struktur disimpan sebagai templat kustom milik proyek (custom-<thesis_id>) sehingga ekspor, pipeline, dan visual
memakai jalur templat yang sama. Isi subbab yang dipertahankan ikut berpindah ke kode barunya.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import owned_thesis
from app.core.ratelimit import limit_user
from app.models.models import CustomTemplate, Thesis, ThesisSection
from app.services.agents import outline
from app.services.agents.documents import GenerationError
from app.services.templates import resolve_template

router = APIRouter(prefix="/theses", tags=["structure"])

MAX_CHAPTERS = 12
MAX_PER_CHAPTER = 30


class SectionIn(BaseModel):
    code: str | None = None  # kode lama bila subbab sudah ada; kosong = subbab baru
    title: str = Field(min_length=1, max_length=140)
    target_words: int = Field(default=400, ge=50, le=4000)
    level: int = Field(default=1, ge=1, le=2)  # 1 = 2.1, 2 = 2.1.1


class ChapterIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    sections: list[SectionIn] = Field(default_factory=list, max_length=MAX_PER_CHAPTER)


class StructureIn(BaseModel):
    chapters: list[ChapterIn] = Field(min_length=1, max_length=MAX_CHAPTERS)
    confirm_delete: bool = False


def _word_count(text: str) -> int:
    return len([w for w in (text or "").split() if any(c.isalnum() for c in w)])


def compute_codes(chapters: list[ChapterIn]) -> list[list[str]]:
    """Kode per subbab: tingkat 1 = N.k, tingkat 2 = N.k.m di bawah tingkat 1 sebelumnya."""
    out: list[list[str]] = []
    for n, ch in enumerate(chapters, start=1):
        codes, k, m = [], 0, 0
        for s in ch.sections:
            if s.level == 2:
                if k == 0:
                    raise HTTPException(422, f"Bab {n}: subbab tingkat 2 harus berada di bawah subbab tingkat 1")
                m += 1
                codes.append(f"{n}.{k}.{m}")
            else:
                k += 1
                m = 0
                codes.append(f"{n}.{k}")
        out.append(codes)
    return out


class SuggestIn(BaseModel):
    chapters: list[str] = Field(default_factory=list, max_length=MAX_CHAPTERS)  # nomor bab; kosong = semua


@router.post("/{thesis_id}/structure/suggest")
async def suggest_subsections(payload: SuggestIn, thesis: Thesis = Depends(owned_thesis), db: Session = Depends(get_db)):
    """Usulan sub-subbab (2.1.1) dari agen. Tidak mengubah data: pengguna meninjau lalu menyimpan lewat PUT /structure."""
    limit_user(thesis.user_id, "structure-suggest", 10, 60)
    try:
        return await outline.propose(thesis, db, payload.chapters)
    except GenerationError as exc:
        raise HTTPException(503, str(exc))


@router.put("/{thesis_id}/structure")
def save_structure(payload: StructureIn, thesis: Thesis = Depends(owned_thesis), db: Session = Depends(get_db)):
    codes = compute_codes(payload.chapters)
    existing = {s.section_code: s for s in thesis.sections}

    referenced: set[str] = set()
    for ch in payload.chapters:
        for s in ch.sections:
            if s.code is None:
                continue
            if s.code not in existing:
                raise HTTPException(422, f"Subbab {s.code} tidak ditemukan")
            if s.code in referenced:
                raise HTTPException(422, f"Subbab {s.code} muncul dua kali")
            referenced.add(s.code)

    removed = [s for c, s in existing.items() if c not in referenced]
    with_text = [s.section_code for s in removed if _word_count(s.content_markdown) > 0]
    if with_text and not payload.confirm_delete:
        raise HTTPException(409, f"Subbab berisi tulisan akan dihapus: {', '.join(sorted(with_text))}. Konfirmasi untuk melanjutkan.")

    # Fase 1: kosongkan kode lama agar penomoran ulang tidak bentrok dengan indeks unik.
    for s in removed:
        db.delete(s)
    for s in thesis.sections:
        if s.section_code in referenced:
            s.section_code = f"~{s.section_id[:12]}"
    db.flush()

    # Fase 2: kode final, judul, bab, target kata; subbab baru dibuat kosong.
    by_old = {c: s for c, s in existing.items() if c in referenced}
    for ch_no, (ch, ch_codes) in enumerate(zip(payload.chapters, codes), start=1):
        for plan, code in zip(ch.sections, ch_codes):
            row = by_old.get(plan.code) if plan.code else None
            if row is None:
                row = ThesisSection(thesis_id=thesis.thesis_id, content_markdown="", citations_json=[])
                db.add(row)
            row.section_code = code
            row.chapter_code = str(ch_no)
            row.section_title = plan.title.strip()
            row.target_words = plan.target_words
    db.flush()

    # Templat milik proyek
    base = resolve_template(db, thesis.campus_template_id)
    spec = {
        **{k: v for k, v in base.items() if k not in ("campus_id", "is_custom")},
        "campus_name": f"Struktur proyek: {thesis.title[:60]}",
        "project_scoped": True,
        "chapters": [
            {
                "chapter_number": str(n),
                "chapter_title": ch.title.strip(),
                "sub_sections": [
                    {"code": code, "title": s.title.strip(), "target_words": s.target_words}
                    for s, code in zip(ch.sections, ch_codes)
                ],
            }
            for n, (ch, ch_codes) in enumerate(zip(payload.chapters, codes), start=1)
        ],
    }
    tid = f"custom-{thesis.thesis_id}"
    row = db.get(CustomTemplate, tid)
    if row:
        row.spec_json = spec
        row.name = spec["campus_name"]
    else:
        db.add(CustomTemplate(template_id=tid, user_id=thesis.user_id, name=spec["campus_name"], source_filename="", spec_json=spec, report_json={}))
    thesis.campus_template_id = tid
    db.commit()
    db.refresh(thesis)

    from app.routers.theses import _thesis_out

    return _thesis_out(thesis)
