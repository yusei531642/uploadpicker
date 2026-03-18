import base64
import io
import os
import subprocess
from threading import Lock, Thread
from urllib.parse import quote

from fastapi import Depends, FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image, UnidentifiedImageError
from sqlmodel import Session, select

from app.config import ensure_directories, settings
from app.db import create_db_and_tables, engine, get_session
from app.models import Photo, PhotoSearchDocument
from app.schemas import SearchRequest
from app.services.embedding import build_image_embedding_from_pil, get_model_status, start_model_warmup
from app.services.faiss_store import rebuild_faiss_index
from app.services.faces import search_similar_faces
from app.services.indexing import index_photo
from app.services.library import clear_library, delete_photo
from app.services.search import search_photos, search_photos_by_image
from app.services.storage import iter_library_images, prepare_existing_image, save_upload
from app.services.updater import get_local_update_status, get_update_status, launch_github_update


ensure_directories()
app = FastAPI(title=settings.app_name)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/assets/images", StaticFiles(directory=settings.image_dir), name="images")
app.mount("/assets/thumbnails", StaticFiles(directory=settings.thumbnail_dir), name="thumbnails")
templates = Jinja2Templates(directory="app/templates")

_INDEX_STATUS_LOCK = Lock()
_INDEX_STATUS: dict[str, object] = {
    "started": False,
    "loading": False,
    "loaded": False,
    "error": None,
    "detail": "検索インデックスの起動待機中です。",
}


def _load_index_in_background() -> None:
    try:
        with Session(engine) as session:
            rebuild_faiss_index(session)
        with _INDEX_STATUS_LOCK:
            _INDEX_STATUS.update(
                {
                    "started": True,
                    "loading": False,
                    "loaded": True,
                    "error": None,
                    "detail": "検索インデックスの準備が完了しました。",
                }
            )
    except Exception as exc:
        with _INDEX_STATUS_LOCK:
            _INDEX_STATUS.update(
                {
                    "started": True,
                    "loading": False,
                    "loaded": False,
                    "error": str(exc),
                    "detail": "検索インデックスの準備に失敗しました。再読み込みしてください。",
                }
            )


def start_index_warmup() -> None:
    with _INDEX_STATUS_LOCK:
        if _INDEX_STATUS["loading"] or _INDEX_STATUS["loaded"]:
            return
        _INDEX_STATUS.update(
            {
                "started": True,
                "loading": True,
                "loaded": False,
                "error": None,
                "detail": "検索インデックスを確認しています。",
            }
        )
    Thread(target=_load_index_in_background, daemon=True).start()


def get_index_status() -> dict[str, object]:
    start_index_warmup()
    with _INDEX_STATUS_LOCK:
        return dict(_INDEX_STATUS)


def build_runtime_status() -> dict[str, object]:
    model_status = get_model_status()
    index_status = get_index_status()

    model_loading = bool(model_status["loading"])
    index_loading = bool(index_status["loading"])
    model_error = model_status["error"]
    index_error = index_status["error"]
    error = model_error or index_error
    loaded = bool(model_status["loaded"] and index_status["loaded"] and not error)
    loading = bool((model_loading or index_loading) and not error and not loaded)

    if error:
        phase = "error"
        detail = str(model_status["detail"] if model_error else index_status["detail"])
    elif model_loading and index_loading:
        phase = "starting"
        detail = "AI モデルと検索インデックスを準備しています。"
    elif model_loading:
        phase = "model-loading"
        detail = str(model_status["detail"])
    elif index_loading:
        phase = "index-loading"
        detail = str(index_status["detail"])
    elif loaded:
        phase = "ready"
        detail = "画像検索の準備が完了しました。"
    else:
        phase = "idle"
        detail = "起動準備をしています。"

    return {
        **model_status,
        "loading": loading,
        "loaded": loaded,
        "error": error,
        "phase": phase,
        "detail": detail,
        "index_started": bool(index_status["started"]),
        "index_loading": index_loading,
        "index_loaded": bool(index_status["loaded"]),
        "index_error": index_error,
        "index_detail": str(index_status["detail"]),
    }


def build_search_groups(search_results) -> list[dict[str, object]]:
    if not search_results or not search_results.results:
        return []

    top_score = max(item.similarity for item in search_results.results)
    strong_threshold = max(top_score - 0.03, 0.28)
    medium_threshold = max(top_score - 0.08, 0.18)
    is_face_mode = search_results.mode == "face"
    is_image_mode = search_results.mode == "image"

    groups = [
        {
            "title": "かなり近い画像" if is_image_mode else "かなり近い候補" if not is_face_mode else "かなり近い顔",
            "description": "アップした見本画像とかなり近そうな候補です。" if is_image_mode else "入力した内容にかなり近そうな画像です。" if not is_face_mode else "基準画像とかなり近い顔の候補です。",
            "tone": "strong",
            "items": [],
        },
        {
            "title": "近い画像" if is_image_mode else "近い候補" if not is_face_mode else "近い顔",
            "description": "見本画像に近いので、先に見ておくと探しやすい候補です。" if is_image_mode else "条件に近いので、先に見ておくと探しやすい画像です。" if not is_face_mode else "同じ人物の可能性があるので先に見ておきたい顔です。",
            "tone": "medium",
            "items": [],
        },
        {
            "title": "参考画像" if is_image_mode else "参考候補" if not is_face_mode else "参考の顔候補",
            "description": "少し広めに拾った候補です。近い画像が少ないときの確認用です。" if not is_face_mode else "少し広めに拾った顔候補です。似ている人が混ざることがあります。",
            "tone": "soft",
            "items": [],
        },
    ]

    for item in search_results.results:
        if item.similarity >= strong_threshold:
            groups[0]["items"].append(item)
        elif item.similarity >= medium_threshold:
            groups[1]["items"].append(item)
        else:
            groups[2]["items"].append(item)

    return [group for group in groups if group["items"]]


@app.on_event("startup")
def on_startup() -> None:
    create_db_and_tables()
    start_model_warmup()
    start_index_warmup()


def build_page_context(
    session: Session,
    *,
    query: str = "",
    people_only: bool = False,
    face_only: bool = False,
    image_people_only: bool = False,
    image_face_only: bool = False,
    search_results=None,
    image_search_preview: str = "",
    image_search_name: str = "",
    notice: str = "",
) -> dict:
    photos = session.exec(select(Photo).order_by(Photo.created_at.desc())).all()
    documents = session.exec(select(PhotoSearchDocument)).all()
    document_map = {document.photo_id: document for document in documents}
    return {
        "photos": photos,
        "documents": document_map,
        "app_status": build_runtime_status(),
        "search_results": search_results,
        "search_groups": build_search_groups(search_results),
        "search_mode": getattr(search_results, "mode", "text") if search_results else "text",
        "query": query,
        "people_only": people_only,
        "face_only": face_only,
        "image_people_only": image_people_only,
        "image_face_only": image_face_only,
        "image_search_preview": image_search_preview,
        "image_search_name": image_search_name,
        "library_dir": str(settings.image_dir.resolve()),
        "notice": notice,
        "update_status": get_local_update_status(),
    }


def build_search_preview_data_url(image) -> str:
    preview = image.copy()
    preview.thumbnail((360, 360))
    buffer = io.BytesIO()
    preview.save(buffer, format="JPEG", quality=88)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


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
    reindexed = 0
    skipped = 0
    for photo in photos:
        try:
            index_photo(session, photo, refresh_index=False)
            reindexed += 1
        except (FileNotFoundError, UnidentifiedImageError, OSError):
            skipped += 1
    rebuild_faiss_index(session)
    return RedirectResponse(url=f"/?notice=再インデックス完了: {reindexed}件更新 / {skipped}件スキップ", status_code=303)


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


@app.post("/photos/{photo_id}/delete")
def delete_registered_photo(photo_id: int, session: Session = Depends(get_session)):
    deleted = delete_photo(session, photo_id)
    notice = "画像を一覧から削除しました。" if deleted else "削除したい画像が見つかりませんでした。"
    return RedirectResponse(url=f"/?notice={quote(notice)}", status_code=303)


@app.post("/photos/clear")
def clear_registered_photos(session: Session = Depends(get_session)):
    deleted_count = clear_library(session)
    if deleted_count:
        notice = f"登録済み画像を {deleted_count} 件まとめて削除しました。"
    else:
        notice = "削除する登録済み画像はありませんでした。"
    return RedirectResponse(url=f"/?notice={quote(notice)}", status_code=303)


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


@app.post("/search-image", response_class=HTMLResponse)
def search_image(
    request: Request,
    image_file: UploadFile = File(...),
    people_only: bool = Form(False),
    face_only: bool = Form(False),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    image_name = image_file.filename or "検索画像"
    try:
        image_bytes = image_file.file.read()
        if not image_bytes:
            raise UnidentifiedImageError("empty image")
        with Image.open(io.BytesIO(image_bytes)) as uploaded_image:
            rgb_image = uploaded_image.convert("RGB")
            query_vector = build_image_embedding_from_pil(rgb_image)
            preview_url = build_search_preview_data_url(rgb_image)
    except (UnidentifiedImageError, OSError):
        return templates.TemplateResponse(
            request,
            "home.html",
            build_page_context(
                session,
                image_people_only=people_only,
                image_face_only=face_only,
                notice="画像を読み込めませんでした。PNG や JPG の画像で試してください。",
            ),
            status_code=400,
        )
    finally:
        image_file.file.close()

    results = search_photos_by_image(
        session,
        query_vector,
        people_only=people_only,
        face_only=face_only,
        query_label=image_name,
    )
    return templates.TemplateResponse(
        request,
        "home.html",
        build_page_context(
            session,
            image_people_only=people_only,
            image_face_only=face_only,
            search_results=results,
            image_search_preview=preview_url,
            image_search_name=image_name,
        ),
    )


@app.post("/search-face/{photo_id}", response_class=HTMLResponse)
def search_face(request: Request, photo_id: int, session: Session = Depends(get_session)) -> HTMLResponse:
    results = search_similar_faces(session, photo_id)
    notice = "同じ人物っぽい顔を優先して探しています。"
    if not results.results:
        notice = "この画像では比較に使える顔を見つけられませんでした。別の画像でも試してください。"
    return templates.TemplateResponse(
        request,
        "home.html",
        build_page_context(
            session,
            search_results=results,
            notice=notice,
        ),
    )


@app.get("/api/model-status")
def model_status_api():
    return build_runtime_status()


@app.get("/api/search")
def search_api(query: str, people_only: bool = False, face_only: bool = False, session: Session = Depends(get_session)):
    return search_photos(session, SearchRequest(query=query, people_only=people_only, face_only=face_only))


@app.get("/api/update-status")
def update_status_api():
    return get_update_status()


@app.post("/run-github-update")
def run_github_update():
    launch_github_update(os.getpid())
    return RedirectResponse(url="/?notice=GitHubから更新を開始しました。数秒後に自動で再起動します。", status_code=303)
