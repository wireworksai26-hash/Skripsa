"""Penjaga mutu teks hasil LLM (audit 7 Nov 2026: BUG-01, BUG-02, BUG-03, BUG-05, BUG-07).

- Paragraf yang (hampir) sama dengan paragraf lain di subbab ini atau subbab lain dibuang (anti salin-tempel).
- Subbab yang wajib berisi butir (rumusan masalah, tujuan, saran) diperiksa agar tidak menjadi esai "tentang" subbab.
- Paragraf raksasa dipecah; penanda sitasi yang tertulis setelah titik dipindah ke sebelum titik.
"""

import re

SHINGLE = 5
DUP_THRESHOLD = 0.6  # >= 60% 5-gram paragraf yang lebih pendek ada di paragraf lain -> duplikat
MAX_PARAGRAPH_WORDS = 180

_CITE = re.compile(r"\([^()]*\d{4}[a-z]?\)|\[\d+(?:[,–-]\s*\d+)*\]")


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", _CITE.sub(" ", text.lower()))


def _shingles(text: str) -> set[tuple[str, ...]]:
    t = _tokens(text)
    if len(t) < SHINGLE:
        return {tuple(t)} if t else set()
    return {tuple(t[i : i + SHINGLE]) for i in range(len(t) - SHINGLE + 1)}


def similarity(a: str, b: str) -> float:
    """Tumpang tindih 5-gram relatif terhadap paragraf yang lebih pendek (abaikan penanda sitasi)."""
    sa, sb = _shingles(a), _shingles(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / min(len(sa), len(sb))


def paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n|\n", text or "") if p.strip()]


def dedupe_paragraphs(text: str, others: list[str] | None = None, threshold: float = DUP_THRESHOLD) -> tuple[str, int]:
    """Buang paragraf yang mengulang paragraf sebelumnya di teks ini atau paragraf di `others`. -> (teks, dibuang)."""
    pool = [p for o in (others or []) for p in paragraphs(o) if len(_tokens(p)) >= 12]
    pool_sh = [_shingles(p) for p in pool]
    kept: list[str] = []
    kept_sh: list[set] = []
    removed = 0
    for p in paragraphs(text):
        sh = _shingles(p)
        short = len(_tokens(p)) < 12  # butir daftar pendek tidak dibandingkan
        dup = not short and any(sh and o and len(sh & o) / min(len(sh), len(o)) >= threshold for o in (*kept_sh, *pool_sh))
        if dup:
            removed += 1
            continue
        kept.append(p)
        kept_sh.append(sh if not short else set())
    return "\n\n".join(kept), removed


def split_long_paragraphs(text: str, max_words: int = MAX_PARAGRAPH_WORDS) -> str:
    out: list[str] = []
    for p in paragraphs(text):
        if len(p.split()) <= max_words or re.match(r"^(\d{1,2}[.)]|[-•*])\s", p):
            out.append(p)
            continue
        sents = re.split(r"(?<=[.!?])\s+(?=[A-Z\"“(])", p)
        chunk: list[str] = []
        for s in sents:
            chunk.append(s)
            if len(" ".join(chunk).split()) >= max_words * 0.7:
                out.append(" ".join(chunk))
                chunk = []
        if chunk:
            if out and len(" ".join(chunk).split()) < 40 and not re.match(r"^(\d{1,2}[.)]|[-•*])\s", out[-1]):
                out[-1] = f"{out[-1]} {' '.join(chunk)}"
            else:
                out.append(" ".join(chunk))
    return "\n\n".join(out)


def markers_before_period(text: str, markers: list[str]) -> str:
    """"...strategi. (Nur, 2021)" -> "...strategi (Nur, 2021)." untuk penanda yang dikenal."""
    for m in sorted(set(markers), key=len, reverse=True):
        esc = re.escape(m)
        # "kalimat. (Nur, 2021)" maupun "kalimat. (Nur, 2021)." -> "kalimat (Nur, 2021)."
        text = re.sub(rf"([^\s.!?])\s*([.!?])\s*{esc}\.?(?=\s|$)", lambda x: f"{x.group(1)} {m}{x.group(2)}", text)
    return text


def polish(text: str, markers: list[str]) -> str:
    return split_long_paragraphs(markers_before_period(text, markers))


# ---------- jenis subbab yang isinya wajib berupa butir ----------

_KINDS = [
    ("rq_obj", r"(rumusan.*tujuan|research questions? and objectives?|questions? and objectives?)"),
    ("rq", r"(rumusan masalah|pertanyaan penelitian|research questions?|problems? of the study|formulation of the problem|statement of the problem)"),
    ("objectives", r"(tujuan penelitian|objectives? of the (study|research)|research objectives?|purposes? of the study)"),
    ("hypothesis", r"(hipotesis|hypothes[ie]s)"),
    ("suggestions", r"(^saran$|\bsaran\b|suggestions?|recommendations?)"),
    ("significance", r"(manfaat|kegunaan|significance)"),
    ("focus", r"(fokus penelitian|batasan masalah|focus of the study|scope|limitation of the (study|problem))"),
    ("findings", r"(temuan|hasil penelitian|hasil pengujian|deskripsi data|findings|results?|description of the data)"),
    ("discussion", r"(pembahasan|discussion)"),
]


def section_kind(title: str, chapter_code: str = "") -> str | None:
    t = (title or "").strip().lower()
    for kind, pat in _KINDS:
        if re.search(pat, t):
            if kind in ("findings", "discussion") and chapter_code not in ("4", ""):
                continue
            return kind
    return None


def kind_rules(kind: str | None, language: str, has_data: bool) -> str:
    en = language == "en"
    common = (
        "Write the actual CONTENT of this section, not an essay ABOUT the section. Never open with sentences such as "
        "'The formulation of research questions represents...' or 'Suggestions are important because...'.\n"
        if en
        else "Tulis ISI subbab ini, bukan esai TENTANG subbab ini. Jangan membuka dengan kalimat seperti "
        "'Perumusan masalah merupakan bagian penting...' atau 'Saran penting karena...'.\n"
    )
    para = (
        f"Keep each paragraph at most {MAX_PARAGRAPH_WORDS} words (5-8 sentences).\n"
        if en
        else f"Setiap paragraf maksimal {MAX_PARAGRAPH_WORDS} kata (5-8 kalimat).\n"
    )
    rules = {
        "rq": (
            "Write one short introductory sentence, then a NUMBERED LIST of 2-4 research questions, one per line, each "
            "starting with '1.', '2.' and ending with a question mark."
            if en
            else "Tulis satu kalimat pengantar singkat, lalu DAFTAR BERNOMOR berisi 2-4 rumusan masalah, satu per baris, "
            "diawali '1.', '2.' dan diakhiri tanda tanya."
        ),
        "rq_obj": (
            "Write: (a) one introductory sentence, then a numbered list of 2-4 research questions ending with '?'; "
            "(b) one sentence, then a numbered list of objectives that mirror the questions, each starting with 'To ...'."
            if en
            else "Tulis: (a) satu kalimat pengantar lalu daftar bernomor 2-4 rumusan masalah yang diakhiri '?'; "
            "(b) satu kalimat lalu daftar bernomor tujuan yang sejalan dengan rumusan, masing-masing diawali 'Untuk ...'."
        ),
        "objectives": (
            "Write one introductory sentence, then a NUMBERED LIST of objectives (one per line, each starting with 'To ...') "
            "that mirror the research questions."
            if en
            else "Tulis satu kalimat pengantar, lalu DAFTAR BERNOMOR tujuan penelitian (satu per baris, diawali 'Untuk ...') "
            "yang sejalan dengan rumusan masalah."
        ),
        "hypothesis": (
            "State the hypotheses explicitly as a numbered list (H1, H0 pairs where relevant)."
            if en
            else "Nyatakan hipotesis secara eksplisit dalam daftar bernomor (pasangan Ha/H0 bila relevan)."
        ),
        "suggestions": (
            "Write one short introductory sentence, then NUMBERED suggestions grouped for (1) English teachers/practitioners, "
            "(2) students, and (3) future researchers. Each suggestion must be concrete and actionable."
            if en
            else "Tulis satu kalimat pengantar singkat, lalu saran BERNOMOR yang dikelompokkan untuk (1) guru/praktisi, "
            "(2) siswa/mahasiswa, dan (3) peneliti selanjutnya. Setiap saran konkret dan dapat dilakukan."
        ),
        "significance": (
            "Present the significance as two parts: theoretical significance and practical significance (for specific "
            "parties), each clearly labelled."
            if en
            else "Sajikan manfaat dalam dua bagian berlabel: manfaat teoretis dan manfaat praktis (untuk pihak-pihak tertentu)."
        ),
        "focus": (
            "State the focus/scope concretely (who, what, where, which aspects), not a general essay."
            if en
            else "Nyatakan fokus/batasan secara konkret (siapa, apa, di mana, aspek apa), bukan esai umum."
        ),
    }
    findings_rule = (
        (
            "Do NOT repeat the research methodology (that belongs to Chapter III). Organise the findings by theme following "
            "the research questions. "
            + (
                "Base every finding on the RESEARCH DATA provided below; do not invent other data."
                if has_data
                else "No field data has been provided: do NOT invent quotes, numbers, or participant details. Instead, write the "
                "structure of each theme and insert clearly marked placeholders in square brackets that the student must "
                "replace, e.g. [DATA: interview excerpt from S1 about ...] or [DATA: percentage of students who ...]."
            )
        )
        if en
        else (
            "JANGAN mengulang metodologi penelitian (itu isi Bab III). Susun temuan per tema mengikuti rumusan masalah. "
            + (
                "Setiap temuan wajib bersandar pada DATA PENELITIAN di bawah; jangan mengarang data lain."
                if has_data
                else "Belum ada data lapangan: JANGAN mengarang kutipan, angka, atau identitas partisipan. Tulis struktur tiap tema "
                "dan sisipkan penanda isian dalam kurung siku yang wajib diganti mahasiswa, mis. [DATA: kutipan wawancara S1 "
                "tentang ...] atau [DATA: persentase siswa yang ...]."
            )
        )
    )
    extra = rules.get(kind or "", "")
    if kind in ("findings", "discussion"):
        extra = findings_rule
    return common + para + (extra + "\n" if extra else "")


def check_kind(kind: str | None, text: str, chapter_four_without_data: bool = False) -> str | None:
    """Pesan koreksi bila isi subbab tidak memenuhi bentuk wajibnya; None bila lolos."""
    items = re.findall(r"(?m)^\s*(?:\d{1,2}[.)]|[a-z][.)]|[-•*])\s+\S", text)
    if kind in ("rq", "rq_obj") and (text.count("?") < 2 or len(items) < 2):
        return "Subbab ini WAJIB memuat daftar bernomor rumusan masalah (minimal 2 butir) yang masing-masing diakhiri tanda tanya. Tulis ulang seluruh subbab."
    if kind == "objectives" and len(items) < 2:
        return "Subbab ini WAJIB memuat daftar bernomor tujuan penelitian (minimal 2 butir). Tulis ulang seluruh subbab."
    if kind == "suggestions" and len(items) < 3:
        return "Subbab ini WAJIB memuat minimal 3 butir saran bernomor yang konkret. Tulis ulang seluruh subbab."
    if chapter_four_without_data and kind == "findings" and "[DATA" not in text.upper():
        return "Belum ada data lapangan: sisipkan penanda isian [DATA: ...] untuk kutipan/angka, jangan menulis temuan umum tanpa data. Tulis ulang."
    return None
