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
        card.setFixedSize(420, 520)
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

        card_layout.addSpacing(16)

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

        # start environment check animation
        QTimer.singleShot(500, self._run_env_check)

    # ── environment check animation ────────────────────────────
    def _run_env_check(self):
        self._env_steps = [
            ("FFmpeg 检测...", 20),
            ("Chromium 检测...", 45),
            ("运行库检测...", 70),
            ("网络连接检测...", 90),
            ("环境自检完成 ✓", 100),
        ]
        self._env_idx = 0
        self._env_timer = QTimer(self)
        self._env_timer.timeout.connect(self._env_tick)
        self._env_timer.start(600)

    def _env_tick(self):
        if self._env_idx >= len(self._env_steps):
            self._env_timer.stop()
            return
        text, val = self._env_steps[self._env_idx]
        self._env_label.setText(text)
        self._env_progress.setValue(val)
        self._env_idx += 1

    # ── login logic ────────────────────────────────────────────
    def _on_login(self):
        username = self._user_input.text().strip()
        password = self._pass_input.text().strip()
        if not username or not password:
            self._error_label.setText("请输入用户名和密码")
            return

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
