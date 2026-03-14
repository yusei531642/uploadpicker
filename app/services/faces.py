from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from sqlmodel import Session, select

from app.config import settings
from app.models import Photo, PhotoSearchDocument
from app.schemas import PhotoResult, SearchResponse
from app.services.embedding import build_image_embedding_from_pil


def _normalize(vector: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vector)
    return vector if norm == 0 else vector / norm


def _persist_face_embedding(vector: np.ndarray, target_name: str) -> str:
    output_path = Path(settings.face_embedding_dir) / f"{target_name}.npy"
    np.save(output_path, vector.astype(np.float32))
    return str(output_path)


def _load_face_embedding(path: str) -> np.ndarray:
    vectors = np.load(path)
    if vectors.ndim == 1:
        return vectors.reshape(1, -1)
    return vectors


def _detect_face_boxes(image_path: str) -> list[tuple[int, int, int, int]]:
    image = cv2.imread(image_path)
    if image is None:
        return []
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    detector = cv2.CascadeClassifier(cascade_path)
    boxes = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))
    return [tuple(map(int, box)) for box in boxes]


def _expand_box(width: int, height: int, box: tuple[int, int, int, int], padding_ratio: float = 0.18) -> tuple[int, int, int, int]:
    x, y, w, h = box
    pad_w = int(w * padding_ratio)
    pad_h = int(h * padding_ratio)
    left = max(0, x - pad_w)
    top = max(0, y - pad_h)
    right = min(width, x + w + pad_w)
    bottom = min(height, y + h + pad_h)
    return left, top, right, bottom


def _crop_faces(image_path: str) -> tuple[int, list[Image.Image]]:
    boxes = _detect_face_boxes(image_path)
    if not boxes:
        return 0, []
    with Image.open(image_path) as image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        crops: list[Image.Image] = []
        for box in sorted(boxes, key=lambda item: item[2] * item[3], reverse=True)[:8]:
            left, top, right, bottom = _expand_box(width, height, box)
            crops.append(rgb.crop((left, top, right, bottom)).copy())
        return len(boxes), crops


def build_face_embedding(image_path: str, stored_name: str) -> tuple[int, str]:
    face_count, crops = _crop_faces(image_path)
    if not crops:
        return face_count, ""
    vectors = np.stack([_normalize(build_image_embedding_from_pil(crop)) for crop in crops], axis=0)
    return face_count, _persist_face_embedding(vectors, stored_name)


def _best_face_similarity(reference_vectors: np.ndarray, candidate_vectors: np.ndarray) -> float:
    reference = np.atleast_2d(reference_vectors)
    candidate = np.atleast_2d(candidate_vectors)
    scores = reference @ candidate.T
    return float(scores.max()) if scores.size else 0.0


def search_similar_faces(session: Session, reference_photo_id: int, limit: int = 24) -> SearchResponse:
    reference_document = session.exec(
        select(PhotoSearchDocument).where(PhotoSearchDocument.photo_id == reference_photo_id)
    ).first()
    reference_photo = session.get(Photo, reference_photo_id)
    if reference_document is None or reference_photo is None or not reference_document.face_vector_path:
        return SearchResponse(
            query="顔検索",
            total=0,
            mode="face",
            reference_photo_id=reference_photo_id,
            results=[],
        )

    reference_vector = _load_face_embedding(reference_document.face_vector_path)
    rows = session.exec(
        select(Photo, PhotoSearchDocument).join(PhotoSearchDocument, Photo.id == PhotoSearchDocument.photo_id)
    ).all()

    results: list[PhotoResult] = []
    for photo, document in rows:
        if not document.face_vector_path:
            continue
        vector_path = Path(document.face_vector_path)
        if not vector_path.exists():
            continue
        score = _best_face_similarity(reference_vector, _load_face_embedding(document.face_vector_path))
        reasons = ["顔特徴一致"]
        if photo.id == reference_photo_id:
            reasons = ["基準画像"]
        results.append(
            PhotoResult(
                id=photo.id or 0,
                original_name=photo.original_name,
                thumbnail_url=f"/assets/thumbnails/{photo.stored_name}",
                image_url=f"/assets/images/{photo.stored_name}",
                caption=document.caption,
                auto_tags=[item.strip() for item in document.auto_tags.split(",") if item.strip()],
                manual_tags=[item.strip() for item in document.manual_tags.split(",") if item.strip()],
                similarity=score,
                match_reasons=reasons,
                person_count=document.person_count,
                face_count=document.face_count,
                face_search_available=bool(document.face_vector_path),
            )
        )

    sorted_results = sorted(results, key=lambda item: item.similarity, reverse=True)[:limit]
    return SearchResponse(
        query=f"顔検索: {reference_photo.original_name}",
        total=len(sorted_results),
        mode="face",
        reference_photo_id=reference_photo_id,
        results=sorted_results,
    )
