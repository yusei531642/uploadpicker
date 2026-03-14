import mimetypes
import uuid
from pathlib import Path

from fastapi import UploadFile
from PIL import Image

from app.config import settings


def save_upload(file: UploadFile) -> tuple[str, str, int, int, str]:
    extension = Path(file.filename or "upload.bin").suffix or ".bin"
    stored_name = f"{uuid.uuid4().hex}{extension.lower()}"
    image_path = settings.image_dir / stored_name
    thumbnail_path = settings.thumbnail_dir / stored_name

    with image_path.open("wb") as buffer:
        while chunk := file.file.read(1024 * 1024):
            buffer.write(chunk)

    with Image.open(image_path) as image:
        rgb_image = image.convert("RGB")
        width, height = rgb_image.size
        thumbnail = rgb_image.copy()
        thumbnail.thumbnail((512, 512))
        thumbnail.save(thumbnail_path, format="JPEG", quality=90)

    mime_type = file.content_type or mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream"
    return stored_name, str(image_path), width, height, mime_type
