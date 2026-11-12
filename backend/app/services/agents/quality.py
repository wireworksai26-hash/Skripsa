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
    ("background", r"(latar belakang|background of the (study|research|problem)|^background$)"),
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
            if kind == "background" and chapter_code not in ("1", ""):
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
            "Write one short introductory sentence, then a NUMBERED LIST of 3 research questions (4 at most; S1 theses are best with 3), one per line, each "
            "starting with '1.', '2.' and ending with a question mark."
            if en
            else "Tulis satu kalimat pengantar singkat, lalu DAFTAR BERNOMOR berisi 3 rumusan masalah (maksimal 4; skripsi S1 paling baik 3), satu per baris, "
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
            "parties), each clearly labelled. State only the CONTRIBUTION this study hopes to make; do not review literature "
            "(citations are optional and should be rare). Do NOT add a closing or summary paragraph (no 'In summary...')."
            if en
            else "Sajikan manfaat dalam dua bagian berlabel: manfaat teoretis dan manfaat praktis (untuk pihak-pihak tertentu). "
            "Nyatakan hanya KONTRIBUSI yang diharapkan dari penelitian ini; jangan meninjau pustaka (sitasi opsional dan jarang). "
            "JANGAN menambah paragraf penutup atau ringkasan (tanpa 'Secara keseluruhan...')."
        ),
        "focus": (
            "State the focus/scope concretely (who, what, where, which aspects), not a general essay. Lock the analysis to ONE "
            "named theory/framework: if the RESEARCHER'S FRAMEWORK names a theory, state explicitly that the analysis is "
            "grounded in it, using its name. If no theory is given, write the placeholder [DATA: main theory used to analyse the data]; "
            "never invent a theorist or framework name. This is not a literature review: state the boundaries only (citations are optional and rare)."
            if en
            else "Nyatakan fokus/batasan secara konkret (siapa, apa, di mana, aspek apa), bukan esai umum. Kunci analisis pada SATU teori/"
            "kerangka bernama: bila KERANGKA DARI PENELITI menyebut teori, tegaskan bahwa analisis berlandaskan teori itu dengan "
            "menyebut namanya. Bila tidak ada, tulis penanda [DATA: teori utama yang membedah data]; jangan mengarang nama ahli atau kerangka. Ini bukan tinjauan pustaka: nyatakan batasannya saja (sitasi opsional dan jarang)."
        ),
        "background": (
            "Write the Background of the Study as ONE continuous argument, in this order: why the topic matters; the phenomenon/"
            "problem in the field; the key concept(s) briefly; relevant previous studies (cited); the research gap. If it refers to "
            "preliminary observation or interviews, do NOT invent numbers or findings: insert a placeholder such as "
            "[DATA: result of the preliminary observation/interview with the teacher]. The LAST paragraph is ONE short paragraph stating "
            "that, based on the phenomena and gap above, the researcher is interested in conducting a study entitled \"<the thesis title>\". "
            "Nothing may follow it. Do NOT write recap paragraphs ('This background has established...') and do not restate teacher roles, "
            "definitions, the reason for the design, or practical benefits (those belong to later subsections). If the length target "
            "is not reached, deepen the argument or previous studies instead of repeating."
            if en
            else "Tulis Latar Belakang sebagai SATU alur argumen berurutan: mengapa topik penting; fenomena/masalah di lapangan; konsep "
            "kunci secara singkat; penelitian terdahulu yang relevan (disitasi); celah penelitian. Bila menyebut observasi/wawancara awal, "
            "JANGAN mengarang angka atau temuan: sisipkan penanda seperti [DATA: hasil observasi/wawancara awal dengan guru]. Paragraf "
            "TERAKHIR adalah SATU paragraf pendek yang menyatakan bahwa, berdasarkan fenomena dan celah di atas, peneliti tertarik "
            "melakukan penelitian berjudul \"<judul skripsi>\". Tidak boleh ada paragraf setelahnya. JANGAN menulis paragraf rangkuman "
            "('Latar belakang ini telah menunjukkan...') dan jangan mengulang peran guru, definisi, alasan memilih desain, atau manfaat "
            "praktis (itu isi subbab lain). Bila target panjang belum tercapai, perdalam argumen atau penelitian terdahulu, bukan mengulang."
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
    # Latar Belakang dan Manfaat tidak ditolak karena ekornya: enforce_closing()/drop_summary_tail() membereskannya secara deterministik.
    if chapter_four_without_data and kind == "findings" and "[DATA" not in text.upper():
        return "Belum ada data lapangan: sisipkan penanda isian [DATA: ...] untuk kutipan/angka, jangan menulis temuan umum tanpa data. Tulis ulang."
    return None


# ---------- bentuk akhir subbab tertentu (Latar Belakang, Manfaat) ----------

_INTEREST = re.compile(r"(entitled|titled|berjudul|bertajuk|judul)", re.I)
_SUMMARY_OPEN = re.compile(
    r"^\s*(this background has|in summary|in conclusion|to sum up|to summari[sz]e|overall,|taken together|secara keseluruhan|singkatnya|"
    r"kesimpulannya|latar belakang (di atas|ini) telah|dengan demikian,? (latar belakang|manfaat))",
    re.I,
)


def drop_summary_tail(text: str) -> str:
    """Buang paragraf penutup yang hanya merangkum (mis. 'In summary, the significance...') bila masih ada isi lain."""
    paras = paragraphs(text)
    while len(paras) > 2 and _SUMMARY_OPEN.match(paras[-1]):
        paras.pop()
    return "\n\n".join(paras)


def enforce_closing(text: str, title: str, language: str) -> str:
    """Latar Belakang ditutup tegas dengan pernyataan ketertarikan peneliti pada judul; paragraf sesudahnya dibuang.

    Kalimat penutup hanya berisi judul asli skripsi (bukan data karangan). Bila model sudah menulisnya, semua yang
    sesudah paragraf itu (rangkuman, pengulangan) dipotong; bila belum, kalimat itu ditambahkan.
    """
    paras = paragraphs(text)
    if not paras or not title.strip():
        return text
    cut = next((i for i in range(len(paras) - 1, -1, -1) if _INTEREST.search(paras[i]) and len(paras[i].split()) <= 90), None)
    if cut is not None:
        return "\n\n".join(paras[: cut + 1])
    paras = [p for p in paras if not _SUMMARY_OPEN.match(p)]
    closing = (
        f'Based on the phenomena and the research gap explained above, the researcher is interested in conducting a study entitled "{title.strip()}".'
        if language == "en"
        else f'Berdasarkan fenomena dan celah penelitian yang telah diuraikan, peneliti tertarik melakukan penelitian berjudul "{title.strip()}".'
    )
    return "\n\n".join(paras + [closing])
