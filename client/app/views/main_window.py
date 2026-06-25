"""Main window with sidebar and stacked content area."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QStackedWidget, QPushButton, QFrame, QApplication
)
from ..styles.theme import (
    BG_COLOR, PRIMARY, TEXT_COLOR, TEXT_SECONDARY, BORDER_COLOR,
    HEADER_HEIGHT, BTN_PRIMARY_SM, BTN_DEFAULT
)
from ..widgets.sidebar import Sidebar
from ..widgets.toast import Toast
from ..auth import auth
from .. import api

from .dashboard import DashboardView
from .analysis import AnalysisView
from .account import AccountView
from .video import VideoView
from .publish import PublishView
from .config import ConfigView
from .log_view import LogView


class _UserInfoWorker(QThread):
    done = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def run(self):
        try:
            result = api.get_user_info()
            self.done.emit(result)
        except Exception as e:
            self.failed.emit(str(e))


class MainWindow(QMainWindow):
    """Application main window."""

    logout_signal = pyqtSignal()

    PAGE_KEYS = ["dashboard", "analysis", "account", "video", "publish", "config", "log"]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("矩阵运营系统")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)

        self._worker = None
        self._init_ui()
        self._load_user_info()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Sidebar ────────────────────────────────────────────
        self._sidebar = Sidebar()
        self._sidebar.menu_changed.connect(self._on_menu_changed)
        self._sidebar.logout_clicked.connect(self._on_logout)
        main_layout.addWidget(self._sidebar)

        # ── Right content area ─────────────────────────────────
        right = QWidget()
        right.setStyleSheet(f"background: {BG_COLOR};")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # top bar
        top_bar = QFrame()
        top_bar.setFixedHeight(HEADER_HEIGHT)
        top_bar.setStyleSheet(f"""
            QFrame {{
                background: white;
                border-bottom: 1px solid {BORDER_COLOR};
            }}
        """)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(24, 0, 24, 0)

        self._page_title = QLabel("数据总览")
        self._page_title.setStyleSheet(f"""
            font-size: 18px;
            font-weight: 600;
            color: {TEXT_COLOR};
        """)
        top_layout.addWidget(self._page_title)

        top_layout.addStretch()

        self._status_label = QLabel("🟢 运行中")
        self._status_label.setStyleSheet(f"font-size: 13px; color: #00B42A;")
        top_layout.addWidget(self._status_label)

        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.setStyleSheet(BTN_DEFAULT)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.setFixedHeight(34)
        refresh_btn.clicked.connect(self._on_refresh)
        top_layout.addWidget(refresh_btn)

        right_layout.addWidget(top_bar)

        # stacked pages
        self._stack = QStackedWidget()
        self._pages: dict[str, QWidget] = {}

        self._pages["dashboard"] = DashboardView()
        self._pages["analysis"] = AnalysisView()
        self._pages["account"] = AccountView()
        self._pages["video"] = VideoView()
        self._pages["publish"] = PublishView()
        self._pages["config"] = ConfigView()
        self._pages["log"] = LogView()

        for key in self.PAGE_KEYS:
            self._stack.addWidget(self._pages[key])

        right_layout.addWidget(self._stack, 1)
        main_layout.addWidget(right, 1)

        # 首次显示时加载默认页面数据
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(300, self._load_initial_page)

        # page titles
        self._page_titles = {
            "dashboard": "数据总览",
            "analysis": "数据分析",
            "account": "账号管理",
            "video": "视频处理",
            "publish": "发布调度",
            "config": "接口配置",
            "log": "日志中心",
        }

    def _load_initial_page(self):
        """Load data for the initial page (dashboard)."""
        from ..api import _debug_log
        _debug_log("[MainWindow] 初始加载仪表盘数据")
        page = self._pages.get("dashboard")
        if hasattr(page, "load_data"):
            page.load_data()

    def _on_menu_changed(self, key: str):
        idx = self.PAGE_KEYS.index(key) if key in self.PAGE_KEYS else 0
        self._stack.setCurrentIndex(idx)
        self._page_title.setText(self._page_titles.get(key, key))
        # load data for the page
        page = self._pages.get(key)
        if hasattr(page, "load_data"):
            page.load_data()

    def _on_refresh(self):
        current_idx = self._stack.currentIndex()
        key = self.PAGE_KEYS[current_idx] if current_idx < len(self.PAGE_KEYS) else ""
        page = self._pages.get(key)
        if hasattr(page, "load_data"):
            page.load_data()
            Toast.success(self, "已刷新")

    def _load_user_info(self):
        self._worker = _UserInfoWorker()
        self._worker.done.connect(self._on_user_info)
        self._worker.failed.connect(lambda m: None)  # silent fail
        self._worker.start()

    def _on_user_info(self, data: dict):
        d = data.get("data", data)
        username = d.get("username", d.get("name", "用户"))
        quota = d.get("quota", d.get("balance", ""))
        self._sidebar.set_user_info(username, str(quota) if quota else "")

    def _on_logout(self):
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, "确认退出", "确定要退出登录吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            auth.clear()
            self.logout_signal.emit()

    def _on_login_success(self):
        """Called after re-login."""
        self._load_user_info()
        self._sidebar.set_active("dashboard")
        self._on_menu_changed("dashboard")
