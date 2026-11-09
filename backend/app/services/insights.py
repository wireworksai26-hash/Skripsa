"""Pemeriksa kemiripan terhadap rujukan, target harian, dan streak menulis."""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.models import Citation, Thesis, WritingActivity
from app.services.agents.quality import _shingles, _tokens, paragraphs

FLAG_THRESHOLD = 0.5  # >= 50% 5-gram potongan rujukan muncul utuh di paragraf


def similarity_report(thesis: Thesis, db: Session) -> dict:
    """Bandingkan paragraf draf dengan judul + abstrak rujukan proyek. Menandai salinan nyaris persis tanpa tanda kutip."""
    refs = db.query(Citation).filter(Citation.thesis_id == thesis.thesis_id).all()
    sources = []
    for r in refs:
        sh = _shingles(f"{r.title}. {r.highlighted_snippet or ''}")
        if len(sh) >= 3:
            sources.append((r, sh))
    out, overall = [], 0.0
    for s in sorted(thesis.sections, key=lambda x: [int(p) if p.isdigit() else 0 for p in x.section_code.split(".")]):
        flagged, peak = [], 0.0
        for p in paragraphs(s.content_markdown or ""):
            if len(_tokens(p)) < 12:
                continue
            ps = _shingles(p)
            best = (0.0, None)
            for r, sh in sources:
                score = len(ps & sh) / min(len(ps), len(sh)) if ps and sh else 0.0
                if score > best[0]:
                    best = (score, r)
            peak = max(peak, best[0])
            if best[0] >= FLAG_THRESHOLD and best[1] is not None:
                a = (best[1].authors or ["Anonim"])[0]
                flagged.append({"excerpt": p[:180], "score": round(best[0], 2), "source": f"{a} ({best[1].publication_year}). {best[1].title}"})
        if (s.content_markdown or "").strip():
            overall = max(overall, peak)
            out.append({"code": s.section_code, "title": s.section_title, "peak": round(peak, 2), "flagged": flagged, "imported": s.origin == "IMPORTED"})
    return {"sections": out, "overall_peak": round(overall, 2), "sources_compared": len(sources), "threshold": FLAG_THRESHOLD}


def record_words(db: Session, user_id: str, delta: int, today: date | None = None) -> None:
    """Tambah kata yang ditulis hari ini. Penghapusan tidak mengurangi (hanya penambahan yang dihitung)."""
    if delta <= 0:
        return
    day = (today or date.today()).isoformat()
    row = db.query(WritingActivity).filter(WritingActivity.user_id == user_id, WritingActivity.day == day).first()
    if row:
        row.words += delta
    else:
        db.add(WritingActivity(user_id=user_id, day=day, words=delta))


def activity_summary(db: Session, user, today: date | None = None, days: int = 14) -> dict:
    today = today or date.today()
    rows = db.query(WritingActivity).filter(WritingActivity.user_id == user.user_id).all()
    by_day = {r.day: r.words for r in rows}
    goal = user.daily_goal or 300
    series = [{"day": (today - timedelta(days=i)).isoformat(), "words": by_day.get((today - timedelta(days=i)).isoformat(), 0)} for i in range(days - 1, -1, -1)]
    # Streak: hari berturut-turut yang mencapai target, dihitung mundur; hari ini yang belum tercapai tidak memutus.
    streak, cursor = 0, today
    if by_day.get(today.isoformat(), 0) < goal:
        cursor = today - timedelta(days=1)
    while by_day.get(cursor.isoformat(), 0) >= goal:
        streak += 1
        cursor -= timedelta(days=1)
    return {"goal": goal, "today": by_day.get(today.isoformat(), 0), "streak": streak, "series": series, "total": sum(by_day.values())}
