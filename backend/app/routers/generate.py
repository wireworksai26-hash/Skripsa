from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import owned_thesis
from app.core.ratelimit import limit_user
from app.models.models import TitleOption
from app.schemas.schemas import GenerateOut
from app.services.agents import rag, writer
from app.services.agents.context import brief_for_chapter, context_keywords, mirror_fields, other_texts, results_data, section_plan, sections_digest
from app.services.pipeline import create_job, run_pipeline, run_titles_only
from app.services.templates import resolve_template

router = APIRouter(prefix="/theses", tags=["generate"])


async def _titles(thesis, db: Session):
    options, provider = await run_titles_only(db, thesis)
    stale = db.query(TitleOption).filter(TitleOption.thesis_id == thesis.thesis_id)
    if thesis.source_mode == "EXISTING" and thesis.picked_title_id:
        # Judul milik pengguna tetap ada di daftar; yang dibuat ulang hanyalah alternatifnya.
        stale = stale.filter(TitleOption.title_id != thesis.picked_title_id)
    stale.delete()
    for opt in options:
        db.add(
            TitleOption(
                thesis_id=thesis.thesis_id,
                text=opt["text"],
                rationale=opt.get("rationale", ""),
                gap=opt.get("gap", ""),
            )
        )
    db.commit()
    rows = db.query(TitleOption).filter(TitleOption.thesis_id == thesis.thesis_id).all()
    return [
        {"title_id": t.title_id, "text": t.text, "rationale": t.rationale, "gap": t.gap}
        for t in rows
    ], provider


@router.post("/{thesis_id}/titles")
async def generate_titles(thesis=Depends(owned_thesis), db: Session = Depends(get_db)):
    limit_user(thesis.user_id, "generate-titles", 20, 60)
    titles, provider = await _titles(thesis, db)
    return {"provider": provider, "titles": titles}


@router.post("/{thesis_id}/sections/{section_code}/generate")
async def generate_section(
    section_code: str,
    overwrite: bool = False,
    thesis=Depends(owned_thesis),
    db: Session = Depends(get_db),
):
    from app.models.models import Citation, ThesisSection

    limit_user(thesis.user_id, "generate-section", 20, 60)
    section = (
        db.query(ThesisSection)
        .filter(ThesisSection.thesis_id == thesis.thesis_id, ThesisSection.section_code == section_code)
        .first()
    )
    if not section:
        raise HTTPException(404, "Subbab belum ada — panggil /sections/build dulu")
    if section.origin == "IMPORTED" and (section.content_markdown or "").strip() and not overwrite:
        raise HTTPException(409, "Subbab ini berisi tulisan Anda. Konfirmasi penimpaan (overwrite=true) bila ingin diganti draf baru.")

    refs_rows = (
        db.query(Citation)
        .filter(
            Citation.thesis_id == thesis.thesis_id,
            Citation.citation_id.in_(thesis.selected_ref_ids or []),
        )
        .all()
    )
    template = resolve_template(db, thesis.campus_template_id)
    if not refs_rows:
        raise HTTPException(422, "Pilih minimal satu rujukan (Langkah 3) sebelum membuat draf")

    ref_dicts = [
        {
            "citation_id": r.citation_id,
            "doi": r.doi,
            "title": r.title,
            "authors": r.authors,
            "publication_year": r.publication_year,
            "journal_name": r.journal_name,
            "volume_issue": r.volume_issue,
            "page_range": r.page_range,
            "highlighted_snippet": r.highlighted_snippet,
        }
        for r in refs_rows
    ]
    query = " ".join(
        p for p in (section.section_title, thesis.title, thesis.variable_x, thesis.variable_y, thesis.subject) if p
    )
    ref_dicts = rag.retrieve(ref_dicts, query)
    draft, provider = await writer.generate_section_draft(
        section_plan(thesis.sections, section),
        {
            "topic": thesis.title,
            "variable_x": thesis.variable_x,
            "variable_y": thesis.variable_y,
            "subject": thesis.subject,
            "method": thesis.research_method,
            "language": thesis.language or "id",
            "existing_digest": sections_digest(thesis.sections, section.section_code),
            "brief": brief_for_chapter(thesis, section.chapter_code, section.section_title),
            "other_texts": other_texts(thesis.sections, section.section_code),
            "results_data": results_data(thesis),
            **mirror_fields(thesis, section),
        },
        ref_dicts,
        template.get("citation_style", "APA_7TH"),
        context_keywords(
            {"topic": thesis.title, "variable_x": thesis.variable_x, "variable_y": thesis.variable_y, "subject": thesis.subject},
            thesis.title,
        ),
    )
    old_content = section.content_markdown
    from app.routers.revise import snapshot

    snapshot(db, section, "buat ulang")
    section.content_markdown = draft["content"]
    section.citations_json = draft["citations"]
    from app.services.insights import record_words

    record_words(db, thesis.user_id, writer.valid_word_count(draft["content"]) - (section.word_count or 0))
    section.word_count = writer.valid_word_count(draft["content"])
    section.origin = "GENERATED"
    if old_content and old_content != draft["content"]:
        section.version_number += 1
    db.commit()

    return GenerateOut(
        section_id=section.section_id,
        section_code=section.section_code,
        content_markdown=section.content_markdown,
        citations_json=section.citations_json or [],
        word_count=section.word_count,
        provider=provider,
    )


@router.post("/{thesis_id}/pipeline/run")
def run_full_pipeline(
    background: BackgroundTasks,
    thesis=Depends(owned_thesis),
    db: Session = Depends(get_db),
):
    limit_user(thesis.user_id, "pipeline-run", 3, 60)
    job = create_job(db, thesis.thesis_id)
    background.add_task(run_pipeline, job.job_id, thesis.thesis_id)
    return {"job_id": job.job_id, "status": "QUEUED"}


@router.get("/{thesis_id}/pipeline/jobs/{job_id}")
def job_status(job_id: str, thesis=Depends(owned_thesis), db: Session = Depends(get_db)):
    from app.models.models import PipelineJob

    job = db.get(PipelineJob, job_id)
    if not job or job.thesis_id != thesis.thesis_id:
        raise HTTPException(404, "Job tidak ditemukan")
    return {
        "job_id": job.job_id,
        "status": job.status,
        "current_step": job.current_step,
        "logs": job.logs or [],
        "error": job.error,
    }
