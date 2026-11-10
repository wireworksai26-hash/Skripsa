from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import exc as sa_exc
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import auth_required, owned_thesis
from app.models.models import Citation, Thesis, ThesisSection, TitleOption
from app.schemas.schemas import CitationIn, CitationOut, SectionOut, SectionPatch, ThesisIn, ThesisPatch
from app.routers.stats import table_out
from sqlalchemy.orm import object_session

from app.services.templates import LANGUAGES, localize_template, resolve_template, suggest_template_id, template_exists

router = APIRouter(prefix="/theses", tags=["theses"])

MAX_IMPORTED_CHARS = 600_000
MAX_CITATIONS = 500
MAX_CITATION_BATCH = 100


def _thesis_out(t: Thesis) -> dict:
    template = resolve_template(object_session(t), t.campus_template_id)
    return {
        "thesis_id": t.thesis_id,
        "title": t.title,
        "research_method": t.research_method,
        "domain_category": t.domain_category,
        "degree_level": t.degree_level,
        "language": t.language or "id",
        "campus_template_id": t.campus_template_id,
        "campus_template_name": template["campus_name"],
        "variable_x": t.variable_x,
        "variable_y": t.variable_y,
        "subject": t.subject,
        "picked_title_id": t.picked_title_id,
        "selected_ref_ids": t.selected_ref_ids or [],
        "status": t.status,
        "source_mode": t.source_mode or "NEW",
        "review_json": t.review_json or {},
        "cover": t.cover_json or {},
        "brief": t.brief_json or {},
        "front": t.front_json or {},
        "appendix": t.appendix_json or [],
        "share_token": t.share_token,
        "charts_json": t.charts_json or [],
        "diagrams_json": t.diagrams_json or [],
        "tables": [table_out(x) for x in t.tables],
        "sections": [
            {
                "section_id": s.section_id,
                "chapter_code": s.chapter_code,
                "section_code": s.section_code,
                "section_title": s.section_title,
                "content_markdown": s.content_markdown,
                "citations_json": s.citations_json or [],
                "word_count": s.word_count,
                "target_words": s.target_words,
                "version_number": s.version_number,
                "origin": s.origin or "GENERATED",
            }
            for s in t.sections
        ],
    }


def _clean_brief(brief) -> dict | None:
    """Simpan hanya bagian yang diisi; kosong semua = tidak ada kerangka."""
    if brief is None:
        return None
    def tidy(key: str, v: str) -> str:
        if key == "theory":  # daftar rujukan: satu per baris, jadi pemisah baris dipertahankan
            return "\n".join(" ".join(line.split()) for line in v.splitlines() if line.strip())
        return " ".join(v.split())

    data = {k: tidy(k, v) for k, v in brief.model_dump().items() if v and v.strip()}
    return data or None


def _add_missing_sections(thesis: Thesis, db: Session) -> list[str]:
    """Lengkapi subbab dari templat; subbab yang sudah ada (mis. hasil impor) tidak disentuh."""
    template = localize_template(resolve_template(db, thesis.campus_template_id), thesis.language or "id")
    existing = {s.section_code for s in thesis.sections}
    created = []
    for ch in template["chapters"]:
        for plan in ch["sub_sections"]:
            if plan["code"] in existing:
                continue
            db.add(
                ThesisSection(
                    thesis_id=thesis.thesis_id,
                    chapter_code=str(ch["chapter_number"]),
                    section_code=plan["code"],
                    section_title=plan["title"],
                    target_words=plan["target_words"],
                    content_markdown="",
                    citations_json=[],
                )
            )
            created.append(plan["code"])
    return created


def _word_count(text: str) -> int:
    return len([w for w in text.split() if any(c.isalnum() for c in w)])


@router.post("", status_code=201)
def create_thesis(
    payload: ThesisIn,
    user=Depends(auth_required),
    db: Session = Depends(get_db),
):
    template_id = payload.template_id or suggest_template_id(payload.method, payload.degree_level)
    if not template_exists(db, template_id, user.user_id):
        raise HTTPException(422, "Templat tidak dikenal atau bukan milik Anda")
    if sum(len(item.content) for item in payload.imported_sections) > MAX_IMPORTED_CHARS:
        raise HTTPException(413, "Isi naskah impor terlalu besar")
    language = payload.language if payload.language in LANGUAGES else "id"
    existing = payload.existing_title is not None or bool(payload.imported_sections)
    thesis = Thesis(
        user_id=user.user_id,
        title=(payload.existing_title or payload.topic).strip(),
        research_method=payload.method if payload.method in ("KUANTITATIF", "KUALITATIF", "MIXED_METHODS", "RND") else "KUANTITATIF",
        domain_category=payload.domain if payload.domain in ("INFORMATIKA", "ENGLISH_EDUCATION", "UMUM") else "UMUM",
        degree_level=payload.degree_level,
        language=language,
        campus_template_id=template_id,
        variable_x=payload.variable_x,
        variable_y=payload.variable_y,
        subject=payload.subject,
        selected_ref_ids=[],
        source_mode="EXISTING" if existing else "NEW",
        brief_json=_clean_brief(payload.brief),
    )
    db.add(thesis)
    db.flush()

    if payload.existing_title:
        # Judul milik pengguna dikunci sebagai pilihan judul, bukan dibuat ulang oleh agen.
        option = TitleOption(thesis_id=thesis.thesis_id, text=thesis.title, rationale="Judul dari Anda", gap="")
        db.add(option)
        db.flush()
        thesis.picked_title_id = option.title_id

    if payload.imported_sections:
        template = resolve_template(db, template_id)
        plan = {s["code"]: s for ch in template["chapters"] for s in ch["sub_sections"]}
        seen: set[str] = set()
        for item in payload.imported_sections:
            content = item.content.strip()
            if item.section_code in seen or not content:
                continue
            seen.add(item.section_code)
            db.add(
                ThesisSection(
                    thesis_id=thesis.thesis_id,
                    chapter_code=item.section_code.split(".")[0],
                    section_code=item.section_code,
                    section_title=item.title.strip(),
                    target_words=plan.get(item.section_code, {}).get("target_words", 400),
                    content_markdown=content,
                    citations_json=[],
                    word_count=_word_count(content),
                    origin="IMPORTED",
                )
            )
        db.flush()
        db.refresh(thesis)
        _add_missing_sections(thesis, db)

    try:
        db.commit()
    except sa_exc.StatementError as exc:
        db.rollback()
        raise HTTPException(422, str(exc))
    db.refresh(thesis)
    return _thesis_out(thesis)


def _summary(t: Thesis) -> dict:
    words = sum(_word_count(x.content_markdown or "") for x in t.sections)
    stamps = [t.updated_at, t.created_at] + [x.updated_at for x in t.sections if x.updated_at]
    last = max((d for d in stamps if d), default=None)

    def score(agent: str):
        v = (t.review_json or {}).get(agent) or {}
        return v.get("score") if v.get("done") else None

    return {
        "thesis_id": t.thesis_id,
        "title": t.title,
        "status": t.status,
        "source_mode": t.source_mode or "NEW",
        "domain": t.domain_category,
        "method": t.research_method,
        "degree_level": t.degree_level,
        "template_id": t.campus_template_id,
        "created_at": t.created_at,
        "updated_at": last,
        "words": words,
        "target_words": sum(x.target_words or 0 for x in t.sections),
        "sections_total": len(t.sections),
        "sections_filled": sum(1 for x in t.sections if _word_count(x.content_markdown or "") >= 10),
        "sections_imported": sum(1 for x in t.sections if x.origin == "IMPORTED" and (x.content_markdown or "").strip()),
        "refs_selected": len(t.selected_ref_ids or []),
        "charts": len(t.charts_json or []) + len(t.diagrams_json or []),
        "tables": len(t.tables),
        "revisions": len(t.versions),
        "review": {"advisor": score("ADVISOR"), "examiner": score("EXAMINER"), "guardrail": score("GUARDRAIL")},
    }


@router.get("")
def list_theses(user=Depends(auth_required), db: Session = Depends(get_db)):
    theses = db.query(Thesis).filter(Thesis.user_id == user.user_id).all()
    rows = [_summary(t) for t in theses]
    rows.sort(key=lambda r: r["updated_at"].isoformat() if r["updated_at"] else "", reverse=True)
    return rows


@router.get("/{thesis_id}")
def get_thesis(thesis: Thesis = Depends(owned_thesis)):
    return _thesis_out(thesis)


@router.patch("/{thesis_id}")
def patch_thesis(
    payload: ThesisPatch,
    thesis: Thesis = Depends(owned_thesis),
    db: Session = Depends(get_db),
):
    if payload.title is not None:
        thesis.title = payload.title
    if payload.picked_title_id is not None:
        thesis.picked_title_id = payload.picked_title_id
    if payload.selected_ref_ids is not None:
        thesis.selected_ref_ids = payload.selected_ref_ids[:15]
    if payload.status is not None:
        thesis.status = payload.status
    if payload.cover is not None:
        thesis.cover_json = payload.cover.model_dump()
    if payload.brief is not None:
        thesis.brief_json = _clean_brief(payload.brief)
    db.commit()
    return _thesis_out(thesis)


@router.delete("/{thesis_id}", status_code=204)
def delete_thesis(thesis: Thesis = Depends(owned_thesis), db: Session = Depends(get_db)):
    from app.models.models import CustomTemplate

    scoped = db.get(CustomTemplate, f"custom-{thesis.thesis_id}")
    if scoped:
        db.delete(scoped)
    db.delete(thesis)
    db.commit()


@router.post("/{thesis_id}/sections/build")
def build_sections(thesis: Thesis = Depends(owned_thesis), db: Session = Depends(get_db)):
    created = _add_missing_sections(thesis, db)
    try:
        db.commit()
    except sa_exc.IntegrityError:
        # Permintaan build lain sudah membuat subbab yang sama: hasilnya identik, jadi anggap sukses.
        db.rollback()
        created = []
    return {"created": created, "total": len(thesis.sections)}


@router.get("/{thesis_id}/sections", response_model=list[SectionOut])
def list_sections(thesis: Thesis = Depends(owned_thesis), db: Session = Depends(get_db)):
    rows = (
        db.query(ThesisSection)
        .filter(ThesisSection.thesis_id == thesis.thesis_id)
        .order_by(ThesisSection.section_code)
        .all()
    )
    return [
        SectionOut(
            section_id=r.section_id,
            chapter_code=r.chapter_code,
            section_code=r.section_code,
            section_title=r.section_title,
            content_markdown=r.content_markdown,
            citations_json=r.citations_json or [],
            word_count=r.word_count,
            target_words=r.target_words,
            version_number=r.version_number,
            origin=r.origin or "GENERATED",
        )
        for r in rows
    ]

@router.patch("/{thesis_id}/sections/{section_code}")
def patch_section(
    section_code: str,
    payload: SectionPatch,
    thesis: Thesis = Depends(owned_thesis),
    db: Session = Depends(get_db),
):
    section = (
        db.query(ThesisSection)
        .filter(ThesisSection.thesis_id == thesis.thesis_id, ThesisSection.section_code == section_code)
        .first()
    )
    if not section:
        raise HTTPException(404, "Subbab tidak ditemukan")
    if payload.content_markdown is not None:
        before = section.word_count or 0
        section.content_markdown = payload.content_markdown
        section.word_count = sum(1 for w in section.content_markdown.split() if any(c.isalnum() for c in w))
        from app.services.insights import record_words

        record_words(db, thesis.user_id, section.word_count - before)
        section.version_number += 1
    db.commit()
    return {"ok": True, "section_code": section.section_code, "word_count": section.word_count}


@router.post("/{thesis_id}/citations", response_model=list[CitationOut], status_code=201)
def add_citations(
    items: list[CitationIn],
    thesis: Thesis = Depends(owned_thesis),
    db: Session = Depends(get_db),
):
    if len(items) > MAX_CITATION_BATCH:
        raise HTTPException(413, f"Maksimal {MAX_CITATION_BATCH} rujukan per permintaan")
    existing_count = db.query(Citation).filter(Citation.thesis_id == thesis.thesis_id).count()
    if existing_count + len(items) > MAX_CITATIONS:
        raise HTTPException(422, f"Maksimal {MAX_CITATIONS} rujukan per skripsi")
    out = []
    for item in items:
        existing = (
            db.query(Citation)
            .filter(Citation.thesis_id == thesis.thesis_id, Citation.title == item.title)
            .first()
        )
        if existing:
            out.append(existing)
            continue
        row = Citation(thesis_id=thesis.thesis_id, **item.model_dump())
        db.add(row)
        out.append(row)
    db.commit()
    result = []
    for r in out:
        if not r.citation_id:
            db.refresh(r)
        result.append(CitationOut(
            citation_id=r.citation_id,
            doi=r.doi,
            title=r.title,
            authors=r.authors or [],
            publication_year=r.publication_year,
            journal_name=r.journal_name,
            volume_issue=r.volume_issue,
            page_range=r.page_range,
            pdf_url=r.pdf_url,
            highlighted_snippet=r.highlighted_snippet,
            page_number=r.page_number,
            source_database=r.source_database,
            cited_by=r.cited_by or 0,
        ))
    return result


@router.get("/{thesis_id}/citations", response_model=list[CitationOut])
def list_citations(thesis: Thesis = Depends(owned_thesis), db: Session = Depends(get_db)):
    rows = db.query(Citation).filter(Citation.thesis_id == thesis.thesis_id).all()
    return [
        CitationOut(
            citation_id=r.citation_id,
            doi=r.doi,
            title=r.title,
            authors=r.authors or [],
            publication_year=r.publication_year,
            journal_name=r.journal_name,
            volume_issue=r.volume_issue,
            page_range=r.page_range,
            pdf_url=r.pdf_url,
            highlighted_snippet=r.highlighted_snippet,
            page_number=r.page_number,
            source_database=r.source_database,
            cited_by=r.cited_by or 0,
        )
        for r in rows
    ]


@router.get("/{thesis_id}/titles")
def list_titles(thesis: Thesis = Depends(owned_thesis), db: Session = Depends(get_db)):
    return [
        {
            "title_id": t.title_id,
            "text": t.text,
            "rationale": t.rationale,
            "gap": t.gap,
        }
        for t in db.query(TitleOption).filter(TitleOption.thesis_id == thesis.thesis_id).all()
    ]
