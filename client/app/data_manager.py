"""
视频数据管理模块
管理视频库、裁切组、篮子、混剪任务的数据持久化
数据存储在 ~/.video-matrix/db.json
"""

import json
import os
import uuid
import shutil
from datetime import datetime
from pathlib import Path

# 数据目录
BASE_DIR = Path.home() / '.video-matrix'
LIBRARY_DIR = BASE_DIR / 'library'
BASKETS_DIR = BASE_DIR / 'baskets'
MIXED_DIR = BASE_DIR / 'mixed'
DB_FILE = BASE_DIR / 'db.json'

# 确保目录存在
for d in [LIBRARY_DIR, BASKETS_DIR, MIXED_DIR]:
    d.mkdir(parents=True, exist_ok=True)


def _gen_id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _load_db() -> dict:
    if DB_FILE.exists():
        try:
            return json.loads(DB_FILE.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {"videos": [], "cut_groups": [], "baskets": [], "mixed": []}


def _save_db(db: dict):
    DB_FILE.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding='utf-8')


# ══════════════════════════════════════════════════════════════
# 视频库
# ══════════════════════════════════════════════════════════════

def add_video(file_path: str, name: str = None, duration: float = 0, size: int = 0) -> dict:
    """添加视频到视频库（复制文件到library目录）"""
    db = _load_db()
    vid_id = _gen_id()
    ext = Path(file_path).suffix
    save_name = f"{vid_id}{ext}"
    save_path = LIBRARY_DIR / save_name

    # 复制文件
    shutil.copy2(file_path, save_path)

    video = {
        "id": vid_id,
        "name": name or Path(file_path).name,
        "file_name": save_name,
        "path": str(save_path),
        "duration": duration,
        "size": size or os.path.getsize(file_path),
        "added_at": _now(),
        "source": "upload"
    }
    db["videos"].append(video)
    _save_db(db)
    return video


def add_mixed_video(basket_id: str, mix_name: str, file_path: str, clips_used: list) -> dict:
    """将混剪完成的视频添加到视频库"""
    db = _load_db()
    vid_id = _gen_id()
    ext = Path(file_path).suffix
    save_name = f"{vid_id}{ext}"
    save_path = LIBRARY_DIR / save_name

    shutil.copy2(file_path, save_path)

    video = {
        "id": vid_id,
        "name": mix_name,
        "file_name": save_name,
        "path": str(save_path),
        "duration": 0,
        "size": os.path.getsize(file_path),
        "added_at": _now(),
        "source": "mixed",
        "basket_id": basket_id,
        "clips_used": clips_used
    }
    db["videos"].append(video)
    _save_db(db)
    return video


def get_videos() -> list:
    """获取视频库列表"""
    db = _load_db()
    return db.get("videos", [])


def get_video(vid_id: str) -> dict:
    """获取单个视频"""
    db = _load_db()
    for v in db.get("videos", []):
        if v["id"] == vid_id:
            return v
    return None


def delete_video(vid_id: str) -> bool:
    """从视频库删除视频"""
    db = _load_db()
    video = None
    for v in db.get("videos", []):
        if v["id"] == vid_id:
            video = v
            break
    if not video:
        return False
    # 删除文件
    if os.path.exists(video["path"]):
        os.remove(video["path"])
    db["videos"] = [v for v in db["videos"] if v["id"] != vid_id]
    _save_db(db)
    return True


# ══════════════════════════════════════════════════════════════
# 裁切组
# ══════════════════════════════════════════════════════════════

def create_cut_group(video_ids: list, cut_mode: str, cut_value: int, mix_segments: int = 1, group_name: str = None) -> dict:
    """
    创建裁切组
    cut_mode: "segments" (按段数) 或 "duration" (按时长秒)
    cut_value: 段数或秒数
    mix_segments: 每个混剪视频取几段
    """
    db = _load_db()
    group_id = _gen_id()
    basket_id = _gen_id()

    # 获取视频信息
    videos = []
    for vid in db.get("videos", []):
        if vid["id"] in video_ids:
            videos.append(vid)

    group = {
        "id": group_id,
        "name": group_name or f"裁切组 {len(db.get('cut_groups', [])) + 1}",
        "video_ids": video_ids,
        "video_count": len(videos),
        "cut_rule": {
            "mode": cut_mode,
            "value": cut_value
        },
        "mix_rule": {
            "segments_per_video": mix_segments
        },
        "status": "pending",  # pending -> cutting -> done
        "basket_id": basket_id,
        "progress": 0,
        "created_at": _now()
    }

    db.setdefault("cut_groups", []).append(group)

    # 创建篮子
    basket = {
        "id": basket_id,
        "group_id": group_id,
        "name": group["name"] + " 篮子",
        "clips": [],
        "status": "empty",  # empty -> ready -> mixing -> done
        "mix_progress": 0,
        "mix_total": 0,
        "created_at": _now()
    }
    db.setdefault("baskets", []).append(basket)

    _save_db(db)
    return group


def get_cut_groups() -> list:
    db = _load_db()
    return db.get("cut_groups", [])


def get_cut_group(group_id: str) -> dict:
    db = _load_db()
    for g in db.get("cut_groups", []):
        if g["id"] == group_id:
            return g
    return None


def update_cut_group_status(group_id: str, status: str, progress: int = None):
    db = _load_db()
    for g in db.get("cut_groups", []):
        if g["id"] == group_id:
            g["status"] = status
            if progress is not None:
                g["progress"] = progress
            break
    _save_db(db)


def delete_cut_group(group_id: str) -> bool:
    """删除裁切组及其篮子"""
    db = _load_db()
    group = None
    for g in db.get("cut_groups", []):
        if g["id"] == group_id:
            group = g
            break
    if not group:
        return False

    # 删除篮子文件
    basket_id = group.get("basket_id")
    basket_dir = BASKETS_DIR / basket_id
    if basket_dir.exists():
        shutil.rmtree(basket_dir)

    db["cut_groups"] = [g for g in db.get("cut_groups", []) if g["id"] != group_id]
    db["baskets"] = [b for b in db.get("baskets", []) if b["id"] != basket_id]
    _save_db(db)
    return True


# ══════════════════════════════════════════════════════════════
# 篮子
# ══════════════════════════════════════════════════════════════

def get_baskets() -> list:
    db = _load_db()
    return db.get("baskets", [])


def get_basket(basket_id: str) -> dict:
    db = _load_db()
    for b in db.get("baskets", []):
        if b["id"] == basket_id:
            return b
    return None


def add_clip_to_basket(basket_id: str, source_video: str, segment_index: int, file_path: str, duration: float = 0):
    """向篮子中添加一个裁切好的片段"""
    db = _load_db()
    clip_id = _gen_id()
    clip = {
        "id": clip_id,
        "source_video": source_video,
        "segment_index": segment_index,
        "path": file_path,
        "duration": duration
    }
    for b in db.get("baskets", []):
        if b["id"] == basket_id:
            b.setdefault("clips", []).append(clip)
            b["status"] = "ready"
            break
    _save_db(db)
    return clip


def update_basket_status(basket_id: str, status: str, mix_progress: int = None, mix_total: int = None):
    db = _load_db()
    for b in db.get("baskets", []):
        if b["id"] == basket_id:
            b["status"] = status
            if mix_progress is not None:
                b["mix_progress"] = mix_progress
            if mix_total is not None:
                b["mix_total"] = mix_total
            break
    _save_db(db)


def get_basket_clips_by_source(basket_id: str) -> dict:
    """按来源视频分组获取篮子中的片段"""
    basket = get_basket(basket_id)
    if not basket:
        return {}
    groups = {}
    for clip in basket.get("clips", []):
        src = clip["source_video"]
        groups.setdefault(src, []).append(clip)
    # 按片段序号排序
    for src in groups:
        groups[src].sort(key=lambda c: c["segment_index"])
    return groups


# ══════════════════════════════════════════════════════════════
# 混剪任务
# ══════════════════════════════════════════════════════════════

def create_mix_task(basket_id: str, segments_per_video: int = 1, auto: bool = True) -> dict:
    """
    创建混剪任务
    auto=True: 自动排列组合
    segments_per_video: 每个混剪视频从每个来源取几段
    """
    db = _load_db()
    basket = None
    for b in db.get("baskets", []):
        if b["id"] == basket_id:
            basket = b
            break
    if not basket:
        return None

    # 按来源分组
    clips_by_source = {}
    for clip in basket.get("clips", []):
        src = clip["source_video"]
        clips_by_source.setdefault(src, []).append(clip)
    for src in clips_by_source:
        clips_by_source[src].sort(key=lambda c: c["segment_index"])

    sources = sorted(clips_by_source.keys())
    # 按最少段数来
    min_clips = min(len(clips_by_source[s]) for s in sources) if sources else 0

    if segments_per_video > min_clips:
        segments_per_video = min_clips

    # 计算组合数
    from itertools import product
    # 每个来源取 segments_per_video 段的组合
    # 简化：每个来源取1段（segments_per_video=1），排列组合
    # 如果 segments_per_video > 1，从每个来源取连续的 segments_per_video 段
    combinations = []
    if segments_per_video == 1:
        # 简单排列组合：每个来源取1段
        source_clips = [clips_by_source[s] for s in sources]
        for combo in product(*source_clips):
            combinations.append([c["id"] for c in combo])
    else:
        # 每个来源取连续 segments_per_video 段
        source_clips = []
        for s in sources:
            clips = clips_by_source[s]
            valid_starts = len(clips) - segments_per_video + 1
            source_clips.append([(clips[i:i+segments_per_video]) for i in range(valid_starts)])
        for combo in product(*source_clips):
            clip_ids = []
            for group in combo:
                clip_ids.extend([c["id"] for c in group])
            combinations.append(clip_ids)

    task_id = _gen_id()
    task = {
        "id": task_id,
        "basket_id": basket_id,
        "segments_per_video": segments_per_video,
        "combinations": combinations,
        "total": len(combinations),
        "completed": 0,
        "status": "pending",  # pending -> running -> done
        "created_at": _now()
    }

    db.setdefault("mix_tasks", []).append(task)

    # 更新篮子状态
    for b in db.get("baskets", []):
        if b["id"] == basket_id:
            b["status"] = "mixing"
            b["mix_total"] = len(combinations)
            b["mix_progress"] = 0
            break

    _save_db(db)
    return task


def get_mix_tasks() -> list:
    db = _load_db()
    return db.get("mix_tasks", [])


def get_mix_task(task_id: str) -> dict:
    db = _load_db()
    for t in db.get("mix_tasks", []):
        if t["id"] == task_id:
            return t
    return None


def update_mix_task_progress(task_id: str, completed: int, status: str = None):
    db = _load_db()
    task = None
    for t in db.get("mix_tasks", []):
        if t["id"] == task_id:
            t["completed"] = completed
            if status:
                t["status"] = status
            task = t
            break
    # 同步更新篮子进度
    if task:
        for b in db.get("baskets", []):
            if b["id"] == task["basket_id"]:
                b["mix_progress"] = completed
                if status == "done":
                    b["status"] = "done"
                break
    _save_db(db)


def add_mixed_result(task_id: str, mix_name: str, file_path: str, clip_ids: list):
    """记录一个混剪完成的结果"""
    db = _load_db()
    result = {
        "id": _gen_id(),
        "task_id": task_id,
        "name": mix_name,
        "path": file_path,
        "clip_ids": clip_ids,
        "created_at": _now()
    }
    db.setdefault("mixed_results", []).append(result)
    _save_db(db)
    return result


def delete_mix_task(task_id: str) -> bool:
    """删除混剪任务"""
    db = _load_db()
    task = None
    for t in db.get("mix_tasks", []):
        if t["id"] == task_id:
            task = t
            break
    if not task:
        return False

    # 删除混剪输出文件
    task_dir = MIXED_DIR / task_id
    if task_dir.exists():
        shutil.rmtree(task_dir)

    db["mix_tasks"] = [t for t in db.get("mix_tasks", []) if t["id"] != task_id]
    _save_db(db)
    return True


# ══════════════════════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════════════════════

def get_clip_by_id(clip_id: str) -> dict:
    """根据ID获取篮子中的片段"""
    db = _load_db()
    for b in db.get("baskets", []):
        for c in b.get("clips", []):
            if c["id"] == clip_id:
                return c
    return None


def get_clips_by_ids(clip_ids: list) -> list:
    """根据ID列表获取多个片段"""
    db = _load_db()
    clip_map = {}
    for b in db.get("baskets", []):
        for c in b.get("clips", []):
            clip_map[c["id"]] = c
    return [clip_map[cid] for cid in clip_ids if cid in clip_map]
