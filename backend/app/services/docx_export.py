import re

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt

from app.services.citation import bibliography
from app.services.templates import get_template

_CENTERS = {  # perataan kiri/kanan
    "center": WD_ALIGN_PARAGRAPH.CENTER,
    "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
}

_ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII"]


def count_words(text: str) -> int:
    return len([w for w in (text or "").replace("\n", " ").split() if re.search(r"[\w\d]", w)])


def export_thesis_docx(thesis_dict: dict) -> str:
    template = thesis_dict.get("template") or get_template(thesis_dict.get("template_id", "nasional-s1-kuantitatif"))
    language = thesis_dict.get("language", "id")
    labels = (
        {
            "fallback_title": "Thesis Draft",
            "chapter": "CHAPTER",
            "references": "REFERENCES",
            "disclaimer": "Draft produced with Skripsa multi-agent assistance — an initial draft for supervision; "
            "it must be evaluated, rewritten, and approved together with the academic supervisor.",
        }
        if language == "en"
        else {
            "fallback_title": "Draf Skripsi",
            "chapter": "BAB",
            "references": "DAFTAR PUSTAKA",
            "disclaimer": "Draf dihasilkan dengan asistensi multi-agent Skripsa — "
            "draf awal bahan bimbingan, wajib dievaluasi dan ditulis ulang bersama Dosen Pembimbing.",
        }
    )
    ps = template["page_setup"]
    doc = Document()

    for section in doc.sections:
        section.page_width = Cm(21)
        section.page_height = Cm(29.7)
        margins = ps["margins_cm"]
        section.top_margin = Cm(margins["top"])
        section.left_margin = Cm(margins["left"])
        section.bottom_margin = Cm(margins["bottom"])
        section.right_margin = Cm(margins["right"])

    style = doc.styles["Normal"]
    style.font.name = ps["font_family"]
    style.font.size = Pt(ps["font_size_pt"])
    style.paragraph_format.line_spacing = ps["line_spacing"]

    def para(text, *, bold=False, italic=False, center=False, size=None, before=0, after=120, indent_cm=None):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER if center else WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.space_before = Pt(before)
        p.paragraph_format.space_after = Pt(after)
        if indent_cm:
            p.paragraph_format.first_line_indent = Cm(indent_cm)
        run = p.add_run(text)
        run.bold = bold
        run.italic = italic
        run.font.name = ps["font_family"]
        run.font.size = Pt(size or ps["font_size_pt"])
        return p

    para(thesis_dict.get("title") or labels["fallback_title"], bold=True, center=True, before=420, after=600)
    para(template["campus_name"], center=True, after=360)
    para(labels["disclaimer"], italic=True, center=True, after=240)

    sections = thesis_dict.get("sections") or []
    chapters: dict[str, list[dict]] = {}
    chapter_titles = {ch["chapter_number"]: ch["chapter_title"] for ch in template["chapters"]}
    for s in sections:
        chapters.setdefault(str(s["chapter_code"]), []).append(s)

    for chapter in sorted(chapters, key=lambda c: int(c) if c.isdigit() else 99):
        para(f"{labels['chapter']} {_ROMAN[int(chapter) - 1] if chapter.isdigit() and int(chapter) <= 7 else chapter}", bold=True, center=True, before=360, after=120)
        para(chapter_titles.get(chapter, ""), bold=True, center=True, after=360)

        for s in sorted(chapters[chapter], key=lambda x: x["section_code"]):
            if count_words(s.get("content_markdown", "")) == 0:
                continue
            para(f"{s['section_code']} {s['section_title']}", bold=True, after=240)
            for block in re.split(r"\n+", s.get("content_markdown", "")):
                block = block.strip()
                if not block:
                    continue
                block = re.sub(r"^[-*\d.]+\s*", "", block)
                para(block, indent_cm=ps["paragraph_indent_cm"])

    picked_refs = [
        {k: r[k] for k in ("authors", "title", "journal_name", "volume_issue", "page_range", "publication_year", "doi")}
        for r in (thesis_dict.get("references") or [])
    ]
    if picked_refs:
        para(labels["references"], bold=True, center=True, before=420, after=360)
        style_citation = template.get("citation_style", "APA_7TH")
        for line in bibliography(picked_refs, style_citation):
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            p.paragraph_format.left_indent = Cm(1)
            p.paragraph_format.first_line_indent = Cm(-1)
            p.paragraph_format.space_after = Pt(240)
            run = p.add_run(line)
            run.font.name = ps["font_family"]
            run.font.size = Pt(ps["font_size_pt"])

    import tempfile
    import os

    fd, path = tempfile.mkstemp(prefix="skripsi-", suffix=".docx")
    os.close(fd)
    doc.save(path)
    return path
