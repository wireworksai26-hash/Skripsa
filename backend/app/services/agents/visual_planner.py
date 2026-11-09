"""Perencana tabel & diagram per bab, menyesuaikan jenis penelitian, jurusan, dan bahasa naskah.

Prinsip (sama dengan penulis draf): tidak ada angka, nama, atau kutipan karangan. Sel yang seharusnya berisi data
penelitian ditulis `[DATA: apa yang harus diisi]`. Tabel "penelitian relevan" dibuat oleh kode dari metadata rujukan
terpilih (bukan oleh LLM), sehingga selalu nyata.
"""

import re
from uuid import uuid4

from app.services.agents.quality import _CITE  # noqa: F401  (pola sitasi bersama)
from app.services.citation import in_text_marker
from app.services.llm import LLMUnavailable, extract_json, llm_chat_ex

MAX_ITEMS = 8
MAX_COLS = 8
MAX_ROWS = 12
DIAGRAM_START = ("flowchart", "graph", "sequencediagram", "classdiagram", "statediagram", "erdiagram", "gantt")

GUIDE = {
    "KUALITATIF": (
        "Qualitative study. Chapter 2: conceptual framework diagram linking the study's focuses to participants' experiences and "
        "findings. Chapter 3: participant profile table (rows are placeholders), interview/observation instrument blueprint table "
        "(aspect | indicators | example question items; question wording is allowed because it is an instrument, not data), "
        "data analysis flow diagram (Miles, Huberman & Saldana), research procedure diagram. Chapter 4: theme matrix table "
        "(theme | related research question | data source | [DATA: representative excerpt]) and a coding table "
        "(code | category | theme) with [DATA] cells."
    ),
    "KUANTITATIF": (
        "Quantitative study. Chapter 2: theoretical/conceptual framework diagram with hypotheses. Chapter 3: population & sample "
        "table (numbers are [DATA]), instrument blueprint table (variable | indicator | item numbers | scale), validity & reliability "
        "result table with [DATA] cells, research design diagram (e.g. pre-test/post-test groups). Chapter 4: descriptive statistics "
        "table, assumption test table, hypothesis test table: all numeric cells are [DATA]."
    ),
    "MIXED_METHODS": (
        "Mixed methods. Chapter 3: research design diagram showing the sequence of quantitative and qualitative phases and where "
        "they are integrated, instrument blueprint table. Chapter 4: joint display table (quantitative result | qualitative theme | "
        "integration) with [DATA] cells."
    ),
    "RND": (
        "Research & development. Chapter 3: development model diagram (e.g. ADDIE or 4D), expert validation instrument table. "
        "Chapter 4: expert validation result table and product trial result table, numeric cells are [DATA]."
    ),
}
INFORMATIKA_GUIDE = (
    "Informatics topic: also propose a system architecture or system flow diagram and a test-case table "
    "(test id | scenario | expected result | [DATA: actual result]) in the chapters where design and testing are described."
)

SYSTEM = (
    "You plan the tables and diagrams of a thesis so that each chapter gets the visuals a supervisor expects for this type of "
    "research. Respond with JSON only: "
    '{"items":[{"chapter":"3","type":"table","title":"...","caption":"...","columns":["..."],"rows":[["..."]],"note":"",'
    '"mermaid":"","rationale":"satu kalimat bahasa Indonesia: mengapa visual ini perlu"}]}\n'
    "Rules:\n"
    "1. NEVER invent numbers, percentages, names, quotes, or results. Any cell that would come from the research data must be "
    "written exactly as [DATA: what to insert]. Placeholders must be specific (e.g. [DATA: number of Class A students]).\n"
    "2. type is \"table\" or \"diagram\". Tables: 2-8 columns, 2-8 rows. Diagrams: valid Mermaid, flowchart TD or LR, every node "
    "label in double quotes like A[\"text\"], at most 14 nodes, no HTML except <br/>, put Mermaid code in \"mermaid\" and leave "
    "columns/rows empty.\n"
    "3. chapter must be one of the chapter numbers provided. At most 3 items per chapter and at most 8 items in total.\n"
    "4. Titles, captions, headers and node labels must be in the thesis language given. Be specific to the thesis title, "
    "variables and subject; avoid generic filler.\n"
    "5. Do not propose a visual whose title is similar to one in 'Already exists'. Do not propose a literature comparison table "
    "(it is generated separately)."
)


def _tidy_title(title: str) -> str:
    t = " ".join((title or "").split()).rstrip(".")
    letters = re.sub(r"[^A-Za-z]", "", t)
    if len(letters) >= 8 and sum(1 for c in letters if c.isupper()) / len(letters) > 0.7:
        t = t.lower()
        return t[:1].upper() + t[1:]
    return t


def studies_table(refs: list[dict], language: str, style: str = "APA_7TH") -> dict | None:
    """Tabel perbandingan penelitian terdahulu: seluruhnya dari metadata & abstrak rujukan terpilih."""
    rows = []
    for i, r in enumerate(refs, start=1):
        who = in_text_marker("APA_7TH", r, i - 1).strip("()").replace(",", "")
        abstract = " ".join((r.get("highlighted_snippet") or "").split())
        first = re.split(r"(?<=[.!?])\s+", abstract)[0][:230] if abstract else ""
        rows.append(
            [
                str(i),
                who,
                _tidy_title(r.get("title") or ""),
                (r.get("journal_name") or "-")[:70],
                first or ("[tidak ada abstrak]" if language != "en" else "[no abstract available]"),
            ]
        )
    if not rows:
        return None
    en = language == "en"
    return {
        "chapter": "2",
        "type": "table",
        "title": "Summary of relevant studies" if en else "Ringkasan penelitian yang relevan",
        "caption": "Summary of relevant studies" if en else "Ringkasan penelitian yang relevan",
        "columns": ["No.", "Author(s) & Year", "Title", "Source", "Focus (from abstract)"] if en else ["No.", "Penulis & Tahun", "Judul", "Sumber", "Fokus (dari abstrak)"],
        "rows": rows[:MAX_ROWS],
        "note": "Disusun otomatis dari metadata dan abstrak rujukan terpilih; tambahkan kolom metode dan celah penelitian sendiri."
        if not en
        else "Generated from the metadata and abstracts of the selected references; add your own method and research-gap columns.",
        "mermaid": "",
        "rationale": "Pembimbing biasanya meminta perbandingan penelitian terdahulu dan celah penelitian di akhir Bab II.",
        "source": "auto",
    }


def _clean_cell(v) -> str:
    return " ".join(str(v if v is not None else "").split())[:160]


def _normalize_table(item: dict, chapter: str, has_data: bool) -> dict | None:
    cols = [_clean_cell(c) for c in (item.get("columns") or [])][:MAX_COLS]
    if len(cols) < 2:
        return None
    rows = []
    for r in (item.get("rows") or [])[:MAX_ROWS]:
        if not isinstance(r, list):
            continue
        cells = [_clean_cell(c) for c in r][: len(cols)]
        cells += [""] * (len(cols) - len(cells))
        if chapter in ("3", "4") and not has_data:
            # Angka pada Bab III/IV tanpa data lapangan pasti karangan: ganti dengan penanda isian.
            cells = [
                c if j == 0 or not re.fullmatch(r"[\d.,%\s–-]+", c or "x") else "[DATA: nilai]" for j, c in enumerate(cells)
            ]
        rows.append(cells)
    if len(rows) < 1:
        return None
    return {"columns": cols, "rows": rows}


def _normalize_mermaid(code: str) -> str | None:
    code = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", (code or "").strip()).strip()
    if not code.lower().startswith(DIAGRAM_START) or code.count("\n") < 2 or len(code) > 3000:
        return None
    return code


def normalize(items: list, chapter_codes: set[str], existing: set[str], has_data: bool) -> list[dict]:
    out: list[dict] = []
    per_chapter: dict[str, int] = {}
    seen = {t.lower() for t in existing}
    for it in items or []:
        if not isinstance(it, dict):
            continue
        chapter = str(it.get("chapter") or "").strip()
        kind = str(it.get("type") or "").strip().lower()
        title = _clean_cell(it.get("title"))
        if chapter not in chapter_codes or kind not in ("table", "diagram") or not title or title.lower() in seen:
            continue
        if per_chapter.get(chapter, 0) >= 3:
            continue
        base = {
            "chapter": chapter,
            "type": kind,
            "title": title[:120],
            "caption": _clean_cell(it.get("caption")) or title[:120],
            "note": " ".join(str(it.get("note") or "").split())[:400],
            "rationale": re.sub(r"^\s*satu kalimat bahasa indonesia\s*:\s*", "", " ".join(str(it.get("rationale") or "").split()), flags=re.I)[:240],
            "columns": [],
            "rows": [],
            "mermaid": "",
            "source": "ai",
        }
        if kind == "table":
            t = _normalize_table(it, chapter, has_data)
            if not t:
                continue
            base.update(t)
        else:
            code = _normalize_mermaid(it.get("mermaid"))
            if not code:
                continue
            base["mermaid"] = code
        base["needs_data"] = "[DATA" in " ".join(" ".join(r) for r in base["rows"]).upper() if kind == "table" else False
        seen.add(title.lower())
        per_chapter[chapter] = per_chapter.get(chapter, 0) + 1
        out.append(base)
        if len(out) >= MAX_ITEMS:
            break
    return out


async def plan_visuals(
    ctx: dict, chapters: list[dict], refs: list[dict], existing: list[str], only: set[str] | None, extra: str
) -> tuple[list[dict], str]:
    """Kembalikan (usulan, penyedia). `chapters`: [{code,title,sections:[...],excerpt}]. Melempar LLMUnavailable."""
    language = ctx.get("language", "id")
    codes = {c["code"] for c in chapters if not only or c["code"] in only}
    has_data = bool((ctx.get("results_data") or "").strip())
    existing_lower = [e.lower() for e in existing]

    items: list[dict] = []
    if "2" in codes and refs:
        st = studies_table(refs, language)
        if st and not any(("relevant studies" in e or "penelitian yang relevan" in e or "penelitian terdahulu" in e) for e in existing_lower):
            st["id"] = uuid4().hex[:8]
            items.append(st)

    guide = GUIDE.get(ctx.get("method", ""), GUIDE["KUANTITATIF"]) + (" " + INFORMATIKA_GUIDE if ctx.get("domain") == "INFORMATIKA" else "")
    chap_text = "\n".join(
        f"- Chapter {c['code']} {c['title']}: sections = {', '.join(c['sections'])}" + (f"\n  written so far: {c['excerpt']}" if c.get("excerpt") else "")
        for c in chapters
        if c["code"] in codes
    )
    user = (
        f"Thesis title: {ctx.get('title')}\nLanguage of all visual text: {'English' if language == 'en' else 'Bahasa Indonesia'}\n"
        f"Research type: {ctx.get('method')} · Field: {ctx.get('domain')} · Level: {ctx.get('degree_level')}\n"
        f"Variable/focus X: {ctx.get('variable_x') or '-'} · Variable/focus Y: {ctx.get('variable_y') or '-'} · Subject: {ctx.get('subject') or '-'}\n\n"
        f"What is typical for this research type: {guide}\n\n"
        f"Chapters you may use (use ONLY these chapter numbers):\n{chap_text}\n\n"
        f"Already exists (do not duplicate): {'; '.join(existing) or '-'}\n"
        + ("\nREAL RESEARCH DATA the student already saved (tables in Chapter 4 may use these values, nothing else):\n"
           + ctx["results_data"][:2500] + "\n" if has_data else "\nNo field data has been saved yet.\n")
        + (f"\nStudent's extra request: {extra}\n" if extra else "")
        + "\nPropose the visuals now."
    )
    convo = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
    last = "tidak ada jawaban"
    provider = ""
    for _ in range(2):
        raw, provider = await llm_chat_ex(convo, tier="heavy", temperature=0.3, max_tokens=5000)
        try:
            data = extract_json(raw)
        except ValueError as exc:
            last = f"JSON tidak valid ({exc})"
            convo = convo + [{"role": "assistant", "content": raw}, {"role": "user", "content": "Invalid JSON. Return the complete JSON again, nothing else."}]
            continue
        got = normalize(data.get("items") or [], codes, set(existing) | {i["title"] for i in items}, has_data)
        if got:
            for g in got:
                g["id"] = uuid4().hex[:8]
            return (items + got)[:MAX_ITEMS + 1], provider
        last = "tidak ada usulan yang valid"
        convo = convo + [{"role": "assistant", "content": raw}, {"role": "user", "content": "No valid items. Follow the rules: valid chapters, valid Mermaid, [DATA: ...] placeholders. Return JSON again."}]
    if items:  # tabel penelitian relevan tetap berguna walau LLM gagal
        return items, provider or "kode"
    raise LLMUnavailable(f"Saran visual tidak dapat dibuat: {last}")
