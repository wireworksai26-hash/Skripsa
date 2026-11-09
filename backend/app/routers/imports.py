from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.core.deps import auth_required
from app.core.ratelimit import limit_user
from app.models.models import User
from app.services.draft_import import MAX_BYTES, ParseError, parse_draft, parse_file

router = APIRouter(prefix="/import", tags=["import"])


class TextIn(BaseModel):
    text: str = Field(min_length=100, max_length=600_000)


@router.post("/parse-text")
def parse_text(payload: TextIn, user: User = Depends(auth_required)):
    """Pecah naskah yang ditempel menjadi bab dan subbab. Hanya pratinjau; tidak ada yang disimpan."""
    limit_user(user.user_id, "import-text", 20, 60)
    try:
        return parse_draft(payload.text)
    except ParseError as exc:
        raise HTTPException(exc.status, str(exc))


@router.post("/parse-file")
async def parse_upload(file: UploadFile = File(...), user: User = Depends(auth_required)):
    limit_user(user.user_id, "import-file", 10, 60)
    data = await file.read(MAX_BYTES + 1)
    try:
        return parse_file(file.filename or "naskah", data)
    except ParseError as exc:
        raise HTTPException(exc.status, str(exc))


class TitleIn(BaseModel):
    title: str = Field(min_length=10, max_length=600)


@router.post("/extract-title")
async def extract_title(payload: TitleIn, user: User = Depends(auth_required)):
    """Ekstrak variabel X/Y, subjek, metode, dan jurusan dari judul. Hanya saran; pengguna yang memutuskan."""
    limit_user(user.user_id, "import-title", 30, 60)
    from app.services.agents.title_extract import extract_from_title

    data, provider = await extract_from_title(payload.title)
    return {**data, "provider": provider}
