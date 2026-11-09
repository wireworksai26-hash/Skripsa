import hashlib
import math
import threading

import numpy as np

try:
    import faiss  # type: ignore

    FAISS_AVAILABLE = True
except Exception:  # pragma: no cover
    faiss = None
    FAISS_AVAILABLE = False

DIM = 1024


class HashingVectorizer:
    """Embedding deterministik berbasis n-gram TF-IDF — tanpa unduhan model.

    Dipakai sebagai fallback; kalau NIM tersedia, embedding API dapat
    disambung dengan mengganti fungsi embed().
    """

    def embed(self, text: str) -> np.ndarray:
        vec = np.zeros(DIM, dtype=np.float32)
        tokens = [t for t in "".join(c.lower() if c.isalnum() else " " for c in text).split() if t]
        if not tokens:
            return vec

        counts: dict[int, int] = {}
        grams = tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]
        for g in grams:
            idx = int.from_bytes(hashlib.md5(g.encode()).digest()[:2], "big") % DIM
            counts[idx] = counts.get(idx, 0) + 1

        for idx, tf in counts.items():
            vec[idx] = (1 + math.log(tf)) / math.sqrt(len(grams))
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec


class VectorStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()  # add() memanggil remove() sambil memegang kunci
        self._ids: list[str] = []
        self._vectors = np.zeros((0, DIM), dtype=np.float32)
        self._meta: dict[str, dict] = {}
        self._index = None
        if FAISS_AVAILABLE:
            self._index = faiss.IndexFlatIP(DIM)

    def add(self, doc_id: str, text: str, meta: dict | None = None) -> None:
        v = HashingVectorizer().embed(text)
        with self._lock:
            if doc_id in self._meta:
                self.remove(doc_id)
            self._ids.append(doc_id)
            self._meta[doc_id] = meta or {}
            self._vectors = np.vstack([self._vectors, v.reshape(1, -1)])
            if self._index is not None:
                self._index.add(v.reshape(1, -1))

    def remove(self, doc_id: str) -> None:
        with self._lock:
            idx = self._ids.index(doc_id)
            self._ids.pop(idx)
            self._meta.pop(doc_id, None)
            self._vectors = np.delete(self._vectors, idx, axis=0)
            self._rebuild_index()

    def _rebuild_index(self) -> None:
        if self._index is None:
            return
        fresh = faiss.IndexFlatIP(DIM)
        if len(self._vectors):
            fresh.add(np.ascontiguousarray(self._vectors))
        self._index = fresh

    def search(self, query: str, k: int = 5, user_id: str | None = None) -> list[dict]:
        if not self._ids:
            return []
        q = HashingVectorizer().embed(query).reshape(1, -1)
        with self._lock:
            take = len(self._ids) if user_id else min(k, len(self._ids))
            if self._index is not None and len(self._vectors) == self._index.ntotal:
                scores, positions = self._index.search(q, take)
                pairs = [
                    (float(s), self._ids[p])
                    for s, p in zip(scores[0], positions[0])
                    if p >= 0
                ]
            else:
                sims = (self._vectors @ q.T).ravel()
                order = np.argsort(sims)[::-1]
                pairs = [(float(sims[i]), self._ids[i]) for i in order]
            if user_id:
                pairs = [
                    (score, did)
                    for score, did in pairs
                    if self._meta.get(did, {}).get("user_id") == user_id
                ][:k]
            else:
                pairs = pairs[:k]
            return [
                {"doc_id": did, "score": round(score, 4), "meta": self._meta.get(did, {})}
                for score, did in sorted(pairs, reverse=True)
            ]

    def size(self) -> int:
        with self._lock:
            return len(self._ids)


_store: VectorStore | None = None
_store_lock = threading.Lock()


def get_vectorstore() -> VectorStore:
    global _store
    with _store_lock:
        if _store is None:
            _store = VectorStore()
        return _store
