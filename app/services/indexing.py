from pathlib import Path

from sqlmodel import Session, select

from app.models import Photo, PhotoSearchDocument
from app.services.detectors import detect_people_and_faces
from app.services.embedding import build_image_embedding, persist_embedding
from app.services.faiss_store import rebuild_faiss_index


def build_initial_caption(original_name: str) -> str:
    stem = Path(original_name).stem.replace("_", " ").replace("-", " ").strip()
    return stem


def build_auto_tags(original_name: str) -> list[str]:
    stem = Path(original_name).stem.lower()
    tags: list[str] = []
    for keyword in ["portrait", "outdoor", "indoor", "smile", "group", "solo", "night", "day"]:
        if keyword in stem:
            tags.append(keyword)
    return tags


def index_photo(session: Session, photo: Photo, refresh_index: bool = True) -> PhotoSearchDocument:
    existing = session.exec(select(PhotoSearchDocument).where(PhotoSearchDocument.photo_id == photo.id)).first()
    caption = build_initial_caption(photo.original_name)
    auto_tags = build_auto_tags(photo.original_name)
    detection = detect_people_and_faces(photo.image_path)
    vector = build_image_embedding(photo.image_path)
    vector_path = persist_embedding(vector, photo.stored_name)

    if existing:
        existing.caption = caption
        existing.auto_tags = ", ".join(auto_tags)
        existing.person_count = detection.person_count
        existing.face_count = detection.face_count
        existing.has_person = detection.has_person
        existing.has_face = detection.has_face
        existing.search_vector_path = vector_path
        session.add(existing)
        session.commit()
        session.refresh(existing)
        if refresh_index:
            rebuild_faiss_index(session)
        return existing

    document = PhotoSearchDocument(
        photo_id=photo.id or 0,
        caption=caption,
        auto_tags=", ".join(auto_tags),
        manual_tags="",
        person_count=detection.person_count,
        face_count=detection.face_count,
        has_person=detection.has_person,
        has_face=detection.has_face,
        search_vector_path=vector_path,
    )
    session.add(document)
    session.commit()
    session.refresh(document)
    if refresh_index:
        rebuild_faiss_index(session)
    return document
