import asyncio
import json

import pytest

from app.services.agents import visual_planner as vp
from app.services.llm import LLMUnavailable

CODES = {"1", "2", "3", "4", "5"}
FLOW = 'flowchart TD\n  A["Peer-presentations"] --> B["Teacher wrap-up"]\n  B --> C["Perceptions"]'
REFS = [
    {"citation_id": "a", "title": "PEER PRESENTATIONS AND ENGAGEMENT IN EFL CLASSES", "authors": ["Dionne, J.", "Lee, K."], "publication_year": 2021,
     "journal_name": "ELT Journal", "highlighted_snippet": "Peer presentations increase engagement in EFL classes. Teacher feedback improves accuracy."},
    {"citation_id": "b", "title": "Wrap-up sessions", "authors": ["Preece, D."], "publication_year": 2025, "journal_name": None, "highlighted_snippet": ""},
]


def test_studies_table_is_built_from_real_metadata_only():
    t = vp.studies_table(REFS, "en")
    assert t["chapter"] == "2" and t["columns"][1] == "Author(s) & Year" and t["source"] == "auto"
    assert t["rows"][0] == ["1", "Dionne & Lee 2021", "Peer presentations and engagement in efl classes", "ELT Journal", "Peer presentations increase engagement in EFL classes."]
    assert t["rows"][1][1] == "Preece 2025" and t["rows"][1][3] == "-" and t["rows"][1][4] == "[no abstract available]"
    assert vp.studies_table([], "en") is None
    assert vp.studies_table(REFS, "id")["columns"][1] == "Penulis & Tahun"


def test_numbers_in_chapter_3_and_4_become_placeholders_unless_real_data_exists():
    item = {"chapter": "4", "type": "table", "title": "Descriptive statistics", "columns": ["Group", "n", "Mean", "Note"],
            "rows": [["Control", "30", "72,5", "ok"], ["Experiment", "[DATA: n]", "81.2%", "x"]]}
    out = vp.normalize([item], CODES, set(), has_data=False)[0]
    assert out["rows"][0] == ["Control", "[DATA: nilai]", "[DATA: nilai]", "ok"], "angka karangan diganti, teks biasa tetap"
    assert out["rows"][1][1] == "[DATA: n]" and out["rows"][1][2] == "[DATA: nilai]" and out["needs_data"] is True
    real = vp.normalize([item], CODES, set(), has_data=True)[0]
    assert real["rows"][0][1] == "30", "data nyata pengguna boleh dipakai"
    ch2 = vp.normalize([{**item, "chapter": "2", "title": "Years"}], CODES, set(), False)[0]
    assert ch2["rows"][0][1] == "30", "Bab II tidak diubah"


def test_normalize_validates_chapter_type_mermaid_duplicates_and_limits():
    items = [
        {"chapter": "9", "type": "table", "title": "Bab tak ada", "columns": ["a", "b"], "rows": [["x", "y"]]},
        {"chapter": "3", "type": "chart", "title": "Jenis salah", "columns": ["a", "b"], "rows": [["x", "y"]]},
        {"chapter": "3", "type": "table", "title": "Satu kolom", "columns": ["a"], "rows": [["x"]]},
        {"chapter": "3", "type": "diagram", "title": "Bukan mermaid", "mermaid": "tolong gambar alur penelitian"},
        {"chapter": "3", "type": "diagram", "title": "Alur analisis", "mermaid": f"```mermaid\n{FLOW}\n```", "rationale": "Perlu."},
        {"chapter": "3", "type": "table", "title": "alur ANALISIS", "columns": ["a", "b"], "rows": [["x", "y"]]},
        {"chapter": "3", "type": "table", "title": "Sudah ada di proyek", "columns": ["a", "b"], "rows": [["x", "y"]]},
        {"chapter": "3", "type": "table", "title": "T1", "columns": ["a", "b"], "rows": [["x", "y"]]},
        {"chapter": "3", "type": "table", "title": "T2", "columns": ["a", "b"], "rows": [["x", "y"]]},
        {"chapter": "3", "type": "table", "title": "T3 melebihi 3 per bab", "columns": ["a", "b"], "rows": [["x", "y"]]},
    ]
    out = vp.normalize(items, CODES, {"sudah ada di proyek"}, False)
    assert [o["title"] for o in out] == ["Alur analisis", "T1", "T2"], "maks 3 per bab; duplikat & tidak valid dibuang"
    assert out[0]["mermaid"] == FLOW and out[0]["type"] == "diagram" and out[0]["columns"] == []
    wide = vp.normalize([{"chapter": "2", "type": "table", "title": "Lebar", "columns": [f"c{i}" for i in range(12)], "rows": [["1"] * 3]}], CODES, set(), False)[0]
    assert len(wide["columns"]) == vp.MAX_COLS and len(wide["rows"][0]) == vp.MAX_COLS, "baris dipadatkan sesuai kolom"


def _llm(monkeypatch, answers, seen=None):
    it = iter(answers)

    async def fake(messages, tier="heavy", temperature=0.4, max_tokens=1600, only=None):
        if seen is not None:
            seen.append(messages)
        a = next(it)
        return (a if isinstance(a, str) else json.dumps(a)), "fake"

    monkeypatch.setattr(vp, "llm_chat_ex", fake)


CH = [{"code": c, "title": f"Bab {c}", "sections": ["a", "b"], "excerpt": ""} for c in ("1", "2", "3", "4")]
CTX = {"title": "Students' voices on peer presentations", "method": "KUALITATIF", "domain": "ENGLISH_EDUCATION", "degree_level": "S1", "language": "en", "results_data": ""}


def test_plan_combines_generated_studies_table_with_llm_items_and_guides_by_method(monkeypatch):
    seen = []
    _llm(monkeypatch, [{"items": [
        {"chapter": "3", "type": "table", "title": "Participant profile", "columns": ["Code", "Semester"], "rows": [["S1", "[DATA: semester]"]], "rationale": "Perlu."},
        {"chapter": "2", "type": "diagram", "title": "Conceptual framework", "mermaid": FLOW, "rationale": "Perlu."},
    ]}], seen)
    items, provider = asyncio.run(vp.plan_visuals(CTX, CH, REFS, [], None, "fokus partisipan"))
    assert [i["title"] for i in items] == ["Summary of relevant studies", "Participant profile", "Conceptual framework"]
    assert items[0]["source"] == "auto" and all(i["id"] for i in items) and provider == "fake"
    prompt = seen[0][-1]["content"]
    assert "Qualitative study" in prompt and "Miles, Huberman" in prompt and "Language of all visual text: English" in prompt
    assert "fokus partisipan" in prompt and "No field data has been saved yet" in prompt
    assert "QUANTITATIVE" not in prompt.upper().replace("QUALITATIVE", "")


def test_plan_respects_chapter_filter_existing_and_real_data(monkeypatch):
    seen = []
    _llm(monkeypatch, [{"items": [{"chapter": "4", "type": "table", "title": "Hasil", "columns": ["Kelompok", "Mean"], "rows": [["Kontrol", "62,2"]]}]}], seen)
    ctx = {**CTX, "method": "KUANTITATIF", "language": "id", "results_data": "Statistik deskriptif:\nKelompok | Mean\nKontrol | 62,2"}
    items, _ = asyncio.run(vp.plan_visuals(ctx, CH, REFS, ["Ringkasan penelitian yang relevan"], {"4"}, ""))
    assert [i["title"] for i in items] == ["Hasil"], "tabel penelitian relevan tidak diulang & bab 2 tidak diminta"
    assert items[0]["rows"][0][1] == "62,2", "data nyata pengguna dipertahankan"
    prompt = seen[0][-1]["content"]
    assert "Quantitative study" in prompt and "REAL RESEARCH DATA" in prompt and "- Chapter 2 " not in prompt and "- Chapter 4 " in prompt


def test_plan_retries_bad_json_and_keeps_studies_table_when_llm_fails(monkeypatch):
    _llm(monkeypatch, ["bukan json", {"items": [{"chapter": "3", "type": "diagram", "title": "Alur", "mermaid": FLOW}]}])
    items, _ = asyncio.run(vp.plan_visuals(CTX, CH, REFS, [], None, ""))
    assert [i["title"] for i in items] == ["Summary of relevant studies", "Alur"]

    _llm(monkeypatch, [{"items": []}, {"items": []}])
    items, provider = asyncio.run(vp.plan_visuals(CTX, CH, REFS, [], None, ""))
    assert [i["title"] for i in items] == ["Summary of relevant studies"], "bagian buatan kode tetap berguna"

    _llm(monkeypatch, [{"items": []}, {"items": []}])
    with pytest.raises(LLMUnavailable, match="tidak ada usulan"):
        asyncio.run(vp.plan_visuals(CTX, CH, [], [], None, ""))


def test_endpoint(client, auth, monkeypatch):
    from app.routers import visuals as router_mod

    headers = auth["headers"]
    tid = client.post("/theses", headers=headers, json={"topic": "Pengaruh Media Digital terhadap Motivasi Belajar", "method": "KUALITATIF", "language": "en"}).json()["thesis_id"]
    assert client.post(f"/theses/{tid}/visuals/plan", json={}).status_code == 401
    assert client.post(f"/theses/{tid}/visuals/plan", headers=headers, json={}).status_code == 503, "tanpa LLM: error jelas"

    cit = client.post(f"/theses/{tid}/citations", headers=headers, json=[{"title": "Media Digital", "authors": ["Nur, A."], "publication_year": 2021, "highlighted_snippet": "Media digital meningkatkan motivasi belajar siswa."}]).json()[0]
    client.patch(f"/theses/{tid}", headers=headers, json={"selected_ref_ids": [cit["citation_id"]]})
    client.post(f"/theses/{tid}/tables", headers=headers, json={"title": "Sudah ada", "columns": ["a"], "rows": [["1"]]})
    seen = []
    _llm(monkeypatch, [{"items": [{"chapter": "3", "type": "table", "title": "Sudah ada", "columns": ["a", "b"], "rows": [["x", "y"]]}, {"chapter": "3", "type": "diagram", "title": "Alur", "mermaid": FLOW}]}], seen)
    res = client.post(f"/theses/{tid}/visuals/plan", headers=headers, json={"chapters": ["2", "3", "x"]})
    assert res.status_code == 200, res.text
    titles = [i["title"] for i in res.json()["items"]]
    assert titles == ["Summary of relevant studies", "Alur"], "judul yang sudah tersimpan tidak diusulkan lagi"
    prompt = seen[0][-1]["content"]
    assert "Sudah ada" in prompt and "- Chapter 3 " in prompt and "- Chapter 5 " not in prompt, "hanya bab yang diminta"
    assert client.get(f"/theses/{tid}/tables", headers=headers).json()[0]["title"] == "Sudah ada" and len(client.get(f"/theses/{tid}/tables", headers=headers).json()) == 1, "usulan tidak disimpan otomatis"


def test_rationale_instruction_prefix_is_stripped():
    out = vp.normalize([{"chapter": "3", "type": "table", "title": "T", "columns": ["a", "b"], "rows": [["x", "y"]],
                         "rationale": "satu kalimat bahasa Indonesia: tabel ini menjelaskan peserta."}], CODES, set(), False)[0]
    assert out["rationale"] == "tabel ini menjelaskan peserta."
