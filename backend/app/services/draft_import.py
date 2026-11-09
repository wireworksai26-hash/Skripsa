"""Impor naskah skripsi yang sudah ada (DOCX / PDF / teks) menjadi bab dan subbab.

Pemecahan murni berbasis aturan (tanpa LLM): judul bab ("BAB I PENDAHULUAN") dan subbab bernomor ("1.1 Latar Belakang").
Hasilnya selalu berupa pratinjau yang diperiksa pengguna sebelum disimpan; apa yang tidak terbaca dilaporkan sebagai
peringatan, bukan ditebak.
"""

import io
import re
import zipfile
from dataclasses import dataclass, field

from app.services.guideline_parser import ParseError, extract_pdf_text

MAX_BYTES = 10 * 1024 * 1024
MAX_CHARS = 600_000
MAX_DOCX_UNCOMPRESSED = 80 * 1024 * 1024
MAX_DOCX_ENTRY = 20 * 1024 * 1024
_ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10}

_CHAPTER = re.compile(r"^\s*BAB\s+([IVX]{1,5}|\d{1,2})\b[\s.:\-–—]*(.*)$", re.IGNORECASE)
_SECTION = re.compile(r"^\s*(\d{1,2})\.(\d{1,2})\.?\s+(\S.*)$")
_END = re.compile(r"^\s*(DAFTAR\s+PUSTAKA|DAFTAR\s+REFERENSI|REFERENCES|BIBLIOGRAPHY|LAMPIRAN)\s*$", re.IGNORECASE)
_TOC_LEADER = re.compile(r"(\.{2,}|(?:\s\.){2,}|\s{3,})\s*[\divxlcIVXLC]{1,5}\s*$")
_PAGE_NUMBER = re.compile(r"^\s*(?:hal(?:aman)?\.?\s*)?[\divxlc]{1,4}\s*$", re.IGNORECASE)


@dataclass
class ParsedSection:
    code: str
    title: str
    content: str = ""
    implicit: bool = False  # dibuat dari isi bab tanpa subbab bernomor

    @property
    def words(self) -> int:
        return len([w for w in self.content.split() if any(c.isalnum() for c in w)])


@dataclass
class ParsedChapter:
    code: str
    title: str
    sections: list[ParsedSection] = field(default_factory=list)


def _chapter_number(raw: str) -> str:
    raw = raw.upper()
    return str(_ROMAN[raw]) if raw in _ROMAN else str(int(raw))


def extract_text(filename: str, data: bytes) -> tuple[str, bool]:
    """Kembalikan (teks, perlu_reflow). PDF memenggal baris di tengah kalimat sehingga perlu disambung ulang."""
    if len(data) > MAX_BYTES:
        raise ParseError("Berkas terlalu besar (maks 10 MB)", 413)
    name = (filename or "").lower()
    if name.endswith(".docx") or data[:2] == b"PK":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                total = 0
                for info in archive.infolist():
                    if info.is_dir():
                        continue
                    if info.file_size > MAX_DOCX_ENTRY:
                        raise ParseError("Isi .docx terlalu besar setelah dekompresi", 413)
                    with archive.open(info) as member:
                        while chunk := member.read(1024 * 1024):
                            total += len(chunk)
                            if total > MAX_DOCX_UNCOMPRESSED:
                                raise ParseError("Isi .docx terlalu besar setelah dekompresi", 413)
            import docx

            doc = docx.Document(io.BytesIO(data))
        except ParseError:
            raise
        except Exception:
            raise ParseError("Berkas .docx tidak dapat dibaca (rusak atau bukan dokumen Word)")
        return "\n".join(p.text for p in doc.paragraphs), False
    if name.endswith(".pdf") or data.lstrip()[:5] == b"%PDF-":
        pages = extract_pdf_text(data).pages
        return "\n".join(pages), True
    if name.endswith(".doc"):
        raise ParseError("Format .doc lama tidak didukung; simpan sebagai .docx lalu unggah ulang")
    try:
        return data.decode("utf-8-sig"), False
    except UnicodeDecodeError:
        return data.decode("latin-1"), False


def _reflow(lines: list[str]) -> list[str]:
    """Sambung baris PDF yang terpenggal: baris tanpa tanda akhir kalimat disambung ke baris huruf kecil berikutnya."""
    out: list[str] = []
    for line in lines:
        if out and out[-1] and line and not re.search(r"[.!?:;]$", out[-1]) and line[0].islower():
            out[-1] = f"{out[-1]} {line}"
        else:
            out.append(line)
    return out


def _is_section_title(title: str) -> bool:
    t = title.strip()
    return 2 <= len(t) <= 120 and t[0].isalpha() and t[0].isupper() and not re.search(r"[.;,:]$", t) and len(t.split()) <= 14


def _clean_lines(text: str, reflow: bool) -> list[str]:
    lines = [re.sub(r"[ \t ]+", " ", l).strip() for l in text.replace("\r", "").split("\n")]
    lines = [l for l in lines if not _PAGE_NUMBER.match(l) or not l]
    return _reflow(lines) if reflow else lines


def parse_draft(text: str, reflow: bool = False) -> dict:
    text = text[:MAX_CHARS]
    lines = _clean_lines(text, reflow)
    chapters: dict[str, ParsedChapter] = {}
    order: list[str] = []
    warnings: list[str] = []
    current_ch: ParsedChapter | None = None
    current_sec: ParsedSection | None = None
    buffer: list[str] = []
    stopped = False

    def flush():
        nonlocal buffer
        body = "\n".join(l for l in buffer if l).strip()
        buffer = []
        if not body or current_ch is None:
            return
        if current_sec is None:
            sec = ParsedSection(f"{current_ch.code}.1", current_ch.title.title() or f"Bab {current_ch.code}", implicit=True)
            current_ch.sections.append(sec)
            sec.content = body
        else:
            current_sec.content = (current_sec.content + "\n" + body).strip() if current_sec.content else body

    def ensure_chapter(code: str, title: str = "") -> ParsedChapter:
        key = code
        if key not in chapters:
            chapters[key] = ParsedChapter(code, title)
            order.append(key)
        elif title and not chapters[key].title:
            chapters[key].title = title
        return chapters[key]

    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if not line:
            buffer.append("")
            continue
        if _TOC_LEADER.search(line) and (_CHAPTER.match(line) or _SECTION.match(line)):
            continue  # baris daftar isi ("BAB I PENDAHULUAN ........ 1")
        if _END.match(line) and current_ch is not None:
            flush()
            stopped = True
            break
        m = _CHAPTER.match(line)
        if m:
            flush()
            title = m.group(2).strip()
            if not title:  # "BAB I" lalu judulnya di baris berikutnya
                j = i
                while j < len(lines) and not lines[j]:
                    j += 1
                if j < len(lines) and len(lines[j]) <= 80 and not _SECTION.match(lines[j]) and not _CHAPTER.match(lines[j]):
                    title = lines[j]
                    i = j + 1
            current_ch = ensure_chapter(_chapter_number(m.group(1)), title)
            current_sec = None
            continue
        s = _SECTION.match(line)
        if s and _is_section_title(s.group(3)):
            flush()
            code_ch = str(int(s.group(1)))
            current_ch = ensure_chapter(code_ch)
            code = f"{code_ch}.{int(s.group(2))}"
            existing = next((x for x in current_ch.sections if x.code == code), None)
            if existing is None:
                existing = ParsedSection(code, s.group(3).strip())
                current_ch.sections.append(existing)
            current_sec = existing
            continue
        buffer.append(line)
    flush()

    if stopped:
        warnings.append("Bagian setelah DAFTAR PUSTAKA/LAMPIRAN tidak diimpor.")

    result: list[dict] = []
    seen_codes: set[str] = set()
    for key in order:
        ch = chapters[key]
        secs = []
        for sec in ch.sections:
            if sec.words < 5:
                continue  # sisa daftar isi atau judul kosong
            if sec.code in seen_codes:
                warnings.append(f"Subbab {sec.code} muncul lebih dari sekali; yang pertama dipakai.")
                continue
            seen_codes.add(sec.code)
            secs.append({"section_code": sec.code, "title": sec.title, "content": sec.content, "words": sec.words})
        if not secs:
            continue
        if len(ch.sections) == 1 and ch.sections[0].implicit:
            warnings.append(f"BAB {ch.code} tidak punya subbab bernomor; seluruh isinya dijadikan satu subbab ({ch.code}.1).")
        result.append({"chapter_code": ch.code, "chapter_title": ch.title.strip(), "sections": secs})

    if not result:
        raise ParseError(
            "Tidak ditemukan judul bab (mis. 'BAB I PENDAHULUAN') atau subbab bernomor (mis. '1.1 Latar Belakang'). "
            "Pastikan judul ditulis di barisnya sendiri, atau tempel isi per bab."
        )
    total = sum(s["words"] for c in result for s in c["sections"])
    return {"chapters": result, "total_words": total, "warnings": warnings}


def parse_file(filename: str, data: bytes) -> dict:
    text, reflow = extract_text(filename, data)
    if len(text.strip()) < 100:
        raise ParseError("Berkas hampir tidak berisi teks")
    out = parse_draft(text, reflow)
    out["filename"] = filename
    return out
