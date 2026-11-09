"""Subbab berbentuk butir ditulis lewat keluaran terstruktur (audit BUG-02/BUG-03).

Uji ulang 7 Nov 2026 menunjukkan LLM tetap menulis esai untuk "Research Objectives" dan "Suggestions", serta
mengarang temuan Bab IV tanpa data, walau sudah diberi instruksi dan dikoreksi dua kali. Di sini LLM hanya mengisi
daftar dalam JSON; kode yang menyusun naskahnya sehingga bentuk wajib (pertanyaan, butir, penanda [DATA]) pasti ada.
"""

import re

from app.services.agents.quality import dedupe_paragraphs, polish
from app.services.llm import LLMUnavailable, extract_json, llm_chat_ex

STRUCTURED_KINDS = {"rq", "rq_obj", "objectives", "suggestions"}

_SCHEMAS = {
    "rq": '{"intro":"one sentence","questions":["question ending with ?", "..."]}  (2-4 questions)',
    "objectives": '{"intro":"one sentence","objectives":["To ...", "..."]}  (2-4 objectives mirroring the research questions)',
    "rq_obj": '{"intro":"one sentence","questions":["...?"],"objectives_intro":"one sentence","objectives":["To ..."]}',
    "suggestions": '{"intro":"one sentence","groups":[{"audience":"English teachers","items":["concrete suggestion", "..."]},'
    '{"audience":"students","items":["..."]},{"audience":"future researchers","items":["..."]}]}  (each group 1-3 items)',
    "findings": '{"themes":[{"title":"short theme name","description":"one paragraph explaining what this theme covers and how it '
    'answers a research question, WITHOUT stating any result","data_needed":["what evidence the student must insert", "..."]}]}'
    "  (3-5 themes, 2-3 data_needed each)",
}


def _clean(s) -> str:
    return " ".join(str(s or "").split()).strip()


def _list(data: dict, *keys: str, questions: bool = False) -> list[str]:
    """Ambil daftar dari kunci mana pun yang dipakai LLM; string tunggal dipecah menjadi butir."""
    pattern = r"(?<=\?)\s+|\n+|(?:^|\s)\d{1,2}[.)]\s+" if questions else r"\n+|(?:^|\s)\d{1,2}[.)]\s+"
    for k in keys:
        v = data.get(k)
        if isinstance(v, str):
            v = [v]
        if isinstance(v, list) and v:
            raw = [str(x.get("text") or x.get("question") or x.get("objective") or "") if isinstance(x, dict) else str(x) for x in v]
            # Satu elemen bisa memuat beberapa butir bernomor yang dipisah baris baru (terlihat pada NIM).
            return [p for item in raw for p in re.split(pattern, item) if p.strip()]
    return []


def compose(kind: str, data: dict, language: str) -> str:
    """JSON -> naskah. Melempar ValueError bila isi wajib kurang."""
    en = language == "en"
    lines: list[str] = []
    if kind in ("rq", "rq_obj"):
        qs = [_clean(re.sub(r"^\d{1,2}[.)]\s*", "", q)).rstrip("?.") + "?" for q in _list(data, "questions", "research_questions", "rumusan_masalah", questions=True) if _clean(q)]
        if len(qs) < 2:
            raise ValueError("kurang dari 2 rumusan masalah")
        lines += [_clean(data.get("intro")) or ("The research questions of this study are as follows:" if en else "Rumusan masalah penelitian ini adalah sebagai berikut:")]
        lines += [f"{i}. {q}" for i, q in enumerate(qs, 1)]
    if kind in ("objectives", "rq_obj"):
        objs = [_clean(re.sub(r"^\d{1,2}[.)]\s*", "", o)).rstrip(".") + "." for o in _list(data, "objectives", "research_objectives", "tujuan") if _clean(o)]
        if len(objs) < 2:
            raise ValueError("kurang dari 2 tujuan penelitian")
        intro = _clean(data.get("objectives_intro") if kind == "rq_obj" else data.get("intro"))
        lines += [intro or ("In line with the research questions, the objectives of this study are:" if en else "Sejalan dengan rumusan masalah, tujuan penelitian ini adalah:")]
        lines += [f"{i}. {o}" for i, o in enumerate(objs, 1)]
    if kind == "suggestions":
        groups = [g for g in data.get("groups") or [] if isinstance(g, dict) and [i for i in g.get("items") or [] if _clean(i)]]
        total = sum(len([i for i in g["items"] if _clean(i)]) for g in groups)
        if total < 3:
            raise ValueError("kurang dari 3 butir saran")
        lines.append(_clean(data.get("intro")) or ("Based on the findings, the following suggestions are proposed:" if en else "Berdasarkan temuan penelitian, diajukan saran berikut:"))
        n = 0
        for g in groups:
            audience = _clean(g.get("audience"))
            lines.append(f"{'For' if en else 'Bagi'} {audience}:" if audience else "")
            for item in g["items"]:
                if _clean(item):
                    n += 1
                    lines.append(f"{n}. {_clean(item).rstrip('.')}.")
    if kind == "findings":
        themes = [t for t in data.get("themes") or [] if isinstance(t, dict) and _clean(t.get("title"))]
        if len(themes) < 2:
            raise ValueError("kurang dari 2 tema temuan")
        lines.append(
            "The findings are organised into the following themes. The bracketed placeholders mark the field data "
            "(interview excerpts, observations, counts) that must be inserted from the actual research before this "
            "chapter can be considered complete."
            if en
            else "Temuan penelitian disusun dalam tema-tema berikut. Penanda dalam kurung siku menandai data lapangan "
            "(kutipan wawancara, hasil observasi, jumlah) yang wajib diisi dari penelitian sebenarnya sebelum bab ini dianggap selesai."
        )
        for i, t in enumerate(themes, 1):
            lines.append(f"{'Theme' if en else 'Tema'} {i}: {_clean(t['title']).rstrip('.')}")
            if _clean(t.get("description")):
                lines.append(_clean(t["description"]))
            needs = [_clean(d) for d in t.get("data_needed") or [] if _clean(d)] or ["supporting evidence" if en else "bukti pendukung"]
            lines += [f"[DATA: {d.rstrip('.')}]" for d in needs]
    return "\n".join(l for l in lines if l)


async def structured_draft(
    kind: str, section: dict, context_prompt: str, language: str, markers: list[str], others: list[str]
) -> tuple[str, str]:
    """Kembalikan (naskah, penyedia). Melempar LLMUnavailable bila bentuk wajib tidak bisa dipenuhi."""
    en = language == "en"
    system = (
        "You fill a JSON structure for one thesis section. Write in "
        + ("formal academic English" if en else "Bahasa Indonesia baku (EYD V)")
        + ". Be specific to the study's title, variables and context. Do not invent data, numbers, quotes, or names. "
        "You may end a sentence with one of the given citation markers exactly as written. Respond with JSON only, shape: "
        + _SCHEMAS[kind]
    )
    convo = [{"role": "system", "content": system}, {"role": "user", "content": context_prompt}]
    last = "tidak ada jawaban"
    for _ in range(2):
        raw, provider = await llm_chat_ex(convo, tier="heavy", temperature=0.3, max_tokens=2600)
        try:
            text = compose(kind, extract_json(raw), language)
        except ValueError as exc:
            last = str(exc)
            convo = convo + [{"role": "assistant", "content": raw}, {"role": "user", "content": f"Invalid: {last}. Return the JSON again, complete."}]
            continue
        text, _ = dedupe_paragraphs(text, others)
        items = len(re.findall(r"(?m)^\d{1,2}\. \S", text)) + text.count("[DATA:")
        if items < 2:
            last = "butir wajib hilang karena mengulang subbab lain"
            continue
        return polish(text, markers), provider
    raise LLMUnavailable(f"Subbab {section['section_code']} tidak dapat disusun: {last}")
