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
    person_count: int
    face_count: int


class SearchResponse(BaseModel):
    query: str
    total: int
    results: list[PhotoResult]
