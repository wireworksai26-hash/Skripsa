import re

CAMPUS_TEMPLATES: dict[str, dict] = {}

_CHAPTER_TITLES = {
    "1": "PENDAHULUAN",
    "2": "KAJIAN PUSTAKA / LANDASAN TEORI",
    "3": "METODE PENELITIAN",
    "4": "HASIL DAN PEMBAHASAN",
    "5": "SIMPULAN DAN SARAN",
}

_CHAPTER_TITLES_EN = {
    "PENDAHULUAN": "INTRODUCTION",
    "KAJIAN PUSTAKA / LANDASAN TEORI": "LITERATURE REVIEW / THEORETICAL FRAMEWORK",
    "METODE PENELITIAN": "RESEARCH METHOD",
    "HASIL DAN PEMBAHASAN": "RESULTS AND DISCUSSION",
    "SIMPULAN DAN SARAN": "CONCLUSION AND SUGGESTIONS",
}

# Judul subbab bawaan dalam bahasa Inggris. Templat kustom yang memakai judul lain dibiarkan apa adanya.
_SECTION_TITLES_EN = {
    "Latar Belakang Masalah": "Background of the Study",
    "Latar Belakang": "Background",
    "Rumusan Masalah": "Statement of the Problem",
    "Rumusan Masalah dan Tujuan": "Research Questions and Objectives",
    "Rumusan dan Tujuan Penelitian": "Research Questions and Objectives",
    "Identifikasi Masalah": "Problem Identification",
    "Tujuan Penelitian": "Research Objectives",
    "Manfaat Penelitian": "Significance of the Study",
    "Manfaat dan Signifikansi Penelitian": "Significance of the Study",
    "Batasan Masalah": "Scope and Limitations",
    "Tinjauan Pustaka": "Literature Review",
    "Landasan Teori": "Theoretical Framework",
    "Kajian Penelitian Relevan": "Review of Relevant Studies",
    "Kajian Literatur Krusial": "Critical Literature Review",
    "Kerangka Pemikiran": "Conceptual Framework",
    "Kerangka Konseptual": "Conceptual Framework",
    "Kerangka Konseptual Metodologi": "Methodological Framework",
    "State of the Art dan Research Gap": "State of the Art and Research Gap",
    "Hipotesis Penelitian": "Research Hypotheses",
    "Jenis dan Desain Penelitian": "Research Design",
    "Pendekatan dan Jenis Penelitian": "Research Approach and Design",
    "Populasi dan Sampel": "Population and Sample",
    "Subjek dan Lokasi Penelitian": "Research Subjects and Site",
    "Teknik Pengumpulan Data": "Data Collection Techniques",
    "Instrumen Penelitian": "Research Instruments",
    "Instrumen dan Teknik Validasi": "Instruments and Validation Techniques",
    "Teknik Analisis Data": "Data Analysis Techniques",
    "Analisis Data (Miles & Huberman)": "Data Analysis (Miles & Huberman)",
    "Keabsahan Data (Trustworthiness)": "Trustworthiness of the Data",
    "Gambaran Umum Objek Penelitian": "Overview of the Research Object",
    "Hasil Pengujian": "Results of Hypothesis Testing",
    "Analisis dan Interpretasi Hasil": "Analysis and Interpretation of Results",
    "Deskripsi Data": "Description of the Data",
    "Temuan Penelitian": "Research Findings",
    "Pembahasan": "Discussion",
    "Pembahasan Temuan": "Discussion of Findings",
    "Diskusi Kritis": "Critical Discussion",
    "Kesimpulan": "Conclusion",
    "Simpulan dan Implikasi": "Conclusions and Implications",
    "Saran": "Suggestions",
    "Fokus Penelitian": "Focus of the Study",
    "Definisi Operasional": "Operational Definitions",
    "Pendekatan dan Desain Penelitian": "Research Approach and Design",
    "Data dan Sumber Data": "Data and Sources of Data",
    "Keabsahan Data": "Trustworthiness of the Data",
    "Simpulan": "Conclusion",
}

_SECTION_TITLES_EN.update(
    {
        "Ruang Lingkup Penelitian": "Scope of the Study",
        "Konsep Utama Penelitian": "Main Concepts of the Study",
        "Konsep Pendukung": "Supporting Concepts",
        "Penelitian yang Relevan ": "Relevant Studies",
        "Analisis Data": "Data Analysis",
        "Hasil Analisis Aspek Utama": "Analysis of the Main Aspects",
        "Hasil Analisis Aspek Pendukung": "Analysis of the Supporting Aspects",
        "Tujuan Pengembangan": "Development Objectives",
        "Manfaat Pengembangan": "Significance of the Development",
        "Asumsi dan Keterbatasan Pengembangan": "Assumptions and Limitations of the Development",
        "Jenis Penelitian dan Model Pengembangan": "Research Type and Development Model",
        "Prosedur Pengembangan": "Development Procedure",
        "Hasil Pengembangan Produk": "Product Development Results",
        "Hasil Validasi dan Uji Coba": "Validation and Trial Results",
        "Deskripsi Kondisi Awal": "Description of the Initial Condition",
        "Pelaksanaan dan Hasil Siklus I": "Implementation and Results of Cycle I",
        "Pelaksanaan dan Hasil Siklus II": "Implementation and Results of Cycle II",
        "Teknik dan Instrumen Pengumpulan Data": "Data Collection Techniques and Instruments",
        "Sumber Data": "Sources of Data",
        "Hasil Kajian": "Review Findings",
        "Pendekatan dan Jenis Penelitian": "Research Approach and Design",
        "Manfaat Hasil Penelitian": "Significance of the Study",
        "Asumsi Penelitian": "Research Assumptions",
        "Asumsi dan Keterbatasan Penelitian": "Assumptions and Limitations",
        "Pembatasan Masalah": "Scope and Limitations",
        "Ruang Lingkup dan Keterbatasan Penelitian": "Scope and Limitations of the Study",
        "Hipotesis": "Research Hypotheses",
        "Hipotesis Tindakan": "Action Hypotheses",
        "Kerangka Teoretis": "Theoretical Framework",
        "Kajian Teoretis": "Theoretical Review",
        "Kerangka Berpikir": "Conceptual Framework",
        "Hasil Penelitian yang Relevan": "Review of Relevant Studies",
        "Penelitian yang Relevan": "Review of Relevant Studies",
        "Pendekatan Penelitian": "Research Approach",
        "Jenis Penelitian": "Type of Research",
        "Lokasi Penelitian": "Research Location",
        "Lokasi dan Waktu Penelitian": "Research Location and Time",
        "Populasi dan Sampel Penelitian": "Population and Sample",
        "Variabel Penelitian": "Research Variables",
        "Definisi Istilah": "Definition of Terms",
        "Data dan Teknik Pengumpulan Data": "Data and Data Collection Techniques",
        "Data dan Sumber Data Penelitian": "Data and Sources of Data",
        "Instrumen Pengumpulan Data": "Data Collection Instruments",
        "Uji Keabsahan Data": "Trustworthiness of the Data",
        "Latar Penelitian": "Research Setting",
        "Subjek Penelitian": "Research Subjects",
        "Prosedur Penelitian": "Research Procedures",
        "Desain Penelitian": "Research Design",
        "Hasil Penelitian": "Research Results",
        "Hasil dan Pembahasan": "Results and Discussion",
        "Spesifikasi Produk yang Diharapkan": "Expected Product Specifications",
        "Desain Uji Coba": "Trial Design",
        "Subjek Uji Coba": "Trial Subjects",
        "Jenis Data": "Types of Data",
        "Simpulan dan Saran": "Conclusions and Suggestions",
        "Kesimpulan dan Saran": "Conclusions and Suggestions",
        "Implikasi": "Implications",
        "Keterbatasan Penelitian": "Limitations of the Study",
        "Rumusan Masalah dan Tujuan Penelitian": "Research Questions and Objectives",
        "Latar Belakang dan Masalah": "Background and Problem",
    }
)

_CHAPTER_TITLES_EN.update(
    {
        "ANALISIS DATA, TEMUAN, DAN PEMBAHASAN": "DATA ANALYSIS, FINDINGS, AND DISCUSSION",
        "PENDAHULUAN": "INTRODUCTION",
        "KAJIAN PUSTAKA": "LITERATURE REVIEW",
        "KERANGKA TEORETIS": "THEORETICAL FRAMEWORK",
        "METODE PENELITIAN": "RESEARCH METHOD",
        "METODOLOGI PENELITIAN": "RESEARCH METHODOLOGY",
        "HASIL PENELITIAN DAN PEMBAHASAN": "RESULTS AND DISCUSSION",
        "HASIL PENELITIAN": "RESEARCH RESULTS",
        "PEMBAHASAN": "DISCUSSION",
        "SIMPULAN": "CONCLUSION",
        "KESIMPULAN": "CONCLUSION",
        "KESIMPULAN DAN SARAN": "CONCLUSION AND SUGGESTIONS",
        "SIMPULAN, IMPLIKASI, DAN SARAN": "CONCLUSIONS, IMPLICATIONS, AND SUGGESTIONS",
    }
)


def _key(title: str) -> str:
    """Kunci pencarian: huruf kecil, spasi rapi, tanpa keterangan kurung di akhir (mis. "(jika ada)")."""
    t = re.sub(r"\s*\([^)]*\)\s*$", "", title or "")
    return re.sub(r"\s+", " ", t).strip().lower()


_SECTION_EN_BY_KEY = {_key(k): v for k, v in _SECTION_TITLES_EN.items()}
_CHAPTER_EN_BY_KEY = {_key(k): v for k, v in _CHAPTER_TITLES_EN.items()}


def _en_section(title: str) -> str:
    out = _SECTION_EN_BY_KEY.get(_key(title))
    if out is None:
        return title
    if re.search(r"\(jika ada\)\s*$", title, flags=re.I):
        out += " (if any)"
    return out


LANGUAGES = ("id", "en")


def localize_template(template: dict, language: str) -> dict:
    """Terjemahkan judul bab/subbab bawaan saat naskah ditulis dalam bahasa Inggris."""
    if language != "en":
        return template
    return {
        **template,
        "chapters": [
            {
                **ch,
                "chapter_title": _CHAPTER_EN_BY_KEY.get(_key(ch["chapter_title"])) or ch.get("chapter_title_en") or ch["chapter_title"],
                "sub_sections": [
                    {**s, "title": (_en_section(s["title"]) if _en_section(s["title"]) != s["title"] else s.get("title_en") or s["title"])}
                    for s in ch["sub_sections"]
                ],
            }
            for ch in template["chapters"]
        ],
    }

_COVER = {
    "logo_cm": 4,
    "title_pt": 14,
    "body_pt": 12,
    "caps": True,
    "title_page": True,
    "approval": True,
    "originality": True,
}

_PAGE_SETUP = {
    "paper_size": "A4",
    "margins_cm": {"top": 4, "left": 4, "bottom": 3, "right": 3},
    "font_family": "Times New Roman",
    "font_size_pt": 12,
    "line_spacing": 1.5,
    "paragraph_indent_cm": 1.0,
}


def _t(
    template_id: str,
    name: str,
    degree: str,
    method: str,
    sub: dict[str, list[dict]],
    titles: dict[str, str] | None = None,
) -> dict:
    titles = titles or {}
    return {
        "campus_id": template_id,
        "campus_name": name,
        "faculty": "Umum",
        "degree_level": degree,
        "page_setup": _PAGE_SETUP,
        "cover": _COVER,
        "citation_style": "APA_7TH",
        "research_method": method,
        "chapters": [
            {
                "chapter_number": num,
                "chapter_title": titles.get(num, _CHAPTER_TITLES[num]),
                "sub_sections": items,
            }
            for num, items in sub.items()
        ],
    }


CAMPUS_TEMPLATES["nasional-s1-kuantitatif"] = _t(
    "nasional-s1-kuantitatif",
    "Standar Nasional S1 — Kuantitatif",
    "S1",
    "KUANTITATIF",
    {
        "1": [
            {"code": "1.1", "title": "Latar Belakang Masalah", "target_words": 1200},
            {"code": "1.2", "title": "Rumusan Masalah", "target_words": 300},
            {"code": "1.3", "title": "Tujuan Penelitian", "target_words": 250},
            {"code": "1.4", "title": "Manfaat Penelitian", "target_words": 300},
            {"code": "1.5", "title": "Batasan Masalah", "target_words": 200},
        ],
        "2": [
            {"code": "2.1", "title": "Tinjauan Pustaka", "target_words": 1200},
            {"code": "2.2", "title": "Kerangka Pemikiran", "target_words": 600},
            {"code": "2.3", "title": "Hipotesis Penelitian", "target_words": 400},
        ],
        "3": [
            {"code": "3.1", "title": "Jenis dan Desain Penelitian", "target_words": 500},
            {"code": "3.2", "title": "Populasi dan Sampel", "target_words": 400},
            {"code": "3.3", "title": "Teknik Pengumpulan Data", "target_words": 400},
            {"code": "3.4", "title": "Instrumen Penelitian", "target_words": 400},
            {"code": "3.5", "title": "Teknik Analisis Data", "target_words": 600},
        ],
        "4": [
            {"code": "4.1", "title": "Gambaran Umum Objek Penelitian", "target_words": 500},
            {"code": "4.2", "title": "Hasil Pengujian", "target_words": 700},
            {"code": "4.3", "title": "Pembahasan", "target_words": 1200},
        ],
        "5": [
            {"code": "5.1", "title": "Kesimpulan", "target_words": 600},
            {"code": "5.2", "title": "Saran", "target_words": 300},
        ],
    },
)

CAMPUS_TEMPLATES["nasional-s1-kualitatif"] = _t(
    "nasional-s1-kualitatif",
    "Standar Nasional S1 — Kualitatif",
    "S1",
    "KUALITATIF",
    {
        # Struktur kualitatif umum (audit BUG-06): fokus menggantikan identifikasi/batasan; rumusan & tujuan terpisah.
        "1": [
            {"code": "1.1", "title": "Latar Belakang Masalah", "target_words": 1200},
            {"code": "1.2", "title": "Fokus Penelitian", "target_words": 250},
            {"code": "1.3", "title": "Rumusan Masalah", "target_words": 200},
            {"code": "1.4", "title": "Tujuan Penelitian", "target_words": 200},
            {"code": "1.5", "title": "Manfaat Penelitian", "target_words": 300},
        ],
        "2": [
            {"code": "2.1", "title": "Landasan Teori", "target_words": 1500},
            {"code": "2.2", "title": "Definisi Operasional", "target_words": 300},
            {"code": "2.3", "title": "Kajian Penelitian Relevan", "target_words": 600},
            {"code": "2.4", "title": "Kerangka Konseptual", "target_words": 400},
        ],
        "3": [
            {"code": "3.1", "title": "Pendekatan dan Desain Penelitian", "target_words": 450},
            {"code": "3.2", "title": "Data dan Sumber Data", "target_words": 400},
            {"code": "3.3", "title": "Instrumen Penelitian", "target_words": 400},
            {"code": "3.4", "title": "Teknik Pengumpulan Data", "target_words": 450},
            {"code": "3.5", "title": "Keabsahan Data", "target_words": 350},
            {"code": "3.6", "title": "Teknik Analisis Data", "target_words": 500},
        ],
        "4": [
            {"code": "4.1", "title": "Temuan Penelitian", "target_words": 1500},
            {"code": "4.2", "title": "Pembahasan", "target_words": 1200},
        ],
        "5": [
            {"code": "5.1", "title": "Simpulan", "target_words": 500},
            {"code": "5.2", "title": "Saran", "target_words": 300},
        ],
    },
)

CAMPUS_TEMPLATES["nasional-s2-umum"] = _t(
    "nasional-s2-umum",
    "Standar Nasional S2 — Format Makalah",
    "S2",
    "KUANTITATIF",
    {
        "1": [
            {"code": "1.1", "title": "Latar Belakang", "target_words": 1200},
            {"code": "1.2", "title": "Rumusan Masalah dan Tujuan", "target_words": 400},
        ],
        "2": [
            {"code": "2.1", "title": "Kajian Literatur Krusial", "target_words": 1200},
            {"code": "2.2", "title": "State of the Art dan Research Gap", "target_words": 600},
        ],
        "3": [
            {"code": "3.1", "title": "Kerangka Konseptual Metodologi", "target_words": 600},
            {"code": "3.2", "title": "Instrumen dan Teknik Validasi", "target_words": 600},
        ],
        "4": [
            {"code": "4.1", "title": "Analisis dan Interpretasi Hasil", "target_words": 1200},
            {"code": "4.2", "title": "Diskusi Kritis", "target_words": 1000},
        ],
        "5": [{"code": "5.1", "title": "Simpulan dan Implikasi", "target_words": 700}],
    },
)


CAMPUS_TEMPLATES["nasional-s1-analisis-dokumen"] = _t(
    "nasional-s1-analisis-dokumen",
    "Analisis Dokumen / Buku Teks (Kualitatif)",
    "S1",
    "KUALITATIF",
    {
        "1": [
            {"code": "1.1", "title": "Latar Belakang Masalah", "target_words": 1200},
            {"code": "1.2", "title": "Rumusan Masalah", "target_words": 250},
            {"code": "1.3", "title": "Tujuan Penelitian", "target_words": 200},
            {"code": "1.4", "title": "Ruang Lingkup Penelitian", "target_words": 200},
            {"code": "1.5", "title": "Manfaat Penelitian", "target_words": 300},
        ],
        "2": [
            {"code": "2.1", "title": "Kerangka Teoretis", "target_words": 300},
            {"code": "2.1.1", "title": "Konsep Utama Penelitian", "target_words": 800},
            {"code": "2.1.2", "title": "Konsep Pendukung", "target_words": 800},
            {"code": "2.2", "title": "Penelitian yang Relevan", "target_words": 600},
            {"code": "2.3", "title": "Kerangka Konseptual", "target_words": 400},
        ],
        "3": [
            {"code": "3.1", "title": "Desain Penelitian", "target_words": 450},
            {"code": "3.2", "title": "Data dan Sumber Data", "target_words": 400},
            {"code": "3.3", "title": "Teknik Pengumpulan Data", "target_words": 400},
            {"code": "3.4", "title": "Teknik Analisis Data", "target_words": 500},
        ],
        "4": [
            {"code": "4.1", "title": "Analisis Data", "target_words": 400},
            {"code": "4.1.1", "title": "Hasil Analisis Aspek Utama", "target_words": 900},
            {"code": "4.1.2", "title": "Hasil Analisis Aspek Pendukung", "target_words": 900},
            {"code": "4.2", "title": "Temuan Penelitian", "target_words": 700},
            {"code": "4.3", "title": "Pembahasan", "target_words": 1000},
        ],
        "5": [
            {"code": "5.1", "title": "Simpulan", "target_words": 500},
            {"code": "5.2", "title": "Saran", "target_words": 300},
        ],
    },
    titles={'4': 'ANALISIS DATA, TEMUAN, DAN PEMBAHASAN'},
)

CAMPUS_TEMPLATES["nasional-s1-rnd"] = _t(
    "nasional-s1-rnd",
    "Penelitian dan Pengembangan (R&D)",
    "S1",
    "RND",
    {
        "1": [
            {"code": "1.1", "title": "Latar Belakang Masalah", "target_words": 1200},
            {"code": "1.2", "title": "Rumusan Masalah", "target_words": 250},
            {"code": "1.3", "title": "Tujuan Pengembangan", "target_words": 250},
            {"code": "1.4", "title": "Spesifikasi Produk yang Diharapkan", "target_words": 350},
            {"code": "1.5", "title": "Manfaat Pengembangan", "target_words": 300},
            {"code": "1.6", "title": "Asumsi dan Keterbatasan Pengembangan", "target_words": 250},
        ],
        "2": [
            {"code": "2.1", "title": "Kajian Teoretis", "target_words": 1200},
            {"code": "2.2", "title": "Hasil Penelitian yang Relevan", "target_words": 600},
            {"code": "2.3", "title": "Kerangka Konseptual", "target_words": 400},
        ],
        "3": [
            {"code": "3.1", "title": "Jenis Penelitian dan Model Pengembangan", "target_words": 450},
            {"code": "3.2", "title": "Prosedur Pengembangan", "target_words": 600},
            {"code": "3.3", "title": "Desain Uji Coba", "target_words": 350},
            {"code": "3.4", "title": "Subjek Uji Coba", "target_words": 250},
            {"code": "3.5", "title": "Jenis Data", "target_words": 250},
            {"code": "3.6", "title": "Definisi Operasional", "target_words": 250},
            {"code": "3.7", "title": "Instrumen Pengumpulan Data", "target_words": 400},
            {"code": "3.8", "title": "Teknik Analisis Data", "target_words": 450},
        ],
        "4": [
            {"code": "4.1", "title": "Hasil Pengembangan Produk", "target_words": 900},
            {"code": "4.2", "title": "Hasil Validasi dan Uji Coba", "target_words": 900},
            {"code": "4.3", "title": "Pembahasan", "target_words": 1000},
        ],
        "5": [
            {"code": "5.1", "title": "Simpulan", "target_words": 500},
            {"code": "5.2", "title": "Saran", "target_words": 300},
        ],
    },
)

CAMPUS_TEMPLATES["nasional-s1-ptk"] = _t(
    "nasional-s1-ptk",
    "Penelitian Tindakan Kelas (PTK)",
    "S1",
    "KUALITATIF",
    {
        "1": [
            {"code": "1.1", "title": "Latar Belakang Masalah", "target_words": 1200},
            {"code": "1.2", "title": "Rumusan Masalah", "target_words": 250},
            {"code": "1.3", "title": "Tujuan Penelitian", "target_words": 200},
            {"code": "1.4", "title": "Hipotesis Tindakan (jika diperlukan)", "target_words": 200},
            {"code": "1.5", "title": "Manfaat Penelitian", "target_words": 300},
            {"code": "1.6", "title": "Ruang Lingkup dan Keterbatasan Penelitian", "target_words": 250},
            {"code": "1.7", "title": "Definisi Operasional", "target_words": 250},
        ],
        "2": [
            {"code": "2.1", "title": "Kajian Teoretis", "target_words": 1200},
            {"code": "2.2", "title": "Hasil Penelitian yang Relevan", "target_words": 600},
            {"code": "2.3", "title": "Kerangka Konseptual", "target_words": 400},
        ],
        "3": [
            {"code": "3.1", "title": "Jenis Penelitian", "target_words": 350},
            {"code": "3.2", "title": "Latar Penelitian", "target_words": 250},
            {"code": "3.3", "title": "Subjek Penelitian", "target_words": 250},
            {"code": "3.4", "title": "Data dan Sumber Data", "target_words": 300},
            {"code": "3.5", "title": "Prosedur Penelitian", "target_words": 700},
            {"code": "3.6", "title": "Teknik Pengumpulan Data", "target_words": 400},
            {"code": "3.7", "title": "Teknik Analisis Data", "target_words": 450},
        ],
        "4": [
            {"code": "4.1", "title": "Deskripsi Kondisi Awal", "target_words": 500},
            {"code": "4.2", "title": "Pelaksanaan dan Hasil Siklus I", "target_words": 900},
            {"code": "4.3", "title": "Pelaksanaan dan Hasil Siklus II", "target_words": 900},
            {"code": "4.4", "title": "Pembahasan", "target_words": 1000},
        ],
        "5": [
            {"code": "5.1", "title": "Simpulan", "target_words": 500},
            {"code": "5.2", "title": "Saran", "target_words": 300},
        ],
    },
)

CAMPUS_TEMPLATES["nasional-s1-pustaka"] = _t(
    "nasional-s1-pustaka",
    "Penelitian Pustaka (Studi Literatur)",
    "S1",
    "KUALITATIF",
    {
        "1": [
            {"code": "1.1", "title": "Latar Belakang Masalah", "target_words": 1200},
            {"code": "1.2", "title": "Rumusan Masalah", "target_words": 250},
            {"code": "1.3", "title": "Tujuan Penelitian", "target_words": 200},
            {"code": "1.4", "title": "Manfaat Penelitian", "target_words": 300},
            {"code": "1.5", "title": "Definisi Istilah", "target_words": 250},
        ],
        "2": [
            {"code": "2.1", "title": "Kajian Teoretis", "target_words": 1500},
            {"code": "2.2", "title": "Kerangka Berpikir", "target_words": 450},
        ],
        "3": [
            {"code": "3.1", "title": "Pendekatan dan Jenis Penelitian", "target_words": 400},
            {"code": "3.2", "title": "Sumber Data", "target_words": 350},
            {"code": "3.3", "title": "Teknik dan Instrumen Pengumpulan Data", "target_words": 400},
            {"code": "3.4", "title": "Teknik Analisis Data", "target_words": 450},
        ],
        "4": [
            {"code": "4.1", "title": "Hasil Kajian", "target_words": 1300},
            {"code": "4.2", "title": "Pembahasan", "target_words": 1100},
        ],
        "5": [
            {"code": "5.1", "title": "Simpulan", "target_words": 500},
            {"code": "5.2", "title": "Saran", "target_words": 300},
        ],
    },
)


def get_template(template_id: str) -> dict:
    """Hanya templat bawaan; untuk templat kustom milik pengguna pakai resolve_template."""
    return CAMPUS_TEMPLATES.get(template_id, CAMPUS_TEMPLATES["nasional-s1-kuantitatif"])


def resolve_template(db, template_id: str) -> dict:
    """Templat bawaan, atau templat kustom (hasil parsing PDF) dari basis data. Id tak dikenal -> bawaan S1."""
    if template_id in CAMPUS_TEMPLATES:
        return CAMPUS_TEMPLATES[template_id]
    if template_id.startswith("custom-"):
        from app.models.models import CustomTemplate

        row = db.get(CustomTemplate, template_id)
        if row:
            return {**row.spec_json, "cover": {**_COVER, **(row.spec_json.get("cover") or {})}, "campus_id": row.template_id, "is_custom": True}
    return CAMPUS_TEMPLATES["nasional-s1-kuantitatif"]


def template_exists(db, template_id: str, user_id: str) -> bool:
    if template_id in CAMPUS_TEMPLATES:
        return True
    if template_id.startswith("custom-"):
        from app.models.models import CustomTemplate

        row = db.get(CustomTemplate, template_id)
        return bool(row and row.user_id == user_id)
    return False


def suggest_template_id(method: str, degree_level: str) -> str:
    if degree_level == "S2":
        return "nasional-s2-umum"
    if method == "KUALITATIF":
        return "nasional-s1-kualitatif"
    if method == "RND":
        return "nasional-s1-rnd"
    return "nasional-s1-kuantitatif"


def total_target_words(template: dict) -> int:
    return sum(
        s["target_words"]
        for ch in template["chapters"]
        for s in ch["sub_sections"]
    )
