import json
from pathlib import Path

import numpy as np
from sqlmodel import Session, select

from app.config import settings
from app.models import PhotoSearchDocument
from app.services.embedding import load_embedding

try:
    import faiss
except ImportError:  # pragma: no cover
    faiss = None


def _load_index_and_mapping() -> tuple[object | None, list[int]]:
    if faiss is None:
        return None, []
    if not settings.faiss_index_path.exists() or not settings.faiss_mapping_path.exists():
        return None, []
    index = faiss.read_index(str(settings.faiss_index_path))
    mapping = json.loads(settings.faiss_mapping_path.read_text(encoding="utf-8"))
    return index, [int(item) for item in mapping]


def rebuild_faiss_index(session: Session) -> None:
    if faiss is None:
        return
    documents = session.exec(
        select(PhotoSearchDocument).where(PhotoSearchDocument.search_vector_path != "")
    ).all()
    vectors: list[np.ndarray] = []
    mapping: list[int] = []
    for document in documents:
        vector_path = Path(document.search_vector_path)
        if not vector_path.exists():
            continue
        vectors.append(load_embedding(document.search_vector_path))
        mapping.append(document.photo_id)
    if not vectors:
        if settings.faiss_index_path.exists():
            settings.faiss_index_path.unlink()
        if settings.faiss_mapping_path.exists():
            settings.faiss_mapping_path.unlink()
        return
    matrix = np.vstack(vectors).astype(np.float32)
    index = faiss.IndexFlatIP(matrix.shape[1])
    index.add(matrix)
    faiss.write_index(index, str(settings.faiss_index_path))
    settings.faiss_mapping_path.write_text(json.dumps(mapping), encoding="utf-8")


def search_index(query_vector: np.ndarray, limit: int) -> list[tuple[int, float]]:
    index, mapping = _load_index_and_mapping()
    if index is None or not mapping:
        return []
    top_k = min(max(limit, 1), len(mapping))
    scores, ids = index.search(np.expand_dims(query_vector.astype(np.float32), axis=0), top_k)
    matches: list[tuple[int, float]] = []
    for raw_idx, score in zip(ids[0], scores[0]):
        if raw_idx < 0 or raw_idx >= len(mapping):
            continue
        matches.append((mapping[raw_idx], float(score)))
    return matches
