from functools import lru_cache
from pathlib import Path

import torch
from PIL import Image

from app.config import settings
from app.services.embedding import get_runtime_device


def _fallback_caption(image_path: str) -> str:
    stem = Path(image_path).stem.replace("_", " ").replace("-", " ").strip()
    return stem or "image"


@lru_cache(maxsize=1)
def _load_caption_bundle():
    from transformers import BlipForConditionalGeneration, BlipProcessor

    processor = BlipProcessor.from_pretrained(settings.caption_model_name)
    model = BlipForConditionalGeneration.from_pretrained(settings.caption_model_name)
    device = get_runtime_device()
    if device == "cuda":
        model = model.to(device=device, dtype=torch.float16)
    else:
        model = model.to(device)
    model.eval()
    return processor, model


def generate_image_caption(image_path: str) -> str:
    try:
        processor, model = _load_caption_bundle()
        device = get_runtime_device()
        with Image.open(image_path) as image:
            rgb = image.convert("RGB")
            inputs = processor(images=rgb, return_tensors="pt")
        inputs = {key: value.to(model.device) for key, value in inputs.items()}
        with torch.no_grad():
            generated_ids = model.generate(**inputs, max_new_tokens=32)
        caption = processor.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()
        return caption or _fallback_caption(image_path)
    except Exception:
        return _fallback_caption(image_path)
