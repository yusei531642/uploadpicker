from pathlib import Path

from sqlmodel import Session, delete, select

from app.models import Photo, PhotoSearchDocument
from app.services.faiss_store import rebuild_faiss_index


def _unlink_if_exists(path_value: str) -> None:
    if not path_value:
        return
    path = Path(path_value)
    if path.exists() and path.is_file():
        path.unlink()


def delete_photo(session: Session, photo_id: int) -> bool:
    photo = session.get(Photo, photo_id)
    if photo is None:
        return False

    document = session.exec(
        select(PhotoSearchDocument).where(PhotoSearchDocument.photo_id == photo_id)
    ).first()

    if document is not None:
        _unlink_if_exists(document.search_vector_path)
        _unlink_if_exists(document.face_vector_path)
        session.delete(document)

    _unlink_if_exists(photo.thumbnail_path)
    _unlink_if_exists(photo.image_path)
    session.delete(photo)
    session.commit()
    rebuild_faiss_index(session)
    return True


def clear_library(session: Session) -> int:
    photos = session.exec(select(Photo)).all()
    if not photos:
        return 0

    photo_ids = [photo.id for photo in photos if photo.id is not None]
    documents = []
    if photo_ids:
        documents = session.exec(
            select(PhotoSearchDocument).where(PhotoSearchDocument.photo_id.in_(photo_ids))
        ).all()

    for document in documents:
        _unlink_if_exists(document.search_vector_path)
        _unlink_if_exists(document.face_vector_path)

    for photo in photos:
        _unlink_if_exists(photo.thumbnail_path)
        _unlink_if_exists(photo.image_path)

    if photo_ids:
        session.exec(
            delete(PhotoSearchDocument).where(PhotoSearchDocument.photo_id.in_(photo_ids))
        )
    session.exec(delete(Photo))
    session.commit()
    rebuild_faiss_index(session)
    return len(photos)
