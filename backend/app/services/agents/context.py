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
