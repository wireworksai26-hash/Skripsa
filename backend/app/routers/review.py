from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.models import Thesis
from app.core.deps import owned_thesis
from app.services import push
from app.services.agents import panel

router = APIRouter(prefix="/theses", tags=["review"])


@router.post("/{thesis_id}/review")
async def run_review(thesis: Thesis = Depends(owned_thesis), db: Session = Depends(get_db)):
    reviews = await panel.run_panel(thesis, db)
    thesis.review_json = {k: {kk: vv for kk, vv in v.items() if kk != "agent"} for k, v in reviews.items()}
    db.commit()
    scores = [v["score"] for v in reviews.values() if v.get("score") is not None]
    summary = "Skor: " + ", ".join(f"{k.title()} {v['score']}" for k, v in reviews.items() if v.get("score") is not None) if scores else "Panel review selesai."
    await push.notify_user(thesis.owner, "review", "Review selesai", summary, "/proyek/6-review")
    return {"ok": True, "reviews": reviews}
