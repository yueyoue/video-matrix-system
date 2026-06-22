"""Platform interface configuration view."""

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QLineEdit, QTabWidget, QFormLayout, QMessageBox, QSpinBox
)
from ..styles.theme import (
    BG_COLOR, CARD_STYLE, TEXT_COLOR, TEXT_SECONDARY, PRIMARY, SUCCESS,
    DANGER, BORDER_COLOR, BTN_PRIMARY, BTN_DEFAULT, BTN_DANGER, INPUT_STYLE,
    TAB_STYLE
)
from ..widgets.toast import Toast
from .. import api


class _ConfigWorker(QThread):
    done = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            result = self._func(*self._args, **self._kwargs)
            self.done.emit(result)
        except Exception as e:
            self.failed.emit(str(e))


class ConfigView(QWidget):
    """Platform interface configuration page."""

    PLATFORMS = [
        ("douyin", "抖音"),
        ("kuaishou", "快手"),
        ("xiaohongshu", "小红书"),
        ("shipinhao", "视频号"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers: list[_ConfigWorker] = []
        self._forms: dict[str, dict] = {}
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        title = QLabel("⚙️ 接口配置")
        title.setStyleSheet(f"font-size: 18px; font-weight: 600; color: {TEXT_COLOR};")
        layout.addWidget(title)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(TAB_STYLE)

        for key, label in self.PLATFORMS:
            tab = self._create_form(key)
            self._tabs.addTab(tab, label)

        layout.addWidget(self._tabs, 1)

    def _create_form(self, platform_key: str) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        card = QFrame()
        card.setStyleSheet(f"QFrame {{{CARD_STYLE} padding: 20px;}}")
        form_layout = QFormLayout(card)
        form_layout.setSpacing(14)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        fields = {}

        fields["backendUrl"] = QLineEdit()
        fields["backendUrl"].setPlaceholderText("创作者后台地址")
        fields["backendUrl"].setStyleSheet(INPUT_STYLE)
        form_layout.addRow("创作者后台地址:", fields["backendUrl"])

        fields["verifyApi"] = QLineEdit()
        fields["verifyApi"].setPlaceholderText("校验接口地址")
        fields["verifyApi"].setStyleSheet(INPUT_STYLE)
        form_layout.addRow("校验接口:", fields["verifyApi"])

        fields["listApi"] = QLineEdit()
        fields["listApi"].setPlaceholderText("作品列表接口")
        fields["listApi"].setStyleSheet(INPUT_STYLE)
        form_layout.addRow("作品列表接口:", fields["listApi"])

        fields["publishApi"] = QLineEdit()
        fields["publishApi"].setPlaceholderText("发布接口地址")
        fields["publishApi"].setStyleSheet(INPUT_STYLE)
        form_layout.addRow("发布接口:", fields["publishApi"])

        fields["selector"] = QLineEdit()
        fields["selector"].setPlaceholderText("CSS选择器")
        fields["selector"].setStyleSheet(INPUT_STYLE)
        form_layout.addRow("选择器:", fields["selector"])

        fields["cookieExpire"] = QSpinBox()
        fields["cookieExpire"].setRange(1, 365)
        fields["cookieExpire"].setValue(7)
        fields["cookieExpire"].setSuffix(" 天")
        fields["cookieExpire"].setStyleSheet(f"""
            QSpinBox {{
                border: 1px solid {BORDER_COLOR}; border-radius: 6px;
                padding: 8px 12px; font-size: 13px;
            }}
        """)
        form_layout.addRow("Cookie有效期:", fields["cookieExpire"])

        layout.addWidget(card)

        # buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        reset_btn = QPushButton("恢复默认")
        reset_btn.setStyleSheet(BTN_DEFAULT)
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.clicked.connect(lambda: self._on_reset(platform_key))
        btn_layout.addWidget(reset_btn)

        save_btn = QPushButton("保存配置")
        save_btn.setStyleSheet(BTN_PRIMARY)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(lambda: self._on_save(platform_key))
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)
        layout.addStretch()

        self._forms[platform_key] = fields
        return widget

    def load_data(self):
        """Load config for all platforms."""
        for key, _ in self.PLATFORMS:
            w = _ConfigWorker(api.get_platform_config, key)
            w.done.connect(lambda data, k=key: self._on_config(k, data))
            # Don't show error for missing config
            w.failed.connect(lambda m: None)
            self._workers.append(w)
            w.start()

    def _on_config(self, platform_key: str, data: dict):
        d = data.get("data", data)
        if not isinstance(d, dict):
            return
        fields = self._forms.get(platform_key, {})
        for name, widget in fields.items():
            val = d.get(name, "")
            if isinstance(widget, QLineEdit):
                widget.setText(str(val))
            elif isinstance(widget, QSpinBox):
                widget.setValue(int(val) if val else 7)

    def _on_save(self, platform_key: str):
        fields = self._forms.get(platform_key, {})
        data = {}
        for name, widget in fields.items():
            if isinstance(widget, QLineEdit):
                data[name] = widget.text()
            elif isinstance(widget, QSpinBox):
                data[name] = widget.value()

        w = _ConfigWorker(api.save_platform_config, platform_key, data)
        w.done.connect(lambda _: Toast.success(self, "配置保存成功"))
        w.failed.connect(lambda m: Toast.error(self, f"保存失败: {m}"))
        self._workers.append(w)
        w.start()

    def _on_reset(self, platform_key: str):
        reply = QMessageBox.question(
            self, "确认重置", "确定要恢复默认配置吗？当前修改将丢失。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            w = _ConfigWorker(api.reset_platform_config, platform_key)
            w.done.connect(lambda _: (Toast.success(self, "已恢复默认"), self.load_data()))
            w.failed.connect(lambda m: Toast.error(self, f"重置失败: {m}"))
            self._workers.append(w)
            w.start()
