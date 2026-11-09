from app.services.llm import LLMUnavailable, extract_json, llm_chat_ex

SYSTEM = (
    "Kamu adalah Generator Judul otomatis untuk mahasiswa S1/S2 Indonesia. "
    "Tanggapi HANYA JSON valid tanpa pembuka: "
    '{"titles":[{"text":"...","rationale":"...","gap":"..."}]} — 5 item. '
    "Judul: bahasa Indonesia baku, spesifik, tanpa titik akhir, 8-16 kata."
)

SYSTEM_EN = (
    "You are an automatic thesis title generator for undergraduate and postgraduate students. "
    "Respond with valid JSON only, no preamble: "
    '{"titles":[{"text":"...","rationale":"...","gap":"..."}]} — 5 items. '
    "Each title MUST be written in formal academic English: specific, no trailing period, 8-16 words. "
    "Write rationale and gap in English as well."
)


async def generate_titles(form: dict) -> tuple[list[dict], str]:
    """Kembalikan (judul, nama_penyedia). Melempar LLMUnavailable; tidak ada judul karangan lokal."""
    language = "en" if form.get("language") == "en" else "id"
    user = (
        f"Topik: {form.get('topic', '')}\n"
        f"Variabel X: {form.get('variable_x', '')}\n"
        f"Variabel Y: {form.get('variable_y', '')}\n"
        f"Subjek/Lokasi: {form.get('subject', '')}\n"
        f"Metode: {form.get('method', '')}\n"
        f"Jurusan: {form.get('domain', '')}\n"
        f"Bahasa judul: {'English' if language == 'en' else 'Bahasa Indonesia'}"
    )
    system = SYSTEM_EN if language == "en" else SYSTEM
    last_error = "tidak ada jawaban"
    # LLM kadang memberi JSON rusak atau kurang dari 5 judul: dua percobaan.
    for _ in range(2):
        raw, provider = await llm_chat_ex(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            tier="fast",
            max_tokens=2200,
        )
        try:
            data = extract_json(raw)
        except ValueError as exc:
            last_error = f"JSON tidak valid ({exc})"
            continue
        titles = [
            {
                "text": str(t.get("text", "")).strip(),
                "rationale": str(t.get("rationale", "")).strip(),
                "gap": str(t.get("gap", "")).strip(),
            }
            for t in (data.get("titles") or [])[:5]
            if isinstance(t, dict) and str(t.get("text", "")).strip()
        ]
        if len(titles) >= 3:
            return titles, provider
        last_error = f"hanya {len(titles)} judul"
    raise LLMUnavailable(f"LLM tidak menghasilkan daftar judul yang layak: {last_error}")
