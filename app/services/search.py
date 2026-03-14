import re
from dataclasses import dataclass

from sqlmodel import Session, select

from app.models import Photo, PhotoSearchDocument
from app.schemas import PhotoResult, SearchRequest, SearchResponse
from app.services.embedding import build_text_embedding, cosine_similarity, load_embedding
from app.services.faiss_store import search_index


@dataclass
class QuerySignals:
    wants_person: bool
    wants_face: bool
    wants_group: bool
    wants_solo: bool
    wants_outdoor: bool
    wants_indoor: bool
    wants_day: bool
    wants_night: bool
    wants_vertical: bool
    wants_horizontal: bool
    wants_smile: bool
    keywords: list[str]


def _split_tags(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _extract_keywords(query: str) -> list[str]:
    tokens = [item.strip() for item in re.split(r"[\s,、。/・]+", query.lower()) if item.strip()]
    filtered = [token for token in tokens if len(token) >= 2]
    if filtered:
        return list(dict.fromkeys(filtered))
    normalized = _normalize_text(query)
    return [normalized] if len(normalized) >= 2 else []


def _extract_query_signals(query: str) -> QuerySignals:
    normalized = _normalize_text(query)
    return QuerySignals(
        wants_person=_contains_any(normalized, ["人物", "女性", "男性", "モデル", "ポートレート", "person", "people", "portrait", "model"]),
        wants_face=_contains_any(normalized, ["顔", "face", "selfie", "自撮り", "アップ", "closeup", "close-up", "バストアップ"]),
        wants_group=_contains_any(normalized, ["複数", "複数人", "グループ", "集合", "みんな", "group", "team", "2人", "3人", "二人", "三人"]),
        wants_solo=_contains_any(normalized, ["一人", "1人", "ひとり", "ソロ", "単独", "solo", "single person"]),
        wants_outdoor=_contains_any(normalized, ["屋外", "外", "outdoor"]),
        wants_indoor=_contains_any(normalized, ["屋内", "室内", "indoor"]),
        wants_day=_contains_any(normalized, ["昼", "日中", "明るい", "day", "bright"]),
        wants_night=_contains_any(normalized, ["夜", "夜景", "暗い", "night", "dark"]),
        wants_vertical=_contains_any(normalized, ["縦", "縦長", "vertical", "portrait orientation"]),
        wants_horizontal=_contains_any(normalized, ["横", "横長", "horizontal", "landscape"]),
        wants_smile=_contains_any(normalized, ["笑顔", "smile", "happy"]),
        keywords=_extract_keywords(query),
    )


def _build_searchable_text(photo: Photo, document: PhotoSearchDocument) -> str:
    parts = [
        photo.original_name,
        document.caption,
        document.auto_tags,
        document.manual_tags,
    ]

    if document.has_person:
        parts.extend(["人物", "person", "people", "portrait"])
    if document.has_face:
        parts.extend(["顔", "face", "closeup", "portrait"])
    if document.person_count == 1:
        parts.extend(["一人", "1人", "ソロ", "solo", "single"])
    elif document.person_count >= 2:
        parts.extend(["複数人", "グループ", "集合", "group"])

    if photo.height > photo.width:
        parts.extend(["縦", "縦長", "vertical"])
    elif photo.width > photo.height:
        parts.extend(["横", "横長", "horizontal", "landscape"])

    return _normalize_text(" ".join(parts))


def _score_keyword_matches(searchable_text: str, keywords: list[str]) -> tuple[float, list[str]]:
    matched = [keyword for keyword in keywords if keyword and keyword in searchable_text]
    unique_matches = list(dict.fromkeys(matched))
    bonus = min(len(unique_matches) * 0.025, 0.1)
    if not unique_matches:
        return 0.0, []
    preview = " / ".join(unique_matches[:3])
    return bonus, [f"語句一致: {preview}"]


def _score_query_signals(photo: Photo, document: PhotoSearchDocument, signals: QuerySignals) -> tuple[float, list[str]]:
    bonus = 0.0
    reasons: list[str] = []

    if signals.wants_person and document.has_person:
        bonus += 0.08
        reasons.append("人物あり")
    if signals.wants_face and document.has_face:
        bonus += 0.08
        reasons.append("顔あり")
    if signals.wants_group and document.person_count >= 2:
        bonus += 0.08
        reasons.append("複数人")
    if signals.wants_solo and document.person_count == 1:
        bonus += 0.08
        reasons.append("一人")
    if signals.wants_outdoor and "outdoor" in document.auto_tags.lower():
        bonus += 0.05
        reasons.append("屋外タグ")
    if signals.wants_indoor and "indoor" in document.auto_tags.lower():
        bonus += 0.05
        reasons.append("屋内タグ")
    if signals.wants_day and "day" in document.auto_tags.lower():
        bonus += 0.04
        reasons.append("昼タグ")
    if signals.wants_night and "night" in document.auto_tags.lower():
        bonus += 0.04
        reasons.append("夜タグ")
    if signals.wants_vertical and photo.height > photo.width:
        bonus += 0.03
        reasons.append("縦長")
    if signals.wants_horizontal and photo.width > photo.height:
        bonus += 0.03
        reasons.append("横長")
    if signals.wants_smile and "smile" in document.auto_tags.lower():
        bonus += 0.04
        reasons.append("笑顔タグ")

    return bonus, reasons[:3]


def search_photos(session: Session, payload: SearchRequest) -> SearchResponse:
    query_vector = build_text_embedding(payload.query)
    query_signals = _extract_query_signals(payload.query)
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

        base_similarity = 0.0
        if document.search_vector_path:
            base_similarity = cosine_similarity(query_vector, load_embedding(document.search_vector_path))

        searchable_text = _build_searchable_text(photo, document)
        keyword_bonus, keyword_reasons = _score_keyword_matches(searchable_text, query_signals.keywords)
        signal_bonus, signal_reasons = _score_query_signals(photo, document, query_signals)
        final_similarity = base_similarity + keyword_bonus + signal_bonus
        match_reasons = list(dict.fromkeys(signal_reasons + keyword_reasons))

        results.append(
            PhotoResult(
                id=photo.id or 0,
                original_name=photo.original_name,
                thumbnail_url=f"/assets/thumbnails/{photo.stored_name}",
                image_url=f"/assets/images/{photo.stored_name}",
                caption=document.caption,
                auto_tags=_split_tags(document.auto_tags),
                manual_tags=_split_tags(document.manual_tags),
                similarity=final_similarity,
                match_reasons=match_reasons,
                person_count=document.person_count,
                face_count=document.face_count,
                face_search_available=bool(document.face_vector_path),
            )
        )

    sorted_results = sorted(results, key=lambda item: item.similarity, reverse=True)[: payload.limit]
    return SearchResponse(query=payload.query, total=len(sorted_results), mode="text", results=sorted_results)
