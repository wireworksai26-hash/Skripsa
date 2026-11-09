"""Parser PDF pedoman penulisan kampus -> templat JSON (Campus Template Engine).

Alur: PyMuPDF (fallback pypdf) mengekstrak teks -> baris berulang/huruf berjarak dibersihkan -> halaman paling
relevan dipilih -> pola aturan eksplisit (margin, huruf, spasi, sitasi) dan daftar bab/subbab dibaca langsung ->
LLM melengkapi nilai yang tidak tertangkap pola -> validasi ketat. Nilai di luar batas masuk akal diganti nilai
bawaan, dan kutipan bukti dicek benar-benar ada di teks PDF agar halusinasi LLM terlihat oleh pengguna.
"""

import asyncio
import io
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

from pypdf import PdfReader
from pypdf.errors import PdfReadError

try:
    import pymupdf  # type: ignore
except Exception:  # pragma: no cover - pymupdf opsional, pypdf tetap dipakai
    pymupdf = None

from app.services.agents.rag import normalize
from app.services.llm import LLMUnavailable, extract_json, llm_chat_ex
from app.services.templates import CAMPUS_TEMPLATES, suggest_template_id

MAX_PDF_BYTES = 15 * 1024 * 1024
MAX_PAGES = 300
TEXT_BUDGET = 40000
MIN_TEXT_CHARS = 400
MAX_LLM_TOKENS = 7000

DEFAULT_COVER = {"logo_cm": 4, "title_pt": 14, "body_pt": 12, "caps": True, "title_page": True, "approval": True, "originality": True}

DEFAULT_PAGE_SETUP = {
    "paper_size": "A4",
    "margins_cm": {"top": 4.0, "left": 4.0, "bottom": 3.0, "right": 3.0},
    "font_family": "Times New Roman",
    "font_size_pt": 12,
    "line_spacing": 1.5,
    "paragraph_indent_cm": 1.0,
}
CITATION_STYLES = {"APA_7TH", "IEEE", "CHICAGO", "HARVARD"}

_PAGE_PATTERNS = [
    (re.compile(r"\b(?:margin|batas\s+(?:atas|bawah|kiri|kanan)|tepi)\b", re.I), 4),
    (re.compile(r"\b(?:spasi|jarak\s+(?:antar)?baris|line\s*spacing)\b", re.I), 4),
    (re.compile(r"\b(?:times\s+new\s+roman|times\s+news\s+roman|arial|calibri|cambria)\b", re.I), 3),
    (re.compile(r"\b(?:ukuran|besar)\s+(?:huruf|font)\b", re.I), 2),
    (re.compile(r"\bsistematika\b", re.I), 5),
    (re.compile(r"\bBAB\s+[IVXLC\d]+\b", re.I), 3),
    (re.compile(r"\b(?:sitasi|kutipan|daftar\s+(?:pustaka|rujukan))\b", re.I), 2),
    (re.compile(r"\b(?:APA|IEEE|HARVARD|CHICAGO)\b"), 2),
    (re.compile(r"\b(?:A4|A-4|kuarto|folio|F4)\b", re.I), 1),
    (re.compile(r"\b(?:menjorok|indentasi|alinea|paragraf)\b", re.I), 1),
    (re.compile(r"\bdaftar\s+isi\b", re.I), 6),
    (re.compile(r"\d+(?:[.,]\d+)?\s*cm\b", re.I), 2),
    (re.compile(r"\d+(?:[.,]\d+)?\s*pt\b", re.I), 1),
    (re.compile(r"\b[1-4]\s*spasi\b", re.I), 2),
]

_ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
_SIDES = ("top", "left", "bottom", "right")
_SIDE_WORDS = {"top": "atas", "left": "kiri", "bottom": "bawah", "right": "kanan"}
_BACKMATTER = re.compile(
    r"^(?:daftar\s+(?:rujukan|pustaka|tabel|gambar|bagan|lampiran)|lampiran|riwayat\s+hidup)\b",
    re.I,
)
_CHAPTER_RE = re.compile(r"^\s*(?:[a-z]\.\s*)?BAB\s+([IVXLC]+|\d{1,2})\b[\s.:\-–—]*(.*)$", re.I)
_SUB_NUM_RE = re.compile(r"^\s*(\d{1,2})\.(\d{1,2})(?:\.(\d{1,2}))?\s+(.+)$")
_SUB_PAREN_RE = re.compile(r"^\s*\d{1,2}\)\s+(.+)$")
_SUB_LETTER_RE = re.compile(r"^\s*([A-Za-z])\.\s+(.+)$")
_TOP_STOP_RE = re.compile(r"^\s*[IVX]+\.\s+")


class ParseError(Exception):
    def __init__(self, message: str, status: int = 422) -> None:
        super().__init__(message)
        self.status = status


@dataclass
class PdfText:
    pages: list[str]
    empty_pages: int = 0

    @property
    def chars(self) -> int:
        return sum(len(p) for p in self.pages)


def _fix_letter_spaced_line(line: str) -> str:
    tokens = line.split()
    if len(tokens) < 8:
        return line
    singles = [t for t in tokens if len(t) == 1 and t.isalnum()]
    if len(singles) / len(tokens) < 0.6:
        return line
    joined = "".join(tokens)
    joined = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", joined)
    joined = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", joined)
    joined = re.sub(r"(?<=[\d|])(?=[A-Za-z])", " ", joined)
    joined = re.sub(r"(?<=[A-Za-z])(?=[\d|])", " ", joined)
    return joined


def _clean_page_text(raw: str) -> str:
    if not raw:
        return ""
    text = unicodedata.normalize("NFKC", raw)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ").replace("\u00ad", "")
    text = re.sub(r"[\u200b-\u200f\u202a-\u202e\ufeff]", "", text)
    text = text.translate({0xF0B7: "-", 0xF0A7: "-", 0xF0B1: "-", 0xF0D8: "-"})
    text = re.sub(r"-\s*\n\s*(?=[a-z])", "", text)
    lines = []
    for line in text.split("\n"):
        line = _fix_letter_spaced_line(re.sub(r"[ \t]+", " ", line).strip())
        if not line:
            continue
        if re.fullmatch(r"[\s\-–—|]*[ivxlcdm\d]{1,4}[\s\-–—|]*", line, re.I):
            continue
        lines.append(line)
    return "\n".join(lines)


def _strip_running_lines(pages: list[str]) -> list[str]:
    if len(pages) < 4:
        return pages

    def key(line: str) -> str:
        low = re.sub(r"\s+", " ", line).strip().lower()
        return re.sub(r"^[ivxlcdm\d]+\s*\|\s*", "", low)

    counts: Counter[str] = Counter()
    for page in pages:
        for line in {key(ln) for ln in page.split("\n") if ln.strip()}:
            if 3 <= len(line) <= 120:
                counts[line] += 1
    threshold = max(3, int(len(pages) * 0.35))
    repeated = {line for line, n in counts.items() if n >= threshold}
    return [
        "\n".join(ln for ln in page.split("\n") if key(ln) not in repeated).strip()
        for page in pages
    ]


def _extract_pages_pymupdf(data: bytes) -> list[str]:
    assert pymupdf is not None
    doc = pymupdf.open(stream=data, filetype="pdf")
    try:
        if doc.needs_pass and not doc.authenticate(""):
            raise ParseError("PDF terkunci kata sandi; buka kuncinya lalu unggah ulang")
        return [doc[i].get_text("text", sort=True) for i in range(min(doc.page_count, MAX_PAGES))]
    finally:
        doc.close()


def _extract_pages_pypdf(data: bytes) -> list[str]:
    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted and not reader.decrypt(""):
        raise ParseError("PDF terkunci kata sandi; buka kuncinya lalu unggah ulang")
    pages = []
    for i, page in enumerate(reader.pages):
        if i >= MAX_PAGES:
            break
        pages.append((page.extract_text() or "").replace("\x00", ""))
    return pages


def extract_pdf_text(data: bytes) -> PdfText:
    if len(data) > MAX_PDF_BYTES:
        raise ParseError("Berkas terlalu besar (maks 15 MB)", 413)
    if not data.lstrip()[:5] == b"%PDF-":
        raise ParseError("Berkas bukan PDF")

    raw_pages: list[str] | None = None
    failure: Exception | None = None
    if pymupdf is not None:
        try:
            raw_pages = _extract_pages_pymupdf(data)
        except ParseError:
            raise
        except (PdfReadError, ValueError, KeyError, OSError, RuntimeError) as exc:
            failure = exc

    if raw_pages is None:
        try:
            raw_pages = _extract_pages_pypdf(data)
        except ParseError:
            raise
        except (PdfReadError, ValueError, KeyError, OSError, RuntimeError) as exc:
            failure = exc

    if raw_pages is not None and sum(len(p) for p in raw_pages) < MIN_TEXT_CHARS:
        try:
            alternate = _extract_pages_pypdf(data)
        except (ParseError, PdfReadError, ValueError, KeyError, OSError, RuntimeError):
            alternate = None
        if alternate and sum(len(p) for p in alternate) > sum(len(p) for p in raw_pages):
            raw_pages = alternate

    if raw_pages is None:
        raise ParseError(f"PDF tidak dapat dibaca ({type(failure).__name__ if failure else 'unknown'})")

    pages = _strip_running_lines([_clean_page_text(p) for p in raw_pages])
    text = PdfText(pages, empty_pages=sum(1 for p in pages if not p))
    if text.chars < MIN_TEXT_CHARS:
        raise ParseError("PDF hampir tidak berisi teks (kemungkinan hasil pindai). OCR belum didukung; unggah PDF berteks.")
    return text


def _score_page(page: str) -> int:
    return sum(len(rx.findall(page)) * weight for rx, weight in _PAGE_PATTERNS)


def select_relevant(text: PdfText, budget: int = TEXT_BUDGET) -> tuple[str, int]:
    """Pilih halaman terpadat aturan pedoman, tetap berurutan; halaman 1-2 dan daftar isi selalu ikut."""
    scored = [(score, i) for i, page in enumerate(text.pages) if (score := _score_page(page)) > 0]
    chosen: set[int] = {i for i in range(min(2, len(text.pages))) if text.pages[i]}
    if any(re.search(r"\.{3,}\s*\d{1,4}\s*$", p, re.M) for p in text.pages[:12]):
        for i in range(min(12, len(text.pages))):
            if not re.search(r"\bdaftar\s+isi\b", text.pages[i], re.I):
                continue
            chosen.add(i)
            for j in (i + 1, i + 2):
                if j < len(text.pages) and re.search(r"\.{3,}\s*\d{1,4}\s*$|\bBAB\s+[IVXLC\d]+\b", text.pages[j]):
                    chosen.add(j)
    used = sum(len(text.pages[i]) for i in chosen)
    for score, i in sorted(scored, reverse=True):
        if i in chosen:
            continue
        if used + len(text.pages[i]) > budget:
            continue
        chosen.add(i)
        used += len(text.pages[i])
    body = "\n\n".join(f"[hal. {i + 1}]\n{text.pages[i]}" for i in sorted(chosen) if text.pages[i])
    return body[: budget + 4000], len(chosen)


def _to_int(value) -> int | None:
    if value is None:
        return None
    raw = str(value).strip().upper()
    if raw.isdigit():
        return int(raw)
    if raw and all(ch in _ROMAN for ch in raw):
        total = prev = 0
        for ch in reversed(raw):
            val = _ROMAN[ch]
            if val < prev:
                total -= val
            else:
                total += val
                prev = val
        return total or None
    return None


def _clean_title(raw) -> str:
    title = re.sub(r"\s+", " ", str(raw or "")).strip()
    title = re.sub(r"[.\s]{2,}\d{1,4}\s*$", "", title)
    return title.strip(" .;:–—-")[:140]


def _toc_clean(line: str) -> str:
    line = re.sub(r"\s*\.{2,}.*$", "", line)
    line = re.sub(r"\s{2,}\d{1,4}\s*$", "", line)
    return line.strip(" .:-–—")


def _sub_key(title) -> str:
    key = normalize(str(title or ""))
    key = re.sub(r"\bdefenisi\b", "definisi", key)
    return re.sub(r"\bkesimpulan\b", "simpulan", key)


def _append_sub(subs: list[dict], title: str) -> None:
    key = _sub_key(title)
    if not key:
        return
    tokens = {t for t in key.split() if len(t) >= 3}
    for idx, existing in enumerate(subs):
        other = _sub_key(existing.get("title") if isinstance(existing, dict) else existing)
        if not other:
            continue
        other_tokens = {t for t in other.split() if len(t) >= 3}
        subset = bool(tokens and other_tokens and (tokens <= other_tokens or other_tokens <= tokens))
        smaller = tokens if len(tokens) <= len(other_tokens) else other_tokens
        if subset and not (len(smaller) >= 2 or any(len(t) >= 6 for t in smaller)):
            subset = False
        if key == other or (min(len(key), len(other)) >= 6 and (key in other or other in key)) or subset:
            if len(key) > len(other):
                base = dict(existing) if isinstance(existing, dict) else {}
                base["title"] = title
                subs[idx] = base
            return
    subs.append({"title": title})


def _chapter_sub_from_inline(rest: str) -> tuple[str, list[str]]:
    first = re.search(r"\b(\d{1,2}\.\d{1,2})(?:\.\d{1,2})?\s+", rest)
    if not first:
        return rest, []
    title = rest[: first.start()]
    subs = []
    for part in re.split(r"[,;]\s*(?=\d{1,2}\.\d{1,2}\s)", rest[first.start():]):
        m = _SUB_NUM_RE.match(part.strip())
        if m:
            subs.append(_clean_title(m.group(4)))
    return title, [s for s in subs if s]


def extract_outline(source: list[str] | str) -> list[dict]:
    pages = [source] if isinstance(source, str) else source
    chapters: dict[int, dict] = {}
    current: int | None = None
    # Pedoman sering memuat sistematika yang sama berkali-kali (daftar isi, bab isi, lalu contoh untuk tiap desain
    # penelitian). Kemunculan pertama yang sudah memuat subbab dianggap resmi; sisanya tidak boleh ditambahkan,
    # kalau tidak subbab dari desain lain ikut menumpuk (mis. 1.6-1.8 dan 3.9-3.14 pada pedoman Unimed).
    locked: set[int] = set()

    def leave() -> None:
        if current is not None and len(chapters.get(current, {}).get("sub_sections", [])) >= 2:
            locked.add(current)

    for page in pages:
        blocks = re.split(r"(?=\bBAB\s+[IVXLC\d]+\b)", page or "")
        for raw_line in "\n".join(blocks).split("\n"):
            line = _toc_clean(raw_line)
            if not line:
                continue
            if _BACKMATTER.match(line):
                leave()
                current = None
                continue

            chapter = _CHAPTER_RE.match(line)
            if chapter:
                number = _to_int(chapter.group(1))
                title, inline_subs = _chapter_sub_from_inline(chapter.group(2))
                title = _clean_title(title)
                if not number or not title:
                    continue
                entry = chapters.setdefault(
                    number, {"chapter_number": number, "chapter_title": title, "sub_sections": []}
                )
                leave()
                if number not in locked:
                    for sub in inline_subs:
                        _append_sub(entry["sub_sections"], sub)
                current = number
                continue

            if _TOP_STOP_RE.match(line) and not _CHAPTER_RE.match(line):
                leave()
                current = None
                continue
            if current is None or len(raw_line) > 100 or raw_line.rstrip().endswith((".", ",", ";")):
                continue

            sub = None
            numeric = _SUB_NUM_RE.match(line)
            if numeric:
                sub = _clean_title(numeric.group(4))
            elif _SUB_PAREN_RE.match(line):
                sub = _clean_title(_SUB_PAREN_RE.match(line).group(1))  # type: ignore[union-attr]
            elif _SUB_LETTER_RE.match(line):
                sub = _clean_title(_SUB_LETTER_RE.match(line).group(2))  # type: ignore[union-attr]
            if not sub or _BACKMATTER.match(sub) or not sub[0].isupper() or normalize(sub) in {"hasil", "data", "isi"}:
                continue
            entry = chapters.get(current)
            if entry is None or current in locked:
                continue
            _append_sub(entry["sub_sections"], sub)

    ordered = [chapters[n] for n in sorted(chapters)][:12]
    for chapter in ordered:
        chapter["sub_sections"] = chapter["sub_sections"][:15]
    return ordered


def _outline_hint(outline: list[dict]) -> str:
    lines = []
    for chapter in outline:
        lines.append(f"BAB {chapter['chapter_number']} {chapter['chapter_title']}")
        for sub in chapter["sub_sections"]:
            lines.append(f"  - {sub['title']}")
    return "\n".join(lines)


def _line_at(text: str, pos: int) -> str:
    start = text.rfind("\n", 0, pos) + 1
    end = text.find("\n", pos)
    return re.sub(r"\s+", " ", text[start : end if end >= 0 else len(text)]).strip()[:300]


def _clauses(text: str):
    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if not line:
            continue
        for part in re.split(r"[;,]|\.\s+(?=[A-Z])", line):
            part = part.strip(" .:-")
            if part:
                yield part


def _extract_margins(text: str) -> dict[str, dict]:
    found: dict[str, dict] = {}
    for clause in _clauses(text):
        low = clause.lower()
        if re.search(r"\d+(?:[.,]\d+)?\s*cm\s*[x×]\s*\d+", low):
            continue
        sides = [side for side in _SIDES if re.search(rf"\b{_SIDE_WORDS[side]}\b", low)]
        if not sides:
            continue
        numbers = re.findall(r"(\d+(?:[.,]\d+)?)\s*cm", low)
        if not numbers:
            continue
        for side in sides:
            if side in found:
                continue
            m = re.search(rf"\b{_SIDE_WORDS[side]}\b[^0-9]{{0,40}}?(\d+(?:[.,]\d+)?)\s*cm", low)
            value = float((m.group(1) if m else numbers[0]).replace(",", "."))
            if 1.0 <= value <= 6.0:
                found[side] = {"value": value, "quote": clause[:300]}
    return found


def _context_score(low: str) -> int:
    score = 0
    if re.search(r"\b(?:naskah|isi|skripsi|pengetikan|pencetakan|diketik|ketik)\b", low):
        score += 3
    if re.search(r"\b(?:judul|sampul|abstrak|prakata|daftar|tabel|gambar|bagan|kutipan|riwayat|lampiran)\b", low):
        score -= 3
    return score


def _extract_font(text: str) -> tuple[dict | None, dict | None]:
    family: tuple[int, dict] | None = None
    size: tuple[int, dict] | None = None
    for line in text.splitlines():
        low = line.lower()
        plain = re.sub(r"\s+", " ", line).strip()[:300]
        score = _context_score(low)
        m = re.search(r"(times\s+new(?:s)?\s+roman|arial|calibri|cambria|bookman\s+old\s+style|tahoma|verdana|georgia)", low)
        if m and (family is None or score > family[0]):
            name = "Times New Roman" if m.group(1).startswith("times") else m.group(1).title()
            family = (score, {"value": name, "quote": plain})
        m = re.search(r"(?:huruf|font|ukuran)[^.\n]{0,60}?(\d{1,2})\s*(?:pt|poin|point)?\b", low)
        if m and 8 <= int(m.group(1)) <= 16 and (size is None or score > size[0]):
            size = (score, {"value": int(m.group(1)), "quote": plain})
    return (family[1] if family else None), (size[1] if size else None)


def _extract_spacing(text: str) -> dict | None:
    best: tuple[int, dict] | None = None
    for line in text.splitlines():
        plain = re.sub(r"\s+", " ", line).strip()
        low = plain.lower()
        value = None
        m = re.search(r"(?:spasi|jarak(?:\s+antar\s*baris)?)\s*:?\s*(\d+(?:[.,]\d+)?)(?:\s*spasi)?", low)
        if m:
            value = float(m.group(1).replace(",", "."))
        elif re.search(r"\bspasi\s+(?:tunggal|satu)\b", low):
            value = 1.0
        elif re.search(r"\bspasi\s+(?:ganda|dua)\b", low):
            value = 2.0
        else:
            m = re.search(r"line\s*spacing\s*=\s*(\d+(?:[.,]\d+)?)", low)
            if m:
                value = float(m.group(1).replace(",", "."))
        if value is None or not (1.0 <= value <= 3.0):
            continue
        score = _context_score(low)
        if value == 1.0 and re.search(r"\b(?:abstrak|abstract|ringkasan|250\s+kata)\b", low):
            score -= 3
        if re.search(r"\b(?:menjorok|kutipan|riwayat\s+hidup)\b", low):
            score -= 3
        if re.search(r"\b(?:jarak\s+spasi|spasi\s+baris|jarak\s+baris)\s*:", low):
            score += 6
        elif re.search(r"line\s+spacing", low):
            score += 1
        if best is None or score > best[0]:
            best = (score, {"value": value, "quote": plain[:300]})
    return best[1] if best else None


def _extract_indent(text: str) -> dict | None:
    for line in text.splitlines():
        m = re.search(r"(?:menjorok|indentasi|indent|awal\s+paragraf|paragraf\s+baru)[^.\n]{0,60}?(\d+(?:[.,]\d+)?)\s*cm", line, re.I)
        if not m:
            continue
        value = float(m.group(1).replace(",", "."))
        if 0.0 <= value <= 3.0:
            return {"value": value, "quote": re.sub(r"\s+", " ", line).strip()[:300]}
    return None


def _extract_paper(text: str) -> dict | None:
    for line in text.splitlines():
        low = line.lower()
        if re.search(r"\b(?:a4|a-4|kuarto|quarto)\b", low):
            return {"value": "A4", "quote": re.sub(r"\s+", " ", line).strip()[:300]}
        if re.search(r"\b(?:f4|folio)\b", low):
            return {"value": "F4", "quote": re.sub(r"\s+", " ", line).strip()[:300]}
        if re.search(r"\bletter\b", low):
            return {"value": "LETTER", "quote": re.sub(r"\s+", " ", line).strip()[:300]}
    return None


def _extract_citation(text: str) -> dict | None:
    for line in text.splitlines():
        if re.search(r"\bAPA\b|American\s+Psychological\s+Association", line):
            return {"value": "APA_7TH", "quote": re.sub(r"\s+", " ", line).strip()[:300]}
        if re.search(r"\bIEEE\b", line):
            return {"value": "IEEE", "quote": re.sub(r"\s+", " ", line).strip()[:300]}
        if re.search(r"\bHarvard\b", line, re.I):
            return {"value": "HARVARD", "quote": re.sub(r"\s+", " ", line).strip()[:300]}
        if re.search(r"\bChicago\b", line, re.I):
            return {"value": "CHICAGO", "quote": re.sub(r"\s+", " ", line).strip()[:300]}
    return None


def _extract_degree(text: str) -> dict | None:
    for line in text.splitlines():
        if re.search(r"\bS-?2\b|\bstrata\s+dua\b|\bmagister\b", line, re.I):
            return {"value": "S2", "quote": re.sub(r"\s+", " ", line).strip()[:300]}
        if re.search(r"\bS-?1\b|\bstrata\s+satu\b|\bsarjana\b", line, re.I):
            return {"value": "S1", "quote": re.sub(r"\s+", " ", line).strip()[:300]}
    return None


def _extract_campus(text: str) -> dict | None:
    pattern = re.compile(
        r"\b(?:Universitas|Institut|Politeknik|Sekolah\s+Tinggi|STMIK|STIE|STIKOM|UIN|IAIN)\b[^\n]{0,110}",
        re.I,
    )
    for match in pattern.finditer(text):
        plain = re.split(
            r"\b(?:Fakultas|Program\s+Studi|Pedoman|Jl\.|Jalan|Spasi|NIM|OLEH|PROGRAM|JURUSAN)\b",
            match.group(0),
            maxsplit=1,
            flags=re.I,
        )[0]
        plain = re.sub(r"\s+", " ", plain).strip(" .,-")
        if plain.isupper():
            plain = plain.title()
        if 12 <= len(plain) <= 120 and not re.search(r"\b(?:sampai|dengan|yang|dan|adalah)\b", plain, re.I):
            return {"value": plain, "quote": plain[:300]}
    return None


def extract_rules(text: str) -> dict:
    family, size = _extract_font(text)
    return {
        "margins": _extract_margins(text),
        "font_family": family,
        "font_size_pt": size,
        "line_spacing": _extract_spacing(text),
        "paragraph_indent_cm": _extract_indent(text),
        "paper_size": _extract_paper(text),
        "citation_style": _extract_citation(text),
        "degree_level": _extract_degree(text),
        "campus_name": _extract_campus(text),
    }


SYSTEM = (
    "Kamu mengekstrak aturan penulisan skripsi dari teks pedoman kampus berbahasa Indonesia menjadi JSON.\n"
    "Aturan: isi HANYA nilai yang tertulis eksplisit di teks. Bila tidak tertulis, isi null. Jangan menebak atau "
    "memakai kebiasaan umum. Semua ukuran dalam cm (margin) dan pt (huruf).\n"
    "Pedoman bisa memakai berbagai gaya penomoran: BAB I, Bab 1, a. Bab 1, subbab 1.1, 1), A., atau a. "
    "Petakan semuanya ke skema di bawah.\n"
    "PENTING untuk \"chapters\": tulis SEMUA bab isi (pendahuluan sampai simpulan) beserta SEMUA subbab yang "
    "tercantum di daftar isi/sistematika. Jangan berhenti di tengah karena jawaban panjang; ringkas judul bila "
    "perlu, tetapi jangan hilangkan bab/subbab. Jangan masukkan sampul, pengesahan, abstrak, daftar isi, daftar "
    "rujukan, atau lampiran sebagai bab.\n"
    "Untuk tiap kelompok data, sertakan kutipan PERSIS (maks 200 karakter) dari teks pada objek \"evidence\".\n"
    "Tanggapi HANYA JSON dengan bentuk:\n"
    '{"campus_name":str|null,"faculty":str|null,"degree_level":"S1"|"S2"|null,'
    '"page_setup":{"paper_size":str|null,"margins_cm":{"top":num|null,"left":num|null,"bottom":num|null,"right":num|null},'
    '"font_family":str|null,"font_size_pt":num|null,"line_spacing":num|null,"paragraph_indent_cm":num|null},'
    '"cover":{"logo_cm":num|null,"title_pt":num|null,"caps":bool|null},'
    '"citation_style":"APA_7TH"|"IEEE"|"CHICAGO"|"HARVARD"|null,'
    '"chapters":[{"chapter_number":str,"chapter_title":str,"sub_sections":[{"code":str,"title":str,"target_words":int|null}]}],'
    '"evidence":{"margins":str|null,"font":str|null,"spacing":str|null,"citation":str|null,"chapters":str|null,"cover":str|null}}\n'
    "chapter_number: gunakan nomor asli dari pedoman (I, II, 1, 2, ...). target_words: isi hanya bila pedoman "
    "menyebut jumlah kata eksplisit; bila tidak, null. Untuk \"cover\": isi hanya bila pedoman menyebut ukuran logo (cm), "
    "ukuran huruf judul sampul (pt), atau kewajiban huruf kapital pada judul sampul; sertakan kutipannya di evidence.cover."
)


async def ask_llm(text: str, outline_hint: str = "") -> tuple[dict, str]:
    hint = f"\n\nSistematika yang terdeteksi otomatis (acuan; lengkapi dari teks):\n{outline_hint}" if outline_hint else ""
    user = f"Teks pedoman (potongan halaman yang relevan):\n\n{text}{hint}"
    convo = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
    last = "tidak ada jawaban"
    for _ in range(2):
        raw, provider = await llm_chat_ex(convo, tier="heavy", temperature=0.1, max_tokens=MAX_LLM_TOKENS)
        try:
            data = extract_json(raw)
            if isinstance(data, dict):
                return data, provider
            last = "JSON bukan objek"
        except ValueError as exc:
            last = f"JSON tidak valid ({exc})"
        convo = convo + [
            {"role": "assistant", "content": raw},
            {"role": "user", "content": "Jawabanmu bukan JSON valid. Balas HANYA dengan satu objek JSON sesuai bentuk."},
        ]
    raise LLMUnavailable(f"LLM tidak menghasilkan JSON pedoman yang valid: {last}")


def _num(v, lo: float, hi: float) -> float | None:
    try:
        x = float(str(v).replace(",", ".")) if v is not None else None
    except ValueError:
        return None
    return x if x is not None and lo <= x <= hi else None


def sanitize_cover(raw) -> dict:
    """Aturan sampul dari klien/templat: nilai di luar batas dibuang, sisanya bawaan."""
    out = dict(DEFAULT_COVER)
    if not isinstance(raw, dict):
        return out
    logo, tpt, bpt = _num(raw.get("logo_cm"), 1.0, 8.0), _num(raw.get("title_pt"), 10.0, 20.0), _num(raw.get("body_pt"), 10.0, 14.0)
    if logo is not None:
        out["logo_cm"] = round(logo, 1)
    if tpt is not None:
        out["title_pt"] = int(round(tpt))
    if bpt is not None:
        out["body_pt"] = int(round(bpt))
    for k in ("caps", "title_page", "approval", "originality"):
        if isinstance(raw.get(k), bool):
            out[k] = raw[k]
    return out


def _merge_raw_chapters(llm_raw, outline: list[dict]) -> list[dict]:
    llm: list[dict] = []
    if isinstance(llm_raw, list):
        for idx, chapter in enumerate(llm_raw[:12], start=1):
            if not isinstance(chapter, dict):
                continue
            title = _clean_title(chapter.get("chapter_title"))
            if not title or _BACKMATTER.match(title):
                continue
            number = _to_int(chapter.get("chapter_number")) or idx
            subs = chapter.get("sub_sections") if isinstance(chapter.get("sub_sections"), list) else []
            llm.append({"chapter_number": number, "chapter_title": title, "sub_sections": list(subs)})

    numbers = [c["chapter_number"] for c in llm]
    if len(set(numbers)) != len(numbers):
        for idx, chapter in enumerate(llm, start=1):
            chapter["chapter_number"] = idx

    if not outline:
        return llm
    if not llm:
        return outline

    by_number = {c["chapter_number"]: c for c in llm}
    merged: list[dict] = []
    present: set[int] = set()
    for chapter in outline:
        number = chapter["chapter_number"]
        if number > 12:
            continue
        present.add(number)
        target = by_number.get(number)
        if target is None:
            merged.append(chapter)
            continue
        subs: list = []
        if chapter["sub_sections"]:
            llm_subs = {
                _sub_key(sub.get("title")): sub
                for sub in (target.get("sub_sections") or [])
                if isinstance(sub, dict)
            }
            for sub in chapter["sub_sections"]:
                item = dict(sub) if isinstance(sub, dict) else {"title": sub}
                match = llm_subs.get(_sub_key(item.get("title")))
                if match and match.get("target_words"):
                    item["target_words"] = match["target_words"]
                subs.append(item)
        else:
            subs = list(target.get("sub_sections") or [])
        merged.append(
            {
                "chapter_number": number,
                "chapter_title": target.get("chapter_title") or chapter["chapter_title"],
                "sub_sections": subs,
            }
        )
    for chapter in llm:
        if chapter["chapter_number"] not in present:
            merged.append(chapter)
    merged.sort(key=lambda c: c["chapter_number"])
    return merged


def _clean_chapters(raw) -> list[dict]:
    out = []
    if not isinstance(raw, list):
        return out
    for idx, ch in enumerate(raw[:12], start=1):
        if not isinstance(ch, dict):
            continue
        title = re.sub(r"\s+", " ", str(ch.get("chapter_title") or "")).strip()[:120]
        if not title or _BACKMATTER.match(title):
            continue
        number = str(idx)
        subs = []
        seen: set[str] = set()
        for sub in (ch.get("sub_sections") or [])[:15]:
            if isinstance(sub, dict):
                source = sub.get("title")
            else:
                source = sub
            st = re.sub(r"\s+", " ", str(source or "")).strip()[:140]
            key = _sub_key(st)
            if not st or not key or key in seen or _BACKMATTER.match(st):
                continue
            seen.add(key)
            words = _num(sub.get("target_words"), 50, 4000) if isinstance(sub, dict) else None
            entry = {"code": f"{number}.{len(subs) + 1}", "title": st, "target_words": int(words) if words else 400}
            en = re.sub(r"\s+", " ", str(sub.get("title_en") or "")).strip()[:140] if isinstance(sub, dict) else ""
            if en:
                entry["title_en"] = en
            subs.append(entry)
        chapter = {"chapter_number": number, "chapter_title": title, "sub_sections": subs}
        ch_en = re.sub(r"\s+", " ", str(ch.get("chapter_title_en") or "")).strip()[:120]
        if ch_en:
            chapter["chapter_title_en"] = ch_en
        out.append(chapter)
    return out


def _verified(quote, source_norm: str) -> dict | None:
    if not quote or not isinstance(quote, str):
        return None
    q = quote.strip()[:300]
    qn = normalize(q)
    return {"quote": q, "verified": bool(qn) and qn in source_norm}


def build_template(
    extracted: dict,
    source_text: str,
    filename: str,
    degree_hint: str = "S1",
    method_hint: str = "KUANTITATIF",
    outline: list[dict] | None = None,
) -> tuple[dict, dict]:
    """Validasi hasil LLM -> (templat, laporan). Tidak pernah melempar karena nilai jelek; nilai jelek = bawaan + peringatan."""
    extracted_fields: list[str] = []
    defaulted: list[str] = []
    warnings: list[str] = []

    rules = extract_rules(source_text)
    outline = extract_outline(source_text) if outline is None else outline

    ps_in = extracted.get("page_setup") if isinstance(extracted.get("page_setup"), dict) else {}
    margins_in = ps_in.get("margins_cm") if isinstance(ps_in.get("margins_cm"), dict) else {}
    margins = {}
    for side in _SIDES:
        val = _num(margins_in.get(side), 1.0, 6.0)
        rule = rules["margins"].get(side)
        if val is None and rule:
            val = rule["value"]
        if val is None:
            margins[side] = DEFAULT_PAGE_SETUP["margins_cm"][side]
            defaulted.append(f"margin {side}")
            continue
        if rule and abs(val - rule["value"]) > 0.05:
            warnings.append(
                f"Margin {side}: LLM membaca {val:g} cm, teks pedoman menyebut {rule['value']:g} cm. Nilai LLM dipakai; periksa manual."
            )
        margins[side] = round(val, 2)
        extracted_fields.append(f"margin {side}")

    def pick(key: str, label: str, lo: float, hi: float, default):
        val = _num(ps_in.get(key), lo, hi)
        rule = rules.get(key)
        if val is None and rule:
            val = rule["value"]
        if val is None:
            defaulted.append(label)
            return default
        extracted_fields.append(label)
        return val

    font_family = str(ps_in.get("font_family") or "").strip()[:60]
    if font_family and len(font_family) >= 3:
        extracted_fields.append("jenis huruf")
    elif rules["font_family"]:
        font_family = rules["font_family"]["value"]
        extracted_fields.append("jenis huruf")
    else:
        font_family = DEFAULT_PAGE_SETUP["font_family"]
        defaulted.append("jenis huruf")
    font_size = pick("font_size_pt", "ukuran huruf", 8, 16, DEFAULT_PAGE_SETUP["font_size_pt"])
    spacing = pick("line_spacing", "spasi baris", 1.0, 3.0, DEFAULT_PAGE_SETUP["line_spacing"])
    indent = pick("paragraph_indent_cm", "indentasi paragraf", 0.0, 3.0, DEFAULT_PAGE_SETUP["paragraph_indent_cm"])

    paper = str(ps_in.get("paper_size") or "").strip().upper()
    if not paper and rules["paper_size"]:
        paper = rules["paper_size"]["value"]
    paper = paper or "A4"
    if paper != "A4":
        warnings.append(f"Ukuran kertas '{paper}' terbaca, tetapi ekspor DOCX saat ini hanya mendukung A4.")
    else:
        extracted_fields.append("ukuran kertas") if (ps_in.get("paper_size") or rules["paper_size"]) else defaulted.append("ukuran kertas")

    style = str(extracted.get("citation_style") or "").strip().upper()
    from_llm = style in CITATION_STYLES
    if not from_llm and rules["citation_style"] and rules["citation_style"]["value"] in CITATION_STYLES:
        style = rules["citation_style"]["value"]
        from_llm = True
    if from_llm:
        extracted_fields.append("gaya sitasi")
    else:
        style = "APA_7TH"
        defaulted.append("gaya sitasi")

    merged = _merge_raw_chapters(extracted.get("chapters"), outline)
    chapters = _clean_chapters(merged)
    if len(chapters) >= 3:
        empty = [c for c in chapters if not c["sub_sections"]]
        for c in empty:
            c["sub_sections"] = [{"code": f"{c['chapter_number']}.1", "title": c["chapter_title"].title(), "target_words": 800}]
        if empty:
            warnings.append(f"{len(empty)} bab tanpa subbab di pedoman: dibuat satu subbab setara judul babnya.")
        extracted_fields.append("sistematika bab")
    else:
        base = CAMPUS_TEMPLATES[suggest_template_id(method_hint, degree_hint)]
        chapters = [
            {"chapter_number": c["chapter_number"], "chapter_title": c["chapter_title"], "sub_sections": [dict(s) for s in c["sub_sections"]]}
            for c in base["chapters"]
        ]
        defaulted.append("sistematika bab")
        warnings.append("Sistematika bab tidak terbaca jelas dari pedoman; dipakai kerangka nasional. Periksa dan sesuaikan.")

    degree = str(extracted.get("degree_level") or "").strip().upper()
    if degree not in ("S1", "S2") and rules["degree_level"]:
        degree = rules["degree_level"]["value"]
    if degree not in ("S1", "S2"):
        degree = degree_hint if degree_hint in ("S1", "S2") else "S1"
    name = re.sub(r"\s+", " ", str(extracted.get("campus_name") or "")).strip()[:120]
    if not name and rules["campus_name"]:
        name = rules["campus_name"]["value"]
    if not name:
        name = re.sub(r"[_\-]+", " ", re.sub(r"\.pdf$", "", filename, flags=re.IGNORECASE)).strip()[:120] or "Templat kampus"
        defaulted.append("nama kampus")
    else:
        extracted_fields.append("nama kampus")

    source_norm = normalize(source_text)
    ev_in = extracted.get("evidence") if isinstance(extracted.get("evidence"), dict) else {}
    evidence = {k: v for k in ("margins", "font", "spacing", "citation", "chapters", "cover") if (v := _verified(ev_in.get(k), source_norm))}
    if not from_llm:
        evidence.pop("citation", None)
    if len(outline) >= 3:
        evidence.pop("chapters", None)
    rule_quotes = {
        "margins": next((r["quote"] for r in rules["margins"].values() if r), ""),
        "font": (rules["font_family"] or {}).get("quote", ""),
        "spacing": (rules["line_spacing"] or {}).get("quote", ""),
        "citation": (rules["citation_style"] or {}).get("quote", ""),
    }
    for key, quote in rule_quotes.items():
        if key not in evidence and quote:
            verified = _verified(quote, source_norm)
            if verified:
                evidence[key] = verified
    for k, v in evidence.items():
        if not v["verified"]:
            warnings.append(f"Kutipan bukti untuk '{k}' tidak ditemukan persis di teks PDF; periksa nilainya secara manual.")

    cover = dict(DEFAULT_COVER)
    cv_in = extracted.get("cover") if isinstance(extracted.get("cover"), dict) else {}
    if evidence.get("cover", {}).get("verified"):  # nilai sampul dipakai hanya bila kutipan buktinya ada persis di teks pedoman
        logo = _num(cv_in.get("logo_cm"), 1.0, 8.0)
        title_pt = _num(cv_in.get("title_pt"), 10.0, 20.0)
        if logo is not None:
            cover["logo_cm"] = round(logo, 1)
        if title_pt is not None:
            cover["title_pt"] = int(round(title_pt))
        if isinstance(cv_in.get("caps"), bool):
            cover["caps"] = cv_in["caps"]
        if logo is not None or title_pt is not None or isinstance(cv_in.get("caps"), bool):
            extracted_fields.append("aturan sampul")

    template = {
        "campus_name": name,
        "faculty": re.sub(r"\s+", " ", str(extracted.get("faculty") or "")).strip()[:120] or "Umum",
        "degree_level": degree,
        "page_setup": {
            "paper_size": "A4",
            "margins_cm": margins,
            "font_family": font_family,
            "font_size_pt": int(round(font_size)),
            "line_spacing": round(float(spacing), 2),
            "paragraph_indent_cm": round(float(indent), 2),
        },
        "cover": cover,
        "citation_style": style,
        "research_method": method_hint,
        "chapters": chapters,
    }
    report = {"extracted": extracted_fields, "defaulted": defaulted, "warnings": warnings, "evidence": evidence}
    return template, report


TRANSLATE_SYSTEM = (
    "Kamu penerjemah istilah akademik. Terjemahkan judul bab/subbab skripsi berbahasa Indonesia ke bahasa Inggris akademik "
    "yang lazim dipakai pada thesis (mis. 'Asumsi Penelitian' -> 'Research Assumptions'). Pertahankan makna dan keterangan "
    'dalam kurung (mis. "(jika ada)" -> "(if any)"). Tanggapi HANYA JSON: {"translations":{"<judul asli>":"<English title>"}}'
)


async def translate_titles(template: dict) -> list[str]:
    """Isi title_en untuk judul yang belum ada di kamus bawaan agar naskah berbahasa Inggris tidak bercampur bahasa.

    Mengembalikan daftar peringatan; bila LLM gagal judul dibiarkan apa adanya (tidak ada terjemahan karangan)."""
    from app.services.templates import _en_section

    pending: list[str] = []
    for ch in template["chapters"]:
        for item in [ch["chapter_title"], *[x["title"] for x in ch["sub_sections"]]]:
            if _en_section(item) == item and item not in pending:
                pending.append(item)
    if not pending:
        return []
    try:
        raw, _ = await llm_chat_ex(
            [{"role": "system", "content": TRANSLATE_SYSTEM}, {"role": "user", "content": chr(10).join(f"- {t}" for t in pending)}],
            tier="fast",
            temperature=0.1,
            max_tokens=1500,
        )
        mapping = extract_json(raw).get("translations") or {}
    except Exception as exc:
        return [f"Judul versi Inggris tidak dapat dibuat otomatis ({exc}); naskah berbahasa Inggris akan memakai judul Indonesia untuk: {', '.join(pending[:6])}."]
    for ch in template["chapters"]:
        if ch["chapter_title"] in mapping and isinstance(mapping[ch["chapter_title"]], str):
            ch["chapter_title_en"] = re.sub(r"\s+", " ", mapping[ch["chapter_title"]]).strip()[:120].upper()
        for x in ch["sub_sections"]:
            v = mapping.get(x["title"])
            if isinstance(v, str) and v.strip():
                x["title_en"] = re.sub(r"\s+", " ", v).strip()[:140]
    return []


async def parse_guideline(data: bytes, filename: str, degree_hint: str = "S1", method_hint: str = "KUANTITATIF") -> dict:
    text = await asyncio.to_thread(extract_pdf_text, data)
    selected, pages_used = select_relevant(text)
    outline = extract_outline(text.pages)
    extracted, provider = await ask_llm(selected, _outline_hint(outline))
    template, report = build_template(extracted, selected, filename, degree_hint, method_hint, outline=outline)
    report["warnings"].extend(await translate_titles(template))
    if text.empty_pages:
        report["warnings"].insert(
            0,
            f"{text.empty_pages} halaman tidak berisi teks (kemungkinan gambar/pindai) dan dilewati.",
        )
    report.update({"pages": len(text.pages), "pages_used": pages_used, "empty_pages": text.empty_pages, "provider": provider, "filename": filename})
    return {"template": template, "report": report}
