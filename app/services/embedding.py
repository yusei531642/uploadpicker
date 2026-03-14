from contextlib import nullcontext
from functools import lru_cache
from pathlib import Path
import re
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
def get_runtime_precision() -> str:
    return "fp16" if get_runtime_device() == "cuda" else "fp32"


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
        precision=get_runtime_precision(),
        device=get_runtime_device(),
    )
    if get_runtime_device() == "cuda":
        open_clip.convert_weights_to_lp(model, dtype=torch.float16)
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
        dtype = _get_model_status_dtype(model)
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


def _get_model_status_dtype(model: torch.nn.Module) -> str:
    dtypes = {str(parameter.dtype) for parameter in model.parameters()}
    if dtypes == {"torch.float16"}:
        return "torch.float16"
    if "torch.float16" in dtypes and "torch.float32" in dtypes:
        return "torch.float16 (mixed)"
    return str(next(model.parameters()).dtype)


def _get_inference_tensor_dtype() -> torch.dtype:
    return torch.float16 if get_runtime_device() == "cuda" else torch.float32


def _inference_context():
    if get_runtime_device() == "cuda":
        return torch.autocast(device_type="cuda", dtype=torch.float16)
    return nullcontext()


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


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _expand_search_phrases(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text.strip())
    lowered = normalized.lower()
    phrases: list[str] = [normalized]

    if _contains_any(normalized, ["女性", "女の人", "女の子", "レディ", "女子"]) or _contains_any(lowered, ["woman", "female", "lady", "girl"]):
        phrases.extend(
            [
                "woman",
                "female person",
                "lady portrait",
                "photo of a woman",
                "portrait of a woman",
                "adult woman",
            ]
        )

    if _contains_any(normalized, ["男性", "男の人", "男の子", "男子"]) or _contains_any(lowered, ["man", "male", "boy"]):
        phrases.extend(
            [
                "man",
                "male person",
                "photo of a man",
                "portrait of a man",
                "adult man",
            ]
        )

    if _contains_any(normalized, ["人物", "人"]) or _contains_any(lowered, ["person", "people", "portrait"]):
        phrases.extend(
            [
                "person",
                "people",
                "portrait photo",
                "photo of a person",
            ]
        )

    if _contains_any(normalized, ["顔", "顔アップ", "バストアップ", "自撮り"]) or _contains_any(lowered, ["face", "closeup", "close-up", "selfie"]):
        phrases.extend(
            [
                "face",
                "close-up portrait",
                "face closeup",
                "selfie photo",
            ]
        )

    if _contains_any(normalized, ["全身"]) or _contains_any(lowered, ["full body", "full-body"]):
        phrases.extend(
            [
                "full body person",
                "full-body portrait",
            ]
        )

    if _contains_any(normalized, ["複数人", "グループ", "集合"]) or _contains_any(lowered, ["group", "team"]):
        phrases.extend(
            [
                "group photo",
                "multiple people",
                "team portrait",
            ]
        )

    if _contains_any(normalized, ["一人", "ひとり", "ソロ"]) or _contains_any(lowered, ["solo", "single person"]):
        phrases.extend(
            [
                "single person",
                "solo portrait",
                "one person photo",
            ]
        )

    unique_phrases = list(dict.fromkeys(phrase.strip() for phrase in phrases if phrase.strip()))
    return unique_phrases


def build_text_embedding(text: str) -> np.ndarray:
    model, _, tokenizer = get_model_bundle()
    base_text = text.strip()
    prompts = [
        base_text,
        f"a photo of {base_text}",
        f"an image of {base_text}",
        f"photo search query: {base_text}",
    ]
    for phrase in _expand_search_phrases(base_text):
        prompts.extend(
            [
                phrase,
                f"a photo of {phrase}",
                f"an image of {phrase}",
            ]
        )
    unique_prompts = list(dict.fromkeys(prompt for prompt in prompts if prompt.strip()))
    tokens = tokenizer(unique_prompts)
    device = get_runtime_device()
    with torch.no_grad():
        with _inference_context():
            text_features = model.encode_text(tokens.to(device))
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
    merged = text_features.mean(dim=0)
    return _normalize(merged.detach().cpu().numpy().astype(np.float32))


def build_image_embedding(image_path: str) -> np.ndarray:
    with Image.open(image_path) as image:
        return build_image_embedding_from_pil(image.convert("RGB"))


def build_image_embedding_from_pil(image: Image.Image) -> np.ndarray:
    model, preprocess, _ = get_model_bundle()
    tensor = preprocess(image).unsqueeze(0).to(device=get_runtime_device(), dtype=_get_inference_tensor_dtype())
    with torch.no_grad():
        with _inference_context():
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
