"""HTTP API client wrapper — matches server routes."""

import os
import sys
import requests
import traceback
from datetime import datetime
from typing import Any

from .auth import auth

# ── Debug logging ──────────────────────────────────────────────
_debug_log_path = os.path.join(os.path.expanduser('~'), '.video-matrix', 'debug.log')

def _debug_log(msg: str):
    """Write debug info to log file."""
    try:
        os.makedirs(os.path.dirname(_debug_log_path), exist_ok=True)
        with open(_debug_log_path, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass

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


def _api_url(path: str) -> str:
    """Construct API URL with .php suffix.
    /auth/login -> /auth/login.php
    /users/5    -> /users.php?_r=5
    /ai/config  -> /ai/config.php
    """
    parts = [p for p in path.split('/') if p]
    if not parts:
        return BASE_URL
    first = parts[0].replace('-', '_')
    if len(parts) == 1:
        return f"{BASE_URL}/{first}.php"
    rest = parts[1:]
    if first in ('auth', 'ai'):
        return f"{BASE_URL}/{first}/{'/'.join(rest)}.php"
    else:
        return f"{BASE_URL}/{first}.php?_r={'/'.join(rest)}"


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
    _debug_log(f"API响应: {resp.status_code} {resp.url}")
    _debug_log(f"响应内容: {resp.text[:500]}")
    if resp.status_code == 401:
        auth.clear()
        raise ApiError(401, "登录已过期，请重新登录")
    try:
        data = resp.json()
    except Exception:
        data = {"message": resp.text or "未知错误"}
        _debug_log(f"JSON解析失败: {resp.text[:200]}")
    if resp.status_code >= 400:
        raise ApiError(resp.status_code, data.get("message", f"请求失败 ({resp.status_code})"))
    return data


# ── Auth ───────────────────────────────────────────────────────
def login(username: str, password: str) -> dict:
    return _handle(requests.post(_api_url("/auth/login"),
                                 json={"username": username, "password": password},
                                 timeout=_TIMEOUT))


def get_profile() -> dict:
    return _handle(requests.get(_api_url("/auth/profile"), headers=_headers(), timeout=_TIMEOUT))


# ── Stats ──────────────────────────────────────────────────────
def get_stats_overview() -> dict:
    return _handle(requests.get(_api_url("/stats/overview"), headers=_headers(), timeout=_TIMEOUT))


def get_stats_users(date: str = "") -> dict:
    params = {}
    if date:
        params["date"] = date
    return _handle(requests.get(_api_url("/stats/users"), headers=_headers(), params=params, timeout=_TIMEOUT))


def get_stats_platforms(date: str = "") -> dict:
    params = {}
    if date:
        params["date"] = date
    return _handle(requests.get(_api_url("/stats/platforms"), headers=_headers(), params=params, timeout=_TIMEOUT))


def get_stats_analysis(params: dict) -> dict:
    return _handle(requests.get(_api_url("/stats/analysis"), headers=_headers(), params=params, timeout=_TIMEOUT))


# ── Accounts ───────────────────────────────────────────────────
def get_accounts(platform: str = "", page: int = 1, page_size: int = 20) -> dict:
    params: dict = {"page": page, "pageSize": page_size}
    if platform:
        params["platform"] = platform
    return _handle(requests.get(_api_url("/accounts"), headers=_headers(), params=params, timeout=_TIMEOUT))


def add_account(data: dict) -> dict:
    return _handle(requests.post(_api_url("/accounts"), headers=_headers(), json=data, timeout=_TIMEOUT))


def update_account(account_id: int, data: dict) -> dict:
    return _handle(requests.put(_api_url(f"/accounts/{account_id}"), headers=_headers(), json=data, timeout=_TIMEOUT))


def delete_account(account_id: int) -> dict:
    return _handle(requests.delete(_api_url(f"/accounts/{account_id}"), headers=_headers(), timeout=_TIMEOUT))


def check_account(account_id: int) -> dict:
    return _handle(requests.post(_api_url(f"/accounts/{account_id}/check"), headers=_headers(), timeout=_TIMEOUT))


# ── Videos ─────────────────────────────────────────────────────
def get_videos(page: int = 1, page_size: int = 20) -> dict:
    return _handle(requests.get(_api_url("/videos"), headers=_headers(),
                                params={"page": page, "pageSize": page_size}, timeout=_TIMEOUT))


def cut_video(data: dict) -> dict:
    return _handle(requests.post(_api_url("/videos/cut"), headers=_headers(), json=data, timeout=60))


def mix_video(data: dict) -> dict:
    return _handle(requests.post(_api_url("/videos/mix"), headers=_headers(), json=data, timeout=60))


def delete_video(video_id: int) -> dict:
    return _handle(requests.delete(_api_url(f"/videos/{video_id}"), headers=_headers(), timeout=_TIMEOUT))


# ── Publish ────────────────────────────────────────────────────
def get_publish_queue(page: int = 1) -> dict:
    return _handle(requests.get(_api_url("/publish/queue"), headers=_headers(),
                                params={"page": page}, timeout=_TIMEOUT))


def get_publish_rule() -> dict:
    return _handle(requests.get(_api_url("/publish/rule"), headers=_headers(), timeout=_TIMEOUT))


def save_publish_rule(data: dict) -> dict:
    return _handle(requests.post(_api_url("/publish/rule"), headers=_headers(), json=data, timeout=_TIMEOUT))


def publish_now(record_id: int) -> dict:
    return _handle(requests.post(_api_url(f"/publish/{record_id}/publishNow"), headers=_headers(), timeout=_TIMEOUT))


def cancel_publish(record_id: int) -> dict:
    return _handle(requests.delete(_api_url(f"/publish/{record_id}"), headers=_headers(), timeout=_TIMEOUT))


# ── AI ─────────────────────────────────────────────────────────
def get_ai_voices() -> dict:
    return _handle(requests.get(_api_url("/ai/voices"), headers=_headers(), timeout=_TIMEOUT))


def add_ai_voice(data: dict) -> dict:
    return _handle(requests.post(_api_url("/ai/voices"), headers=_headers(), json=data, timeout=_TIMEOUT))


def update_ai_voice(voice_id: int, data: dict) -> dict:
    return _handle(requests.put(_api_url(f"/ai/voices/{voice_id}"), headers=_headers(), json=data, timeout=_TIMEOUT))


def get_ai_config() -> dict:
    return _handle(requests.get(_api_url("/ai/config"), headers=_headers(), timeout=_TIMEOUT))


def update_ai_config(data: dict) -> dict:
    return _handle(requests.put(_api_url("/ai/config"), headers=_headers(), json=data, timeout=_TIMEOUT))


def test_ai_connection() -> dict:
    return _handle(requests.post(_api_url("/ai/test"), headers=_headers(), timeout=30))


# ── Platform Config ────────────────────────────────────────────
def get_platform_config(platform: str) -> dict:
    return _handle(requests.get(_api_url(f"/platform-config/{platform}"), headers=_headers(), timeout=_TIMEOUT))


def update_platform_config(platform: str, data: dict) -> dict:
    return _handle(requests.put(_api_url(f"/platform-config/{platform}"), headers=_headers(), json=data, timeout=_TIMEOUT))


def reset_platform_config(platform: str) -> dict:
    return _handle(requests.post(_api_url(f"/platform-config/{platform}/reset"), headers=_headers(), timeout=_TIMEOUT))


# ── Versions ───────────────────────────────────────────────────
def get_versions() -> dict:
    return _handle(requests.get(_api_url("/versions"), headers=_headers(), timeout=_TIMEOUT))


def publish_version(data: dict) -> dict:
    return _handle(requests.post(_api_url("/versions"), headers=_headers(), json=data, timeout=_TIMEOUT))


def update_version(version_id: int, data: dict) -> dict:
    return _handle(requests.put(_api_url(f"/versions/{version_id}"), headers=_headers(), json=data, timeout=_TIMEOUT))


def get_latest_version() -> dict:
    return _handle(requests.get(_api_url("/versions/latest"), headers=_headers(), timeout=_TIMEOUT))


# ── Logs ───────────────────────────────────────────────────────
def get_logs(params: dict = None, page: int = 1, page_size: int = 50) -> dict:
    p = {**(params or {}), "page": page, "pageSize": page_size}
    return _handle(requests.get(_api_url("/logs"), headers=_headers(), params=p, timeout=_TIMEOUT))


def export_logs() -> bytes:
    resp = requests.get(_api_url("/logs/export"), headers=_headers(), timeout=30)
    if resp.status_code >= 400:
        _handle(resp)
    return resp.content


# ── Upload ─────────────────────────────────────────────────────
def upload_file(file_path: str) -> dict:
    with open(file_path, "rb") as f:
        resp = requests.post(_api_url("/upload"),
                             headers={"Authorization": f"Bearer {auth.token}"},
                             files={"file": f}, timeout=120)
    return _handle(resp)


# ── Aliases & missing functions (views expect these names) ─────

def get_overview_stats() -> dict:
    return get_stats_overview()


def get_user_info() -> dict:
    return get_profile()


def get_publish_rules() -> dict:
    return get_publish_rule()


def save_publish_rules(data: dict) -> dict:
    return save_publish_rule(data)


def save_platform_config(platform: str, data: dict) -> dict:
    return update_platform_config(platform, data)


def get_analysis_summary(params: dict) -> dict:
    return _handle(requests.get(_api_url("/stats/analysis"), headers=_headers(),
                                params={**params, "type": "summary"}, timeout=_TIMEOUT))


def get_analysis_by_platform(params: dict) -> dict:
    return _handle(requests.get(_api_url("/stats/analysis"), headers=_headers(),
                                params={**params, "type": "platform"}, timeout=_TIMEOUT))


def get_analysis_by_video(params: dict, page: int = 1) -> dict:
    return _handle(requests.get(_api_url("/stats/analysis"), headers=_headers(),
                                params={**params, "type": "video", "page": page}, timeout=_TIMEOUT))


def export_analysis(params: dict) -> bytes:
    resp = requests.get(_api_url("/stats/analysis"), headers=_headers(),
                        params={**params, "export": 1}, timeout=30)
    if resp.status_code >= 400:
        _handle(resp)
    return resp.content


def remove_from_queue(queue_id: int) -> dict:
    return _handle(requests.delete(_api_url(f"/publish/{queue_id}"),
                                   headers=_headers(), timeout=_TIMEOUT))


def add_to_publish_queue(video_ids: list) -> dict:
    return _handle(requests.post(_api_url("/publish/queue"), headers=_headers(),
                                 json={"video_ids": video_ids}, timeout=_TIMEOUT))


def batch_check_accounts(ids: list) -> dict:
    return _handle(requests.post(_api_url("/accounts/batch-check"), headers=_headers(),
                                 json={"ids": ids}, timeout=60))


def start_clip(data: dict) -> dict:
    return _handle(requests.post(_api_url("/videos/cut"), headers=_headers(),
                                 json=data, timeout=60))


def start_mix(data: dict) -> dict:
    return _handle(requests.post(_api_url("/videos/mix"), headers=_headers(),
                                 json=data, timeout=60))


def export_logs(params: dict = None) -> bytes:
    resp = requests.get(_api_url("/logs/export"), headers=_headers(),
                        params=params or {}, timeout=30)
    if resp.status_code >= 400:
        _handle(resp)
    return resp.content
