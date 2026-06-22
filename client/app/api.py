"""HTTP API client wrapper — matches server routes."""

import os
import requests
from typing import Any

from .auth import auth

# Allow overriding via environment variable or config file
import json as _json
from pathlib import Path as _Path

_cfg_path = _Path.home() / ".video-matrix" / "config.json"
_saved_url = ""
if _cfg_path.exists():
    try:
        _saved_url = _json.loads(_cfg_path.read_text()).get("server_url", "")
    except Exception:
        pass

BASE_URL = os.environ.get("API_BASE_URL", _saved_url or "http://localhost:3000/api")
_TIMEOUT = 15


class ApiError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(message)


def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    if auth.token:
        h["Authorization"] = f"Bearer {auth.token}"
    return h


def _handle(resp: requests.Response) -> Any:
    if resp.status_code == 401:
        auth.clear()
        raise ApiError(401, "登录已过期，请重新登录")
    try:
        data = resp.json()
    except Exception:
        data = {"message": resp.text or "未知错误"}
    if resp.status_code >= 400:
        raise ApiError(resp.status_code, data.get("message", f"请求失败 ({resp.status_code})"))
    return data


# ── Auth ───────────────────────────────────────────────────────
def login(username: str, password: str) -> dict:
    return _handle(requests.post(f"{BASE_URL}/auth/login",
                                 json={"username": username, "password": password},
                                 timeout=_TIMEOUT))


def get_profile() -> dict:
    return _handle(requests.get(f"{BASE_URL}/auth/profile", headers=_headers(), timeout=_TIMEOUT))


# ── Stats ──────────────────────────────────────────────────────
def get_stats_overview() -> dict:
    return _handle(requests.get(f"{BASE_URL}/stats/overview", headers=_headers(), timeout=_TIMEOUT))


def get_stats_users(date: str = "") -> dict:
    params = {}
    if date:
        params["date"] = date
    return _handle(requests.get(f"{BASE_URL}/stats/users", headers=_headers(), params=params, timeout=_TIMEOUT))


def get_stats_platforms(date: str = "") -> dict:
    params = {}
    if date:
        params["date"] = date
    return _handle(requests.get(f"{BASE_URL}/stats/platforms", headers=_headers(), params=params, timeout=_TIMEOUT))


def get_stats_analysis(params: dict) -> dict:
    return _handle(requests.get(f"{BASE_URL}/stats/analysis", headers=_headers(), params=params, timeout=_TIMEOUT))


# ── Accounts ───────────────────────────────────────────────────
def get_accounts(platform: str = "", page: int = 1, page_size: int = 20) -> dict:
    params: dict = {"page": page, "pageSize": page_size}
    if platform:
        params["platform"] = platform
    return _handle(requests.get(f"{BASE_URL}/accounts", headers=_headers(), params=params, timeout=_TIMEOUT))


def add_account(data: dict) -> dict:
    return _handle(requests.post(f"{BASE_URL}/accounts", headers=_headers(), json=data, timeout=_TIMEOUT))


def update_account(account_id: int, data: dict) -> dict:
    return _handle(requests.put(f"{BASE_URL}/accounts/{account_id}", headers=_headers(), json=data, timeout=_TIMEOUT))


def delete_account(account_id: int) -> dict:
    return _handle(requests.delete(f"{BASE_URL}/accounts/{account_id}", headers=_headers(), timeout=_TIMEOUT))


def check_account(account_id: int) -> dict:
    return _handle(requests.post(f"{BASE_URL}/accounts/{account_id}/check", headers=_headers(), timeout=_TIMEOUT))


# ── Videos ─────────────────────────────────────────────────────
def get_videos(page: int = 1, page_size: int = 20) -> dict:
    return _handle(requests.get(f"{BASE_URL}/videos", headers=_headers(),
                                params={"page": page, "pageSize": page_size}, timeout=_TIMEOUT))


def cut_video(data: dict) -> dict:
    return _handle(requests.post(f"{BASE_URL}/videos/cut", headers=_headers(), json=data, timeout=60))


def mix_video(data: dict) -> dict:
    return _handle(requests.post(f"{BASE_URL}/videos/mix", headers=_headers(), json=data, timeout=60))


def delete_video(video_id: int) -> dict:
    return _handle(requests.delete(f"{BASE_URL}/videos/{video_id}", headers=_headers(), timeout=_TIMEOUT))


# ── Publish ────────────────────────────────────────────────────
def get_publish_queue() -> dict:
    return _handle(requests.get(f"{BASE_URL}/publish/queue", headers=_headers(), timeout=_TIMEOUT))


def get_publish_rule() -> dict:
    return _handle(requests.get(f"{BASE_URL}/publish/rule", headers=_headers(), timeout=_TIMEOUT))


def save_publish_rule(data: dict) -> dict:
    return _handle(requests.post(f"{BASE_URL}/publish/rule", headers=_headers(), json=data, timeout=_TIMEOUT))


def publish_now(record_id: int) -> dict:
    return _handle(requests.post(f"{BASE_URL}/publish/{record_id}/publishNow", headers=_headers(), timeout=_TIMEOUT))


def cancel_publish(record_id: int) -> dict:
    return _handle(requests.delete(f"{BASE_URL}/publish/{record_id}", headers=_headers(), timeout=_TIMEOUT))


# ── AI ─────────────────────────────────────────────────────────
def get_ai_voices() -> dict:
    return _handle(requests.get(f"{BASE_URL}/ai/voices", headers=_headers(), timeout=_TIMEOUT))


def add_ai_voice(data: dict) -> dict:
    return _handle(requests.post(f"{BASE_URL}/ai/voices", headers=_headers(), json=data, timeout=_TIMEOUT))


def update_ai_voice(voice_id: int, data: dict) -> dict:
    return _handle(requests.put(f"{BASE_URL}/ai/voices/{voice_id}", headers=_headers(), json=data, timeout=_TIMEOUT))


def get_ai_config() -> dict:
    return _handle(requests.get(f"{BASE_URL}/ai/config", headers=_headers(), timeout=_TIMEOUT))


def update_ai_config(data: dict) -> dict:
    return _handle(requests.put(f"{BASE_URL}/ai/config", headers=_headers(), json=data, timeout=_TIMEOUT))


def test_ai_connection() -> dict:
    return _handle(requests.post(f"{BASE_URL}/ai/test", headers=_headers(), timeout=30))


# ── Platform Config ────────────────────────────────────────────
def get_platform_config(platform: str) -> dict:
    return _handle(requests.get(f"{BASE_URL}/platform-config/{platform}", headers=_headers(), timeout=_TIMEOUT))


def update_platform_config(platform: str, data: dict) -> dict:
    return _handle(requests.put(f"{BASE_URL}/platform-config/{platform}", headers=_headers(), json=data, timeout=_TIMEOUT))


def reset_platform_config(platform: str) -> dict:
    return _handle(requests.post(f"{BASE_URL}/platform-config/{platform}/reset", headers=_headers(), timeout=_TIMEOUT))


# ── Versions ───────────────────────────────────────────────────
def get_versions() -> dict:
    return _handle(requests.get(f"{BASE_URL}/versions", headers=_headers(), timeout=_TIMEOUT))


def publish_version(data: dict) -> dict:
    return _handle(requests.post(f"{BASE_URL}/versions", headers=_headers(), json=data, timeout=_TIMEOUT))


def update_version(version_id: int, data: dict) -> dict:
    return _handle(requests.put(f"{BASE_URL}/versions/{version_id}", headers=_headers(), json=data, timeout=_TIMEOUT))


def get_latest_version() -> dict:
    return _handle(requests.get(f"{BASE_URL}/versions/latest", headers=_headers(), timeout=_TIMEOUT))


# ── Logs ───────────────────────────────────────────────────────
def get_logs(params: dict = None, page: int = 1, page_size: int = 50) -> dict:
    p = {**(params or {}), "page": page, "pageSize": page_size}
    return _handle(requests.get(f"{BASE_URL}/logs", headers=_headers(), params=p, timeout=_TIMEOUT))


def export_logs() -> bytes:
    resp = requests.get(f"{BASE_URL}/logs/export", headers=_headers(), timeout=30)
    if resp.status_code >= 400:
        _handle(resp)
    return resp.content


# ── Upload ─────────────────────────────────────────────────────
def upload_file(file_path: str) -> dict:
    with open(file_path, "rb") as f:
        resp = requests.post(f"{BASE_URL}/upload",
                             headers={"Authorization": f"Bearer {auth.token}"},
                             files={"file": f}, timeout=120)
    return _handle(resp)
