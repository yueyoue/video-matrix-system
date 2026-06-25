"""Data analysis view with filters, summary cards, and detailed tables."""

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDate
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QFrame, QHeaderView, QPushButton, QComboBox,
    QDateEdit, QFileDialog, QTabWidget, QSpinBox
)
from ..styles.theme import (
    BG_COLOR, CARD_STYLE, TEXT_COLOR, TEXT_SECONDARY, PRIMARY, SUCCESS,
    DANGER, WARNING, BORDER_COLOR, TABLE_STYLE, BTN_PRIMARY, BTN_DEFAULT,
    INPUT_STYLE, BTN_PRIMARY_SM
)
from ..widgets.stat_card import StatCard
from ..widgets.toast import Toast
from .. import api


def _stop_worker(worker):
    """安全停止一个 QThread worker"""
    if worker is not None and worker.isRunning():
        worker.quit()
        if not worker.wait(3000):
            worker.terminate()
            worker.wait(1000)


class _SyncWorker(QThread):
    done = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def run(self):
        try:
            result = api.sync_video_data()
            self.done.emit(result)
        except Exception as e:
            self.failed.emit(str(e))


class _AnalysisWorker(QThread):
    done = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, params: dict, page: int = 1):
        super().__init__()
        self.params = params
        self.page = page

    def run(self):
        try:
            summary = api.get_analysis_summary(self.params)
            by_platform = api.get_analysis_by_platform(self.params)
            by_video = api.get_analysis_by_video(self.params, page=self.page)
            self.done.emit({
                "summary": summary,
                "byPlatform": by_platform,
                "byVideo": by_video,
            })
        except Exception as e:
            self.failed.emit(str(e))


class AnalysisView(QWidget):
    """Data analysis page with filtering and detailed tables."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._sync_worker = None
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

        # quick date buttons
        for label, days in [("今日", 0), ("近7天", 7), ("30天", 30)]:
            btn = QPushButton(label)
            btn.setStyleSheet(BTN_DEFAULT)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(34)
            btn.clicked.connect(lambda _, d=days: self._set_date_range(d))
            fl.addWidget(btn)

        fl.addWidget(QLabel("从"))
        self._date_from = QDateEdit()
        self._date_from.setCalendarPopup(True)
        self._date_from.setDate(QDate.currentDate().addDays(-7))
        self._date_from.setStyleSheet(INPUT_STYLE)
        self._date_from.setFixedHeight(34)
        fl.addWidget(self._date_from)

        fl.addWidget(QLabel("至"))
        self._date_to = QDateEdit()
        self._date_to.setCalendarPopup(True)
        self._date_to.setDate(QDate.currentDate())
        self._date_to.setStyleSheet(INPUT_STYLE)
        self._date_to.setFixedHeight(34)
        fl.addWidget(self._date_to)

        fl.addWidget(QLabel("平台"))
        self._platform_combo = QComboBox()
        self._platform_combo.addItems(["全部", "抖音", "快手", "小红书", "视频号"])
        self._platform_combo.setStyleSheet(INPUT_STYLE)
        self._platform_combo.setFixedHeight(34)
        fl.addWidget(self._platform_combo)

        query_btn = QPushButton("查询")
        query_btn.setStyleSheet(BTN_PRIMARY)
        query_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        query_btn.setFixedHeight(34)
        query_btn.clicked.connect(self._on_query)
        fl.addWidget(query_btn)

        export_btn = QPushButton("导出Excel")
        export_btn.setStyleSheet(BTN_DEFAULT)
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.setFixedHeight(34)
        export_btn.clicked.connect(self._on_export)
        fl.addWidget(export_btn)

        fl.addStretch()

        # sync button
        self._sync_btn = QPushButton("📡 同步数据")
        self._sync_btn.setStyleSheet(BTN_PRIMARY)
        self._sync_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sync_btn.setFixedHeight(34)
        self._sync_btn.clicked.connect(self._on_sync)
        fl.addWidget(self._sync_btn)

        layout.addWidget(filter_frame)

        # ── Summary cards ──────────────────────────────────────
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(16)

        self._card_play = StatCard("总播放量", "0", "▶️", PRIMARY)
        self._card_like = StatCard("总点赞量", "0", "❤️", DANGER)
        self._card_comment = StatCard("总评论量", "0", "💬", WARNING)
        self._card_share = StatCard("总分享量", "0", "🔗", SUCCESS)

        for c in [self._card_play, self._card_like, self._card_comment, self._card_share]:
            cards_layout.addWidget(c)
        layout.addLayout(cards_layout)

        # ── Tables ─────────────────────────────────────────────
        tab_widget = QTabWidget()
        tab_widget.setStyleSheet("""
            QTabWidget::pane { border: none; }
            QTabBar::tab {
                padding: 8px 20px; font-size: 14px;
                border: none; border-bottom: 2px solid transparent;
                color: #999;
            }
            QTabBar::tab:selected { color: #165DFF; border-bottom: 2px solid #165DFF; }
        """)

        # platform detail table
        self._platform_table = QTableWidget()
        self._platform_table.setStyleSheet(TABLE_STYLE)
        self._platform_table.setColumnCount(6)
        self._platform_table.setHorizontalHeaderLabels(
            ["平台", "播放量", "点赞量", "评论量", "分享量", "发布数"])
        self._platform_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._platform_table.verticalHeader().setVisible(False)
        self._platform_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tab_widget.addTab(self._platform_table, "分平台明细")

        # video detail table with pagination
        video_tab = QWidget()
        vt_layout = QVBoxLayout(video_tab)
        vt_layout.setContentsMargins(0, 0, 0, 0)

        self._video_table = QTableWidget()
        self._video_table.setStyleSheet(TABLE_STYLE)
        self._video_table.setColumnCount(7)
        self._video_table.setHorizontalHeaderLabels(
            ["视频标题", "平台", "账号", "播放量", "点赞量", "评论量", "发布时间"])
        self._video_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._video_table.verticalHeader().setVisible(False)
        self._video_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        vt_layout.addWidget(self._video_table)

        # pagination
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
        vt_layout.addLayout(page_layout)

        tab_widget.addTab(video_tab, "单视频明细")
        layout.addWidget(tab_widget, 1)

    def _set_date_range(self, days: int):
        today = QDate.currentDate()
        self._date_to.setDate(today)
        if days == 0:
            self._date_from.setDate(today)
        else:
            self._date_from.setDate(today.addDays(-days))

    def _get_params(self) -> dict:
        platform_map = {"全部": "", "抖音": "douyin", "快手": "kuaishou",
                        "小红书": "xiaohongshu", "视频号": "weixin"}
        platform = platform_map.get(self._platform_combo.currentText(), "")
        params = {
            "startDate": self._date_from.date().toString("yyyy-MM-dd"),
            "endDate": self._date_to.date().toString("yyyy-MM-dd"),
        }
        if platform:
            params["platform"] = platform
        return params

    def _on_query(self):
        self._page = 1
        self._load()

    def _load(self):
        from ..api import _debug_log
        params = self._get_params()
        _debug_log(f"[Analysis] 查询参数: {params}, 页码: {self._page}")
        _stop_worker(self._worker)
        self._worker = _AnalysisWorker(params, self._page)
        self._worker.done.connect(self._on_data)
        self._worker.failed.connect(lambda m: (Toast.error(self, f"查询失败: {m}\n调试日志: ~/.video-matrix/debug.log"), _debug_log(f"[Analysis] 查询失败: {m}")))
        self._worker.start()

    def _on_data(self, data: dict):
        # summary
        s = data.get("summary", {}).get("data", data.get("summary", {}))
        self._card_play.set_value(f"{s.get('totalPlays', s.get('playCount', 0)):,}")
        self._card_like.set_value(f"{s.get('totalLikes', s.get('likeCount', 0)):,}")
        self._card_comment.set_value(f"{s.get('totalComments', s.get('commentCount', 0)):,}")
        self._card_share.set_value(f"{s.get('totalShares', s.get('shareCount', 0)):,}")

        # platform table
        platforms = data.get("byPlatform", {}).get("data", data.get("byPlatform", []))
        if isinstance(platforms, dict):
            platforms = platforms.get("list", [])
        self._platform_table.setRowCount(len(platforms) + 1)
        totals = [0, 0, 0, 0, 0]
        for i, p in enumerate(platforms):
            vals = [
                str(p.get("platform", "")),
                str(p.get("playCount", p.get("plays", 0))),
                str(p.get("likeCount", p.get("likes", 0))),
                str(p.get("commentCount", p.get("comments", 0))),
                str(p.get("shareCount", p.get("shares", 0))),
                str(p.get("publishCount", p.get("publish", 0))),
            ]
            for j, v in enumerate(vals):
                self._platform_table.setItem(i, j, QTableWidgetItem(v))
                if j > 0:
                    try:
                        totals[j-1] += int(v)
                    except ValueError:
                        pass
        # total row
        total_row = ["合计"] + [str(t) for t in totals]
        for j, v in enumerate(total_row):
            item = QTableWidgetItem(v)
            item.setForeground(QColor(PRIMARY))
            self._platform_table.setItem(len(platforms), j, item)

        # video table
        video_data = data.get("byVideo", {}).get("data", data.get("byVideo", {}))
        if isinstance(video_data, dict):
            videos = video_data.get("list", video_data.get("records", []))
            total = video_data.get("total", len(videos))
            self._total_pages = max(1, (total + 19) // 20)
        else:
            videos = video_data if isinstance(video_data, list) else []
            self._total_pages = 1

        self._video_table.setRowCount(len(videos))
        for i, v in enumerate(videos):
            self._video_table.setItem(i, 0, QTableWidgetItem(str(v.get("title", v.get("videoTitle", "")))))
            self._video_table.setItem(i, 1, QTableWidgetItem(str(v.get("platform", ""))))
            self._video_table.setItem(i, 2, QTableWidgetItem(str(v.get("accountName", v.get("account", "")))))
            self._video_table.setItem(i, 3, QTableWidgetItem(str(v.get("playCount", v.get("plays", 0)))))
            self._video_table.setItem(i, 4, QTableWidgetItem(str(v.get("likeCount", v.get("likes", 0)))))
            self._video_table.setItem(i, 5, QTableWidgetItem(str(v.get("commentCount", v.get("comments", 0)))))
            self._video_table.setItem(i, 6, QTableWidgetItem(str(v.get("publishTime", v.get("createdAt", "")))))

        self._page_label.setText(f"第 {self._page} 页 / 共 {self._total_pages} 页")
        self._prev_btn.setEnabled(self._page > 1)
        self._next_btn.setEnabled(self._page < self._total_pages)

    def _change_page(self, delta: int):
        new_page = self._page + delta
        if 1 <= new_page <= self._total_pages:
            self._page = new_page
            self._load()

    def _on_export(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出Excel", "数据分析.xlsx", "Excel (*.xlsx)")
        if not path:
            return
        try:
            content = api.export_analysis(self._get_params())
            with open(path, "wb") as f:
                f.write(content)
            Toast.success(self, f"导出成功: {path}")
        except Exception as e:
            Toast.error(self, f"导出失败: {e}")

    def _on_sync(self):
        """触发数据同步"""
        self._sync_btn.setEnabled(False)
        self._sync_btn.setText("⏳ 同步中...")
        _stop_worker(self._sync_worker)
        self._sync_worker = _SyncWorker()
        self._sync_worker.done.connect(self._on_sync_done)
        self._sync_worker.failed.connect(self._on_sync_failed)
        self._sync_worker.start()

    def _on_sync_done(self, data: dict):
        d = data.get("data", data)
        totalNew = d.get("total_new_records", 0)
        self._sync_btn.setEnabled(True)
        self._sync_btn.setText("📡 同步数据")
        Toast.success(self, f"同步完成！新增 {totalNew} 条视频数据")
        self._on_query()

    def _on_sync_failed(self, msg: str):
        self._sync_btn.setEnabled(True)
        self._sync_btn.setText("📡 同步数据")
        Toast.error(self, f"同步失败: {msg}")

    def load_data(self):
        self._on_query()

    def cleanup(self):
        """清理所有线程，窗口关闭时调用"""
        _stop_worker(self._worker)
        _stop_worker(self._sync_worker)
