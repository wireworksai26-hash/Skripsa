"""Retrieval tingkat kalimat atas abstrak rujukan terpilih (RAG).

Tiap kalimat abstrak diindeks sebagai satu bagian (passage). Untuk sebuah subbab, query dibentuk dari
judul subbab + topik; bagian yang paling relevan diambil, lalu dikelompokkan per rujukan. Hasilnya dipakai
penulis sebagai satu-satunya bukti yang boleh dikutip, dan kalimat itulah yang kelak disorot di PDF.
"""

import re

from app.services.vectorestore import VectorStore

_MIN_WORDS = 6
_MAX_SENTENCES = 14


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text or "").strip())
    return [p.strip() for p in parts if len(p.split()) >= _MIN_WORDS][:_MAX_SENTENCES]


def normalize(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (text or "").lower()))


def is_from_abstract(snippet: str, abstract: str) -> bool:
    """True bila snippet adalah kutipan nyata (utuh) dari abstrak, abaikan spasi/tanda baca."""
    s, a = normalize(snippet), normalize(abstract)
    return bool(s) and s in a


def retrieve(refs: list[dict], query: str, max_refs: int = 6, passages_per_ref: int = 2) -> list[dict]:
    """Urutkan rujukan berdasarkan relevansi kalimat abstraknya terhadap query; sertakan bukti ('evidence')."""
    store = VectorStore()
    by_id = {r["citation_id"]: r for r in refs}
    for r in refs:
        cid = r["citation_id"]
        title = r.get("title") or ""
        sentences = split_sentences(r.get("highlighted_snippet") or "")
        if not sentences:
            store.add(f"{cid}#title", title, {"cid": cid, "sentence": ""})
        for i, sent in enumerate(sentences):
            store.add(f"{cid}#{i}", f"{title}. {sent}", {"cid": cid, "sentence": sent})

    hits = store.search(query, k=max(store.size(), 1))
    ranked: dict[str, dict] = {}
    for h in hits:
        cid = h["meta"]["cid"]
        entry = ranked.setdefault(cid, {"score": h["score"], "evidence": []})
        sentence = h["meta"]["sentence"]
        if sentence and len(entry["evidence"]) < passages_per_ref:
            entry["evidence"].append(sentence)

    out = []
    for cid, entry in sorted(ranked.items(), key=lambda kv: kv[1]["score"], reverse=True)[:max_refs]:
        out.append({**by_id[cid], "evidence": entry["evidence"], "rag_score": entry["score"]})
    return out
