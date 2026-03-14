from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

from app.config import settings


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, echo=False, connect_args=connect_args)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    _run_lightweight_migrations()


def get_session():
    with Session(engine) as session:
        yield session


def _run_lightweight_migrations() -> None:
    if not settings.database_url.startswith("sqlite"):
        return

    with engine.begin() as connection:
        columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info('photosearchdocument')")).fetchall()
        }
        if "face_vector_path" not in columns:
            connection.execute(
                text("ALTER TABLE photosearchdocument ADD COLUMN face_vector_path TEXT NOT NULL DEFAULT ''")
            )
