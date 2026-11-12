"""Usulan sub-subbab (tingkat 3, mis. 2.1.1) agar kerangka skripsi lebih terarah.

Agen hanya mengusulkan judul. Usulan tidak menulis ke basis data: pengguna meninjaunya di editor struktur
(ubah, hapus, atau terima) lalu menyimpannya lewat jalur struktur yang sudah ada. Judul divalidasi:
tanpa nomor, tanpa nama/tahun/angka, dan tidak berupa klaim hasil.
"""

import asyncio
import re

from app.services.agents.context import _code_key, brief_for_chapter
from app.services.agents.documents import GenerationError, _ask, _lang
from app.services.agents.quality import section_kind
from app.services.templates import localize_template, resolve_template

MIN_PARENT_WORDS = 300
MAX_CHILDREN = 5
MIN_CHILDREN = 2
_PARENT_RE = re.compile(r"^\d+\.\d+$")
_NUMBERING_RE = re.compile(r"^\s*(?:\d+(?:\.\d+)*[.)]?|[A-Za-z][.)])\s+")  # "2.1.1 ", "1) ", "A. "

SYSTEM = """Kamu pembimbing skripsi berpengalaman yang merancang kerangka. Untuk setiap SUBBAB yang diberikan, usulkan
SUB-SUBBAB (tingkat 3, mis. 2.1.1) agar isi skripsi lebih terarah.
Aturan:
1. Pecah hanya subbab yang cukup luas dan lazim punya anak subbab pada skripsi {method}. Subbab yang sempit atau memang
   lazimnya satu uraian utuh: "children" kosong. Jangan memaksa.
2. {min_c} sampai {max_c} sub-subbab per subbab, tidak tumpang tindih, berurutan logis. Jumlah "words" semua anak mendekati
   target kata induknya (tiap anak 100-600 kata).
3. Judul spesifik pada topik penelitian ini (sebut konsep, variabel, atau subjek), bukan judul generik.
4. Judul berupa frasa judul (maksimal 12 kata): TANPA nomor, nama penulis, tahun, angka, atau kesimpulan/klaim hasil.
5. Patuhi KERANGKA PENELITI bila ada; jangan menambah teori atau metode yang bertentangan.
6. Bab IV hanya struktur penyajian (mis. deskripsi data, uji prasyarat, pengujian hipotesis), tanpa mengklaim hasil.
   Bab V (kesimpulan dan saran) umumnya tanpa anak.
7. Bahasa judul: {lang}.
Tanggapi HANYA JSON: {{"sections":[{{"code":"2.1","children":[{{"title":"","words":300}}]}}]}}"""


def clean_title(raw: object) -> str:
    t = _NUMBERING_RE.sub("", str(raw or "")).strip().strip("\"'“”‘’").strip(" .:;-–—")
    t = " ".join(t.split())
    if not t or len(t) > 140 or len(t.split()) > 16:
        return ""
    if re.search(r"\d{4}|%|\bet al\b", t, re.I):  # tahun, persentase, atau penulis = kutipan/klaim, bukan judul
        return ""
    return t


def clean_children(parent_title: str, parent_words: int, raw: object) -> list[dict]:
    """Judul bersih, tanpa duplikat dan tanpa mengulang judul induk; 2-5 anak, kata per anak 80-800."""
    out: list[dict] = []
    seen = {parent_title.strip().lower()}
    for item in raw if isinstance(raw, list) else []:
        data = item if isinstance(item, dict) else {"title": item}
        title = clean_title(data.get("title"))
        key = title.lower()
        if not title or key in seen:
            continue
        seen.add(key)
        words = data.get("words")
        out.append({"title": title, "target_words": int(words) if isinstance(words, (int, float)) and words > 0 else 0})
    out = out[:MAX_CHILDREN]
    if len(out) < MIN_CHILDREN:
        return []  # satu anak tidak berarti pemecahan
    default = max(100, round((parent_words or 400) / len(out) / 50) * 50)
    for c in out:
        c["target_words"] = max(80, min(800, c["target_words"] or default))
    return out


# Subbab yang memang berbentuk butir/uraian pendek atau penutup: tidak dipecah lagi.
_NO_SPLIT_KINDS = {"rq", "rq_obj", "objectives", "hypothesis", "suggestions", "focus"}
_NO_SPLIT_TITLE = re.compile(r"(kesimpulan|conclusion|daftar|references?|appendix|lampiran)", re.I)


def splittable(section) -> bool:
    if section_kind(section.section_title, str(section.chapter_code)) in _NO_SPLIT_KINDS:
        return False
    return not _NO_SPLIT_TITLE.search(section.section_title or "")


def _children_exist(codes: list[str], parent: str) -> bool:
    return any(c.startswith(parent + ".") for c in codes)


async def propose(thesis, db, chapters: list[str] | None = None) -> dict:
    """{suggestions: {kode: [{title, target_words}]}, skipped: [kode], errors: [str], provider: str}."""
    template = localize_template(resolve_template(db, thesis.campus_template_id), thesis.language or "id")
    chapter_titles = {str(c["chapter_number"]): c["chapter_title"] for c in template.get("chapters", [])}
    sections = sorted(thesis.sections, key=lambda s: _code_key(s.section_code))
    codes = [s.section_code for s in sections]

    wanted = {str(c) for c in (chapters or [])}
    chapter_nums = sorted({str(s.chapter_code) for s in sections}, key=lambda c: int(c) if c.isdigit() else 99)
    # Mode "semua bab" melewati Bab I (lazimnya tanpa tingkat 3) dan bab penutup; bab yang dipilih eksplisit tetap diproses.
    auto_skip = {chapter_nums[0], chapter_nums[-1]} if len(chapter_nums) >= 3 else set()
    by_chapter: dict[str, list] = {}
    skipped: list[str] = []
    for s in sections:
        if not _PARENT_RE.match(s.section_code) or (wanted and str(s.chapter_code) not in wanted):
            continue
        if not wanted and str(s.chapter_code) in auto_skip:
            continue
        if not splittable(s):
            continue
        if _children_exist(codes, s.section_code):
            skipped.append(s.section_code)
            continue
        if (s.target_words or 0) < MIN_PARENT_WORDS:
            continue
        by_chapter.setdefault(str(s.chapter_code), []).append(s)
    if not by_chapter:
        return {"suggestions": {}, "skipped": skipped, "errors": [], "provider": ""}

    lang = _lang(thesis)
    gate = asyncio.Semaphore(3)

    async def one(ch: str, parents: list) -> tuple[dict, str, str | None]:
        by_code = {p.section_code: p for p in parents}
        brief = brief_for_chapter(thesis, ch)
        lines = "\n".join(f"- {p.section_code} {p.section_title} (target {p.target_words} kata)" for p in parents)
        user = (
            f"Judul skripsi: {thesis.title}\n"
            f"Topik: {thesis.title}; variabel X: {thesis.variable_x or '-'}; variabel Y: {thesis.variable_y or '-'}; "
            f"subjek: {thesis.subject or '-'}; metode: {thesis.research_method}; jenjang: {thesis.degree_level or 'S1'}\n"
            + (f"KERANGKA PENELITI:\n{brief}\n" if brief else "")
            + f"\nBab {ch}: {chapter_titles.get(ch, '')}\nSubbab yang boleh diberi sub-subbab:\n{lines}"
        )
        messages = [
            {"role": "system", "content": SYSTEM.format(method=thesis.research_method, min_c=MIN_CHILDREN, max_c=MAX_CHILDREN, lang=lang)},
            {"role": "user", "content": user},
        ]

        def validate(data: dict) -> dict:
            rows = data.get("sections") if isinstance(data, dict) else None
            if not isinstance(rows, list):
                raise ValueError('JSON harus berisi "sections" berupa daftar')
            found: dict[str, list[dict]] = {}
            for row in rows:
                code = str((row or {}).get("code", "")).strip()
                parent = by_code.get(code)
                if not parent:
                    continue  # kode di luar daftar yang diminta diabaikan, bukan dipercaya
                kids = clean_children(parent.section_title, parent.target_words or 0, (row or {}).get("children"))
                if kids:
                    found[code] = kids
            return found

        async with gate:
            try:
                result, provider = await _ask(messages, validate, max_tokens=1600, temperature=0.3)
                return result, provider, None
            except GenerationError as exc:
                return {}, "", f"Bab {ch}: {exc}"

    results = await asyncio.gather(*[one(ch, ps) for ch, ps in by_chapter.items()])
    suggestions: dict[str, list[dict]] = {}
    errors: list[str] = []
    provider = ""
    for found, prov, err in results:
        suggestions.update(found)
        provider = provider or prov
        if err:
            errors.append(err)
    if errors and not suggestions and len(errors) == len(results):
        raise GenerationError("; ".join(errors))
    return {"suggestions": suggestions, "skipped": skipped, "errors": errors, "provider": provider}
