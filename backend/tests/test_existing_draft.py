import io
import json

import pytest

from app.services import draft_import as di
from tests.pdf_util import make_pdf

PARA = "Penelitian ini membahas pengaruh media digital terhadap motivasi belajar siswa di sekolah menengah pertama secara mendalam."

DRAFT = f"""UNIVERSITAS CONTOH
PENGARUH MEDIA DIGITAL TERHADAP MOTIVASI BELAJAR SISWA

DAFTAR ISI
BAB I PENDAHULUAN ........................ 1
1.1 Latar Belakang ........................ 2
BAB II TINJAUAN PUSTAKA .................. 8

BAB I
PENDAHULUAN
1.1 Latar Belakang Masalah
{PARA}
{PARA} Paragraf kedua tentang urgensi.
1.2 Rumusan Masalah
Bagaimana pengaruh media digital terhadap motivasi belajar siswa pada kelas delapan di sekolah ini?
1.2.1 Sub-sub bagian yang tidak jadi subbab
Rincian rumusan masalah yang masih bagian dari subbab 1.2 dan harus tetap menempel pada isinya.

BAB II TINJAUAN PUSTAKA
{PARA}
Kajian ini tidak punya subbab bernomor sama sekali sehingga seluruh isi menjadi satu subbab otomatis.

BAB III. METODE PENELITIAN
3.1 Desain Penelitian
Penelitian menggunakan desain kuasi eksperimen dengan kelompok kontrol dan kelompok eksperimen yang dibandingkan.

DAFTAR PUSTAKA
Nur, A. (2021). Media digital. Jurnal X.
"""


def test_parse_splits_chapters_sections_and_ignores_toc_and_references():
    out = di.parse_draft(DRAFT)
    chapters = {c["chapter_code"]: c for c in out["chapters"]}
    assert list(chapters) == ["1", "2", "3"], "daftar isi tidak membuat bab ganda"
    assert chapters["1"]["chapter_title"] == "PENDAHULUAN", "judul bab di baris berikutnya terbaca"
    assert chapters["3"]["chapter_title"] == "METODE PENELITIAN"

    s1 = {s["section_code"]: s for s in chapters["1"]["sections"]}
    assert list(s1) == ["1.1", "1.2"] and s1["1.1"]["title"] == "Latar Belakang Masalah"
    assert "Paragraf kedua" in s1["1.1"]["content"]
    assert "1.2.1 Sub-sub bagian" in s1["1.2"]["content"] and "Rincian rumusan" in s1["1.2"]["content"], "1.2.1 tetap isi 1.2"

    s2 = chapters["2"]["sections"]
    assert [s["section_code"] for s in s2] == ["2.1"] and s2[0]["title"] == "Tinjauan Pustaka"
    assert any("tidak punya subbab bernomor" in w for w in out["warnings"])
    assert "Nur, A. (2021)" not in json.dumps(out) and any("DAFTAR PUSTAKA" in w for w in out["warnings"])
    assert out["total_words"] == sum(s["words"] for c in out["chapters"] for s in c["sections"])


def test_parse_numbered_sections_without_chapter_headings_and_duplicates():
    text = f"1.1 Latar Belakang\n{PARA}\n2.1 Tinjauan Pustaka\n{PARA}\n1.1 Latar Belakang\n{PARA} kedua kali muncul"
    out = di.parse_draft(text)
    assert [c["chapter_code"] for c in out["chapters"]] == ["1", "2"]
    assert out["chapters"][0]["sections"][0]["content"].count("kedua kali muncul") == 1, "judul yang sama digabung, bukan digandakan"


def test_sentences_that_look_like_numbering_are_not_headings():
    text = f"BAB I PENDAHULUAN\n1.1 Latar Belakang\n{PARA}\n1.5 kali lebih besar daripada kelompok kontrol menurut hasil pengamatan awal.\nKalimat lanjutan."
    sec = di.parse_draft(text)["chapters"][0]["sections"]
    assert [s["section_code"] for s in sec] == ["1.1"], "huruf kecil di awal = bukan judul subbab"
    assert "1.5 kali lebih besar" in sec[0]["content"]


def test_no_structure_raises_helpful_error():
    with pytest.raises(di.ParseError, match="judul bab"):
        di.parse_draft("Ini hanya satu paragraf panjang tanpa judul bab apa pun. " * 10)


def _docx_bytes(paragraphs):
    import docx

    d = docx.Document()
    for p in paragraphs:
        d.add_paragraph(p)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def test_docx_and_txt_and_pdf_files():
    paras = DRAFT.split("\n")
    out = di.parse_file("skripsi.docx", _docx_bytes(paras))
    assert [c["chapter_code"] for c in out["chapters"]] == ["1", "2", "3"] and out["filename"] == "skripsi.docx"

    assert len(di.parse_file("catatan.txt", DRAFT.encode("utf-8"))["chapters"]) == 3
    assert len(di.parse_file("latin.txt", DRAFT.replace("MEDIA", "MÉDIA").encode("latin-1"))["chapters"]) == 3

    # PDF: baris terpenggal di tengah kalimat harus tersambung kembali
    lines = ["BAB I PENDAHULUAN", "1.1 Latar Belakang Masalah", "Penelitian ini membahas pengaruh media digital terhadap", "motivasi belajar siswa di sekolah menengah pertama secara", "mendalam dan sistematis sesuai kajian terdahulu yang relevan."]
    pdf = make_pdf([lines + ["Teks tambahan agar PDF memuat cukup banyak karakter untuk dibaca. " * 8]])
    sec = di.parse_file("n.pdf", pdf)["chapters"][0]["sections"][0]
    assert "terhadap motivasi belajar siswa" in sec["content"] and "secara mendalam" in sec["content"]


def test_file_errors():
    with pytest.raises(di.ParseError, match="docx"):
        di.parse_file("rusak.docx", b"PK\x03\x04 bukan zip")
    with pytest.raises(di.ParseError, match=".doc lama"):
        di.parse_file("lama.doc", b"\xd0\xcf\x11\xe0 xxxxxxxxxxxxxxxx")
    with pytest.raises(di.ParseError) as e:
        di.parse_file("besar.txt", b"x" * (di.MAX_BYTES + 1))
    assert e.value.status == 413
    with pytest.raises(di.ParseError, match="hampir tidak berisi teks"):
        di.parse_file("kosong.txt", b"   pendek   ")


# ---------- migrasi basis data ----------

def test_add_missing_columns_upgrades_old_database_and_keeps_rows(tmp_path):
    from sqlalchemy import create_engine, inspect, text

    from app.core.db import add_missing_columns

    eng = create_engine(f"sqlite:///{(tmp_path / 'lama.db').as_posix()}")
    with eng.begin() as c:
        c.execute(text("CREATE TABLE theses (thesis_id VARCHAR(36) PRIMARY KEY, user_id VARCHAR(36) NOT NULL, title TEXT NOT NULL, research_method VARCHAR(50) NOT NULL, domain_category VARCHAR(100) NOT NULL, campus_template_id VARCHAR(100) NOT NULL, status VARCHAR(50))"))
        c.execute(text("CREATE TABLE thesis_sections (section_id VARCHAR(36) PRIMARY KEY, thesis_id VARCHAR(36) NOT NULL, chapter_code VARCHAR(20) NOT NULL, section_code VARCHAR(20) NOT NULL, section_title VARCHAR(255) NOT NULL)"))
        c.execute(text("INSERT INTO theses VALUES ('t1','u1','Judul lama','KUANTITATIF','UMUM','nasional-s1-kuantitatif','IN_PROGRESS')"))
        c.execute(text("INSERT INTO thesis_sections VALUES ('s1','t1','1','1.1','Latar')"))

    added = add_missing_columns(eng)
    assert "theses.source_mode" in added and "thesis_sections.origin" in added
    cols = {c["name"] for c in inspect(eng).get_columns("thesis_sections")}
    assert "origin" in cols
    with eng.connect() as c:
        assert c.execute(text("SELECT source_mode FROM theses")).scalar() == "NEW", "baris lama terisi default"
        assert c.execute(text("SELECT origin FROM thesis_sections")).scalar() == "GENERATED"
    assert add_missing_columns(eng) == [], "dijalankan dua kali aman"


# ---------- API ----------

IMPORTED = [
    {"section_code": "1.1", "title": "Latar Belakang Masalah", "content": " ".join([PARA] * 4)},
    {"section_code": "3.9", "title": "Subbab di luar templat", "content": PARA},
]


def _create_existing(client, headers, **extra):
    body = {
        "topic": "Pengaruh Media Digital terhadap Motivasi Belajar Siswa",
        "existing_title": "Pengaruh Media Digital terhadap Motivasi Belajar Siswa SMP",
        "variable_x": "Media digital", "variable_y": "Motivasi belajar", "subject": "Siswa SMP",
        "imported_sections": IMPORTED,
    }
    body.update(extra)
    return client.post("/theses", headers=headers, json=body)


def test_create_from_existing_title_and_chapters(client, auth):
    headers = auth["headers"]
    res = _create_existing(client, headers)
    assert res.status_code == 201, res.text
    t = res.json()
    assert t["source_mode"] == "EXISTING" and t["title"] == "Pengaruh Media Digital terhadap Motivasi Belajar Siswa SMP"
    assert t["picked_title_id"], "judul pengguna terkunci"
    titles = client.get(f"/theses/{t['thesis_id']}/titles", headers=headers).json()
    assert [x["text"] for x in titles] == [t["title"]] and titles[0]["title_id"] == t["picked_title_id"]

    secs = {s["section_code"]: s for s in t["sections"]}
    assert secs["1.1"]["origin"] == "IMPORTED" and secs["1.1"]["word_count"] > 40
    assert secs["1.1"]["target_words"] == 1200, "target kata mengikuti templat bila kodenya ada"
    assert secs["3.9"]["target_words"] == 400 and secs["3.9"]["origin"] == "IMPORTED"
    assert secs["1.2"]["origin"] == "GENERATED" and secs["1.2"]["content_markdown"] == "", "subbab templat yang kosong dilengkapi"
    assert len(secs) >= 18, "kerangka templat lengkap + subbab impor"


def test_title_only_and_chapters_only_and_default_mode(client, auth):
    headers = auth["headers"]
    title_only = _create_existing(client, headers, imported_sections=[]).json()
    assert title_only["source_mode"] == "EXISTING" and title_only["sections"] == [], "judul saja: subbab dibangun nanti di Langkah 4"

    chapters_only = client.post("/theses", headers=headers, json={"topic": "Pengaruh Media Digital terhadap Motivasi", "imported_sections": IMPORTED}).json()
    assert chapters_only["source_mode"] == "EXISTING" and chapters_only["picked_title_id"] is None

    plain = client.post("/theses", headers=headers, json={"topic": "Pengaruh Media Digital terhadap Motivasi"}).json()
    assert plain["source_mode"] == "NEW" and plain["sections"] == []


def test_import_validation(client, auth):
    headers = auth["headers"]
    bad_code = _create_existing(client, headers, imported_sections=[{"section_code": "satu", "title": "x", "content": "y"}])
    assert bad_code.status_code == 422
    short_title = _create_existing(client, headers, existing_title="pendek")
    assert short_title.status_code == 422
    dup = _create_existing(client, headers, imported_sections=[IMPORTED[0], {**IMPORTED[0], "content": "salinan kedua"}]).json()
    assert [s["section_code"] for s in dup["sections"]].count("1.1") == 1
    assert next(s for s in dup["sections"] if s["section_code"] == "1.1")["content_markdown"] == IMPORTED[0]["content"]


def test_user_text_is_protected_from_overwrite_and_context_reaches_writer(client, auth, fake_llm, monkeypatch):
    headers = auth["headers"]
    tid = _create_existing(client, headers).json()["thesis_id"]
    cit = client.post(
        f"/theses/{tid}/citations", headers=headers,
        json=[{"title": "Media Digital dan Motivasi", "authors": ["Nur, A."], "publication_year": 2021, "highlighted_snippet": "Media digital meningkatkan motivasi belajar siswa secara signifikan."}],
    ).json()[0]
    client.patch(f"/theses/{tid}", headers=headers, json={"selected_ref_ids": [cit["citation_id"]]})

    blocked = client.post(f"/theses/{tid}/sections/1.1/generate", headers=headers)
    assert blocked.status_code == 409 and "tulisan Anda" in blocked.json()["detail"]
    assert client.get(f"/theses/{tid}", headers=headers).json()["sections"][0]["content_markdown"], "isi pengguna utuh"

    from app.services.agents import writer

    captured = {}
    real = writer.llm_chat_ex

    async def spy(messages, **kw):
        captured.setdefault("convo", messages)
        return await real(messages, **kw)

    monkeypatch.setattr(writer, "llm_chat_ex", spy)
    ok = client.post(f"/theses/{tid}/sections/2.1/generate", headers=headers)
    assert ok.status_code == 200, ok.text
    first_prompt = captured["convo"][1]["content"]
    assert "SUDAH ditulis" in first_prompt and "- 1.1 Latar Belakang Masalah" in first_prompt, "judul subbab lain dikirim sebagai konteks"
    assert PARA not in first_prompt, "teks subbab lain TIDAK dikirim (audit BUG-01: memicu salin-tempel)"
    assert "- 2.1" not in first_prompt.split("Referensi terverifikasi")[0], "subbab yang sedang ditulis tidak dimasukkan"

    over = client.post(f"/theses/{tid}/sections/1.1/generate?overwrite=true", headers=headers)
    assert over.status_code == 200
    after = {s["section_code"]: s for s in client.get(f"/theses/{tid}", headers=headers).json()["sections"]}
    assert after["1.1"]["origin"] == "GENERATED", "setelah ditimpa dengan izin, subbab menjadi hasil agen"


def test_title_regeneration_keeps_users_own_title(client, auth, fake_llm):
    headers = auth["headers"]
    t = _create_existing(client, headers, imported_sections=[]).json()
    res = client.post(f"/theses/{t['thesis_id']}/titles", headers=headers).json()
    texts = [x["text"] for x in res["titles"]]
    assert t["title"] in texts and len(texts) == 6, "judul pengguna + 5 alternatif"
    again = client.post(f"/theses/{t['thesis_id']}/titles", headers=headers).json()["titles"]
    assert len(again) == 6 and sum(1 for x in again if x["text"] == t["title"]) == 1
    detail = client.get(f"/theses/{t['thesis_id']}", headers=headers).json()
    assert detail["picked_title_id"] == t["picked_title_id"] and detail["title"] == t["title"]


def test_pipeline_and_guardrail_respect_imported_text(client, auth, fake_llm):
    import time

    headers = auth["headers"]
    tid = _create_existing(client, headers).json()["thesis_id"]
    cit = client.post(f"/theses/{tid}/citations", headers=headers, json=[{"title": "Media Digital", "authors": ["Nur, A."], "publication_year": 2021, "highlighted_snippet": "Media digital meningkatkan motivasi belajar siswa."}]).json()[0]
    client.patch(f"/theses/{tid}", headers=headers, json={"selected_ref_ids": [cit["citation_id"]]})
    original = next(s for s in client.get(f"/theses/{tid}", headers=headers).json()["sections"] if s["section_code"] == "1.1")["content_markdown"]

    job = client.post(f"/theses/{tid}/pipeline/run", headers=headers).json()["job_id"]
    for _ in range(150):
        st = client.get(f"/theses/{tid}/pipeline/jobs/{job}", headers=headers).json()
        if st["status"] in ("COMPLETED", "FAILED"):
            break
        time.sleep(0.1)
    assert st["status"] == "COMPLETED", st

    detail = client.get(f"/theses/{tid}", headers=headers).json()
    s11 = next(s for s in detail["sections"] if s["section_code"] == "1.1")
    assert s11["content_markdown"] == original and s11["origin"] == "IMPORTED", "pipeline tidak menimpa tulisan pengguna"
    assert any(s["origin"] == "GENERATED" and s["word_count"] > 30 for s in detail["sections"]), "subbab kosong tetap diisi"

    notes = [n["text"] for n in detail["review_json"]["GUARDRAIL"]["notes"]]
    assert any("tulisan Anda (1.1" in n for n in notes), "catatan bahwa subbab impor tidak diverifikasi sitasinya"
    assert not any(n.startswith("[1.1]") and "belum ada sitasi" in n for n in notes), "tulisan pengguna tidak dituntut sitasi tertaut"


def test_import_parse_endpoints(client, auth):
    headers = auth["headers"]
    assert client.post("/import/parse-text", json={"text": DRAFT}).status_code == 401

    ok = client.post("/import/parse-text", headers=headers, json={"text": DRAFT})
    assert ok.status_code == 200 and [c["chapter_code"] for c in ok.json()["chapters"]] == ["1", "2", "3"]
    assert client.post("/import/parse-text", headers=headers, json={"text": "terlalu pendek"}).status_code == 422
    flat = client.post("/import/parse-text", headers=headers, json={"text": "tanpa struktur " * 30})
    assert flat.status_code == 422 and "judul bab" in flat.json()["detail"]

    up = client.post("/import/parse-file", headers=headers, files={"file": ("skripsi.docx", _docx_bytes(DRAFT.split("\n")), "application/octet-stream")})
    assert up.status_code == 200 and up.json()["filename"] == "skripsi.docx" and up.json()["total_words"] > 50
    bad = client.post("/import/parse-file", headers=headers, files={"file": ("x.doc", b"\xd0\xcf\x11\xe0 aaaaaaaaaaaaaaaa", "application/msword")})
    assert bad.status_code == 422


# ---------- subbab ganda (balapan permintaan build) ----------

def test_unique_index_blocks_duplicates_and_build_is_idempotent(client, auth, monkeypatch):
    from sqlalchemy.exc import IntegrityError

    from app.models.models import ThesisSection
    from app.routers import theses as theses_router

    headers = auth["headers"]
    tid = client.post("/theses", headers=headers, json={"topic": "Pengaruh Media Digital terhadap Motivasi Belajar"}).json()["thesis_id"]
    first = client.post(f"/theses/{tid}/sections/build", headers=headers).json()
    again = client.post(f"/theses/{tid}/sections/build", headers=headers).json()
    assert first["total"] == again["total"] and again["created"] == [], "build dua kali tidak menggandakan"

    # Balapan: permintaan lain sudah menyisipkan kode yang sama tepat sebelum commit kita.
    from app.core import db as core_db

    def racing_add(thesis, db):
        db.add(ThesisSection(thesis_id=thesis.thesis_id, chapter_code="1", section_code="1.1", section_title="dobel", target_words=1, content_markdown=""))
        return ["1.1"]

    monkeypatch.setattr(theses_router, "_add_missing_sections", racing_add)
    res = client.post(f"/theses/{tid}/sections/build", headers=headers)
    assert res.status_code == 200 and res.json()["created"] == [], "IntegrityError ditangani, bukan 500"
    codes = [s["section_code"] for s in client.get(f"/theses/{tid}/sections", headers=headers).json()]
    assert len(codes) == len(set(codes))

    s = core_db.SessionLocal()
    try:
        s.add(ThesisSection(thesis_id=tid, chapter_code="1", section_code="1.1", section_title="x", target_words=1, content_markdown=""))
        with pytest.raises(IntegrityError):
            s.commit()
    finally:
        s.rollback()
        s.close()


def test_ensure_unique_sections_cleans_old_duplicates_keeping_the_one_with_content(tmp_path):
    from sqlalchemy import create_engine, text

    from app.core.db import ensure_unique_sections

    eng = create_engine(f"sqlite:///{(tmp_path / 'dup.db').as_posix()}")
    with eng.begin() as c:
        c.execute(text("CREATE TABLE thesis_sections (section_id VARCHAR(36) PRIMARY KEY, thesis_id VARCHAR(36) NOT NULL, section_code VARCHAR(20) NOT NULL, content_markdown TEXT NOT NULL, created_at TIMESTAMP)"))
        for sid, code, body in [("a", "1.1", ""), ("b", "1.1", "tulisan penting"), ("c", "1.1", ""), ("d", "1.2", ""), ("e", "1.2", "")]:
            c.execute(text("INSERT INTO thesis_sections VALUES (:i,'t1',:c,:b,'2026-01-01')"), {"i": sid, "c": code, "b": body})
    assert ensure_unique_sections(eng) == 3
    with eng.connect() as c:
        rows = dict(c.execute(text("SELECT section_code, section_id FROM thesis_sections")).fetchall())
    assert rows["1.1"] == "b" and len(rows) == 2, "yang berisi dipertahankan"
    assert ensure_unique_sections(eng) == 0
