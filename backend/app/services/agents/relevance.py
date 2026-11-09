"""Penyaring relevansi rujukan (audit BUG-05): pencarian kata kunci menarik karya yang hanya kebetulan memuat kata
yang sama (mis. "wrap-up" dalam presentasi ilmiah, bukan pengajaran bahasa). LLM menilai tiap kandidat 0-3 terhadap
topik; nilai 0 dibuang. Bila LLM gagal, urutan semula dipertahankan (pencarian tidak boleh gagal karena penyaring)."""

from app.services.llm import LLMUnavailable, extract_json, llm_chat_ex

SYSTEM = (
    "Kamu menilai relevansi artikel ilmiah terhadap topik skripsi. Untuk setiap artikel beri skor: "
    "3 = sangat relevan (topik dan konteks sama), 2 = relevan (topik sama, konteks berbeda), "
    "1 = relevan sebagian (teori/metode yang bisa dipakai), 0 = tidak relevan (bidang, subjek, atau makna kata kunci berbeda). "
    'Tanggapi HANYA JSON: {"scores":[{"i":1,"s":2}]} untuk SEMUA nomor artikel.'
)


async def rerank(topic: str, refs: list[dict]) -> tuple[list[dict], int]:
    """Kembalikan (rujukan terurut relevansi tanpa yang bernilai 0, jumlah dibuang)."""
    if len(refs) < 3:
        return refs, 0
    lines = [
        f"{i}. {r.get('title', '')[:180]} — {(r.get('highlighted_snippet') or '')[:220]}"
        for i, r in enumerate(refs, start=1)
    ]
    user = f"Topik skripsi: {topic}\n\nArtikel:\n" + "\n".join(lines)
    try:
        raw, _ = await llm_chat_ex(
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}], tier="fast", temperature=0.0, max_tokens=900
        )
        data = extract_json(raw)
    except (LLMUnavailable, ValueError):
        return refs, 0
    scores: dict[int, int] = {}
    for item in data.get("scores") or []:
        try:
            scores[int(item["i"])] = max(0, min(3, int(item["s"])))
        except (KeyError, TypeError, ValueError):
            continue
    if not scores:
        return refs, 0
    ranked = [(scores.get(i, 1), -i, r) for i, r in enumerate(refs, start=1)]
    kept = [r for s, _, r in sorted(ranked, key=lambda x: (x[0], x[1]), reverse=True) if s > 0]
    for s, _, r in ranked:
        r["relevance"] = s
    return kept, len(refs) - len(kept)
