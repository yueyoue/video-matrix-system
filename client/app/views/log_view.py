"""Log center view with filtering, export, and local debug log viewer."""

from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QTextCursor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QFrame, QHeaderView, QPushButton, QComboBox,
    QLineEdit, QFileDialog, QSpinBox, QTabWidget, QTextEdit,
    QPlainTextEdit, QCheckBox
)
from ..styles.theme import (
    BG_COLOR, CARD_STYLE, TEXT_COLOR, TEXT_SECONDARY, PRIMARY, SUCCESS,
    DANGER, WARNING, BORDER_COLOR, TABLE_STYLE, BTN_PRIMARY, BTN_DEFAULT,
    INPUT_STYLE, BTN_PRIMARY_SM
)
from ..widgets.toast import Toast
from .. import api

# 本地调试日志路径
LOCAL_DEBUG_LOG = Path.home() / '.video-matrix' / 'debug.log'


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


class LocalLogTab(QWidget):
    """本地调试日志查看器"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 操作栏
        bar = QHBoxLayout()
        bar.setSpacing(8)

        self._level_filter = QComboBox()
        self._level_filter.addItems(["全部", "ERROR", "WARN", "INFO", "FFmpeg"])
        self._level_filter.setStyleSheet(INPUT_STYLE)
        self._level_filter.setFixedHeight(34)
        self._level_filter.currentIndexChanged.connect(self._apply_filter)
        bar.addWidget(QLabel("过滤:"))
        bar.addWidget(self._level_filter)

        self._auto_scroll = QCheckBox("自动滚动")
        self._auto_scroll.setChecked(True)
        self._auto_scroll.setStyleSheet(f"font-size: 13px;")
        bar.addWidget(self._auto_scroll)

        bar.addStretch()

        clear_btn = QPushButton("清空显示")
        clear_btn.setStyleSheet(BTN_DEFAULT)
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setFixedHeight(34)
        clear_btn.clicked.connect(lambda: self._log_text.clear())
        bar.addWidget(clear_btn)

        export_btn = QPushButton("导出日志")
        export_btn.setStyleSheet(BTN_DEFAULT)
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.setFixedHeight(34)
        export_btn.clicked.connect(self._export_log)
        bar.addWidget(export_btn)

        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.setStyleSheet(BTN_PRIMARY_SM)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.setFixedHeight(34)
        refresh_btn.clicked.connect(self.load_data)
        bar.addWidget(refresh_btn)

        layout.addLayout(bar)

        # 日志路径提示
        path_label = QLabel(f"📂 日志文件: {LOCAL_DEBUG_LOG}")
        path_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px; padding: 2px 0;")
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(path_label)

        # 日志内容显示
        self._log_text = QPlainTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._log_text.setStyleSheet(f"""
            QPlainTextEdit {{
                background: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                border: 1px solid {BORDER_COLOR};
                border-radius: 6px;
                padding: 8px;
                selection-background-color: #264f78;
            }}
        """)
        layout.addWidget(self._log_text, 1)

        # 底部状态
        self._status = QLabel("")
        self._status.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(self._status)

    def load_data(self):
        """加载本地调试日志"""
        if not LOCAL_DEBUG_LOG.exists():
            self._log_text.setPlainText("暂无本地调试日志。\n\n日志文件会在执行 FFmpeg 操作等任务时自动生成。")
            self._status.setText("日志文件不存在")
            return

        try:
            content = LOCAL_DEBUG_LOG.read_text(encoding='utf-8', errors='replace')
            lines = content.strip().split('\n')

            # 获取最后 2000 行（避免日志过大卡顿）
            max_lines = 2000
            if len(lines) > max_lines:
                lines = lines[-max_lines:]
                truncated = True
            else:
                truncated = False

            self._all_lines = lines
            self._apply_filter()

            file_size = LOCAL_DEBUG_LOG.stat().st_size
            size_str = f"{file_size / 1024:.1f} KB" if file_size < 1024 * 1024 else f"{file_size / 1048576:.1f} MB"
            self._status.setText(
                f"共 {len(self._all_lines)} 行 | 文件大小: {size_str}"
                + (" | ⚠️ 显示最后 2000 行" if truncated else "")
            )
        except Exception as e:
            self._log_text.setPlainText(f"读取日志失败: {e}")
            self._status.setText("读取失败")

    def _apply_filter(self):
        """根据选择的级别过滤日志"""
        if not hasattr(self, '_all_lines'):
            return

        filter_text = self._level_filter.currentText()
        if filter_text == "全部":
            filtered = self._all_lines
        elif filter_text == "ERROR":
            filtered = [l for l in self._all_lines if 'ERROR' in l.upper() or '失败' in l or 'error' in l.lower()]
        elif filter_text == "WARN":
            filtered = [l for l in self._all_lines if 'WARN' in l.upper() or '警告' in l]
        elif filter_text == "INFO":
            filtered = [l for l in self._all_lines if '[FFmpeg]' in l or 'INFO' in l.upper()]
        elif filter_text == "FFmpeg":
            filtered = [l for l in self._all_lines if '[FFmpeg]' in l or 'ffmpeg' in l.lower() or 'ffprobe' in l.lower()]
        else:
            filtered = self._all_lines

        self._log_text.clear()
        self._log_text.setPlainText('\n'.join(filtered))

        # 自动滚动到底部
        if self._auto_scroll.isChecked():
            cursor = self._log_text.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self._log_text.setTextCursor(cursor)

    def _export_log(self):
        """导出本地日志"""
        if not LOCAL_DEBUG_LOG.exists():
            Toast.warning(self, "日志文件不存在")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出调试日志",
            f"debug_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
            "日志文件 (*.log);;所有文件 (*)"
        )
        if not path:
            return
        try:
            import shutil
            shutil.copy2(str(LOCAL_DEBUG_LOG), path)
            Toast.success(self, f"导出成功: {path}")
        except Exception as e:
            Toast.error(self, f"导出失败: {e}")


class ServerLogTab(QWidget):
    """服务端日志查看器（原有功能）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers: list[_LogWorker] = []
        self._page = 1
        self._total_pages = 1
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

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
            level_item.setForeground(QColor(level_map.get(level.upper(), TEXT_SECONDARY)))
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


class LogView(QWidget):
    """日志中心 - 包含服务端日志和本地调试日志两个标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet("""
            QTabWidget::pane { border: none; }
            QTabBar::tab { padding: 10px 20px; font-size: 14px; border: none; border-bottom: 2px solid transparent; color: #999; }
            QTabBar::tab:selected { color: #165DFF; border-bottom: 2px solid #165DFF; }
        """)

        self._local_tab = LocalLogTab()
        self._server_tab = ServerLogTab()

        self._tabs.addTab(self._local_tab, "🐛 本地调试日志")
        self._tabs.addTab(self._server_tab, "📋 服务端日志")

        layout.addWidget(self._tabs)

    def load_data(self):
        # 默认加载本地日志（当前选中的标签页）
        current = self._tabs.currentWidget()
        if hasattr(current, 'load_data'):
            current.load_data()
