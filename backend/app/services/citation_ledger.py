"""Buku bukti sitasi: untuk tiap rujukan, di mana dikutip (subbab + kalimatnya) dan bukti grounding-nya
(cuplikan abstrak, DOI, sumber data), supaya saat ditanya "kutipan ini dari mana?" jawabannya satu pencarian.

Dua sumber naskah memakai mesin yang sama:
  * naskah di platform (subbab di database), dan
  * naskah jadi yang diunggah (DOCX/PDF), dicocokkan ke rujukan yang sudah ter-grounding pada proyek.

Murni deterministik (regex + pencocokan nama belakang/tahun/judul); tidak memakai LLM dan tidak pernah mengarang rujukan.
Rujukan yang ada di naskah tetapi tidak ada di grounding dilaporkan apa adanya sebagai belum terverifikasi.
"""

import re

from sqlalchemy.orm import Session

from app.models.models import Citation, Thesis
from app.services import foundational
from app.services.citation import in_text_marker, reference_string, surname_of
from app.services.citation_audit import _CONN, _NARR, _NUM, _PAREN, _YEAR, _expand_numbers, _first_author, _key
from app.services.draft_import import ParseError, extract_text, parse_draft
from app.services.templates import resolve_template

SENTENCE_MAX = 320
_END_HEADING = re.compile(r"^\s*(DAFTAR\s+PUSTAKA|DAFTAR\s+REFERENSI|REFERENCES|BIBLIOGRAPHY|REFERENCE\s+LIST)\s*$", re.IGNORECASE)
_AFTER_BIB = re.compile(r"^\s*(LAMPIRAN|APPENDIX|APPENDICES)\b", re.IGNORECASE)
_ENTRY_START = re.compile(r"^\s*(?:\[\d{1,3}\]|\d{1,3}[.)])\s+|^\s*[^\W\d_][\w'’\-]+(?:\s[^\W\d_][\w'’\-]+)?,\s+[A-Z]\.")


def _sort_code(code: str) -> list[int]:
    return [int(p) if p.isdigit() else 0 for p in code.split(".")]


def sentence_around(text: str, start: int, end: int) -> str:
    """Kalimat yang memuat sitasi (batas: titik/baris kosong), dipangkas bila terlalu panjang."""
    left = max(text.rfind(". ", 0, start), text.rfind("\n", 0, start))
    a = 0 if left < 0 else left + 1
    cuts = [i for i in (text.find(". ", end), text.find("\n", end)) if i >= 0]
    b = (min(cuts) + 1) if cuts else len(text)
    sent = " ".join(text[a:b].split())
    if len(sent) <= SENTENCE_MAX:
        return sent
    rel = start - a
    lo = max(0, min(rel - SENTENCE_MAX // 2, len(sent) - SENTENCE_MAX))
    return ("…" if lo else "") + sent[lo : lo + SENTENCE_MAX].strip() + ("…" if lo + SENTENCE_MAX < len(sent) else "")


def scan(sections: list[dict]) -> list[dict]:
    """Semua sitasi di teks. Tiap hit: {kind, section, title, text, author, year, numbers, sentence}."""
    hits: list[dict] = []
    for sec in sections:
        text = sec.get("content") or ""
        if not text.strip():
            continue
        where = {"section": sec["code"], "title": sec["title"], "own_writing": bool(sec.get("own_writing"))}
        spans: list[tuple[int, int]] = []
        for m in _PAREN.finditer(text):
            for piece in m.group(1).split(";"):
                y = re.search(_YEAR, piece)
                if not y:
                    continue
                author_part = piece[: y.start()].strip(" ,")
                if author_part and re.match(r"[A-Z]", author_part):
                    hits.append({**where, "kind": "author-year", "text": f"({piece.strip()})", "author": _first_author(author_part), "year": y.group(0), "numbers": [], "sentence": sentence_around(text, m.start(), m.end())})
                    spans.append((m.start(), m.end()))
        for m in _NARR.finditer(text):
            if any(a <= m.start() < b for a, b in spans):
                continue
            hits.append({**where, "kind": "author-year", "text": m.group(0), "author": _first_author(m.group(1)), "year": m.group(2), "numbers": [], "sentence": sentence_around(text, m.start(), m.end())})
        for m in _NUM.finditer(text):
            hits.append({**where, "kind": "numeric", "text": m.group(0), "author": "", "year": "", "numbers": _expand_numbers(m.group(1)), "sentence": sentence_around(text, m.start(), m.end())})
    return hits


def split_bibliography(text: str) -> list[str]:
    """Entri daftar pustaka dari naskah yang diunggah: blok sesudah judul 'DAFTAR PUSTAKA' terakhir sampai Lampiran."""
    lines = text.splitlines()
    starts = [i for i, l in enumerate(lines) if _END_HEADING.match(l)]
    if not starts:
        return []
    block: list[str] = []
    for l in lines[starts[-1] + 1 :]:
        if _AFTER_BIB.match(l):
            break
        block.append(l)
    entries: list[str] = []
    for l in block:
        l = l.strip()
        if not l:
            continue
        if not entries or _ENTRY_START.match(l):
            entries.append(l)
        else:  # baris lanjutan (PDF memenggal entri)
            entries[-1] += " " + l
    return [e for e in entries if len(e) >= 25][:600]


def _tidy(text: str) -> str:
    """reference_string memakai tanda hubung panjang bila jurnal tak diketahui; jangan tampilkan sebagai isi."""
    text = re.sub(r"\s—(?=[.,])", "", text)
    return re.sub(r"\.\s*\.", ".", text).strip()


def _ref_view(c: Citation, style: str, number: int) -> dict:
    d = {"authors": c.authors or [], "publication_year": c.publication_year, "title": c.title, "journal_name": c.journal_name, "volume_issue": c.volume_issue, "page_range": c.page_range, "doi": c.doi}
    return {
        "citation_id": c.citation_id,
        "number": number,
        "reference": _tidy(reference_string(d, style)),
        "short": in_text_marker("APA_7TH", d, 0),
        "title": c.title,
        "authors": c.authors or [],
        "year": c.publication_year or 0,
        "journal": c.journal_name or "",
        "doi": c.doi or "",
        "doi_url": f"https://doi.org/{c.doi}" if c.doi else "",
        "pdf_url": c.pdf_url or "",
        "source": c.source_database or "",
        "page": c.page_number or 1,
        "evidence": (c.highlighted_snippet or "").strip(),
        "uses": [],
    }


def _index(refs: list[Citation]):
    by_key: dict[tuple[str, int], Citation] = {}
    by_surname: dict[str, list[Citation]] = {}
    for r in refs:
        s = _key(surname_of((r.authors or ["Anonim"])[0]))
        by_surname.setdefault(s, []).append(r)
        by_key[(s, int(r.publication_year or 0))] = r
    return by_key, by_surname


def build(refs: list[Citation], sections: list[dict], style: str, grounding: dict[tuple[str, str], str] | None = None, numbered: list[Citation | None] | None = None) -> dict:
    """Buku bukti: satu entri per rujukan dengan daftar tempat dikutip. `grounding[(kode_subbab, citation_id)]` = cuplikan
    bukti yang dipakai penulis agen saat menulis subbab itu. `numbered` = urutan rujukan untuk sitasi bernomor."""
    ordered = sorted(refs, key=lambda r: (_key(surname_of((r.authors or ["Anonim"])[0])), r.publication_year or 0, (r.title or "").lower()))
    views = {r.citation_id: _ref_view(r, style, i + 1) for i, r in enumerate(ordered)}
    by_key, by_surname = _index(refs)
    unmatched: dict[str, dict] = {}
    for h in scan(sections):
        targets: list[tuple[Citation, bool]] = []
        if h["kind"] == "numeric":
            targets = [(numbered[n - 1], False) for n in h["numbers"] if numbered and 1 <= n <= len(numbered) and numbered[n - 1] is not None]
            if not targets:
                unmatched.setdefault(h["text"], {"text": h["text"], "uses": []})["uses"].append(_use(h, None, grounding))
                continue
        else:
            k, yr = _key(h["author"]), int(h["year"][:4])
            if (k, yr) in by_key:
                targets = [(by_key[(k, yr)], False)]
            elif k in by_surname:
                targets = [(by_surname[k][0], True)]  # penulis jelas, tahun beda
            else:
                unmatched.setdefault(h["text"], {"text": h["text"], "uses": []})["uses"].append(_use(h, None, grounding))
                continue
        for ref, year_mismatch in targets:
            u = _use(h, ref, grounding)
            u["year_mismatch"] = year_mismatch
            views[ref.citation_id]["uses"].append(u)
    entries = list(views.values())
    for e in entries:
        e["status"] = "cited" if e["uses"] else "uncited"
    return {
        "style": style,
        "entries": entries,
        "unmatched": list(unmatched.values())[:80],
        "totals": {"references": len(entries), "cited": sum(1 for e in entries if e["uses"]), "uncited": sum(1 for e in entries if not e["uses"]), "uses": sum(len(e["uses"]) for e in entries)},
    }


def _use(h: dict, ref: Citation | None, grounding: dict[tuple[str, str], str] | None) -> dict:
    snippet = (grounding or {}).get((h["section"], ref.citation_id)) if ref else None
    return {"section": h["section"], "title": h["title"], "marker": h["text"], "sentence": h["sentence"], "grounded_snippet": snippet or "", "own_writing": h.get("own_writing", False), "year_mismatch": False}


def _thesis_refs(thesis: Thesis, db: Session) -> list[Citation]:
    return db.query(Citation).filter(Citation.thesis_id == thesis.thesis_id).all()


def ledger_for_thesis(thesis: Thesis, db: Session) -> dict:
    """Buku bukti dari subbab di platform; hanya rujukan terpilih (yang masuk daftar pustaka)."""
    style = resolve_template(db, thesis.campus_template_id).get("citation_style", "APA_7TH")
    selected = set(thesis.selected_ref_ids or [])
    all_refs = _thesis_refs(thesis, db)
    refs = [c for c in all_refs if c.citation_id in selected] if selected else all_refs
    sections, grounding = [], {}
    for s in sorted(thesis.sections, key=lambda x: _sort_code(x.section_code)):
        sections.append({"code": s.section_code, "title": s.section_title, "content": s.content_markdown or "", "own_writing": s.origin == "IMPORTED"})
        for c in s.citations_json or []:
            if c.get("reference_id") and c.get("snippet"):
                grounding[(s.section_code, c["reference_id"])] = c["snippet"]
    out = build(refs, sections, style, grounding, numbered=refs)
    out["source"] = "platform"
    return out


def _match_entry(raw: str, refs: list[Citation]) -> tuple[Citation | None, str]:
    """Cocokkan satu baris daftar pustaka naskah ke rujukan ter-grounding: judul utuh termuat (kuat), atau penulis+tahun unik."""
    cr = foundational.compact(raw)
    best: Citation | None = None
    for r in refs:
        ct = foundational.compact(r.title or "")
        if len(ct) >= 12 and ct in cr and (best is None or len(ct) > len(foundational.compact(best.title))):
            best = r
    if best:
        return best, "judul"
    head = foundational.fold(raw[:140])
    cands = [
        r for r in refs
        if r.publication_year and str(r.publication_year) in raw and foundational.fold(surname_of((r.authors or [""])[0])) and foundational.fold(surname_of((r.authors or [""])[0])) in head
    ]
    if len(cands) == 1:
        return cands[0], "penulis-tahun"
    return None, ""


def track_upload(thesis: Thesis, db: Session, filename: str, data: bytes) -> dict:
    """Lacak kutipan di naskah jadi: cocokkan ke grounding proyek, dan laporkan yang tak terlacak."""
    text, reflow = extract_text(filename, data)
    if len(text.strip()) < 100:
        raise ParseError("Berkas hampir tidak berisi teks")
    style = resolve_template(db, thesis.campus_template_id).get("citation_style", "APA_7TH")
    try:
        parsed = parse_draft(text, reflow)
        sections = [{"code": s["section_code"], "title": s["title"], "content": s["content"], "own_writing": True} for c in parsed["chapters"] for s in c["sections"]]
        warnings = [w for w in (parsed.get("warnings") or []) if "tidak diimpor" not in w]  # bagian sesudah Daftar Pustaka memang tidak dipindai
    except ParseError:
        body = text.split("\n")
        sections = [{"code": "-", "title": "Seluruh naskah", "content": "\n".join(body), "own_writing": True}]
        warnings = ["Judul bab tidak terbaca; seluruh naskah dipindai sebagai satu bagian."]

    refs = _thesis_refs(thesis, db)
    bib = split_bibliography(text)
    numbered: list[Citation | None] | None = None
    matched_entries: list[dict] = []
    unmatched_entries: list[str] = []
    entry_map: list[Citation | None] = []
    for raw in bib:
        ref, how = _match_entry(raw, refs)
        entry_map.append(ref)
        if ref:
            matched_entries.append({"raw": raw, "citation_id": ref.citation_id, "by": how})
        else:
            unmatched_entries.append(raw)
    if bib and any(re.match(r"^\s*(\[\d+\]|\d+[.)])\s", b) for b in bib[:5]):
        numbered = entry_map  # [n] = entri ke-n di daftar pustaka naskah; entri tak cocok tetap menjaga urutan

    out = build(refs, sections, style, grounding=None, numbered=numbered)
    for e in out["entries"]:  # naskah jadi: abaikan rujukan grounding yang tak dikutip sebagai "uncited di naskah"
        e["in_bibliography"] = any(m["citation_id"] == e["citation_id"] for m in matched_entries)

    # sitasi yang tidak cocok ke grounding: ada di daftar pustaka naskah (belum terverifikasi) atau tidak ada sama sekali
    unverified: list[dict] = []
    missing: list[dict] = []
    for item in out["unmatched"]:
        m = re.match(r"\(?\s*([^\d,;&()]+?)(?:\s+et al\.?)?(?:\s*(?:&|and|dan)\s+[^,;()]+)?,?\s*((?:19|20)\d{2})", item["text"])
        raw_hit = None
        if m:
            sur = foundational.fold(_first_author(m.group(1)))
            for raw in unmatched_entries:
                if sur and sur in foundational.fold(raw[:140]) and m.group(2) in raw:
                    raw_hit = raw
                    break
        (unverified if raw_hit else missing).append({**item, "bibliography_entry": raw_hit or ""})
    grouped: dict[str, dict] = {}
    for u in unverified:
        g = grouped.setdefault(u["bibliography_entry"], {"bibliography_entry": u["bibliography_entry"], "markers": [], "uses": []})
        g["markers"].append(u["text"])
        g["uses"].extend(u["uses"])
    out["unverified"] = list(grouped.values())
    out["missing"] = missing
    out["unmatched"] = []
    cited_raw = {g["bibliography_entry"] for g in out["unverified"]}
    out["bibliography"] = {
        "found": bool(bib),
        "entries": len(bib),
        "matched": len(matched_entries),
        "unmatched": unmatched_entries[:200],
        "never_cited": [raw for raw in unmatched_entries if raw not in cited_raw][:100],
    }
    in_text = sum(len(e["uses"]) for e in out["entries"]) + sum(len(g["uses"]) for g in out["unverified"]) + sum(len(m["uses"]) for m in missing)
    mismatch = sum(1 for e in out["entries"] for u in e["uses"] if u["year_mismatch"])
    out["source"] = "upload"
    out["filename"] = filename
    out["warnings"] = warnings
    out["summary"] = {
        "in_text": in_text,
        "tracked": sum(len(e["uses"]) for e in out["entries"]) - mismatch,
        "year_mismatch": mismatch,
        "unverified": sum(len(g["uses"]) for g in out["unverified"]),
        "missing": sum(len(m["uses"]) for m in missing),
        "grounded_refs": len(refs),
    }
    return out
