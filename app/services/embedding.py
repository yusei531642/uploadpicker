from functools import lru_cache
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from app.config import settings


@lru_cache(maxsize=1)
def get_runtime_device() -> str:
    return "cuda" if settings.device == "cuda" and torch.cuda.is_available() else "cpu"


@lru_cache(maxsize=1)
def get_model_bundle():
    import open_clip

    model, _, preprocess = open_clip.create_model_and_transforms(
        settings.clip_model_name,
        pretrained=settings.clip_pretrained,
        device=get_runtime_device(),
    )
    tokenizer = open_clip.get_tokenizer(settings.clip_model_name)
    model.eval()
    return model, preprocess, tokenizer


def _normalize(vector: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vector)
    return vector if norm == 0 else vector / norm


@lru_cache(maxsize=1)
def get_model_status() -> dict:
    device = get_runtime_device()
    try:
        model, _, _ = get_model_bundle()
        dtype = str(next(model.parameters()).dtype)
        return {
            "device": device,
            "model_name": settings.clip_model_name,
            "pretrained": settings.clip_pretrained,
            "loaded": True,
            "dtype": dtype,
        }
    except Exception as exc:
        return {
            "device": device,
            "model_name": settings.clip_model_name,
            "pretrained": settings.clip_pretrained,
            "loaded": False,
            "error": str(exc),
        }


def build_text_embedding(text: str) -> np.ndarray:
    model, _, tokenizer = get_model_bundle()
    tokens = tokenizer([text])
    device = get_runtime_device()
    with torch.no_grad():
        text_features = model.encode_text(tokens.to(device))
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)
    return _normalize(text_features[0].detach().cpu().numpy().astype(np.float32))


def build_image_embedding(image_path: str) -> np.ndarray:
    model, preprocess, _ = get_model_bundle()
    image = Image.open(image_path).convert("RGB")
    tensor = preprocess(image).unsqueeze(0).to(get_runtime_device())
    with torch.no_grad():
        image_features = model.encode_image(tensor)
        image_features = image_features / image_features.norm(dim=-1, keepdim=True)
    return _normalize(image_features[0].detach().cpu().numpy().astype(np.float32))


def persist_embedding(vector: np.ndarray, target_name: str) -> str:
    output_path = Path(settings.embedding_dir) / f"{target_name}.npy"
    np.save(output_path, vector)
    return str(output_path)


def load_embedding(path: str) -> np.ndarray:
    return np.load(path)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denominator == 0:
        return 0.0
    return float(np.dot(a, b) / denominator)
