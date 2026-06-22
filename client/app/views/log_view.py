"""Log center view with filtering and export."""

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QFrame, QHeaderView, QPushButton, QComboBox,
    QLineEdit, QFileDialog, QSpinBox
)
from ..styles.theme import (
    BG_COLOR, CARD_STYLE, TEXT_COLOR, TEXT_SECONDARY, PRIMARY, SUCCESS,
    DANGER, WARNING, BORDER_COLOR, TABLE_STYLE, BTN_PRIMARY, BTN_DEFAULT,
    INPUT_STYLE, BTN_PRIMARY_SM
)
from ..widgets.toast import Toast
from .. import api


class _LogWorker(QThread):
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


class LogView(QWidget):
    """Log center page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers: list[_LogWorker] = []
        self._page = 1
        self._total_pages = 1
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # ── Filter bar ─────────────────────────────────────────
        filter_frame = QFrame()
        filter_frame.setStyleSheet(f"QFrame {{{CARD_STYLE} padding: 12px 16px;}}")
        fl = QHBoxLayout(filter_frame)
        fl.setSpacing(8)

        fl.addWidget(QLabel("级别:"))
        self._level_combo = QComboBox()
        self._level_combo.addItems(["全部", "INFO", "WARN", "ERROR", "DEBUG"])
        self._level_combo.setStyleSheet(INPUT_STYLE)
        self._level_combo.setFixedHeight(34)
        fl.addWidget(self._level_combo)

        fl.addWidget(QLabel("关键词:"))
        self._keyword_input = QLineEdit()
        self._keyword_input.setPlaceholderText("搜索日志内容...")
        self._keyword_input.setStyleSheet(INPUT_STYLE)
        self._keyword_input.setFixedHeight(34)
        self._keyword_input.returnPressed.connect(self._on_search)
        fl.addWidget(self._keyword_input)

        search_btn = QPushButton("搜索")
        search_btn.setStyleSheet(BTN_PRIMARY)
        search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        search_btn.setFixedHeight(34)
        search_btn.clicked.connect(self._on_search)
        fl.addWidget(search_btn)

        export_btn = QPushButton("导出日志")
        export_btn.setStyleSheet(BTN_DEFAULT)
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.setFixedHeight(34)
        export_btn.clicked.connect(self._on_export)
        fl.addWidget(export_btn)

        refresh_btn = QPushButton("刷新")
        refresh_btn.setStyleSheet(BTN_PRIMARY_SM)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.setFixedHeight(34)
        refresh_btn.clicked.connect(self._on_search)
        fl.addWidget(refresh_btn)

        fl.addStretch()
        layout.addWidget(filter_frame)

        # ── Log table ──────────────────────────────────────────
        self._table = QTableWidget()
        self._table.setStyleSheet(TABLE_STYLE)
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["时间", "级别", "模块", "详情"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self._table, 1)

        # ── Pagination ─────────────────────────────────────────
        page_layout = QHBoxLayout()
        page_layout.addStretch()
        self._prev_btn = QPushButton("上一页")
        self._prev_btn.setStyleSheet(BTN_DEFAULT)
        self._prev_btn.setFixedHeight(32)
        self._prev_btn.clicked.connect(lambda: self._change_page(-1))
        page_layout.addWidget(self._prev_btn)

        self._page_label = QLabel("第 1 页")
        self._page_label.setStyleSheet(f"color: {TEXT_SECONDARY}; padding: 0 12px;")
        page_layout.addWidget(self._page_label)

        self._next_btn = QPushButton("下一页")
        self._next_btn.setStyleSheet(BTN_DEFAULT)
        self._next_btn.setFixedHeight(32)
        self._next_btn.clicked.connect(lambda: self._change_page(1))
        page_layout.addWidget(self._next_btn)
        page_layout.addStretch()
        layout.addLayout(page_layout)

    def _get_params(self) -> dict:
        params: dict = {}
        level = self._level_combo.currentText()
        if level != "全部":
            params["level"] = level
        keyword = self._keyword_input.text().strip()
        if keyword:
            params["keyword"] = keyword
        return params

    def _on_search(self):
        self._page = 1
        self._load()

    def _load(self):
        params = self._get_params()
        w = _LogWorker(api.get_logs, params, self._page)
        w.done.connect(self._on_data)
        w.failed.connect(lambda m: Toast.error(self, f"加载日志失败: {m}"))
        self._workers.append(w)
        w.start()

    def _on_data(self, data: dict):
        d = data.get("data", data)
        if isinstance(d, dict):
            logs = d.get("list", d.get("records", []))
            total = d.get("total", len(logs))
            self._total_pages = max(1, (total + 49) // 50)
        else:
            logs = d if isinstance(d, list) else []
            self._total_pages = 1

        self._table.setRowCount(len(logs))
        for i, log in enumerate(logs):
            self._table.setItem(i, 0, QTableWidgetItem(str(log.get("time", log.get("createdAt", "")))))

            level = str(log.get("level", "INFO"))
            level_item = QTableWidgetItem(level)
            level_map = {"INFO": SUCCESS, "WARN": WARNING, "ERROR": DANGER, "DEBUG": TEXT_SECONDARY}
            level_item.setForeground(level_map.get(level.upper(), TEXT_SECONDARY))
            self._table.setItem(i, 1, level_item)

            self._table.setItem(i, 2, QTableWidgetItem(str(log.get("module", log.get("source", "")))))
            self._table.setItem(i, 3, QTableWidgetItem(str(log.get("message", log.get("detail", "")))))

        self._page_label.setText(f"第 {self._page} 页 / 共 {self._total_pages} 页")
        self._prev_btn.setEnabled(self._page > 1)
        self._next_btn.setEnabled(self._page < self._total_pages)

    def _change_page(self, delta: int):
        new_page = self._page + delta
        if 1 <= new_page <= self._total_pages:
            self._page = new_page
            self._load()

    def _on_export(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出日志", "日志导出.csv", "CSV (*.csv);;所有文件 (*)")
        if not path:
            return
        try:
            content = api.export_logs(self._get_params())
            with open(path, "wb") as f:
                f.write(content)
            Toast.success(self, f"导出成功: {path}")
        except Exception as e:
            Toast.error(self, f"导出失败: {e}")

    def load_data(self):
        self._on_search()
