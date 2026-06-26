"""
数据采集页面 - 监控账号管理 + Playwright 数据采集 + 统计展示
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QUrl
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QLineEdit, QDialog, QFormLayout, QDateEdit,
    QMessageBox, QProgressBar, QSplitter, QTabWidget, QTextEdit
)
from PyQt6.QtGui import QColor
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage

from ..styles.theme import (
    BG_COLOR, CARD_STYLE, TEXT_COLOR, TEXT_SECONDARY, PRIMARY,
    SUCCESS, DANGER, WARNING, BORDER_COLOR,
    BTN_PRIMARY, BTN_DEFAULT, BTN_DANGER, TABLE_STYLE,
    INPUT_STYLE
)
from ..widgets.toast import Toast
from ..widgets.stat_card import StatCard
from .. import api

# 本地定义缺失的样式
COMBO_STYLE = f"""
QComboBox {{
    background: white; border: 1px solid {BORDER_COLOR}; border-radius: 6px;
    padding: 6px 12px; font-size: 13px; color: {TEXT_COLOR};
    min-height: 20px;
}}
QComboBox:hover {{ border-color: {PRIMARY}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{ background: white; border: 1px solid {BORDER_COLOR}; selection-background-color: {PRIMARY}12; }}
"""


# ── 本地数据存储 ──────────────────────────────────────────
DATA_DIR = Path.home() / ".video-matrix" / "data_collect"
ACCOUNTS_FILE = DATA_DIR / "monitored_accounts.json"
RESULTS_FILE = DATA_DIR / "collect_results.json"


def _load_json(path: Path) -> list:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── 采集工作线程（仅用于非浏览器平台） ──────────────────
class CollectWorker(QThread):
    progress = pyqtSignal(str, int, int)
    finished = pyqtSignal(list)
    account_done = pyqtSignal(str, str, int)

    def __init__(self, accounts: list):
        super().__init__()
        self._accounts = accounts
        self._results = []
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        import requests as req
        for acc in self._accounts:
            if self._cancelled:
                break
            name = acc["account_name"]
            platform = acc["platform"]
            sec_uid = acc["sec_uid"]
            try:
                self.progress.emit(name, 0, 0)
                videos = self._scrape_http(platform, sec_uid, name)
                self._results.append({
                    "account_name": name, "platform": platform,
                    "videos": videos, "error": None,
                    "collected_at": datetime.now().isoformat()
                })
                self.account_done.emit(name, "ok", len(videos))
            except Exception as e:
                self._results.append({
                    "account_name": name, "platform": platform,
                    "videos": [], "error": str(e),
                    "collected_at": datetime.now().isoformat()
                })
                self.account_done.emit(name, str(e), 0)
        self.finished.emit(self._results)

    def _scrape_http(self, platform, sec_uid, name):
        return []  # HTTP方式已弃用，改用浏览器

    @staticmethod
    def _find_key(obj, target_key):
        if isinstance(obj, dict):
            if target_key in obj:
                return obj[target_key]
            for v in obj.values():
                r = CollectWorker._find_key(v, target_key)
                if r is not None:
                    return r
        elif isinstance(obj, list):
            for item in obj:
                r = CollectWorker._find_key(item, target_key)
                if r is not None:
                    return r
        return None


# ── 浏览器采集器（主线程） ──────────────────────────────
class BrowserScraper(QObject):
    """在主线程用 QWebEngineView 加载页面并提取数据"""
    account_done = pyqtSignal(str, str, int)  # name, error_or_ok, video_count
    all_done = pyqtSignal(list)                # all results
    log_msg = pyqtSignal(str)

    EXTRACT_JS = """
    (function() {
        var videos = [];
        // 方案1: RENDER_DATA
        var scripts = ['RENDER_DATA', '__ROUTER_DATA', '_ROUTER_DATA'];
        for (var i = 0; i < scripts.length; i++) {
            var el = document.getElementById(scripts[i]);
            if (el) {
                try {
                    var data = JSON.parse(decodeURIComponent(el.textContent));
                    function findKey(obj, key) {
                        if (!obj) return null;
                        if (obj[key]) return obj[key];
                        for (var k in obj) {
                            if (typeof obj[k] === 'object') {
                                var r = findKey(obj[k], key);
                                if (r) return r;
                            }
                        }
                        return null;
                    }
                    var list = findKey(data, 'aweme_list');
                    if (list && list.length > 0) {
                        for (var j = 0; j < list.length; j++) {
                            var item = list[j];
                            var stats = item.statistics || {};
                            videos.push({
                                title: item.desc || '',
                                plays: stats.play_count || 0,
                                likes: stats.digg_count || 0,
                                comments: stats.comment_count || 0,
                                shares: stats.share_count || 0,
                                publish_time: item.create_time ? new Date(item.create_time * 1000).toISOString().split('T')[0] : ''
                            });
                        }
                        return JSON.stringify({source: scripts[i], videos: videos});
                    }
                } catch(e) {}
            }
        }
        // 方案2: DOM提取
        var items = document.querySelectorAll('[class*="videoCard"], [class*="video-card"], .ECMy_Zdt, [class*="DyVideoCover"]');
        for (var i = 0; i < items.length; i++) {
            var el = items[i];
            var titleEl = el.querySelector('[class*="title"], a[title], [class*="desc"]');
            var title = titleEl ? (titleEl.getAttribute('title') || titleEl.textContent.trim()) : '';
            if (title && title.length > 2) videos.push({title: title, plays: 0, likes: 0, comments: 0, shares: 0, publish_time: ''});
        }
        return JSON.stringify({source: 'DOM', videos: videos});
    })()
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._accounts = []
        self._results = []
        self._idx = 0
        self._browser = None
        self._retry = 0

    def start(self, accounts: list):
        self._accounts = accounts
        self._results = []
        self._idx = 0
        self._start_next()

    def _start_next(self):
        if self._idx >= len(self._accounts):
            self.all_done.emit(self._results)
            return

        acc = self._accounts[self._idx]
        name = acc['account_name']
        platform = acc['platform']
        sec_uid = acc['sec_uid']
        self._retry = 0

        url_map = {
            'douyin': f'https://www.douyin.com/user/{sec_uid}',
            'kuaishou': f'https://www.kuaishou.com/profile/{sec_uid}',
            'xiaohongshu': f'https://www.xiaohongshu.com/user/profile/{sec_uid}',
        }
        url = url_map.get(platform, '')
        if not url:
            self.account_done.emit(name, f'不支持的平台: {platform}', 0)
            self._results.append({'account_name': name, 'platform': platform, 'videos': [], 'error': f'不支持: {platform}'});
            self._idx += 1
            QTimer.singleShot(500, self._start_next)
            return

        self.log_msg.emit(f'正在采集 {name} ({platform})...')

        # 创建浏览器实例
        if self._browser:
            self._browser.deleteLater()
        profile = QWebEngineProfile(f'scraper_{name}', self.parent())
        page = QWebEnginePage(profile, self.parent())
        self._browser = QWebEngineView(self.parent())
        self._browser.setPage(page)
        self._browser.setFixedSize(1280, 800)
        self._browser.move(-2000, -2000)
        self._browser.loadFinished.connect(self._on_loaded)
        self._browser.show()
        self._browser.load(QUrl(url))

    def _on_loaded(self, ok):
        acc = self._accounts[self._idx]
        name = acc['account_name']

        if not ok:
            self.log_msg.emit(f'❌ {name}: 页面加载失败')
            self.account_done.emit(name, '页面加载失败', 0)
            self._results.append({'account_name': name, 'platform': acc['platform'], 'videos': [], 'error': '页面加载失败'})
            self._idx += 1
            QTimer.singleShot(500, self._start_next)
            return

        self.log_msg.emit(f'  页面已加载，等待渲染...')
        QTimer.singleShot(4000, self._extract)

    def _extract(self):
        acc = self._accounts[self._idx]
        name = acc['account_name']
        self._browser.page().runJavaScript(self.EXTRACT_JS, self._on_result)

    def _on_result(self, result):
        acc = self._accounts[self._idx]
        name = acc['account_name']

        videos = []
        source = 'none'
        if result:
            try:
                data = json.loads(result)
                source = data.get('source', '?')
                videos = data.get('videos', [])
            except Exception:
                pass

        if not videos and self._retry < 2:
            self._retry += 1
            self.log_msg.emit(f'  第{self._retry}次未提取到，滚动后重试...')
            self._browser.page().runJavaScript('window.scrollTo(0, document.body.scrollHeight);')
            QTimer.singleShot(3000, self._extract)
            return

        self.log_msg.emit(f'  提取方式: {source}, 视频数: {len(videos)}')
        self.account_done.emit(name, 'ok' if videos else '未提取到数据', len(videos))
        self._results.append({
            'account_name': name, 'platform': acc['platform'],
            'videos': videos, 'error': None if videos else '未提取到数据',
            'collected_at': datetime.now().isoformat()
        })
        self._idx += 1
        QTimer.singleShot(1000, self._start_next)


# ── 添加账号对话框 ──────────────────────────────────────────
class AddAccountDialog(QDialog):
    def __init__(self, parent=None, edit_data=None):
        super().__init__(parent)
        self._edit_data = edit_data
        self.setWindowTitle("编辑监控账号" if edit_data else "添加监控账号")
        self.setFixedSize(450, 320)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        form = QFormLayout()
        form.setSpacing(12)

        self._platform = QComboBox()
        self._platform.setStyleSheet(COMBO_STYLE)
        self._platform.addItems(["抖音", "快手", "小红书", "视频号"])
        self._platform_map = {"抖音": "douyin", "快手": "kuaishou", "小红书": "xiaohongshu", "视频号": "weixin"}
        self._platform_reverse = {v: k for k, v in self._platform_map.items()}
        form.addRow("平台:", self._platform)

        self._name = QLineEdit()
        self._name.setStyleSheet(INPUT_STYLE)
        self._name.setPlaceholderText("输入账号昵称")
        form.addRow("账号名称:", self._name)

        self._sec_uid = QLineEdit()
        self._sec_uid.setStyleSheet(INPUT_STYLE)
        self._sec_uid.setPlaceholderText("主页链接中 /user/ 后面的部分")
        form.addRow("主页ID:", self._sec_uid)

        self._url_hint = QLabel("选择平台后显示链接格式提示")
        self._url_hint.setStyleSheet(f"font-size: 12px; color: {TEXT_SECONDARY};")
        self._url_hint.setWordWrap(True)
        form.addRow("", self._url_hint)

        self._platform.currentIndexChanged.connect(self._update_hint)
        self._update_hint(0)

        if self._edit_data:
            p = self._edit_data.get("platform", "")
            idx = list(self._platform_map.values()).index(p) if p in self._platform_map.values() else 0
            self._platform.setCurrentIndex(idx)
            self._name.setText(self._edit_data.get("account_name", ""))
            self._sec_uid.setText(self._edit_data.get("sec_uid", ""))

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet(BTN_DEFAULT)
        cancel_btn.setFixedSize(80, 34)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("保存")
        ok_btn.setStyleSheet(BTN_PRIMARY)
        ok_btn.setFixedSize(80, 34)
        ok_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

    def _update_hint(self, idx):
        hints = {
            "抖音": "抖音: 打开抖音App → 个人主页 → 分享 → 复制链接\n链接中 /user/ 后面的部分就是主页ID\n例: https://www.douyin.com/user/MS4wLjABAAAAxx → MS4wLjABAAAAxx",
            "快手": "快手: 打开快手App → 个人主页 → 分享 → 复制链接\n链接中 /profile/ 后面的部分就是主页ID",
            "小红书": "小红书: 打开小红书App → 个人主页 → 分享 → 复制链接\n链接中 /user/profile/ 后面的部分就是主页ID",
            "视频号": "视频号: 暂不支持自动采集",
        }
        platform_text = self._platform.currentText()
        self._url_hint.setText(hints.get(platform_text, ""))

    def _on_save(self):
        if not self._name.text().strip():
            Toast.warning(self, "请输入账号名称")
            return
        if not self._sec_uid.text().strip():
            Toast.warning(self, "请输入主页ID")
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "platform": self._platform_map.get(self._platform.currentText(), "douyin"),
            "account_name": self._name.text().strip(),
            "sec_uid": self._sec_uid.text().strip(),
        }


# ── 主页面 ──────────────────────────────────────────────────
class DataCollectView(QWidget):
    """数据采集页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._accounts: list[dict] = _load_json(ACCOUNTS_FILE)
        self._results: list[dict] = _load_json(RESULTS_FILE)
        self._worker: CollectWorker | None = None
        self._scraper: BrowserScraper | None = None
        self._init_ui()
        self._refresh_table()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # ── 顶部统计卡片 ──────────────────────────────────
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(12)

        self._card_accounts = StatCard("监控账号", "0", "📊", PRIMARY)
        self._card_videos = StatCard("视频总数", "0", "🎬", SUCCESS)
        self._card_plays = StatCard("总播放量", "0", "👁️", WARNING)
        self._card_likes = StatCard("总点赞量", "0", "❤️", "#FF4757")

        for card in [self._card_accounts, self._card_videos, self._card_plays, self._card_likes]:
            cards_layout.addWidget(card)
        layout.addLayout(cards_layout)

        # ── 工具栏 ──────────────────────────────────────────
        toolbar = QHBoxLayout()

        self._add_btn = QPushButton("➕ 添加账号")
        self._add_btn.setStyleSheet(BTN_PRIMARY)
        self._add_btn.setFixedHeight(36)
        self._add_btn.clicked.connect(self._on_add)
        toolbar.addWidget(self._add_btn)

        self._collect_btn = QPushButton("🔄 开始采集")
        self._collect_btn.setStyleSheet(BTN_PRIMARY)
        self._collect_btn.setFixedHeight(36)
        self._collect_btn.clicked.connect(self._on_collect)
        toolbar.addWidget(self._collect_btn)

        self._sync_btn = QPushButton("☁️ 同步到服务端")
        self._sync_btn.setStyleSheet(BTN_DEFAULT)
        self._sync_btn.setFixedHeight(36)
        self._sync_btn.clicked.connect(self._on_sync)
        toolbar.addWidget(self._sync_btn)

        self._export_btn = QPushButton("📥 导出Excel")
        self._export_btn.setStyleSheet(BTN_DEFAULT)
        self._export_btn.setFixedHeight(36)
        self._export_btn.clicked.connect(self._on_export)
        toolbar.addWidget(self._export_btn)

        toolbar.addStretch()

        # 平台筛选
        self._filter_platform = QComboBox()
        self._filter_platform.setStyleSheet(COMBO_STYLE)
        self._filter_platform.setFixedWidth(120)
        self._filter_platform.addItems(["全部平台", "抖音", "快手", "小红书"])
        self._filter_platform.currentIndexChanged.connect(self._refresh_table)
        toolbar.addWidget(self._filter_platform)

        layout.addLayout(toolbar)

        # ── 进度条 ──────────────────────────────────────────
        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background: {BORDER_COLOR};
                border-radius: 3px;
                border: none;
            }}
            QProgressBar::chunk {{
                background: {PRIMARY};
                border-radius: 3px;
            }}
        """)
        self._progress_bar.hide()
        layout.addWidget(self._progress_bar)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet(f"font-size: 13px; color: {TEXT_SECONDARY};")
        layout.addWidget(self._status_label)

        # ── Tab 切换 ──────────────────────────────────────
        tabs = QTabWidget()
        tabs.setStyleSheet(f"""
            QTabBar::tab {{
                padding: 8px 20px;
                font-size: 13px;
                border: none;
                color: {TEXT_SECONDARY};
            }}
            QTabBar::tab:selected {{
                color: {PRIMARY};
                font-weight: 600;
                border-bottom: 2px solid {PRIMARY};
            }}
        """)

        # Tab1: 监控账号列表
        self._accounts_table = QTableWidget()
        self._accounts_table.setStyleSheet(TABLE_STYLE)
        self._accounts_table.setColumnCount(7)
        self._accounts_table.setHorizontalHeaderLabels(["平台", "账号名称", "主页ID", "视频数", "总播放", "状态", "操作"])
        self._accounts_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._accounts_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self._accounts_table.setColumnWidth(6, 200)
        self._accounts_table.verticalHeader().setDefaultSectionSize(42)
        self._accounts_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tabs.addTab(self._accounts_table, "📋 监控账号")

        # Tab2: 采集结果
        self._results_table = QTableWidget()
        self._results_table.setStyleSheet(TABLE_STYLE)
        self._results_table.setColumnCount(7)
        self._results_table.setHorizontalHeaderLabels(["平台", "账号", "视频标题", "播放量", "点赞量", "评论量", "分享量"])
        self._results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._results_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._results_table.verticalHeader().setDefaultSectionSize(42)
        self._results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tabs.addTab(self._results_table, "📊 采集结果")

        # Tab3: 采集日志
        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setStyleSheet(f"""
            QTextEdit {{
                background: #1e1e1e;
                color: #d4d4d4;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 12px;
                border: none;
                padding: 8px;
            }}
        """)
        tabs.addTab(self._log_text, "📝 采集日志")

        layout.addWidget(tabs, 1)

    def _refresh_table(self):
        """刷新账号表格"""
        filter_text = self._filter_platform.currentText()
        platform_map = {"抖音": "douyin", "快手": "kuaishou", "小红书": "xiaohongshu"}
        filter_p = platform_map.get(filter_text, "")

        accounts = [a for a in self._accounts if not filter_p or a.get("platform") == filter_p]
        self._accounts_table.setRowCount(len(accounts))

        for row, acc in enumerate(accounts):
            p = acc.get("platform", "")
            p_name = {"douyin": "抖音", "kuaishou": "快手", "xiaohongshu": "小红书", "weixin": "视频号"}.get(p, p)

            self._accounts_table.setItem(row, 0, QTableWidgetItem(p_name))
            self._accounts_table.setItem(row, 1, QTableWidgetItem(acc.get("account_name", "")))
            self._accounts_table.setItem(row, 2, QTableWidgetItem(acc.get("sec_uid", "")))

            # 从结果中统计
            video_count = 0
            total_plays = 0
            for r in self._results:
                if r.get("account_name") == acc.get("account_name"):
                    videos = r.get("videos", [])
                    video_count = len(videos)
                    total_plays = sum(v.get("plays", 0) for v in videos)
                    break

            self._accounts_table.setItem(row, 3, QTableWidgetItem(str(video_count)))
            self._accounts_table.setItem(row, 4, QTableWidgetItem(self._format_num(total_plays)))

            status = "已采集" if video_count > 0 else "未采集"
            status_item = QTableWidgetItem(status)
            status_item.setForeground(QColor(SUCCESS) if video_count > 0 else QColor(TEXT_SECONDARY))
            self._accounts_table.setItem(row, 5, status_item)

            # 操作按钮
            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(4, 2, 4, 2)
            btn_layout.setSpacing(4)

            edit_btn = QPushButton("编辑")
            edit_btn.setStyleSheet(f"font-size: 11px; color: {PRIMARY}; border: 1px solid {BORDER_COLOR}; border-radius: 4px; padding: 2px 8px;")
            edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            edit_btn.setFixedHeight(26)
            edit_btn.clicked.connect(lambda _, r=row: self._on_edit(r))
            btn_layout.addWidget(edit_btn)

            del_btn = QPushButton("删除")
            del_btn.setStyleSheet(f"font-size: 11px; color: {DANGER}; border: 1px solid {BORDER_COLOR}; border-radius: 4px; padding: 2px 8px;")
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.setFixedHeight(26)
            del_btn.clicked.connect(lambda _, r=row: self._on_delete(r))
            btn_layout.addWidget(del_btn)

            self._accounts_table.setCellWidget(row, 6, btn_widget)

        # 更新统计卡片
        self._card_accounts.set_value(str(len(self._accounts)))
        total_videos = sum(len(r.get("videos", [])) for r in self._results)
        total_plays = sum(v.get("plays", 0) for r in self._results for v in r.get("videos", []))
        total_likes = sum(v.get("likes", 0) for r in self._results for v in r.get("videos", []))
        self._card_videos.set_value(str(total_videos))
        self._card_plays.set_value(self._format_num(total_plays))
        self._card_likes.set_value(self._format_num(total_likes))

        # 刷新结果表格
        self._refresh_results()

    def _refresh_results(self):
        """刷新采集结果表格"""
        filter_text = self._filter_platform.currentText()
        platform_map = {"抖音": "douyin", "快手": "kuaishou", "小红书": "xiaohongshu"}
        filter_p = platform_map.get(filter_text, "")

        all_videos = []
        for r in self._results:
            p = r.get("platform", "")
            if filter_p and p != filter_p:
                continue
            for v in r.get("videos", []):
                all_videos.append({**v, "platform": p, "account_name": r.get("account_name", "")})

        self._results_table.setRowCount(len(all_videos))
        for row, v in enumerate(all_videos):
            p_name = {"douyin": "抖音", "kuaishou": "快手", "xiaohongshu": "小红书"}.get(v["platform"], v["platform"])
            self._results_table.setItem(row, 0, QTableWidgetItem(p_name))
            self._results_table.setItem(row, 1, QTableWidgetItem(v.get("account_name", "")))
            self._results_table.setItem(row, 2, QTableWidgetItem(v.get("title", "")))
            self._results_table.setItem(row, 3, QTableWidgetItem(self._format_num(v.get("plays", 0))))
            self._results_table.setItem(row, 4, QTableWidgetItem(self._format_num(v.get("likes", 0))))
            self._results_table.setItem(row, 5, QTableWidgetItem(str(v.get("comments", 0))))
            self._results_table.setItem(row, 6, QTableWidgetItem(str(v.get("shares", 0))))

    def _on_add(self):
        dlg = AddAccountDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            self._accounts.append(data)
            _save_json(ACCOUNTS_FILE, self._accounts)
            self._refresh_table()
            Toast.success(self, f"已添加 {data['account_name']}")

    def _on_edit(self, row):
        if row >= len(self._accounts):
            return
        dlg = AddAccountDialog(self, edit_data=self._accounts[row])
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            self._accounts[row] = data
            _save_json(ACCOUNTS_FILE, self._accounts)
            self._refresh_table()
            Toast.success(self, "已更新")

    def _on_delete(self, row):
        if row >= len(self._accounts):
            return
        acc = self._accounts[row]
        reply = QMessageBox.question(
            self, "确认删除", f"确定删除监控账号「{acc.get('account_name', '')}」？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._accounts.pop(row)
            _save_json(ACCOUNTS_FILE, self._accounts)
            self._refresh_table()
            Toast.success(self, "已删除")

    def _on_collect(self):
        """开始采集 - 使用嵌入浏览器（主线程）"""
        if not self._accounts:
            Toast.warning(self, "请先添加监控账号")
            return

        self._log_text.clear()
        self._log("开始采集...")
        self._progress_bar.setRange(0, 0)
        self._progress_bar.show()
        self._collect_btn.setEnabled(False)
        self._status_label.setText("正在采集数据...")

        self._scraper = BrowserScraper(self)
        self._scraper.log_msg.connect(self._log)
        self._scraper.account_done.connect(self._on_account_done)
        self._scraper.all_done.connect(self._on_browser_done)
        self._scraper.start(self._accounts)

    def _on_browser_done(self, results: list):
        self._collect_btn.setEnabled(True)
        self._progress_bar.hide()
        self._status_label.setText(f"采集完成，共 {len(results)} 个账号")

        old_map = {r["account_name"]: r for r in self._results}
        for r in results:
            if r.get("videos"):
                old_map[r["account_name"]] = r
            elif r.get("error") and r["account_name"] in old_map:
                pass
        self._results = list(old_map.values())
        _save_json(RESULTS_FILE, self._results)

        self._refresh_table()
        total_videos = sum(len(r.get("videos", [])) for r in self._results)
        self._log(f"\n🎉 全部采集完成! 共 {total_videos} 条视频数据")
        Toast.success(self, f"采集完成，共 {total_videos} 条视频")

    def _on_progress(self, name: str, page: int, count: int):
        self._status_label.setText(f"正在采集 {name} (第{page}页, 已找到{count}条)...")

    def _on_account_done(self, name: str, result: str, count: int):
        if result == "ok":
            self._log(f"✅ {name}: 采集成功, {count} 条视频")
        else:
            self._log(f"❌ {name}: {result}")

    def _on_finished(self, results: list):
        self._collect_btn.setEnabled(True)
        self._progress_bar.hide()
        self._status_label.setText(f"采集完成，共 {len(results)} 个账号")

        # 合并结果（保留旧数据）
        old_map = {r["account_name"]: r for r in self._results}
        for r in results:
            if r.get("videos"):
                old_map[r["account_name"]] = r
            elif r.get("error") and r["account_name"] in old_map:
                pass  # 采集失败保留旧数据
        self._results = list(old_map.values())
        _save_json(RESULTS_FILE, self._results)

        self._refresh_table()
        total_videos = sum(len(r.get("videos", [])) for r in self._results)
        self._log(f"\n🎉 全部采集完成! 共 {total_videos} 条视频数据")
        Toast.success(self, f"采集完成，共 {total_videos} 条视频")

    def _on_sync(self):
        """同步到服务端"""
        if not self._results:
            Toast.warning(self, "暂无采集数据，请先采集")
            return

        try:
            # 将采集结果同步到服务端
            for r in self._results:
                if r.get("videos"):
                    api.sync_collected_data(r)
            Toast.success(self, "数据已同步到服务端")
            self._log("☁️ 数据已同步到服务端")
        except Exception as e:
            Toast.error(self, f"同步失败: {e}")
            self._log(f"❌ 同步失败: {e}")

    def _on_export(self):
        """导出Excel"""
        if not self._results:
            Toast.warning(self, "暂无数据")
            return

        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "导出数据", f"video_data_{datetime.now().strftime('%Y%m%d')}.csv",
            "CSV Files (*.csv)"
        )
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8-sig") as f:
                f.write("平台,账号,视频标题,播放量,点赞量,评论量,分享量\n")
                for r in self._results:
                    p_name = {"douyin": "抖音", "kuaishou": "快手", "xiaohongshu": "小红书"}.get(r.get("platform", ""), r.get("platform", ""))
                    for v in r.get("videos", []):
                        title = v.get("title", "").replace('"', '""')
                        f.write(f'"{p_name}","{r.get("account_name", "")}","{title}",{v.get("plays", 0)},{v.get("likes", 0)},{v.get("comments", 0)},{v.get("shares", 0)}\n')
            Toast.success(self, f"已导出到 {path}")
        except Exception as e:
            Toast.error(self, f"导出失败: {e}")

    def _log(self, msg: str):
        self._log_text.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    @staticmethod
    def _format_num(n) -> str:
        if n >= 10000:
            return f"{n / 10000:.1f}w"
        return str(n)

    def load_data(self):
        """页面加载时刷新"""
        self._accounts = _load_json(ACCOUNTS_FILE)
        self._results = _load_json(RESULTS_FILE)
        self._refresh_table()

    def cleanup(self):
        """清理资源"""
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)
        if self._scraper:
            self._scraper.deleteLater()
