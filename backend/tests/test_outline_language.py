import asyncio
import json

from app.services import guideline_parser as gp
from app.services.templates import localize_template

TOC = """DAFTAR ISI
2. Bagian Isi .......... 8
a. Bab 1 Pendahuluan .......... 8
1) Latar Belakang .......... 8
2) Rumusan Masalah .......... 8
3) Tujuan Penelitian .......... 9
4) Manfaat Hasil Penelitian .......... 9
5) Asumsi Penelitian .......... 9
b. Bab 2 Kajian Pustaka .......... 9
c. Bab 3 Metode Penelitian .......... 9
1) Pendekatan Penelitian .......... 10
2) Populasi dan Sampel .......... 10
d. Bab 4 Hasil Penelitian dan Pembahasan .......... 12
"""
EXAMPLE = """BAB I PENDAHULUAN
A. Latar Belakang
B. Rumusan Masalah
C. Tujuan Penelitian
D. Manfaat Hasil Penelitian
E. Asumsi Penelitian
F. Identifikasi Masalah
G. Pembatasan Masalah
H. Hipotesis Penelitian (jika ada)
BAB III METODE PENELITIAN
A. Pendekatan Penelitian
B. Populasi dan Sampel
C. Latar Penelitian
D. Prosedur Penelitian
"""


def test_repeated_systematics_in_guideline_do_not_pile_up():
    outline = gp.extract_outline([TOC, EXAMPLE])
    by = {c["chapter_number"]: [s["title"] for s in c["sub_sections"]] for c in outline}
    assert by[1] == ["Latar Belakang", "Rumusan Masalah", "Tujuan Penelitian", "Manfaat Hasil Penelitian", "Asumsi Penelitian"]
    assert by[3] == ["Pendekatan Penelitian", "Populasi dan Sampel"], "contoh desain lain tidak boleh menambah subbab"


def test_english_titles_cover_guideline_vocabulary():
    t = {
        "chapters": [
            {"chapter_number": "1", "chapter_title": "Pendahuluan", "sub_sections": [{"code": "1.1", "title": "Manfaat Hasil Penelitian"}, {"code": "1.2", "title": "Asumsi Penelitian"}, {"code": "1.3", "title": "Hipotesis Penelitian (jika ada)"}]},
            {"chapter_number": "4", "chapter_title": "Hasil Penelitian dan Pembahasan", "sub_sections": []},
        ]
    }
    en = localize_template(t, "en")["chapters"]
    assert en[0]["chapter_title"] == "INTRODUCTION" and en[1]["chapter_title"] == "RESULTS AND DISCUSSION"
    assert [s["title"] for s in en[0]["sub_sections"]] == ["Significance of the Study", "Research Assumptions", "Research Hypotheses (if any)"]
    assert localize_template(t, "id")["chapters"][0]["chapter_title"] == "Pendahuluan"


def test_unknown_titles_get_llm_translation_or_stay_untouched(monkeypatch):
    template = {"chapters": [{"chapter_number": "1", "chapter_title": "Pendahuluan", "sub_sections": [{"code": "1.1", "title": "Topik Khusus Kampus"}]}]}

    async def fake(messages, **kw):
        return json.dumps({"translations": {"Topik Khusus Kampus": "Campus-Specific Topic"}}), "fake"

    monkeypatch.setattr(gp, "llm_chat_ex", fake)
    assert asyncio.run(gp.translate_titles(template)) == []
    assert template["chapters"][0]["sub_sections"][0]["title_en"] == "Campus-Specific Topic"
    assert localize_template(template, "en")["chapters"][0]["sub_sections"][0]["title"] == "Campus-Specific Topic"

    async def down(messages, **kw):
        raise RuntimeError("tidak ada penyedia")

    monkeypatch.setattr(gp, "llm_chat_ex", down)
    t2 = {"chapters": [{"chapter_number": "1", "chapter_title": "Pendahuluan", "sub_sections": [{"code": "1.1", "title": "Topik Lain"}]}]}
    warn = asyncio.run(gp.translate_titles(t2))
    assert warn and "title_en" not in t2["chapters"][0]["sub_sections"][0], "gagal: tidak ada terjemahan karangan"
    assert localize_template(t2, "en")["chapters"][0]["sub_sections"][0]["title"] == "Topik Lain"
