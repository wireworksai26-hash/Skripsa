"""Data penelitian milik pengguna untuk Bab IV dan pengolahannya oleh agen.

- Tabel (CSV/TSV): diolah deterministik (statistik deskriptif dan distribusi frekuensi), tanpa LLM, jadi tidak bisa dikarang.
- Teks (transkrip wawancara, catatan observasi, data analisis dokumen): LLM mengodekan menjadi tema, dan setiap kutipan
  WAJIB ada persis di data pengguna; kutipan yang tidak ditemukan dibuang, tema tanpa kutipan terverifikasi dibuang.
"""

import csv
import io
import re

from app.services.agents.advisor import _norm
from app.services.agents.documents import GenerationError, _ask, _lang, _words
from app.services.stats import describe

MAX_CONTENT = 60_000
KINDS = ("table", "text")


TXT = {
    "id": {
        "desc": "Statistik deskriptif", "var": "Variabel", "mean": "Rata-rata", "max": "Maks", "dist": "Distribusi", "freq": "Frekuensi", "pct": "Persentase",
        "rows_note": "{n} baris data dari pengguna.", "theme": "Tema", "themes": "Tema hasil pengodean", "desc_col": "Deskripsi", "quotes": "Kutipan dari data",
        "verified": "Kutipan disalin persis dari data penelitian pengguna dan diverifikasi otomatis.", "agent_note": "Catatan agen",
    },
    "en": {
        "desc": "Descriptive statistics", "var": "Variable", "mean": "Mean", "max": "Max", "dist": "Distribution of", "freq": "Frequency", "pct": "Percentage",
        "rows_note": "{n} rows of data provided by the researcher.", "theme": "Theme", "themes": "Themes from coding", "desc_col": "Description", "quotes": "Excerpts from the data",
        "verified": "Excerpts are copied verbatim from the researcher's data and verified automatically.", "agent_note": "Agent note",
    },
}


def _fmt(x: float, nd: int = 2) -> str:
    return f"{x:.{nd}f}".replace(".", ",")


def _number(raw: str) -> float | None:
    t = (raw or "").strip().replace(" ", "")
    if not t:
        return None
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})+(,\d+)?", t):
        return float(t.replace(".", "").replace(",", "."))
    if re.fullmatch(r"-?\d+([.,]\d+)?", t):
        return float(t.replace(",", "."))
    return None


def parse_table(text: str) -> tuple[list[str], list[list[str]]]:
    sample = text.strip()
    if not sample:
        raise ValueError("Data kosong")
    first = sample.splitlines()[0]
    delim = ";" if first.count(";") >= first.count(",") and ";" in first else "\t" if "\t" in first else ","
    rows = [[c.strip() for c in r] for r in csv.reader(io.StringIO(sample), delimiter=delim) if any(c.strip() for c in r)]
    if len(rows) < 2:
        raise ValueError("Tabel minimal berisi baris judul dan satu baris data")
    cols = rows[0]
    width = len(cols)
    body = [r[:width] + [""] * (width - len(r)) for r in rows[1:]]
    if width < 1 or len(body) > 5000:
        raise ValueError("Tabel tidak valid (maksimal 5000 baris)")
    return [c or f"Kolom {i + 1}" for i, c in enumerate(cols)], body


def analyze_table(title: str, content: str, lang: str = "id") -> dict:
    L = TXT["en" if lang == "en" else "id"]
    cols, rows = parse_table(content)
    desc_rows, freq_tables, skipped = [], [], []
    for i, name in enumerate(cols):
        raw = [r[i] for r in rows if r[i].strip()]
        nums = [_number(v) for v in raw]
        if raw and all(n is not None for n in nums) and len(raw) >= 2:
            d = describe([n for n in nums if n is not None])
            desc_rows.append([name, str(d["n"]), _fmt(d["mean"]), _fmt(d["sd"]), _fmt(d["min"]), _fmt(d["max"])])
        elif raw:
            counts: dict[str, int] = {}
            for v in raw:
                counts[v] = counts.get(v, 0) + 1
            if len(counts) <= 12:
                total = len(raw)
                freq_tables.append(
                    {
                        "title": f"{L['dist']} {name}",
                        "columns": [name, L["freq"], L["pct"]],
                        "rows": [[k, str(c), _fmt(100 * c / total, 1) + "%"] for k, c in sorted(counts.items(), key=lambda kv: -kv[1])],
                        "note": f"n = {total}",
                    }
                )
            else:
                skipped.append(name)
    tables = []
    if desc_rows:
        tables.append({"title": f"{L['desc']} ({title})", "columns": [L["var"], "n", L["mean"], "SD", "Min", L["max"]], "rows": desc_rows, "note": L["rows_note"].format(n=len(rows))})
    tables.extend(freq_tables)
    if not tables:
        raise ValueError("Tidak ada kolom angka atau kategori (maksimal 12 nilai berbeda) yang dapat diolah")
    return {"type": "table", "tables": tables, "rows": len(rows), "skipped_columns": skipped}


CODING_SYSTEM = """Kamu analis data kualitatif yang teliti. Kodekan DATA mentah milik peneliti menjadi tema.
Aturan wajib:
1. Buat 3-6 tema yang benar-benar muncul pada data. Setiap tema: "name" (singkat), "description" (1-2 kalimat berdasarkan data), dan "excerpts": 2-4 kutipan PERSIS (8-40 kata, disalin apa adanya dari data) yang mendukung tema.
2. Dilarang mengarang kutipan, nama, angka, atau temuan yang tidak ada di data. Kutipan yang tidak ditemukan persis di data akan dibuang.
3. Boleh menambahkan "notes": hal penting yang belum terjawab atau terlalu tipis datanya.
4. Bahasa tema dan deskripsi: {lang}.
Tanggapi HANYA JSON: {{"themes":[{{"name":"","description":"","excerpts":["",""]}}],"notes":""}}"""


async def analyze_text(thesis, title: str, content: str) -> tuple[dict, str]:
    L = TXT["en" if (thesis.language or "id") == "en" else "id"]
    norm_data = _norm(content)
    user = f"Judul penelitian: {thesis.title}\nMetode: {thesis.research_method}\nJudul data: {title}\n\nDATA:\n{content[:40_000]}"

    def validate(d: dict) -> dict:
        out = []
        for t in d.get("themes") or []:
            if not isinstance(t, dict):
                continue
            quotes = []
            for q in t.get("excerpts") or []:
                nq = _norm(str(q)).strip(" .…\"'")
                if len(nq.split()) >= 4 and nq in norm_data:
                    quotes.append(" ".join(str(q).split()))
            name = " ".join(str(t.get("name", "")).split())[:100]
            if name and quotes:
                out.append({"name": name, "description": " ".join(str(t.get("description", "")).split()), "excerpts": quotes[:4]})
        if not out:
            raise ValueError("tidak ada tema dengan kutipan yang ditemukan persis di data")
        return {"themes": out, "notes": " ".join(str(d.get("notes", "")).split())}

    if _words(content) < 40:
        raise GenerationError("Data teks terlalu pendek untuk dikodekan (minimal sekitar 40 kata).")
    data, provider = await _ask([{"role": "system", "content": CODING_SYSTEM.format(lang=_lang(thesis))}, {"role": "user", "content": user}], validate, max_tokens=3000, temperature=0.2)
    tables = [
        {
            "title": f"{L['themes']} ({title})",
            "columns": [L["theme"], L["desc_col"], L["quotes"]],
            "rows": [[t["name"], t["description"], " / ".join(f"“{q}”" for q in t["excerpts"])] for t in data["themes"]],
            "note": L["verified"] + (f" {L['agent_note']}: {data['notes']}" if data["notes"] else ""),
        }
    ]
    return {"type": "text", "themes": data["themes"], "notes": data["notes"], "tables": tables}, provider


def summary_for_writer(items) -> str:
    """Ringkasan data pengguna + hasil olahnya untuk Bab IV (dipakai sebagai satu-satunya sumber temuan)."""
    parts = []
    for it in items:
        a = it.analysis_json or {}
        if a.get("type") == "text":
            lines = [f"Tema {i}. {t['name']}: {t['description']} Kutipan: " + " | ".join(t["excerpts"]) for i, t in enumerate(a.get("themes", []), 1)]
            parts.append(f"DATA PENGGUNA ({it.title}, hasil pengodean tema):\n" + "\n".join(lines))
        elif a.get("type") == "table":
            parts.append(f"DATA PENGGUNA ({it.title}): {a.get('rows', 0)} baris; tabel hasil olahnya tercantum di bawah.")
        elif it.content:
            parts.append(f"DATA PENGGUNA ({it.title}, belum diolah), cuplikan:\n{it.content[:2500]}")
    return "\n\n".join(parts)
