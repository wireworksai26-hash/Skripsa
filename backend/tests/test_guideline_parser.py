import asyncio
import json

import pytest

from app.services import guideline_parser as gp
from tests.conftest import _ensure_user
from tests.pdf_util import GUIDELINE_PAGES, make_pdf

GOOD = {
    "campus_name": "Universitas Contoh Nusantara",
    "faculty": "Fakultas Teknik dan Informatika",
    "degree_level": "S1",
    "page_setup": {
        "paper_size": "A4",
        "margins_cm": {"top": 4, "left": 4, "bottom": 3, "right": 3},
        "font_family": "Times New Roman",
        "font_size_pt": 12,
        "line_spacing": 1.5,
        "paragraph_indent_cm": 1,
    },
    "citation_style": "APA_7TH",
    "chapters": [
        {"chapter_number": "I", "chapter_title": "PENDAHULUAN", "sub_sections": [
            {"code": "1.1", "title": "Latar Belakang Masalah", "target_words": None},
            {"code": "1.2", "title": "Rumusan Masalah", "target_words": 300}]},
        {"chapter_number": "II", "chapter_title": "TINJAUAN PUSTAKA", "sub_sections": [{"code": "2.1", "title": "Landasan Teori"}]},
        {"chapter_number": "III", "chapter_title": "METODE PENELITIAN", "sub_sections": [{"code": "3.1", "title": "Desain Penelitian"}]},
        {"chapter_number": "IV", "chapter_title": "HASIL DAN PEMBAHASAN", "sub_sections": []},
        {"chapter_number": "V", "chapter_title": "PENUTUP", "sub_sections": [{"code": "5.1", "title": "Simpulan"}]},
    ],
    "evidence": {
        "margins": "Margin atas 4 cm, kiri 4 cm, bawah 3 cm, dan kanan 3 cm.",
        "font": "Jenis huruf Times New Roman ukuran 12 pt dengan spasi 1,5",
        "citation": "Sitasi dan daftar pustaka mengikuti gaya APA edisi ketujuh.",
    },
}


def _fake_llm(payloads):
    it = iter(payloads)

    async def fake(messages, tier="heavy", temperature=0.4, max_tokens=1600, only=None):
        p = next(it)
        return (p if isinstance(p, str) else json.dumps(p)), "fake"

    return fake


# ---------- ekstraksi PDF ----------

def test_extract_text_roundtrip_with_real_pdf():
    text = gp.extract_pdf_text(make_pdf(GUIDELINE_PAGES))
    assert len(text.pages) == 3
    assert "Margin atas 4 cm" in text.pages[1] and "BAB V PENUTUP" in text.pages[2]


def test_scanned_pdf_without_text_is_rejected_with_clear_message():
    with pytest.raises(gp.ParseError, match="hasil pindai"):
        gp.extract_pdf_text(make_pdf([[], [], []]))


def test_non_pdf_and_oversize_and_garbage():
    with pytest.raises(gp.ParseError, match="bukan PDF"):
        gp.extract_pdf_text(b"PK\x03\x04 ini docx")
    with pytest.raises(gp.ParseError) as e:
        gp.extract_pdf_text(b"%PDF-" + b"x" * (gp.MAX_PDF_BYTES + 1))
    assert e.value.status == 413
    with pytest.raises(gp.ParseError, match="tidak dapat dibaca|hasil pindai"):
        gp.extract_pdf_text(b"%PDF-1.4\nrusak total tanpa objek")


def test_select_relevant_keeps_front_pages_and_prefers_guideline_pages():
    filler = ["Kata pengantar dan ucapan terima kasih panjang lebar tanpa aturan apa pun. " * 3]
    pages = [["Sampul"], ["Daftar isi"]] + [filler] * 30 + [GUIDELINE_PAGES[1], GUIDELINE_PAGES[2]]
    text = gp.PdfText([" ".join(p) for p in pages])
    selected, used = gp.select_relevant(text, budget=900)
    assert "[hal. 1]" in selected and "Margin atas 4 cm" in selected and "BAB V PENUTUP" in selected
    assert "ucapan terima kasih" not in selected and used < 10


def test_letter_spaced_header_and_hyphenation_are_cleaned():
    cleaned = gp._clean_page_text(
        "i | P e d o m a n  P e n u l i s a n  S k r i p s i  F B S U n i m e d\npenuli-\nsan karya"
    )
    assert "Pedoman Penulisan Skripsi FBS Unimed" in cleaned
    assert "penulisan karya" in cleaned


def test_repeated_page_headers_are_removed():
    raw = [f"{n} | P e d o m a n  P e n u l i s a n  S k r i p s i\nisi halaman {n}" for n in range(1, 5)]
    pages = gp._strip_running_lines([gp._clean_page_text(p) for p in raw])
    assert all("Pedoman Penulisan" not in p for p in pages)
    assert "isi halaman 1" in pages[0]


def test_outline_reads_toc_numbering_styles_and_ignores_back_matter():
    text = "\n".join(
        [
            "DAFTAR ISI",
            "A. Bagian Awal",
            "a. Bab 1 Pendahuluan ............................ 8",
            "1) Latar Belakang ................................ 8",
            "2) Rumusan Masalah ............................... 9",
            "b. Bab 2 Kajian Pustaka .......................... 9",
            "d. Bab 4 Hasil Penelitian dan Pembahasan ........ 12",
            "a. Hasil Penelitian ............................. 12",
            "b. Pembahasan ................................... 12",
            "e. Bab 5 Simpulan dan Saran ...................... 13",
            "a. Simpulan ..................................... 13",
            "b. Saran ........................................ 13",
            "f. Daftar Rujukan ............................... 13",
            "I. Sanksi Terkait Penyusunan Skripsi ............ 13",
        ]
    )
    outline = gp.extract_outline(text)
    by_number = {c["chapter_number"]: c for c in outline}
    assert sorted(by_number) == [1, 2, 4, 5]
    assert [s["title"] for s in by_number[1]["sub_sections"]] == ["Latar Belakang", "Rumusan Masalah"]
    assert [s["title"] for s in by_number[4]["sub_sections"]] == ["Hasil Penelitian", "Pembahasan"]
    assert [s["title"] for s in by_number[5]["sub_sections"]] == ["Simpulan", "Saran"]


def test_outline_reads_inline_subsections():
    outline = gp.extract_outline("BAB I PENDAHULUAN: 1.1 Latar Belakang, 1.2 Rumusan Masalah.")
    assert outline[0]["chapter_number"] == 1
    assert [s["title"] for s in outline[0]["sub_sections"]] == ["Latar Belakang", "Rumusan Masalah"]


# ---------- validasi templat ----------

def test_rules_fill_page_setup_when_llm_omits_it():
    src = "\n".join(" ".join(p) for p in GUIDELINE_PAGES)
    tpl, rep = gp.build_template({"chapters": GOOD["chapters"]}, src, "pedoman.pdf")
    assert tpl["page_setup"]["margins_cm"] == {"top": 4.0, "left": 4.0, "bottom": 3.0, "right": 3.0}
    assert tpl["page_setup"]["font_family"] == "Times New Roman" and tpl["page_setup"]["font_size_pt"] == 12
    assert tpl["page_setup"]["line_spacing"] == 1.5 and tpl["page_setup"]["paragraph_indent_cm"] == 1.0
    assert tpl["citation_style"] == "APA_7TH" and tpl["degree_level"] == "S1"
    assert tpl["campus_name"] == "Universitas Contoh Nusantara"
    assert {
        "margin top",
        "margin left",
        "margin bottom",
        "margin right",
        "jenis huruf",
        "ukuran huruf",
        "spasi baris",
        "indentasi paragraf",
        "gaya sitasi",
        "nama kampus",
    } <= set(rep["extracted"])

def test_build_template_normalizes_numbering_and_fills_missing_subsections():
    src = " ".join(" ".join(p) for p in GUIDELINE_PAGES)
    tpl, rep = gp.build_template(GOOD, src, "pedoman.pdf")
    assert [c["chapter_number"] for c in tpl["chapters"]] == ["1", "2", "3", "4", "5"], "romawi -> angka berurutan"
    assert tpl["chapters"][0]["sub_sections"][0] == {"code": "1.1", "title": "Latar Belakang Masalah", "target_words": 400}
    assert tpl["chapters"][0]["sub_sections"][1]["target_words"] == 300
    assert len(tpl["chapters"][0]["sub_sections"]) == 4, "subbab dari daftar isi pedoman melengkapi jawaban LLM"
    assert [s["title"] for s in tpl["chapters"][3]["sub_sections"]] == ["Hasil Penelitian", "Pembahasan"]
    assert not any("bab tanpa subbab" in w for w in rep["warnings"])
    assert tpl["page_setup"]["margins_cm"] == {"top": 4.0, "left": 4.0, "bottom": 3.0, "right": 3.0}
    assert tpl["citation_style"] == "APA_7TH" and rep["defaulted"] == []
    assert rep["evidence"]["margins"]["verified"] is True and rep["evidence"]["font"]["verified"] is True


def test_out_of_range_values_fall_back_to_defaults_and_are_reported():
    bad = json.loads(json.dumps(GOOD))
    bad["page_setup"].update({"font_size_pt": 72, "line_spacing": "abc", "paragraph_indent_cm": -1})
    bad["page_setup"]["margins_cm"] = {"top": 15, "left": "4,5", "bottom": None, "right": 0}
    bad["citation_style"] = "VANCOUVER"
    tpl, rep = gp.build_template(bad, "", "x.pdf")
    ps = tpl["page_setup"]
    assert ps["font_size_pt"] == 12 and ps["line_spacing"] == 1.5 and ps["paragraph_indent_cm"] == 1.0
    assert ps["margins_cm"] == {"top": 4.0, "left": 4.5, "bottom": 3.0, "right": 3.0}, "koma desimal ala Indonesia terbaca"
    assert tpl["citation_style"] == "APA_7TH"
    for label in ("ukuran huruf", "spasi baris", "indentasi paragraf", "margin top", "margin bottom", "margin right", "gaya sitasi"):
        assert label in rep["defaulted"], label


def test_fabricated_evidence_is_flagged_unverified():
    fake = json.loads(json.dumps(GOOD))
    fake["evidence"]["margins"] = "Margin 2,54 cm di semua sisi sesuai standar Word."
    _, rep = gp.build_template(fake, " ".join(" ".join(p) for p in GUIDELINE_PAGES), "x.pdf")
    assert rep["evidence"]["margins"]["verified"] is False
    assert any("margins" in w and "tidak ditemukan" in w for w in rep["warnings"])


def test_unreadable_structure_falls_back_to_national_chapters_and_letter_paper_warns():
    tpl, rep = gp.build_template({"chapters": [{"chapter_title": "Satu"}], "page_setup": {"paper_size": "Letter"}}, "", "pedoman_kampus_x.pdf", "S2")
    assert tpl["campus_name"] == "pedoman kampus x" and tpl["degree_level"] == "S2"
    assert len(tpl["chapters"]) >= 3 and "sistematika bab" in rep["defaulted"]
    assert any("kerangka nasional" in w for w in rep["warnings"]) and any("LETTER" in w for w in rep["warnings"])
    assert tpl["page_setup"]["paper_size"] == "A4"


# ---------- alur penuh dengan LLM tiruan ----------

def test_parse_guideline_end_to_end(monkeypatch):
    monkeypatch.setattr(gp, "llm_chat_ex", _fake_llm([GOOD, "{\"translations\": {}}"]))
    out = asyncio.run(gp.parse_guideline(make_pdf(GUIDELINE_PAGES), "pedoman_ucn.pdf"))
    tpl, rep = out["template"], out["report"]
    assert tpl["campus_name"] == "Universitas Contoh Nusantara" and rep["pages"] == 3 and rep["provider"] == "fake"
    assert rep["evidence"]["citation"]["verified"] is True and rep["warnings"] == []
    assert len(tpl["chapters"][3]["sub_sections"]) == 2, "sistematika pedoman mengisi bab yang kosong"


def test_llm_bad_json_is_retried_once_then_gives_up(monkeypatch):
    from app.services.llm import LLMUnavailable

    monkeypatch.setattr(gp, "llm_chat_ex", _fake_llm(["maaf, ini bukan json", GOOD]))
    assert asyncio.run(gp.parse_guideline(make_pdf(GUIDELINE_PAGES), "a.pdf"))["template"]["citation_style"] == "APA_7TH"
    monkeypatch.setattr(gp, "llm_chat_ex", _fake_llm(["bukan json", "tetap bukan"]))
    with pytest.raises(LLMUnavailable, match="JSON"):
        asyncio.run(gp.parse_guideline(make_pdf(GUIDELINE_PAGES), "a.pdf"))


# ---------- endpoint ----------

def _upload(client, headers, pdf=None, name="pedoman.pdf"):
    return client.post(
        "/templates/parse",
        headers=headers,
        files={"file": (name, pdf if pdf is not None else make_pdf(GUIDELINE_PAGES), "application/pdf")},
        data={"degree_hint": "S1", "method_hint": "KUANTITATIF"},
    )


def test_templates_endpoints_full_flow(client, auth, monkeypatch):
    headers = auth["headers"]
    monkeypatch.setattr(gp, "llm_chat_ex", _fake_llm([GOOD, GOOD]))

    assert client.get("/templates").status_code == 401
    assert client.post("/templates/parse", files={"file": ("a.pdf", make_pdf(GUIDELINE_PAGES), "application/pdf")}).status_code == 401

    assert _upload(client, headers, b"bukan pdf sama sekali").status_code == 422
    assert _upload(client, headers, make_pdf([[], []])).status_code == 422

    parsed = _upload(client, headers)
    assert parsed.status_code == 200, parsed.text
    body = parsed.json()
    assert body["template"]["campus_name"] == "Universitas Contoh Nusantara"

    # klien menyunting nama dan menaruh margin ngawur: harus divalidasi ulang di server
    edited = body["template"]
    edited["page_setup"]["margins_cm"]["top"] = 99
    saved = client.post("/templates/custom", headers=headers, json={"template": edited, "name": "UCN Teknik", "source_filename": "pedoman.pdf", "report": body["report"]})
    assert saved.status_code == 201, saved.text
    tid = saved.json()["campus_id"]
    assert tid.startswith("custom-") and saved.json()["is_custom"] is True and saved.json()["campus_name"] == "UCN Teknik"

    listing = client.get("/templates", headers=headers).json()["templates"]
    ids = [t["campus_id"] for t in listing]
    assert tid in ids and "nasional-s1-kuantitatif" in ids
    detail = client.get(f"/templates/{tid}", headers=headers).json()
    assert detail["page_setup"]["margins_cm"]["top"] == 4.0, "margin 99 cm ditolak, kembali ke bawaan"
    assert detail["chapters"][0]["sub_sections"][0]["code"] == "1.1"

    # pemilik lain tidak melihat dan tidak bisa memakainya
    other = _ensure_user(client, {"full_name": "Lain", "email": "lain-tpl@test.id", "password": "rahasia456", "major_name": "SI", "campus_name": "X"})
    assert tid not in [t["campus_id"] for t in client.get("/templates", headers=other["headers"]).json()["templates"]]
    assert client.get(f"/templates/{tid}", headers=other["headers"]).status_code == 404
    use = client.post("/theses", headers=other["headers"], json={"topic": "Pengaruh Media Digital terhadap Motivasi", "template_id": tid})
    assert use.status_code == 422

    # dipakai oleh proyek: subbab dibangun dari bab hasil parsing, bukan templat nasional
    th = client.post("/theses", headers=headers, json={"topic": "Pengaruh Media Digital terhadap Motivasi", "template_id": tid})
    assert th.status_code == 201 and th.json()["campus_template_name"] == "UCN Teknik"
    thesis_id = th.json()["thesis_id"]
    client.post(f"/theses/{thesis_id}/sections/build", headers=headers)
    codes = [s["section_code"] for s in client.get(f"/theses/{thesis_id}/sections", headers=headers).json()]
    assert "1.1" in codes and "4.1" in codes and len(codes) == 14  # 4+3+3+2+2 dari LLM + daftar isi pedoman
    titles = {s["section_code"]: s["section_title"] for s in client.get(f"/theses/{thesis_id}/sections", headers=headers).json()}
    assert titles["1.2"] == "Rumusan Masalah" and titles["4.1"] == "Hasil Penelitian"
    assert titles["2.3"] == "Kerangka Pemikiran"

    assert client.post("/theses", headers=headers, json={"topic": "Pengaruh Media Digital terhadap Motivasi", "template_id": "tidak-ada"}).status_code == 422

    # tidak bisa dihapus selagi dipakai; bisa setelah proyeknya dihapus
    assert client.delete(f"/templates/{tid}", headers=headers).status_code == 409
    assert client.delete(f"/theses/{thesis_id}", headers=headers).status_code == 204
    assert client.delete(f"/templates/{tid}", headers=other["headers"]).status_code == 404
    assert client.delete(f"/templates/{tid}", headers=headers).status_code == 204
    assert client.get(f"/templates/{tid}", headers=headers).status_code == 404
