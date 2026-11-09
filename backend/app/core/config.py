import logging
import secrets
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parents[2]
log = logging.getLogger(__name__)

_INSECURE_SECRETS = {
    "",
    "dev-insecure-change-me",
    "ganti-dengan-string-acak-panjang",
    "changeme",
}


class Settings(BaseSettings):
    database_url: str = f"sqlite:///{(BASE_DIR / 'skripsi.db').as_posix()}"

    secret_key: str = ""
    token_ttl_minutes: int = 60 * 24 * 7
    environment: str = "development"

    nim_base_url: str = "https://integrate.api.nvidia.com/v1"
    nim_api_key: str = ""
    # Urutan hasil uji 7 Nov 2026 (draf 600 kata + JSON terstruktur, 4 percobaan): Super 120B dan Ultra 550B konsisten
    # menulis sitasi; Lightning (sebelumnya utama) gagal di 2 dari 3 percobaan. Model raksasa lain antre >30 dtk.
    nim_model: str = "nvidia/nemotron-3.5-super-vl-120b-a12b"
    nim_fallback_models: str = "nvidia/nemotron-3-ultra-550b-a55b,nvidia/nemotron-3.5-lightning-30b-a3b"

    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "llama-3.3-70b-versatile"

    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    gemini_model: str = "gemini-2.5-flash"

    # Urutan penyedia per tier; yang tanpa kunci dilewati otomatis.
    llm_fast_order: str = "groq,gemini,nim"
    llm_heavy_order: str = "nim,gemini,groq"

    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    polite_email: str = "skripsi-ai@example.org"
    semantic_scholar_api_key: str = ""
    openalex_api_key: str = ""
    core_api_key: str = ""

    # Push notification (OneSignal). Kosong = fitur nonaktif.
    onesignal_app_id: str = ""
    onesignal_api_key: str = ""
    app_url: str = "http://localhost:3000"  # tujuan saat notifikasi diketuk

    @model_validator(mode="after")
    def _secure_secret(self):
        if self.secret_key.strip() in _INSECURE_SECRETS:
            self.secret_key = secrets.token_urlsafe(48)
            log.warning(
                "SKRIPSI_SECRET_KEY tidak diisi dengan aman; memakai kunci acak sementara. "
                "Isi nilai acak panjang di backend/.env agar sesi login tidak hilang saat server restart."
            )
        return self

    class Config:
        env_prefix = "SKRIPSI_"
        env_file = BASE_DIR / ".env"


settings = Settings()
