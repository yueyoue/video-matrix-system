"""HTTP API client wrapper."""

import requests
from typing import Any

from .auth import auth

BASE_URL = "http://localhost:3000/api"
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
    resp = requests.post(f"{BASE_URL}/auth/login",
                         json={"username": username, "password": password},
                         timeout=_TIMEOUT)
    return _handle(resp)


def get_user_info() -> dict:
    return _handle(requests.get(f"{BASE_URL}/auth/me", headers=_headers(), timeout=_TIMEOUT))


# ── Dashboard / Stats ──────────────────────────────────────────
def get_overview_stats() -> dict:
    return _handle(requests.get(f"{BASE_URL}/stats/overview", headers=_headers(), timeout=_TIMEOUT))


def get_recent_publish(limit: int = 20) -> dict:
    return _handle(requests.get(f"{BASE_URL}/stats/recent-publish",
                                headers=_headers(), params={"limit": limit}, timeout=_TIMEOUT))


def get_alerts() -> dict:
    return _handle(requests.get(f"{BASE_URL}/stats/alerts", headers=_headers(), timeout=_TIMEOUT))


# ── Analysis ───────────────────────────────────────────────────
def get_analysis_summary(params: dict) -> dict:
    return _handle(requests.get(f"{BASE_URL}/analysis/summary",
                                headers=_headers(), params=params, timeout=_TIMEOUT))


def get_analysis_by_platform(params: dict) -> dict:
    return _handle(requests.get(f"{BASE_URL}/analysis/by-platform",
                                headers=_headers(), params=params, timeout=_TIMEOUT))


def get_analysis_by_video(params: dict, page: int = 1, page_size: int = 20) -> dict:
    p = {**params, "page": page, "pageSize": page_size}
    return _handle(requests.get(f"{BASE_URL}/analysis/by-video",
                                headers=_headers(), params=p, timeout=_TIMEOUT))


def export_analysis(params: dict) -> bytes:
    resp = requests.get(f"{BASE_URL}/analysis/export",
                        headers=_headers(), params=params, timeout=30)
    if resp.status_code >= 400:
        _handle(resp)
    return resp.content


# ── Accounts ───────────────────────────────────────────────────
def get_accounts(platform: str = "", page: int = 1, page_size: int = 20) -> dict:
    params: dict = {"page": page, "pageSize": page_size}
    if platform:
        params["platform"] = platform
    return _handle(requests.get(f"{BASE_URL}/accounts",
                                headers=_headers(), params=params, timeout=_TIMEOUT))


def get_account_counts() -> dict:
    return _handle(requests.get(f"{BASE_URL}/accounts/counts", headers=_headers(), timeout=_TIMEOUT))


def add_account(data: dict) -> dict:
    return _handle(requests.post(f"{BASE_URL}/accounts",
                                 headers=_headers(), json=data, timeout=_TIMEOUT))


def update_account(account_id: str, data: dict) -> dict:
    return _handle(requests.put(f"{BASE_URL}/accounts/{account_id}",
                                headers=_headers(), json=data, timeout=_TIMEOUT))


def delete_account(account_id: str) -> dict:
    return _handle(requests.delete(f"{BASE_URL}/accounts/{account_id}",
                                   headers=_headers(), timeout=_TIMEOUT))


def batch_check_accounts(account_ids: list[str]) -> dict:
    return _handle(requests.post(f"{BASE_URL}/accounts/batch-check",
                                 headers=_headers(), json={"ids": account_ids}, timeout=_TIMEOUT))


# ── Video ──────────────────────────────────────────────────────
def upload_video(file_path: str) -> dict:
    with open(file_path, "rb") as f:
        resp = requests.post(f"{BASE_URL}/videos/upload",
                             headers={"Authorization": f"Bearer {auth.token}"},
                             files={"file": f}, timeout=60)
    return _handle(resp)


def get_videos(page: int = 1, page_size: int = 20) -> dict:
    return _handle(requests.get(f"{BASE_URL}/videos",
                                headers=_headers(),
                                params={"page": page, "pageSize": page_size},
                                timeout=_TIMEOUT))


def start_clip(data: dict) -> dict:
    return _handle(requests.post(f"{BASE_URL}/videos/clip",
                                 headers=_headers(), json=data, timeout=_TIMEOUT))


def start_mix(data: dict) -> dict:
    return _handle(requests.post(f"{BASE_URL}/videos/mix",
                                 headers=_headers(), json=data, timeout=60))


def add_to_publish_queue(video_ids: list[str]) -> dict:
    return _handle(requests.post(f"{BASE_URL}/videos/to-queue",
                                 headers=_headers(), json={"videoIds": video_ids}, timeout=_TIMEOUT))


def delete_video(video_id: str) -> dict:
    return _handle(requests.delete(f"{BASE_URL}/videos/{video_id}",
                                   headers=_headers(), timeout=_TIMEOUT))


# ── Publish ────────────────────────────────────────────────────
def get_publish_rules() -> dict:
    return _handle(requests.get(f"{BASE_URL}/publish/rules", headers=_headers(), timeout=_TIMEOUT))


def save_publish_rules(data: dict) -> dict:
    return _handle(requests.put(f"{BASE_URL}/publish/rules",
                                headers=_headers(), json=data, timeout=_TIMEOUT))


def get_publish_queue(page: int = 1, page_size: int = 20) -> dict:
    return _handle(requests.get(f"{BASE_URL}/publish/queue",
                                headers=_headers(),
                                params={"page": page, "pageSize": page_size},
                                timeout=_TIMEOUT))


def remove_from_queue(item_id: str) -> dict:
    return _handle(requests.delete(f"{BASE_URL}/publish/queue/{item_id}",
                                   headers=_headers(), timeout=_TIMEOUT))


# ── Config ─────────────────────────────────────────────────────
def get_platform_config(platform: str) -> dict:
    return _handle(requests.get(f"{BASE_URL}/config/{platform}",
                                headers=_headers(), timeout=_TIMEOUT))


def save_platform_config(platform: str, data: dict) -> dict:
    return _handle(requests.put(f"{BASE_URL}/config/{platform}",
                                headers=_headers(), json=data, timeout=_TIMEOUT))


def reset_platform_config(platform: str) -> dict:
    return _handle(requests.post(f"{BASE_URL}/config/{platform}/reset",
                                 headers=_headers(), timeout=_TIMEOUT))


# ── Logs ───────────────────────────────────────────────────────
def get_logs(params: dict, page: int = 1, page_size: int = 50) -> dict:
    p = {**params, "page": page, "pageSize": page_size}
    return _handle(requests.get(f"{BASE_URL}/logs",
                                headers=_headers(), params=p, timeout=_TIMEOUT))


def export_logs(params: dict) -> bytes:
    resp = requests.get(f"{BASE_URL}/logs/export",
                        headers=_headers(), params=params, timeout=30)
    if resp.status_code >= 400:
        _handle(resp)
    return resp.content
