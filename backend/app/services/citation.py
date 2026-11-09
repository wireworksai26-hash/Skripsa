APA_7TH = "APA_7TH"
IEEE = "IEEE"
CHICAGO = "CHICAGO"
HARVARD = "HARVARD"


def surname_of(author: str) -> str:
    author = author.strip()
    if not author:
        return "Anonim"
    if "," in author:
        return author.split(",", 1)[0].strip()
    parts = author.split()
    return parts[-1]


def initials_of(author: str) -> str:
    if "," in author:
        given = author.split(",", 1)[1].strip()
    else:
        given = " ".join(author.strip().split()[:-1])
    return " ".join(f"{g[0].upper()}." for g in given.split() if g)


def in_text_marker(style: str, ref: dict, index: int) -> str:
    authors = ref.get("authors") or []
    last = surname_of(authors[0]) if authors else "Anonim"
    year = ref.get("publication_year", 0) or ref.get("year", 0)
    if style == IEEE:
        return f"[{index + 1}]"
    second = ""
    etal = ""
    if len(authors) == 2:
        second = f" & {surname_of(authors[1])}"
    elif len(authors) > 2:
        etal = " et al."
    if style == CHICAGO:
        return f"({last}{second}{etal} {year})"
    return f"({last}{second}{etal}, {year})"


def page_range(ref: dict) -> str:
    return ref.get("page_range") or ref.get("pages") or ""


def reference_string(ref: dict, style: str) -> str:
    authors = ref.get("authors") or ["Anonim"]
    year = ref.get("publication_year", 0) or ref.get("year", 0)
    title = ref.get("title", "")
    journal = ref.get("journal_name") or ref.get("journal") or "—"
    vol = ref.get("volume_issue") or ""
    pages = page_range(ref)
    doi = ref.get("doi")

    if style == IEEE:
        ieee_authors = ", ".join(f"{initials_of(a)} {surname_of(a)}" for a in authors)
        vol_part = f", vol. {vol}" if vol else ""
        pages_part = f", pp. {pages}" if pages else ""
        doi_part = f" doi: {doi}" if doi else ""
        return f'{ieee_authors}, "{title}," {journal}{vol_part}{pages_part}, {year}.{doi_part}'

    if style == CHICAGO:
        chi_authors = ", ".join(f"{surname_of(a)}, {initials_of(a)}" for a in authors)
        vol_part = f" {vol}" if vol else ""
        pages_part = f", {pages}" if pages else ""
        return f'{chi_authors}. "{title}." {journal}{vol_part}{pages_part} ({year}).'

    apa_authors = ", ".join(f"{surname_of(a)}, {initials_of(a)}" for a in authors)
    doi_part = f" https://doi.org/{doi}" if doi else ""
    pages_part = f", {pages}" if pages else ""
    if style == HARVARD:
        return f"{apa_authors} ({year}) '{title}', {journal}{', ' + vol if vol else ''}{pages_part}.{doi_part}"
    return f"{apa_authors} ({year}) {title}. {journal}{', ' + vol if vol else ''}{pages_part}.{doi_part}"


def bibliography(refs: list[dict], style: str) -> list[str]:
    items = list(refs)
    if style == IEEE:
        return [f"[{i + 1}] {reference_string(r, style)}" for i, r in enumerate(items)]
    items.sort(key=lambda r: surname_of((r.get("authors") or ["Anonim"])[0]).lower())
    return [reference_string(r, style) for r in items]
