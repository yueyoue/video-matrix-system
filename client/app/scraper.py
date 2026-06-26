"""
数据采集爬虫 - 使用 QWebEngineView 加载页面，提取视频数据

支持平台：
- 抖音: https://www.douyin.com/user/{sec_uid}
- 快手: https://www.kuaishou.com/profile/{user_id}
- 小红书: https://www.xiaohongshu.com/user/profile/{user_id}
"""

import json
import time
from datetime import datetime
from typing import Optional

from PyQt6.QtCore import QUrl, QTimer, QEventLoop, QObject, pyqtSignal
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage


class ScraperSignals(QObject):
    """爬虫信号"""
    progress = pyqtSignal(str, int, int)   # (account_name, current_page, videos_found)
    finished = pyqtSignal(str, list)        # (account_name, videos_list)
    error = pyqtSignal(str, str)            # (account_name, error_message)


class ProfileScraper(QWebEngineView):
    """
    用 QWebEngineView 加载用户主页，通过 JS 提取视频数据。
    每个实例独立 profile，不干扰登录 Cookie。
    """

    def __init__(self, platform: str, sec_uid: str, account_name: str, parent=None):
        super().__init__(parent)
        self._platform = platform
        self._sec_uid = sec_uid
        self._account_name = account_name
        self._videos: list[dict] = []
        self._page_count = 0
        self._max_pages = 15
        self._scroll_count = 0
        self._max_scrolls = 30
        self._signals = ScraperSignals()
        self._done = False

        # 使用独立 profile 避免污染登录态
        profile = QWebEngineProfile(f"scraper_{account_name}", self)
        page = QWebEnginePage(profile, self)
        self.setPage(page)

        self.setFixedSize(1280, 800)  # 需要一定尺寸才能正常渲染
        self.move(-2000, -2000)  # 移到屏幕外

        # 页面加载完成后开始提取
        self.loadFinished.connect(self._on_load_finished)

    @property
    def signals(self) -> ScraperSignals:
        return self._signals

    def start(self):
        """开始爬取"""
        url = self._build_url()
        if not url:
            self._signals.error.emit(self._account_name, f"不支持的平台: {self._platform}")
            return

        print(f"[Scraper] 开始爬取 {self._account_name} -> {url}")
        self.load(QUrl(url))

    def _build_url(self) -> str:
        urls = {
            "douyin": f"https://www.douyin.com/user/{self._sec_uid}",
            "kuaishou": f"https://www.kuaishou.com/profile/{self._sec_uid}",
            "xiaohongshu": f"https://www.xiaohongshu.com/user/profile/{self._sec_uid}",
        }
        return urls.get(self._platform, "")

    def _on_load_finished(self, ok: bool):
        if not ok:
            self._signals.error.emit(self._account_name, "页面加载失败")
            self._cleanup()
            return

        print(f"[Scraper] 页面加载完成，等待渲染...")
        # 等待 JS 渲染完成
        QTimer.singleShot(3000, self._start_extract)

    def _start_extract(self):
        """开始提取数据 - 先尝试从嵌入数据提取，再尝试DOM"""
        js = self._get_extract_js()
        self.page().runJavaScript(js, self._on_extract_result)

    def _get_extract_js(self) -> str:
        """返回提取视频数据的 JS 代码"""
        if self._platform == "douyin":
            return """
            (function() {
                // 方案1: 从 RENDER_DATA 提取
                var script = document.getElementById('RENDER_DATA');
                if (script) {
                    try {
                        var data = JSON.parse(decodeURIComponent(script.textContent));
                        // 递归查找 aweme_list
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
                            var videos = [];
                            for (var i = 0; i < list.length; i++) {
                                var item = list[i];
                                var stats = item.statistics || {};
                                videos.push({
                                    title: item.desc || '',
                                    plays: stats.play_count || 0,
                                    likes: stats.digg_count || 0,
                                    comments: stats.comment_count || 0,
                                    shares: stats.share_count || 0,
                                    publish_time: item.create_time ? new Date(item.create_time * 1000).toISOString() : ''
                                });
                            }
                            return JSON.stringify({source: 'RENDER_DATA', videos: videos});
                        }
                    } catch(e) {}
                }

                // 方案2: 从DOM提取
                var videos = [];
                var items = document.querySelectorAll('[class*="videoCard"], [class*="video-card"], .ECMy_Zdt');
                for (var i = 0; i < items.length; i++) {
                    var el = items[i];
                    var titleEl = el.querySelector('[class*="title"], [class*="desc"], a[title]');
                    var statsEls = el.querySelectorAll('[class*="count"], [class*="num"], span');
                    var title = titleEl ? (titleEl.getAttribute('title') || titleEl.textContent.trim()) : '';
                    var plays = 0, likes = 0;
                    for (var j = 0; j < statsEls.length; j++) {
                        var txt = statsEls[j].textContent.trim();
                        if (/^[\\d.]+[万w]?$/i.test(txt)) {
                            var n = parseFloat(txt);
                            if (txt.match(/[万w]/i)) n *= 10000;
                            if (plays === 0) plays = Math.round(n);
                            else if (likes === 0) likes = Math.round(n);
                        }
                    }
                    if (title) videos.push({title: title, plays: plays, likes: likes, comments: 0, shares: 0, publish_time: ''});
                }
                return JSON.stringify({source: 'DOM', videos: videos});
            })();
            """
        elif self._platform == "kuaishou":
            return """
            (function() {
                var videos = [];
                var items = document.querySelectorAll('.video-card, [class*="videoCard"], .profile-photo-item');
                for (var i = 0; i < items.length; i++) {
                    var el = items[i];
                    var titleEl = el.querySelector('.title, .caption, [class*="title"]');
                    var viewEl = el.querySelector('.count, [class*="view"], [class*="play"]');
                    var title = titleEl ? titleEl.textContent.trim() : '';
                    var plays = 0;
                    if (viewEl) {
                        var txt = viewEl.textContent.trim();
                        var n = parseFloat(txt);
                        if (txt.match(/[万w]/i)) n *= 10000;
                        plays = Math.round(n);
                    }
                    if (title) videos.push({title: title, plays: plays, likes: 0, comments: 0, shares: 0, publish_time: ''});
                }
                return JSON.stringify({source: 'DOM', videos: videos});
            })();
            """
        else:  # xiaohongshu
            return """
            (function() {
                var videos = [];
                var items = document.querySelectorAll('.note-item, [class*="noteItem"], section.note-item');
                for (var i = 0; i < items.length; i++) {
                    var el = items[i];
                    var titleEl = el.querySelector('.title, [class*="title"], .desc');
                    var likeEl = el.querySelector('.count, [class*="like"], [class*="count"]');
                    var title = titleEl ? titleEl.textContent.trim() : '';
                    var likes = 0;
                    if (likeEl) {
                        var txt = likeEl.textContent.trim();
                        var n = parseFloat(txt);
                        if (txt.match(/[万w]/i)) n *= 10000;
                        likes = Math.round(n);
                    }
                    if (title) videos.push({title: title, plays: 0, likes: likes, comments: 0, shares: 0, publish_time: ''});
                }
                return JSON.stringify({source: 'DOM', videos: videos});
            })();
            """

    def _on_extract_result(self, result):
        """提取结果回调"""
        if not result:
            # 可能页面还没渲染完，等一下再试
            if self._scroll_count < 3:
                self._scroll_count += 1
                QTimer.singleShot(2000, self._start_extract)
                return
            self._signals.error.emit(self._account_name, "未能提取到视频数据")
            self._cleanup()
            return

        try:
            data = json.loads(result)
            source = data.get("source", "unknown")
            videos = data.get("videos", [])
            print(f"[Scraper] {self._account_name} 提取方式={source}, 视频数={len(videos)}")

            if not videos and self._scroll_count < self._max_scrolls:
                # 没提取到，尝试滚动加载更多
                self._scroll_count += 1
                self._scroll_page()
                return

            self._videos = videos
            self._signals.finished.emit(self._account_name, videos)
        except json.JSONDecodeError as e:
            print(f"[Scraper] JSON解析失败: {e}, result={str(result)[:200]}")
            self._signals.error.emit(self._account_name, f"数据解析失败: {e}")
        finally:
            self._cleanup()

    def _scroll_page(self):
        """滚动页面加载更多内容"""
        js = "window.scrollTo(0, document.body.scrollHeight);"
        self.page().runJavaScript(js, lambda _: QTimer.singleShot(2000, self._check_scroll_end))

    def _check_scroll_end(self):
        """检查是否滚动到底部"""
        js = """
        (function() {
            var h = document.body.scrollHeight;
            window.scrollTo(0, h);
            return document.body.scrollHeight;
        })();
        """
        self.page().runJavaScript(js, self._on_scroll_result)

    def _on_scroll_result(self, new_height):
        """滚动后重新提取"""
        self._page_count += 1
        self._signals.progress.emit(self._account_name, self._page_count, len(self._videos))
        self._start_extract()

    def _cleanup(self):
        """清理资源"""
        self._done = True
        QTimer.singleShot(500, self.close)


class ScraperManager(QObject):
    """
    管理多个爬虫实例，依次爬取。
    """

    all_finished = pyqtSignal(list)  # 所有结果 [{account_name, platform, videos, error}]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._accounts: list[dict] = []
        self._results: list[dict] = []
        self._current_idx = 0
        self._scraper: Optional[ProfileScraper] = None

    def start(self, accounts: list[dict]):
        """
        开始批量爬取。
        accounts: [{"platform": "douyin", "sec_uid": "xxx", "account_name": "xxx"}, ...]
        """
        self._accounts = accounts
        self._results = []
        self._current_idx = 0
        self._start_next()

    def _start_next(self):
        if self._current_idx >= len(self._accounts):
            self.all_finished.emit(self._results)
            return

        acc = self._accounts[self._current_idx]
        self._scraper = ProfileScraper(
            platform=acc["platform"],
            sec_uid=acc["sec_uid"],
            account_name=acc["account_name"],
            parent=self.parent()  # attach to parent to keep alive
        )
        self._scraper.signals.finished.connect(self._on_finished)
        self._scraper.signals.error.connect(self._on_error)
        self._scraper.signals.progress.connect(self._on_progress)
        self._scraper.show()  # QWebEngineView 需要 show 才能正常工作
        self._scraper.start()

    def _on_finished(self, account_name: str, videos: list):
        self._results.append({
            "account_name": account_name,
            "platform": self._accounts[self._current_idx]["platform"],
            "videos": videos,
            "error": None
        })
        print(f"[ScraperManager] {account_name} 完成, {len(videos)} 条视频")
        self._current_idx += 1
        QTimer.singleShot(1000, self._start_next)

    def _on_error(self, account_name: str, error: str):
        self._results.append({
            "account_name": account_name,
            "platform": self._accounts[self._current_idx]["platform"],
            "videos": [],
            "error": error
        })
        print(f"[ScraperManager] {account_name} 失败: {error}")
        self._current_idx += 1
        QTimer.singleShot(1000, self._start_next)

    def _on_progress(self, account_name: str, page: int, count: int):
        print(f"[ScraperManager] {account_name} 滚动第{page}页, 已找到{count}条")
