"""Token management & authentication state."""

import json
import os
import time
from pathlib import Path

_TOKEN_FILE = Path.home() / ".video-matrix" / "token.json"


class AuthManager:
    """Manages JWT token persistence and validity."""

    def __init__(self):
        self._token: str | None = None
        self._user: dict | None = None
        self._expires_at: float = 0
        self._load()

    # ── persistence ────────────────────────────────────────────
    def _load(self):
        if _TOKEN_FILE.exists():
            try:
                data = json.loads(_TOKEN_FILE.read_text())
                self._token = data.get("token")
                self._user = data.get("user")
                self._expires_at = data.get("expires_at", 0)
            except Exception:
                pass

    def _save(self):
        _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        _TOKEN_FILE.write_text(json.dumps({
            "token": self._token,
            "user": self._user,
            "expires_at": self._expires_at,
        }, ensure_ascii=False, indent=2))

    # ── public API ─────────────────────────────────────────────
    @property
    def token(self) -> str | None:
        return self._token

    @property
    def user(self) -> dict | None:
        return self._user

    @property
    def is_valid(self) -> bool:
        if not self._token:
            return False
        if self._expires_at and time.time() > self._expires_at:
            return False
        return True

    def set_token(self, token: str, user: dict | None = None, expires_in: int = 86400):
        self._token = token
        self._user = user
        self._expires_at = time.time() + expires_in
        self._save()

    def clear(self):
        self._token = None
        self._user = None
        self._expires_at = 0
        try:
            _TOKEN_FILE.unlink(missing_ok=True)
        except Exception:
            pass


# Global singleton
auth = AuthManager()
