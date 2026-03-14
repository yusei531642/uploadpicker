from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class Photo(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    original_name: str
    stored_name: str
    image_path: str
    thumbnail_path: str
    mime_type: str
    width: int
    height: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PhotoSearchDocument(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    photo_id: int = Field(index=True, foreign_key="photo.id")
    caption: str = ""
    auto_tags: str = ""
    manual_tags: str = ""
    person_count: int = 0
    face_count: int = 0
    has_person: bool = False
    has_face: bool = False
    search_vector_path: str = ""
    face_vector_path: str = ""
