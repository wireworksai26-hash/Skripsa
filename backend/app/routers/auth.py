from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import auth_required
from app.core.ratelimit import (
    client_ip,
    count,
    hit,
    login_blocked,
    login_failed,
    login_key,
    login_succeeded,
)
from app.core.security import create_token, hash_password, verify_password
from app.models.models import User
from app.schemas.schemas import LoginIn, ProfileIn, RegisterIn, TokenOut, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

REGISTER_LIMIT = 30
REGISTER_WINDOW = 3600
_DUMMY_HASH = hash_password("timing-only-password")


@router.post("/register", response_model=TokenOut, status_code=201)
def register(payload: RegisterIn, request: Request, db: Session = Depends(get_db)):
    ip = client_ip(request)
    register_key = f"register-success:{ip}"
    if count(register_key, REGISTER_WINDOW) >= REGISTER_LIMIT:
        raise HTTPException(429, "Terlalu banyak pendaftaran. Coba lagi nanti.", headers={"Retry-After": str(REGISTER_WINDOW)})
    email = payload.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "Email sudah terdaftar")
    user = User(
        full_name=payload.full_name,
        email=email,
        password_hash=hash_password(payload.password),
        major_name=payload.major_name,
        campus_name=payload.campus_name,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Email sudah terdaftar")
    hit(register_key, REGISTER_LIMIT, REGISTER_WINDOW)
    db.refresh(user)
    return TokenOut(
        access_token=create_token(user.user_id),
        user_id=user.user_id,
        full_name=user.full_name,
        email=user.email,
    )


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)):
    key = login_key(request, payload.email)
    if login_blocked(key):
        raise HTTPException(429, "Terlalu banyak percobaan login. Coba lagi nanti.", headers={"Retry-After": "300"})
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    valid = verify_password(payload.password, user.password_hash if user else _DUMMY_HASH)
    if not user or not valid:
        login_failed(key)
        raise HTTPException(401, "Email atau password salah")
    login_succeeded(key)
    return TokenOut(
        access_token=create_token(user.user_id),
        user_id=user.user_id,
        full_name=user.full_name,
        email=user.email,
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(auth_required)):
    return user


@router.put("/profile", response_model=UserOut)
def update_profile(payload: ProfileIn, user: User = Depends(auth_required), db: Session = Depends(get_db)):
    user.full_name = payload.full_name.strip()
    user.nim = payload.nim.strip()
    user.major_name = payload.major_name.strip()
    user.faculty = payload.faculty.strip()
    user.campus_name = payload.campus_name.strip()
    user.city = payload.city.strip()
    user.logo_data = payload.logo_data
    if payload.notify_prefs is not None:
        user.notify_prefs = payload.notify_prefs
    db.commit()
    db.refresh(user)
    return user
