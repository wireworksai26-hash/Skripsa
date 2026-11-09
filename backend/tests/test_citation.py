import json

from app.services.citation import bibliography, in_text_marker, reference_string


REF = {
    "citation_id": "c1",
    "doi": "10.1000/example",
    "title": "Pengaruh Media Pembelajaran Terhadap Motivasi Belajar",
    "authors": ["Nur, A.", "Putri, B."],
    "publication_year": 2021,
    "journal_name": "Jurnal Pendidikan",
    "volume_issue": "5(2)",
    "page_range": "101-115",
}


def test_in_text_marker_apa():
    marker = in_text_marker("APA_7TH", REF, 0)
    assert marker == "(Nur & Putri, 2021)"


def test_in_text_marker_ieee():
    assert in_text_marker("IEEE", REF, 3) == "[4]"


def test_reference_string_apa():
    s = reference_string(REF, "APA_7TH")
    assert s.startswith("Nur, A., Putri, B. (2021)")
    assert "https://doi.org/10.1000/example" in s


def test_reference_string_ieee():
    s = reference_string(REF, "IEEE")
    assert "A. Nur" in s
    assert "doi: 10.1000/example" in s


def test_bibliography_sorted_and_prefix():
    ref_b = REF | {
        "citation_id": "c2",
        "authors": ["Ahmad, C."],
        "title": "Kualitatif Pendidikan",
    }
    items = bibliography([REF, ref_b], "APA_7TH")
    assert items[0].startswith("Ahmad, C.")
    assert items[1].startswith("Nur, A.")


def test_pipeline_dump_json_cyclic_no_op():
    payload = {"note": "data interleaved"}
    assert json.dumps(payload)
