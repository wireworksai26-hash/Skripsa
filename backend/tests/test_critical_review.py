"""Skor review harus kritis: naskah cacat tidak boleh lolos dengan nilai tinggi (audit 7 Nov 2026)."""

import asyncio
import json

from app.core import db as core_db
from app.models.models import Thesis, ThesisSection
from app.services.agents import advisor, guardrail

GOOD = (
    "Penelitian terdahulu menunjukkan bahwa media digital yang dirancang interaktif memperbesar keterlibatan siswa "
    "dalam pembelajaran sains di sekolah menengah atas pada berbagai wilayah di Indonesia. Namun belum ada kajian "
    "yang menguji hubungan tersebut pada kelas dengan akses perangkat terbatas sehingga celah ini perlu dijawab {n}. Oleh karena itu penelitian ini menguji pengaruh media digital terhadap motivasi belajar siswa secara kuantitatif."
)


def _make(client, headers, suffix=""):
    tid = client.post(
        "/theses", headers=headers,
        json={"topic": "Pengaruh Media Digital terhadap Motivasi Belajar" + suffix, "variable_x": "Media Digital", "variable_y": "Motivasi", "subject": "Siswa SMA", "method": "KUANTITATIF"},
    ).json()["thesis_id"]
    client.post(f"/theses/{tid}/sections/build", headers=headers)
    return tid


def _fill(tid, mapping):
    db = core_db.SessionLocal()
    try:
        for s in db.query(ThesisSection).filter(ThesisSection.thesis_id == tid).all():
            if s.section_code in mapping:
                s.content_markdown = mapping[s.section_code]
        db.commit()
    finally:
        db.close()


def _run(tid, coro_fn):
    db = core_db.SessionLocal()
    try:
        thesis = db.get(Thesis, tid)
        return asyncio.run(coro_fn(thesis, db))
    finally:
        db.close()


def test_guardrail_caps_duplicates_placeholders_and_essay_forms(client, auth):
    tid = _make(client, auth["headers"], " A")
    dup = GOOD.format(n="satu")
    _fill(tid, {"1.1": dup, "1.2": dup, "1.3": "Rumusan masalah penelitian ini penting karena " + GOOD.format(n="dua") + " [DATA: n responden]"})
    res = _run(tid, guardrail.guardrail_review)

    assert res["score"] <= 69, res["caps"]
    assert res["cap"] == 69 and res["facts"]["duplicate_pairs"] >= 1 and res["facts"]["placeholders"] == 1
    keys = {b["key"] for b in res["breakdown"]}
    assert {"coverage", "originality", "form", "cite_cov", "doi", "data", "readability"} <= keys
    assert any("duplikat" in n["text"] for n in res["notes"])
    assert any("belum Anda ganti" in n["text"] for n in res["notes"])


def test_guardrail_length_alone_no_longer_buys_a_high_score(client, auth):
    tid = _make(client, auth["headers"], " B")
    long = " ".join(GOOD.format(n=f"k{i}") + f" Kalimat tambahan unik nomor {i} tentang topik {i * 7} berbeda." for i in range(40))
    _fill(tid, {"1.1": long})
    res = _run(tid, guardrail.guardrail_review)
    assert res["score"] < 75, "satu subbab panjang, sisanya kosong: tidak boleh dianggap bagus"
    assert res["cap"] is not None and any("kosong" in c for c in res["caps"])


def test_advisor_unverified_evidence_and_guardrail_facts_limit_scores(client, auth, monkeypatch):
    tid = _make(client, auth["headers"], " C")
    dup = GOOD.format(n="satu")
    _fill(tid, {"1.1": dup, "1.2": dup})

    async def lenient(messages, **kw):
        dims = {k: {"skor": 5, "bukti": "kutipan karangan yang sama sekali tidak ada di draf", "kritik": "bagus", "saran": "-"} for k in "ABCDEF"}
        return json.dumps({"dimensi": dims, "kelemahan_utama": []}), "fake"

    monkeypatch.setattr(advisor, "llm_chat_ex", lenient)

    async def go(thesis, db):
        rail = await guardrail.guardrail_review(thesis, db)
        return rail, await advisor.advisor_review(thesis, db, rail)

    rail, adv = _run(tid, go)
    assert adv["done"] is True
    assert all(b["detail"].endswith("bukti tidak terverifikasi") for b in adv["breakdown"])
    assert adv["score"] <= 2 / 5 * 100 and adv["score"] <= rail["cap"], "LLM yang terlalu ramah tetap tertahan"
    assert not [n for n in adv["notes"] if n["kind"] == "praise"], "pujian tanpa bukti ditolak"


def test_advisor_with_verified_evidence_scores_by_rubric(client, auth, monkeypatch):
    tid = _make(client, auth["headers"], " D")
    _fill(tid, {"1.1": GOOD.format(n="satu")})

    async def judge(messages, **kw):
        evidence = "belum ada kajian yang menguji hubungan tersebut pada kelas dengan akses perangkat terbatas"
        dims = {k: {"skor": 4, "bukti": evidence, "kritik": "Cukup tajam.", "saran": "Tambah data."} for k in "ABCDEF"}
        return json.dumps({"dimensi": dims, "kelemahan_utama": ["Belum ada data."]}), "fake"

    monkeypatch.setattr(advisor, "llm_chat_ex", judge)
    guard = {"facts": {}, "breakdown": [], "caps": [], "cap": None}
    adv = _run(tid, lambda t, d: advisor.advisor_review(t, d, guard))
    assert adv["done"] is True and adv["score"] == 80 and sum(b["max"] for b in adv["breakdown"]) == 100
    assert any(n["kind"] == "praise" for n in adv["notes"])


def test_advisor_without_llm_is_not_done_and_has_no_score(client, auth, monkeypatch):
    from app.services.llm import LLMUnavailable

    tid = _make(client, auth["headers"], " E")
    _fill(tid, {"1.1": GOOD.format(n="satu")})

    async def down(*a, **k):
        raise LLMUnavailable("semua penyedia gagal")

    monkeypatch.setattr(advisor, "llm_chat_ex", down)
    adv = _run(tid, lambda t, d: advisor.advisor_review(t, d, {}))
    assert adv["done"] is False and "score" not in adv and "tidak dapat dibuat" in adv["notes"][0]["text"]
