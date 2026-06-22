"""Sidebar navigation widget."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSizePolicy, QSpacerItem
)
from ..styles.theme import (
    SIDEBAR_BG, SIDEBAR_WIDTH, PRIMARY, TEXT_COLOR, TEXT_SECONDARY,
    BORDER_COLOR, DANGER, BTN_TEXT, BTN_DANGER_TEXT
)


class SidebarMenu(QPushButton):
    """Single sidebar menu item."""

    def __init__(self, icon: str, text: str, parent=None):
        super().__init__(f"  {icon}  {text}", parent)
        self.setCheckable(True)
        self.setFixedHeight(42)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 8px;
                text-align: left;
                padding-left: 16px;
                font-size: 14px;
                color: {TEXT_COLOR};
            }}
            QPushButton:hover {{
                background: #F2F3F5;
            }}
            QPushButton:checked {{
                background: {PRIMARY}12;
                color: {PRIMARY};
                font-weight: 600;
            }}
        """)


class Sidebar(QWidget):
    """Left sidebar with navigation menu and user info."""

    menu_changed = pyqtSignal(str)  # emits page key
    logout_clicked = pyqtSignal()

    MENU_ITEMS = [
        ("📊", "数据总览", "dashboard"),
        ("📈", "数据分析", "analysis"),
        ("👥", "账号管理", "account"),
        ("🎬", "视频处理", "video"),
        ("🚀", "发布调度", "publish"),
        ("⚙️", "接口配置", "config"),
        ("📋", "日志中心", "log"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(SIDEBAR_WIDTH)
        self.setStyleSheet(f"""
            QWidget {{
                background: {SIDEBAR_BG};
                border-right: 1px solid {BORDER_COLOR};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(4)

        # ── Logo ───────────────────────────────────────────────
        logo_layout = QHBoxLayout()
        logo_icon = QLabel("🎬")
        logo_icon.setStyleSheet("font-size: 24px;")
        logo_layout.addWidget(logo_icon)
        logo_text = QLabel("矩阵运营系统")
        logo_text.setStyleSheet(f"""
            font-size: 16px;
            font-weight: 700;
            color: {TEXT_COLOR};
        """)
        logo_layout.addWidget(logo_text)
        logo_layout.addStretch()
        layout.addLayout(logo_layout)

        # separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background: {BORDER_COLOR}; max-height: 1px;")
        layout.addSpacing(12)
        layout.addWidget(sep)
        layout.addSpacing(12)

        # ── Menu Items ─────────────────────────────────────────
        self._menus: dict[str, SidebarMenu] = {}
        for icon, text, key in self.MENU_ITEMS:
            btn = SidebarMenu(icon, text)
            btn.clicked.connect(lambda checked, k=key: self._on_menu_click(k))
            self._menus[key] = btn
            layout.addWidget(btn)

        layout.addStretch()

        # ── User Info Footer ───────────────────────────────────
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"background: {BORDER_COLOR}; max-height: 1px;")
        layout.addWidget(sep2)
        layout.addSpacing(8)

        self._user_label = QLabel("👤 未登录")
        self._user_label.setStyleSheet(f"font-size: 13px; color: {TEXT_COLOR}; padding: 4px 16px;")
        layout.addWidget(self._user_label)

        self._quota_label = QLabel("📦 配额: --")
        self._quota_label.setStyleSheet(f"font-size: 12px; color: {TEXT_SECONDARY}; padding: 2px 16px;")
        layout.addWidget(self._quota_label)

        self._version_label = QLabel("🏷️ v1.0.0")
        self._version_label.setStyleSheet(f"font-size: 12px; color: {TEXT_SECONDARY}; padding: 2px 16px;")
        layout.addWidget(self._version_label)

        # bottom buttons
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(8, 0, 8, 0)

        update_btn = QPushButton("检查更新")
        update_btn.setStyleSheet(BTN_TEXT)
        update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        update_btn.setFixedHeight(28)
        btn_layout.addWidget(update_btn)

        logout_btn = QPushButton("退出登录")
        logout_btn.setStyleSheet(BTN_DANGER_TEXT)
        logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_btn.setFixedHeight(28)
        logout_btn.clicked.connect(self.logout_clicked.emit)
        btn_layout.addWidget(logout_btn)

        layout.addLayout(btn_layout)

        # default selection
        self._current_key = "dashboard"
        self._menus["dashboard"].setChecked(True)

    def _on_menu_click(self, key: str):
        if key == self._current_key:
            return
        self._menus[self._current_key].setChecked(False)
        self._current_key = key
        self._menus[key].setChecked(True)
        self.menu_changed.emit(key)

    def set_user_info(self, username: str, quota: str = ""):
        self._user_label.setText(f"👤 {username}")
        if quota:
            self._quota_label.setText(f"📦 配额: {quota}")

    def set_active(self, key: str):
        if key in self._menus:
            self._on_menu_click(key)
