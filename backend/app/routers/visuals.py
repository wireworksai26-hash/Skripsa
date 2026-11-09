from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import owned_thesis
from app.models.models import Citation, Thesis
from app.services.agents import visual_planner
from app.services.agents.context import results_data
from app.services.templates import localize_template, resolve_template

router = APIRouter(prefix="/theses", tags=["visuals"])


class PlanIn(BaseModel):
    chapters: list[str] = Field(default_factory=list, max_length=12)
    extra: str = Field(default="", max_length=500)


@router.post("/{thesis_id}/visuals/plan")
async def plan(payload: PlanIn, thesis: Thesis = Depends(owned_thesis), db: Session = Depends(get_db)):
    """Usulan tabel & diagram per bab. Hanya saran: tidak ada yang disimpan sebelum pengguna menyetujuinya."""
    language = thesis.language or "id"
    template = localize_template(resolve_template(db, thesis.campus_template_id), language)
    by_chapter: dict[str, list] = {}
    for s in thesis.sections:
        by_chapter.setdefault(s.chapter_code, []).append(s)
    chapters = []
    for ch in template["chapters"]:
        code = str(ch["chapter_number"])
        written = [s for s in sorted(by_chapter.get(code, []), key=lambda x: x.section_code) if (s.content_markdown or "").strip()]
        chapters.append(
            {
                "code": code,
                "title": ch["chapter_title"],
                "sections": [s["title"] for s in ch["sub_sections"]],
                "excerpt": " | ".join(" ".join(s.content_markdown.split())[:160] for s in written[:3]),
            }
        )
    refs = [
        {
            "citation_id": r.citation_id, "title": r.title, "authors": r.authors, "publication_year": r.publication_year,
            "journal_name": r.journal_name, "highlighted_snippet": r.highlighted_snippet,
        }
        for r in db.query(Citation).filter(Citation.thesis_id == thesis.thesis_id, Citation.citation_id.in_(thesis.selected_ref_ids or [])).all()
    ]
    existing = (
        [t.title for t in thesis.tables]
        + [d.get("title", "") for d in (thesis.diagrams_json or [])]
        + [c.get("title", "") for c in (thesis.charts_json or [])]
    )
    only = {c for c in payload.chapters if c.isdigit()} or None
    items, provider = await visual_planner.plan_visuals(
        {
            "title": thesis.title, "method": thesis.research_method, "domain": thesis.domain_category, "degree_level": thesis.degree_level,
            "variable_x": thesis.variable_x, "variable_y": thesis.variable_y, "subject": thesis.subject, "language": language,
            "results_data": results_data(thesis),
        },
        chapters, refs, existing, only, payload.extra.strip(),
    )
    return {"items": items, "provider": provider}
