from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import owned_thesis
from app.core.ratelimit import limit_user
from app.schemas.schemas import ChartIn, DiagramIn
from app.services.charts import render_chart

router = APIRouter(prefix="/theses", tags=["charts"])

MAX_CHARTS = 40
MAX_DIAGRAMS = 40


@router.post("/{thesis_id}/charts")
def add_chart(
    payload: ChartIn,
    thesis=Depends(owned_thesis),
    db: Session = Depends(get_db),
):
    limit_user(thesis.user_id, "charts", 60, 60)
    if not payload.series:
        return {"ok": False, "detail": "series kosong"}
    if len(thesis.charts_json or []) >= MAX_CHARTS:
        raise HTTPException(422, f"Maksimal {MAX_CHARTS} grafik per skripsi")
    image = render_chart(payload.model_dump())
    entry = {"id": str(uuid4()), **payload.model_dump(), "image": image}
    thesis.charts_json = (thesis.charts_json or []) + [entry]
    db.commit()
    return {"ok": True, "total_charts": len(thesis.charts_json), "chart_id": entry["id"], "image": image}


@router.get("/{thesis_id}/charts")
def list_charts(thesis=Depends(owned_thesis), db: Session = Depends(get_db)):
    return thesis.charts_json or []


@router.delete("/{thesis_id}/charts/{chart_id}")
def remove_chart(
    chart_id: str,
    thesis=Depends(owned_thesis),
    db: Session = Depends(get_db),
):
    charts = [c for c in (thesis.charts_json or []) if c.get("id") != chart_id]
    thesis.charts_json = charts
    db.commit()
    return {"ok": True, "total_charts": len(charts)}


@router.post("/{thesis_id}/diagrams")
def add_diagram(
    payload: DiagramIn,
    thesis=Depends(owned_thesis),
    db: Session = Depends(get_db),
):
    limit_user(thesis.user_id, "diagrams", 60, 60)
    if len(thesis.diagrams_json or []) >= MAX_DIAGRAMS:
        raise HTTPException(422, f"Maksimal {MAX_DIAGRAMS} diagram per skripsi")
    entry = {"id": str(uuid4()), **payload.model_dump()}
    thesis.diagrams_json = (thesis.diagrams_json or []) + [entry]
    db.commit()
    return {"ok": True, "diagram_id": entry["id"], "total_diagrams": len(thesis.diagrams_json)}


@router.delete("/{thesis_id}/diagrams/{diagram_id}")
def remove_diagram(
    diagram_id: str,
    thesis=Depends(owned_thesis),
    db: Session = Depends(get_db),
):
    thesis.diagrams_json = [d for d in (thesis.diagrams_json or []) if d.get("id") != diagram_id]
    db.commit()
    return {"ok": True, "total_diagrams": len(thesis.diagrams_json)}
