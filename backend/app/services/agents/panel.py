from sqlalchemy.orm import Session

from app.models.models import Thesis
from app.services.agents import advisor, guardrail, review


async def run_panel(thesis: Thesis, db: Session) -> dict:
    """Guardrail lebih dulu (fakta deterministik), lalu Advisor memakainya sebagai batas skor, lalu Examiner."""
    rail = await guardrail.guardrail_review(thesis, db)
    adv = await advisor.advisor_review(thesis, db, rail)
    exam = await review.examiner_review(thesis, db)
    return {"ADVISOR": adv, "EXAMINER": exam, "GUARDRAIL": rail}
