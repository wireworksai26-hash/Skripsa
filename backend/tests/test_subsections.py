import asyncio
import json

from app.core import db as core_db
from app.models.models import Thesis, ThesisSection
from app.services.agents import documents, outline, writer
from app.services.agents.context import section_plan

TOPIC = "Pengaruh Kecemasan Berbicara terhadap Kemauan Berkomunikasi Mahasiswa EFL"


def _thesis(client, h, suffix="", **extra):
    r = client.post("/theses", headers=h, json={"topic": TOPIC + suffix, "method": "KUANTITATIF", "variable_x": "Kecemasan berbicara", "variable_y": "Kemauan berkomunikasi", "subject": "Mahasiswa EFL", **extra})
    tid = r.json()["thesis_id"]
    client.post(f"/theses/{tid}/sections/build", headers=h)
    return tid


def _fake_llm(monkeypatch, handler):
    calls = []

    async def fake(messages, tier="heavy", temperature=0.3, max_tokens=1600, only=None):
        calls.append(messages)
        return json.dumps(handler(messages)), "fake"

    monkeypatch.setattr(documents, "llm_chat_ex", fake)
    return calls


def test_clean_title_rejects_numbering_years_numbers_and_long_titles():
    assert outline.clean_title("2.1.1 Kecemasan Berbicara dalam Kelas EFL.") == "Kecemasan Berbicara dalam Kelas EFL"
    assert outline.clean_title('"Willingness to Communicate"') == "Willingness to Communicate"
    assert outline.clean_title("Teori Bandura (1997)") == "", "tahun = kutipan, bukan judul"
    assert outline.clean_title("Peningkatan 47% pada kemauan berkomunikasi") == ""
    assert outline.clean_title("Smith et al. tentang kecemasan") == ""
    assert outline.clean_title("kata " * 20) == ""
    assert outline.clean_title("") == ""


def test_clean_children_dedupes_clamps_and_needs_two():
    kids = outline.clean_children("Landasan Teori", 600, [{"title": "A. Kecemasan", "words": 5000}, {"title": "kecemasan"}, {"title": "Landasan Teori"}, {"title": "Kemauan Berkomunikasi", "words": 10}, "Efikasi Diri"])
    assert [k["title"] for k in kids] == ["Kecemasan", "Kemauan Berkomunikasi", "Efikasi Diri"]
    assert [k["target_words"] for k in kids] == [800, 80, 200], "dibatasi 80-800; tanpa angka = bagi rata target induk"
    assert outline.clean_children("X", 600, [{"title": "Satu saja"}]) == [], "satu anak bukan pemecahan"
    assert outline.clean_children("X", 600, "bukan daftar") == []
    assert len(outline.clean_children("X", 900, [{"title": f"Bagian {chr(65 + i)}"} for i in range(9)])) == 5


def test_propose_endpoint_validates_ignores_unknown_codes_and_skips_existing(client, auth, monkeypatch):
    h = auth["headers"]
    tid = _thesis(client, h, " sub1")
    secs = {s["section_code"]: s for s in client.get(f"/theses/{tid}", headers=h).json()["sections"]}
    parents = [c for c, s in secs.items() if c.count(".") == 1 and s["target_words"] >= 300 and c.startswith("2.")]
    assert parents, "templat bawaan punya subbab Bab II >= 300 kata"
    first = parents[0]

    def handler(messages):
        assert "Kecemasan berbicara" in messages[-1]["content"], "topik dan variabel dikirim ke agen"
        return {"sections": [
            {"code": first, "children": [{"title": "1. Kecemasan Berbicara pada Mahasiswa EFL", "words": 200}, {"title": "Kemauan Berkomunikasi dalam Bahasa Kedua", "words": 200}, {"title": "Teori Horwitz (1986)"}]},
            {"code": "9.9", "children": [{"title": "Tidak ada"}, {"title": "Juga tidak ada"}]},
            {"code": "1.1.1", "children": [{"title": "Sudah level tiga"}, {"title": "Tidak boleh"}]},
        ]}

    calls = _fake_llm(monkeypatch, handler)
    r = client.post(f"/theses/{tid}/structure/suggest", headers=h, json={})
    assert r.status_code == 200, r.text
    out = r.json()
    assert list(out["suggestions"]) == [first], "kode di luar daftar diabaikan"
    kids = out["suggestions"][first]
    assert [k["title"] for k in kids] == ["Kecemasan Berbicara pada Mahasiswa EFL", "Kemauan Berkomunikasi dalam Bahasa Kedua"], "nomor dibuang, judul bertahun ditolak"
    assert calls and out["provider"] == "fake"

    # Setelah disimpan, subbab itu sudah punya anak dan tidak diusulkan ulang.
    chapters = []
    detail = client.get(f"/theses/{tid}", headers=h).json()
    by_ch = {}
    for s in sorted(detail["sections"], key=lambda s: [int(p) for p in s["section_code"].split(".")]):
        by_ch.setdefault(s["chapter_code"], []).append(s)
    titles = {c["chapter_number"]: c["chapter_title"] for c in client.get(f"/templates/{detail['campus_template_id']}", headers=h).json()["chapters"]}
    for ch, rows in by_ch.items():
        secs_in = []
        for s in rows:
            secs_in.append({"code": s["section_code"], "title": s["section_title"], "target_words": s["target_words"], "level": 2 if s["section_code"].count(".") > 1 else 1})
            if s["section_code"] == first:
                secs_in += [{"code": None, "title": k["title"], "target_words": k["target_words"], "level": 2} for k in kids]
        chapters.append({"title": titles.get(ch, f"Bab {ch}"), "sections": secs_in})
    save = client.put(f"/theses/{tid}/structure", headers=h, json={"chapters": chapters})
    assert save.status_code == 200, save.text
    saved_codes = {s["section_code"] for s in save.json()["sections"]}
    assert f"{first}.1" in saved_codes and f"{first}.2" in saved_codes

    again = client.post(f"/theses/{tid}/structure/suggest", headers=h, json={"chapters": [first.split(".")[0]]}).json()
    assert first in again["skipped"] and first not in again["suggestions"]


def test_propose_reports_llm_failure_and_requires_owner(client, auth, monkeypatch):
    h = auth["headers"]
    tid = _thesis(client, h, " sub2")
    from app.services.llm import LLMUnavailable

    async def down(messages, **kw):
        raise LLMUnavailable("semua penyedia gagal")

    monkeypatch.setattr(documents, "llm_chat_ex", down)
    assert client.post(f"/theses/{tid}/structure/suggest", headers=h, json={}).status_code == 503
    assert client.post(f"/theses/{tid}/structure/suggest", json={}).status_code in (401, 403)


def _sections(*rows):
    return [ThesisSection(chapter_code=c.split(".")[0], section_code=c, section_title=t, target_words=w) for c, t, w in rows]


def test_section_plan_parent_writes_intro_and_child_stays_in_its_lane():
    secs = _sections(("2.1", "Landasan Teori", 600), ("2.1.1", "Kecemasan Berbicara", 250), ("2.1.2", "Kemauan Berkomunikasi", 250), ("2.2", "Penelitian Terdahulu", 400))
    parent = section_plan(secs, secs[0])
    assert parent["target_words"] == 150 and "pengantar singkat" in parent["outline_hint"]
    assert "2.1.1 Kecemasan Berbicara" in parent["outline_hint"] and "2.1.2 Kemauan Berkomunikasi" in parent["outline_hint"]
    child = section_plan(secs, secs[1])
    assert child["target_words"] == 250
    assert "2.1 Landasan Teori" in child["outline_hint"] and "2.1.2 Kemauan Berkomunikasi" in child["outline_hint"] and "JANGAN dibahas" in child["outline_hint"]
    assert "2.1.1 Kecemasan" not in child["outline_hint"].split("saudara")[1], "daftar saudara tidak memuat dirinya sendiri"
    plain = section_plan(secs, secs[3])
    assert plain["target_words"] == 400 and "outline_hint" not in plain, "subbab tanpa anak tidak berubah"


def test_writer_prompt_carries_outline_hint(monkeypatch):
    captured = {}

    async def fake(messages, **kw):
        captured["user"] = messages[-1]["content"]
        raise RuntimeError("cukup, hanya prompt yang diperiksa")

    monkeypatch.setattr(writer, "llm_chat_ex", fake)
    secs = _sections(("2.1", "Landasan Teori", 600), ("2.1.1", "Kecemasan Berbicara", 250), ("2.1.2", "Kemauan Berkomunikasi", 250))
    refs = [{"citation_id": "r1", "authors": ["Nur"], "publication_year": 2021, "title": "T", "doi": None, "evidence": ["Kalimat bukti."]}]
    try:
        asyncio.run(writer.generate_section_draft(section_plan(secs, secs[1]), {"topic": TOPIC, "language": "id"}, refs, "APA_7TH", ""))
    except Exception:
        pass
    assert "STRUKTUR:" in captured.get("user", "") and "2.1.2 Kemauan Berkomunikasi" in captured["user"]
