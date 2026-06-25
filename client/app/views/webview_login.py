"""
内嵌 WebView 扫码登录对话框
- 每个账号使用独立的 WebEngineProfile（隔离 Cookie）
- 登录成功后自动提取 Cookie
- 集成防封安全策略
"""

import json
import os
import time
from pathlib import Path

from PyQt6.QtCore import Qt, QUrl, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QApplication, QProgressBar
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import (
    QWebEngineProfile, QWebEnginePage, QWebEngineCookieStore
)

from ..styles.theme import (
    BG_COLOR, CARD_STYLE, TEXT_COLOR, TEXT_SECONDARY, PRIMARY,
    SUCCESS, DANGER, WARNING, BORDER_COLOR, BTN_PRIMARY, BTN_DEFAULT
)
from ..widgets.toast import Toast
from .. import anti_ban

# ── 平台登录 URL ──────────────────────────────────────────
PLATFORM_LOGIN_URLS = {
    "douyin": "https://creator.douyin.com/",
    "kuaishou": "https://cp.kuaishou.com/",
    "xiaohongshu": "https://creator.xiaohongshu.com/",
    "weixin": "https://channels.weixin.qq.com/",
}

# ── 平台登录成功后的 URL 特征 ──────────────────────────────
PLATFORM_LOGIN_SUCCESS_INDICATORS = {
    "douyin": ["creator.douyin.com/creator-micro", "creator.douyin.com/home"],
    "kuaishou": ["cp.kuaishou.com/home", "cp.kuaishou.com/user"],
    "xiaohongshu": ["creator.xiaohongshu.com/home", "creator.xiaohongshu.com/creator"],
    "weixin": ["channels.weixin.qq.com/home", "channels.weixin.qq.com/finder"],
}


class WebViewLoginDialog(QDialog):
    """内嵌浏览器扫码登录对话框
    
    每个实例使用独立的 QWebEngineProfile，确保 Cookie 隔离。
    """
    login_success = pyqtSignal(dict)  # {"cookies": str, "platform": str, "nickname": str}

    def __init__(self, platform: str, nickname: str = "", parent=None):
        super().__init__(parent)
        self._platform = platform
        self._nickname = nickname
        self._cookies = {}
        self._cookie_str = ""
        self._login_detected = False
        self._check_timer = None
        self._collected_cookies = []  # 通过 cookieAdded 收集的完整 cookie 数据

        platform_names = {
            "douyin": "抖音", "kuaishou": "快手",
            "xiaohongshu": "小红书", "weixin": "视频号"
        }
        p_name = platform_names.get(platform, platform)
        self.setWindowTitle(f"{p_name} 扫码登录 - {'(' + nickname + ') ' if nickname else ''}请在下方扫码")
        self.setMinimumSize(900, 700)
        self.resize(1000, 750)
        self.setStyleSheet(f"QDialog {{ background: {BG_COLOR}; }}")

        self._init_ui()
        self._load_page()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # ── 顶部提示栏 ──
        tip_frame = QFrame()
        tip_frame.setStyleSheet(f"""
            QFrame {{
                background: #FFF7E6;
                border: 1px solid #FFD591;
                border-radius: 6px;
                padding: 8px 12px;
            }}
        """)
        tip_layout = QHBoxLayout(tip_frame)
        tip_layout.setContentsMargins(8, 6, 8, 6)

        tip_icon = QLabel("🔒")
        tip_icon.setStyleSheet("font-size: 16px; border: none;")
        tip_layout.addWidget(tip_icon)

        self._tip_label = QLabel(
            "请在下方浏览器中扫码登录。每个账号使用独立的浏览器环境，互不影响。\n"
            "登录成功后系统会自动检测并提取凭证。"
        )
        self._tip_label.setStyleSheet(f"color: #AD6800; font-size: 12px; border: none;")
        self._tip_label.setWordWrap(True)
        tip_layout.addWidget(self._tip_label, 1)
        layout.addWidget(tip_frame)

        # ── 状态栏 ──
        status_bar = QHBoxLayout()
        self._status_label = QLabel("⏳ 正在加载登录页面...")
        self._status_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        status_bar.addWidget(self._status_label)
        status_bar.addStretch()

        self._ua_label = QLabel()
        self._ua_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        status_bar.addWidget(self._ua_label)
        layout.addLayout(status_bar)

        # ── 进度条 ──
        self._progress = QProgressBar()
        self._progress.setFixedHeight(3)
        self._progress.setRange(0, 0)  # indeterminate
        self._progress.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                background: {BORDER_COLOR};
                border-radius: 1px;
            }}
            QProgressBar::chunk {{
                background: {PRIMARY};
                border-radius: 1px;
            }}
        """)
        layout.addWidget(self._progress)

        # ── WebView ──
        # 使用独立 Profile 隔离 Cookie
        profile_name = f"login_{self._platform}_{int(time.time())}"
        self._profile = QWebEngineProfile(profile_name, self)
        self._profile.setHttpUserAgent(anti_ban.get_random_ua())
        self._ua_label.setText(f"UA: ...{self._profile.httpUserAgent()[-30:]}")

        self._web_view = QWebEngineView()
        self._page = QWebEnginePage(self._profile, self._web_view)
        self._web_view.setPage(self._page)

        # 监听 URL 变化（用于检测登录成功）
        self._page.urlChanged.connect(self._on_url_changed)
        self._page.loadFinished.connect(self._on_load_finished)

        layout.addWidget(self._web_view, 1)

        # ── 底部操作栏 ──
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(8)

        self._manual_btn = QPushButton("✅ 我已扫码登录，手动确认")
        self._manual_btn.setStyleSheet(BTN_PRIMARY)
        self._manual_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._manual_btn.clicked.connect(self._on_manual_confirm)
        self._manual_btn.setEnabled(False)
        bottom_bar.addWidget(self._manual_btn)

        self._refresh_btn = QPushButton("🔄 刷新页面")
        self._refresh_btn.setStyleSheet(BTN_DEFAULT)
        self._refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_btn.clicked.connect(self._on_refresh)
        bottom_bar.addWidget(self._refresh_btn)

        bottom_bar.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet(BTN_DEFAULT)
        cancel_btn.clicked.connect(self.reject)
        bottom_bar.addWidget(cancel_btn)

        layout.addLayout(bottom_bar)

        # ── 定时检测 Cookie 变化 ──
        self._cookie_store = self._profile.cookieStore()
        self._cookie_store.cookieAdded.connect(self._on_cookie_added)
        self._known_cookies = set()

    def _load_page(self):
        """加载平台登录页面"""
        url = PLATFORM_LOGIN_URLS.get(self._platform, "")
        if not url:
            Toast.error(self, f"未知平台: {self._platform}")
            self.reject()
            return

        # 防封：加载前随机等待
        delay = anti_ban.get_random_delay("page_load_wait")
        self._status_label.setText(f"⏳ 等待 {delay:.1f}s 后加载（防封随机延迟）...")
        QTimer.singleShot(int(delay * 1000), lambda: self._do_load(url))

    def _do_load(self, url: str):
        self._status_label.setText(f"⏳ 正在加载: {url}")
        self._web_view.load(QUrl(url))

    def _on_load_finished(self, ok: bool):
        if ok:
            self._status_label.setText("✅ 页面加载完成，请扫码或输入账号密码登录")
            self._manual_btn.setEnabled(True)
            self._progress.setRange(0, 100)
            self._progress.setValue(100)
        else:
            self._status_label.setText("❌ 页面加载失败，请点击刷新或检查网络")

    def _on_url_changed(self, url: QUrl):
        """URL 变化时检测是否登录成功"""
        url_str = url.toString()
        indicators = PLATFORM_LOGIN_SUCCESS_INDICATORS.get(self._platform, [])
        for indicator in indicators:
            if indicator in url_str:
                if not self._login_detected:
                    self._login_detected = True
                    self._status_label.setText("🎉 检测到登录成功！正在提取凭证...")
                    QTimer.singleShot(2000, self._extract_cookies)
                return

    def _on_cookie_added(self, cookie):
        """Cookie 添加时记录完整数据"""
        name = cookie.name().data().decode() if cookie.name() else ""
        value = cookie.value().data().decode() if cookie.value() else ""
        domain = cookie.domain()
        self._known_cookies.add(f"{name}@{domain}")
        if name and value:
            self._collected_cookies.append(f"{name}={value}")

    def _on_manual_confirm(self):
        """用户手动确认登录完成"""
        if self._login_detected:
            self._extract_cookies()
        else:
            # 还没检测到登录成功，再检查一下当前 URL
            current_url = self._page.url().toString()
            self._status_label.setText(f"🔍 当前URL: {current_url[:60]}... 正在提取Cookie...")
            QTimer.singleShot(1500, self._extract_cookies)

    def _extract_cookies(self):
        """提取当前所有 Cookie"""
        self._status_label.setText("🔑 正在提取 Cookie...")
        try:
            self._cookie_store.getAllCookies(self._on_cookies_ready)
        except AttributeError:
            # PyQt6 版本不支持 getAllCookies，使用通过 cookieAdded 收集的数据
            self._on_cookies_ready_from_signal()

    def _on_cookies_ready(self, cookies):
        """Cookie 提取完成回调"""
        cookie_parts = []
        for cookie in cookies:
            name = cookie.name().data().decode() if cookie.name() else ""
            value = cookie.value().data().decode() if cookie.value() else ""
            domain = cookie.domain()
            if name and value:
                cookie_parts.append(f"{name}={value}")

        self._cookie_str = "; ".join(cookie_parts)

        if not self._cookie_str:
            Toast.warning(self, "未获取到Cookie，请确认已在页面中完成登录")
            self._status_label.setText("⚠️ 未获取到Cookie，请确认登录状态")
            return

        # 记录登录操作
        if self._nickname:
            anti_ban.log_operation(
                f"{self._platform}_{self._nickname}",
                self._platform, "login"
            )

        self._status_label.setText(f"✅ 成功提取 {len(cookie_parts)} 个Cookie")

        # 发射信号
        self.login_success.emit({
            "cookies": self._cookie_str,
            "platform": self._platform,
            "nickname": self._nickname,
            "cookie_count": len(cookie_parts),
        })

        # 延迟关闭，让用户看到提示
        QTimer.singleShot(1500, self.accept)

    def _on_cookies_ready_from_signal(self):
        """使用通过 cookieAdded 信号收集的 Cookie 数据"""
        # 去重并保留最后的值
        seen = {}
        for c in self._collected_cookies:
            name = c.split('=', 1)[0] if '=' in c else c
            seen[name] = c
        cookie_parts = list(seen.values())

        self._cookie_str = "; ".join(cookie_parts)

        if not self._cookie_str:
            Toast.warning(self, "未获取到Cookie，请确认已在页面中完成登录")
            self._status_label.setText("⚠️ 未获取到Cookie，请确认登录状态")
            return

        # 记录登录操作
        if self._nickname:
            anti_ban.log_operation(
                f"{self._platform}_{self._nickname}",
                self._platform, "login"
            )

        self._status_label.setText(f"✅ 成功提取 {len(cookie_parts)} 个Cookie")

        # 发射信号
        self.login_success.emit({
            "cookies": self._cookie_str,
            "platform": self._platform,
            "nickname": self._nickname,
            "cookie_count": len(cookie_parts),
        })

        # 延迟关闭，让用户看到提示
        QTimer.singleShot(1500, self.accept)

    def _on_refresh(self):
        """刷新页面"""
        self._web_view.reload()

    def get_cookies(self) -> str:
        """获取提取的 Cookie 字符串"""
        return self._cookie_str

    def closeEvent(self, event):
        """关闭时清理"""
        if self._check_timer:
            self._check_timer.stop()
        # Profile 会在 dialog 被删除时自动清理
        super().closeEvent(event)
