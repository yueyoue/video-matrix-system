"""Dashboard view – overview stats, recent publishes, alerts, and data sync."""

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QFrame, QHeaderView, QPushButton
)
from ..styles.theme import (
    BG_COLOR, CARD_STYLE, TEXT_COLOR, TEXT_SECONDARY, PRIMARY, SUCCESS,
    DANGER, WARNING, BORDER_COLOR, TABLE_STYLE, BTN_PRIMARY_SM, BTN_PRIMARY, BTN_DEFAULT
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


class _DataWorker(QThread):
    done = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def run(self):
        try:
            stats = api.get_overview_stats()
            self.done.emit(stats)
        except Exception as e:
            self.failed.emit(str(e))


class _SyncWorker(QThread):
    done = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, account_id=0):
        super().__init__()
        self.account_id = account_id

    def run(self):
        try:
            result = api.sync_video_data(self.account_id)
            self.done.emit(result)
        except Exception as e:
            self.failed.emit(str(e))


class _SyncStatusWorker(QThread):
    done = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def run(self):
        try:
            result = api.get_sync_status()
            self.done.emit(result)
        except Exception as e:
            self.failed.emit(str(e))


class DashboardView(QWidget):
    """Data overview page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data_worker = None
        self._sync_worker = None
        self._sync_status_worker = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # ── Sync bar ──────────────────────────────────────────
        sync_bar = QFrame()
        sync_bar.setStyleSheet(f"QFrame {{{CARD_STYLE} padding: 12px 16px;}}")
        sb_layout = QHBoxLayout(sync_bar)
        sb_layout.setSpacing(12)

        sync_icon = QLabel("🔄")
        sync_icon.setStyleSheet("font-size: 16px; border: none;")
        sb_layout.addWidget(sync_icon)

        self._sync_info = QLabel("点击同步按钮从已登录的视频平台拉取最新数据")
        self._sync_info.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px; border: none;")
        sb_layout.addWidget(self._sync_info, 1)

        self._sync_btn = QPushButton("📡 同步平台数据")
        self._sync_btn.setStyleSheet(BTN_PRIMARY)
        self._sync_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sync_btn.setFixedHeight(36)
        self._sync_btn.clicked.connect(self._on_sync)
        sb_layout.addWidget(self._sync_btn)

        layout.addWidget(sync_bar)

        # ── Stat cards row ─────────────────────────────────────
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(16)

        self._card_videos = StatCard("视频数据量", "0", "📊", PRIMARY)
        self._card_plays = StatCard("总播放量", "0", "▶️", SUCCESS)
        self._card_accounts = StatCard("管理账号数", "0", "👥", WARNING)
        self._card_publish = StatCard("今日发布", "0", "📤", DANGER)

        for c in [self._card_videos, self._card_plays, self._card_accounts, self._card_publish]:
            cards_layout.addWidget(c)
        layout.addLayout(cards_layout)

        # ── Bottom area ────────────────────────────────────────
        bottom = QHBoxLayout()
        bottom.setSpacing(16)

        # recent publish table
        recent_card = QFrame()
        recent_card.setStyleSheet(f"QFrame {{{CARD_STYLE} padding: 16px;}}")
        rc_layout = QVBoxLayout(recent_card)
        rc_layout.setSpacing(12)

        rc_header = QHBoxLayout()
        rc_title = QLabel("📋 最近发布记录")
        rc_title.setStyleSheet(f"font-size: 15px; font-weight: 600; color: {TEXT_COLOR};")
        rc_header.addWidget(rc_title)
        rc_header.addStretch()
        refresh_btn = QPushButton("刷新")
        refresh_btn.setStyleSheet(BTN_PRIMARY_SM)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self.load_data)
        rc_header.addWidget(refresh_btn)
        rc_layout.addLayout(rc_header)

        self._recent_table = QTableWidget()
        self._recent_table.setStyleSheet(TABLE_STYLE)
        self._recent_table.setColumnCount(5)
        self._recent_table.setHorizontalHeaderLabels(["时间", "平台", "账号", "视频标题", "状态"])
        self._recent_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._recent_table.verticalHeader().setVisible(False)
        self._recent_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._recent_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        rc_layout.addWidget(self._recent_table)
        bottom.addWidget(recent_card, 3)

        # alerts
        alert_card = QFrame()
        alert_card.setStyleSheet(f"QFrame {{{CARD_STYLE} padding: 16px;}}")
        alert_card.setFixedWidth(320)
        ac_layout = QVBoxLayout(alert_card)
        ac_layout.setSpacing(12)

        a_title = QLabel("⚠️ 异常预警")
        a_title.setStyleSheet(f"font-size: 15px; font-weight: 600; color: {TEXT_COLOR};")
        ac_layout.addWidget(a_title)

        self._alert_list = QVBoxLayout()
        ac_layout.addLayout(self._alert_list)
        ac_layout.addStretch()

        bottom.addWidget(alert_card, 2)
        layout.addLayout(bottom, 1)

    def load_data(self):
        from ..api import _debug_log, BASE_URL
        _debug_log(f"[Dashboard] 开始加载数据, 服务器: {BASE_URL}")

        # 停止旧的 worker
        _stop_worker(self._data_worker)
        _stop_worker(self._sync_status_worker)

        # 加载概览数据
        self._data_worker = _DataWorker()
        self._data_worker.done.connect(self._on_data)
        self._data_worker.failed.connect(self._on_error)
        self._data_worker.start()

        # 加载同步状态
        self._sync_status_worker = _SyncStatusWorker()
        self._sync_status_worker.done.connect(self._on_sync_status)
        self._sync_status_worker.failed.connect(lambda m: None)
        self._sync_status_worker.start()

    def cleanup(self):
        """清理所有线程，窗口关闭时调用"""
        _stop_worker(self._data_worker)
        _stop_worker(self._sync_worker)
        _stop_worker(self._sync_status_worker)

    def _on_sync_status(self, data: dict):
        d = data.get("data", data)
        total = d.get("total_videos", 0)
        lastSync = d.get("last_sync", "未同步")
        activeAccs = d.get("active_accounts", 0)
        if lastSync and lastSync != "未同步":
            self._sync_info.setText(f"📊 已同步 {total} 条视频数据 | 活跃账号 {activeAccs} 个 | 上次同步: {lastSync}")
        else:
            self._sync_info.setText(f"📊 已同步 {total} 条视频数据 | 活跃账号 {activeAccs} 个 | 尚未同步过数据")

    def _on_sync(self):
        """触发数据同步"""
        self._sync_btn.setEnabled(False)
        self._sync_btn.setText("⏳ 同步中...")
        self._sync_info.setText("正在从已登录的视频平台拉取数据，请稍候...")
        self._sync_info.setStyleSheet(f"color: {WARNING}; font-size: 13px; border: none;")

        _stop_worker(self._sync_worker)
        self._sync_worker = _SyncWorker()
        self._sync_worker.done.connect(self._on_sync_done)
        self._sync_worker.failed.connect(self._on_sync_failed)
        self._sync_worker.start()

    def _on_sync_done(self, data: dict):
        d = data.get("data", data)
        totalNew = d.get("total_new_records", 0)
        syncedAccs = d.get("synced_accounts", 0)
        errors = d.get("errors", [])
        results = d.get("results", [])

        self._sync_btn.setEnabled(True)
        self._sync_btn.setText("📡 同步平台数据")

        if errors and not results:
            errMsg = "; ".join([e.get("error", str(e)) for e in errors[:3]])
            self._sync_info.setText(f"❌ 同步失败: {errMsg}")
            self._sync_info.setStyleSheet(f"color: {DANGER}; font-size: 13px; border: none;")
            Toast.error(self, f"同步失败: {errMsg}")
        else:
            totalPlays = sum(r.get("plays", 0) for r in results)
            self._sync_info.setText(f"✅ 同步完成！{syncedAccs} 个账号，新增 {totalNew} 条数据，总播放 {totalPlays:,}")
            self._sync_info.setStyleSheet(f"color: {SUCCESS}; font-size: 13px; border: none; font-weight: 600;")
            msg = f"同步完成！新增 {totalNew} 条视频数据"
            if errors:
                errAccs = ", ".join([e.get("account", "") for e in errors[:3]])
                msg += f"\n⚠️ 以下账号同步失败: {errAccs}"
            Toast.success(self, msg)

        self.load_data()

    def _on_sync_failed(self, msg: str):
        self._sync_btn.setEnabled(True)
        self._sync_btn.setText("📡 同步平台数据")
        self._sync_info.setText(f"❌ 同步失败: {msg}")
        self._sync_info.setStyleSheet(f"color: {DANGER}; font-size: 13px; border: none;")
        Toast.error(self, f"同步失败: {msg}")

    def _on_data(self, data: dict):
        d = data.get("data", data)
        from ..api import _debug_log
        _debug_log(f"[Dashboard] 收到数据: {str(d)[:500]}")

        self._card_accounts.set_value(str(d.get("accountCount", d.get("total_users", 0))))

        todaySuccess = int(d.get("today_publish_success", 0))
        todayFailed = int(d.get("today_publish_failed", 0))
        todayTotal = todaySuccess + todayFailed
        self._card_publish.set_value(str(todayTotal))

        videoDataCount = d.get("video_data_count", 0)
        self._card_videos.set_value(str(videoDataCount))

        totalPlays = d.get("total_plays", 0)
        if totalPlays > 0:
            if totalPlays >= 10000:
                self._card_plays.set_value(f"{totalPlays/10000:.1f}万")
            else:
                self._card_plays.set_value(str(totalPlays))
        else:
            self._card_plays.set_value("0")

        records = d.get("recentPublish", d.get("recent", []))
        self._recent_table.setRowCount(len(records))
        for i, r in enumerate(records):
            self._recent_table.setItem(i, 0, QTableWidgetItem(str(r.get("time", r.get("createdAt", "")))))
            self._recent_table.setItem(i, 1, QTableWidgetItem(str(r.get("platform", ""))))
            self._recent_table.setItem(i, 2, QTableWidgetItem(str(r.get("accountName", r.get("account", "")))))
            self._recent_table.setItem(i, 3, QTableWidgetItem(str(r.get("videoTitle", r.get("title", "")))))
            status = str(r.get("status", ""))
            item = QTableWidgetItem(status)
            if "成功" in status or "success" in status.lower():
                item.setForeground(QColor(SUCCESS))
            elif "失败" in status or "fail" in status.lower():
                item.setForeground(QColor(DANGER))
            self._recent_table.setItem(i, 4, item)

        alerts = d.get("alerts", [])
        while self._alert_list.count():
            child = self._alert_list.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not alerts:
            lbl = QLabel("暂无异常 🎉")
            lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px; padding: 20px;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._alert_list.addWidget(lbl)
        else:
            for a in alerts[:8]:
                al = QLabel(f"⚠ {a.get('message', a.get('text', str(a)))}")
                al.setStyleSheet(f"color: {WARNING}; font-size: 13px; padding: 4px 0;")
                al.setWordWrap(True)
                self._alert_list.addWidget(al)

    def _on_error(self, msg: str):
        from ..api import _debug_log, BASE_URL
        _debug_log(f"[Dashboard] 加载失败: {msg}")
        _debug_log(f"[Dashboard] 服务器地址: {BASE_URL}")
        Toast.error(self, f"加载数据失败: {msg}\n\n调试日志已写入: ~/.video-matrix/debug.log")
