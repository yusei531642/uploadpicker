from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "UploadPicker"
    host: str = "127.0.0.1"
    port: int = 8000
    data_dir: Path = Path("data")
    image_dir: Path = Path("data/images")
    thumbnail_dir: Path = Path("data/thumbnails")
    embedding_dir: Path = Path("data/embeddings")
    index_dir: Path = Path("data/indexes")
    faiss_index_path: Path = Path("data/indexes/photo_embeddings.faiss")
    faiss_mapping_path: Path = Path("data/indexes/photo_embeddings.json")
    database_url: str = "sqlite:///data/uploadpicker.db"
    device: str = "cuda"
    clip_model_name: str = "ViT-L-14"
    clip_pretrained: str = "openai"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()


def ensure_directories() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.image_dir.mkdir(parents=True, exist_ok=True)
    settings.thumbnail_dir.mkdir(parents=True, exist_ok=True)
    settings.embedding_dir.mkdir(parents=True, exist_ok=True)
    settings.index_dir.mkdir(parents=True, exist_ok=True)
