"""Pemeriksa konsistensi sitasi: sitasi dalam teks vs daftar rujukan terpilih, rujukan yang tak pernah dikutip,
tahun yang tidak cocok, campuran gaya (APA vs IEEE), dan duplikat/kekurangan data pada daftar rujukan.

Murni deterministik (regex dan pencocokan nama belakang + tahun); tidak memakai LLM.
"""

import re

from sqlalchemy.orm import Session

from app.models.models import Citation, Thesis
from app.services.citation import surname_of
from app.services.templates import resolve_template

_YEAR = r"(?:19|20)\d{2}[a-z]?"
# (Penulis, 2021) / (Penulis & Lain, 2021) / (Penulis et al., 2021) / (A, 2020; B, 2021)
_PAREN = re.compile(r"\(([^()]{3,200}?" + _YEAR + r")\)")
# Penulis (2021) / Penulis et al. (2021) / Penulis dan Lain (2021) / Penulis & Lain (2021)
_NARR = re.compile(r"\b([A-Z][\w'’-]+(?:\s+et al\.|\s+(?:&|and|dan)\s+[A-Z][\w'’-]+)?)\s+\((" + _YEAR + r")\)")
_NUM = re.compile(r"\[(\d{1,3}(?:\s*[,–-]\s*\d{1,3})*)\]")
_CONN = re.compile(r"\s(&|and|dan)\s")


def _key(name: str) -> str:
    return re.sub(r"[^a-z]", "", name.lower())


def _first_author(text: str) -> str:
    text = re.sub(r"\bet al\.?", "", text)
    head = re.split(r"\s+(?:&|and|dan)\s+|,", text.strip())[0]
    words = head.split()
    return words[-1] if words else head


def _expand_numbers(raw: str) -> list[int]:
    out = []
    for part in re.split(r"\s*,\s*", raw):
        m = re.fullmatch(r"(\d+)\s*[–-]\s*(\d+)", part)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            out.extend(range(a, min(b, a + 50) + 1))
        elif part.strip().isdigit():
            out.append(int(part))
    return out


def audit(thesis: Thesis, db: Session) -> dict:
    refs = [c for c in db.query(Citation).filter(Citation.thesis_id == thesis.thesis_id).all() if c.citation_id in (thesis.selected_ref_ids or [])]
    style = resolve_template(db, thesis.campus_template_id).get("citation_style", "APA_7TH")
    index: dict[tuple[str, int], Citation] = {}
    by_surname: dict[str, list[Citation]] = {}
    for r in refs:
        s = _key(surname_of((r.authors or ["Anonim"])[0]))
        by_surname.setdefault(s, []).append(r)
        index[(s, int(r.publication_year or 0))] = r

    cited_ids: set[str] = set()
    unknown, mismatch = [], []
    apa_count = num_count = 0
    connectors: dict[str, int] = {}
    numeric_out_of_range = []

    for sec in sorted(thesis.sections, key=lambda x: [int(p) if p.isdigit() else 0 for p in x.section_code.split(".")]):
        text = sec.content_markdown or ""
        if not text.strip():
            continue
        where = {"section": sec.section_code, "title": sec.section_title, "own_writing": sec.origin == "IMPORTED"}
        found: list[tuple[str, str, str]] = []  # (teks, penulis pertama, tahun)
        for m in _PAREN.finditer(text):
            for piece in re.split(r";", m.group(1)):
                y = re.search(_YEAR, piece)
                if not y:
                    continue
                author_part = piece[: y.start()].strip(" ,")
                if author_part and re.match(r"[A-Z]", author_part):
                    found.append((f"({piece.strip()})", _first_author(author_part), y.group(0)))
                    for c in _CONN.findall(author_part):
                        connectors[c] = connectors.get(c, 0) + 1
        for m in _NARR.finditer(text):
            found.append((m.group(0), _first_author(m.group(1)), m.group(2)))
            for c in _CONN.findall(m.group(1)):
                connectors[c] = connectors.get(c, 0) + 1
        apa_count += len(found)
        for shown, author, year in found:
            k, yr = _key(author), int(year[:4])
            if (k, yr) in index:
                cited_ids.add(index[(k, yr)].citation_id)
            elif k in by_surname:
                mismatch.append({**where, "text": shown, "listed_years": sorted({int(r.publication_year or 0) for r in by_surname[k]})})
                for r in by_surname[k]:
                    cited_ids.add(r.citation_id)  # penulisnya jelas dikutip; tahun saja yang salah
            else:
                unknown.append({**where, "text": shown})
        for m in _NUM.finditer(text):
            nums = _expand_numbers(m.group(1))
            num_count += 1
            for n in nums:
                if 1 <= n <= len(refs):
                    if style == "IEEE":
                        cited_ids.add(refs[n - 1].citation_id)
                else:
                    numeric_out_of_range.append({**where, "text": m.group(0), "number": n})

    uncited = [r for r in refs if r.citation_id not in cited_ids]

    dup, seen = [], {}
    for r in refs:
        key = ("doi", (r.doi or "").lower()) if r.doi else ("title", re.sub(r"\W+", " ", (r.title or "").lower()).strip())
        if key in seen:
            dup.append({"title": r.title, "same_as": seen[key].title})
        else:
            seen[key] = r
    weak = {
        "no_authors": [r.title for r in refs if not r.authors or any(str(a).strip().lower() == "anonim" for a in r.authors)],
        "no_year": [r.title for r in refs if not r.publication_year],
        "no_doi": sum(1 for r in refs if not r.doi),
    }

    issues: list[str] = []
    mixed = apa_count > 0 and num_count > 0
    if mixed:
        issues.append(f"Gaya sitasi campur: {apa_count} sitasi gaya penulis-tahun dan {num_count} sitasi bernomor. Pilih satu gaya ({'IEEE' if style == 'IEEE' else 'APA'} sesuai templat).")
    elif style == "IEEE" and apa_count > 0:
        issues.append("Templat memakai IEEE (bernomor) tetapi teks memakai gaya penulis-tahun.")
    elif style != "IEEE" and num_count > 0 and apa_count == 0:
        issues.append("Templat memakai gaya penulis-tahun tetapi teks memakai sitasi bernomor.")
    if len([c for c, n in connectors.items() if n > 0]) > 1:
        issues.append("Kata sambung antar-penulis tidak konsisten: " + ", ".join(f"'{c}' ({n}x)" for c, n in connectors.items()) + ". Gunakan satu bentuk (APA memakai '&' di dalam kurung).")

    return {
        "style": style,
        "references": len(refs),
        "in_text_citations": apa_count + num_count,
        "unknown": unknown[:60],
        "year_mismatch": mismatch[:60],
        "uncited": [{"title": r.title, "authors": (r.authors or ["Anonim"])[:2], "year": r.publication_year} for r in uncited],
        "numeric_out_of_range": numeric_out_of_range[:30],
        "duplicates": dup,
        "weak": weak,
        "style_issues": issues,
        "ok": not (unknown or mismatch or uncited or dup or issues or numeric_out_of_range),
    }
