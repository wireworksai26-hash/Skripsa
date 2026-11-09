import time

from tests.conftest import _ensure_user


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "scientific_apis" in body


def test_register_login_me(client, auth):
    resp = client.post(
        "/auth/login",
        json={"email": auth["email"], "password": "rahasia123"},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == auth["email"]

    bad = client.get("/auth/me", headers={"Authorization": "Bearer rusak"})
    assert bad.status_code == 401


def test_full_thesis_flow(client, auth, fake_llm):
    headers = auth["headers"]

    thesis = client.post(
        "/theses",
        headers=headers,
        json={
            "topic": "Pengaruh Media Digital terhadap Motivasi Belajar Siswa SMA",
            "variable_x": "Media Digital",
            "variable_y": "Motivasi Belajar",
            "subject": "Siswa SMA Negeri",
            "method": "KUANTITATIF",
            "domain": "INFORMATIKA",
            "degree_level": "S1",
        },
    )
    assert thesis.status_code == 201, thesis.text
    body = thesis.json()
    tid = body["thesis_id"]
    assert body["campus_template_id"]

    titles = client.post(f"/theses/{tid}/titles", headers=headers)
    assert titles.status_code == 200
    titles_data = titles.json()
    assert titles_data["provider"] == "fake"
    assert fake_llm == ["fast"], "judul = tugas ringan"
    assert len(titles_data["titles"]) == 5

    pick = client.patch(
        f"/theses/{tid}",
        headers=headers,
        json={
            "title": titles_data["titles"][0]["text"],
            "picked_title_id": titles_data["titles"][0]["title_id"],
        },
    )
    assert pick.status_code == 200
    assert pick.json()["title"] == titles_data["titles"][0]["text"]

    built = client.post(f"/theses/{tid}/sections/build", headers=headers)
    assert built.status_code == 200

    sections = client.get(f"/theses/{tid}/sections", headers=headers)
    assert sections.status_code == 200
    rows = sections.json()
    assert len(rows) >= 10

    refs = client.post(
        f"/theses/{tid}/citations",
        headers=headers,
        json=[
            {
                "doi": "10.1000/fake-doi",
                "title": "Kualitatif Pendidikan Media Digital",
                "authors": ["Nur, A.", "Putri, B."],
                "publication_year": 2021,
                "journal_name": "Jurnal Pendidikan Digital",
                "volume_issue": "5(2)",
                "page_range": "101-115",
                "highlighted_snippet": (
                    "Media digital terbukti meningkatkan motivasi belajar siswa dalam "
                    "pembelajaran di kelas secara signifikan menurut penelitian ini."
                ),
            }
        ],
    )
    assert refs.status_code == 201
    ref = refs.json()[0]
    ref_id = ref["citation_id"]

    linked = client.patch(f"/theses/{tid}", headers=headers, json={"selected_ref_ids": [ref_id]})
    assert linked.status_code == 200

    generated = client.post(f"/theses/{tid}/sections/1.1/generate", headers=headers)
    assert generated.status_code == 200, generated.text
    gen = generated.json()
    assert gen["provider"] == "fake"
    assert gen["word_count"] > 40
    assert fake_llm[-1] == "heavy", "draf subbab = tugas berat"
    assert [c["reference_id"] for c in gen["citations_json"]] == [ref_id], "sitasi ke id tak dikenal harus dibuang"

    rag = client.post(
        "/rag/index",
        params={"thesis_id": tid},
        headers=headers,
        json={"citation_ids": [ref_id]},
    )
    assert rag.status_code == 200

    searched = client.post(
        "/rag/search",
        headers=headers,
        json={"query": "media digital motivasi belajar", "k": 3},
    )
    assert searched.status_code == 200
    assert searched.json()["hits"]

    chart = client.post(
        f"/theses/{tid}/charts",
        headers=headers,
        json={
            "kind": "bar",
            "title": "Skor Motivasi",
            "xlabel": "Kelas",
            "ylabel": "Skor",
            "series": [
                {"label": "Kontrol", "value": 65.2},
                {"label": "Eksperimen", "value": 78.4},
            ],
            "caption": "Perbandingan skor motivasi belajar.",
        },
    )
    assert chart.status_code == 200

    review = client.post(f"/theses/{tid}/review", headers=headers)
    assert review.status_code == 200
    reviews = review.json()["reviews"]
    assert set(reviews) == {"ADVISOR", "EXAMINER", "GUARDRAIL"}
    assert all(r["done"] for r in reviews.values())

    export = client.get(f"/theses/{tid}/export.docx", headers=headers)
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert len(export.content) > 5000

    thesis_list = client.get("/theses", headers=headers)
    assert thesis_list.status_code == 200

    deleted = client.delete(f"/theses/{tid}", headers=headers)
    assert deleted.status_code == 204


def test_run_pipeline_job_completes(client, auth, fake_llm):
    headers = auth["headers"]
    thesis = client.post(
        "/theses",
        headers=headers,
        json={
            "topic": "Pengaruh Gamifikasi terhadap Hasil Belajar Siswa SMP",
            "variable_x": "Gamifikasi",
            "variable_y": "Hasil Belajar",
            "subject": "Siswa SMP",
        },
    )
    assert thesis.status_code == 201
    tid = thesis.json()["thesis_id"]

    cit = client.post(
        f"/theses/{tid}/citations",
        headers=headers,
        json=[{"title": "Gamifikasi dan Hasil Belajar", "authors": ["Nur, A."], "publication_year": 2021, "highlighted_snippet": "Gamifikasi meningkatkan hasil belajar."}],
    ).json()[0]
    client.patch(f"/theses/{tid}", headers=headers, json={"selected_ref_ids": [cit["citation_id"]]})

    run = client.post(f"/theses/{tid}/pipeline/run", headers=headers)
    assert run.status_code == 200
    job_id = run.json()["job_id"]

    status_final, logs = None, []
    for _ in range(100):
        resp = client.get(f"/theses/{tid}/pipeline/jobs/{job_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        status_final = data["status"]
        logs = data["logs"]
        if status_final in ("COMPLETED", "FAILED"):
            break
        time.sleep(0.1)

    assert status_final == "COMPLETED", (status_final, logs)

    detail = client.get(f"/theses/{tid}", headers=headers).json()
    assert detail["status"] == "DRAF_FINAL"
    assert detail["review_json"], "review harus tersimpan"
    drafted = [s for s in detail["sections"] if s["word_count"] > 30]
    assert drafted, "minimal satu subbab terisi"

    client.delete(f"/theses/{tid}", headers=headers)


def test_thesis_isolated_between_users(client, auth):
    headers = auth["headers"]
    other = _ensure_user(
        client,
        {
            "full_name": "Mahasiswa Lain",
            "email": "lain@test.id",
            "password": "rahasia456",
            "major_name": "Sistem Informasi",
            "campus_name": "Universitas Uji",
        },
    )
    other_headers = other["headers"]

    thesis = client.post(
        "/theses",
        headers=headers,
        json={"topic": "Skripsi Milik Pengguna Pertama Saja di Sistem"},
    )
    tid = thesis.json()["thesis_id"]

    hacker = client.get(f"/theses/{tid}", headers=other_headers)
    assert hacker.status_code == 404


def test_diagram_roundtrip(client, auth):
    headers = auth["headers"]
    tid = client.post(
        "/theses",
        headers=headers,
        json={"topic": "Pengaruh Media Digital terhadap Motivasi Belajar", "method": "KUANTITATIF"},
    ).json()["thesis_id"]

    bad = client.post(f"/theses/{tid}/diagrams", headers=headers, json={"code": "graph TD; A-->B"})
    assert bad.status_code == 422

    png = "data:image/png;base64,iVBORw0KGgo="
    ok = client.post(
        f"/theses/{tid}/diagrams",
        headers=headers,
        json={"title": "Alur", "code": "graph TD; A-->B", "image": png, "width": 10, "height": 20},
    )
    assert ok.status_code == 200 and ok.json()["total_diagrams"] == 1
    did = ok.json()["diagram_id"]

    got = client.get(f"/theses/{tid}", headers=headers).json()
    assert got["diagrams_json"][0]["id"] == did

    gone = client.delete(f"/theses/{tid}/diagrams/{did}", headers=headers)
    assert gone.json()["total_diagrams"] == 0


def test_no_llm_means_503_not_fake_text(client, auth):
    """Tanpa kunci LLM, judul tidak boleh dikarang: server menjawab 503 dengan pesan jelas."""
    headers = auth["headers"]
    tid = client.post(
        "/theses", headers=headers, json={"topic": "Pengaruh Media Digital terhadap Motivasi Belajar"}
    ).json()["thesis_id"]
    res = client.post(f"/theses/{tid}/titles", headers=headers)
    assert res.status_code == 503
    assert "LLM" in res.json()["detail"]
    assert client.get(f"/theses/{tid}/titles", headers=headers).json() == []


def test_draft_requires_selected_refs(client, auth, fake_llm):
    headers = auth["headers"]
    tid = client.post(
        "/theses", headers=headers, json={"topic": "Pengaruh Media Digital terhadap Motivasi Belajar"}
    ).json()["thesis_id"]
    client.post(f"/theses/{tid}/sections/build", headers=headers)
    res = client.post(f"/theses/{tid}/sections/1.1/generate", headers=headers)
    assert res.status_code == 422


def test_stats_endpoint_and_tables_roundtrip(client, auth):
    headers = auth["headers"]
    tid = client.post("/theses", headers=headers, json={"topic": "Pengaruh Media Digital terhadap Motivasi Belajar"}).json()["thesis_id"]

    assert client.post("/stats/analyze", json={"groups": [{"name": "A", "values": [1, 2]}]}).status_code == 401
    res = client.post(
        "/stats/analyze",
        headers=headers,
        json={"groups": [{"name": "Kontrol", "values": [60, 62, 65, 61, 63]}, {"name": "Eksperimen", "values": [75, 78, 72, 80, 77]}]},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["test"]["test"] == "welch_t" and body["test"]["significant"] is True
    assert body["test"]["p"] < 0.001 and "Eksperimen" in body["interpretation"]

    dup = client.post("/stats/analyze", headers=headers, json={"groups": [{"name": "A", "values": [1, 2]}, {"name": "A", "values": [3, 4]}]})
    assert dup.status_code == 422 and "unik" in dup.json()["detail"]
    flat = client.post("/stats/analyze", headers=headers, json={"groups": [{"name": "A", "values": [5, 5, 5]}, {"name": "B", "values": [5, 5, 5]}]})
    assert flat.status_code == 422 and "SD = 0" in flat.json()["detail"]

    bad = client.post(f"/theses/{tid}/tables", headers=headers, json={"title": "T", "columns": ["a", "b"], "rows": [["1"]]})
    assert bad.status_code == 422
    ok = client.post(
        f"/theses/{tid}/tables",
        headers=headers,
        json={"title": "Statistik Deskriptif", "caption": "Hasil", "columns": ["Kelompok", "n"], "rows": [["Kontrol", "5"], ["Eksperimen", "5"]], "note": "Sumber: data primer"},
    )
    assert ok.status_code == 201
    table_id = ok.json()["table_id"]

    detail = client.get(f"/theses/{tid}", headers=headers).json()
    assert [t["title"] for t in detail["tables"]] == ["Statistik Deskriptif"]
    assert detail["tables"][0]["rows"][1] == ["Eksperimen", "5"]

    assert client.delete(f"/theses/{tid}/tables/{table_id}", headers=headers).status_code == 204
    assert client.get(f"/theses/{tid}/tables", headers=headers).json() == []


def test_diagram_engine_plantuml_accepted_and_unknown_rejected(client, auth):
    headers = auth["headers"]
    tid = client.post("/theses", headers=headers, json={"topic": "Pengaruh Media Digital terhadap Motivasi Belajar"}).json()["thesis_id"]
    png = "data:image/png;base64,iVBORw0KGgo="
    ok = client.post(f"/theses/{tid}/diagrams", headers=headers, json={"engine": "plantuml", "title": "Use case", "code": "@startuml\nA -> B\n@enduml", "image": png})
    assert ok.status_code == 200
    assert client.get(f"/theses/{tid}", headers=headers).json()["diagrams_json"][0]["engine"] == "plantuml"
    bad = client.post(f"/theses/{tid}/diagrams", headers=headers, json={"engine": "graphviz", "code": "digraph{}", "image": png})
    assert bad.status_code == 422


def _thesis_with_draft(client, headers):
    tid = client.post(
        "/theses", headers=headers,
        json={"topic": "Pengaruh Media Digital terhadap Motivasi Belajar", "variable_x": "Media Digital", "variable_y": "Motivasi", "subject": "Siswa SMA", "method": "KUANTITATIF"},
    ).json()["thesis_id"]
    client.post(f"/theses/{tid}/sections/build", headers=headers)
    cit = client.post(
        f"/theses/{tid}/citations", headers=headers,
        json=[{"title": "Media Digital dan Motivasi", "authors": ["Nur, A."], "publication_year": 2021, "highlighted_snippet": "Media digital meningkatkan motivasi belajar siswa secara signifikan."}],
    ).json()[0]
    client.patch(f"/theses/{tid}", headers=headers, json={"selected_ref_ids": [cit["citation_id"]]})
    return tid


def test_examiner_questions_are_grounded_in_draft_and_flagged_critical(client, auth, fake_llm, monkeypatch):
    headers = auth["headers"]
    tid = _thesis_with_draft(client, headers)
    assert client.post(f"/theses/{tid}/sections/1.1/generate", headers=headers).status_code == 200

    captured = {}
    from app.services.agents import review as review_mod

    real = review_mod.llm_chat_ex

    async def spy(messages, **kw):
        captured["user"] = messages[-1]["content"]
        return await real(messages, **kw)

    monkeypatch.setattr(review_mod, "llm_chat_ex", spy)
    res = client.post(f"/theses/{tid}/review", headers=headers).json()["reviews"]["EXAMINER"]

    assert res["done"] is True and len(res["notes"]) == 6 and "score" not in res, "tanpa skor karangan"
    assert res["notes"][0]["text"].startswith("P1 · Metodologi") and "Saran jawaban:" in res["notes"][0]["text"]
    assert [n["kind"] for n in res["notes"]].count("warn") == 1, "satu pertanyaan bertanda kritis -> warn"
    assert "Media Digital" in captured["user"] and "[1.1 Latar Belakang Masalah]" in captured["user"], "prompt memuat isi draf"
    assert "Nur, A." in captured["user"] and "Media Digital dan Motivasi" in captured["user"], "dan rujukan proyek"


def test_examiner_without_draft_or_llm_is_not_done_and_invents_nothing(client, auth, monkeypatch):
    headers = auth["headers"]
    tid = _thesis_with_draft(client, headers)

    res = client.post(f"/theses/{tid}/review", headers=headers).json()["reviews"]
    assert res["EXAMINER"]["done"] is False and "Belum ada draf" in res["EXAMINER"]["notes"][0]["text"]
    assert res["ADVISOR"]["done"] is False and "score" not in res["ADVISOR"], "pembimbing tidak menilai tanpa draf"
    assert res["GUARDRAIL"]["done"] is True, "guardrail tetap jalan"

    from app.services.agents import review as review_mod

    async def never(*a, **k):
        raise AssertionError("LLM tidak boleh dipanggil tanpa draf")

    monkeypatch.setattr(review_mod, "llm_chat_ex", never)
    assert client.post(f"/theses/{tid}/review", headers=headers).status_code == 200


def test_examiner_llm_failure_is_reported_not_faked(client, auth, fake_llm, monkeypatch):
    headers = auth["headers"]
    tid = _thesis_with_draft(client, headers)
    client.post(f"/theses/{tid}/sections/1.1/generate", headers=headers)

    from app.services.agents import review as review_mod
    from app.services.llm import LLMUnavailable

    async def down(*a, **k):
        raise LLMUnavailable("semua penyedia gagal")

    monkeypatch.setattr(review_mod, "llm_chat_ex", down)
    ex = client.post(f"/theses/{tid}/review", headers=headers).json()["reviews"]["EXAMINER"]
    assert ex["done"] is False and "semua penyedia gagal" in ex["notes"][0]["text"] and len(ex["notes"]) == 1

    answers = iter(["bukan json", "tetap bukan json"])

    async def junk(*a, **k):
        return next(answers), "fake"

    monkeypatch.setattr(review_mod, "llm_chat_ex", junk)
    ex = client.post(f"/theses/{tid}/review", headers=headers).json()["reviews"]["EXAMINER"]
    assert ex["done"] is False and "tidak layak" in ex["notes"][0]["text"]
