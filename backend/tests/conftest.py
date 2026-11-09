import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import db as core_db
from app.core.db import Base
from app.core.config import settings
from app.main import app

# Tes harus deterministik: jangan memakai kunci/API eksternal dari .env pengembang.
settings.nim_api_key = ""
settings.groq_api_key = ""
settings.openalex_api_key = ""
settings.core_api_key = ""
settings.polite_email = ""
settings.gemini_api_key = ""
settings.semantic_scholar_api_key = ""

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
core_db.engine = engine
core_db.SessionLocal.configure(bind=engine)


def _override_get_db():
    db = core_db.SessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[core_db.get_db] = _override_get_db


@pytest.fixture(scope="session")
def client():
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c


def _ensure_user(client, register_payload: dict) -> dict:
    resp = client.post("/auth/register", json=register_payload)
    if resp.status_code == 409:
        resp = client.post(
            "/auth/login",
            json={"email": register_payload["email"], "password": register_payload["password"]},
        )
    assert resp.status_code in (200, 201), resp.text
    data = resp.json()
    return {
        "headers": {"Authorization": f"Bearer {data['access_token']}"},
        "user_id": data["user_id"],
        "email": data["email"],
    }


@pytest.fixture
def auth(client):
    return _ensure_user(
        client,
        {
            "full_name": "Test Mahasiswa",
            "email": "mhs@test.id",
            "password": "rahasia123",
            "major_name": "Teknik Informatika",
            "campus_name": "Universitas Uji",
        },
    )


@pytest.fixture()
def fake_llm(monkeypatch):
    """LLM tiruan deterministik: tes tidak menyentuh jaringan, dan tidak ada teks template di aplikasi."""
    import json
    import re

    from app.services.agents import advisor, review, structured, titles, writer

    calls = []
    counter = {"n": 0}

    async def fake(messages, tier="heavy", temperature=0.4, max_tokens=1600, only=None):
        calls.append(tier)
        system = messages[0]["content"]
        if "Generator Judul" in system:
            items = [{"text": f"Judul Uji Nomor {i} tentang Media Digital dan Motivasi", "rationale": "r", "gap": "g"} for i in range(5)]
            return json.dumps({"titles": items}), "fake"
        if "You fill a JSON structure" in system:
            return json.dumps({
                "intro": "Rumusan dan tujuan penelitian disusun sebagai berikut.",
                "questions": ["Bagaimana media digital memengaruhi motivasi belajar siswa", "Faktor apa yang memperkuat pengaruh tersebut"],
                "objectives_intro": "Tujuan penelitian ini adalah:",
                "objectives": ["Untuk menganalisis pengaruh media digital", "Untuk mengidentifikasi faktor penguat"],
                "groups": [{"audience": "guru", "items": ["Gunakan media digital secara terencana", "Evaluasi motivasi berkala"]}, {"audience": "peneliti selanjutnya", "items": ["Perluas sampel penelitian"]}],
                "themes": [{"title": "Persepsi siswa", "description": "Tema ini menjawab rumusan pertama.", "data_needed": ["kutipan wawancara S1"]}, {"title": "Tantangan", "description": "Tema ini menjawab rumusan kedua.", "data_needed": ["catatan observasi"]}],
            }), "fake"
        if "RUBRIK PEMBIMBING" in system:
            title = re.search(r"Judul: (.+)", messages[-1]["content"]).group(1)
            dims = {k: {"skor": 3, "bukti": title, "kritik": f"Dimensi {k} memadai tetapi masih umum.", "saran": "Perjelas argumen."} for k in "ABCDEF"}
            return json.dumps({"dimensi": dims, "kelemahan_utama": ["Argumen belum tajam."]}), "fake"
        if "Dosen Penguji" in system:
            qs = [
                {"fokus": "Metodologi", "level": "kritis" if i == 2 else "umum", "pertanyaan": f"Pertanyaan sidang nomor {i} tentang variabel dan sampel penelitian ini?", "saran_jawaban": "Jelaskan desain, sampel, dan instrumen sesuai Bab 3 pada draf."}
                for i in range(1, 7)
            ]
            return json.dumps({"questions": qs}), "fake"
        # LLM tiruan yang patuh: menulis penanda persis seperti yang diberikan di prompt.
        # Rujukan dicari di SELURUH percakapan sebab pesan lanjutan hanya membawa instruksi tambahan.
        pairs = re.findall(r'reference_id=([^;\s]+);.*?penanda="([^"]+)"', "\n".join(m["content"] for m in messages))
        requested = re.findall(r"minimal (\d+) kata", messages[-1]["content"])
        need = max(40, min(int(requested[-1]), 400)) if requested else 80
        sents = []
        words = 0
        while words < need:
            counter["n"] += 1
            s = f"Temuan kajian ke-{counter['n']} menunjukkan media digital meningkatkan motivasi belajar siswa secara konsisten."
            sents.append(s)
            words += len(s.split())
        first_id, first_marker = pairs[0]
        content = " ".join(sents) + f" {first_marker}."
        cites = [{"reference_id": first_id, "snippet": "kalimat abstrak"}, {"reference_id": "id-tidak-ada", "snippet": "x"}]
        return json.dumps({"content": content, "citations": cites}), "fake"

    monkeypatch.setattr(titles, "llm_chat_ex", fake)
    monkeypatch.setattr(writer, "llm_chat_ex", fake)
    monkeypatch.setattr(review, "llm_chat_ex", fake)
    monkeypatch.setattr(advisor, "llm_chat_ex", fake)
    monkeypatch.setattr(structured, "llm_chat_ex", fake)
    return calls
