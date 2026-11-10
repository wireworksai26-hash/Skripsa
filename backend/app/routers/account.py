"""Akun: ganti password, ekspor data, hapus akun, reset password, dan verifikasi email."""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.deps import auth_required
from app.core.ratelimit import limit_request, limit_user
from app.core.security import binder_of, create_purpose_token, hash_password, verify_password, verify_purpose_token
from app.models.models import CustomTemplate, User, WritingActivity
from app.services import mailer

router = APIRouter(prefix="/auth", tags=["account"])

RESET_TTL_MIN = 30
VERIFY_TTL_MIN = 60 * 24 * 3


class PasswordChangeIn(BaseModel):
    current_password: str = Field(max_length=1024)
    new_password: str = Field(min_length=8, max_length=1024)


class DeleteAccountIn(BaseModel):
    password: str = Field(max_length=1024)


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str = Field(max_length=4096)
    password: str = Field(min_length=8, max_length=1024)


class VerifyIn(BaseModel):
    token: str = Field(max_length=4096)


@router.put("/password", status_code=204)
def change_password(payload: PasswordChangeIn, user: User = Depends(auth_required), db: Session = Depends(get_db)):
    limit_user(user.user_id, "change-password", 5, 600)
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(403, "Password saat ini salah")
    user.password_hash = hash_password(payload.new_password)
    db.commit()


def _code_key(code: str) -> list[int]:
    return [int(p) if p.isdigit() else 0 for p in code.split(".")]


def _export_thesis(t) -> dict:
    return {
        "thesis_id": t.thesis_id,
        "title": t.title,
        "method": t.research_method,
        "domain": t.domain_category,
        "degree_level": t.degree_level,
        "language": t.language,
        "status": t.status,
        "variable_x": t.variable_x,
        "variable_y": t.variable_y,
        "subject": t.subject,
        "brief": t.brief_json,
        "cover": t.cover_json,
        "front_matter": t.front_json,
        "appendices": t.appendix_json,
        "reviews": t.review_json,
        "charts": t.charts_json,
        "diagrams": t.diagrams_json,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "sections": [
            {"code": s.section_code, "title": s.section_title, "content": s.content_markdown, "citations": s.citations_json, "origin": s.origin}
            for s in sorted(t.sections, key=lambda x: _code_key(x.section_code))
        ],
        "references": [
            {"title": c.title, "authors": c.authors, "year": c.publication_year, "journal": c.journal_name, "doi": c.doi, "source": c.source_database, "selected": c.citation_id in (t.selected_ref_ids or [])}
            for c in t.citations
        ],
        "tables": [{"title": x.title, "columns": x.columns_json, "rows": x.rows_json, "note": x.note, "chapter": x.chapter_code} for x in t.tables],
        "research_data": [{"title": d.title, "kind": d.kind, "content": d.content, "analysis": d.analysis_json} for d in t.research_data],
    }


@router.get("/export")
def export_my_data(user: User = Depends(auth_required), db: Session = Depends(get_db)):
    """Seluruh data milik pengguna dalam satu berkas JSON. Hash password tidak disertakan."""
    limit_user(user.user_id, "export-data", 5, 600)
    custom = db.query(CustomTemplate).filter(CustomTemplate.user_id == user.user_id).all()
    activity = db.query(WritingActivity).filter(WritingActivity.user_id == user.user_id).all()
    data = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "profile": {
            "full_name": user.full_name,
            "email": user.email,
            "nim": user.nim,
            "major": user.major_name,
            "faculty": user.faculty,
            "campus": user.campus_name,
            "city": user.city,
            "email_verified": user.email_verified,
            "daily_goal": user.daily_goal,
            "notify_prefs": user.notify_prefs,
            "has_logo": bool(user.logo_data),
        },
        "theses": [_export_thesis(t) for t in user.theses],
        "custom_templates": [{"name": c.name, "spec": c.spec_json} for c in custom if not (c.spec_json or {}).get("project_scoped")],
        "writing_activity": [{"day": a.day, "words": a.words} for a in sorted(activity, key=lambda x: x.day)],
    }
    return Response(
        json.dumps(data, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="skripsiai-data-saya.json"'},
    )


@router.delete("/account", status_code=204)
def delete_account(payload: DeleteAccountIn, user: User = Depends(auth_required), db: Session = Depends(get_db)):
    """Hapus akun beserta semua proyek, draf, data, dan komentar. Tidak bisa dibatalkan."""
    limit_user(user.user_id, "delete-account", 5, 600)
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(403, "Password salah")
    for tpl in db.query(CustomTemplate).filter(CustomTemplate.user_id == user.user_id).all():
        db.delete(tpl)
    for row in db.query(WritingActivity).filter(WritingActivity.user_id == user.user_id).all():
        db.delete(row)
    db.delete(user)  # proyek ikut terhapus (ORM cascade); tabel anak lain lewat ON DELETE CASCADE
    db.commit()


@router.post("/forgot")
async def forgot_password(payload: ForgotIn, request: Request, db: Session = Depends(get_db)):
    limit_request(request, "forgot", 5, 900)
    if not mailer.is_configured():
        raise HTTPException(503, "Pemulihan password lewat email belum dikonfigurasi di server ini. Hubungi admin.")
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if user:
        token = create_purpose_token(user.user_id, "reset", binder_of(user.password_hash), RESET_TTL_MIN)
        link = f"{settings.app_url.rstrip('/')}/reset?token={token}"
        await mailer.send_mail(
            user.email,
            "Atur ulang password SkripsiAI",
            f"Halo {user.full_name},\n\nAda permintaan mengatur ulang password akun SkripsiAI Anda. Buka tautan ini dalam {RESET_TTL_MIN} menit:\n{link}\n\nAbaikan email ini bila Anda tidak memintanya.",
        )
    return {"ok": True}  # selalu sama agar email terdaftar tidak bisa ditebak


@router.post("/reset", status_code=204)
def reset_password(payload: ResetIn, request: Request, db: Session = Depends(get_db)):
    limit_request(request, "reset", 10, 900)
    parsed = verify_purpose_token(payload.token, "reset")
    user = db.get(User, parsed[0]) if parsed else None
    if not parsed or not user or parsed[1] != binder_of(user.password_hash):
        raise HTTPException(400, "Tautan tidak valid atau sudah kedaluwarsa")
    user.password_hash = hash_password(payload.password)  # binder berubah, jadi tautan lama gugur
    db.commit()


@router.post("/send-verification")
async def send_verification(user: User = Depends(auth_required)):
    limit_user(user.user_id, "send-verification", 3, 3600)
    if user.email_verified:
        return {"ok": True, "already": True}
    if not mailer.is_configured():
        raise HTTPException(503, "Verifikasi email belum dikonfigurasi di server ini.")
    token = create_purpose_token(user.user_id, "verify", binder_of(user.email), VERIFY_TTL_MIN)
    link = f"{settings.app_url.rstrip('/')}/verifikasi?token={token}"
    sent = await mailer.send_mail(user.email, "Verifikasi email SkripsiAI", f"Halo {user.full_name},\n\nVerifikasi email Anda dengan membuka tautan ini:\n{link}\n")
    if not sent:
        raise HTTPException(503, "Email tidak dapat dikirim saat ini. Coba lagi nanti.")
    return {"ok": True}


@router.post("/verify", status_code=204)
def verify_email(payload: VerifyIn, request: Request, db: Session = Depends(get_db)):
    limit_request(request, "verify", 20, 900)
    parsed = verify_purpose_token(payload.token, "verify")
    user = db.get(User, parsed[0]) if parsed else None
    if not parsed or not user or parsed[1] != binder_of(user.email):
        raise HTTPException(400, "Tautan tidak valid atau sudah kedaluwarsa")
    user.email_verified = True
    db.commit()
