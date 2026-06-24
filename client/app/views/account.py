"""Account management view with platform tabs, table, and CRUD dialogs."""

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QFrame, QHeaderView, QPushButton, QDialog,
    QLineEdit, QFormLayout, QComboBox, QCheckBox, QTabWidget,
    QMessageBox, QSpinBox, QScrollArea, QTextEdit
)
from ..styles.theme import (
    BG_COLOR, CARD_STYLE, TEXT_COLOR, TEXT_SECONDARY, PRIMARY, SUCCESS,
    DANGER, WARNING, BORDER_COLOR, TABLE_STYLE, BTN_PRIMARY, BTN_DEFAULT,
    BTN_DANGER, BTN_PRIMARY_SM, BTN_DANGER_TEXT, INPUT_STYLE, CHECKBOX_STYLE,
    TAB_STYLE, BTN_TEXT
)
from ..widgets.toast import Toast
from .. import api


class _AccountWorker(QThread):
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


class _AddAccountDialog(QDialog):
    """Dialog for adding a new account with cookie-based login."""

    PLATFORM_URLS = {
        "douyin": {
            "name": "抖音",
            "login_url": "https://creator.douyin.com/",
            "cookie_tip": "1. 浏览器打开上方链接并登录\n2. 按F12打开开发者工具 → Network\n3. 刷新页面，点击任意请求\n4. 复制请求头中的Cookie值",
        },
        "kuaishou": {
            "name": "快手",
            "login_url": "https://cp.kuaishou.com/",
            "cookie_tip": "1. 浏览器打开上方链接并登录\n2. 按F12打开开发者工具 → Network\n3. 刷新页面，点击任意请求\n4. 复制请求头中的Cookie值",
        },
        "xiaohongshu": {
            "name": "小红书",
            "login_url": "https://creator.xiaohongshu.com/",
            "cookie_tip": "1. 浏览器打开上方链接并登录\n2. 按F12打开开发者工具 → Network\n3. 刷新页面，点击任意请求\n4. 复制请求头中的Cookie值",
        },
        "weixin": {
            "name": "视频号",
            "login_url": "https://channels.weixin.qq.com/",
            "cookie_tip": "1. 浏览器打开上方链接并登录\n2. 按F12打开开发者工具 → Network\n3. 刷新页面，点击任意请求\n4. 复制请求头中的Cookie值",
        },
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加账号")
        self.setFixedSize(520, 580)
        self.setStyleSheet(f"QDialog {{ background: {BG_COLOR}; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        title = QLabel("添加平台账号")
        title.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {TEXT_COLOR};")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(12)

        # 平台选择
        self._platform = QComboBox()
        self._platform.addItems(["抖音", "快手", "小红书", "视频号"])
        self._platform.setStyleSheet(INPUT_STYLE)
        self._platform.currentIndexChanged.connect(self._on_platform_changed)
        form.addRow("平台:", self._platform)

        # 昵称
        self._nickname = QLineEdit()
        self._nickname.setPlaceholderText("输入账号昵称")
        self._nickname.setStyleSheet(INPUT_STYLE)
        form.addRow("昵称:", self._nickname)

        layout.addLayout(form)

        # 登录引导区域
        self._login_guide = QFrame()
        self._login_guide.setStyleSheet(f"QFrame {{{CARD_STYLE} padding: 12px;}}")
        guide_layout = QVBoxLayout(self._login_guide)
        guide_layout.setSpacing(8)

        # 登录方式选择
        login_mode_bar = QHBoxLayout()
        login_mode_bar.addWidget(QLabel("登录方式: "))
        self._login_mode = QComboBox()
        self._login_mode.addItems(["Cookie登录（推荐）", "扫码登录"])  
        self._login_mode.setStyleSheet(INPUT_STYLE)
        self._login_mode.currentIndexChanged.connect(self._on_login_mode_changed)
        login_mode_bar.addWidget(self._login_mode)
        login_mode_bar.addStretch()
        guide_layout.addLayout(login_mode_bar)

        # Cookie输入区
        self._cookie_widget = QWidget()
        cookie_layout = QVBoxLayout(self._cookie_widget)
        cookie_layout.setContentsMargins(0, 0, 0, 0)
        cookie_layout.setSpacing(6)

        self._login_url_label = QLabel()
        self._login_url_label.setOpenExternalLinks(True)
        self._login_url_label.setStyleSheet(f"color: {PRIMARY}; font-size: 12px;")
        cookie_layout.addWidget(self._login_url_label)

        self._cookie_tip_label = QLabel()
        self._cookie_tip_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        self._cookie_tip_label.setWordWrap(True)
        cookie_layout.addWidget(self._cookie_tip_label)

        self._cookie_input = QTextEdit()
        self._cookie_input.setPlaceholderText("粘贴从浏览器复制的Cookie...")
        self._cookie_input.setStyleSheet(f"QTextEdit {{ border: 1px solid {BORDER_COLOR}; border-radius: 6px; padding: 6px; font-size: 11px; }}")
        self._cookie_input.setMaximumHeight(80)
        cookie_layout.addWidget(self._cookie_input)

        guide_layout.addWidget(self._cookie_widget)

        # 扫码登录区
        self._qrcode_widget = QWidget()
        qr_layout = QVBoxLayout(self._qrcode_widget)
        qr_layout.setContentsMargins(0, 0, 0, 0)
        qr_layout.setSpacing(6)

        qr_hint = QLabel("📱 点击下方按钮打开平台登录页面，扫码登录后复制Cookie粘贴到上方")
        qr_hint.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        qr_hint.setWordWrap(True)
        qr_layout.addWidget(qr_hint)

        open_browser_btn = QPushButton("🌐 打开登录页面")
        open_browser_btn.setStyleSheet(BTN_PRIMARY_SM)
        open_browser_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_browser_btn.clicked.connect(self._open_login_page)
        qr_layout.addWidget(open_browser_btn)

        self._qrcode_widget.setVisible(False)
        guide_layout.addWidget(self._qrcode_widget)

        layout.addWidget(self._login_guide)

        # 备注
        remark_form = QFormLayout()
        self._remark = QLineEdit()
        self._remark.setPlaceholderText("备注信息（可选）")
        self._remark.setStyleSheet(INPUT_STYLE)
        remark_form.addRow("备注:", self._remark)
        layout.addLayout(remark_form)

        layout.addStretch()

        # 按钮
        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet(BTN_DEFAULT)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("保存")
        save_btn.setStyleSheet(BTN_PRIMARY)
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

        self.result_data = None
        # 初始化平台提示
        self._on_platform_changed(0)

    def _on_platform_changed(self, idx):
        platform_keys = ["douyin", "kuaishou", "xiaohongshu", "weixin"]
        key = platform_keys[idx] if idx < len(platform_keys) else "douyin"
        info = self.PLATFORM_URLS.get(key, {})
        self._login_url_label.setText(f'🔗 <a href="{info.get("login_url", "#")}">{info.get("login_url", "")}</a>')
        self._cookie_tip_label.setText(info.get("cookie_tip", ""))

    def _on_login_mode_changed(self, idx):
        self._cookie_widget.setVisible(idx == 0)
        self._qrcode_widget.setVisible(idx == 1)

    def _open_login_page(self):
        platform_keys = ["douyin", "kuaishou", "xiaohongshu", "weixin"]
        idx = self._platform.currentIndex()
        key = platform_keys[idx] if idx < len(platform_keys) else "douyin"
        url = self.PLATFORM_URLS.get(key, {}).get("login_url", "")
        if url:
            import webbrowser
            webbrowser.open(url)

    def _on_save(self):
        platform_map = {"抖音": "douyin", "快手": "kuaishou",
                        "小红书": "xiaohongshu", "视频号": "weixin"}
        nickname = self._nickname.text().strip()
        cookie = self._cookie_input.toPlainText().strip()

        if not nickname:
            Toast.warning(self, "请输入昵称")
            return

        self.result_data = {
            "platform": platform_map.get(self._platform.currentText(), "douyin"),
            "nickname": nickname,
            "cookie": cookie,
            "remark": self._remark.text().strip(),
        }
        self.accept()


class _EditAccountDialog(QDialog):
    """Dialog for editing an existing account."""

    def __init__(self, account: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑账号")
        self.setFixedSize(400, 280)
        self.setStyleSheet(f"QDialog {{ background: {BG_COLOR}; }}")
        self._account = account

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        title = QLabel(f"编辑账号 - {account.get('nickname', '')}")
        title.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {TEXT_COLOR};")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(12)

        self._nickname = QLineEdit(account.get("nickname", ""))
        self._nickname.setStyleSheet(INPUT_STYLE)
        form.addRow("昵称:", self._nickname)

        self._remark = QLineEdit(account.get("remark", ""))
        self._remark.setStyleSheet(INPUT_STYLE)
        form.addRow("备注:", self._remark)

        layout.addLayout(form)
        layout.addStretch()

        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet(BTN_DEFAULT)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("保存")
        save_btn.setStyleSheet(BTN_PRIMARY)
        save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def get_data(self) -> dict:
        return {
            "nickname": self._nickname.text().strip(),
            "remark": self._remark.text().strip(),
        }


class AccountView(QWidget):
    """Account management page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers: list[_AccountWorker] = []
        self._page = 1
        self._total_pages = 1
        self._current_platform = ""
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # ── Platform tabs ──────────────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(TAB_STYLE)
        self._tab_platforms = [
            ("", "全部"),
            ("douyin", "抖音"),
            ("kuaishou", "快手"),
            ("xiaohongshu", "小红书"),
            ("weixin", "视频号"),
        ]
        for key, label in self._tab_platforms:
            placeholder = QWidget()
            self._tabs.addTab(placeholder, label)
        self._tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self._tabs)

        # ── Action bar ─────────────────────────────────────────
        action_bar = QHBoxLayout()
        action_bar.setSpacing(8)

        check_btn = QPushButton("🔍 批量检测状态")
        check_btn.setStyleSheet(BTN_DEFAULT)
        check_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        check_btn.clicked.connect(self._on_batch_check)
        action_bar.addWidget(check_btn)

        add_btn = QPushButton("➕ 添加账号")
        add_btn.setStyleSheet(BTN_PRIMARY)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._on_add_account)
        action_bar.addWidget(add_btn)

        action_bar.addStretch()

        refresh_btn = QPushButton("刷新")
        refresh_btn.setStyleSheet(BTN_PRIMARY_SM)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self._load)
        action_bar.addWidget(refresh_btn)

        layout.addLayout(action_bar)

        # ── Table ──────────────────────────────────────────────
        self._table = QTableWidget()
        self._table.setStyleSheet(TABLE_STYLE)
        self._table.setColumnCount(9)
        self._table.setHorizontalHeaderLabels([
            "全选", "头像", "昵称", "状态", "作品数", "总播放量",
            "今日发布", "最后登录", "操作"
        ])
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(0, 40)
        self._table.setColumnWidth(1, 50)
        self._table.setColumnWidth(8, 140)
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

    def _on_tab_changed(self, index: int):
        self._current_platform = self._tab_platforms[index][0]
        self._page = 1
        self._load()

    def load_data(self):
        self._load()

    def _load(self):
        w = _AccountWorker(api.get_accounts, self._current_platform, self._page)
        w.done.connect(self._on_data)
        w.failed.connect(lambda m: Toast.error(self, f"加载失败: {m}"))
        self._workers.append(w)
        w.start()

    def _on_data(self, data: dict):
        d = data.get("data", data)
        if isinstance(d, dict):
            accounts = d.get("list", d.get("records", []))
            total = d.get("total", len(accounts))
            self._total_pages = max(1, (total + 19) // 20)
        else:
            accounts = d if isinstance(d, list) else []
            self._total_pages = 1

        self._table.setRowCount(len(accounts))
        for i, acc in enumerate(accounts):
            # checkbox
            cb = QCheckBox()
            cb.setStyleSheet(CHECKBOX_STYLE)
            self._table.setCellWidget(i, 0, cb)

            # avatar placeholder
            avatar = QLabel("👤")
            avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
            avatar.setStyleSheet("font-size: 18px;")
            self._table.setCellWidget(i, 1, avatar)

            self._table.setItem(i, 2, QTableWidgetItem(str(acc.get("nickname", ""))))

            status = str(acc.get("status", "正常"))
            status_item = QTableWidgetItem(status)
            if "正常" in status or "active" in status.lower():
                status_item.setForeground(SUCCESS)
            elif "异常" in status or "error" in status.lower():
                status_item.setForeground(DANGER)
            else:
                status_item.setForeground(WARNING)
            self._table.setItem(i, 3, status_item)

            self._table.setItem(i, 4, QTableWidgetItem(str(acc.get("workCount", acc.get("videoCount", 0)))))
            self._table.setItem(i, 5, QTableWidgetItem(str(acc.get("totalPlays", acc.get("playCount", 0)))))
            self._table.setItem(i, 6, QTableWidgetItem(str(acc.get("todayPublish", 0))))
            self._table.setItem(i, 7, QTableWidgetItem(str(acc.get("lastLogin", acc.get("lastLoginAt", "")))))

            # action buttons
            action_widget = QWidget()
            al = QHBoxLayout(action_widget)
            al.setContentsMargins(4, 2, 4, 2)
            al.setSpacing(4)

            edit_btn = QPushButton("编辑")
            edit_btn.setStyleSheet(BTN_PRIMARY_SM)
            edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            edit_btn.setFixedHeight(26)
            aid = str(acc.get("id", acc.get("_id", i)))
            edit_btn.clicked.connect(lambda _, a=acc: self._on_edit(a))
            al.addWidget(edit_btn)

            del_btn = QPushButton("删除")
            del_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {DANGER}; color: white; border: none;
                    border-radius: 4px; padding: 4px 12px; font-size: 12px;
                }}
                QPushButton:hover {{ background: {DANGER}; }}
            """)
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.setFixedHeight(26)
            del_btn.clicked.connect(lambda _, a=acc: self._on_delete(a))
            al.addWidget(del_btn)

            self._table.setCellWidget(i, 8, action_widget)

        self._page_label.setText(f"第 {self._page} 页 / 共 {self._total_pages} 页")
        self._prev_btn.setEnabled(self._page > 1)
        self._next_btn.setEnabled(self._page < self._total_pages)

    def _change_page(self, delta: int):
        new_page = self._page + delta
        if 1 <= new_page <= self._total_pages:
            self._page = new_page
            self._load()

    def _on_add_account(self):
        dlg = _AddAccountDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_data:
            w = _AccountWorker(api.add_account, dlg.result_data)
            w.done.connect(lambda _: (Toast.success(self, "账号添加成功"), self._load()))
            w.failed.connect(lambda m: Toast.error(self, f"添加失败: {m}"))
            self._workers.append(w)
            w.start()

    def _on_edit(self, account: dict):
        dlg = _EditAccountDialog(account, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            aid = str(account.get("id", account.get("_id", "")))
            w = _AccountWorker(api.update_account, aid, dlg.get_data())
            w.done.connect(lambda _: (Toast.success(self, "更新成功"), self._load()))
            w.failed.connect(lambda m: Toast.error(self, f"更新失败: {m}"))
            self._workers.append(w)
            w.start()

    def _on_delete(self, account: dict):
        name = account.get("nickname", "")
        reply = QMessageBox.question(
            self, "确认删除", f"确定要删除账号「{name}」吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            aid = str(account.get("id", account.get("_id", "")))
            w = _AccountWorker(api.delete_account, aid)
            w.done.connect(lambda _: (Toast.success(self, "删除成功"), self._load()))
            w.failed.connect(lambda m: Toast.error(self, f"删除失败: {m}"))
            self._workers.append(w)
            w.start()

    def _on_batch_check(self):
        ids = []
        for i in range(self._table.rowCount()):
            cb = self._table.cellWidget(i, 0)
            if isinstance(cb, QCheckBox) and cb.isChecked():
                ids.append(str(i))  # placeholder
        if not ids:
            Toast.warning(self, "请先勾选要检测的账号")
            return
        w = _AccountWorker(api.batch_check_accounts, ids)
        w.done.connect(lambda _: Toast.success(self, "批量检测已提交"))
        w.failed.connect(lambda m: Toast.error(self, f"检测失败: {m}"))
        self._workers.append(w)
        w.start()
