from fastapi import Depends, FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.config import ensure_directories, settings
from app.db import create_db_and_tables, get_session
from app.models import Photo, PhotoSearchDocument
from app.schemas import SearchRequest
from app.services.embedding import get_model_status
from app.services.faiss_store import rebuild_faiss_index
from app.services.indexing import index_photo
from app.services.search import search_photos
from app.services.storage import save_upload


ensure_directories()
app = FastAPI(title=settings.app_name)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/assets/images", StaticFiles(directory=settings.image_dir), name="images")
app.mount("/assets/thumbnails", StaticFiles(directory=settings.thumbnail_dir), name="thumbnails")
templates = Jinja2Templates(directory="app/templates")


@app.on_event("startup")
def on_startup() -> None:
    create_db_and_tables()
    for session in get_session():
        rebuild_faiss_index(session)
        break


@app.get("/", response_class=HTMLResponse)
def home(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    photos = session.exec(select(Photo).order_by(Photo.created_at.desc())).all()
    documents = session.exec(select(PhotoSearchDocument)).all()
    document_map = {document.photo_id: document for document in documents}
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "photos": photos,
            "documents": document_map,
            "model_status": get_model_status(),
            "search_results": None,
            "query": "",
            "people_only": False,
            "face_only": False,
        },
    )


@app.post("/upload")
def upload_photo(session: Session = Depends(get_session), file: UploadFile = File(...)):
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
    return RedirectResponse(url="/", status_code=303)


@app.post("/reindex")
def reindex_all_photos(session: Session = Depends(get_session)):
    photos = session.exec(select(Photo).order_by(Photo.created_at.desc())).all()
    for photo in photos:
        index_photo(session, photo, refresh_index=False)
    rebuild_faiss_index(session)
    return RedirectResponse(url="/", status_code=303)


@app.post("/search", response_class=HTMLResponse)
def search(request: Request, query: str = Form(...), people_only: bool = Form(False), face_only: bool = Form(False), session: Session = Depends(get_session)) -> HTMLResponse:
    photos = session.exec(select(Photo).order_by(Photo.created_at.desc())).all()
    documents = session.exec(select(PhotoSearchDocument)).all()
    document_map = {document.photo_id: document for document in documents}
    results = search_photos(
        session,
        SearchRequest(query=query, people_only=people_only, face_only=face_only),
    )
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "photos": photos,
            "documents": document_map,
            "model_status": get_model_status(),
            "search_results": results,
            "query": query,
            "people_only": people_only,
            "face_only": face_only,
        },
    )


@app.get("/api/search")
def search_api(query: str, people_only: bool = False, face_only: bool = False, session: Session = Depends(get_session)):
    return search_photos(session, SearchRequest(query=query, people_only=people_only, face_only=face_only))
