"""Advisor Agent: dosen pembimbing yang kritis.

Audit 7 Nov 2026: Advisor lama murni aturan sederhana dan selalu memuji (judul >= 5 kata = +10, dua variabel = +10),
sehingga naskah cacat tetap diberi 90. Sekarang:
  1. LLM menilai enam dimensi dengan skala 0-5 berjangkar (3 = draf mahasiswa yang memadai).
  2. Tiap skor wajib disertai kutipan persis dari draf; kutipan yang tidak ditemukan membatasi skor maksimal 2.
  3. Temuan deterministik Guardrail (duplikat, data belum ada, rujukan Anonim) membatasi skor dimensi dan total.
  4. Tanpa LLM hasilnya done=False; tidak ada skor karangan.
"""

from sqlalchemy.orm import Session

from app.models.models import Thesis
from app.services.agents.review import _note, _ref_digest, _section_digest
from app.services.llm import LLMUnavailable, extract_json, llm_chat_ex

ADVISOR_DIMS = [
    ("A", "Judul & variabel", 15),
    ("B", "Latar belakang & celah riset", 20),
    ("C", "Keselarasan rumusan, tujuan, metode", 15),
    ("D", "Landasan teori & dukungan literatur", 20),
    ("E", "Bukti, data, dan hasil", 20),
    ("F", "Orisinalitas & kejelasan tulisan", 10),
]

ADVISOR_SYSTEM = """RUBRIK PEMBIMBING. Kamu dosen pembimbing skripsi yang ketat, jujur, dan tidak basa-basi. Tugasmu menilai DRAF, bukan menyenangkan mahasiswa. Penilaian yang terlalu murah merugikan mahasiswa saat sidang.

Dimensi:
A. Judul & variabel: judul spesifik, variabel X/Y terdefinisi operasional, selaras dengan subjek dan metode.
B. Latar belakang & celah riset: masalah konkret berkonteks, celah riset eksplisit (apa yang belum diteliti), bukan pernyataan umum tentang pentingnya topik.
C. Keselarasan rumusan, tujuan, metode: rumusan masalah, tujuan, dan metode saling menjawab; metode sesuai jenis penelitian.
D. Landasan teori & dukungan literatur: teori dan temuan terdahulu dipakai untuk berargumen, bukan sekadar disebut; rujukan relevan.
E. Bukti, data, dan hasil: klaim hasil bersandar pada data nyata, bukan karangan; pembahasan membandingkan temuan dengan teori.
F. Orisinalitas & kejelasan tulisan: tidak ada pengulangan antarsubbab, tidak bertele-tele, bahasa akademik lugas.

Skala tiap dimensi 0-5 dengan jangkar tetap:
0 = tidak ada atau tidak bisa dinilai; 1 = ada tetapi cacat serius; 2 = lemah, perlu perbaikan mendasar; 3 = memadai untuk draf mahasiswa, ada kekurangan nyata; 4 = baik, kekurangan kecil; 5 = luar biasa, hampir tanpa cela (sangat jarang).

Aturan wajib:
1. Skor 3 adalah draf mahasiswa yang cukup. Skor 4-5 hanya bila kamu dapat mengutip bukti kuat. Jangan menaikkan skor karena draf panjang atau berbahasa rapi.
2. Untuk SETIAP dimensi tulis "bukti": kutipan PERSIS (8-30 kata) dari DRAF atau judul yang mendasari skormu, disalin apa adanya. Kutipan yang tidak ada di draf dianggap tanpa bukti.
3. "kritik": kelemahan spesifik dengan menyebut kode subbab (mis. 1.2) atau kata dari draf; dilarang kritik generik. "saran": satu langkah perbaikan konkret.
4. Dilarang memuji hal yang tidak ada di draf. Penanda [DATA: ...] berarti data penelitian belum ada; jangan menilai seolah data itu ada.
5. Tulis kritik dan saran dalam Bahasa Indonesia baku.

Tanggapi HANYA JSON:
{"dimensi":{"A":{"skor":0,"bukti":"...","kritik":"...","saran":"..."},"B":{...},"C":{...},"D":{...},"E":{...},"F":{...}},"kelemahan_utama":["...","..."]}"""


def _norm(text: str) -> str:
    return " ".join((text or "").lower().replace("’", "'").split())


def _corpus(thesis: Thesis) -> str:
    return _norm(thesis.title + " " + " ".join(s.content_markdown or "" for s in thesis.sections))


def _user_prompt(thesis: Thesis, db: Session, guard: dict) -> str:
    facts = guard.get("facts") or {}
    checks = "; ".join(f"{b['label']} {b['points']}/{b['max']} ({b['detail']})" for b in guard.get("breakdown", []))
    return (
        f"Judul: {thesis.title}\n"
        f"Metode: {thesis.research_method} · Jurusan: {thesis.domain_category} · Jenjang: {thesis.degree_level}\n"
        f"Variabel X: {thesis.variable_x or '-'} · Variabel Y: {thesis.variable_y or '-'} · Subjek: {thesis.subject or '-'}\n"
        f"Hasil pemeriksaan otomatis (fakta): {checks}\n"
        f"Penanda [DATA] belum terisi: {facts.get('placeholders', 0)}; pasangan paragraf duplikat: {facts.get('duplicate_pairs', 0)}; "
        f"rujukan tanpa penulis: {facts.get('anonymous_refs', 0)}\n"
        f"Rujukan terpilih:\n{_ref_digest(thesis, db, 12)}\n\n"
        f"DRAF (cuplikan per subbab):\n{_section_digest(thesis, limit=14, per_section=900)}"
    )


def parse(raw: str, corpus: str) -> tuple[dict, list[str]]:
    data = extract_json(raw)
    dims = data.get("dimensi")
    if not isinstance(dims, dict):
        raise ValueError("tidak ada objek dimensi")
    out: dict[str, dict] = {}
    for key, _label, _mx in ADVISOR_DIMS:
        d = dims.get(key)
        if not isinstance(d, dict):
            raise ValueError(f"dimensi {key} tidak ada")
        try:
            score = int(round(float(d.get("skor"))))
        except (TypeError, ValueError):
            raise ValueError(f"skor dimensi {key} bukan angka")
        quote = _norm(str(d.get("bukti", ""))).strip(" .…\"'")
        out[key] = {
            "skor": max(0, min(5, score)),
            "verified": len(quote.split()) >= 4 and quote in corpus,
            "kritik": " ".join(str(d.get("kritik", "")).split()),
            "saran": " ".join(str(d.get("saran", "")).split()),
        }
    weak = [" ".join(str(x).split()) for x in (data.get("kelemahan_utama") or []) if str(x).strip()][:3]
    return out, weak


def apply_caps(dims: dict, guard: dict) -> list[str]:
    """LLM tidak boleh memberi nilai tinggi bila pemeriksa deterministik menemukan cacat."""
    facts = guard.get("facts") or {}
    applied: list[str] = []

    def cap(key: str, mx: int, why: str):
        if dims[key]["skor"] > mx:
            dims[key]["skor"] = mx
            applied.append(f"dimensi {key} dibatasi {mx}: {why}")

    for key, d in dims.items():
        if d["skor"] >= 3 and not d["verified"]:
            cap(key, 2, "kutipan bukti tidak ditemukan di draf")
    if facts.get("duplicate_pairs"):
        cap("F", 1, "ada paragraf duplikat antarsubbab")
    if facts.get("meta_sections"):
        cap("F", 2, "ada pembuka klise tentang pentingnya subbab")
    if facts.get("placeholders"):
        cap("E", 2, "data penelitian belum terisi")
    if facts.get("anonymous_refs"):
        cap("D", 3, "ada rujukan tanpa penulis")
    return applied


async def advisor_review(thesis: Thesis, db: Session, guard: dict) -> dict:
    base = {"agent": "ADVISOR", "model_name": "Advisor Agent · Dosen Pembimbing", "done": False}
    if not _section_digest(thesis):
        return {**base, "notes": [_note("warn", "Belum ada draf subbab (minimal 50 kata) untuk dinilai. Buat draf di Langkah 4 dulu.")]}

    corpus = _corpus(thesis)
    messages = [{"role": "system", "content": ADVISOR_SYSTEM}, {"role": "user", "content": _user_prompt(thesis, db, guard)}]
    last = "tidak ada jawaban"
    for _ in range(2):
        try:
            raw, provider = await llm_chat_ex(messages, tier="heavy", temperature=0.2, max_tokens=3000)
        except LLMUnavailable as exc:
            return {**base, "notes": [_note("warn", f"Penilaian pembimbing tidak dapat dibuat: {exc}")]}
        try:
            dims, weak = parse(raw, corpus)
        except ValueError as exc:
            last = f"JSON tidak valid ({exc})"
            messages = messages + [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": "Jawabanmu bukan JSON valid atau ada dimensi yang hilang. Balas HANYA satu objek JSON dengan dimensi A sampai F lengkap."},
            ]
            continue

        applied = apply_caps(dims, guard)
        breakdown, notes = [], []
        for key, label, mx in ADVISOR_DIMS:
            d = dims[key]
            breakdown.append(
                {
                    "key": key,
                    "label": label,
                    "points": round(mx * d["skor"] / 5, 1),
                    "max": mx,
                    "detail": f"skor {d['skor']}/5" + ("" if d["verified"] else " · bukti tidak terverifikasi"),
                }
            )
            tail = f" Saran: {d['saran']}" if d["saran"] else ""
            if d["skor"] <= 2 and d["kritik"]:
                notes.append(_note("fix", f"{label} ({d['skor']}/5): {d['kritik']}{tail}"))
            elif d["skor"] == 3 and d["kritik"]:
                notes.append(_note("warn", f"{label} (3/5): {d['kritik']}{tail}"))
            elif d["skor"] >= 4 and d["verified"]:
                notes.append(_note("praise", f"{label} ({d['skor']}/5): {d['kritik'] or 'Kuat.'}"))
        notes += [_note("fix", f"Kelemahan utama: {w}") for w in weak]

        raw_total = round(sum(b["points"] for b in breakdown))
        guard_cap = guard.get("cap")
        score = min(raw_total, guard_cap) if guard_cap else raw_total
        if guard_cap and raw_total > guard_cap:
            notes.insert(0, _note("warn", f"Skor dibatasi {score} (nilai rubrik {raw_total}) karena temuan Guardrail: " + "; ".join(guard.get("caps") or []) + "."))
        notes += [_note("info", f"Koreksi otomatis: {a}.") for a in applied]
        return {
            **base,
            "model_name": f"Advisor Agent · Dosen Pembimbing ({provider})",
            "notes": notes,
            "done": True,
            "score": score,
            "breakdown": breakdown,
            "caps": guard.get("caps") or [],
        }
    return {**base, "notes": [_note("warn", f"Penilaian pembimbing tidak dapat dibuat: LLM menjawab tidak layak ({last}).")]}
