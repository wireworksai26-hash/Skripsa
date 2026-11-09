"""Impor/ekspor referensi BibTeX dan RIS (Zotero, Mendeley, EndNote)."""

import re

_YEAR = re.compile(r"(19|20)\d{2}")


def _clean(v: str) -> str:
    v = re.sub(r"\s+", " ", v.replace("{", "").replace("}", "")).strip().strip(",").strip()
    return v


def _split_authors_bibtex(raw: str) -> list[str]:
    out = []
    for a in re.split(r"\s+and\s+", _clean(raw)):
        a = a.strip()
        if a:
            out.append(a)
    return out


def _bib_fields(body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    i = 0
    n = len(body)
    while i < n:
        m = re.compile(r"\s*([A-Za-z][A-Za-z0-9_-]*)\s*=\s*").match(body, i)
        if not m:
            i += 1
            continue
        key = m.group(1).lower()
        i = m.end()
        if i >= n:
            break
        if body[i] == "{":
            depth, j = 1, i + 1
            while j < n and depth:
                depth += (body[j] == "{") - (body[j] == "}")
                j += 1
            value = body[i + 1 : j - 1]
            i = j
        elif body[i] == '"':
            j = body.find('"', i + 1)
            j = n if j < 0 else j
            value, i = body[i + 1 : j], j + 1
        else:
            m2 = re.compile(r"[^,]+").match(body, i)
            value = m2.group(0) if m2 else ""
            i = m2.end() if m2 else i + 1
        fields[key] = value
    return fields


def parse_bibtex(text: str) -> list[dict]:
    refs = []
    for m in re.finditer(r"@(\w+)\s*\{\s*([^,\s]*)\s*,", text):
        kind = m.group(1).lower()
        if kind in {"comment", "string", "preamble"}:
            continue
        depth, j = 1, m.end()
        while j < len(text) and depth:
            depth += (text[j] == "{") - (text[j] == "}")
            j += 1
        f = _bib_fields(text[m.end() : j - 1])
        title = _clean(f.get("title", ""))
        if not title:
            continue
        year = _YEAR.search(f.get("year", "") or f.get("date", ""))
        refs.append(
            {
                "title": title,
                "authors": _split_authors_bibtex(f.get("author", "")),
                "publication_year": int(year.group(0)) if year else 0,
                "journal_name": _clean(f.get("journal", "") or f.get("booktitle", "") or f.get("publisher", "")) or None,
                "volume_issue": _clean(f.get("volume", "") + (f"({_clean(f['number'])})" if f.get("number") else "")) or None,
                "page_range": _clean(f.get("pages", "")).replace("--", "–") or None,
                "doi": _clean(f.get("doi", "")).replace("https://doi.org/", "") or None,
                "pdf_url": _clean(f.get("url", "")) or None,
                "highlighted_snippet": _clean(f.get("abstract", "")),
                "source_database": "BibTeX",
            }
        )
    return refs


def parse_ris(text: str) -> list[dict]:
    refs, cur = [], {}
    for line in text.splitlines():
        m = re.match(r"^([A-Z][A-Z0-9])\s{2}-\s?(.*)$", line)
        if not m:
            continue
        tag, val = m.group(1), m.group(2).strip()
        if tag == "TY":
            cur = {"AU": []}
        elif tag == "ER":
            if cur.get("title"):
                refs.append(_ris_to_ref(cur))
            cur = {}
        elif cur is not None:
            if tag in ("AU", "A1"):
                cur.setdefault("AU", []).append(val)
            elif tag in ("TI", "T1"):
                cur["title"] = cur.get("title") or val
            elif tag in ("PY", "Y1", "DA"):
                cur.setdefault("year", val)
            elif tag in ("JO", "JF", "T2", "JA"):
                cur.setdefault("journal", val)
            elif tag == "VL":
                cur["vol"] = val
            elif tag == "IS":
                cur["issue"] = val
            elif tag == "SP":
                cur["sp"] = val
            elif tag == "EP":
                cur["ep"] = val
            elif tag == "DO":
                cur["doi"] = val
            elif tag in ("UR", "L1"):
                cur.setdefault("url", val)
            elif tag in ("AB", "N2"):
                cur.setdefault("abstract", val)
    if cur.get("title"):
        refs.append(_ris_to_ref(cur))
    return refs


def _ris_to_ref(c: dict) -> dict:
    year = _YEAR.search(c.get("year", ""))
    vol = c.get("vol", "")
    issue = f"({c['issue']})" if c.get("issue") else ""
    pages = "–".join(x for x in [c.get("sp", ""), c.get("ep", "")] if x)
    return {
        "title": _clean(c["title"]),
        "authors": c.get("AU", []),
        "publication_year": int(year.group(0)) if year else 0,
        "journal_name": c.get("journal") or None,
        "volume_issue": (vol + issue) or None,
        "page_range": pages or None,
        "doi": (c.get("doi") or "").replace("https://doi.org/", "") or None,
        "pdf_url": c.get("url") or None,
        "highlighted_snippet": c.get("abstract", ""),
        "source_database": "RIS",
    }


def parse_references(text: str) -> list[dict]:
    """Deteksi format otomatis: BibTeX (@article{...}) atau RIS (TY  - ...)."""
    if re.search(r"^\s*TY\s{2}-", text, flags=re.M):
        return parse_ris(text)
    return parse_bibtex(text)


def _key(ref: dict, i: int) -> str:
    first = (ref.get("authors") or ["ref"])[0]
    sur = re.sub(r"[^A-Za-z]", "", first.split(",")[0].split()[-1] if first else "ref") or "ref"
    return f"{sur.lower()}{ref.get('publication_year') or 'nd'}_{i + 1}"


def to_bibtex(refs: list[dict]) -> str:
    out = []
    for i, r in enumerate(refs):
        kind = "article" if r.get("journal_name") else "misc"
        lines = [f"@{kind}{{{_key(r, i)},", f"  title = {{{r['title']}}},"]
        if r.get("authors"):
            lines.append(f"  author = {{{' and '.join(r['authors'])}}},")
        if r.get("publication_year"):
            lines.append(f"  year = {{{r['publication_year']}}},")
        if r.get("journal_name"):
            lines.append(f"  journal = {{{r['journal_name']}}},")
        if r.get("volume_issue"):
            lines.append(f"  volume = {{{r['volume_issue']}}},")
        if r.get("page_range"):
            lines.append(f"  pages = {{{r['page_range'].replace('–', '--')}}},")
        if r.get("doi"):
            lines.append(f"  doi = {{{r['doi']}}},")
        out.append("\n".join(lines).rstrip(",") + "\n}")
    return "\n\n".join(out) + ("\n" if out else "")


def to_ris(refs: list[dict]) -> str:
    out = []
    for r in refs:
        lines = ["TY  - JOUR" if r.get("journal_name") else "TY  - GEN", f"TI  - {r['title']}"]
        lines += [f"AU  - {a}" for a in r.get("authors") or []]
        if r.get("publication_year"):
            lines.append(f"PY  - {r['publication_year']}")
        if r.get("journal_name"):
            lines.append(f"JO  - {r['journal_name']}")
        if r.get("volume_issue"):
            lines.append(f"VL  - {r['volume_issue']}")
        if r.get("page_range"):
            sp, _, ep = r["page_range"].replace("–", "-").partition("-")
            lines.append(f"SP  - {sp}")
            if ep:
                lines.append(f"EP  - {ep}")
        if r.get("doi"):
            lines.append(f"DO  - {r['doi']}")
        lines.append("ER  - ")
        out.append("\n".join(lines))
    return "\n".join(out) + ("\n" if out else "")
