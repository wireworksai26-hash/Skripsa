import base64
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    major_name: str = Field(min_length=1, max_length=100)
    campus_name: str = Field(min_length=1, max_length=255)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    full_name: str
    email: str


class UserOut(BaseModel):
    user_id: str
    full_name: str
    email: str
    major_name: str
    campus_name: str
    nim: str = ""
    faculty: str = ""
    city: str = ""
    logo_data: str | None = None
    notify_prefs: dict | None = None


LOGO_PREFIX = "data:image/png;base64,"
LOGO_MAX_BYTES = 300 * 1024


class ProfileIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    nim: str = Field(default="", max_length=40)
    major_name: str = Field(min_length=1, max_length=100)
    faculty: str = Field(default="", max_length=150)
    campus_name: str = Field(min_length=1, max_length=255)
    city: str = Field(default="", max_length=80)
    logo_data: str | None = None  # None/"" = hapus logo
    notify_prefs: dict | None = None

    @field_validator("logo_data")
    @classmethod
    def _logo(cls, v):
        if not v:
            return None
        if not v.startswith(LOGO_PREFIX):
            raise ValueError("Logo harus berformat PNG")
        try:
            raw = base64.b64decode(v[len(LOGO_PREFIX):], validate=True)
        except Exception:
            raise ValueError("Data logo rusak")
        if len(raw) > LOGO_MAX_BYTES:
            raise ValueError("Logo terlalu besar (maksimal 300 KB)")
        if not raw.startswith(bytes([0x89]) + b"PNG"):
            raise ValueError("Berkas bukan PNG yang valid")
        return v


class CoverIn(BaseModel):
    year: int | None = Field(default=None, ge=1990, le=2100)
    advisor1: str = Field(default="", max_length=200)
    advisor2: str = Field(default="", max_length=200)
    doc_type: str = Field(default="SKRIPSI", pattern=r"^(SKRIPSI|PROPOSAL)$")
    degree_title: str = Field(default="", max_length=120)
    logo_cm: float | None = Field(default=None, ge=1, le=8)
    title_page: bool = True
    approval: bool = True
    originality: bool = True


class ImportedSection(BaseModel):
    section_code: str = Field(pattern=r"^\d{1,2}\.\d{1,2}$")
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=80000)


class ThesisIn(BaseModel):
    topic: str = Field(min_length=10, max_length=600)
    variable_x: str = ""
    variable_y: str = ""
    subject: str = ""
    method: str = "KUANTITATIF"
    domain: str = "UMUM"
    degree_level: str = "S1"
    language: str = "id"  # "id" = Bahasa Indonesia, "en" = English (isi & judul bab)
    template_id: str = ""  # kosong = disarankan dari metode & jenjang
    # Melanjutkan naskah sendiri: judul milik pengguna dikunci, dan bab yang sudah ada diimpor.
    existing_title: str | None = Field(default=None, min_length=10, max_length=600)
    imported_sections: list[ImportedSection] = Field(default_factory=list, max_length=80)


class ThesisPatch(BaseModel):
    title: str | None = Field(default=None, max_length=600)
    picked_title_id: str | None = Field(default=None, max_length=64)
    selected_ref_ids: list[Annotated[str, Field(max_length=64)]] | None = Field(default=None, max_length=50)
    status: str | None = Field(default=None, pattern=r"^(IN_PROGRESS|DRAF_FINAL)$")
    cover: CoverIn | None = None


class CitationIn(BaseModel):
    doi: str | None = Field(default=None, max_length=300)
    title: str = Field(min_length=1, max_length=5000)
    authors: list[Annotated[str, Field(max_length=300)]] = Field(default_factory=list, max_length=50)
    publication_year: int = Field(default=0, ge=0, le=2100)
    journal_name: str | None = Field(default=None, max_length=500)
    volume_issue: str | None = Field(default=None, max_length=100)
    page_range: str | None = Field(default=None, max_length=100)
    pdf_url: str | None = Field(default=None, max_length=5000)
    highlighted_snippet: str = Field(default="", max_length=50_000)
    page_number: int = Field(default=1, ge=1, le=10_000)
    source_database: str = Field(default="OpenAlex", max_length=50)
    cited_by: int = Field(default=0, ge=0, le=10_000_000)


class CitationOut(CitationIn):
    citation_id: str


class SectionOut(BaseModel):
    section_id: str
    chapter_code: str
    section_code: str
    section_title: str
    content_markdown: str
    citations_json: list = []
    word_count: int
    target_words: int
    version_number: int
    origin: str = "GENERATED"


class SectionPatch(BaseModel):
    content_markdown: str | None = Field(default=None, max_length=300_000)


class TitleOut(BaseModel):
    title_id: str
    text: str
    rationale: str
    gap: str


class GenerateOut(BaseModel):
    section_id: str
    section_code: str
    content_markdown: str
    citations_json: list
    word_count: int
    provider: str


class ChartPoint(BaseModel):
    label: str = Field(default="", max_length=120)
    value: float = 0


class ChartIn(BaseModel):
    kind: str = Field(default="bar", pattern=r"^(bar|line|pie)$")
    chapter: str = Field(default="4", pattern=r"^(?:[1-9]|1[0-2])$")
    title: str = Field(default="Grafik", max_length=200)
    xlabel: str | None = Field(default=None, max_length=100)
    ylabel: str | None = Field(default=None, max_length=100)
    series: list[ChartPoint] = Field(default_factory=list, max_length=50)
    caption: str = Field(default="", max_length=1000)


class DiagramIn(BaseModel):
    code: str = Field(min_length=1, max_length=20_000)
    image: str = Field(min_length=1, max_length=4_000_000)
    engine: str = Field(default="mermaid", pattern=r"^(mermaid|plantuml)$")
    chapter: str = Field(default="4", pattern=r"^(?:[1-9]|1[0-2])$")
    title: str = Field(default="Diagram", max_length=200)
    caption: str = Field(default="", max_length=300)
    width: int = Field(default=0, ge=0, le=5000)
    height: int = Field(default=0, ge=0, le=5000)

    @field_validator("image")
    @classmethod
    def _png_data_uri(cls, v: str) -> str:
        if not v.startswith("data:image/png;base64,"):
            raise ValueError("Diagram harus berupa PNG data URI")
        return v


class RagIndexIn(BaseModel):
    citation_ids: list[Annotated[str, Field(max_length=64)]] | None = Field(default=None, max_length=500)


class RagSearchIn(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    k: int = Field(default=5, ge=1, le=20)


class ReviewOut(BaseModel):
    ok: bool
    reviews: dict = {}
