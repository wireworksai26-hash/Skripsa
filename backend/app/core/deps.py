from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import verify_token
from app.models.models import Thesis, User


def auth_required(
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
) -> User:
    token = authorization.replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(401, "Token tidak ada")
    uid = verify_token(token)
    if not uid:
        raise HTTPException(401, "Token tidak valid atau kedaluwarsa")
    user = db.get(User, uid)
    if not user:
        raise HTTPException(401, "Pengguna tidak ditemukan")
    return user


def owned_thesis(thesis_id: str, user: User = Depends(auth_required), db: Session = Depends(get_db)) -> Thesis:
    thesis = db.get(Thesis, thesis_id)
    if not thesis or thesis.user_id != user.user_id:
        raise HTTPException(404, "Proyek skripsi tidak ditemukan")
    return thesis
