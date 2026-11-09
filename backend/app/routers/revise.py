from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import owned_thesis
from app.models.models import Citation, SectionVersion, Thesis, ThesisSection
from app.services.agents import rag, reviser
from app.services.agents.context import context_keywords, other_texts, sections_digest
from app.services.agents.writer import valid_word_count
from app.services.templates import resolve_template

router = APIRouter(prefix="/theses", tags=["revise"])

MAX_VERSIONS_PER_SECTION = 10


class ReviseIn(BaseModel):
    feedback: list[str] = Field(min_length=1, max_length=14)
    include_imported: bool = False


def snapshot(db: Session, section: ThesisSection, reason: str) -> SectionVersion | None:
    """Simpan isi saat ini agar bisa diurungkan. Subbab kosong tidak perlu disimpan."""
    if not (section.content_markdown or "").strip():
        return None
    row = SectionVersion(
        thesis_id=section.thesis_id,
        section_id=section.section_id,
        section_code=section.section_code,
        content_markdown=section.content_markdown,
        citations_json=section.citations_json or [],
        reason=reason,
    )
    db.add(row)
    db.flush()
    old = (
        db.query(SectionVersion)
        .filter(SectionVersion.section_id == section.section_id)
        .order_by(SectionVersion.created_at.desc(), SectionVersion.version_id)
        .offset(MAX_VERSIONS_PER_SECTION)
        .all()
    )
    for o in old:
        db.delete(o)
    return row


def _find(db: Session, thesis: Thesis, code: str) -> ThesisSection:
    section = (
        db.query(ThesisSection)
        .filter(ThesisSection.thesis_id == thesis.thesis_id, ThesisSection.section_code == code)
        .first()
    )
    if not section:
        raise HTTPException(404, "Subbab tidak ditemukan")
    return section


def _out(section: ThesisSection, **extra) -> dict:
    return {
        "section_code": section.section_code,
        "content_markdown": section.content_markdown,
        "citations_json": section.citations_json or [],
        "word_count": section.word_count,
        **extra,
    }


@router.post("/{thesis_id}/sections/{section_code}/revise")
async def revise(
    section_code: str,
    payload: ReviseIn,
    thesis: Thesis = Depends(owned_thesis),
    db: Session = Depends(get_db),
):
    section = _find(db, thesis, section_code)
    if valid_word_count(section.content_markdown or "") < 10:
        raise HTTPException(422, "Subbab ini belum berisi draf; buat dulu sebelum diperbaiki")
    if section.origin == "IMPORTED" and not payload.include_imported:
        raise HTTPException(409, "Subbab ini berisi tulisan Anda. Setujui perbaikan atas tulisan Anda (include_imported=true).")

    refs_rows = (
        db.query(Citation)
        .filter(Citation.thesis_id == thesis.thesis_id, Citation.citation_id.in_(thesis.selected_ref_ids or []))
        .all()
    )
    if not refs_rows:
        raise HTTPException(422, "Pilih minimal satu rujukan (Langkah 3) sebelum memperbaiki naskah")
    ref_dicts = [
        {
            "citation_id": r.citation_id, "doi": r.doi, "title": r.title, "authors": r.authors,
            "publication_year": r.publication_year, "journal_name": r.journal_name, "highlighted_snippet": r.highlighted_snippet,
        }
        for r in refs_rows
    ]
    query = " ".join(p for p in (section.section_title, thesis.title, thesis.variable_x, thesis.variable_y, *payload.feedback[:3]) if p)
    ranked = rag.retrieve(ref_dicts, query)
    template = resolve_template(db, thesis.campus_template_id)

    draft, changes, provider = await reviser.revise_section(
        {"section_code": section.section_code, "section_title": section.section_title, "target_words": section.target_words, "content": section.content_markdown},
        {
            "title": thesis.title, "variable_x": thesis.variable_x, "variable_y": thesis.variable_y, "subject": thesis.subject,
            "method": thesis.research_method, "existing_digest": sections_digest(thesis.sections, section.section_code),
            "others": other_texts(thesis.sections, section.section_code),
            "keywords": context_keywords({"topic": thesis.title, "variable_x": thesis.variable_x, "variable_y": thesis.variable_y, "subject": thesis.subject}, thesis.title),
        },
        [f.strip()[:1200] for f in payload.feedback if f.strip()],
        ranked,
        template.get("citation_style", "APA_7TH"),
    )
    before = section.word_count or valid_word_count(section.content_markdown)
    version = snapshot(db, section, "revisi")
    section.content_markdown = draft["content"]
    section.citations_json = draft["citations"]
    section.word_count = valid_word_count(draft["content"])
    section.version_number += 1
    db.commit()
    return _out(section, provider=provider, changes=changes, before_words=before, can_undo=version is not None)


@router.post("/{thesis_id}/sections/{section_code}/undo")
def undo(section_code: str, thesis: Thesis = Depends(owned_thesis), db: Session = Depends(get_db)):
    section = _find(db, thesis, section_code)
    last = (
        db.query(SectionVersion)
        .filter(SectionVersion.section_id == section.section_id)
        .order_by(SectionVersion.created_at.desc(), SectionVersion.version_id)
        .first()
    )
    if not last:
        raise HTTPException(404, "Tidak ada versi sebelumnya untuk dikembalikan")
    section.content_markdown = last.content_markdown
    section.citations_json = last.citations_json or []
    section.word_count = valid_word_count(last.content_markdown)
    section.version_number += 1
    db.delete(last)
    db.commit()
    remaining = db.query(SectionVersion).filter(SectionVersion.section_id == section.section_id).count()
    return _out(section, can_undo=remaining > 0)
