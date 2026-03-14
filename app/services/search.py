from sqlmodel import Session, select

from app.models import Photo, PhotoSearchDocument
from app.schemas import PhotoResult, SearchRequest, SearchResponse
from app.services.embedding import build_text_embedding, cosine_similarity, load_embedding
from app.services.faiss_store import search_index


def _split_tags(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def search_photos(session: Session, payload: SearchRequest) -> SearchResponse:
    query_vector = build_text_embedding(payload.query)
    statement = select(Photo, PhotoSearchDocument).join(PhotoSearchDocument, Photo.id == PhotoSearchDocument.photo_id)
    rows = session.exec(statement).all()
    rows_by_photo_id = {photo.id: (photo, document) for photo, document in rows}

    candidate_scores = dict(search_index(query_vector, max(payload.limit * 8, 64)))
    ranked_photo_ids = list(candidate_scores.keys())
    if ranked_photo_ids:
        ordered_rows = [rows_by_photo_id[photo_id] for photo_id in ranked_photo_ids if photo_id in rows_by_photo_id]
    else:
        ordered_rows = rows

    results: list[PhotoResult] = []
    for photo, document in ordered_rows:
        if payload.people_only and not document.has_person:
            continue
        if payload.face_only and not document.has_face:
            continue
        similarity = 0.0
        if document.search_vector_path:
            similarity = cosine_similarity(query_vector, load_embedding(document.search_vector_path))
        results.append(
            PhotoResult(
                id=photo.id or 0,
                original_name=photo.original_name,
                thumbnail_url=f"/assets/thumbnails/{photo.stored_name}",
                image_url=f"/assets/images/{photo.stored_name}",
                caption=document.caption,
                auto_tags=_split_tags(document.auto_tags),
                manual_tags=_split_tags(document.manual_tags),
                similarity=similarity,
                person_count=document.person_count,
                face_count=document.face_count,
            )
        )

    sorted_results = sorted(results, key=lambda item: item.similarity, reverse=True)[: payload.limit]
    return SearchResponse(query=payload.query, total=len(sorted_results), results=sorted_results)
