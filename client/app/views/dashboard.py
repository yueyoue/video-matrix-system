"""Dashboard view – overview stats, recent publishes, alerts."""

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QFrame, QHeaderView, QPushButton, QScrollArea
)
from ..styles.theme import (
    BG_COLOR, CARD_STYLE, TEXT_COLOR, TEXT_SECONDARY, PRIMARY, SUCCESS,
    DANGER, WARNING, BORDER_COLOR, TABLE_STYLE, BTN_PRIMARY_SM
)
from ..widgets.stat_card import StatCard
from ..widgets.toast import Toast
from .. import api


class _DataWorker(QThread):
    done = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def run(self):
        try:
            stats = api.get_overview_stats()
            self.done.emit(stats)
        except Exception as e:
            self.failed.emit(str(e))


class DashboardView(QWidget):
    """Data overview page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # ── Stat cards row ─────────────────────────────────────
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(16)

        self._card_gen = StatCard("生成视频数", "0", "🎬", PRIMARY)
        self._card_ok = StatCard("发布成功数", "0", "✅", SUCCESS)
        self._card_fail = StatCard("发布失败数", "0", "❌", DANGER)
        self._card_acc = StatCard("管理账号数", "0", "👥", WARNING)

        for c in [self._card_gen, self._card_ok, self._card_fail, self._card_acc]:
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
        self._worker = _DataWorker()
        self._worker.done.connect(self._on_data)
        self._worker.failed.connect(self._on_error)
        self._worker.start()

    def _on_data(self, data: dict):
        d = data.get("data", data)
        self._card_gen.set_value(str(d.get("totalVideos", d.get("videoCount", 0))))
        self._card_ok.set_value(str(d.get("publishSuccess", d.get("successCount", 0))))
        self._card_fail.set_value(str(d.get("publishFailed", d.get("failCount", 0))))
        self._card_acc.set_value(str(d.get("accountCount", d.get("totalAccounts", 0))))

        # recent records
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
                item.setForeground(SUCCESS)
            elif "失败" in status or "fail" in status.lower():
                item.setForeground(DANGER)
            self._recent_table.setItem(i, 4, item)

        # alerts
        alerts = d.get("alerts", [])
        # clear old alerts
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
        Toast.error(self, f"加载数据失败: {msg}")
