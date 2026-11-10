"""Teori dasar: mencocokkan daftar rujukan yang ditulis peneliti (isian Teori) ke basis data publik.

Prinsip proyek: tidak ada rujukan karangan. Sebuah baris hanya dimasukkan bila karya yang sama benar-benar ditemukan
(judul mirip, nama penulis pertama cocok, tahun sama atau selisih 1). Yang tidak ketemu dilaporkan apa adanya.
"""

import asyncio
import re
import unicodedata
from difflib import SequenceMatcher

from app.services import scientific_api as sci

MAX_ENTRIES = 15
YEAR_TOLERANCE = 1
MIN_TITLE_SIMILARITY = 0.9

_YEAR_RE = re.compile(r"\(((?:15|16|17|18|19|20)\d{2})[a-z]?\)\.?")
_BULLET_RE = re.compile(r"^\s*(?:[-*•]|\d{1,2}[.)])\s+")
_INITIALS_RE = re.compile(r"^(?:[A-Z]\.?\s*){1,4}$")


def fold(text: str) -> str:
    """Huruf kecil tanpa aksen (Dörnyei -> dornyei) agar nama dari sumber berbeda bisa dibandingkan."""
    nfd = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in nfd if not unicodedata.combining(c)).lower()


def compact(text: str) -> str:
    """Hanya huruf dan angka, tanpa spasi. Tahan terhadap salah ketik seperti 'ofControl' (spasi hilang)."""
    return re.sub(r"[^a-z0-9]+", "", fold(text))


def parse_entries(text: str) -> tuple[list[dict], list[dict]]:
    """Pecah isian teori menjadi baris rujukan. Mengembalikan (entri terbaca, entri yang tidak bisa dibaca)."""
    entries: list[dict] = []
    unparsed: list[dict] = []
    for raw in re.split(r"[\r\n]+", text or ""):
        line = _BULLET_RE.sub("", raw).strip()
        if len(line) < 4:
            continue
        for seg in _split_line(line):
            entry = _parse_line(seg)
            if entry:
                entries.append(entry)
            else:
                unparsed.append({"raw": seg, "reason": "Format tidak dikenali. Tulis: Penulis, A. (tahun). Judul. Sumber."})
    return entries[:MAX_ENTRIES], unparsed


_NEXT_AUTHOR_RE = re.compile(r"\.\s+(?=[^\W\d_][\w'’\-]+,\s+[A-Z]\.)")


def _split_line(line: str) -> list[str]:
    """Beberapa rujukan yang tertulis dalam satu baris dipecah di awal nama penulis berikutnya ('... Journal. MacIntyre, P.D.')."""
    years = list(_YEAR_RE.finditer(line))
    if len(years) < 2:
        return [line]
    starts = [0]
    for prev, nxt in zip(years, years[1:]):
        gap = line[prev.end() : nxt.start()]
        found = _NEXT_AUTHOR_RE.search(gap)
        if not found:
            return [line]  # batas tidak bisa dipastikan: biarkan utuh daripada salah potong
        starts.append(prev.end() + found.end())
    ends = starts[1:] + [len(line)]
    return [line[a:b].strip() for a, b in zip(starts, ends) if line[a:b].strip()]


def _parse_line(line: str) -> dict | None:
    m = _YEAR_RE.search(line)
    if not m:
        return None
    authors_part = line[: m.start()].strip(" ,.")
    rest = line[m.end() :].strip()
    if not authors_part or not rest:
        return None
    title = _extract_title(rest)
    if len(compact(title)) < 6:
        return None
    return {
        "raw": line,
        "year": int(m.group(1)),
        "surnames": _surnames(authors_part),
        "title": title,
    }


def _extract_title(rest: str) -> str:
    rest = re.sub(r"\s*\([^()]*\)\s*\.?\s*$", "", rest).strip() or rest  # catatan penutup seperti "(speaking performance)"
    m = re.match(r'^(.+?[^.\s])\.(?:\s+(?=[A-Z"“‘\[])|\s*$)', rest)  # kalimat pertama = judul; sisanya nama jurnal/penerbit
    title = (m.group(1) if m else rest).strip(" .")
    return title


def _surnames(authors_part: str) -> list[str]:
    """'Horwitz, E.K., Horwitz, M.B., & Cope, J.' -> ['Horwitz', 'Horwitz', 'Cope']; juga 'Albert Bandura'."""
    cleaned = re.sub(r"\s*(?:&|\band\b|\bdan\b)\s*", ", ", authors_part)
    tokens = [t.strip() for t in cleaned.split(",") if t.strip()]
    names = [t for t in tokens if not _INITIALS_RE.match(t)]
    if len(names) == len(tokens) and len(tokens) >= 1 and all(" " in t for t in tokens[:1]):
        names = [t.split()[-1] for t in tokens]  # 'Albert Bandura' (tanpa koma/inisial): nama belakang = kata terakhir
    return [n for n in names if len(compact(n)) >= 2]


def _similarity(a: str, b: str) -> float:
    ca, cb = compact(a), compact(b)
    if not ca or not cb:
        return 0.0
    if ca == cb:
        return 1.0
    sa, sb = " ".join(fold(a).split()), " ".join(fold(b).split())
    short, long_ = (sa, sb) if len(sa) <= len(sb) else (sb, sa)
    # Judul vs judul + subjudul ("Judul: Subjudul"). Tambahan kata biasa ("... in Practice") berarti karya lain.
    if len(compact(short)) >= 15 and long_.startswith(short) and long_[len(short) :].lstrip()[:1] in {":", "-", "–", "—", "("}:
        return 0.95
    return SequenceMatcher(None, ca, cb).ratio()


def _author_ok(entry: dict, cand: dict) -> bool:
    names = [fold(n) for n in entry["surnames"][:1]]
    if not names:
        return False
    authors = " ".join(fold(a) for a in (cand.get("authors") or []) if a and a.strip().lower() != "anonim")
    return bool(authors) and all(n in authors for n in names)


def _year_ok(entry: dict, cand: dict) -> bool:
    y = cand.get("publication_year") or 0
    return bool(y) and abs(int(y) - entry["year"]) <= YEAR_TOLERANCE


def best_match(entry: dict, candidates: list[dict]) -> tuple[dict | None, dict | None]:
    """(cocok, terdekat-tapi-ditolak). Cocok bila judul mirip, penulis pertama sama, dan tahun berdekatan."""
    accepted: list[tuple[float, dict]] = []
    closest: tuple[float, dict] | None = None
    for c in candidates:
        if not sci.usable(c):
            continue
        sim = _similarity(entry["title"], c.get("title", ""))
        if sim < MIN_TITLE_SIMILARITY:
            continue
        if _author_ok(entry, c) and _year_ok(entry, c):
            accepted.append((sim, c))
        elif _author_ok(entry, c) and (closest is None or sim > closest[0]):
            closest = (sim, c)  # karya yang sama tetapi tahun berbeda (cetak ulang/edisi)
    if not accepted:
        return None, (closest[1] if closest else None)
    accepted.sort(
        key=lambda t: (t[0], bool(t[1].get("highlighted_snippet")), bool(t[1].get("doi")), t[1].get("cited_by", 0) or 0),
        reverse=True,
    )
    best = dict(accepted[0][1])
    for _, other in accepted[1:]:  # lengkapi bidang kosong dari sumber lain untuk karya yang sama
        for field in ("doi", "pdf_url", "journal_name", "volume_issue", "page_range", "highlighted_snippet"):
            if not best.get(field) and other.get(field):
                best[field] = other[field]
    if (best.get("title") or "").isupper():  # sebagian sumber menyimpan judul KAPITAL semua; pakai penulisan Anda
        best["title"] = entry["title"]
    return best, None


def _last_name(author: str) -> str:
    return author.split(",")[0].strip() if "," in author else (author.split() or [""])[-1]


def describe_differences(entry: dict, ref: dict) -> str:
    """Catatan bila data basis data berbeda dari yang Anda tulis (tahun, daftar penulis). Rujukan memakai data basis data."""
    notes: list[str] = []
    year = ref.get("publication_year") or 0
    if year and year != entry["year"]:
        notes.append(f"Tahun di basis data {year}, di daftar Anda {entry['year']}; rujukan memakai {year}.")
    mine = {fold(n) for n in entry["surnames"]}
    extra = [a for a in (ref.get("authors") or []) if fold(_last_name(a)) not in mine]
    if extra:
        notes.append("Basis data juga mencantumkan penulis: " + ", ".join(extra[:3]) + ". Pastikan sesuai edisi yang Anda pakai.")
    return " ".join(notes)


async def _candidates(entry: dict) -> tuple[list[dict], int, int]:
    """Cari ke OpenAlex dan Crossref tanpa batas tahun. Mengembalikan (kandidat, jumlah sumber, jumlah gagal)."""
    first = entry["surnames"][0] if entry["surnames"] else ""
    jobs = [
        sci.search_openalex(entry["title"], 8, None),
        sci.search_crossref(f"{entry['title']} {first} {entry['year']}".strip(), 8, None),
    ]
    results = await asyncio.gather(*jobs, return_exceptions=True)
    out: list[dict] = []
    failed = 0
    for r in results:
        if isinstance(r, Exception):
            failed += 1
        else:
            out.extend(r)
    return out, len(jobs), failed


async def resolve_all(theory_text: str) -> dict:
    """Hasil: {found: [{entry, ref}], not_found: [{raw, reason, closest}], unparsed: [...]}. Tidak pernah mengarang rujukan."""
    entries, unparsed = parse_entries(theory_text)
    gate = asyncio.Semaphore(4)

    async def one(entry: dict) -> dict:
        async with gate:
            cands, total, failed = await _candidates(entry)
        if failed == total:
            return {"entry": entry, "ref": None, "reason": "Sumber data tidak dapat dijangkau. Coba lagi beberapa saat lagi.", "closest": None}
        ref, closest = best_match(entry, cands)
        if ref:
            return {"entry": entry, "ref": ref, "reason": "", "closest": None, "note": describe_differences(entry, ref)}
        if closest:
            reason = (
                f"Karya dengan judul sama ditemukan tetapi terbit {closest.get('publication_year') or '?'}, "
                f"bukan {entry['year']}. Tidak dimasukkan otomatis; impor BibTeX bila yakin itu edisi yang Anda pakai."
            )
        else:
            reason = "Tidak ditemukan di OpenAlex atau Crossref (buku sering tidak terdata). Impor lewat BibTeX/RIS bila perlu."
        return {"entry": entry, "ref": None, "reason": reason, "closest": closest}

    resolved = await asyncio.gather(*[one(e) for e in entries])
    return {
        "found": [r for r in resolved if r["ref"]],
        "not_found": [
            {
                "raw": r["entry"]["raw"],
                "reason": r["reason"],
                "closest": (
                    {"title": r["closest"].get("title"), "year": r["closest"].get("publication_year"), "doi": r["closest"].get("doi")}
                    if r["closest"]
                    else None
                ),
            }
            for r in resolved
            if not r["ref"]
        ],
        "unparsed": unparsed,
    }
