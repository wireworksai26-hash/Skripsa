import traceback
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models.models import Citation, PipelineJob, RagDocument, Thesis, ThesisSection
from app.services import push
from app.services.agents import panel, rag, titles, writer
from app.services.agents.context import brief_for_chapter, context_keywords, other_texts, results_data, sections_digest
from app.services.scientific_api import verify_doi
from app.services.templates import localize_template, resolve_template
from app.services.vectorestore import get_vectorstore


def _sections_from_template(template: dict) -> list[dict]:
    return [
        {
            "chapter_code": str(ch["chapter_number"]),
            "section_code": s["code"],
            "section_title": s["title"],
            "target_words": s["target_words"],
        }
        for ch in template["chapters"]
        for s in ch["sub_sections"]
    ]


def create_job(db: Session, thesis_id: str) -> PipelineJob:
    job = PipelineJob(job_id=str(uuid4()), thesis_id=thesis_id, status="QUEUED", logs=[])
    db.add(job)
    db.commit()
    return job


class _Job:
    def __init__(self, job_id: str) -> None:
        self.job_id = job_id

    def log(self, message: str) -> None:
        db = SessionLocal()
        try:
            job = db.get(PipelineJob, self.job_id)
            if job:
                logs = job.logs or []
                logs.append(message)
                job.logs = logs
                db.commit()
        finally:
            db.close()

    def step(self, name: str) -> None:
        db = SessionLocal()
        try:
            job = db.get(PipelineJob, self.job_id)
            if job:
                job.current_step = name
                job.status = "RUNNING"
                logs = job.logs or []
                logs.append(f"▶ {name}")
                job.logs = logs
                db.commit()
        finally:
            db.close()

    def finish(self, error: str | None = None) -> None:
        from datetime import datetime, timezone

        db = SessionLocal()
        try:
            job = db.get(PipelineJob, self.job_id)
            if job:
                job.status = "FAILED" if error else "COMPLETED"
                job.error = error
                job.finished_at = datetime.now(timezone.utc)
                logs = job.logs or []
                logs.append(("✗ " + error) if error else "✓ selesai")
                job.logs = logs
                db.commit()
        finally:
            db.close()


async def run_pipeline(job_id: str, thesis_id: str) -> None:
    job = _Job(job_id)
    try:
        db = SessionLocal()
        try:
            thesis = db.get(Thesis, thesis_id)
            if not thesis:
                job.finish("Thesis tidak ditemukan")
                return

            # 1. Campus Template Agent — outline subbab
            job.step("Campus Template Agent · outline subbab")
            template = localize_template(resolve_template(db, thesis.campus_template_id), thesis.language or "id")
            existing = {s.section_code for s in thesis.sections}
            for plan in _sections_from_template(template):
                if plan["section_code"] in existing:
                    continue
                db.add(
                    ThesisSection(
                        thesis_id=thesis_id,
                        chapter_code=plan["chapter_code"],
                        section_code=plan["section_code"],
                        section_title=plan["section_title"],
                        target_words=plan["target_words"],
                        content_markdown="",
                        citations_json=[],
                    )
                )
            db.commit()
            db.refresh(thesis)
            db.expire(thesis, ["sections"])
            job.log(f"{len(thesis.sections)} subbab siap dari template {template['campus_name']}")

            # 2. Literature RAG — indeks abstrak artikel terpilih
            job.step("Literature RAG Agent · indeks abstrak")
            store = get_vectorstore()
            refs = db.query(Citation).filter(Citation.thesis_id == thesis_id).all()
            picked = [r for r in refs if r.citation_id in (thesis.selected_ref_ids or [])]
            for r in picked:
                text = f"{r.title}. {r.journal_name or ''}. {r.highlighted_snippet or ''}"
                if r.doi:
                    alive = await verify_doi(r.doi)
                    if alive:
                        db.add(RagDocument(doc_id=f"rag-{r.citation_id}", thesis_id=thesis_id, source_type="citation", content=text, meta_json={"citation_id": r.citation_id}))
                else:
                    db.add(RagDocument(doc_id=f"rag-{r.citation_id}", thesis_id=thesis_id, source_type="citation", content=text, meta_json={"citation_id": r.citation_id}))
            db.commit()
            job.log(f"{len(picked)} artikel terindeks (vector dim {store.size()})")

            # 3. Academic Writer Agent — draf per subbab
            job.step("Academic Writer Agent · draf per subbab")
            picked_title = thesis.title
            ctx_keywords = context_keywords(
                {
                    "topic": thesis.title,
                    "variable_x": thesis.variable_x,
                    "variable_y": thesis.variable_y,
                    "subject": thesis.subject,
                },
                picked_title,
            )
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
                for r in picked
            ]
            if not ref_dicts:
                job.finish("Pilih minimal satu rujukan sebelum menjalankan pipeline")
                return
            count = 0
            used: set[str] = set()
            for section in thesis.sections:
                if section.origin == "IMPORTED" or writer.valid_word_count(section.content_markdown or "") >= 10:
                    continue  # tulisan pengguna tidak disentuh
                draft, provider = await writer.generate_section_draft(
                    {
                        "chapter_code": section.chapter_code,
                        "section_code": section.section_code,
                        "section_title": section.section_title,
                        "target_words": section.target_words,
                    },
                    {
                        "topic": thesis.title,
                        "variable_x": thesis.variable_x,
                        "variable_y": thesis.variable_y,
                        "subject": thesis.subject,
                        "method": thesis.research_method,
                        "language": thesis.language or "id",
                        "existing_digest": sections_digest(thesis.sections, section.section_code),
                        "brief": brief_for_chapter(thesis, section.chapter_code),
                        "other_texts": other_texts(thesis.sections, section.section_code),
                        "results_data": results_data(thesis),
                    },
                    rag.retrieve(
                        ref_dicts,
                        " ".join(p for p in (section.section_title, thesis.title, thesis.variable_x, thesis.variable_y) if p),
                    ),
                    template.get("citation_style", "APA_7TH"),
                    ctx_keywords,
                )
                section.content_markdown = draft["content"]
                section.citations_json = draft["citations"]
                section.word_count = writer.valid_word_count(draft["content"])
                used.add(provider)
                count += 1
            db.commit()
            job.log(f"{count} subbab draf ditulis oleh {', '.join(sorted(used)) or '-'}")

            # 4. Advisor + Examiner + Guardrail
            job.step("Advisor & Examiner & Guardrail · review")
            db.expire(thesis, ["sections"])
            reviews = await panel.run_panel(thesis, db)
            thesis.review_json = {
                k: {kk: vv for kk, vv in v.items() if kk != "agent"} for k, v in reviews.items()
            }
            thesis.status = "DRAF_FINAL"
            db.commit()
            job.log("review tersimpan pada thesis.review_json")

            await push.notify_user(thesis.owner, "draft", "Draf skripsi selesai", f"{count} subbab ditulis. Buka untuk memeriksa hasil dan skor review.", "/proyek/6-review")
            job.finish(None)
        finally:
            db.close()
    except Exception as exc:  # pragma: no cover — safety net
        traceback.print_exc()
        job.finish(str(exc))


async def run_titles_only(db: Session, thesis: Thesis) -> tuple[list[dict], str]:
    form = {
        "topic": thesis.title,
        "variable_x": thesis.variable_x,
        "variable_y": thesis.variable_y,
        "subject": thesis.subject,
        "method": thesis.research_method,
        "domain": thesis.domain_category,
        "degree_level": thesis.degree_level,
        "language": thesis.language or "id",
    }
    return await titles.generate_titles(form)
