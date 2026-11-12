import re

from app.services.agents.context import form_keywords
from app.services.agents.quality import check_kind, dedupe_paragraphs, drop_summary_tail, enforce_closing, kind_rules, polish, section_kind
from app.services.agents.rag import is_from_abstract
from app.services.agents.structured import STRUCTURED_KINDS, structured_draft
from app.services.citation import in_text_marker
from app.services.llm import LLMUnavailable, extract_json, llm_chat_ex, route


def first_sentences(text: str, n: int = 1) -> str:
    sents = [s for s in re.split(r"(?<=[.!?])\s+", text.replace("\n", " ")) if s.strip()]
    return " ".join(sents[:n])[:400].strip()


def sentence_matching(text: str, keywords: list[str]) -> str:
    sents = [s for s in re.split(r"(?<=[.!?])\s+", text.replace("\n", " ")) if s.strip()]
    key = [k.lower() for k in keywords if len(k) > 3]
    for s in sents:
        low = s.lower()
        if any(k in low for k in key):
            return s.strip()[:400]
    return (sents[0].strip()[:400]) if sents else ""


def ground_snippet(ref: dict, keywords) -> str:
    if isinstance(keywords, str):
        keywords = form_keywords(keywords)
    abstract = ref.get("highlighted_snippet") or ""
    if not abstract:
        return "Cuplikan abstrak tidak tersedia di basis data — verifikasi lengkap melalui tautan DOI/publikasi."
    picked = sentence_matching(abstract, keywords or [])
    return picked or first_sentences(abstract)


def _system(language: str = "id") -> str:
    if language == "en":
        return (
            "You are an Academic Writer Agent writing a thesis draft in formal academic English (APA 7th style) "
            "for undergraduate/postgraduate students.\n"
            "Mandatory rules:\n"
            "1. Write the ENTIRE draft in English, in your own words. No headings; use numbered lists ONLY when the section instructions require them. "
            "Length must approach the section word target: target >= 600 words -> 6-10 paragraphs; "
            "target >= 1000 words -> 8-14 paragraphs. Do not stop before reaching the target.\n"
            '2. PARAPHRASE the EVIDENCE. Never copy evidence sentences into "content"; evidence may only be copied into "snippet".\n'
            "3. Every factual claim MUST end with an in-text citation. Write the PENANDA given for that reference EXACTLY as "
            "provided (character for character), placed at the end of the sentence before the period; do not invent markers.\n"
            "4. Do not invent names, years, or DOIs beyond the provided references.\n"
            "5. Avoid filler sentences; use formal academic English spelling and grammar consistently.\n"
            '6. Respond with JSON ONLY: {"content":"...", "citations":[{"reference_id":"<cited reference id>",'
            '"snippet":"exact copy of ONE evidence sentence from that reference"}]}\n'
            'Style example (illustrative only): "Interactive media use is associated with higher student participation '
            'in class (Author, 2020)." -> the marker "(Author, 2020)" is written exactly as provided.'
        )
    return (
        "Kamu adalah Academic Writer Agent yang menulis draf skripsi bahasa Indonesia baku "
        "(EYD V / PUEBI) untuk mahasiswa S1/S2.\n"
        "Aturan wajib:\n"
        "1. Tulis dalam kalimatmu sendiri, tanpa heading; daftar bernomor HANYA bila instruksi subbab memintanya. "
        "Panjang draf WAJIB mendekati target kata subbab: bila target >= 600 kata tulis 6-10 paragraf; "
        "bila target >= 1000 kata tulis 8-14 paragraf. Jangan berhenti sebelum target tercapai.\n"
        '2. PARAFRASEKAN isi BUKTI. Dilarang menyalin kalimat BUKTI ke dalam content; BUKTI hanya boleh disalin ke "snippet".\n'
        "3. Setiap klaim faktual HARUS diakhiri sitasi dalam-teks. Tulis PENANDA yang diberikan untuk referensi itu "
        "PERSIS apa adanya (karakter demi karakter), diletakkan di akhir kalimat sebelum titik; jangan mengubah atau "
        "membuat penanda sendiri.\n"
        "4. Dilarang mengarang nama, tahun, atau DOI di luar referensi yang diberikan.\n"
        "5. Hindari kalimat pengisi; gunakan ejaan baku KBBI.\n"
        '6. Tanggapi HANYA JSON: {"content":"...", "citations":[{"reference_id":"<id referensi yang dikutip>",'
        '"snippet":"salinan PERSIS satu kalimat BUKTI dari referensi itu"}]}\n'
        'Contoh gaya (isi hanya ilustrasi): "Penggunaan media interaktif berkaitan dengan peningkatan partisipasi siswa '
        'di kelas (Penulis, 2020)." -> penanda "(Penulis, 2020)" ditulis persis seperti diberikan.'
    )


def _target_plan(section: dict) -> tuple[int, int]:
    """(target kata, kata minimum yang diterima). Subbab tanpa target tetap minimal 40 kata."""
    target = int(section.get("target_words") or 0)
    if target >= 100:
        return target, max(40, round(target * 0.85))
    return target, 40


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", text.replace("\n", " ")) if s.strip()]


def _merge_draft(base: str, extra: str) -> str:
    """Gabungkan lanjutan tanpa mengulang kalimat yang sudah ditulis."""
    if not base.strip():
        return extra.strip()
    if not extra.strip():
        return base
    parts = _sentences(extra)
    for k in range(1, min(3, len(parts)) + 1):
        if " ".join(parts[:k]) in base:
            parts = parts[k:]
            break
    tail = " ".join(parts).strip()
    return f"{base.rstrip()}\n\n{tail}" if tail else base


def _grounded_snippet(proposed: str, ref: dict, keywords) -> str:
    """Snippet yang disorot di PDF harus kutipan nyata dari abstrak; karangan LLM diganti kalimat bukti."""
    if proposed and is_from_abstract(proposed, ref.get("highlighted_snippet") or ""):
        return proposed
    evidence = ref.get("evidence") or []
    return evidence[0] if evidence else ground_snippet(ref, keywords)


def _salvage_content(raw: str) -> str:
    """Selamatkan isi draf saat JSON model rusak/terpotong; sitasi tetap dipulihkan dari penanda di teks."""
    m = re.search(r'"content"\s*:\s*"', raw)
    if not m:
        return ""
    rest = raw[m.end() :]
    close = re.search(r'"\s*(?:,\s*"citations"\s*:|\})', rest)
    body = rest[: close.start()] if close else rest
    return (
        body.replace("\\n", "\n")
        .replace("\\r", "")
        .replace("\\t", "\t")
        .replace('\\"', '"')
        .strip()
    )


def valid_word_count(text: str) -> int:
    return len([w for w in re.sub(r"[#*_>~-]", " ", text).split() if any(ch.isalnum() for ch in w)])


def _collect_citations(data: dict, content: str, markers: dict[str, str], ref_picks: list[dict], keywords) -> list[dict]:
    """Penanda berasal dari metadata, dan hanya dihitung bila benar tertulis di isi draf."""
    cites: list[dict] = []
    seen: set[str] = set()
    for c in data.get("citations") or []:
        if not isinstance(c, dict):
            continue
        rid = str(c.get("reference_id", ""))
        if rid not in markers or rid in seen or markers[rid] not in content:
            continue  # bukan rujukan terpilih / duplikat / penanda tak tertulis di isi
        ref = next(r for r in ref_picks if r["citation_id"] == rid)
        seen.add(rid)
        cites.append(
            {
                "marker": markers[rid],
                "reference_id": rid,
                "snippet": _grounded_snippet(str(c.get("snippet", "")).strip(), ref, keywords),
            }
        )
    # LLM menulis penanda di teks tetapi lupa mendaftarkan sitasinya: tetap sah.
    for rid, marker in markers.items():
        if rid not in seen and marker in content:
            ref = next(r for r in ref_picks if r["citation_id"] == rid)
            cites.append({"marker": marker, "reference_id": rid, "snippet": _grounded_snippet("", ref, keywords)})
    return cites


async def generate_section_draft(
    section: dict, form: dict, refs: list[dict], style: str, keywords_join: str
) -> tuple[dict, str]:
    """Kembalikan (draf, nama_penyedia). Melempar LLMUnavailable; tidak ada teks karangan lokal.

    Draf hanya boleh bersandar pada rujukan terpilih, jadi tanpa rujukan fungsi ini menolak bekerja.
    Penanda sitasi dibuat dari metadata rujukan (bukan dari LLM) dan hanya dianggap sitasi bila benar-benar
    tertulis di dalam isi draf. Draf pendek dilanjutkan (maks. 4 kali) sampai ±85% target kata tercapai;
    jawaban cacat dikoreksi dengan umpan balik spesifik (2 percobaan per penyedia), lalu pindah penyedia.
    """
    if not refs:
        raise LLMUnavailable("Pilih minimal satu rujukan sebelum membuat draf")

    keywords = form_keywords(keywords_join)
    language = "en" if form.get("language") == "en" else "id"
    ref_picks = refs[:6]
    markers = {r["citation_id"]: in_text_marker(style, r, i) for i, r in enumerate(ref_picks)}

    def _block(i: int, r: dict) -> str:
        head = (
            f"  {i + 1}. reference_id={r['citation_id']}; penulis={', '.join(r.get('authors', [])[:3])}; "
            f"tahun={r.get('publication_year', 0)}; judul={r.get('title')}; DOI={r.get('doi') or '-'}; "
            f'penanda="{markers[r["citation_id"]]}"'
        )
        evidence = r.get("evidence") or []
        if not evidence:
            return head + "\n     BUKTI: (abstrak tidak tersedia; jangan buat klaim dari referensi ini)"
        return head + "".join(f'\n     BUKTI: "{e}"' for e in evidence)

    ref_blocks = "\n".join(_block(i, r) for i, r in enumerate(ref_picks))
    digest = (form.get("existing_digest") or "").strip()
    existing_block = (
        "Subbab lain yang SUDAH ditulis (hanya judulnya; isinya JANGAN diulang, tulis materi yang berbeda sesuai judul subbab ini):\n"
        f"{digest}\n\n"
        if digest
        else ""
    )
    brief = (form.get("brief") or "").strip()
    brief_block = (
        "KERANGKA DARI PENELITI (sudah mereka temukan; WAJIB diikuti. Jangan mengganti fenomena, masalah, teori, atau metode ini, "
        "dan jangan menambah teori atau metode lain yang bertentangan. Kembangkan, jangan dibantah):\n"
        f"{brief}\n\n"
        if brief
        else ""
    )
    others = [t for t in (form.get("other_texts") or []) if t]
    kind = section_kind(section["section_title"], str(section["chapter_code"]))
    results_data = (form.get("results_data") or "").strip()
    chapter_four_no_data = str(section["chapter_code"]) == "4" and kind == "findings" and not results_data
    data_block = (
        f"DATA PENELITIAN (satu-satunya sumber temuan):\n{results_data}\n\n"
        if results_data and str(section["chapter_code"]) == "4"
        else ""
    )
    section_rules = kind_rules(kind, language, bool(results_data))
    # Bab III (metodologi) sering bersandar pada buku metode yang tidak ada di rujukan terpilih; memaksakan sitasi
    # justru mendorong sitasi asal tempel. Di bab ini sitasi dianjurkan, bukan syarat.
    citations_required = str(section["chapter_code"]) != "3" and kind not in ("significance", "focus")
    target_words, min_words = _target_plan(section)
    length_rule = (
        f"Panjang wajib: minimal {min_words} kata (target {target_words} kata). "
        "Tulis paragraf yang benar-benar berkembang; jangan mengakhiri draf sebelum target tercapai.\n"
        if target_words
        else ""
    )
    language_rule = (
        "Tulis seluruh isi subbab ini dalam bahasa Inggris akademik formal "
        "(jangan mencampur bahasa Indonesia selain nama diri/istilah).\n"
        if language == "en"
        else ""
    )
    mirror = (form.get("mirror_rq") or "").strip()
    mirror_block = (
        "RUMUSAN MASALAH YANG SUDAH DITULIS (tujuan WAJIB mencerminkannya satu per satu: jumlah butir sama, urutan sama, istilah kunci sama. "
        "Jangan mengganti konsep, mis. 'respond/response' tidak boleh menjadi 'perception', dan jangan menambah topik baru):\n"
        f"{mirror}\n\n"
        if mirror and kind == "objectives"
        else ""
    )
    outline_hint = (section.get("outline_hint") or "").strip()
    outline_block = f"STRUKTUR: {outline_hint}\n" if outline_hint else ""
    user = (
        f"Judul skripsi: {form.get('title', form.get('topic', ''))}\n"
        f"Formulir: topik=\"{form.get('topic')}\", X=\"{form.get('variable_x')}\", "
        f"Y=\"{form.get('variable_y')}\", subjek=\"{form.get('subject')}\", metode={form.get('method')}\n"
        f"Tugas: Bab {section['chapter_code']} subbab {section['section_code']} — "
        f"{section['section_title']} (target {section['target_words']} kata)\n"
        f"{outline_block}"
        f"{language_rule}"
        f"{length_rule}"
        f"{section_rules}"
        f"{existing_block}"
        f"{mirror_block}"
        f"{brief_block}"
        f"{data_block}"
        f"Referensi terverifikasi (satu-satunya sumber sitasi):\n{ref_blocks}\n"
        'Untuk setiap sitasi, isi "snippet" dengan salinan persis SATU kalimat BUKTI dari referensi tersebut.'
    )

    marker_list = ", ".join(markers.values())

    # Subbab berbentuk butir, dan temuan Bab IV tanpa data, disusun dari JSON terstruktur (audit BUG-02/03).
    structured_kind = kind if kind in STRUCTURED_KINDS else ("findings" if chapter_four_no_data else None)
    if structured_kind:
        text, provider = await structured_draft(structured_kind, section, user, language, list(markers.values()), others, mirror_count=int(form.get("mirror_count") or 0) or None)
        found = {c["reference_id"]: c for c in _collect_citations({}, text, markers, ref_picks, keywords)}
        return {"content": text, "citations": list(found.values())}, provider

    def finish(text: str, found: dict, provider: str):
        if kind == "background":
            text = enforce_closing(drop_summary_tail(text), str(form.get("title") or form.get("topic") or ""), language)
        elif kind == "significance":
            text = drop_summary_tail(text)
        content = polish(text, list(markers.values()))
        # Paragraf yang dipotong tidak boleh meninggalkan sitasi yatim di daftar sitasi subbab.
        kept = {k: v for k, v in found.items() if markers.get(k) and markers[k] in content}
        return {"content": content, "citations": list(kept.values())}, provider

    max_tokens = min(4096, max(2400, int(target_words * 2.2) + 800))
    names: list[str | None] = [p.name for p in route("heavy")] or [None]
    failures: list[str] = []
    for name in names:
        convo = [{"role": "system", "content": _system(language)}, {"role": "user", "content": user}]
        last_error = "tidak ada jawaban"
        content = ""
        cites: dict[str, dict] = {}
        quality_fails = 0
        kind_fails = 0
        replace_next = False  # tulis ulang utuh karena bentuk subbab salah
        last_provider = name or "llm"
        for _ in range(5):
            try:
                raw, provider = await llm_chat_ex(convo, tier="heavy", max_tokens=max_tokens, only=name)
                last_provider = provider
            except LLMUnavailable as exc:  # error jaringan/kuota: langsung ke penyedia berikutnya
                last_error = str(exc)
                break
            correction = ""
            try:
                data = extract_json(raw)
            except ValueError as exc:
                salvaged = _salvage_content(raw)
                last_error = f"JSON tidak valid ({exc})"
                if salvaged:
                    data = {"content": salvaged, "citations": []}
                else:
                    correction = "Jawabanmu bukan JSON valid. Balas HANYA dengan satu objek JSON sesuai format."
                    data = None

            if data is not None:
                part = str(data.get("content", "")).strip()
                part_cites = _collect_citations(data, part, markers, ref_picks, keywords) if part else []
                # Gabungan lanjutan dibersihkan dari paragraf yang mengulang subbab ini maupun subbab lain (BUG-01).
                base = "" if replace_next else content
                merged, _removed = dedupe_paragraphs(_merge_draft(base, part), others)
                grown = valid_word_count(merged) - valid_word_count(base)
                if not content and not part_cites and citations_required:
                    last_error = "draf tidak memuat penanda sitasi dari rujukan terpilih"
                    correction = (
                        "Isi draf TIDAK memuat penanda sitasi. Tulis ulang: parafrasekan BUKTI (jangan menyalinnya) dan "
                        f"akhiri tiap klaim dengan salah satu penanda ini, persis apa adanya: {marker_list}."
                    )
                elif grown < 15 and not base:
                    last_error = "draf menyalin bagian lain naskah"
                    correction = (
                        "Drafmu mengulang paragraf dari subbab lain. Tulis isi BARU yang khusus membahas judul subbab ini, "
                        f"tetap memakai penanda sitasi yang diberikan: {marker_list}."
                    )
                elif grown < 15:
                    last_error = "lanjutan tidak menambah isi baru"
                    correction = (
                        "Bagian lanjutan mengulang kalimat yang sudah ada. Tulis paragraf BARU yang memperdalam argumen "
                        f"(minimal {max(60, target_words // 3)} kata), tetap memakai penanda sitasi yang diberikan."
                    )
                else:
                    if replace_next:
                        cites = {}
                        replace_next = False
                    content = merged
                    for c in part_cites:
                        cites.setdefault(c["reference_id"], c)
                    words = valid_word_count(content)
                    if not target_words or words >= min_words:
                        problem = check_kind(kind, content, chapter_four_no_data)
                        if problem and kind_fails < 2:
                            # Bentuk wajib tidak terpenuhi (mis. rumusan masalah tanpa pertanyaan): minta tulis ulang utuh;
                            # draf lama tetap disimpan sebagai cadangan bila tulis ulang gagal.
                            kind_fails += 1
                            last_error = problem
                            replace_next = True
                            convo = convo + [{"role": "assistant", "content": raw}, {"role": "user", "content": problem}]
                            continue
                        return finish(content, cites, provider)
                    need = target_words - words
                    convo = convo + [
                        {"role": "assistant", "content": raw},
                        {
                            "role": "user",
                            "content": (
                                f"Draf sementara baru {words} kata dari target {target_words}. "
                                f"LANJUTKAN tanpa mengulang kalimat yang sudah ada: tambahkan minimal {need} kata "
                                "(2-4 paragraf baru) yang memperdalam argumen subbab ini, tetap memakai penanda "
                                'sitasi yang diberikan. Balas JSON yang sama, tetapi "content" berisi HANYA bagian lanjutan.'
                                + (" Write the continuation in English." if language == "en" else "")
                            ),
                        },
                    ]
                    continue

            if correction:
                quality_fails += 1
                convo = convo + ([] if data is None else [{"role": "assistant", "content": raw}]) + [
                    {"role": "user", "content": correction}
                ]
                if quality_fails >= 2:
                    break

        if content and (cites or not citations_required):
            return finish(content, cites, last_provider)
        failures.append(f"{name or 'llm'}: {last_error}")
    raise LLMUnavailable("LLM tidak menghasilkan draf yang layak — " + "; ".join(failures))
