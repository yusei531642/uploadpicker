import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.config import settings


def _project_root() -> Path:
    return settings.project_root.resolve()


def _read_local_commit() -> str | None:
    project_root = _project_root()
    git_dir = project_root / ".git"
    if not git_dir.exists():
        return None
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True,
        )
    except Exception:
        return None
    value = completed.stdout.strip()
    return value or None


def _format_datetime(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return parsed.strftime("%Y-%m-%d %H:%M UTC")


def get_local_update_status() -> dict[str, object]:
    local_commit = _read_local_commit()
    return {
        "app_version": settings.app_version,
        "local_commit": local_commit,
        "local_commit_short": local_commit[:7] if local_commit else None,
        "github_url": f"https://github.com/{settings.github_owner}/{settings.github_repo}",
        "branch": settings.github_branch,
        "remote_commit": None,
        "remote_commit_short": None,
        "remote_message": None,
        "remote_committed_at": None,
        "remote_committed_at_label": None,
        "remote_url": f"https://github.com/{settings.github_owner}/{settings.github_repo}",
        "update_available": None,
        "update_check_error": None,
        "can_update": True,
    }


def fetch_remote_update_status() -> dict[str, object]:
    url = f"https://api.github.com/repos/{settings.github_owner}/{settings.github_repo}/commits/{settings.github_branch}"
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "UploadPicker-Updater",
        },
    )
    with urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    commit = str(payload.get("sha", "")).strip() or None
    html_url = payload.get("html_url") or f"https://github.com/{settings.github_owner}/{settings.github_repo}"
    commit_info = payload.get("commit", {})
    committer = commit_info.get("committer", {})
    message = str(commit_info.get("message", "")).strip() or None
    committed_at = str(committer.get("date", "")).strip() or None
    return {
        "remote_commit": commit,
        "remote_commit_short": commit[:7] if commit else None,
        "remote_message": message,
        "remote_committed_at": committed_at,
        "remote_committed_at_label": _format_datetime(committed_at),
        "remote_url": html_url,
    }


def get_update_status() -> dict[str, object]:
    local = get_local_update_status()
    try:
        remote = fetch_remote_update_status()
    except URLError as exc:
        return {
            **local,
            "can_update": True,
            "update_available": None,
            "update_check_error": f"GitHub に接続できませんでした: {exc.reason}",
        }
    except Exception as exc:
        return {
            **local,
            "can_update": True,
            "update_available": None,
            "update_check_error": f"更新確認に失敗しました: {exc}",
        }

    update_available = None
    if local["local_commit"] and remote["remote_commit"]:
        update_available = local["local_commit"] != remote["remote_commit"]

    return {
        **local,
        **remote,
        "can_update": True,
        "update_available": update_available,
        "update_check_error": None,
    }


def launch_github_update(target_pid: int) -> None:
    project_root = _project_root()
    updater = project_root / "Update UploadPicker.bat"
    if not updater.exists():
        raise FileNotFoundError(f"Updater script not found: {updater}")

    creationflags = 0
    if os.name == "nt":
        detached_process = getattr(subprocess, "DETACHED_PROCESS", 0)
        new_process_group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        creationflags = detached_process | new_process_group

    subprocess.Popen(
        [str(updater), str(target_pid)],
        cwd=project_root,
        creationflags=creationflags,
        close_fds=True,
    )
