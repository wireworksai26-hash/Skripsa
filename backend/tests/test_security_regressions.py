import asyncio
import os
import tempfile
from uuid import uuid4

import pytest

from app.core.config import settings
from app.services.pdf_fetch import PdfFetchError, assert_public_url


def _thesis(client, headers) -> str:
    res = client.post(
        "/theses",
        headers=headers,
        json={"topic": f"Keamanan data penelitian {uuid4().hex[:8]}"},
    )
    assert res.status_code == 201, res.text
    return res.json()["thesis_id"]


def _user(client) -> dict:
    email = f"aman-{uuid4().hex[:10]}@test.id"
    res = client.post(
        "/auth/register",
        json={
            "full_name": "Pengguna Uji",
            "email": email,
            "password": "rahasia123",
            "major_name": "Teknik Informatika",
            "campus_name": "Universitas Uji",
        },
    )
    assert res.status_code == 201, res.text
    data = res.json()
    return {"headers": {"Authorization": f"Bearer {data['access_token']}"}, "user_id": data["user_id"]}


def test_rag_search_is_isolated_between_users(client, auth):
    headers = auth["headers"]
    tid = _thesis(client, headers)
    title = f"Rujukan rahasia {uuid4().hex[:8]}"
    citation = client.post(
        f"/theses/{tid}/citations",
        headers=headers,
        json=[{"title": title, "publication_year": 2024}],
    ).json()[0]
    assert client.post("/rag/index", headers=headers, params={"thesis_id": tid}, json={"citation_ids": [citation["citation_id"]]}).status_code == 200

    own = client.post("/rag/search", headers=headers, json={"query": title, "k": 5}).json()["hits"]
    assert any(hit["meta"].get("thesis_id") == tid for hit in own)

    other = _user(client)
    foreign = client.post("/rag/search", headers=other["headers"], json={"query": title, "k": 5}).json()["hits"]
    assert all(hit["meta"].get("thesis_id") != tid for hit in foreign)


def test_rag_reindex_is_idempotent(client, auth):
    headers = auth["headers"]
    tid = _thesis(client, headers)
    citation = client.post(
        f"/theses/{tid}/citations",
        headers=headers,
        json=[{"title": f"Rujukan indeks {uuid4().hex[:8]}", "publication_year": 2024}],
    ).json()[0]
    payload = {"citation_ids": [citation["citation_id"]]}
    assert client.post("/rag/index", headers=headers, params={"thesis_id": tid}, json=payload).status_code == 200
    again = client.post("/rag/index", headers=headers, params={"thesis_id": tid}, json=payload)
    assert again.status_code == 200


def test_input_bounds_are_enforced(client, auth):
    headers = auth["headers"]
    tid = _thesis(client, headers)
    assert client.post(f"/theses/{tid}/sections/build", headers=headers).status_code == 200
    assert client.patch(f"/theses/{tid}/sections/1.1", headers=headers, json={"content_markdown": "a" * 300_001}).status_code == 422
    assert client.post(f"/theses/{tid}/citations", headers=headers, json=[{"title": f"R{i}"} for i in range(101)]).status_code == 413
    assert client.post(f"/theses/{tid}/charts", headers=headers, json={"series": [{"label": "x", "value": 1}] * 51}).status_code == 422
    assert client.post("/rag/search", headers=headers, json={"query": "topik", "k": 21}).status_code == 422


def test_health_is_cached(client, monkeypatch):
    from app import main

    main._health_cache = None
    main._health_cached_at = 0.0
    calls = {"n": 0}

    async def fake_probe():
        calls["n"] += 1
        return {"Crossref": 200}

    monkeypatch.setattr(main, "_probe_scientific_apis", fake_probe)
    assert client.get("/health").status_code == 200
    assert client.get("/health").status_code == 200
    assert calls["n"] == 1


def test_export_temp_file_is_removed(client, auth, monkeypatch):
    headers = auth["headers"]
    tid = _thesis(client, headers)
    holder = {}

    def fake_export(_: dict) -> str:
        fd, path = tempfile.mkstemp(suffix=".docx")
        os.close(fd)
        with open(path, "wb") as fh:
            fh.write(b"PK\x03\x04" + b"x" * 6000)
        holder["path"] = path
        return path

    from app.services import docx_export

    monkeypatch.setattr(docx_export, "export_thesis_docx", fake_export)
    res = client.get(f"/theses/{tid}/export.docx", headers=headers)
    assert res.status_code == 200
    assert holder["path"] and not os.path.exists(holder["path"])


def test_secret_and_pdf_port_hardening():
    assert len(settings.secret_key) >= 32
    with pytest.raises(PdfFetchError):
        asyncio.run(assert_public_url("https://93.184.216.34:8443/a.pdf"))
