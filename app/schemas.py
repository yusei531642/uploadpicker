from pydantic import BaseModel


class SearchRequest(BaseModel):
    query: str
    limit: int = 24
    people_only: bool = False
    face_only: bool = False


class PhotoResult(BaseModel):
    id: int
    original_name: str
    thumbnail_url: str
    image_url: str
    caption: str
    auto_tags: list[str]
    manual_tags: list[str]
    similarity: float
    match_reasons: list[str]
    person_count: int
    face_count: int
    face_search_available: bool


class SearchResponse(BaseModel):
    query: str
    total: int
    mode: str = "text"
    reference_photo_id: int | None = None
    results: list[PhotoResult]
