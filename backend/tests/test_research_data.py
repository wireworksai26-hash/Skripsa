import json

from app.services import research_data as rd

CSV = "Kelas;Skor;Motivasi\nA;80;4,5\nA;70;3,5\nB;90;5\nB;60;2,5\nB;75;4\n"
TRANSCRIPT = (
    "Peneliti: Bagaimana pengalaman Anda presentasi? Siswa 1: Awalnya saya sangat gugup berbicara di depan kelas tetapi lama kelamaan saya terbiasa dan merasa lebih percaya diri. "
    "Siswa 2: Saya merasa penjelasan guru setelah presentasi membantu saya memahami materi yang tadinya membingungkan bagi saya. "
    "Siswa 3: Kadang saya bergantung pada AI untuk menyusun slide karena waktu persiapan terlalu singkat dan tugas lain menumpuk."
)


def _thesis(client, h, suffix):
    return client.post("/theses", headers=h, json={"topic": "Pengalaman Siswa dalam Presentasi dan Ketergantungan pada AI" + suffix, "method": "KUALITATIF"}).json()["thesis_id"]


def test_table_analysis_is_deterministic_and_creates_tables(client, auth):
    h = auth["headers"]
    tid = _thesis(client, h, " d1")
    d = client.post(f"/theses/{tid}/data", headers=h, json={"title": "Hasil tes", "kind": "table", "content": CSV}).json()
    assert d["analyzed"] is False
    r = client.post(f"/theses/{tid}/data/{d['data_id']}/analyze", headers=h)
    assert r.status_code == 200, r.text
    titles = [t["title"] for t in r.json()["tables"]]
    assert any(t.startswith("Statistik deskriptif") for t in titles) and "Distribusi Kelas" in titles
    desc = next(t for t in r.json()["tables"] if t["title"].startswith("Statistik deskriptif"))
    skor = next(row for row in desc["rows"] if row[0] == "Skor")
    assert skor[1] == "5" and skor[2] == "75,00" and skor[4] == "60,00" and skor[5] == "90,00", skor
    assert next(row for row in desc["rows"] if row[0] == "Motivasi")[2] == "3,90", "koma desimal terbaca"
    assert len(client.get(f"/theses/{tid}", headers=h).json()["tables"]) == len(titles)
    # analisis ulang tidak menggandakan tabel
    client.post(f"/theses/{tid}/data/{d['data_id']}/analyze", headers=h)
    assert len(client.get(f"/theses/{tid}", headers=h).json()["tables"]) == len(titles)
    # mengubah data membuang hasil olah lama
    client.put(f"/theses/{tid}/data/{d['data_id']}", headers=h, json={"title": "Hasil tes", "kind": "table", "content": CSV + "A;85;4\n"})
    assert client.get(f"/theses/{tid}", headers=h).json()["tables"] == []
    # menghapus data membuang tabelnya
    client.post(f"/theses/{tid}/data/{d['data_id']}/analyze", headers=h)
    assert client.delete(f"/theses/{tid}/data/{d['data_id']}", headers=h).status_code == 204
    assert client.get(f"/theses/{tid}", headers=h).json()["tables"] == []


def test_table_without_usable_columns_is_rejected(client, auth):
    h = auth["headers"]
    tid = _thesis(client, h, " d2")
    d = client.post(f"/theses/{tid}/data", headers=h, json={"title": "Kosong", "kind": "table", "content": "Nama\n" + "\n".join(f"orang {i}" for i in range(14))}).json()
    assert client.post(f"/theses/{tid}/data/{d['data_id']}/analyze", headers=h).status_code == 422


def test_text_coding_keeps_only_verbatim_excerpts(client, auth, monkeypatch):
    h = auth["headers"]
    tid = _thesis(client, h, " d3")

    async def fake(messages, **kw):
        themes = [
            {"name": "Kepercayaan diri meningkat", "description": "Gugup berubah terbiasa.", "excerpts": ["Awalnya saya sangat gugup berbicara di depan kelas tetapi lama kelamaan saya terbiasa", "kutipan karangan yang tidak ada dalam transkrip sama sekali"]},
            {"name": "Tema karangan", "description": "x", "excerpts": ["kalimat rekaan yang tidak pernah diucapkan siapa pun di transkrip"]},
            {"name": "Ketergantungan pada AI", "description": "Waktu singkat.", "excerpts": ["Kadang saya bergantung pada AI untuk menyusun slide karena waktu persiapan terlalu singkat"]},
        ]
        return json.dumps({"themes": themes, "notes": "Data tipis."}), "fake"

    monkeypatch.setattr(rd, "_ask", rd._ask)  # jalur asli, hanya LLM yang dipalsukan
    from app.services.agents import documents

    monkeypatch.setattr(documents, "llm_chat_ex", fake)
    d = client.post(f"/theses/{tid}/data", headers=h, json={"title": "Transkrip wawancara", "kind": "text", "content": TRANSCRIPT}).json()
    r = client.post(f"/theses/{tid}/data/{d['data_id']}/analyze", headers=h)
    assert r.status_code == 200, r.text
    themes = r.json()["data"]["analysis"]["themes"]
    assert [t["name"] for t in themes] == ["Kepercayaan diri meningkat", "Ketergantungan pada AI"], "tema tanpa kutipan terverifikasi dibuang"
    assert len(themes[0]["excerpts"]) == 1, "kutipan karangan dibuang"
    table = r.json()["tables"][0]
    assert table["title"].startswith("Tema hasil pengodean") and "diverifikasi otomatis" in table["note"]


def test_writer_context_includes_user_data(client, auth):
    from app.core import db as core_db
    from app.models.models import Thesis
    from app.services.agents.context import results_data

    h = auth["headers"]
    tid = _thesis(client, h, " d4")
    client.post(f"/theses/{tid}/data", headers=h, json={"title": "Catatan observasi", "kind": "text", "content": "Siswa terlihat gugup pada menit pertama presentasi lalu mulai tenang."})
    db = core_db.SessionLocal()
    assert "Catatan observasi" in results_data(db.get(Thesis, tid))
    db.close()


def test_data_limits_and_ownership(client, auth):
    h = auth["headers"]
    tid = _thesis(client, h, " d5")
    assert client.post(f"/theses/{tid}/data", headers=h, json={"title": "x", "kind": "pdf", "content": "isi"}).status_code == 422
    other = client.post("/auth/register", json={"full_name": "Lain", "email": "lain-data@test.id", "password": "rahasia123", "major_name": "TI", "campus_name": "X"}).json()
    oh = {"Authorization": f"Bearer {other['access_token']}"}
    assert client.get(f"/theses/{tid}/data", headers=oh).status_code == 404


def test_english_thesis_gets_english_table_labels(client, auth):
    h = auth["headers"]
    tid = client.post("/theses", headers=h, json={"topic": "Students Engagement and Digital Media Use in Classroom", "method": "KUANTITATIF", "language": "en"}).json()["thesis_id"]
    d = client.post(f"/theses/{tid}/data", headers=h, json={"title": "Scores", "kind": "table", "content": CSV}).json()
    r = client.post(f"/theses/{tid}/data/{d['data_id']}/analyze", headers=h).json()
    titles = [t["title"] for t in r["tables"]]
    assert titles[0].startswith("Descriptive statistics") and "Distribution of Kelas" in titles
    assert r["tables"][0]["columns"][:3] == ["Variable", "n", "Mean"]
