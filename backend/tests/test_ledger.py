"""Buku bukti sitasi dan pelacakan naskah jadi."""

from app.services import foundational
from app.services.citation_ledger import sentence_around, split_bibliography

ABSTRACT = "Scaffolding helps students write descriptive texts. Teachers provide temporary support during writing tasks."


def _thesis(client, h, suffix):
    r = client.post("/theses", headers=h, json={"topic": "Pengaruh Scaffolding terhadap Kemampuan Menulis Teks Deskriptif" + suffix, "method": "KUANTITATIF", "language": "en"})
    tid = r.json()["thesis_id"]
    client.post(f"/theses/{tid}/sections/build", headers=h)
    cites = client.post(
        f"/theses/{tid}/citations", headers=h,
        json=[
            {"title": "Scaffolding in writing instruction", "authors": ["Nur, Ahmad"], "publication_year": 2021, "highlighted_snippet": ABSTRACT, "source_database": "OpenAlex", "doi": "10.1234/abc"},
            {"title": "Unused reference about motivation", "authors": ["Lopez, Maria"], "publication_year": 2018, "highlighted_snippet": "Motivation drives learning.", "source_database": "Crossref"},
        ],
    ).json()
    client.patch(f"/theses/{tid}", headers=h, json={"selected_ref_ids": [c["citation_id"] for c in cites]})
    return tid, cites


def test_sentence_around_returns_the_citing_sentence():
    text = "Intro sentence here. Scaffolding improves writing (Nur, 2021). Another one follows."
    s = text.index("(Nur")
    assert sentence_around(text, s, s + 11) == "Scaffolding improves writing (Nur, 2021)."


def test_split_bibliography_joins_wrapped_lines_and_stops_at_appendix():
    text = "BAB V\nisi\nDAFTAR PUSTAKA\nNur, A. (2021). Scaffolding in writing\ninstruction. Journal of Writing, 3(1), 1-10.\nLopez, M. (2018). Unused reference about motivation. Journal, 2, 1-9.\nLAMPIRAN\nLampiran 1"
    entries = split_bibliography(text)
    assert len(entries) == 2 and "instruction. Journal of Writing" in entries[0] and "Lampiran" not in " ".join(entries)


def test_ledger_lists_where_each_reference_is_cited_with_grounding(client, auth):
    h = auth["headers"]
    tid, cites = _thesis(client, h, " led1")
    nur = next(c for c in cites if c["title"].startswith("Scaffolding"))
    code = client.get(f"/theses/{tid}", headers=h).json()["sections"][0]["section_code"]
    client.patch(f"/theses/{tid}/sections/{code}", headers=h, json={"content_markdown": "Opening remark. Scaffolding improves descriptive writing (Nur, 2021). Closing remark."})
    r = client.get(f"/theses/{tid}/citation-ledger", headers=h)
    assert r.status_code == 200, r.text
    led = r.json()
    nur_entry = next(e for e in led["entries"] if e["citation_id"] == nur["citation_id"])
    assert nur_entry["status"] == "cited" and nur_entry["doi_url"] == "https://doi.org/10.1234/abc"
    use = nur_entry["uses"][0]
    assert use["section"] == code and use["sentence"] == "Scaffolding improves descriptive writing (Nur, 2021)."
    assert nur_entry["evidence"] == ABSTRACT
    lopez = next(e for e in led["entries"] if e["authors"][0].startswith("Lopez"))
    assert lopez["status"] == "uncited" and led["totals"]["cited"] == 1 and led["totals"]["uncited"] == 1


def test_ledger_requires_ownership(client, auth):
    tid, _ = _thesis(client, auth["headers"], " led2")
    assert client.get(f"/theses/{tid}/citation-ledger").status_code in (401, 403)


FINAL = """BAB I PENDAHULUAN
1.1 Latar Belakang
Scaffolding improves descriptive writing (Nur, 2021). Technology also matters (Smith, 2019). Ghost claims appear too (Ghost, 2020). Another view (Nur, 2020) differs.
DAFTAR PUSTAKA
Nur, A. (2021). Scaffolding in writing instruction. Journal of Writing, 3(1), 1-10.
Smith, J. (2019). Technology in language classrooms and its effects. Journal of Tech, 5, 20-30.
Lopez, M. (2018). Unused reference about motivation. Journal, 2, 1-9.
"""


def test_track_upload_separates_tracked_unverified_missing_and_year_mismatch(client, auth):
    h = auth["headers"]
    tid, cites = _thesis(client, h, " trk1")
    r = client.post(f"/theses/{tid}/citation-ledger/track", headers=h, files={"file": ("final.txt", FINAL.encode(), "text/plain")})
    assert r.status_code == 200, r.text
    out = r.json()
    s = out["summary"]
    assert s["in_text"] == 4 and s["tracked"] == 1 and s["year_mismatch"] == 1 and s["unverified"] == 1 and s["missing"] == 1
    assert [m["text"] for m in out["missing"]] == ["(Ghost, 2020)"]
    assert out["unverified"][0]["bibliography_entry"].startswith("Smith, J. (2019)")
    nur = next(e for e in out["entries"] if e["authors"][0].startswith("Nur"))
    assert nur["in_bibliography"] and {u["year_mismatch"] for u in nur["uses"]} == {False, True}
    assert out["bibliography"]["entries"] == 3 and out["bibliography"]["matched"] == 2
    assert len(out["bibliography"]["unmatched"]) == 1
    bad = client.post(f"/theses/{tid}/citation-ledger/track", headers=h, files={"file": ("x.txt", b"terlalu pendek", "text/plain")})
    assert bad.status_code == 422


def test_verify_adds_only_found_references(client, auth, monkeypatch):
    h = auth["headers"]
    tid, _ = _thesis(client, h, " ver1")

    async def fake(text):
        entry = {"raw": text.splitlines()[0], "year": 2019, "surnames": ["Smith"], "title": "Technology in language classrooms"}
        ref = {"title": "Technology in language classrooms", "authors": ["Smith, John"], "publication_year": 2019, "doi": "10.1/xyz", "source_database": "OpenAlex", "highlighted_snippet": "Technology supports language learning."}
        return {"found": [{"entry": entry, "ref": ref, "note": ""}], "not_found": [{"raw": "Ghost, G. (2020). Nothing.", "reason": "x", "closest": None}], "unparsed": []}

    monkeypatch.setattr(foundational, "resolve_all", fake)
    r = client.post(f"/theses/{tid}/citation-ledger/verify", headers=h, json={"entries": ["Smith, J. (2019). Technology in language classrooms. Journal of Tech."]})
    assert r.status_code == 200 and r.json()["added"] == 1 and len(r.json()["not_found"]) == 1
    again = client.post(f"/theses/{tid}/citation-ledger/verify", headers=h, json={"entries": ["Smith, J. (2019). Technology in language classrooms. Journal of Tech."]})
    assert again.json()["added"] == 0 and again.json()["found"][0]["already"] is True
    track = client.post(f"/theses/{tid}/citation-ledger/track", headers=h, files={"file": ("final.txt", FINAL.encode(), "text/plain")}).json()
    assert track["summary"]["unverified"] == 0 and track["summary"]["tracked"] == 2


def test_track_upload_reads_a_real_docx(client, auth):
    import io

    import docx

    d = docx.Document()
    for line in FINAL.splitlines():
        d.add_paragraph(line)
    buf = io.BytesIO()
    d.save(buf)
    h = auth["headers"]
    tid, _ = _thesis(client, h, " trk2")
    r = client.post(f"/theses/{tid}/citation-ledger/track", headers=h, files={"file": ("final.docx", buf.getvalue(), "application/octet-stream")})
    assert r.status_code == 200, r.text
    assert r.json()["summary"]["tracked"] == 1 and r.json()["filename"] == "final.docx"
