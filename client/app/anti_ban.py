"""
防封安全策略配置
- 操作间隔随机延迟
- User-Agent 池轮换
- 平台操作频率限制
- 账号操作记录追踪
"""

import random
import time
import json
import os
from pathlib import Path
from datetime import datetime

# ── User-Agent 池 ─────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
]

# ── 延迟配置（秒）─────────────────────────────────────────
DELAY_CONFIG = {
    "login_interval": (30, 120),        # 同平台两次登录间隔
    "operation_interval": (5, 15),      # 通用操作间隔
    "publish_interval": (180, 600),     # 发布间隔（3-10分钟）
    "batch_operation": (10, 30),        # 批量操作间隔
    "page_load_wait": (2, 5),           # 页面加载等待
    "human_like_scroll": (0.5, 2.0),    # 模拟人类滚动间隔
}

# ── 频率限制 ──────────────────────────────────────────────
RATE_LIMITS = {
    "douyin": {
        "max_publish_per_hour": 3,
        "max_publish_per_day": 10,
        "max_login_per_day": 5,
        "min_publish_interval": 300,    # 最小发布间隔（秒）
    },
    "kuaishou": {
        "max_publish_per_hour": 3,
        "max_publish_per_day": 10,
        "max_login_per_day": 5,
        "min_publish_interval": 300,
    },
    "xiaohongshu": {
        "max_publish_per_hour": 2,
        "max_publish_per_day": 8,
        "max_login_per_day": 5,
        "min_publish_interval": 600,
    },
    "weixin": {
        "max_publish_per_hour": 2,
        "max_publish_per_day": 8,
        "max_login_per_day": 5,
        "min_publish_interval": 600,
    },
}

# ── 操作日志路径 ──────────────────────────────────────────
_LOG_DIR = Path.home() / ".video-matrix"
_OPERATION_LOG = _LOG_DIR / "operation_log.json"


def _load_operations() -> dict:
    """加载操作日志"""
    if _OPERATION_LOG.exists():
        try:
            return json.loads(_OPERATION_LOG.read_text())
        except Exception:
            pass
    return {"accounts": {}, "global": {"last_operation": 0}}


def _save_operations(data: dict):
    """保存操作日志"""
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    _OPERATION_LOG.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def log_operation(account_id: str, platform: str, operation: str):
    """记录一次操作"""
    data = _load_operations()
    now = time.time()
    today = datetime.now().strftime("%Y-%m-%d")

    if account_id not in data["accounts"]:
        data["accounts"][account_id] = {
            "platform": platform,
            "last_login": 0,
            "operations": [],
            "daily_counts": {},
        }

    acc = data["accounts"][account_id]
    acc["operations"].append({"type": operation, "time": now})
    # 只保留最近100条
    acc["operations"] = acc["operations"][-100:]

    if today not in acc["daily_counts"]:
        acc["daily_counts"] = {}
    acc["daily_counts"][today] = acc["daily_counts"].get(today, {})
    acc["daily_counts"][today][operation] = acc["daily_counts"][today].get(operation, 0) + 1

    data["global"]["last_operation"] = now
    _save_operations(data)


def can_perform_operation(account_id: str, platform: str, operation: str) -> tuple[bool, str]:
    """检查是否允许执行操作，返回 (allowed, reason)"""
    data = _load_operations()
    now = time.time()
    today = datetime.now().strftime("%Y-%m-%d")
    limits = RATE_LIMITS.get(platform, RATE_LIMITS.get("douyin"))

    if account_id not in data["accounts"]:
        return True, "新账号，允许操作"

    acc = data["accounts"][account_id]

    # 检查登录频率
    if operation == "login":
        recent_logins = sum(
            1 for op in acc["operations"]
            if op["type"] == "login" and now - op["time"] < 86400
        )
        if recent_logins >= limits["max_login_per_day"]:
            return False, f"今日登录次数已达上限({limits['max_login_per_day']})"

        last_login = acc.get("last_login", 0)
        min_interval = DELAY_CONFIG["login_interval"][0]
        if now - last_login < min_interval:
            wait = int(min_interval - (now - last_login))
            return False, f"距上次登录间隔太短，请等待{wait}秒"

    # 检查发布频率
    if operation == "publish":
        daily_counts = acc.get("daily_counts", {}).get(today, {})
        daily_publish = daily_counts.get("publish", 0)
        if daily_publish >= limits["max_publish_per_day"]:
            return False, f"今日发布已达上限({limits['max_publish_per_day']})"

        recent_hour_publish = sum(
            1 for op in acc["operations"]
            if op["type"] == "publish" and now - op["time"] < 3600
        )
        if recent_hour_publish >= limits["max_publish_per_hour"]:
            return False, f"近1小时发布已达上限({limits['max_publish_per_hour']})"

        # 检查最小发布间隔
        last_publish = 0
        for op in reversed(acc["operations"]):
            if op["type"] == "publish":
                last_publish = op["time"]
                break
        if last_publish and now - last_publish < limits["min_publish_interval"]:
            wait = int(limits["min_publish_interval"] - (now - last_publish))
            return False, f"距上次发布间隔太短，请等待{wait}秒"

    return True, "允许操作"


def get_random_delay(delay_type: str) -> float:
    """获取随机延迟时间"""
    config = DELAY_CONFIG.get(delay_type, (1, 5))
    return random.uniform(config[0], config[1])


def get_random_ua() -> str:
    """获取随机 User-Agent"""
    return random.choice(USER_AGENTS)


def get_ua_for_account(account_id: str) -> str:
    """为账号分配固定的 User-Agent（基于账号ID哈希）"""
    idx = hash(account_id) % len(USER_AGENTS)
    return USER_AGENTS[idx]


def get_account_health(account_id: str) -> dict:
    """获取账号健康状态"""
    data = _load_operations()
    now = time.time()
    today = datetime.now().strftime("%Y-%m-%d")

    if account_id not in data["accounts"]:
        return {"status": "unknown", "message": "无操作记录"}

    acc = data["accounts"][account_id]
    daily_counts = acc.get("daily_counts", {}).get(today, {})
    platform = acc.get("platform", "douyin")
    limits = RATE_LIMITS.get(platform, RATE_LIMITS.get("douyin"))

    publish_count = daily_counts.get("publish", 0)
    login_count = daily_counts.get("login", 0)

    warnings = []
    if publish_count >= limits["max_publish_per_day"] * 0.8:
        warnings.append("今日发布量接近上限")
    if login_count >= limits["max_login_per_day"] * 0.8:
        warnings.append("今日登录次数接近上限")

    # 检查最近操作间隔是否过短
    recent_ops = [op for op in acc["operations"] if now - op["time"] < 3600]
    if len(recent_ops) > 10:
        warnings.append("近1小时操作频繁")

    if warnings:
        return {"status": "warning", "message": "；".join(warnings)}
    return {"status": "healthy", "message": "正常"}


def cleanup_old_logs(days: int = 30):
    """清理超过指定天数的操作日志"""
    data = _load_operations()
    cutoff = time.time() - days * 86400

    for acc_id in list(data["accounts"].keys()):
        acc = data["accounts"][acc_id]
        acc["operations"] = [op for op in acc["operations"] if op["time"] > cutoff]
        # 清理旧的每日统计
        old_dates = [d for d in acc.get("daily_counts", {}) if d < datetime.fromtimestamp(cutoff).strftime("%Y-%m-%d")]
        for d in old_dates:
            del acc["daily_counts"][d]

    _save_operations(data)
