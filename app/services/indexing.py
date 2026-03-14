from pathlib import Path

from sqlmodel import Session, select

from app.models import Photo, PhotoSearchDocument
from app.services.captions import generate_image_caption
from app.services.detectors import detect_people_and_faces
from app.services.embedding import build_image_embedding, persist_embedding
from app.services.faiss_store import rebuild_faiss_index
from app.services.faces import build_face_embedding


def build_initial_caption(original_name: str) -> str:
    stem = Path(original_name).stem.replace("_", " ").replace("-", " ").strip()
    return stem


def build_auto_tags(original_name: str, caption: str, detection) -> list[str]:
    stem = Path(original_name).stem.lower()
    caption_text = caption.lower()
    combined = f"{stem} {caption_text}"
    tags: list[str] = []
    for keyword in ["portrait", "outdoor", "indoor", "smile", "group", "solo", "night", "day"]:
        if keyword in combined:
            tags.append(keyword)
    if detection.person_count == 1 and "solo" not in tags:
        tags.append("solo")
    if detection.person_count >= 2 and "group" not in tags:
        tags.append("group")
    if detection.has_face and "portrait" not in tags:
        tags.append("portrait")
    return tags


def index_photo(session: Session, photo: Photo, refresh_index: bool = True) -> PhotoSearchDocument:
    existing = session.exec(select(PhotoSearchDocument).where(PhotoSearchDocument.photo_id == photo.id)).first()
    detection = detect_people_and_faces(photo.image_path)
    caption = generate_image_caption(photo.image_path) or build_initial_caption(photo.original_name)
    auto_tags = build_auto_tags(photo.original_name, caption, detection)
    vector = build_image_embedding(photo.image_path)
    vector_path = persist_embedding(vector, photo.stored_name)
    face_count, face_vector_path = build_face_embedding(photo.image_path, photo.stored_name)
    resolved_face_count = max(detection.face_count, face_count)
    resolved_has_face = bool(face_vector_path) or detection.has_face

    if existing:
        existing.caption = caption
        existing.auto_tags = ", ".join(auto_tags)
        existing.person_count = detection.person_count
        existing.face_count = resolved_face_count
        existing.has_person = detection.has_person
        existing.has_face = resolved_has_face
        existing.search_vector_path = vector_path
        existing.face_vector_path = face_vector_path
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
        face_count=resolved_face_count,
        has_person=detection.has_person,
        has_face=resolved_has_face,
        search_vector_path=vector_path,
        face_vector_path=face_vector_path,
    )
    session.add(document)
    session.commit()
    session.refresh(document)
    if refresh_index:
        rebuild_faiss_index(session)
    return document
