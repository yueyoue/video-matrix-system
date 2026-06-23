"""Login page with environment check animation."""

import threading
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QProgressBar, QFrame, QApplication
)
from ..styles.theme import (
    PRIMARY, BG_COLOR, BORDER_COLOR, TEXT_COLOR, TEXT_SECONDARY,
    BTN_PRIMARY, INPUT_STYLE, CHECKBOX_STYLE, PROGRESS_STYLE, DANGER
)
from ..auth import auth
from .. import api


class _LoginWorker(QThread):
    """Background thread for API login."""
    success = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, username: str, password: str):
        super().__init__()
        self._u = username
        self._p = password

    def run(self):
        try:
            result = api.login(self._u, self._p)
            self.success.emit(result)
        except Exception as e:
            self.failed.emit(str(e))


class _EnvCheckWorker(QThread):
    """Background thread for real environment check + ffmpeg auto-install."""
    progress = pyqtSignal(str, int)  # message, percent
    finished_ok = pyqtSignal(bool)   # all_ok

    def run(self):
        import shutil, subprocess
        all_ok = True

        # Step 1: FFmpeg 检测
        self.progress.emit("🔍 正在检测 FFmpeg...", 10)
        from .. import ffmpeg as ff
        ff_available = ff.is_ffmpeg_available()
        if ff_available:
            self.progress.emit("✅ FFmpeg 已安装", 30)
        else:
            self.progress.emit("⚠️ 未检测到 FFmpeg，正在自动下载...", 15)
            def _dl_cb(percent, msg):
                # Map download 0-100 to our 15-70 range
                mapped = 15 + int(percent * 55 / 100)
                self.progress.emit(msg, mapped)
            ok = ff.download_ffmpeg(progress_callback=_dl_cb)
            if ok:
                # Re-check
                ff._ffmpeg_path = None
                ff._ffprobe_path = None
                if ff.is_ffmpeg_available():
                    self.progress.emit("✅ FFmpeg 安装成功!", 70)
                else:
                    self.progress.emit("❌ FFmpeg 安装后仍无法使用", 70)
                    all_ok = False
            else:
                self.progress.emit("❌ FFmpeg 自动下载失败，请手动安装", 70)
                all_ok = False

        # Step 2: Chromium 检测
        self.progress.emit("🔍 正在检测 Chromium...", 75)
        import shutil as _shutil
        chrome_found = _shutil.which('chromium') or _shutil.which('chrome') or _shutil.which('google-chrome')
        if chrome_found:
            self.progress.emit("✅ Chromium 已安装", 82)
        else:
            self.progress.emit("⚠️ 未检测到 Chromium（部分功能可能受限）", 82)

        # Step 3: 运行库检测
        self.progress.emit("🔍 正在检测运行库...", 86)
        try:
            import PyQt6
            self.progress.emit("✅ PyQt6 运行库正常", 90)
        except ImportError:
            self.progress.emit("❌ 缺少 PyQt6 运行库", 90)
            all_ok = False

        # Step 4: 网络连接检测
        self.progress.emit("🔍 正在检测网络连接...", 93)
        try:
            import urllib.request
            urllib.request.urlopen("https://www.baidu.com", timeout=5)
            self.progress.emit("✅ 网络连接正常", 97)
        except Exception:
            self.progress.emit("⚠️ 网络连接异常", 97)

        self.progress.emit("环境自检完成 ✅" if all_ok else "环境自检完成（部分异常）", 100)
        self.finished_ok.emit(all_ok)


class LoginView(QWidget):
    """Login page with credentials form and environment check animation."""

    login_success = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG_COLOR};")
        self._worker = None
        self._init_ui()

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # card
        card = QFrame()
        card.setFixedSize(420, 650)
        card.setStyleSheet(f"""
            QFrame {{
                background: white;
                border: 1px solid {BORDER_COLOR};
                border-radius: 12px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(40, 32, 40, 32)
        card_layout.setSpacing(16)

        # title
        title = QLabel("🎬 矩阵运营系统")
        title.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {TEXT_COLOR};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(title)

        subtitle = QLabel("请登录您的账号")
        subtitle.setStyleSheet(f"font-size: 14px; color: {TEXT_SECONDARY};")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(subtitle)

        card_layout.addSpacing(8)

        # server address
        server_label = QLabel("服务器地址")
        server_label.setStyleSheet(f"font-size: 13px; color: {TEXT_COLOR}; font-weight: 600;")
        card_layout.addWidget(server_label)

        self._server_input = QLineEdit()
        self._server_input.setPlaceholderText("例如: https://sp.tthsdd.top/api")
        self._server_input.setStyleSheet(INPUT_STYLE)
        self._server_input.setMinimumHeight(40)
        # load saved server url
        from pathlib import Path
        import json as _json
        cfg_path = Path.home() / ".video-matrix" / "config.json"
        saved_url = ""
        if cfg_path.exists():
            try:
                saved_url = _json.loads(cfg_path.read_text()).get("server_url", "")
            except Exception:
                pass
        self._server_input.setText(saved_url)
        card_layout.addWidget(self._server_input)

        card_layout.addSpacing(8)

        # username
        self._user_input = QLineEdit()
        self._user_input.setPlaceholderText("请输入用户名")
        self._user_input.setStyleSheet(INPUT_STYLE)
        self._user_input.setMinimumHeight(40)
        card_layout.addWidget(self._user_input)

        # password
        self._pass_input = QLineEdit()
        self._pass_input.setPlaceholderText("请输入密码")
        self._pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._pass_input.setStyleSheet(INPUT_STYLE)
        self._pass_input.setMinimumHeight(40)
        self._pass_input.returnPressed.connect(self._on_login)
        card_layout.addWidget(self._pass_input)

        # remember password
        cb_layout = QHBoxLayout()
        self._remember_cb = QCheckBox("记住密码")
        self._remember_cb.setStyleSheet(CHECKBOX_STYLE)
        cb_layout.addWidget(self._remember_cb)
        cb_layout.addStretch()
        card_layout.addLayout(cb_layout)

        # login button
        self._login_btn = QPushButton("登  录")
        self._login_btn.setStyleSheet(BTN_PRIMARY)
        self._login_btn.setFixedHeight(42)
        self._login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._login_btn.clicked.connect(self._on_login)
        card_layout.addWidget(self._login_btn)

        # error label
        self._error_label = QLabel("")
        self._error_label.setStyleSheet(f"color: {DANGER}; font-size: 12px;")
        self._error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_label.setWordWrap(True)
        card_layout.addWidget(self._error_label)

        card_layout.addSpacing(8)

        # environment check section
        env_title = QLabel("环境自检")
        env_title.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {TEXT_COLOR};")
        card_layout.addWidget(env_title)

        self._env_progress = QProgressBar()
        self._env_progress.setStyleSheet(PROGRESS_STYLE)
        self._env_progress.setFixedHeight(8)
        self._env_progress.setRange(0, 100)
        self._env_progress.setValue(0)
        card_layout.addWidget(self._env_progress)

        self._env_label = QLabel("就绪")
        self._env_label.setStyleSheet(f"font-size: 12px; color: {TEXT_SECONDARY};")
        card_layout.addWidget(self._env_label)

        card_layout.addStretch()

        # version
        ver = QLabel("v1.0.0")
        ver.setStyleSheet(f"font-size: 12px; color: {TEXT_SECONDARY};")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(ver)

        outer.addWidget(card)

        # start real environment check
        QTimer.singleShot(500, self._run_env_check)

    # ── environment check (real) ───────────────────────────────
    def _run_env_check(self):
        self._env_worker = _EnvCheckWorker()
        self._env_worker.progress.connect(self._on_env_progress)
        self._env_worker.finished_ok.connect(self._on_env_done)
        self._env_worker.start()

    def _on_env_progress(self, msg: str, val: int):
        self._env_label.setText(msg)
        self._env_progress.setValue(val)

    def _on_env_done(self, all_ok: bool):
        if not all_ok:
            self._env_label.setText(self._env_label.text() + " （可尝试登录后在设置中修复）")

    # ── login logic ────────────────────────────────────────────
    def _on_login(self):
        username = self._user_input.text().strip()
        password = self._pass_input.text().strip()
        server_url = self._server_input.text().strip().rstrip('/')

        if not server_url:
            self._error_label.setText("请输入服务器地址")
            return
        if not username or not password:
            self._error_label.setText("请输入用户名和密码")
            return

        # save server url
        from pathlib import Path
        import json as _json
        cfg_dir = Path.home() / ".video-matrix"
        cfg_dir.mkdir(exist_ok=True)
        cfg_path = cfg_dir / "config.json"
        cfg = {}
        if cfg_path.exists():
            try:
                cfg = _json.loads(cfg_path.read_text())
            except Exception:
                pass
        cfg["server_url"] = server_url
        cfg_path.write_text(_json.dumps(cfg, ensure_ascii=False, indent=2))
        from .. import api
        api.BASE_URL = server_url

        self._error_label.setText("")
        self._login_btn.setEnabled(False)
        self._login_btn.setText("登录中...")

        self._worker = _LoginWorker(username, password)
        self._worker.success.connect(self._on_success)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_success(self, data: dict):
        self._login_btn.setEnabled(True)
        self._login_btn.setText("登  录")
        token = data.get("token", data.get("data", {}).get("token", ""))
        user = data.get("user", data.get("data", {}).get("user", {}))
        if not token:
            # fallback: if API returns token directly in data
            token = data.get("data", token) if isinstance(data.get("data"), str) else token
        auth.set_token(token, user)
        self.login_success.emit()

    def _on_failed(self, msg: str):
        self._login_btn.setEnabled(True)
        self._login_btn.setText("登  录")
        self._error_label.setText(msg)
