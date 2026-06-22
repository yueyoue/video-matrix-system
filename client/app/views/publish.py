"""Publish scheduling view with rules and queue."""

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QFrame, QHeaderView, QPushButton, QCheckBox,
    QSpinBox, QTimeEdit, QComboBox, QMessageBox, QFormLayout
)
from ..styles.theme import (
    BG_COLOR, CARD_STYLE, TEXT_COLOR, TEXT_SECONDARY, PRIMARY, SUCCESS,
    DANGER, WARNING, BORDER_COLOR, TABLE_STYLE, BTN_PRIMARY, BTN_DEFAULT,
    BTN_DANGER, BTN_PRIMARY_SM, BTN_DANGER_TEXT, INPUT_STYLE, CHECKBOX_STYLE,
    SPINBOX_STYLE
)
from ..widgets.toast import Toast
from .. import api


class _PublishWorker(QThread):
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


class PublishView(QWidget):
    """Publish scheduling page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers: list[_PublishWorker] = []
        self._page = 1
        self._total_pages = 1
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # ── Left: Rules ────────────────────────────────────────
        rules_card = QFrame()
        rules_card.setStyleSheet(f"QFrame {{{CARD_STYLE} padding: 16px;}}")
        rules_card.setFixedWidth(360)
        rl = QVBoxLayout(rules_card)
        rl.setSpacing(14)

        rules_title = QLabel("⚙️ 发布规则设置")
        rules_title.setStyleSheet(f"font-size: 15px; font-weight: 600; color: {TEXT_COLOR};")
        rl.addWidget(rules_title)

        # platform checkboxes
        plat_label = QLabel("发布平台:")
        plat_label.setStyleSheet(f"font-size: 13px; font-weight: 500; color: {TEXT_COLOR};")
        rl.addWidget(plat_label)

        plat_layout = QHBoxLayout()
        self._plat_cbs = {}
        for name in ["抖音", "快手", "小红书", "视频号"]:
            cb = QCheckBox(name)
            cb.setStyleSheet(CHECKBOX_STYLE)
            self._plat_cbs[name] = cb
            plat_layout.addWidget(cb)
        plat_layout.addStretch()
        rl.addLayout(plat_layout)

        form = QFormLayout()
        form.setSpacing(12)

        self._daily_limit = QSpinBox()
        self._daily_limit.setRange(1, 100)
        self._daily_limit.setValue(5)
        self._daily_limit.setStyleSheet(SPINBOX_STYLE)
        form.addRow("每日上限:", self._daily_limit)

        self._publish_time = QTimeEdit()
        self._publish_time.setDisplayFormat("HH:mm")
        self._publish_time.setStyleSheet(INPUT_STYLE)
        form.addRow("发布时间:", self._publish_time)

        self._publish_order = QComboBox()
        self._publish_order.addItems(["按队列顺序", "随机发布", "优先最新", "优先最旧"])
        self._publish_order.setStyleSheet(INPUT_STYLE)
        form.addRow("发布顺序:", self._publish_order)

        rl.addLayout(form)

        self._auto_remove = QCheckBox("发布成功后自动移除")
        self._auto_remove.setStyleSheet(CHECKBOX_STYLE)
        self._auto_remove.setChecked(True)
        rl.addWidget(self._auto_remove)

        save_btn = QPushButton("保存规则")
        save_btn.setStyleSheet(BTN_PRIMARY)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self._on_save_rules)
        rl.addWidget(save_btn)

        rl.addStretch()
        layout.addWidget(rules_card)

        # ── Right: Queue ───────────────────────────────────────
        right = QVBoxLayout()
        right.setSpacing(12)

        queue_header = QHBoxLayout()
        queue_title = QLabel("📋 待发布队列")
        queue_title.setStyleSheet(f"font-size: 15px; font-weight: 600; color: {TEXT_COLOR};")
        queue_header.addWidget(queue_title)
        queue_header.addStretch()

        refresh_btn = QPushButton("刷新")
        refresh_btn.setStyleSheet(BTN_PRIMARY_SM)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self._load_queue)
        queue_header.addWidget(refresh_btn)
        right.addLayout(queue_header)

        self._queue_table = QTableWidget()
        self._queue_table.setStyleSheet(TABLE_STYLE)
        self._queue_table.setColumnCount(7)
        self._queue_table.setHorizontalHeaderLabels([
            "计划时间", "平台", "账号", "视频", "状态", "优先级", "操作"
        ])
        self._queue_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._queue_table.horizontalHeader().setSectionResizeMode(
            6, QHeaderView.ResizeMode.Fixed)
        self._queue_table.setColumnWidth(6, 100)
        self._queue_table.verticalHeader().setVisible(False)
        self._queue_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._queue_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        right.addWidget(self._queue_table, 1)

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
        right.addLayout(page_layout)

        layout.addLayout(right, 1)

    def load_data(self):
        self._load_rules()
        self._load_queue()

    def _load_rules(self):
        w = _PublishWorker(api.get_publish_rules)
        w.done.connect(self._on_rules)
        w.failed.connect(lambda m: Toast.error(self, f"加载规则失败: {m}"))
        self._workers.append(w)
        w.start()

    def _on_rules(self, data: dict):
        if not isinstance(data, dict):
            return
        d = data.get("data", data)
        if isinstance(d, dict):
            platforms = d.get("platforms", [])
            for name, cb in self._plat_cbs.items():
                # check if platform name or key is in the list
                key_map = {"抖音": "douyin", "快手": "kuaishou",
                           "小红书": "xiaohongshu", "视频号": "shipinhao"}
                cb.setChecked(key_map.get(name, name) in platforms or name in platforms)

            self._daily_limit.setValue(d.get("dailyLimit", d.get("dailyMax", 5)))
            order = d.get("publishOrder", d.get("order", "按队列顺序"))
            idx = self._publish_order.findText(order)
            if idx >= 0:
                self._publish_order.setCurrentIndex(idx)
            self._auto_remove.setChecked(d.get("autoRemove", True))

    def _on_save_rules(self):
        key_map = {"抖音": "douyin", "快手": "kuaishou",
                   "小红书": "xiaohongshu", "视频号": "shipinhao"}
        platforms = [key_map[n] for n, cb in self._plat_cbs.items() if cb.isChecked()]
        data = {
            "platforms": platforms,
            "dailyLimit": self._daily_limit.value(),
            "publishTime": self._publish_time.time().toString("HH:mm"),
            "publishOrder": self._publish_order.currentText(),
            "autoRemove": self._auto_remove.isChecked(),
        }
        w = _PublishWorker(api.save_publish_rules, data)
        w.done.connect(lambda _: Toast.success(self, "规则保存成功"))
        w.failed.connect(lambda m: Toast.error(self, f"保存失败: {m}"))
        self._workers.append(w)
        w.start()

    def _load_queue(self):
        w = _PublishWorker(api.get_publish_queue, self._page)
        w.done.connect(self._on_queue)
        w.failed.connect(lambda m: Toast.error(self, f"加载队列失败: {m}"))
        self._workers.append(w)
        w.start()

    def _on_queue(self, data: dict):
        d = data.get("data", data)
        if isinstance(d, dict):
            items = d.get("list", d.get("records", []))
            total = d.get("total", len(items))
            self._total_pages = max(1, (total + 19) // 20)
        else:
            items = d if isinstance(d, list) else []
            self._total_pages = 1

        self._queue_table.setRowCount(len(items))
        for i, item in enumerate(items):
            self._queue_table.setItem(i, 0, QTableWidgetItem(str(item.get("scheduledTime", item.get("planTime", "")))))
            self._queue_table.setItem(i, 1, QTableWidgetItem(str(item.get("platform", ""))))
            self._queue_table.setItem(i, 2, QTableWidgetItem(str(item.get("accountName", item.get("account", "")))))
            self._queue_table.setItem(i, 3, QTableWidgetItem(str(item.get("videoTitle", item.get("video", "")))))

            status = str(item.get("status", ""))
            status_item = QTableWidgetItem(status)
            if "待" in status or "pending" in status.lower():
                status_item.setForeground(WARNING)
            elif "成功" in status or "success" in status.lower():
                status_item.setForeground(SUCCESS)
            elif "失败" in status or "fail" in status.lower():
                status_item.setForeground(DANGER)
            self._queue_table.setItem(i, 4, status_item)

            self._queue_table.setItem(i, 5, QTableWidgetItem(str(item.get("priority", "-"))))

            # remove button
            remove_btn = QPushButton("移除")
            remove_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {DANGER}; border: none;
                    padding: 4px 8px; font-size: 12px;
                }}
                QPushButton:hover {{ color: {DANGER}; font-weight: bold; }}
            """)
            remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            qid = str(item.get("id", item.get("_id", i)))
            remove_btn.clicked.connect(lambda _, q=qid: self._on_remove(q))
            self._queue_table.setCellWidget(i, 6, remove_btn)

        self._page_label.setText(f"第 {self._page} 页 / 共 {self._total_pages} 页")
        self._prev_btn.setEnabled(self._page > 1)
        self._next_btn.setEnabled(self._page < self._total_pages)

    def _change_page(self, delta: int):
        new_page = self._page + delta
        if 1 <= new_page <= self._total_pages:
            self._page = new_page
            self._load_queue()

    def _on_remove(self, queue_id: str):
        reply = QMessageBox.question(
            self, "确认移除", "确定要从队列中移除此任务吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            w = _PublishWorker(api.remove_from_queue, queue_id)
            w.done.connect(lambda _: (Toast.success(self, "已移除"), self._load_queue()))
            w.failed.connect(lambda m: Toast.error(self, f"移除失败: {m}"))
            self._workers.append(w)
            w.start()
