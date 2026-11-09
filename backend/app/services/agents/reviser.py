"""Perbaikan subbab berdasarkan umpan balik review (Advisor, Examiner, Guardrail) atau instruksi pengguna.

Perbaikan tidak boleh mengarang: klaim baru hanya boleh bersandar pada kalimat bukti rujukan terpilih, penanda sitasi
berasal dari metadata rujukan, dan jawaban yang kehilangan banyak isi ditolak (draf yang dipangkas bukan perbaikan).
"""

from app.services.agents.context import form_keywords
from app.services.agents.quality import dedupe_paragraphs, polish
from app.services.agents.writer import _collect_citations, valid_word_count
from app.services.citation import in_text_marker
from app.services.llm import LLMUnavailable, extract_json, llm_chat_ex

MIN_KEEP_RATIO = 0.6  # hasil perbaikan minimal 60% panjang naskah asli
DELIM = "###PERUBAHAN###"

SYSTEM = (
    "Kamu adalah Academic Writer Agent yang MEMPERBAIKI satu subbab skripsi berdasarkan umpan balik dosen.\n"
    "Aturan wajib:\n"
    "1. Tulis dalam bahasa yang sama dengan naskah asli, gaya akademik baku. Pertahankan struktur paragraf dan isi yang sudah baik.\n"
    "2. Terapkan HANYA umpan balik yang relevan dengan subbab ini; abaikan yang membahas subbab lain. Untuk pertanyaan penguji, "
    "tambahkan atau perjelas penjelasan di naskah sehingga pertanyaan itu terjawab, bukan menulis jawaban sebagai dialog.\n"
    "3. Klaim faktual baru HARUS bersandar pada kalimat BUKTI yang diberikan, dan diakhiri PENANDA sitasi yang diberikan "
    "PERSIS apa adanya. Ganti penanda sitasi lama di naskah dengan penanda dari daftar. Dilarang mengarang data, angka, "
    "nama peneliti, atau hasil penelitian yang tidak ada di naskah atau BUKTI. Bila umpan balik menuntut data yang tidak ada, "
    "tulis kalimat yang menyatakan keterbatasan itu, jangan mengarangnya.\n"
    "4. Jangan memperpendek naskah; hasil harus setara atau lebih panjang dari aslinya.\n"
    "5. FORMAT JAWABAN (teks biasa, BUKAN JSON): tulis naskah subbab lengkap hasil perbaikan, lalu satu baris persis "
    f"{DELIM}, lalu 2-6 butir singkat (satu per baris, diawali tanda -) yang meringkas perubahan.\n"
    "Tulis naskah apa adanya tanpa judul subbab, tanpa pembuka, tanpa penutup."
)


def _blocks(refs: list[dict], markers: dict[str, str]) -> str:
    out = []
    for i, r in enumerate(refs):
        head = (
            f"  {i + 1}. reference_id={r['citation_id']}; penulis={', '.join((r.get('authors') or [])[:3])}; "
            f"tahun={r.get('publication_year', 0)}; judul={r.get('title')}; penanda=\"{markers[r['citation_id']]}\""
        )
        evidence = r.get("evidence") or []
        out.append(head + ("".join(f'\n     BUKTI: "{e}"' for e in evidence) if evidence else "\n     BUKTI: (abstrak tidak tersedia)"))
    return "\n".join(out)


def parse_response(raw: str) -> tuple[str, list[str]]:
    """Pisahkan naskah dan ringkasan perubahan. JSON {content, changes} tetap diterima bila LLM memakainya."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip().startswith("```") else lines[1:]).strip()
    if text.startswith("{") and '"content"' in text[:60]:
        try:
            d = extract_json(text)
            return str(d.get("content", "")).strip(), [" ".join(str(c).split())[:240] for c in (d.get("changes") or []) if str(c).strip()][:8]
        except ValueError:
            pass
    body, _, tail = text.partition(DELIM)
    changes = [" ".join(l.lstrip("-*• ").split())[:240] for l in tail.splitlines() if l.strip("-*• ").strip()][:8]
    return body.strip(), changes


async def revise_section(
    section: dict, context: dict, feedback: list[str], refs: list[dict], style: str
) -> tuple[dict, list[str], str]:
    """Kembalikan (draf {content, citations}, ringkasan_perubahan, penyedia). Melempar LLMUnavailable bila tak layak."""
    if not refs:
        raise LLMUnavailable("Pilih minimal satu rujukan sebelum memperbaiki naskah")
    original = section["content"]
    original_words = valid_word_count(original)
    ref_picks = refs[:6]
    markers = {r["citation_id"]: in_text_marker(style, r, i) for i, r in enumerate(ref_picks)}
    keywords = form_keywords(context.get("keywords", ""))
    digest = (context.get("existing_digest") or "").strip()

    user = (
        f"Judul skripsi: {context.get('title')}\n"
        f"Variabel X: {context.get('variable_x') or '-'} · Variabel Y: {context.get('variable_y') or '-'} · "
        f"Subjek: {context.get('subject') or '-'} · Metode: {context.get('method')}\n"
        f"Subbab: {section['section_code']} {section['section_title']} (target {section['target_words']} kata)\n\n"
        "UMPAN BALIK YANG DIPILIH PENGGUNA:\n" + "\n".join(f"- {f}" for f in feedback) + "\n\n"
        + (f"Bagian lain naskah (untuk keselarasan; jangan diulang):\n{digest}\n\n" if digest else "")
        + f"Referensi (satu-satunya sumber klaim baru):\n{_blocks(ref_picks, markers)}\n\n"
        f"NASKAH SUBBAB SAAT INI:\n{original}"
    )
    convo = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
    last = "tidak ada jawaban"
    # Naskah panjang butuh banyak token: ~2,2 token per kata ditambah ruang untuk ringkasan perubahan.
    budget = min(8000, max(3000, int(original_words * 2.4) + 700))
    for _ in range(2):
        raw, provider = await llm_chat_ex(convo, tier="heavy", temperature=0.3, max_tokens=budget)
        content, changes = parse_response(raw)
        correction = ""
        if valid_word_count(content) < max(40, int(original_words * MIN_KEEP_RATIO)):
            last = "hasil perbaikan terlalu pendek dibanding naskah asli"
            correction = "Hasil terlalu pendek atau terpotong. Tulis ulang SELURUH subbab (setara atau lebih panjang dari aslinya), lalu pemisah dan ringkasan perubahan."
        elif content == original.strip():
            last = "tidak ada perubahan"
            correction = "Naskah tidak berubah. Terapkan umpan balik yang relevan dengan menambah atau memperjelas isi."
        else:
            content, _ = dedupe_paragraphs(content, context.get("others") or [])
            content = polish(content, list(markers.values()))
            cites = _collect_citations({}, content, markers, ref_picks, keywords)
            return {"content": content, "citations": cites}, changes, provider
        convo = convo + [{"role": "assistant", "content": raw}, {"role": "user", "content": correction}]
    raise LLMUnavailable(f"Perbaikan tidak layak: {last}")
