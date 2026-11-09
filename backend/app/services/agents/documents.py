"""Agen dokumen pendukung: abstrak/kata pengantar, lampiran instrumen, dan evaluasi latihan sidang.

Semua keluaran LLM divalidasi: angka yang tidak ada di draf ditolak (anti karangan data), kutipan bukti diverifikasi,
dan tanpa LLM hasilnya galat yang jelas, bukan teks templat.
"""

import re

from sqlalchemy.orm import Session

from app.models.models import Thesis
from app.services.agents.advisor import _norm
from app.services.agents.review import _ref_digest, _section_digest
from app.services.llm import LLMUnavailable, extract_json, llm_chat_ex


class GenerationError(Exception):
    pass


def _lang(thesis: Thesis) -> str:
    return "English" if (thesis.language or "id") == "en" else "Bahasa Indonesia baku"


def _corpus(thesis: Thesis) -> str:
    return _norm(" ".join([thesis.title, thesis.variable_x or "", thesis.variable_y or "", thesis.subject or ""] + [s.content_markdown or "" for s in thesis.sections]))


def invented_numbers(text: str, corpus: str) -> list[str]:
    """Angka (tahun diabaikan bila ada di korpus) pada keluaran yang tidak muncul di draf."""
    bad = []
    for n in re.findall(r"\d+(?:[.,]\d+)?", text):
        if n not in corpus and n.replace(",", ".") not in corpus and n.replace(".", ",") not in corpus:
            bad.append(n)
    return sorted(set(bad))


async def _ask(messages: list[dict], validate, max_tokens: int = 3500, temperature: float = 0.3):
    last = "tidak ada jawaban"
    for _ in range(2):
        try:
            raw, provider = await llm_chat_ex(messages, tier="heavy", temperature=temperature, max_tokens=max_tokens)
        except LLMUnavailable as exc:
            raise GenerationError(str(exc))
        try:
            return validate(extract_json(raw)), provider
        except ValueError as exc:
            last = str(exc)
            messages = messages + [{"role": "assistant", "content": raw}, {"role": "user", "content": f"Perbaiki: {last}. Balas HANYA JSON valid sesuai format."}]
    raise GenerationError(f"LLM menjawab tidak layak ({last})")


def _words(s: str) -> int:
    return len(re.findall(r"\w+", s or ""))


# ---------------- abstrak, kata kunci, kata pengantar ----------------

FRONT_SYSTEM = """Kamu penulis akademik yang jujur. Tulis halaman depan skripsi dari DRAF yang diberikan.
Aturan:
1. "abstract_id" (Bahasa Indonesia) dan "abstract_en" (English): 1 paragraf, 100-250 kata (secukupnya; jangan memadati dengan hal yang belum ada di draf), memuat latar masalah, tujuan, metode, subjek, dan hasil. Isi hanya hal yang ADA di draf.
2. Dilarang mengarang angka, hasil, atau temuan. Bila draf belum memuat hasil/data, tulis penanda [DATA: temuan utama] pada tempat hasil; jangan menebak.
3. "keywords_id" dan "keywords_en": 3-5 kata kunci dari judul, variabel, dan metode.
4. "preface": kata pengantar 3-4 paragraf (syukur, latar singkat penelitian, ucapan terima kasih kepada dosen pembimbing, keluarga, dan pihak lain secara umum, penutup). Jangan menyebut nama orang selain yang diberikan; untuk nama yang tidak diberikan tulis peran saja (mis. "dosen pembimbing").
5. Bahasa preface mengikuti bahasa skripsi: {lang}.
Tanggapi HANYA JSON: {{"abstract_id":"","abstract_en":"","keywords_id":[],"keywords_en":[],"preface":""}}"""


async def generate_front_matter(thesis: Thesis, db: Session) -> tuple[dict, str]:
    digest = _section_digest(thesis, limit=14, per_section=700)
    if not digest:
        raise GenerationError("Belum ada draf subbab (minimal 50 kata). Buat draf di Langkah 4 dulu.")
    advisor = (thesis.cover_json or {}).get("advisor1", "")
    corpus = _corpus(thesis)
    user = (
        f"Judul: {thesis.title}\nMetode: {thesis.research_method} · Jenjang: {thesis.degree_level}\n"
        f"Variabel X: {thesis.variable_x or '-'} · Variabel Y: {thesis.variable_y or '-'} · Subjek: {thesis.subject or '-'}\n"
        f"Dosen pembimbing I: {advisor or '(tidak diberikan)'}\nRujukan:\n{_ref_digest(thesis, db, 8)}\n\nDRAF:\n{digest}"
    )

    def validate(d: dict) -> dict:
        out = {}
        for k in ("abstract_id", "abstract_en", "preface"):
            v = " ".join(str(d.get(k, "")).split()) if k != "preface" else "\n\n".join(" ".join(p.split()) for p in re.split(r"\n\s*\n", str(d.get(k, ""))) if p.strip())
            out[k] = v
        for k in ("abstract_id", "abstract_en"):
            if not 60 <= _words(out[k]) <= 320:
                raise ValueError(f"{k} harus 100-250 kata (sekarang {_words(out[k])})")
            bad = invented_numbers(out[k].replace("[DATA", ""), corpus)
            if bad:
                raise ValueError(f"{k} memuat angka yang tidak ada di draf: {', '.join(bad[:5])}. Hapus atau ganti penanda [DATA: ...]")
        if _words(out["preface"]) < 60:
            raise ValueError("preface terlalu pendek")
        for k in ("keywords_id", "keywords_en"):
            kw = [" ".join(str(x).split()) for x in (d.get(k) or []) if str(x).strip()][:5]
            if len(kw) < 3:
                raise ValueError(f"{k} minimal 3 kata kunci")
            out[k] = kw
        return out

    data, provider = await _ask([{"role": "system", "content": FRONT_SYSTEM.format(lang=_lang(thesis))}, {"role": "user", "content": user}], validate)
    return data, provider


# ---------------- lampiran instrumen ----------------

APPENDIX_SYSTEM = """Kamu perancang instrumen penelitian. Buat DRAF lampiran instrumen dari konteks penelitian berikut.
Aturan:
1. Jenis dokumen yang diminta: {kinds}. Satu objek per jenis.
2. Kuesioner: kelompokkan per variabel/indikator, 8-12 pernyataan per variabel, skala Likert 1-5 (cantumkan keterangan skala di "intro"). Pedoman wawancara: 8-12 pertanyaan terbuka yang menjawab rumusan masalah, urut dari umum ke spesifik. Angket validasi ahli: 8-12 aspek penilaian dengan skala 1-4.
3. Setiap butir menyebut konsep dari variabel/subjek/judul yang diberikan. Dilarang butir generik, dilarang mengarang data, nama responden, atau hasil.
4. Bahasa: {lang}. "intro" menjelaskan tujuan, petunjuk pengisian, dan catatan bahwa instrumen perlu divalidasi dosen pembimbing/ahli sebelum dipakai.
Tanggapi HANYA JSON: {{"appendices":[{{"kind":"kuesioner|wawancara|validasi","title":"","intro":"","items":["",""]}}]}}"""

_KINDS = {
    "KUANTITATIF": ["kuesioner"],
    "KUALITATIF": ["wawancara"],
    "MIXED_METHODS": ["kuesioner", "wawancara"],
    "RND": ["kuesioner", "validasi"],
}


async def generate_appendices(thesis: Thesis, db: Session) -> tuple[list[dict], str]:
    kinds = _KINDS.get(thesis.research_method, ["kuesioner"])
    rq = next((s.content_markdown for s in thesis.sections if re.search(r"rumusan|research question", s.section_title, re.I) and s.content_markdown), "")
    user = (
        f"Judul: {thesis.title}\nMetode: {thesis.research_method}\nVariabel X: {thesis.variable_x or '-'} · Variabel Y: {thesis.variable_y or '-'} · Subjek: {thesis.subject or '-'}\n"
        f"Rumusan masalah (dari draf):\n{rq[:900] or '(belum ditulis; turunkan dari judul dan variabel)'}"
    )

    def validate(d: dict) -> list[dict]:
        items = d.get("appendices")
        if not isinstance(items, list) or not items:
            raise ValueError("appendices kosong")
        out = []
        for a in items:
            if not isinstance(a, dict):
                continue
            its = []
            for x in a.get("items") or []:
                t = " ".join(str(x).split())
                if len(t) >= 12 and t.lower() not in {i.lower() for i in its}:
                    its.append(t)
            if len(its) < 5:
                continue
            kind = str(a.get("kind", "")).lower()
            out.append({"kind": kind if kind in {"kuesioner", "wawancara", "validasi"} else kinds[0], "title": " ".join(str(a.get("title", "")).split())[:150] or "Instrumen", "intro": " ".join(str(a.get("intro", "")).split()), "items": its[:40]})
        if not out:
            raise ValueError("tidak ada lampiran dengan minimal 5 butir")
        return out

    data, provider = await _ask([{"role": "system", "content": APPENDIX_SYSTEM.format(kinds=", ".join(kinds), lang=_lang(thesis))}, {"role": "user", "content": user}], validate, temperature=0.5)
    for i, a in enumerate(data, start=1):
        a["id"] = f"L{i}"
    return data, provider


# ---------------- evaluasi latihan sidang ----------------

DEFENSE_DIMS = [("isi", "Ketepatan isi", 5), ("dasar", "Dasar bukti dan rujukan", 5), ("jelas", "Kejelasan dan ketegasan", 5)]

DEFENSE_SYSTEM = """RUBRIK PENGUJI. Kamu dosen penguji yang adil tetapi tegas. Nilai JAWABAN mahasiswa atas PERTANYAAN sidang, berdasarkan DRAF skripsinya.
Dimensi (skor 0-5, 3 = jawaban cukup untuk mahasiswa S1, 5 hampir sempurna dan jarang):
- isi: menjawab inti pertanyaan secara benar dan tepat sasaran.
- dasar: bersandar pada isi draf, data, atau rujukan; bukan klaim tanpa dasar.
- jelas: runtut, ringkas, tidak berputar-putar.
Aturan: "bukti" = kutipan PERSIS (maks 25 kata) dari JAWABAN mahasiswa yang mendasari skormu (kosong bila jawaban tidak memuat apa pun yang layak); kritik harus spesifik; dilarang memuji hal yang tidak ada di jawaban; dilarang mengarang data pada "jawaban_lebih_baik" (pakai isi draf atau katakan apa yang harus disiapkan). Bahasa: {lang}.
Tanggapi HANYA JSON: {{"dimensi":{{"isi":{{"skor":0,"bukti":"","kritik":""}},"dasar":{{...}},"jelas":{{...}}}},"kekuatan":"","perbaikan":["",""],"jawaban_lebih_baik":""}}"""


async def evaluate_defense(thesis: Thesis, db: Session, question: str, answer: str) -> tuple[dict, str]:
    if _words(answer) < 5:
        raise GenerationError("Jawaban terlalu pendek untuk dinilai.")
    user = f"Judul: {thesis.title}\nRujukan:\n{_ref_digest(thesis, db, 8)}\n\nDRAF:\n{_section_digest(thesis, limit=12, per_section=500)}\n\nPERTANYAAN: {question}\n\nJAWABAN MAHASISWA: {answer}"
    ans_norm = _norm(answer)

    def validate(d: dict) -> dict:
        dims = d.get("dimensi")
        if not isinstance(dims, dict):
            raise ValueError("dimensi tidak ada")
        out, total = [], 0
        for key, label, mx in DEFENSE_DIMS:
            x = dims.get(key)
            if not isinstance(x, dict):
                raise ValueError(f"dimensi {key} tidak ada")
            try:
                score = max(0, min(5, int(round(float(x.get("skor"))))))
            except (TypeError, ValueError):
                raise ValueError(f"skor {key} bukan angka")
            quote = _norm(str(x.get("bukti", ""))).strip(" .…\"'")
            verified = len(quote.split()) >= 3 and quote in ans_norm
            if score >= 3 and not verified:
                score = 2
            if _words(answer) < 20:
                score = min(score, 2)
            total += score
            out.append({"key": key, "label": label, "score": score, "max": mx, "critique": " ".join(str(x.get("kritik", "")).split()), "verified": verified})
        return {
            "score": round(100 * total / (5 * len(DEFENSE_DIMS))),
            "dimensions": out,
            "strength": " ".join(str(d.get("kekuatan", "")).split()),
            "improvements": [" ".join(str(i).split()) for i in (d.get("perbaikan") or []) if str(i).strip()][:4],
            "better_answer": " ".join(str(d.get("jawaban_lebih_baik", "")).split()),
        }

    return await _ask([{"role": "system", "content": DEFENSE_SYSTEM.format(lang=_lang(thesis))}, {"role": "user", "content": user}], validate, max_tokens=2200, temperature=0.2)
