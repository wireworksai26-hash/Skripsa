from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import auth_required, owned_thesis
from app.core.ratelimit import limit_user
from app.models.models import Citation, RagDocument, Thesis
from app.schemas.schemas import RagIndexIn, RagSearchIn
from app.services.vectorestore import get_vectorstore

router = APIRouter(tags=["rag"])

MAX_INDEXED_REFS = 500


def _doc_text(r: Citation) -> str:
    return f"{r.title}. {r.journal_name or ''}. {r.highlighted_snippet or ''}"


@router.post("/rag/index")
def index_refs(
    payload: RagIndexIn,
    thesis: Thesis = Depends(owned_thesis),
    db: Session = Depends(get_db),
):
    limit_user(thesis.user_id, "rag-index", 12, 60)
    query = db.query(Citation).filter(Citation.thesis_id == thesis.thesis_id)
    if payload.citation_ids:
        query = query.filter(Citation.citation_id.in_(payload.citation_ids))
    refs = query.limit(MAX_INDEXED_REFS).all()

    store = get_vectorstore()
    for ref in refs:
        text = _doc_text(ref)
        meta = {
            "citation_id": ref.citation_id,
            "title": ref.title,
            "user_id": thesis.user_id,
            "thesis_id": thesis.thesis_id,
        }
        db.merge(
            RagDocument(
                doc_id=f"rag-{ref.citation_id}",
                thesis_id=thesis.thesis_id,
                source_type="citation",
                content=text,
                meta_json=meta,
            )
        )
        store.add(f"rag-{ref.citation_id}", text, meta)
    db.commit()
    return {"indexed": len(refs), "total_vectors": store.size()}


@router.post("/rag/search")
def search(payload: RagSearchIn, user=Depends(auth_required)):
    limit_user(user.user_id, "rag-search", 60, 60)
    hits = get_vectorstore().search(payload.query, k=payload.k, user_id=user.user_id)
    return {"hits": hits}
