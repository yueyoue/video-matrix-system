"""Account management view with platform tabs, table, and CRUD dialogs.

集成 WebView 扫码登录 + 防封安全策略
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QFrame, QHeaderView, QPushButton, QDialog,
    QLineEdit, QFormLayout, QComboBox, QCheckBox, QTabWidget,
    QMessageBox, QSpinBox, QScrollArea, QTextEdit, QProgressBar
)
from ..styles.theme import (
    BG_COLOR, CARD_STYLE, TEXT_COLOR, TEXT_SECONDARY, PRIMARY, SUCCESS,
    DANGER, WARNING, BORDER_COLOR, TABLE_STYLE, BTN_PRIMARY, BTN_DEFAULT,
    BTN_DANGER, BTN_PRIMARY_SM, BTN_DANGER_TEXT, INPUT_STYLE, CHECKBOX_STYLE,
    TAB_STYLE, BTN_TEXT
)
from ..widgets.toast import Toast
from .. import api
from .. import anti_ban


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


class _InstallWorker(QThread):
    """后台安装 PyQt6-WebEngine 的工作线程"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)  # success, message

    def run(self):
        import subprocess
        import sys
        import time
        try:
            python = sys.executable
            mirrors = [
                ('清华源', 'https://pypi.tuna.tsinghua.edu.cn/simple', 'pypi.tuna.tsinghua.edu.cn'),
                ('阿里源', 'https://mirrors.aliyun.com/pypi/simple', 'mirrors.aliyun.com'),
                ('豆瓣源', 'https://pypi.douban.com/simple', 'pypi.douban.com'),
                ('官方源', 'https://pypi.org/simple', 'pypi.org'),
            ]

            # 测速：用 socket 连接测试延迟，选最快的源
            self.progress.emit("正在测速选择最快的下载源...")
            import socket
            fastest = None
            fastest_time = 999
            for name, url, host in mirrors:
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(3)
                    start_t = time.time()
                    s.connect((host, 443))
                    elapsed = time.time() - start_t
                    s.close()
                    if elapsed < fastest_time:
                        fastest_time = elapsed
                        fastest = (name, url, host)
                except Exception:
                    continue

            if fastest is None:
                fastest = ('清华源', 'https://pypi.tuna.tsinghua.edu.cn/simple', 'pypi.tuna.tsinghua.edu.cn')

            name, url, host = fastest
            self.progress.emit(f"✅ 选择{name}（延迟 {fastest_time*1000:.0f}ms），开始安装...")

            result = subprocess.run(
                [python, '-m', 'pip', 'install', 'PyQt6-WebEngine', '--upgrade',
                 '-i', url, '--trusted-host', host],
                capture_output=True, text=True, timeout=300,
                creationflags=0x08000000 if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            if result.returncode == 0:
                self.finished.emit(True, "安装成功！请重启应用程序后再次扫码登录。")
                return
            else:
                last_err = (result.stderr or result.stdout or '').strip()[-200:]
                self.finished.emit(False, f"{name}安装失败：{last_err}\n请手动执行：pip install PyQt6-WebEngine -i {url}")
        except subprocess.TimeoutExpired:
            self.finished.emit(False, f"安装超时，请检查网络后重试。\n手动执行：pip install PyQt6-WebEngine -i https://pypi.tuna.tsinghua.edu.cn/simple")
        except Exception as e:
            self.finished.emit(False, f"安装出错：{e}\n手动执行：pip install PyQt6-WebEngine -i https://pypi.tuna.tsinghua.edu.cn/simple")


class _InstallWebEngineDialog(QDialog):
    """PyQt6-WebEngine 安装对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("安装 WebView 组件")
        self.setFixedSize(460, 260)
        self.setStyleSheet(f"QDialog {{ background: {BG_COLOR}; }}")
        self._worker = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        title = QLabel("📦 安装 WebView 组件")
        title.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {TEXT_COLOR};")
        layout.addWidget(title)

        desc = QLabel(
            "扫码登录需要 PyQt6-WebEngine 组件。\n"
            "点击下方按钮自动安装（需要联网，约 1-3 分钟）。"
        )
        desc.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet(f"color: {TEXT_COLOR}; font-size: 13px;")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)  # indeterminate
        self._progress.setFixedHeight(6)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet(BTN_DEFAULT)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        self._install_btn = QPushButton("⚡ 一键安装")
        self._install_btn.setStyleSheet(BTN_PRIMARY)
        self._install_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._install_btn.clicked.connect(self._start_install)
        btn_layout.addWidget(self._install_btn)

        layout.addLayout(btn_layout)

    def _start_install(self):
        self._install_btn.setEnabled(False)
        self._install_btn.setText("安装中...")
        self._progress.setVisible(True)
        self._status_label.setText("正在安装，请耐心等待...")
        self._status_label.setStyleSheet(f"color: {WARNING}; font-size: 13px;")

        self._worker = _InstallWorker()
        self._worker.progress.connect(lambda m: self._status_label.setText(m))
        self._worker.finished.connect(self._on_install_done)
        self._worker.start()

    def _on_install_done(self, success: bool, message: str):
        self._progress.setVisible(False)
        if success:
            self._status_label.setText(f"✅ {message}")
            self._status_label.setStyleSheet(f"color: {SUCCESS}; font-size: 13px; font-weight: 600;")
            self._install_btn.setText("完成")
            self._install_btn.clicked.connect(self.accept)
        else:
            self._status_label.setText(f"❌ {message}")
            self._status_label.setStyleSheet(f"color: {DANGER}; font-size: 13px;")
            self._install_btn.setText("重试")
            self._install_btn.setEnabled(True)
            self._install_btn.clicked.disconnect()
            self._install_btn.clicked.connect(self._start_install)


class _AddAccountDialog(QDialog):
    """添加账号对话框 - 支持内嵌 WebView 扫码登录
    
    登录流程：
    1. 输入昵称
    2. 点击“扫码登录” → 弹出内嵌浏览器窗口
    3. 用户在浏览器中扫码/登录
    4. 登录成功 → 自动提取 Cookie 并保存
    """

    PLATFORM_NAMES = {
        "douyin": "抖音",
        "kuaishou": "快手",
        "xiaohongshu": "小红书",
        "weixin": "视频号",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加平台账号")
        self.setFixedSize(500, 380)
        self.setStyleSheet(f"QDialog {{ background: {BG_COLOR}; }}")
        self.result_data = None
        self._cookies = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # 标题
        title = QLabel("➕ 添加平台账号")
        title.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {TEXT_COLOR};")
        layout.addWidget(title)

        # 表单
        form = QFormLayout()
        form.setSpacing(12)

        self._platform = QComboBox()
        self._platform.addItems(list(self.PLATFORM_NAMES.values()))
        self._platform.setStyleSheet(INPUT_STYLE)
        form.addRow("平台:", self._platform)

        self._nickname = QLineEdit()
        self._nickname.setPlaceholderText("输入账号昵称（方便识别）")
        self._nickname.setStyleSheet(INPUT_STYLE)
        form.addRow("昵称:", self._nickname)

        layout.addLayout(form)

        # 登录方式说明
        info_frame = QFrame()
        info_frame.setStyleSheet(f"QFrame {{{CARD_STYLE} padding: 12px;}}")
        info_layout = QVBoxLayout(info_frame)
        info_layout.setSpacing(8)

        login_mode_label = QLabel("🔐 登录方式: 内嵌浏览器扫码登录")
        login_mode_label.setStyleSheet(f"font-weight: 600; color: {TEXT_COLOR}; font-size: 13px;")
        info_layout.addWidget(login_mode_label)

        desc = QLabel(
            "• 点击“扫码登录”后将打开内嵌浏览器窗口\n"
            "• 在浏览器中扫码或输入账号密码登录\n"
            "• 每个账号使用独立浏览器环境，互不影响\n"
            "• 登录成功后自动提取并保存 Cookie"
        )
        desc.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; line-height: 1.6;")
        desc.setWordWrap(True)
        info_layout.addWidget(desc)

        self._cookie_status = QLabel("")
        self._cookie_status.setStyleSheet(f"color: {SUCCESS}; font-size: 12px;")
        info_layout.addWidget(self._cookie_status)

        layout.addWidget(info_frame)

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
        btn_layout.setSpacing(8)

        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet(BTN_DEFAULT)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        self._scan_btn = QPushButton("📱 扫码登录")
        self._scan_btn.setStyleSheet(BTN_PRIMARY)
        self._scan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._scan_btn.clicked.connect(self._on_scan_login)
        btn_layout.addWidget(self._scan_btn)

        self._save_btn = QPushButton("✅ 保存")
        self._save_btn.setStyleSheet(BTN_DEFAULT)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(self._save_btn)

        layout.addLayout(btn_layout)

    def _get_platform_key(self) -> str:
        """获取当前选择的平台 key"""
        platform_map = {"抖音": "douyin", "快手": "kuaishou",
                        "小红书": "xiaohongshu", "视频号": "weixin"}
        return platform_map.get(self._platform.currentText(), "douyin")

    def _on_scan_login(self):
        """打开内嵌 WebView 扫码登录"""
        nickname = self._nickname.text().strip()
        if not nickname:
            Toast.warning(self, "请先输入账号昵称")
            return

        # 检查防封：同平台登录频率
        platform = self._get_platform_key()
        allowed, reason = anti_ban.can_perform_operation(
            f"{platform}_{nickname}", platform, "login"
        )
        if not allowed:
            Toast.warning(self, f"安全限制: {reason}")
            return

        # 打开 WebView 登录窗口
        try:
            from .webview_login import WebViewLoginDialog
            dlg = WebViewLoginDialog(platform, nickname, self)
            dlg.login_success.connect(self._on_login_success)
            dlg.exec()
        except ImportError:
            # 弹出安装对话框
            install_dlg = _InstallWebEngineDialog(self)
            if install_dlg.exec() == QDialog.DialogCode.Accepted:
                Toast.info(self, "安装完成，请重启应用后再次扫码登录")
        except Exception as e:
            err_msg = str(e)
            if 'QtWebEngineWidgets' in err_msg or 'ShareOpenGLContexts' in err_msg:
                install_dlg = _InstallWebEngineDialog(self)
                if install_dlg.exec() == QDialog.DialogCode.Accepted:
                    Toast.info(self, "安装完成，请重启应用后再次扫码登录")
            else:
                Toast.error(self, f"打开登录窗口失败: {err_msg}")

    def _on_login_success(self, data: dict):
        """WebView 登录成功回调"""
        self._cookies = data.get("cookies", "")
        count = data.get("cookie_count", 0)
        self._cookie_status.setText(f"✅ Cookie 已获取 ({count} 个)")
        self._cookie_status.setStyleSheet(f"color: {SUCCESS}; font-size: 12px; font-weight: 600;")
        self._save_btn.setEnabled(True)
        self._save_btn.setStyleSheet(BTN_PRIMARY)
        self._scan_btn.setText("📱 重新扫码")
        Toast.success(self, "登录成功！请点保存")

    def _on_save(self):
        nickname = self._nickname.text().strip()
        if not nickname:
            Toast.warning(self, "请输入昵称")
            return
        if not self._cookies:
            Toast.warning(self, "请先扫码登录获取 Cookie")
            return

        platform = self._get_platform_key()
        self.result_data = {
            "platform": platform,
            "nickname": nickname,
            "cookie": self._cookies,
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
        from ..api import _debug_log
        _debug_log(f"[AccountView] 加载账号列表: platform={self._current_platform}, page={self._page}")
        w = _AccountWorker(api.get_accounts, self._current_platform, self._page)
        w.done.connect(self._on_data)
        w.failed.connect(lambda m: (Toast.error(self, f"加载失败: {m}"), _debug_log(f"[AccountView] 加载失败: {m}")))
        self._workers.append(w)
        w.start()

    def _on_data(self, data: dict):
        from ..api import _debug_log
        _debug_log(f"[AccountView] 收到数据: {str(data)[:300]}")
        d = data.get("data", data)
        if isinstance(d, dict):
            accounts = d.get("list", d.get("records", d.get("accounts", [])))
            total = d.get("total", len(accounts))
            self._total_pages = max(1, (total + 19) // 20)
        elif isinstance(d, list):
            accounts = d
            self._total_pages = 1
        else:
            accounts = []
            self._total_pages = 1
            _debug_log(f"[AccountView] 无法解析数据: type={type(d)}")

        _debug_log(f"[AccountView] 账号数量: {len(accounts)}")

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
        # 检查登录状态
        from ..auth import auth
        if not auth.is_valid:
            Toast.error(self, "请先登录系统，再添加账号")
            return
        dlg = _AddAccountDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_data:
            data = dlg.result_data
            # 验证必填字段
            if not data.get("nickname"):
                Toast.warning(self, "请输入账号昵称")
                return
            if not data.get("platform"):
                Toast.warning(self, "请选择平台")
                return
            if not data.get("cookie"):
                Toast.warning(self, "Cookie 为空，请先扫码登录")
                return
            # 防封检查：同平台同名账号是否已存在
            platform = data["platform"]
            nickname = data["nickname"]
            from ..api import _debug_log
            _debug_log(f"[AccountView] 添加账号: platform={platform}, nickname={nickname}")
            # 显示正在添加的提示
            Toast.info(self, f"正在添加 {nickname}...")
            w = _AccountWorker(api.add_account, data)
            w.done.connect(lambda r: self._on_add_success(r, nickname))
            w.failed.connect(lambda m: Toast.error(self, f"添加失败: {m}"))
            self._workers.append(w)
            w.start()

    def _on_add_success(self, result, nickname):
        Toast.success(self, f"账号 {nickname} 添加成功！")
        self._load()

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
