from sqlalchemy.orm import Session

from app.models.models import Citation, Thesis
from app.services.llm import LLMUnavailable, extract_json, llm_chat_ex


def _note(kind: str, text: str) -> dict:
    return {"kind": kind, "text": text}


def word_count(text: str) -> int:
    return len([w for w in text.split() if any(ch.isalnum() for ch in w)])


EXAMINER_SYSTEM = (
    "Kamu adalah Dosen Penguji skripsi di perguruan tinggi Indonesia yang kritis namun adil. "
    "Susun simulasi pertanyaan sidang berdasarkan DRAF yang diberikan.\n"
    "Aturan:\n"
    "1. Buat 6-8 pertanyaan, urut dari yang umum ke yang paling tajam. Fokus bervariasi: Urgensi, Rumusan masalah, "
    "Metodologi, Data dan instrumen, Hasil dan pembahasan, Kebaruan, Rujukan, Keterbatasan.\n"
    "2. Setiap pertanyaan HARUS menyebut hal konkret dari draf (variabel, subjek, subbab, metode, atau rujukan yang "
    "benar-benar ada). Dilarang pertanyaan generik yang bisa diajukan ke skripsi mana pun.\n"
    "3. Saran jawaban 2-4 kalimat, bersandar pada isi draf dan rujukan yang diberikan. Dilarang mengarang data, hasil, "
    "angka, atau nama peneliti. Jika draf belum memuat dasar jawabannya, tulis apa yang perlu disiapkan mahasiswa.\n"
    "4. level: \"umum\" atau \"kritis\" (kritis = celah yang kemungkinan besar dipersoalkan penguji).\n"
    "5. Bahasa Indonesia baku.\n"
    'Tanggapi HANYA JSON: {"questions":[{"fokus":"...","level":"umum|kritis","pertanyaan":"...","saran_jawaban":"..."}]}'
)

EXAMINER_SYSTEM_EN = (
    "You are a thesis examiner at an international university: critical but fair. "
    "Simulate defense questions based on the DRAFT provided.\n"
    "Rules:\n"
    "1. Write 6-8 questions, ordered from general to sharpest. Vary the focus: urgency, research questions, "
    "methodology, data and instruments, results and discussion, novelty, references, limitations.\n"
    "2. Every question MUST mention something concrete from the draft (variables, subject, section, method, or a "
    "reference that actually exists). Generic questions that could be asked of any thesis are forbidden.\n"
    "3. Suggested answers: 2-4 sentences grounded in the draft and the provided references. Never invent data, "
    "results, numbers, or author names. If the draft lacks the basis for an answer, state what the student must prepare.\n"
    "4. level: \"umum\" or \"kritis\" (kritis = a gap the examiner will most likely challenge).\n"
    "5. Write everything in formal academic English.\n"
    'Respond with JSON ONLY: {"questions":[{"fokus":"...","level":"umum|kritis","pertanyaan":"...","saran_jawaban":"..."}]}'
)


def _section_digest(thesis: Thesis, limit: int = 8, per_section: int = 520) -> str:
    rows = sorted(
        (s for s in thesis.sections if word_count(s.content_markdown or "") >= 50),
        key=lambda s: [int(p) if p.isdigit() else 0 for p in s.section_code.split(".")],
    )
    parts = []
    for s in rows[:limit]:
        text = " ".join((s.content_markdown or "").split())
        parts.append(f"[{s.section_code} {s.section_title}] {text[:per_section]}{'…' if len(text) > per_section else ''}")
    return "\n".join(parts)


def _ref_digest(thesis: Thesis, db: Session, limit: int = 8) -> str:
    refs = (
        db.query(Citation)
        .filter(Citation.thesis_id == thesis.thesis_id, Citation.citation_id.in_(thesis.selected_ref_ids or []))
        .limit(limit)
        .all()
    )
    return "\n".join(f"- {(r.authors or ['Anonim'])[0]} ({r.publication_year}). {r.title}" for r in refs) or "(belum ada)"


def _clean_questions(data: dict) -> list[dict]:
    out = []
    for q in data.get("questions") or []:
        if not isinstance(q, dict):
            continue
        question = " ".join(str(q.get("pertanyaan", "")).split())
        answer = " ".join(str(q.get("saran_jawaban", "")).split())
        if len(question) < 20 or len(answer) < 20:
            continue
        out.append(
            {
                "fokus": " ".join(str(q.get("fokus", "Umum")).split())[:40] or "Umum",
                "kritis": str(q.get("level", "")).strip().lower() == "kritis",
                "pertanyaan": question,
                "saran_jawaban": answer,
            }
        )
    return out[:8]


async def examiner_review(thesis: Thesis, db: Session) -> dict:
    """Simulasi pertanyaan sidang oleh LLM, berdasarkan isi draf dan rujukan proyek ini.

    Bila tidak ada draf atau LLM gagal, hasilnya ditandai belum selesai dengan alasan yang jelas; tidak ada
    pertanyaan templat yang dikarang sebagai pengganti.
    """
    base = {"agent": "EXAMINER", "model_name": "Examiner Agent · Dosen Penguji", "done": False}
    digest = _section_digest(thesis)
    if not digest:
        return {**base, "notes": [_note("warn", "Belum ada draf subbab (minimal 50 kata) untuk diuji. Buat draf di Langkah 4 dulu.")]}

    user = (
        f"Judul: {thesis.title}\n"
        f"Metode: {thesis.research_method} · Jurusan: {thesis.domain_category} · Jenjang: {thesis.degree_level}\n"
        f"Variabel X: {thesis.variable_x or '-'} · Variabel Y: {thesis.variable_y or '-'} · Subjek/lokasi: {thesis.subject or '-'}\n"
        f"Visual di Bab IV: {len(thesis.charts_json or [])} grafik, {len(thesis.diagrams_json or [])} diagram, {len(thesis.tables)} tabel\n"
        f"Rujukan terpilih:\n{_ref_digest(thesis, db)}\n\n"
        f"DRAF (cuplikan per subbab):\n{digest}"
    )
    system = EXAMINER_SYSTEM_EN if (thesis.language or "id") == "en" else EXAMINER_SYSTEM
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]

    last = "tidak ada jawaban"
    for _ in range(2):
        try:
            raw, provider = await llm_chat_ex(messages, tier="heavy", temperature=0.5, max_tokens=3200)
        except LLMUnavailable as exc:
            return {**base, "notes": [_note("warn", f"Pertanyaan sidang tidak dapat dibuat: {exc}")]}
        try:
            questions = _clean_questions(extract_json(raw))
        except ValueError as exc:
            last = f"JSON tidak valid ({exc})"
            messages = messages + [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": "Jawabanmu bukan JSON valid. Balas HANYA dengan satu objek JSON sesuai format."},
            ]
            continue
        if len(questions) >= 3:
            notes = [
                _note(
                    "warn" if q["kritis"] else "info",
                    f'P{i} · {q["fokus"]}{" · kritis" if q["kritis"] else ""} — "{q["pertanyaan"]}"\nSaran jawaban: {q["saran_jawaban"]}',
                )
                for i, q in enumerate(questions, start=1)
            ]
            return {**base, "model_name": f"Examiner Agent · Dosen Penguji ({provider})", "notes": notes, "done": True}
        last = f"hanya {len(questions)} pertanyaan yang layak"
        messages = messages + [
            {"role": "assistant", "content": raw},
            {"role": "user", "content": "Pertanyaan kurang atau terlalu pendek. Buat 6-8 pertanyaan lengkap dengan saran jawaban."},
        ]
    return {**base, "notes": [_note("warn", f"Pertanyaan sidang tidak dapat dibuat: LLM menjawab tidak layak ({last}).")]}
