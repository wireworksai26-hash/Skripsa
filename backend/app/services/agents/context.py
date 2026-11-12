import re


def form_keywords(text: str) -> list[str]:
    return [
        w.lower()
        for w in re.findall(r"[\w]+", text)
        if len(w) > 3
    ]


def context_keywords(form: dict, title: str) -> str:
    return " ".join(
        part for part in [
            form.get("topic", ""),
            form.get("variable_x", ""),
            form.get("variable_y", ""),
            form.get("subject", ""),
            title,
        ]
        if part
    )


def _code_key(code: str) -> list[int]:
    return [int(p) if p.isdigit() else 0 for p in code.split(".")]


def sections_digest(sections, exclude_code: str, limit: int = 30, per_section: int = 0) -> str:
    """Daftar subbab lain yang sudah berisi (kode, judul, jumlah kata) tanpa teksnya.

    Audit 7 Nov 2026 (BUG-01): mengirim kalimat pembuka subbab lain membuat LLM menyalinnya mentah-mentah.
    """
    rows = sorted(
        (s for s in sections if s.section_code != exclude_code and len((s.content_markdown or "").split()) >= 50),
        key=lambda s: _code_key(s.section_code),
    )
    return "\n".join(f"- {s.section_code} {s.section_title} ({len((s.content_markdown or '').split())} kata)" for s in rows[:limit])


PARENT_INTRO_WORDS = 150


def _children(sections, code: str) -> list:
    depth = code.count(".") + 1
    kids = [s for s in sections if s.section_code.startswith(code + ".") and s.section_code.count(".") + 1 == depth + 1]
    return sorted(kids, key=lambda s: _code_key(s.section_code))


def section_plan(sections, section) -> dict:
    """Bahan tugas penulis untuk satu subbab, sadar hierarki: induk hanya menulis pengantar, anak tidak melebar ke saudaranya."""
    plan = {
        "chapter_code": section.chapter_code,
        "section_code": section.section_code,
        "section_title": section.section_title,
        "target_words": section.target_words,
    }
    code = section.section_code
    if code.count(".") >= 2:
        parent_code = code.rsplit(".", 1)[0]
        parent = next((s for s in sections if s.section_code == parent_code), None)
        siblings = [s for s in _children(sections, parent_code) if s.section_code != code]
        hint = f"Ini sub-subbab dari {parent_code} {parent.section_title if parent else ''}.".replace("  ", " ")
        if siblings:
            hint += " Sub-subbab saudara (dibahas terpisah, JANGAN dibahas di sini): " + "; ".join(f"{s.section_code} {s.section_title}" for s in siblings) + "."
        plan["outline_hint"] = hint + " Tulis HANYA cakupan judul sub-subbab ini."
    else:
        kids = _children(sections, code)
        if kids:
            plan["target_words"] = min(int(section.target_words or PARENT_INTRO_WORDS), PARENT_INTRO_WORDS)
            plan["outline_hint"] = (
                "Subbab ini punya sub-subbab: " + "; ".join(f"{s.section_code} {s.section_title}" for s in kids)
                + ". Tulis HANYA pengantar singkat (1-2 paragraf) yang memperkenalkan cakupan subbab ini; JANGAN membahas isi tiap sub-subbab."
            )
    return plan


def other_texts(sections, exclude_code: str) -> list[str]:
    """Isi subbab lain, hanya untuk pemeriksaan duplikasi (tidak dikirim ke LLM)."""
    return [s.content_markdown for s in sections if s.section_code != exclude_code and (s.content_markdown or "").strip()]


def results_data(thesis) -> str:
    """Tabel hasil (statistik, dsb.) yang disimpan pengguna, sebagai data nyata untuk Bab IV."""
    parts = []
    for t in getattr(thesis, "tables", []) or []:
        rows = [" | ".join(t.columns_json or [])] + [" | ".join(r) for r in (t.rows_json or [])]
        parts.append(f"{t.title}:\n" + "\n".join(rows) + (f"\nCatatan: {t.note}" if t.note else ""))
    from app.services.research_data import summary_for_writer

    own = summary_for_writer(getattr(thesis, "research_data", []) or [])
    if own:
        parts.append(own)
    return "\n\n".join(parts)


BRIEF_LABELS = {
    "topic": "Topik",
    "phenomenon": "Fenomena",
    "problem": "Research problem (masalah penelitian)",
    "theory": "Teori yang dipakai",
    "method": "Metode (desain, pengumpulan data, analisis)",
}
# Bagian kerangka yang relevan per bab; sisanya tidak dikirim agar prompt tetap fokus.
BRIEF_BY_CHAPTER = {
    "1": ("topic", "phenomenon", "problem"),
    "2": ("topic", "theory", "problem"),
    "3": ("method", "problem", "theory"),
    "4": ("problem", "method", "theory"),
    "5": ("problem", "theory", "method"),
}


def brief_for_chapter(thesis, chapter_code: str, section_title: str = "") -> str:
    """Kerangka dari peneliti untuk satu bab. Kosong bila peneliti tidak mengisinya."""
    brief = getattr(thesis, "brief_json", None) or {}
    keys = BRIEF_BY_CHAPTER.get(str(chapter_code).split(".")[0], tuple(BRIEF_LABELS))
    if section_title and str(chapter_code).split(".")[0] == "1":
        from app.services.agents.quality import section_kind

        if section_kind(section_title, "1") == "focus":  # Ruang lingkup wajib mengunci teori dan metode utama
            keys = tuple(dict.fromkeys((*keys, "theory", "method")))
    return "\n".join(f"- {BRIEF_LABELS[k]}: {brief[k]}" for k in keys if brief.get(k))


def mirror_rq(sections, section) -> tuple[str, int]:
    """Untuk subbab Tujuan: teks Rumusan Masalah yang sudah ada dan jumlah butirnya, agar tujuan mencerminkannya satu per satu."""
    from app.services.agents.quality import section_kind

    if section_kind(section.section_title, str(section.chapter_code)) != "objectives":
        return "", 0
    for s in sorted(sections, key=lambda x: _code_key(x.section_code)):
        if s.section_code != section.section_code and section_kind(s.section_title, str(s.chapter_code)) == "rq" and (s.content_markdown or "").strip():
            text = s.content_markdown.strip()
            return text, len(re.findall(r"(?m)^\s*\d{1,2}[.)]\s+\S", text))
    return "", 0


def mirror_fields(thesis, section) -> dict:
    text, count = mirror_rq(thesis.sections, section)
    return {"mirror_rq": text, "mirror_count": count} if text else {}
