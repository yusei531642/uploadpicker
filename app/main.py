import subprocess

from fastapi import Depends, FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import UnidentifiedImageError
from sqlmodel import Session, select

from app.config import ensure_directories, settings
from app.db import create_db_and_tables, get_session
from app.models import Photo, PhotoSearchDocument
from app.schemas import SearchRequest
from app.services.embedding import get_model_status, start_model_warmup
from app.services.faiss_store import rebuild_faiss_index
from app.services.indexing import index_photo
from app.services.search import search_photos
from app.services.storage import iter_library_images, prepare_existing_image, save_upload


ensure_directories()
app = FastAPI(title=settings.app_name)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/assets/images", StaticFiles(directory=settings.image_dir), name="images")
app.mount("/assets/thumbnails", StaticFiles(directory=settings.thumbnail_dir), name="thumbnails")
templates = Jinja2Templates(directory="app/templates")


@app.on_event("startup")
def on_startup() -> None:
    create_db_and_tables()
    start_model_warmup()
    for session in get_session():
        rebuild_faiss_index(session)
        break


def build_page_context(
    session: Session,
    *,
    query: str = "",
    people_only: bool = False,
    face_only: bool = False,
    search_results=None,
    notice: str = "",
) -> dict:
    photos = session.exec(select(Photo).order_by(Photo.created_at.desc())).all()
    documents = session.exec(select(PhotoSearchDocument)).all()
    document_map = {document.photo_id: document for document in documents}
    return {
        "photos": photos,
        "documents": document_map,
        "model_status": get_model_status(),
        "search_results": search_results,
        "query": query,
        "people_only": people_only,
        "face_only": face_only,
        "library_dir": str(settings.image_dir.resolve()),
        "notice": notice,
    }


@app.get("/", response_class=HTMLResponse)
def home(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    notice = request.query_params.get("notice", "")
    return templates.TemplateResponse(
        request,
        "home.html",
        build_page_context(session, notice=notice),
    )


def register_uploaded_photo(session: Session, file: UploadFile) -> None:
    stored_name, image_path, width, height, mime_type = save_upload(file)
    photo = Photo(
        original_name=file.filename or stored_name,
        stored_name=stored_name,
        image_path=image_path,
        thumbnail_path=str(settings.thumbnail_dir / stored_name),
        mime_type=mime_type,
        width=width,
        height=height,
    )
    session.add(photo)
    session.commit()
    session.refresh(photo)
    index_photo(session, photo)


@app.post("/upload")
def upload_photo(session: Session = Depends(get_session), file: UploadFile = File(...)):
    register_uploaded_photo(session, file)
    return RedirectResponse(url="/", status_code=303)


@app.post("/upload-batch")
def upload_batch(session: Session = Depends(get_session), files: list[UploadFile] = File(...)):
    imported = 0
    skipped = 0
    for file in files:
        if not file.filename:
            skipped += 1
            continue
        try:
            register_uploaded_photo(session, file)
            imported += 1
        except (UnidentifiedImageError, OSError):
            skipped += 1
        finally:
            file.file.close()
    notice = f"一括アップロード完了: {imported}件追加 / {skipped}件スキップ"
    return RedirectResponse(url=f"/?notice={notice}", status_code=303)


@app.post("/reindex")
def reindex_all_photos(session: Session = Depends(get_session)):
    photos = session.exec(select(Photo).order_by(Photo.created_at.desc())).all()
    for photo in photos:
        index_photo(session, photo, refresh_index=False)
    rebuild_faiss_index(session)
    return RedirectResponse(url="/?notice=再インデックスが完了しました。", status_code=303)


@app.post("/open-image-folder")
def open_image_folder():
    subprocess.Popen(["explorer", str(settings.image_dir.resolve())])
    return RedirectResponse(url="/?notice=画像フォルダを開きました。", status_code=303)


@app.post("/import-folder-images")
def import_folder_images(session: Session = Depends(get_session)):
    existing_names = set(session.exec(select(Photo.stored_name)).all())
    imported = 0
    skipped = 0
    for image_path in iter_library_images():
        if image_path.name in existing_names:
            skipped += 1
            continue
        try:
            stored_name, image_path_value, width, height, mime_type = prepare_existing_image(image_path)
        except (UnidentifiedImageError, OSError):
            skipped += 1
            continue
        photo = Photo(
            original_name=image_path.name,
            stored_name=stored_name,
            image_path=image_path_value,
            thumbnail_path=str(settings.thumbnail_dir / stored_name),
            mime_type=mime_type,
            width=width,
            height=height,
        )
        session.add(photo)
        session.commit()
        session.refresh(photo)
        index_photo(session, photo, refresh_index=False)
        existing_names.add(image_path.name)
        imported += 1
    rebuild_faiss_index(session)
    return RedirectResponse(url=f"/?notice=フォルダ取り込み完了: {imported}件追加 / {skipped}件スキップ", status_code=303)


@app.post("/search", response_class=HTMLResponse)
def search(request: Request, query: str = Form(...), people_only: bool = Form(False), face_only: bool = Form(False), session: Session = Depends(get_session)) -> HTMLResponse:
    results = search_photos(
        session,
        SearchRequest(query=query, people_only=people_only, face_only=face_only),
    )
    return templates.TemplateResponse(
        request,
        "home.html",
        build_page_context(
            session,
            query=query,
            people_only=people_only,
            face_only=face_only,
            search_results=results,
        ),
    )


@app.get("/api/model-status")
def model_status_api():
    return get_model_status()


@app.get("/api/search")
def search_api(query: str, people_only: bool = False, face_only: bool = False, session: Session = Depends(get_session)):
    return search_photos(session, SearchRequest(query=query, people_only=people_only, face_only=face_only))
