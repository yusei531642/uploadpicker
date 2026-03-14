from functools import lru_cache
from pathlib import Path
import shutil
import subprocess
from threading import Lock, Thread

import numpy as np
import torch
from PIL import Image

from app.config import settings


_MODEL_STATUS_LOCK = Lock()
_MODEL_STATUS: dict[str, object] = {
    "started": False,
    "loading": False,
    "loaded": False,
    "dtype": None,
    "error": None,
    "detail": "AI モデルの起動待機中です。",
}


@lru_cache(maxsize=1)
def get_runtime_device() -> str:
    preferred = settings.device.lower()
    if preferred == "cpu":
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


@lru_cache(maxsize=1)
def get_detected_gpu_name() -> str | None:
    if torch.cuda.is_available():
        try:
            return torch.cuda.get_device_name(0)
        except Exception:
            return "CUDA GPU"
    if shutil.which("nvidia-smi"):
        try:
            output = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
            if output:
                return output.splitlines()[0].strip()
        except Exception:
            return None
    return None


@lru_cache(maxsize=1)
def get_device_reason() -> str:
    preferred = settings.device.lower()
    if preferred == "cpu":
        return "設定により CPU を使用しています。"
    if torch.cuda.is_available():
        return "利用可能な GPU を優先して使用しています。"
    detected_gpu = get_detected_gpu_name()
    if detected_gpu:
        return "GPU は検出されていますが、CUDA 対応の PyTorch ランタイムが使えていないため CPU を使用しています。Install / Repair を再実行してください。"
    return "利用可能な GPU ランタイムが見つからないため CPU を使用しています。"


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


def _base_status() -> dict:
    return {
        "device": get_runtime_device(),
        "model_name": settings.clip_model_name,
        "pretrained": settings.clip_pretrained,
        "gpu_name": get_detected_gpu_name(),
        "device_reason": get_device_reason(),
    }


def _load_model_in_background() -> None:
    try:
        with _MODEL_STATUS_LOCK:
            _MODEL_STATUS.update(
                {
                    "detail": "AI モデルを読み込んでいます。初回起動は少し時間がかかります。",
                }
            )
        model, _, _ = get_model_bundle()
        dtype = str(next(model.parameters()).dtype)
        with _MODEL_STATUS_LOCK:
            _MODEL_STATUS.update(
                {
                    "started": True,
                    "loading": False,
                    "loaded": True,
                    "dtype": dtype,
                    "error": None,
                    "detail": "AI モデルの準備が完了しました。",
                }
            )
    except Exception as exc:
        with _MODEL_STATUS_LOCK:
            _MODEL_STATUS.update(
                {
                    "started": True,
                    "loading": False,
                    "loaded": False,
                    "dtype": None,
                    "error": str(exc),
                    "detail": "AI モデルの読み込みに失敗しました。再読み込みしてください。",
                }
            )


def start_model_warmup() -> None:
    with _MODEL_STATUS_LOCK:
        if _MODEL_STATUS["loading"] or _MODEL_STATUS["loaded"]:
            return
        _MODEL_STATUS.update(
            {
                "started": True,
                "loading": True,
                "loaded": False,
                "dtype": None,
                "error": None,
                "detail": "AI モデルの起動準備を始めています。",
            }
        )
    Thread(target=_load_model_in_background, daemon=True).start()


def _normalize(vector: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vector)
    return vector if norm == 0 else vector / norm


def get_model_status() -> dict:
    start_model_warmup()
    with _MODEL_STATUS_LOCK:
        status = dict(_MODEL_STATUS)
    return {
        **_base_status(),
        "started": bool(status["started"]),
        "loading": bool(status["loading"]),
        "loaded": bool(status["loaded"]),
        "dtype": status["dtype"],
        "error": status["error"],
        "detail": str(status["detail"]),
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
