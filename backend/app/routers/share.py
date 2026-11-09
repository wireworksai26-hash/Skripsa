import hashlib

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.ratelimit import limit_request
from app.models.models import Citation, ShareComment, Thesis
from app.services.citation import bibliography

router = APIRouter(prefix="/share", tags=["share"])

MAX_COMMENTS = 300


def _by_token(db: Session, token: str) -> Thesis:
    if not token or len(token) < 20:
        raise HTTPException(404, "Tautan tidak berlaku")
    t = db.query(Thesis).filter(Thesis.share_token == token).first()
    if not t:
        raise HTTPException(404, "Tautan tidak berlaku atau sudah dicabut")
    return t


def _key(code: str) -> list[int]:
    return [int(p) if p.isdigit() else 0 for p in code.split(".")]


@router.get("/{token}")
def read_shared(token: str, request: Request, db: Session = Depends(get_db)):
    """Tampilan baca-saja untuk pembimbing: hanya judul, isi subbab, dan daftar pustaka. Tidak ada data akun."""
    limit_request(request, "share-read", 120, 60)
    t = _by_token(db, token)
    refs = db.query(Citation).filter(Citation.thesis_id == t.thesis_id, Citation.citation_id.in_(t.selected_ref_ids or [])).all()
    style = "APA_7TH"
    try:
        biblio = bibliography(
            [{"title": r.title, "authors": r.authors or [], "publication_year": r.publication_year, "journal_name": r.journal_name, "volume_issue": r.volume_issue, "page_range": r.page_range, "doi": r.doi} for r in refs],
            style,
        )
    except Exception:
        biblio = [f"{(r.authors or ['Anonim'])[0]} ({r.publication_year}). {r.title}" for r in refs]
    comments = db.query(ShareComment).filter(ShareComment.thesis_id == t.thesis_id).order_by(ShareComment.created_at).all()
    return {
        "title": t.title,
        "language": t.language,
        "author": (t.owner.full_name if t.owner else ""),
        "sections": [
            {"code": s.section_code, "title": s.section_title, "content": s.content_markdown}
            for s in sorted(t.sections, key=lambda s: _key(s.section_code))
            if (s.content_markdown or "").strip()
        ],
        "bibliography": biblio,
        "comments": [{"comment_id": c.comment_id, "section_code": c.section_code, "author": c.author, "text": c.text, "resolved": c.resolved, "created_at": c.created_at.isoformat() if c.created_at else ""} for c in comments],
    }


class CommentIn(BaseModel):
    section_code: str = Field(default="", max_length=20)
    author: str = Field(default="Pembimbing", max_length=80)
    text: str = Field(min_length=2, max_length=1500)


@router.post("/{token}/comments", status_code=201)
def add_comment(
    token: str,
    payload: CommentIn,
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    token_key = hashlib.sha256(token.encode()).hexdigest()[:16]
    limit_request(request, f"share-comment:{token_key}", 30, 3600)
    t = _by_token(db, token)
    if db.query(ShareComment).filter(ShareComment.thesis_id == t.thesis_id).count() >= MAX_COMMENTS:
        raise HTTPException(429, "Batas komentar tercapai")
    if payload.section_code and payload.section_code not in {s.section_code for s in t.sections}:
        raise HTTPException(422, "Subbab tidak dikenal")
    c = ShareComment(thesis_id=t.thesis_id, section_code=payload.section_code, author=payload.author.strip() or "Pembimbing", text=payload.text.strip())
    db.add(c)
    db.commit()
    owner = t.owner
    if owner:
        from app.services import push

        background.add_task(
            push.notify_user,
            owner,
            "review",
            "Komentar baru dari pembimbing",
            f"{c.author}: {c.text[:90]}",
            "/proyek/6-review",
        )
    return {"comment_id": c.comment_id}
