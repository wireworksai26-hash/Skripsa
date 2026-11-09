"""Quality Guardrail: pemeriksa mutu deterministik yang ketat (bukan penjumlah poin kelengkapan).

Audit 7 Nov 2026: skor lama memberi 96 pada naskah yang berisi paragraf duplikat, esai tanpa butir, dan temuan tanpa
data, karena 55% skor hanya "jumlah kata >= target". Sekarang skor = 100 poin dari enam kriteria, dan temuan berat
memasang BATAS ATAS skor (mis. ada duplikat -> maksimal 69), jadi naskah cacat tidak bisa lolos dengan nilai tinggi.
Semua poin dan batas ditampilkan agar pengguna tahu persis mengapa skornya segitu.
"""

import asyncio
import re
from datetime import date

from sqlalchemy.orm import Session

from app.models.models import Citation, Thesis
from app.services.agents.quality import (
    MAX_PARAGRAPH_WORDS,
    _shingles,
    _tokens,
    check_kind,
    paragraphs,
    section_kind,
    DUP_THRESHOLD,
)
from app.services.scientific_api import verify_doi

_META_OPENING = re.compile(
    r"(?is)^\W*(?:the\s+)?(?:formulation|development|importance|role|concept|process|analysis|preparation)\s+of\b.{0,160}?"
    r"\b(?:represents?|is\s+(?:a|an|the)\s+(?:critical|essential|fundamental|vital|key)|serves?\s+as)\b"
    r"|represents?\s+a\s+critical\s+(?:juncture|component|step)|rich\s+tapestry|"
    r"^\W*(?:pentingnya|perumusan|penyusunan)\b.{0,120}?\bmerupakan\s+(?:bagian|aspek|langkah)\s+(?:yang\s+)?(?:penting|krusial|mendasar)"
)
_CITE_AFTER_PERIOD = re.compile(r"[.!?]\s*\([A-Z][^()]*\d{4}[a-z]?\)")
_STRUCTURED = {"rq", "rq_obj", "objectives", "suggestions"}


def word_count(text: str) -> int:
    return len([w for w in (text or "").split() if any(ch.isalnum() for ch in w)])


def _code_key(code: str) -> list[int]:
    return [int(p) if p.isdigit() else 0 for p in code.split(".")]


def _point(key: str, label: str, points: float, mx: int, detail: str) -> dict:
    return {"key": key, "label": label, "points": round(max(0.0, min(points, mx)), 1), "max": mx, "detail": detail}


async def guardrail_review(thesis: Thesis, db: Session) -> dict:
    notes: list[dict] = []
    caps: list[tuple[int, str]] = []
    secs = sorted(thesis.sections, key=lambda s: _code_key(s.section_code))
    written = [s for s in secs if word_count(s.content_markdown or "") > 0]
    breakdown: list[dict] = []
    facts: dict = {}
    share = len(written) / len(secs) if secs else 0.0  # porsi subbab yang benar-benar ditulis

    def note(kind: str, text: str):
        notes.append({"kind": kind, "text": text})

    if not secs:
        note("warn", "Belum ada subbab draf untuk diperiksa.")

    # 1. Kelengkapan (15): subbab berbentuk butir memang pendek, jadi targetnya dilonggarkan.
    ratios, empty = [], []
    for s in secs:
        target = s.target_words or 0
        if not target:
            continue
        kind = section_kind(s.section_title, s.chapter_code)
        eff = target * 0.4 if kind in _STRUCTURED else target
        wc = word_count(s.content_markdown or "")
        ratios.append(min(wc / max(eff, 1), 1.0))
        if wc == 0:
            empty.append(s.section_code)
        elif wc < eff * 0.8:
            note("fix", f"[{s.section_code}] {s.section_title}: {wc} kata, di bawah 80% target ({round(eff)}).")
    cover = sum(ratios) / len(ratios) if ratios else 0.0
    breakdown.append(_point("coverage", "Kelengkapan subbab", 15 * cover, 15, f"{len(secs) - len(empty)}/{len(secs)} subbab terisi, rata-rata {round(100 * cover)}% dari target"))
    if empty:
        caps.append((74, f"{len(empty)} subbab masih kosong ({', '.join(empty[:6])})"))
        note("warn", f"{len(empty)} subbab masih kosong: {', '.join(empty[:8])}.")

    # 2. Orisinalitas internal (20): paragraf yang sama antar/intra subbab.
    items = [(s.section_code, p, _shingles(p)) for s in written for p in paragraphs(s.content_markdown) if len(_tokens(p)) >= 12]
    dups: list[tuple[str, str]] = []
    for i, (ca, pa, sa) in enumerate(items):
        for cb, pb, sb in items[i + 1 :]:
            if sa and sb and len(sa & sb) / min(len(sa), len(sb)) >= DUP_THRESHOLD:
                dups.append((ca, cb))
    facts["duplicate_pairs"] = len(dups)
    breakdown.append(_point("originality", "Tidak ada paragraf berulang", (20 - 5 * len(dups)) * share, 20, ("tidak ada paragraf duplikat" if not dups else f"{len(dups)} pasangan paragraf duplikat") + f"; dinilai pada {len(written)}/{len(secs)} subbab"))
    if dups:
        caps.append((69, f"{len(dups)} paragraf duplikat (self-plagiarism)"))
        where = ", ".join(sorted({f"{a}↔{b}" if a != b else f"{a} (di dalam subbab)" for a, b in dups})[:6])
        note("fix", f"Paragraf duplikat terdeteksi: {where}. Buat ulang subbab terkait; paragraf yang sama dianggap menyalin diri sendiri.")

    # 3. Bentuk wajib subbab (15): rumusan masalah, tujuan, saran harus berupa butir.
    form_fail, form_seen = [], 0
    for s in written:
        kind = section_kind(s.section_title, s.chapter_code)
        if kind in _STRUCTURED:
            form_seen += 1
            problem = check_kind(kind, s.content_markdown or "")
            if problem:
                form_fail.append(s.section_code)
                note("fix", f"[{s.section_code}] {s.section_title}: tidak berbentuk daftar yang diwajibkan (esai tentang subbab, bukan isinya).")
    form_pts = 15 - 5 * len(form_fail) if form_seen else 0
    breakdown.append(_point("form", "Bentuk subbab inti (rumusan, tujuan, saran)", form_pts, 15, "belum ada subbab inti yang bisa dinilai" if not form_seen else f"{form_seen - len(form_fail)}/{form_seen} berbentuk benar"))
    if form_fail:
        caps.append((74, f"subbab inti berupa esai: {', '.join(form_fail)}"))

    # 4. Bukti & sitasi (20)
    cited_ids: set[str] = set()
    need, have = 0, 0
    for s in written:
        for c in s.citations_json or []:
            cited_ids.add(c.get("reference_id"))
        if s.chapter_code == "3" or s.origin == "IMPORTED" or word_count(s.content_markdown or "") < 80:
            continue
        need += 1
        if s.citations_json:
            have += 1
        else:
            note("warn", f"[{s.section_code}] {s.section_title}: belum ada sitasi; klaim tanpa rujukan tidak lolos guardrail.")
    cov_pts = 8 * (have / need) if need else 0
    breakdown.append(_point("cite_cov", "Sitasi pada subbab isi", cov_pts, 8, f"{have}/{need} subbab isi bersitasi" if need else "belum ada subbab isi yang bisa dinilai"))

    selected = [r for r in db.query(Citation).filter(Citation.thesis_id == thesis.thesis_id).all() if r.citation_id in (thesis.selected_ref_ids or [])]
    with_doi = [r for r in selected if r.doi][:10]
    doi_status = await asyncio.gather(*[verify_doi(r.doi) for r in with_doi])
    ok = sum(1 for x in doi_status if x)
    doi_pts = 6 * (ok / len(with_doi)) if with_doi else 0
    breakdown.append(_point("doi", "DOI rujukan aktif", doi_pts, 6, f"{ok}/{len(with_doi)} DOI terverifikasi di Crossref" if with_doi else "tidak ada DOI yang bisa diverifikasi, jadi tidak diberi poin"))
    for r, alive in zip(with_doi, doi_status):
        if not alive:
            note("fix", f"DOI tidak ditemukan di Crossref: {r.doi}. Periksa ulang rujukannya.")

    cy = date.today().year
    pool = [r for r in selected if (cited_ids and r.citation_id in cited_ids) or not cited_ids]
    recent = [r for r in pool if (r.publication_year or 0) >= cy - 10]
    anonim = [r for r in pool if not r.authors or any(str(a).strip().lower() == "anonim" for a in r.authors)]
    facts["anonymous_refs"] = len(anonim)
    rec_pts = (3 * (len(recent) / len(pool)) + (3 if not anonim else 0)) if pool else 0
    breakdown.append(_point("refs_quality", "Kemutakhiran & kejelasan penulis rujukan", rec_pts, 6, f"{len(recent)}/{len(pool)} rujukan ≤10 tahun; {len(anonim)} tanpa penulis" if pool else "belum ada rujukan terpakai"))
    if anonim:
        note("fix", f"{len(anonim)} rujukan tanpa penulis ('Anonim'): ganti dengan sumber yang penulisnya jelas.")
    old = [r for r in pool if 0 < (r.publication_year or 0) < cy - 10]
    if old:
        note("warn", f"{len(old)} rujukan lebih dari 10 tahun ({', '.join(str(r.publication_year) for r in old[:5])}); banyak pedoman mewajibkan 5–10 tahun terakhir.")
    uncited = [r for r in selected if cited_ids and r.citation_id not in cited_ids]
    if uncited and len(uncited) >= max(3, len(selected) // 2):
        note("info", f"{len(uncited)} dari {len(selected)} rujukan terpilih tidak dikutip di naskah dan tidak akan masuk daftar pustaka.")

    # 5. Kejujuran data (15)
    text_all = "\n".join(s.content_markdown or "" for s in written)
    placeholders = len(re.findall(r"\[DATA", text_all, flags=re.I))
    has_results = bool(thesis.tables or thesis.charts_json or any((d.content or '').strip() for d in thesis.research_data))
    ch4 = [s for s in written if s.chapter_code == "4"]
    facts["placeholders"] = placeholders
    if placeholders:
        data_pts, detail = 8, f"{placeholders} penanda [DATA] belum diisi (jujur, tetapi bab belum selesai)"
        caps.append((79, f"{placeholders} penanda [DATA] belum diganti data penelitian"))
        note("warn", f"{placeholders} penanda [DATA: …] belum Anda ganti dengan data penelitian sebenarnya. Naskah belum layak diajukan sebelum semuanya terisi.")
    elif ch4 and not has_results:
        data_pts, detail = 4, "Bab IV ditulis tanpa data atau tabel hasil tersimpan"
        caps.append((74, "Bab IV tidak bersandar pada data yang tersimpan"))
        note("fix", "Bab IV memuat temuan, tetapi belum ada tabel/grafik hasil yang tersimpan. Klaim hasil belum bisa diverifikasi; simpan data di halaman Visual.")
    elif ch4:
        data_pts, detail = 15, "Bab IV didukung tabel/grafik hasil yang tersimpan"
    else:
        data_pts, detail = 0, "Bab IV belum ditulis"
    breakdown.append(_point("data", "Kejujuran data (Bab IV bersandar data nyata)", data_pts, 15, detail))

    # 6. Keterbacaan (15)
    penalty, giants, metas = 0, [], []
    for s in written:
        c = s.content_markdown or ""
        big = [p for p in paragraphs(c) if len(p.split()) > MAX_PARAGRAPH_WORDS + 40 and not re.match(r"^\d{1,2}[.)]\s", p)]
        if big:
            giants.append(s.section_code)
            penalty += 3
        if _META_OPENING.search(c[:400]):
            metas.append(s.section_code)
            penalty += 3
    after = len(_CITE_AFTER_PERIOD.findall(text_all))
    if after:
        penalty += 2
    facts["meta_sections"] = metas
    breakdown.append(_point("readability", "Keterbacaan & gaya akademik", (15 - penalty) * share, 15, "tidak ada paragraf raksasa/pembuka klise" if not penalty else f"{len(giants)} subbab berparagraf raksasa, {len(metas)} berpembuka klise, {after} sitasi setelah titik"))
    if giants:
        note("warn", f"Paragraf terlalu panjang (>{MAX_PARAGRAPH_WORDS + 40} kata) di subbab {', '.join(giants[:6])}; pecah menjadi 5–8 kalimat per paragraf.")
    if metas:
        caps.append((79, f"pembuka klise/meta-writing di {', '.join(metas[:4])}"))
        note("fix", f"Subbab {', '.join(metas[:6])} dibuka dengan kalimat klise tentang 'pentingnya' subbab itu, bukan isinya. Tulis langsung substansinya.")
    if after:
        note("info", f"{after} sitasi berada setelah tanda titik; pindahkan ke sebelum titik kalimat.")

    imported = [s for s in written if s.origin == "IMPORTED"]
    if imported:
        note("info", f"{len(imported)} subbab adalah tulisan Anda ({', '.join(s.section_code for s in imported[:8])}). Sitasinya tidak diverifikasi otomatis; periksa sendiri kesesuaian dengan daftar pustaka.")

    raw = round(sum(b["points"] for b in breakdown))
    cap_val = min((c for c, _ in caps), default=100)
    score = min(raw, cap_val)
    cap_notes = sorted({f"maks. {c}: {why}" for c, why in caps})
    if cap_notes:
        notes.insert(0, {"kind": "warn", "text": f"Skor dibatasi {score} (poin mentah {raw}) karena: " + "; ".join(why for _, why in sorted(caps))})
    words = sum(word_count(s.content_markdown or "") for s in secs)
    target = sum(s.target_words or 0 for s in secs)
    notes.insert(0, {"kind": "info", "text": f"Total {words} kata dari target {target} kata. Jumlah kata hanya satu dari enam kriteria dan tidak menentukan mutu."})

    return {
        "agent": "GUARDRAIL",
        "model_name": "Quality Guardrail · Validator",
        "notes": notes,
        "done": True,
        "score": score,
        "breakdown": breakdown,
        "caps": cap_notes,
        "cap": cap_val if caps else None,
        "facts": facts,
    }
