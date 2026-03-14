import mimetypes
import uuid
from pathlib import Path

from fastapi import UploadFile
from PIL import Image

from app.config import settings


def _build_thumbnail(image_path: Path, thumbnail_path: Path) -> tuple[int, int]:
    with Image.open(image_path) as image:
        rgb_image = image.convert("RGB")
        width, height = rgb_image.size
        thumbnail = rgb_image.copy()
        thumbnail.thumbnail((512, 512))
        thumbnail.save(thumbnail_path, format="JPEG", quality=90)
    return width, height


def save_upload(file: UploadFile) -> tuple[str, str, int, int, str]:
    extension = Path(file.filename or "upload.bin").suffix or ".bin"
    stored_name = f"{uuid.uuid4().hex}{extension.lower()}"
    image_path = settings.image_dir / stored_name
    thumbnail_path = settings.thumbnail_dir / stored_name

    with image_path.open("wb") as buffer:
        while chunk := file.file.read(1024 * 1024):
            buffer.write(chunk)

    width, height = _build_thumbnail(image_path, thumbnail_path)

    mime_type = file.content_type or mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream"
    return stored_name, str(image_path), width, height, mime_type


def prepare_existing_image(image_path: Path) -> tuple[str, str, int, int, str]:
    thumbnail_path = settings.thumbnail_dir / image_path.name
    width, height = _build_thumbnail(image_path, thumbnail_path)
    mime_type = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
    return image_path.name, str(image_path), width, height, mime_type


def iter_library_images() -> list[Path]:
    return sorted(
        [path for path in settings.image_dir.iterdir() if path.is_file()],
        key=lambda path: path.name.lower(),
    )
