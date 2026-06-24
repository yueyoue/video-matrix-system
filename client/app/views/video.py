"""
视频处理模块 v4 - 视频库、裁切队列、篮子、AI制作、混剪队列、待发布库
修复：按钮样式、新增AI制作、混剪AI插入设置
"""

import os
import json
import random
import subprocess
import sys
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QLineEdit, QSpinBox, QComboBox, QFileDialog, QGridLayout, QScrollArea,
    QSizePolicy, QProgressBar, QCheckBox, QTabWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QFormLayout, QGroupBox, QMessageBox,
    QListWidget, QListWidgetItem, QAbstractItemView, QDialog, QDialogButtonBox,
    QTextEdit, QDoubleSpinBox
)
from ..styles.theme import (
    BG_COLOR, CARD_STYLE, TEXT_COLOR, TEXT_SECONDARY, PRIMARY, PRIMARY_HOVER,
    SUCCESS, DANGER, DANGER_HOVER, WARNING, BORDER_COLOR, WHITE,
    BTN_PRIMARY, BTN_PRIMARY_SM, BTN_DEFAULT, BTN_DANGER, BTN_DANGER_TEXT,
    BTN_SUCCESS, BTN_TEXT, INPUT_STYLE, SPINBOX_STYLE, TABLE_STYLE
)
from ..widgets.toast import Toast
from .. import ffmpeg
from .. import data_manager as dm
from pathlib import Path


# ══════════════════════════════════════════════════════════════
# 样式常量 - 表格行内操作按钮（单行CSS，避免解析问题）
# ══════════════════════════════════════════════════════════════



# ══════════════════════════════════════════════════════════════
# 工作线程
# ══════════════════════════════════════════════════════════════

class _UploadWorker(QThread):
    done = pyqtSignal(dict)
    failed = pyqtSignal(str)
    def __init__(self, file_paths): super().__init__(); self.file_paths = file_paths
    def run(self):
        try:
            results = []
            for fp in self.file_paths:
                dur = 0
                try: dur = ffmpeg.get_duration(fp)
                except: pass
                results.append(dm.add_video(fp, duration=dur))
            self.done.emit({"videos": results})
        except Exception as e: self.failed.emit(str(e))


class _CutWorker(QThread):
    progress = pyqtSignal(str, int)
    done = pyqtSignal(str)
    failed = pyqtSignal(str)
    def __init__(self, group_id): super().__init__(); self.group_id = group_id
    def run(self):
        try:
            group = dm.get_cut_group(self.group_id)
            if not group: self.failed.emit("裁切组不存在"); return
            dm.update_cut_group_status(self.group_id, "cutting", 0)
            cut_rule = group["cut_rule"]
            basket_id = group["basket_id"]
            basket_dir = dm.BASKETS_DIR / basket_id
            basket_dir.mkdir(parents=True, exist_ok=True)
            videos = [dm.get_video(vid) for vid in group["video_ids"]]
            videos = [v for v in videos if v]
            total = len(videos)
            for idx, video in enumerate(videos):
                self.progress.emit(f"裁切: {video['name']} ({idx+1}/{total})", int(idx/total*100))
                if cut_rule["mode"] == "segments":
                    clips = ffmpeg.cut_video_segments(video["path"], cut_rule["value"], str(basket_dir), video["name"])
                else:
                    clips = ffmpeg.cut_video_by_duration(video["path"], cut_rule["value"], str(basket_dir), video["name"])
                for i, cp in enumerate(clips):
                    cd = 0
                    try: cd = ffmpeg.get_duration(cp)
                    except: pass
                    dm.add_clip_to_basket(basket_id, video["name"], i+1, cp, cd)
                dm.update_cut_group_status(self.group_id, "cutting", int((idx+1)/total*100))
            dm.update_cut_group_status(self.group_id, "done", 100)
            self.progress.emit("裁切完成!", 100)
            self.done.emit(self.group_id)
        except Exception as e:
            dm.update_cut_group_status(self.group_id, "error")
            self.failed.emit(str(e))


class _MixWorker(QThread):
    progress = pyqtSignal(str, int)
    done = pyqtSignal(str)
    failed = pyqtSignal(str)
    def __init__(self, task_id, audio_combos=None, audio_mode="random", ai_insert=None):
        super().__init__()
        self.task_id = task_id
        self.audio_combos = audio_combos or []
        self.audio_mode = audio_mode
        self.ai_insert = ai_insert or {}
    def run(self):
        try:
            task = dm.get_mix_task(self.task_id)
            if not task: self.failed.emit("混剪任务不存在"); return
            dm.update_mix_task_progress(self.task_id, 0, "running")
            basket_id = task["basket_id"]
            segments_per_video = task.get("segments_per_video", 1)
            if segments_per_video < 1: segments_per_video = 1
            clips_by_src = dm.get_basket_clips_by_source(basket_id)
            sources = sorted(clips_by_src.keys())
            if not sources:
                dm.update_mix_task_progress(self.task_id, 0, "error")
                self.failed.emit("篮子中没有片段，请先完成裁切"); return
            min_clips = min(len(clips_by_src[s]) for s in sources)
            if min_clips < 1:
                dm.update_mix_task_progress(self.task_id, 0, "error")
                self.failed.emit("篮子中没有可用片段"); return
            if segments_per_video > min_clips: segments_per_video = min_clips
            from itertools import product
            if segments_per_video == 1:
                source_clips = [clips_by_src[s] for s in sources]
                combinations = [[c["id"] for c in combo] for combo in product(*source_clips)]
            else:
                source_clip_groups = []
                for s in sources:
                    clips = clips_by_src[s]
                    groups = [clips[i:i+segments_per_video] for i in range(len(clips) - segments_per_video + 1)]
                    source_clip_groups.append(groups)
                combinations = []
                for combo in product(*source_clip_groups):
                    ids = []
                    for group in combo: ids.extend([c["id"] for c in group])
                    combinations.append(ids)
            total = len(combinations)
            if total == 0:
                dm.update_mix_task_progress(self.task_id, 0, "error")
                self.failed.emit("无法生成组合"); return
            dm.update_mix_task_total(self.task_id, total)
            mix_dir = dm.MIXED_DIR / self.task_id
            mix_dir.mkdir(parents=True, exist_ok=True)

            # 收集AI生成的素材路径
            ai_videos = []
            ai_audios = []
            for item in dm.get_ai_assets():
                if item.get("type") == "video" and os.path.exists(item.get("path", "")):
                    ai_videos.append(item)
                elif item.get("type") == "audio" and os.path.exists(item.get("path", "")):
                    ai_audios.append(item)

            # 确定指定的素材
            video_asset_id = self.ai_insert.get("video_asset", "random")
            audio_asset_id = self.ai_insert.get("audio_asset", "random")
            specified_video = None
            specified_audio = None
            if video_asset_id != "random":
                for a in ai_videos:
                    if a["id"] == video_asset_id:
                        specified_video = a["path"]; break
            if audio_asset_id != "random":
                for a in ai_audios:
                    if a["id"] == audio_asset_id:
                        specified_audio = a["path"]; break

            for idx, clip_ids in enumerate(combinations):
                self.progress.emit(f"混剪 {idx+1}/{total}", int(idx/total*100))
                clips = dm.get_clips_by_ids(clip_ids)
                clip_paths = [c["path"] for c in clips]
                if not clip_paths: continue
                mix_name = f"混剪_{idx+1}"
                out_path = str(mix_dir / f"{mix_name}.mp4")
                audio_path = None; subtitle_text = ""
                if self.audio_combos:
                    combo = random.choice(self.audio_combos) if self.audio_mode == "random" else self.audio_combos[idx % len(self.audio_combos)]
                    audio_path = combo.get("audio")
                    subtitle_text = combo.get("text", "")

                # 应用AI视频插入
                final_paths = list(clip_paths)
                ai_video_pos = self.ai_insert.get("video_position", "none")
                if ai_video_pos != "none":
                    chosen_ai = specified_video or (random.choice(ai_videos)["path"] if ai_videos else None)
                    if chosen_ai:
                        final_paths.insert(0, chosen_ai)
                    elif ai_video_pos == "tail":
                        final_paths.append(chosen_ai)
                    elif ai_video_pos == "random":
                        pos = random.randint(1, len(final_paths) - 1) if len(final_paths) > 1 else 1
                        final_paths.insert(pos, chosen_ai)
                    elif ai_video_pos == "fixed":
                        fixed_sec = self.ai_insert.get("video_fixed_time", 5)
                        # 固定时间点插入 - 在混剪后作为片尾附加
                        final_paths.append(chosen_ai)

                ffmpeg.mix_videos(final_paths, out_path, bg_audio=audio_path)

                # 应用AI音频插入
                ai_audio_pos = self.ai_insert.get("audio_position", "none")
                if ai_audio_pos != "none":
                    chosen_audio = specified_audio or (random.choice(ai_audios)["path"] if ai_audios else None)
                    if chosen_audio:
                        try:
                            ffmpeg.insert_audio(out_path, chosen_audio, ai_audio_pos,
                                               self.ai_insert.get("audio_fixed_time", 5))
                        except Exception:
                            pass

                if subtitle_text:
                    try: ffmpeg.add_subtitle(out_path, subtitle_text)
                    except: pass
                dm.add_mixed_result(self.task_id, mix_name, out_path, clip_ids)
                dm.update_mix_task_progress(self.task_id, idx+1)
            dm.update_mix_task_progress(self.task_id, total, "done")
            self.progress.emit("混剪完成!", 100)
            self.done.emit(self.task_id)
        except Exception as e:
            import traceback
            dm.update_mix_task_progress(self.task_id, 0, "error")
            self.failed.emit(str(e))


class _AIGenerateWorker(QThread):
    """AI生成视频/音频的工作线程"""
    progress = pyqtSignal(str, int)
    item_done = pyqtSignal(dict)  # 单个完成
    all_done = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, prompts, model_config, gen_type="video", settings=None):
        super().__init__()
        self.prompts = prompts
        self.model_config = model_config
        self.gen_type = gen_type
        self.settings = settings or {}

    def run(self):
        import urllib.request
        import urllib.error
        total = len(self.prompts)
        for idx, prompt in enumerate(self.prompts):
            self.progress.emit(f"生成中 ({idx+1}/{total}): {prompt[:30]}...", int(idx/total*100))
            try:
                result = self._call_api(prompt)
                if result:
                    self.item_done.emit(result)
            except Exception as e:
                self.item_done.emit({"error": str(e), "prompt": prompt})
        self.progress.emit("全部完成!", 100)
        self.all_done.emit()

    def _call_api(self, prompt):
        import urllib.request
        import urllib.error
        import json as _json

        api_url = self.model_config.get("api_url", "").strip()
        api_key = self.model_config.get("api_key", "").strip()
        model_name = self.model_config.get("model", "").strip()

        if not api_url:
            raise ValueError("请先配置API地址")

        # 根据不同类型API构建请求
        provider = self.model_config.get("provider", "")

        if provider in ("openai", "zhipu", "deepseek", "moonshot", "qwen"):
            # OpenAI兼容格式 - 文本生成
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            body = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": "你是一个专业的视频脚本和音频文案创作助手。根据用户的需求生成高质量的视频脚本文案。"},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": self.settings.get("max_tokens", 2000),
                "temperature": self.settings.get("temperature", 0.7)
            }
            req = urllib.request.Request(
                api_url,
                data=_json.dumps(body).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            resp = urllib.request.urlopen(req, timeout=120)
            data = _json.loads(resp.read().decode("utf-8"))
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            # 保存生成结果为文本文件
            ai_dir = dm.AI_DIR
            ai_dir.mkdir(parents=True, exist_ok=True)
            file_id = dm._gen_id()
            if self.gen_type == "video":
                save_path = ai_dir / f"ai_video_{file_id}.txt"
                asset_type = "video"
            else:
                save_path = ai_dir / f"ai_audio_{file_id}.txt"
                asset_type = "audio"

            save_path.write_text(content, encoding="utf-8")

            return {
                "id": file_id,
                "type": asset_type,
                "name": prompt[:50],
                "prompt": prompt,
                "content": content,
                "path": str(save_path),
                "model": model_name,
                "provider": provider
            }

        elif provider == "siliconflow":
            # SiliconFlow API (支持视频/图像生成)
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            body = {
                "model": model_name,
                "prompt": prompt,
            }
            # 添加生成参数
            if self.gen_type == "video":
                body["num_frames"] = self.settings.get("num_frames", 16)
                body["fps"] = self.settings.get("fps", 8)
            body["num_inference_steps"] = self.settings.get("steps", 20)
            body["guidance_scale"] = self.settings.get("guidance", 7.5)

            req = urllib.request.Request(
                api_url,
                data=_json.dumps(body).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            resp = urllib.request.urlopen(req, timeout=300)
            data = _json.loads(resp.read().decode("utf-8"))

            ai_dir = dm.AI_DIR
            ai_dir.mkdir(parents=True, exist_ok=True)
            file_id = dm._gen_id()

            # 检查是否有图片/视频URL
            output_url = data.get("output", data.get("data", [{}]))
            if isinstance(output_url, list) and output_url:
                output_url = output_url[0].get("url", "") if isinstance(output_url[0], dict) else str(output_url[0])
            elif isinstance(output_url, dict):
                output_url = output_url.get("url", "")

            if output_url:
                ext = ".mp4" if self.gen_type == "video" else ".mp3"
                save_path = ai_dir / f"ai_{self.gen_type}_{file_id}{ext}"
                req2 = urllib.request.Request(output_url, headers={"User-Agent": "VideoMatrix/1.0"})
                resp2 = urllib.request.urlopen(req2, timeout=120)
                save_path.write_bytes(resp2.read())
                return {
                    "id": file_id,
                    "type": self.gen_type,
                    "name": prompt[:50],
                    "prompt": prompt,
                    "path": str(save_path),
                    "model": model_name,
                    "provider": provider
                }
            else:
                # 回退为文本保存
                save_path = ai_dir / f"ai_{self.gen_type}_{file_id}.txt"
                save_path.write_text(_json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                return {
                    "id": file_id,
                    "type": self.gen_type,
                    "name": prompt[:50],
                    "prompt": prompt,
                    "content": _json.dumps(data, ensure_ascii=False),
                    "path": str(save_path),
                    "model": model_name,
                    "provider": provider
                }
        else:
            raise ValueError(f"不支持的提供商: {provider}")


# ══════════════════════════════════════════════════════════════
# AI模型配置对话框
# ══════════════════════════════════════════════════════════════

DEFAULT_MODELS = [
    {"name": "智谱清言 (GLM-4)", "provider": "zhipu", "api_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions", "model": "glm-4-flash", "desc": "智谱AI，国产大模型"},
    {"name": "通义千问 (Qwen)", "provider": "qwen", "api_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions", "model": "qwen-turbo", "desc": "阿里云通义千问"},
    {"name": "DeepSeek", "provider": "deepseek", "api_url": "https://api.deepseek.com/v1/chat/completions", "model": "deepseek-chat", "desc": "DeepSeek大模型"},
    {"name": "月之暗面 (Kimi)", "provider": "moonshot", "api_url": "https://api.moonshot.cn/v1/chat/completions", "model": "moonshot-v1-8k", "desc": "Moonshot AI"},
    {"name": "OpenAI GPT", "provider": "openai", "api_url": "https://api.openai.com/v1/chat/completions", "model": "gpt-4o-mini", "desc": "OpenAI GPT系列"},
    {"name": "SiliconFlow (视频生成)", "provider": "siliconflow", "api_url": "https://api.siliconflow.cn/v1/video/submit", "model": "wanai/Wan2.1-T2V-14B", "desc": "硅基流动，支持视频生成"},
]


class AIModelConfigDialog(QDialog):
    """AI模型配置对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI 模型配置")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        self._config = dm.get_ai_config()
        self._init_ui()
        self._load_config()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 预设模型选择
        preset_frame = QFrame()
        preset_frame.setStyleSheet(f"QFrame {{{CARD_STYLE} padding: 12px;}}")
        pf = QVBoxLayout(preset_frame)
        pf.addWidget(QLabel("📋 预设模型（点击快速填充）"))
        preset_grid = QGridLayout()
        preset_grid.setSpacing(6)
        for idx, m in enumerate(DEFAULT_MODELS):
            btn = QPushButton(m["name"])
            btn.setStyleSheet(BTN_DEFAULT)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(m["desc"])
            btn.clicked.connect(lambda _, mm=m: self._apply_preset(mm))
            preset_grid.addWidget(btn, idx // 3, idx % 3)
        pf.addLayout(preset_grid)
        layout.addWidget(preset_frame)

        # API配置表单
        config_group = QGroupBox("API 配置")
        config_group.setStyleSheet(f"QGroupBox {{{CARD_STYLE} font-size:14px; font-weight:600; padding-top:16px; margin-top:8px;}} QGroupBox::title {{subcontrol-origin:margin; left:16px; padding:0 8px;}}")
        form = QFormLayout(config_group)
        form.setSpacing(10)

        self._provider_combo = QComboBox()
        self._provider_combo.addItems(["zhipu", "qwen", "deepseek", "moonshot", "openai", "siliconflow", "custom"])
        self._provider_combo.setStyleSheet(INPUT_STYLE)
        self._provider_combo.currentTextChanged.connect(self._on_provider_changed)
        form.addRow("提供商:", self._provider_combo)

        self._api_url_input = QLineEdit()
        self._api_url_input.setPlaceholderText("API接口地址")
        self._api_url_input.setStyleSheet(INPUT_STYLE)
        self._api_url_input.setMinimumHeight(36)
        form.addRow("API 地址:", self._api_url_input)

        self._api_key_input = QLineEdit()
        self._api_key_input.setPlaceholderText("输入API Key")
        self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_input.setStyleSheet(INPUT_STYLE)
        self._api_key_input.setMinimumHeight(36)
        form.addRow("API Key:", self._api_key_input)

        self._model_input = QLineEdit()
        self._model_input.setPlaceholderText("模型名称，如 glm-4-flash")
        self._model_input.setStyleSheet(INPUT_STYLE)
        self._model_input.setMinimumHeight(36)
        form.addRow("模型名称:", self._model_input)

        layout.addWidget(config_group)

        # 自定义模型添加
        custom_frame = QFrame()
        custom_frame.setStyleSheet(f"QFrame {{{CARD_STYLE} padding: 12px;}}")
        cf_layout = QVBoxLayout(custom_frame)
        cf_layout.setSpacing(8)
        cf_layout.addWidget(QLabel("➕ 自定义添加模型（保存后可在预设中快速选择）"))
        cf_row = QHBoxLayout()
        cf_row.addWidget(QLabel("名称:"))
        self._custom_name = QLineEdit()
        self._custom_name.setPlaceholderText("如: 我的GPT-4")
        self._custom_name.setStyleSheet(INPUT_STYLE)
        self._custom_name.setFixedWidth(140)
        cf_row.addWidget(self._custom_name)
        cf_row.addWidget(QLabel("Provider:"))
        self._custom_provider = QLineEdit()
        self._custom_provider.setPlaceholderText("如: openai")
        self._custom_provider.setStyleSheet(INPUT_STYLE)
        self._custom_provider.setFixedWidth(100)
        cf_row.addWidget(self._custom_provider)
        cf_row.addWidget(QLabel("模型名:"))
        self._custom_model = QLineEdit()
        self._custom_model.setPlaceholderText("如: gpt-4o")
        self._custom_model.setStyleSheet(INPUT_STYLE)
        self._custom_model.setFixedWidth(120)
        cf_row.addWidget(self._custom_model)
        add_custom_btn = QPushButton("添加")
        add_custom_btn.setStyleSheet(BTN_PRIMARY_SM)
        add_custom_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_custom_btn.clicked.connect(self._add_custom_model)
        cf_row.addWidget(add_custom_btn)
        cf_layout.addLayout(cf_row)

        # 已保存的自定义模型列表
        self._custom_model_list = QLabel("")
        self._custom_model_list.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        self._custom_model_list.setWordWrap(True)
        cf_layout.addWidget(self._custom_model_list)
        layout.addWidget(custom_frame)
        self._refresh_custom_models()

        # 生成参数
        param_group = QGroupBox("生成参数")
        param_group.setStyleSheet(f"QGroupBox {{{CARD_STYLE} font-size:14px; font-weight:600; padding-top:16px; margin-top:8px;}} QGroupBox::title {{subcontrol-origin:margin; left:16px; padding:0 8px;}}")
        pl = QFormLayout(param_group)
        pl.setSpacing(10)

        self._temp_spin = QDoubleSpinBox()
        self._temp_spin.setRange(0.0, 2.0)
        self._temp_spin.setValue(0.7)
        self._temp_spin.setSingleStep(0.1)
        self._temp_spin.setStyleSheet(SPINBOX_STYLE)
        pl.addRow("温度 (Temperature):", self._temp_spin)

        self._max_tokens_spin = QSpinBox()
        self._max_tokens_spin.setRange(100, 32000)
        self._max_tokens_spin.setValue(2000)
        self._max_tokens_spin.setStyleSheet(SPINBOX_STYLE)
        pl.addRow("最大Token:", self._max_tokens_spin)

        self._steps_spin = QSpinBox()
        self._steps_spin.setRange(1, 100)
        self._steps_spin.setValue(20)
        self._steps_spin.setStyleSheet(SPINBOX_STYLE)
        pl.addRow("推理步数 (视频生成):", self._steps_spin)

        self._guidance_spin = QDoubleSpinBox()
        self._guidance_spin.setRange(1.0, 20.0)
        self._guidance_spin.setValue(7.5)
        self._guidance_spin.setSingleStep(0.5)
        self._guidance_spin.setStyleSheet(SPINBOX_STYLE)
        pl.addRow("引导系数 (Guidance):", self._guidance_spin)

        layout.addWidget(param_group)

        # 测试按钮
        test_bar = QHBoxLayout()
        test_btn = QPushButton("🔌 测试连接")
        test_btn.setStyleSheet(BTN_PRIMARY)
        test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        test_btn.clicked.connect(self._test_connection)
        test_bar.addWidget(test_btn)
        self._test_result = QLabel("")
        self._test_result.setStyleSheet(f"font-size: 13px;")
        test_bar.addWidget(self._test_result, 1)
        layout.addLayout(test_bar)

        # 确定/取消
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self._on_save)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _apply_preset(self, model):
        idx = self._provider_combo.findText(model["provider"])
        if idx >= 0: self._provider_combo.setCurrentIndex(idx)
        self._api_url_input.setText(model["api_url"])
        self._model_input.setText(model["model"])

    def _on_provider_changed(self, text):
        """提供商切换时的处理"""
        if text == "custom":
            self._api_url_input.setPlaceholderText("输入完整的API接口地址")
            self._model_input.setPlaceholderText("输入模型名称")
        else:
            self._api_url_input.setPlaceholderText("API接口地址")
            self._model_input.setPlaceholderText("模型名称，如 glm-4-flash")

    def _add_custom_model(self):
        """添加自定义模型到预设列表"""
        name = self._custom_name.text().strip()
        provider = self._custom_provider.text().strip()
        model = self._custom_model.text().strip()
        if not name or not provider or not model:
            from ..widgets.toast import Toast
            Toast.warning(self, "请填写完整信息")
            return
        custom_models = dm.get_custom_models()
        custom_models.append({"name": name, "provider": provider, "model": model, "desc": "用户自定义"})
        dm.save_custom_models(custom_models)
        self._custom_name.clear()
        self._custom_provider.clear()
        self._custom_model.clear()
        self._refresh_custom_models()
        from ..widgets.toast import Toast
        Toast.success(self, f"已添加自定义模型: {name}")

    def _refresh_custom_models(self):
        """刷新自定义模型显示"""
        custom_models = dm.get_custom_models()
        if custom_models:
            texts = [f"• {m['name']} ({m['provider']}/{m['model']})" for m in custom_models]
            self._custom_model_list.setText("已添加: " + "  ".join(texts))
        else:
            self._custom_model_list.setText("暂无自定义模型")

    def _load_config(self):
        if not self._config: return
        idx = self._provider_combo.findText(self._config.get("provider", ""))
        if idx >= 0: self._provider_combo.setCurrentIndex(idx)
        self._api_url_input.setText(self._config.get("api_url", ""))
        self._api_key_input.setText(self._config.get("api_key", ""))
        self._model_input.setText(self._config.get("model", ""))
        self._temp_spin.setValue(self._config.get("temperature", 0.7))
        self._max_tokens_spin.setValue(self._config.get("max_tokens", 2000))
        self._steps_spin.setValue(self._config.get("steps", 20))
        self._guidance_spin.setValue(self._config.get("guidance", 7.5))

    def _test_connection(self):
        import urllib.request
        import urllib.error
        import json as _json
        api_url = self._api_url_input.text().strip()
        api_key = self._api_key_input.text().strip()
        model = self._model_input.text().strip()
        provider = self._provider_combo.currentText()

        if not api_url or not api_key:
            self._test_result.setStyleSheet(f"color: {DANGER}; font-size: 13px;")
            self._test_result.setText("❌ 请填写API地址和Key")
            return

        self._test_result.setStyleSheet(f"color: {WARNING}; font-size: 13px;")
        self._test_result.setText("⏳ 测试中...")
        QApplication.processEvents()

        try:
            if provider in ("openai", "zhipu", "deepseek", "moonshot", "qwen"):
                headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
                body = {"model": model, "messages": [{"role": "user", "content": "你好，测试连接"}], "max_tokens": 10}
                req = urllib.request.Request(api_url, data=_json.dumps(body).encode("utf-8"), headers=headers, method="POST")
                resp = urllib.request.urlopen(req, timeout=30)
                data = _json.loads(resp.read().decode("utf-8"))
                if "choices" in data:
                    self._test_result.setStyleSheet(f"color: {SUCCESS}; font-size: 13px;")
                    self._test_result.setText("✅ 连接成功!")
                else:
                    self._test_result.setStyleSheet(f"color: {DANGER}; font-size: 13px;")
                    self._test_result.setText(f"❌ 返回格式异常")
            else:
                # 通用测试
                headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
                req = urllib.request.Request(api_url, headers=headers, method="GET")
                resp = urllib.request.urlopen(req, timeout=15)
                self._test_result.setStyleSheet(f"color: {SUCCESS}; font-size: 13px;")
                self._test_result.setText(f"✅ 服务器可达 (HTTP {resp.status})")
        except urllib.error.HTTPError as e:
            self._test_result.setStyleSheet(f"color: {DANGER}; font-size: 13px;")
            self._test_result.setText(f"❌ HTTP {e.code}: {e.reason}")
        except Exception as e:
            self._test_result.setStyleSheet(f"color: {DANGER}; font-size: 13px;")
            self._test_result.setText(f"❌ 连接失败: {str(e)[:60]}")

    def _on_save(self):
        config = {
            "provider": self._provider_combo.currentText(),
            "api_url": self._api_url_input.text().strip(),
            "api_key": self._api_key_input.text().strip(),
            "model": self._model_input.text().strip(),
            "temperature": self._temp_spin.value(),
            "max_tokens": self._max_tokens_spin.value(),
            "steps": self._steps_spin.value(),
            "guidance": self._guidance_spin.value(),
        }
        dm.save_ai_config(config)
        self._config = config
        self.accept()

    def get_config(self):
        return self._config


# ══════════════════════════════════════════════════════════════
# 文字+音频组合对话框
# ══════════════════════════════════════════════════════════════

class AudioComboDialog(QDialog):
    def __init__(self, parent=None, combos=None):
        super().__init__(parent)
        self.setWindowTitle("文字+音频组合设置")
        self.setMinimumWidth(500)
        self.combos = list(combos) if combos else []
        self._init_ui()
        self._refresh_list()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        info = QLabel("每个组合包含一段文字（字幕）和一个音频文件。混剪时每个视频会随机或按顺序使用一个组合。")
        info.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        info.setWordWrap(True)
        layout.addWidget(info)
        add_frame = QFrame()
        add_frame.setStyleSheet(f"QFrame {{{CARD_STYLE} padding: 12px;}}")
        add_layout = QHBoxLayout(add_frame)
        add_layout.addWidget(QLabel("文字:"))
        self._text_input = QLineEdit()
        self._text_input.setPlaceholderText("字幕文字（可选）")
        self._text_input.setStyleSheet(INPUT_STYLE)
        add_layout.addWidget(self._text_input)
        add_layout.addWidget(QLabel("音频:"))
        self._audio_input = QLineEdit()
        self._audio_input.setPlaceholderText("音频文件路径")
        self._audio_input.setStyleSheet(INPUT_STYLE)
        add_layout.addWidget(self._audio_input)
        browse_btn = QPushButton("浏览")
        browse_btn.setStyleSheet(BTN_DEFAULT)
        browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_btn.clicked.connect(self._browse_audio)
        add_layout.addWidget(browse_btn)
        add_btn = QPushButton("添加")
        add_btn.setStyleSheet(BTN_PRIMARY_SM)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._add_combo)
        add_layout.addWidget(add_btn)
        layout.addWidget(add_frame)
        self._list = QTableWidget()
        self._list.setStyleSheet(TABLE_STYLE)
        self._list.setColumnCount(4)
        self._list.setHorizontalHeaderLabels(["序号", "文字", "音频", "操作"])
        self._list.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._list.verticalHeader().setVisible(False)
        layout.addWidget(self._list, 1)
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _browse_audio(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择音频", "", "音频 (*.mp3 *.wav *.aac *.m4a);;所有 (*)")
        if path: self._audio_input.setText(path)

    def _add_combo(self):
        text = self._text_input.text().strip()
        audio = self._audio_input.text().strip()
        if not text and not audio:
            Toast.warning(self, "请至少填写文字或音频")
            return
        self.combos.append({"text": text, "audio": audio})
        self._text_input.clear()
        self._audio_input.clear()
        self._refresh_list()

    def _refresh_list(self):
        self._list.setRowCount(len(self.combos))
        for i, c in enumerate(self.combos):
            self._list.setItem(i, 0, QTableWidgetItem(str(i+1)))
            self._list.setItem(i, 1, QTableWidgetItem(c.get("text", "")))
            self._list.setItem(i, 2, QTableWidgetItem(os.path.basename(c.get("audio", "")) or "--"))
            del_btn = QPushButton("删除")
            del_btn.setStyleSheet(f"color: {DANGER}; border:none; font-size:11px; padding:0px 4px;")
            del_btn.setFixedHeight(28)
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            idx = i
            del_btn.clicked.connect(lambda _, ii=idx: (self.combos.pop(ii), self._refresh_list()))
            self._list.setCellWidget(i, 3, del_btn)

    def get_combos(self):
        return self.combos


# ══════════════════════════════════════════════════════════════
# 辅助函数
# ══════════════════════════════════════════════════════════════

def _btn(text, color, callback):
    """快速创建操作按钮"""
    btn = QPushButton(text)
    btn.setStyleSheet(f"color: {color}; border: none; font-size: 11px; padding: 0px 4px;")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFixedHeight(28)
    btn.clicked.connect(callback)
    return btn


def _make_btn(text, style, callback):
    """顶部操作按钮"""
    btn = QPushButton(text)
    btn.setStyleSheet(style)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFixedHeight(32)
    btn.setMinimumWidth(50)
    btn.clicked.connect(callback)
    return btn


def _open_folder(path: str):
    if not path or not os.path.exists(path): return
    folder = os.path.dirname(path) if os.path.isfile(path) else path
    if not os.path.isdir(folder): return
    if sys.platform == 'win32': os.startfile(folder)
    elif sys.platform == 'darwin': subprocess.Popen(['open', folder])
    else: subprocess.Popen(['xdg-open', folder])


def _folder_link_widget(path: str):
    if not path: return QLabel("--")
    folder = os.path.dirname(path) if os.path.isfile(path) else path
    label = QLabel(os.path.basename(path) or folder)
    label.setStyleSheet(f"color: {PRIMARY}; font-size: 12px;")
    label.setCursor(Qt.CursorShape.PointingHandCursor)
    label.setToolTip(f"点击打开: {folder}")
    label.mousePressEvent = lambda e: _open_folder(path)
    return label


# ══════════════════════════════════════════════════════════════
# 主界面
# ══════════════════════════════════════════════════════════════

class VideoView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers = []
        self._audio_combos = []
        self._audio_mode = "random"
        self._ai_insert = {
            "video_position": "none",
            "video_fixed_time": 5,
            "audio_position": "none",
            "audio_fixed_time": 5,
        }
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet("""
            QTabWidget::pane { border: none; }
            QTabBar::tab { padding: 10px 20px; font-size: 14px; border: none; border-bottom: 2px solid transparent; color: #999; }
            QTabBar::tab:selected { color: #165DFF; border-bottom: 2px solid #165DFF; }
        """)
        self._tabs.addTab(self._create_library_tab(), "📁 视频库")
        self._tabs.addTab(self._create_cut_tab(), "✂️ 裁切队列")
        self._tabs.addTab(self._create_basket_tab(), "🧺 篮子")
        self._tabs.addTab(self._create_ai_tab(), "🤖 AI制作")
        self._tabs.addTab(self._create_mix_tab(), "🎞️ 混剪队列")
        self._tabs.addTab(self._create_publish_tab(), "📤 待发布库")
        layout.addWidget(self._tabs)

        # 启用视频库的拖放
        self.setAcceptDrops(True)

    def _toggle_all_checkboxes(self, table, logical_index):
        """点击表头第0列时，切换该列所有QCheckBox的状态"""
        if logical_index != 0:
            return
        # 检查当前是否全部选中
        all_checked = True
        for row in range(table.rowCount()):
            cb = table.cellWidget(row, 0)
            if isinstance(cb, QCheckBox) and not cb.isChecked():
                all_checked = False
                break
        # 反转状态
        new_state = not all_checked
        for row in range(table.rowCount()):
            cb = table.cellWidget(row, 0)
            if isinstance(cb, QCheckBox):
                cb.setChecked(new_state)

    # ── 拖放支持 ─────────────────────────────────────────
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            # 检查是否有视频文件
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                ext = os.path.splitext(path)[1].lower()
                if ext in ('.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm'):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        if not event.mimeData().hasUrls():
            return
        video_files = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isfile(path):
                ext = os.path.splitext(path)[1].lower()
                if ext in ('.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm'):
                    video_files.append(path)
        if video_files:
            w = _UploadWorker(video_files)
            w.done.connect(lambda r: (Toast.success(self, f"拖入{len(r['videos'])}个视频"), self._refresh_library()))
            w.failed.connect(lambda m: Toast.error(self, f"导入失败: {m}"))
            self._workers.append(w)
            w.start()
            event.acceptProposedAction()

    # ── 视频库 ─────────────────────────────────────────────
    def _create_library_tab(self):
        tab = QWidget(); layout = QVBoxLayout(tab); layout.setSpacing(12)
        path_bar = QHBoxLayout()
        path_label = QLabel(f"📂 视频文件夹: {dm.LIBRARY_DIR}")
        path_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; padding: 4px 0;")
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path_bar.addWidget(path_label, 1)
        open_btn = QPushButton("打开文件夹")
        open_btn.setStyleSheet(BTN_TEXT)
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.clicked.connect(lambda: _open_folder(str(dm.LIBRARY_DIR)))
        path_bar.addWidget(open_btn)
        layout.addLayout(path_bar)
        bar = QHBoxLayout(); bar.setSpacing(8)
        bar.addWidget(_make_btn("📁 上传视频", BTN_PRIMARY, self._upload_videos))
        self._group_name = QLineEdit(); self._group_name.setPlaceholderText("裁切组名称"); self._group_name.setStyleSheet(INPUT_STYLE); self._group_name.setFixedWidth(130)
        bar.addWidget(self._group_name)
        bar.addWidget(_make_btn("✂️ 添加到裁切队列", BTN_PRIMARY, self._add_to_cut))
        bar.addStretch()
        bar.addWidget(_make_btn("🗑️ 清空全部", BTN_DANGER, self._library_clear_all))
        bar.addWidget(_make_btn("⬇️ FFmpeg", BTN_DEFAULT, self._check_ffmpeg))
        bar.addWidget(_make_btn("🔄 刷新", BTN_DEFAULT, self._refresh_library))
        layout.addLayout(bar)
        self._lib_table = QTableWidget()
        self._lib_table.setStyleSheet(TABLE_STYLE)
        self._lib_table.setColumnCount(8)
        self._lib_table.setHorizontalHeaderLabels(["☑", "文件名", "时长", "大小", "来源", "路径", "时间", "操作"])
        self._lib_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._lib_table.horizontalHeader().setMinimumSectionSize(30)
        self._lib_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._lib_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self._lib_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self._lib_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self._lib_table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        self._lib_table.setColumnWidth(0, 40)
        self._lib_table.setColumnWidth(2, 85)
        self._lib_table.setColumnWidth(3, 85)
        self._lib_table.setColumnWidth(4, 85)
        self._lib_table.setColumnWidth(7, 90)
        self._lib_table.verticalHeader().setVisible(False)
        self._lib_table.verticalHeader().setDefaultSectionSize(42)
        self._lib_table.horizontalHeader().sectionClicked.connect(lambda idx: self._toggle_all_checkboxes(self._lib_table, idx))
        layout.addWidget(self._lib_table, 1)
        return tab

    # ── 裁切队列 ───────────────────────────────────────────
    def _create_cut_tab(self):
        tab = QWidget(); layout = QVBoxLayout(tab); layout.setSpacing(12)
        path_bar = QHBoxLayout()
        path_label = QLabel(f"📂 裁切文件夹: {dm.BASKETS_DIR}")
        path_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; padding: 4px 0;")
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path_bar.addWidget(path_label, 1)
        open_btn = QPushButton("打开文件夹"); open_btn.setStyleSheet(BTN_TEXT)
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.clicked.connect(lambda: _open_folder(str(dm.BASKETS_DIR)))
        path_bar.addWidget(open_btn)
        layout.addLayout(path_bar)
        rule_grp = QGroupBox("裁切规则")
        rule_grp.setStyleSheet(f"QGroupBox {{{CARD_STYLE} font-size:14px; font-weight:600; padding-top:16px; margin-top:8px;}} QGroupBox::title {{subcontrol-origin:margin; left:16px; padding:0 8px;}}")
        rl = QFormLayout(rule_grp); rl.setSpacing(10)
        self._cut_mode = QComboBox(); self._cut_mode.addItems(["按段数", "按时长(秒)"]); self._cut_mode.setStyleSheet(INPUT_STYLE)
        rl.addRow("裁切方式:", self._cut_mode)
        self._cut_val = QSpinBox(); self._cut_val.setRange(1, 9999); self._cut_val.setValue(5); self._cut_val.setStyleSheet(SPINBOX_STYLE)
        rl.addRow("裁切值:", self._cut_val)
        self._mix_seg = QSpinBox(); self._mix_seg.setRange(1, 50); self._mix_seg.setValue(1); self._mix_seg.setStyleSheet(SPINBOX_STYLE)
        rl.addRow("每个混剪取几段:", self._mix_seg)
        layout.addWidget(rule_grp)
        bar = QHBoxLayout(); bar.setSpacing(8)
        bar.addWidget(_make_btn("▶️ 裁切选中", BTN_PRIMARY, self._cut_selected))
        bar.addWidget(_make_btn("▶️ 裁切全部", BTN_DEFAULT, self._cut_all))
        bar.addStretch()
        bar.addWidget(_make_btn("🗑️ 删除选中", BTN_DANGER, self._cut_delete_selected))
        bar.addWidget(_make_btn("🗑️ 清空全部", BTN_DANGER, self._cut_clear_all))
        bar.addWidget(QLabel("  进度:"))
        self._cut_pbar = QProgressBar(); self._cut_pbar.setFixedWidth(180); self._cut_pbar.setFixedHeight(18)
        bar.addWidget(self._cut_pbar)
        layout.addLayout(bar)
        self._cut_table = QTableWidget()
        self._cut_table.setStyleSheet(TABLE_STYLE)
        self._cut_table.setColumnCount(7)
        self._cut_table.setHorizontalHeaderLabels(["☑", "组名", "视频数", "规则", "状态", "进度", "操作"])
        self._cut_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._cut_table.horizontalHeader().setMinimumSectionSize(30)
        self._cut_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._cut_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self._cut_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self._cut_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self._cut_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self._cut_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self._cut_table.setColumnWidth(0, 40)
        self._cut_table.setColumnWidth(2, 85)
        self._cut_table.setColumnWidth(3, 85)
        self._cut_table.setColumnWidth(4, 85)
        self._cut_table.setColumnWidth(5, 85)
        self._cut_table.setColumnWidth(6, 120)
        self._cut_table.verticalHeader().setVisible(False)
        self._cut_table.verticalHeader().setDefaultSectionSize(42)
        self._cut_table.horizontalHeader().sectionClicked.connect(lambda idx: self._toggle_all_checkboxes(self._cut_table, idx))
        layout.addWidget(self._cut_table, 1)
        return tab

    # ── 篮子 ───────────────────────────────────────────────
    def _create_basket_tab(self):
        tab = QWidget(); layout = QVBoxLayout(tab); layout.setSpacing(12)
        path_bar = QHBoxLayout()
        path_label = QLabel(f"📂 篮子文件夹: {dm.BASKETS_DIR}")
        path_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; padding: 4px 0;")
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path_bar.addWidget(path_label, 1)
        open_btn = QPushButton("打开文件夹"); open_btn.setStyleSheet(BTN_TEXT)
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.clicked.connect(lambda: _open_folder(str(dm.BASKETS_DIR)))
        path_bar.addWidget(open_btn)
        layout.addLayout(path_bar)
        bar = QHBoxLayout(); bar.setSpacing(8)
        bar.addWidget(QLabel("篮子:"))
        self._basket_combo = QComboBox(); self._basket_combo.setStyleSheet(INPUT_STYLE); self._basket_combo.setMinimumWidth(200)
        self._basket_combo.currentIndexChanged.connect(self._on_basket_sel)
        bar.addWidget(self._basket_combo)
        bar.addStretch()
        bar.addWidget(_make_btn("🗑️ 删除选中片段", BTN_DANGER, self._basket_delete_selected))
        bar.addWidget(_make_btn("🗑️ 清空当前篮子", BTN_DANGER, self._basket_clear))
        self._basket_status = QLabel(""); self._basket_status.setStyleSheet(f"color:{TEXT_SECONDARY};")
        bar.addWidget(self._basket_status)
        layout.addLayout(bar)
        self._basket_table = QTableWidget()
        self._basket_table.setStyleSheet(TABLE_STYLE)
        self._basket_table.setColumnCount(6)
        self._basket_table.setHorizontalHeaderLabels(["☑", "来源", "片段", "时长", "路径", "ID"])
        self._basket_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._basket_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._basket_table.setColumnWidth(0, 40)
        self._basket_table.verticalHeader().setVisible(False)
        self._basket_table.verticalHeader().setDefaultSectionSize(42)
        self._basket_table.horizontalHeader().sectionClicked.connect(lambda idx: self._toggle_all_checkboxes(self._basket_table, idx))
        layout.addWidget(self._basket_table, 1)
        return tab

    # ── AI制作 ─────────────────────────────────────────────
    def _create_ai_tab(self):
        tab = QWidget(); layout = QVBoxLayout(tab); layout.setSpacing(12)

        # 文件夹路径
        path_bar = QHBoxLayout()
        path_label = QLabel(f"📂 AI素材文件夹: {dm.AI_DIR}")
        path_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; padding: 4px 0;")
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path_bar.addWidget(path_label, 1)
        open_btn = QPushButton("打开文件夹"); open_btn.setStyleSheet(BTN_TEXT)
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.clicked.connect(lambda: _open_folder(str(dm.AI_DIR)))
        path_bar.addWidget(open_btn)
        layout.addLayout(path_bar)

        # 模型配置区
        model_frame = QFrame()
        model_frame.setStyleSheet(f"QFrame {{{CARD_STYLE} padding: 12px;}}")
        mf = QHBoxLayout(model_frame)
        mf.addWidget(QLabel("🤖 AI模型:"))
        self._ai_model_label = QLabel("未配置")
        self._ai_model_label.setStyleSheet(f"color: {WARNING}; font-size: 13px;")
        mf.addWidget(self._ai_model_label)
        mf.addStretch()
        config_btn = QPushButton("⚙️ 模型配置")
        config_btn.setStyleSheet(BTN_DEFAULT)
        config_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        config_btn.clicked.connect(self._open_ai_config)
        mf.addWidget(config_btn)
        layout.addWidget(model_frame)

        # 生成类型和提示词输入
        input_frame = QFrame()
        input_frame.setStyleSheet(f"QFrame {{{CARD_STYLE} padding: 12px;}}")
        il = QVBoxLayout(input_frame)
        il.setSpacing(8)

        type_bar = QHBoxLayout()
        type_bar.addWidget(QLabel("生成类型:"))
        self._ai_gen_type = QComboBox()
        self._ai_gen_type.addItems(["视频脚本/文案", "音频文案/旁白"])
        self._ai_gen_type.setStyleSheet(INPUT_STYLE)
        self._ai_gen_type.setFixedWidth(160)
        type_bar.addWidget(self._ai_gen_type)
        type_bar.addStretch()
        il.addLayout(type_bar)

        il.addWidget(QLabel("提示词（每行一个，可同时生成多个）:"))
        self._ai_prompt_input = QTextEdit()
        self._ai_prompt_input.setPlaceholderText("输入提示词，每行一个\n例如：\n一段产品展示的开场白，30秒左右\n一段科技感十足的产品介绍片尾\n一段温馨的感谢语旁白")
        self._ai_prompt_input.setStyleSheet(f"""
            QTextEdit {{
                border: 1px solid {BORDER_COLOR};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
                color: {TEXT_COLOR};
                background: white;
            }}
            QTextEdit:focus {{ border-color: {PRIMARY}; }}
        """)
        self._ai_prompt_input.setMinimumHeight(100)
        il.addWidget(self._ai_prompt_input)

        gen_bar = QHBoxLayout()
        gen_bar.addStretch()
        self._ai_gen_btn = QPushButton("🚀 开始生成")
        self._ai_gen_btn.setStyleSheet(BTN_PRIMARY)
        self._ai_gen_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ai_gen_btn.clicked.connect(self._start_ai_generate)
        gen_bar.addWidget(self._ai_gen_btn)
        il.addLayout(gen_bar)
        layout.addWidget(input_frame)

        # 进度
        self._ai_progress_bar = QProgressBar()
        self._ai_progress_bar.setFixedHeight(8)
        self._ai_progress_bar.setRange(0, 100)
        self._ai_progress_bar.setValue(0)
        layout.addWidget(self._ai_progress_bar)
        self._ai_progress_label = QLabel("就绪")
        self._ai_progress_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        layout.addWidget(self._ai_progress_label)

        # 操作栏
        bar = QHBoxLayout(); bar.setSpacing(8)
        bar.addWidget(_make_btn("🔄 刷新", BTN_DEFAULT, self._refresh_ai_assets))
        bar.addStretch()
        bar.addWidget(_make_btn("🗑️ 删除选中", BTN_DANGER, self._ai_delete_selected))
        bar.addWidget(_make_btn("🗑️ 清空全部", BTN_DANGER, self._ai_clear_all))
        layout.addLayout(bar)

        # AI素材列表
        self._ai_table = QTableWidget()
        self._ai_table.setStyleSheet(TABLE_STYLE)
        self._ai_table.setColumnCount(7)
        self._ai_table.setHorizontalHeaderLabels(["☑", "名称", "类型", "模型", "提示词", "路径", "操作"])
        self._ai_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._ai_table.horizontalHeader().setMinimumSectionSize(30)
        self._ai_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._ai_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self._ai_table.setColumnWidth(0, 40)
        self._ai_table.setColumnWidth(6, 90)
        self._ai_table.verticalHeader().setVisible(False)
        self._ai_table.verticalHeader().setDefaultSectionSize(42)
        self._ai_table.horizontalHeader().sectionClicked.connect(lambda idx: self._toggle_all_checkboxes(self._ai_table, idx))
        layout.addWidget(self._ai_table, 1)
        return tab

    # ── 混剪队列 ───────────────────────────────────────────
    def _create_mix_tab(self):
        tab = QWidget(); layout = QVBoxLayout(tab); layout.setSpacing(12)

        # 文件夹路径
        path_bar = QHBoxLayout()
        path_label = QLabel(f"📂 混剪输出文件夹: {dm.MIXED_DIR}")
        path_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; padding: 4px 0;")
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path_bar.addWidget(path_label, 1)
        open_btn = QPushButton("打开文件夹"); open_btn.setStyleSheet(BTN_TEXT)
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.clicked.connect(lambda: _open_folder(str(dm.MIXED_DIR)))
        path_bar.addWidget(open_btn)
        layout.addLayout(path_bar)

        # 文字+音频设置
        audio_frame = QFrame()
        audio_frame.setStyleSheet(f"QFrame {{{CARD_STYLE} padding: 12px;}}")
        al = QHBoxLayout(audio_frame)
        al.addWidget(QLabel("🎵 文字+音频:"))
        self._audio_mode_combo = QComboBox()
        self._audio_mode_combo.addItems(["随机分配", "按顺序分配"])
        self._audio_mode_combo.setStyleSheet(INPUT_STYLE)
        self._audio_mode_combo.setFixedWidth(120)
        al.addWidget(self._audio_mode_combo)
        edit_audio_btn = QPushButton("编辑组合")
        edit_audio_btn.setStyleSheet(BTN_DEFAULT)
        edit_audio_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_audio_btn.clicked.connect(self._edit_audio_combos)
        al.addWidget(edit_audio_btn)
        self._audio_count_label = QLabel("0个组合")
        self._audio_count_label.setStyleSheet(f"color:{TEXT_SECONDARY};")
        al.addWidget(self._audio_count_label)
        al.addStretch()
        layout.addWidget(audio_frame)

        # AI素材插入设置
        ai_insert_frame = QFrame()
        ai_insert_frame.setStyleSheet(f"QFrame {{{CARD_STYLE} padding: 12px;}}")
        ail = QVBoxLayout(ai_insert_frame)
        ail.setSpacing(8)
        ail.addWidget(QLabel("🤖 AI素材插入设置"))

        # 视频插入
        vid_row = QHBoxLayout()
        vid_row.addWidget(QLabel("AI视频插入位置:"))
        self._ai_video_pos = QComboBox()
        self._ai_video_pos.addItems(["不插入", "片头", "片尾", "随机位置", "固定时间点"])
        self._ai_video_pos.setStyleSheet(INPUT_STYLE)
        self._ai_video_pos.setFixedWidth(140)
        self._ai_video_pos.currentIndexChanged.connect(self._on_ai_video_pos_changed)
        vid_row.addWidget(self._ai_video_pos)
        vid_row.addWidget(QLabel("固定时间(秒):"))
        self._ai_video_time = QSpinBox()
        self._ai_video_time.setRange(1, 300)
        self._ai_video_time.setValue(5)
        self._ai_video_time.setStyleSheet(SPINBOX_STYLE)
        self._ai_video_time.setFixedWidth(80)
        self._ai_video_time.setEnabled(False)
        vid_row.addWidget(self._ai_video_time)
        # 选择素材按钮
        self._ai_video_sel_btn = QPushButton("选择素材")
        self._ai_video_sel_btn.setStyleSheet(BTN_DEFAULT)
        self._ai_video_sel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ai_video_sel_btn.setFixedWidth(90)
        self._ai_video_sel_btn.clicked.connect(lambda: self._pick_ai_asset("video"))
        vid_row.addWidget(self._ai_video_sel_btn)
        self._ai_video_sel_label = QLabel("随机选择")
        self._ai_video_sel_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        vid_row.addWidget(self._ai_video_sel_label)
        vid_row.addStretch()
        ail.addLayout(vid_row)

        # 音频插入
        aud_row = QHBoxLayout()
        aud_row.addWidget(QLabel("AI音频插入位置:"))
        self._ai_audio_pos = QComboBox()
        self._ai_audio_pos.addItems(["不插入", "片头", "片尾", "随机位置", "固定时间点"])
        self._ai_audio_pos.setStyleSheet(INPUT_STYLE)
        self._ai_audio_pos.setFixedWidth(140)
        self._ai_audio_pos.currentIndexChanged.connect(self._on_ai_audio_pos_changed)
        aud_row.addWidget(self._ai_audio_pos)
        aud_row.addWidget(QLabel("固定时间(秒):"))
        self._ai_audio_time = QSpinBox()
        self._ai_audio_time.setRange(1, 300)
        self._ai_audio_time.setValue(5)
        self._ai_audio_time.setStyleSheet(SPINBOX_STYLE)
        self._ai_audio_time.setFixedWidth(80)
        self._ai_audio_time.setEnabled(False)
        aud_row.addWidget(self._ai_audio_time)
        # 选择素材按钮
        self._ai_audio_sel_btn = QPushButton("选择素材")
        self._ai_audio_sel_btn.setStyleSheet(BTN_DEFAULT)
        self._ai_audio_sel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ai_audio_sel_btn.setFixedWidth(90)
        self._ai_audio_sel_btn.clicked.connect(lambda: self._pick_ai_asset("audio"))
        aud_row.addWidget(self._ai_audio_sel_btn)
        self._ai_audio_sel_label = QLabel("随机选择")
        self._ai_audio_sel_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        aud_row.addWidget(self._ai_audio_sel_label)
        aud_row.addStretch()
        ail.addLayout(aud_row)

        layout.addWidget(ai_insert_frame)

        # 操作栏
        bar = QHBoxLayout(); bar.setSpacing(8)
        bar.addWidget(_make_btn("▶️ 开始混剪", BTN_PRIMARY, self._mix_selected))
        bar.addStretch()
        bar.addWidget(_make_btn("🗑️ 删除选中", BTN_DANGER, self._mix_delete_selected))
        bar.addWidget(_make_btn("🗑️ 清空全部", BTN_DANGER, self._mix_clear_all))
        bar.addWidget(QLabel("  进度:"))
        self._mix_pbar = QProgressBar(); self._mix_pbar.setFixedWidth(180); self._mix_pbar.setFixedHeight(18)
        bar.addWidget(self._mix_pbar)
        layout.addLayout(bar)

        self._mix_table = QTableWidget()
        self._mix_table.setStyleSheet(TABLE_STYLE)
        self._mix_table.setColumnCount(7)
        self._mix_table.setHorizontalHeaderLabels(["☑", "篮子", "取几段", "组合数", "已完成", "状态", "操作"])
        self._mix_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._mix_table.horizontalHeader().setMinimumSectionSize(30)
        self._mix_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._mix_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self._mix_table.setColumnWidth(0, 40)
        self._mix_table.setColumnWidth(6, 150)
        self._mix_table.verticalHeader().setVisible(False)
        self._mix_table.verticalHeader().setDefaultSectionSize(42)
        self._mix_table.horizontalHeader().sectionClicked.connect(lambda idx: self._toggle_all_checkboxes(self._mix_table, idx))
        layout.addWidget(self._mix_table, 1)
        return tab

    # ── 待发布库 ───────────────────────────────────────────
    def _create_publish_tab(self):
        tab = QWidget(); layout = QVBoxLayout(tab); layout.setSpacing(12)
        path_bar = QHBoxLayout()
        path_label = QLabel(f"📂 待发布文件夹: {dm.PUBLISH_DIR}")
        path_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; padding: 4px 0;")
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path_bar.addWidget(path_label, 1)
        open_btn = QPushButton("打开文件夹"); open_btn.setStyleSheet(BTN_TEXT)
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.clicked.connect(lambda: _open_folder(str(dm.PUBLISH_DIR)))
        path_bar.addWidget(open_btn)
        layout.addLayout(path_bar)
        info = QLabel("💡 混剪完成的视频导出后会出现在这里，后续将根据发布调度规则自动发布到各大视频平台。")
        info.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; padding: 4px 0;")
        info.setWordWrap(True)
        layout.addWidget(info)
        bar = QHBoxLayout(); bar.setSpacing(8)
        bar.addWidget(_make_btn("🔄 刷新", BTN_DEFAULT, self._refresh_publish))
        bar.addStretch()
        bar.addWidget(_make_btn("🗑️ 删除选中", BTN_DANGER, self._publish_delete_selected))
        bar.addWidget(_make_btn("🗑️ 清空全部", BTN_DANGER, self._publish_clear_all))
        layout.addLayout(bar)
        self._pub_table = QTableWidget()
        self._pub_table.setStyleSheet(TABLE_STYLE)
        self._pub_table.setColumnCount(8)
        self._pub_table.setHorizontalHeaderLabels(["☑", "文件名", "大小", "来源", "路径", "发布时间", "状态", "操作"])
        self._pub_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._pub_table.horizontalHeader().setMinimumSectionSize(30)
        self._pub_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._pub_table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        self._pub_table.setColumnWidth(0, 40)
        self._pub_table.setColumnWidth(7, 90)
        self._pub_table.verticalHeader().setVisible(False)
        self._pub_table.verticalHeader().setDefaultSectionSize(42)
        self._pub_table.horizontalHeader().sectionClicked.connect(lambda idx: self._toggle_all_checkboxes(self._pub_table, idx))
        layout.addWidget(self._pub_table, 1)
        return tab

    # ══════════════════════════════════════════════════════════
    # 数据刷新
    # ══════════════════════════════════════════════════════════

    def load_data(self):
        self._refresh_library(); self._refresh_cut(); self._refresh_baskets()
        self._refresh_ai_assets(); self._refresh_mix(); self._refresh_publish()
        self._update_ai_model_label()

    def _refresh_library(self):
        videos = dm.get_videos()
        self._lib_table.setRowCount(len(videos))
        for i, v in enumerate(videos):
            self._lib_table.setCellWidget(i, 0, QCheckBox())
            self._lib_table.setItem(i, 1, QTableWidgetItem(v["name"]))
            d = v.get("duration", 0)
            self._lib_table.setItem(i, 2, QTableWidgetItem(f"{int(d//60)}:{int(d%60):02d}" if d else "--"))
            s = v.get("size", 0)
            self._lib_table.setItem(i, 3, QTableWidgetItem(f"{s/1048576:.1f}MB" if s else "--"))
            self._lib_table.setItem(i, 4, QTableWidgetItem("上传" if v.get("source")=="upload" else "混剪"))
            self._lib_table.setCellWidget(i, 5, _folder_link_widget(v.get("path", "")))
            self._lib_table.setItem(i, 6, QTableWidgetItem(v.get("added_at", "")))
            vid = v["id"]
            self._lib_table.setCellWidget(i, 7, _btn("删除", DANGER, lambda _, vv=vid: self._del_video(vv)))

    def _refresh_cut(self):
        groups = dm.get_cut_groups()
        self._cut_table.setRowCount(len(groups))
        for i, g in enumerate(groups):
            self._cut_table.setCellWidget(i, 0, QCheckBox())
            self._cut_table.setItem(i, 1, QTableWidgetItem(g["name"]))
            self._cut_table.setItem(i, 2, QTableWidgetItem(str(g.get("video_count", 0))))
            r = g.get("cut_rule", {})
            self._cut_table.setItem(i, 3, QTableWidgetItem(f"{'段数' if r.get('mode')=='segments' else '时长'}:{r.get('value',0)}"))
            sm = {"pending":"待裁切","cutting":"裁切中","done":"已完成","error":"错误"}
            si = QTableWidgetItem(sm.get(g.get("status",""), ""))
            if g.get("status")=="done": si.setForeground(QColor(SUCCESS))
            elif g.get("status")=="cutting": si.setForeground(QColor(WARNING))
            elif g.get("status")=="error": si.setForeground(QColor(DANGER))
            self._cut_table.setItem(i, 4, si)
            self._cut_table.setItem(i, 5, QTableWidgetItem(f"{g.get('progress',0)}%"))
            ow = QWidget(); ow.setMinimumWidth(110)
            ow.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            ol = QHBoxLayout(ow); ol.setContentsMargins(4, 4, 4, 4); ol.setSpacing(6)
            gid = g["id"]
            if g.get("status") == "pending":
                ol.addWidget(_btn("裁切", PRIMARY, lambda _, gg=gid: self._cut_one(gg)))
            ol.addWidget(_btn("删除", DANGER, lambda _, gg=gid: self._del_cut(gg)))
            ol.addStretch()
            self._cut_table.setCellWidget(i, 6, ow)

    def _refresh_baskets(self):
        self._basket_combo.clear()
        for b in dm.get_baskets():
            cnt = len(b.get("clips", []))
            self._basket_combo.addItem(f"{b['name']} ({cnt}片段)", b["id"])

    def _on_basket_sel(self, idx):
        bid = self._basket_combo.currentData()
        if not bid: self._basket_table.setRowCount(0); self._basket_status.setText(""); return
        basket = dm.get_basket(bid)
        if not basket: return
        sm = {"empty":"空","ready":"就绪","mixing":"混剪中","done":"完成"}
        self._basket_status.setText(f"状态: {sm.get(basket.get('status',''), '')}")
        clips = basket.get("clips", [])
        self._basket_table.setRowCount(len(clips))
        for i, c in enumerate(clips):
            self._basket_table.setCellWidget(i, 0, QCheckBox())
            self._basket_table.setItem(i, 1, QTableWidgetItem(c.get("source_video","")))
            self._basket_table.setItem(i, 2, QTableWidgetItem(str(c.get("segment_index",0))))
            d = c.get("duration", 0)
            self._basket_table.setItem(i, 3, QTableWidgetItem(f"{int(d//60)}:{int(d%60):02d}" if d else "--"))
            self._basket_table.setCellWidget(i, 4, _folder_link_widget(c.get("path", "")))
            self._basket_table.setItem(i, 5, QTableWidgetItem(c.get("id","")))

    def _refresh_ai_assets(self):
        assets = dm.get_ai_assets()
        self._ai_table.setRowCount(len(assets))
        type_map = {"video": "视频", "audio": "音频"}
        for i, a in enumerate(assets):
            self._ai_table.setCellWidget(i, 0, QCheckBox())
            self._ai_table.setItem(i, 1, QTableWidgetItem(a.get("name", "")[:40]))
            self._ai_table.setItem(i, 2, QTableWidgetItem(type_map.get(a.get("type", ""), a.get("type", ""))))
            self._ai_table.setItem(i, 3, QTableWidgetItem(a.get("model", "")))
            self._ai_table.setItem(i, 4, QTableWidgetItem(a.get("prompt", "")[:50]))
            self._ai_table.setCellWidget(i, 5, _folder_link_widget(a.get("path", "")))
            aid = a["id"]
            self._ai_table.setCellWidget(i, 6, _btn("删除", DANGER, lambda _, aa=aid: self._del_ai_asset(aa)))

    def _refresh_mix(self):
        tasks = dm.get_mix_tasks()
        self._mix_table.setRowCount(len(tasks))
        for i, t in enumerate(tasks):
            self._mix_table.setCellWidget(i, 0, QCheckBox())
            basket = dm.get_basket(t.get("basket_id",""))
            self._mix_table.setItem(i, 1, QTableWidgetItem(basket["name"] if basket else "--"))
            self._mix_table.setItem(i, 2, QTableWidgetItem(str(t.get("segments_per_video",1))))
            self._mix_table.setItem(i, 3, QTableWidgetItem(str(t.get("total",0))))
            self._mix_table.setItem(i, 4, QTableWidgetItem(str(t.get("completed",0))))
            sm = {"pending":"待处理","running":"混剪中","done":"已完成","error":"错误"}
            si = QTableWidgetItem(sm.get(t.get("status",""), ""))
            if t.get("status")=="done": si.setForeground(QColor(SUCCESS))
            elif t.get("status")=="running": si.setForeground(QColor(WARNING))
            elif t.get("status")=="error": si.setForeground(QColor(DANGER))
            self._mix_table.setItem(i, 5, si)
            tid = t["id"]
            ow = QWidget(); ow.setMinimumWidth(140)
            ow.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            ol = QHBoxLayout(ow); ol.setContentsMargins(4, 4, 4, 4); ol.setSpacing(6)
            if t.get("status") == "pending":
                ol.addWidget(_btn("混剪", PRIMARY, lambda _, tt=tid: self._mix_one(tt)))
            if t.get("status") == "done":
                exported_count = dm.get_mixed_exported_count(tid)
                if exported_count > 0:
                    already_label = QLabel(f"已导出{exported_count}个")
                    already_label.setStyleSheet(f"color: {SUCCESS}; font-size: 12px;")
                    ol.addWidget(already_label)
                else:
                    ol.addWidget(_btn("导出", SUCCESS, lambda _, tt=tid: self._export_mix(tt)))
            ol.addWidget(_btn("删除", DANGER, lambda _, tt=tid: self._del_mix(tt)))
            ol.addStretch()
            self._mix_table.setCellWidget(i, 6, ow)

    def _refresh_publish(self):
        videos = dm.get_pending_videos()
        self._pub_table.setRowCount(len(videos))
        status_map = {"pending": "待发布", "scheduled": "已排期", "published": "已发布"}
        for i, v in enumerate(videos):
            self._pub_table.setCellWidget(i, 0, QCheckBox())
            self._pub_table.setItem(i, 1, QTableWidgetItem(v.get("name", "")))
            s = v.get("size", 0)
            self._pub_table.setItem(i, 2, QTableWidgetItem(f"{s/1048576:.1f}MB" if s else "--"))
            self._pub_table.setItem(i, 3, QTableWidgetItem("混剪" if v.get("source") == "mixed" else "上传"))
            self._pub_table.setCellWidget(i, 4, _folder_link_widget(v.get("path", "")))
            self._pub_table.setItem(i, 5, QTableWidgetItem(v.get("added_at", "")))
            ps = v.get("publish_status", "pending")
            si = QTableWidgetItem(status_map.get(ps, ps))
            if ps == "published": si.setForeground(QColor(SUCCESS))
            elif ps == "scheduled": si.setForeground(QColor(WARNING))
            else: si.setForeground(QColor(PRIMARY))
            self._pub_table.setItem(i, 6, si)
            vid = v["id"]
            self._pub_table.setCellWidget(i, 7, _btn("删除", DANGER, lambda _, vv=vid: self._del_pending(vv)))

    # ══════════════════════════════════════════════════════════
    # AI制作操作
    # ══════════════════════════════════════════════════════════

    def _update_ai_model_label(self):
        config = dm.get_ai_config()
        if config and config.get("model"):
            self._ai_model_label.setText(f"{config.get('provider','')}/{config.get('model','')}")
            self._ai_model_label.setStyleSheet(f"color: {SUCCESS}; font-size: 13px;")
        else:
            self._ai_model_label.setText("未配置（点击右侧⚙️配置）")
            self._ai_model_label.setStyleSheet(f"color: {WARNING}; font-size: 13px;")

    def _open_ai_config(self):
        dlg = AIModelConfigDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._update_ai_model_label()

    def _start_ai_generate(self):
        prompt_text = self._ai_prompt_input.toPlainText().strip()
        if not prompt_text:
            Toast.warning(self, "请输入提示词")
            return
        prompts = [p.strip() for p in prompt_text.split("\n") if p.strip()]
        if not prompts:
            Toast.warning(self, "请输入有效的提示词")
            return
        config = dm.get_ai_config()
        if not config or not config.get("api_key"):
            Toast.warning(self, "请先配置AI模型（点击⚙️模型配置）")
            return
        gen_type = "video" if self._ai_gen_type.currentIndex() == 0 else "audio"
        self._ai_gen_btn.setEnabled(False)
        self._ai_gen_btn.setText("⏳ 生成中...")
        settings = {
            "temperature": config.get("temperature", 0.7),
            "max_tokens": config.get("max_tokens", 2000),
            "steps": config.get("steps", 20),
            "guidance": config.get("guidance", 7.5),
        }
        w = _AIGenerateWorker(prompts, config, gen_type, settings)
        w.progress.connect(self._on_ai_progress)
        w.item_done.connect(self._on_ai_item_done)
        w.all_done.connect(self._on_ai_all_done)
        w.failed.connect(lambda m: Toast.error(self, f"生成失败: {m}"))
        self._workers.append(w); w.start()

    def _on_ai_progress(self, msg, val):
        self._ai_progress_label.setText(msg)
        self._ai_progress_bar.setValue(val)

    def _on_ai_item_done(self, result):
        if result.get("error"):
            Toast.warning(self, f"生成失败: {result['error'][:50]}")
            return
        dm.add_ai_asset(result)
        self._refresh_ai_assets()

    def _on_ai_all_done(self):
        self._ai_gen_btn.setEnabled(True)
        self._ai_gen_btn.setText("🚀 开始生成")
        Toast.success(self, "AI生成完成!")
        self._ai_progress_label.setText("全部完成 ✅")

    def _del_ai_asset(self, aid):
        if QMessageBox.question(self, "确认", "删除此AI素材？") == QMessageBox.StandardButton.Yes:
            dm.delete_ai_asset(aid); self._refresh_ai_assets()

    def _ai_delete_selected(self):
        ids = []
        for i in range(self._ai_table.rowCount()):
            cb = self._ai_table.cellWidget(i, 0)
            if cb and cb.isChecked():
                assets = dm.get_ai_assets()
                if i < len(assets): ids.append(assets[i]["id"])
        if not ids: Toast.warning(self, "请勾选"); return
        if QMessageBox.question(self, "确认", f"删除{len(ids)}个素材？") == QMessageBox.StandardButton.Yes:
            for aid in ids: dm.delete_ai_asset(aid)
            self._refresh_ai_assets(); Toast.success(self, f"已删除{len(ids)}个素材")

    def _ai_clear_all(self):
        assets = dm.get_ai_assets()
        if not assets: return
        if QMessageBox.question(self, "确认", f"清空全部{len(assets)}个AI素材？") == QMessageBox.StandardButton.Yes:
            dm.clear_ai_assets()
            self._refresh_ai_assets(); Toast.success(self, "已清空AI素材")

    # ══════════════════════════════════════════════════════════
    # 混剪AI插入设置
    # ══════════════════════════════════════════════════════════

    def _on_ai_video_pos_changed(self, idx):
        pos_map = {0: "none", 1: "head", 2: "tail", 3: "random", 4: "fixed"}
        self._ai_insert["video_position"] = pos_map.get(idx, "none")
        self._ai_video_time.setEnabled(idx == 4)

    def _on_ai_audio_pos_changed(self, idx):
        pos_map = {0: "none", 1: "head", 2: "tail", 3: "random", 4: "fixed"}
        self._ai_insert["audio_position"] = pos_map.get(idx, "none")
        self._ai_audio_time.setEnabled(idx == 4)

    def _pick_ai_asset(self, asset_type):
        """选择AI素材 - 弹出选择对话框"""
        assets = [a for a in dm.get_ai_assets() if a.get("type") == asset_type]
        if not assets:
            Toast.warning(self, f"暂无AI{'视频' if asset_type == 'video' else '音频'}素材，请先在AI制作中生成")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(f"选择AI{'视频' if asset_type == 'video' else '音频'}素材")
        dlg.setMinimumWidth(500)
        dlg.setMinimumHeight(400)
        dl = QVBoxLayout(dlg)

        # 随机选择选项
        random_cb = QCheckBox("🎲 随机选择（每次混剪随机挑选一个素材）")
        random_cb.setChecked(True)
        random_cb.setStyleSheet(f"font-size: 13px; padding: 8px;")
        dl.addWidget(random_cb)

        dl.addWidget(QLabel("或手动指定素材:"))

        # 素材列表
        list_widget = QTableWidget()
        list_widget.setStyleSheet(TABLE_STYLE)
        list_widget.setColumnCount(4)
        list_widget.setHorizontalHeaderLabels(["选择", "名称", "提示词", "路径"])
        list_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        list_widget.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        list_widget.setColumnWidth(0, 50)
        list_widget.verticalHeader().setVisible(False)
        list_widget.setRowCount(len(assets))
        for i, a in enumerate(assets):
            rb = QCheckBox()
            rb.setEnabled(False)
            list_widget.setCellWidget(i, 0, rb)
            list_widget.setItem(i, 1, QTableWidgetItem(a.get("name", "")[:30]))
            list_widget.setItem(i, 2, QTableWidgetItem(a.get("prompt", "")[:40]))
            list_widget.setItem(i, 3, QTableWidgetItem(os.path.basename(a.get("path", ""))))
        dl.addWidget(list_widget, 1)

        def _on_random_toggled(checked):
            for i in range(list_widget.rowCount()):
                cb = list_widget.cellWidget(i, 0)
                if cb: cb.setEnabled(not checked); cb.setChecked(False)
        random_cb.toggled.connect(_on_random_toggled)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(dlg.accept)
        btn_box.rejected.connect(dlg.reject)
        dl.addWidget(btn_box)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            if asset_type == "video":
                if random_cb.isChecked():
                    self._ai_insert["video_asset"] = "random"
                    self._ai_video_sel_label.setText("🎲 随机选择")
                else:
                    for i in range(list_widget.rowCount()):
                        cb = list_widget.cellWidget(i, 0)
                        if cb and cb.isChecked():
                            self._ai_insert["video_asset"] = assets[i]["id"]
                            self._ai_video_sel_label.setText(f"📌 {assets[i].get('name','')[:15]}")
                            break
                    else:
                        self._ai_insert["video_asset"] = "random"
                        self._ai_video_sel_label.setText("🎲 随机选择")
            else:
                if random_cb.isChecked():
                    self._ai_insert["audio_asset"] = "random"
                    self._ai_audio_sel_label.setText("🎲 随机选择")
                else:
                    for i in range(list_widget.rowCount()):
                        cb = list_widget.cellWidget(i, 0)
                        if cb and cb.isChecked():
                            self._ai_insert["audio_asset"] = assets[i]["id"]
                            self._ai_audio_sel_label.setText(f"📌 {assets[i].get('name','')[:15]}")
                            break
                    else:
                        self._ai_insert["audio_asset"] = "random"
                        self._ai_audio_sel_label.setText("🎲 随机选择")

    # ══════════════════════════════════════════════════════════
    # 视频库操作
    # ══════════════════════════════════════════════════════════

    def _upload_videos(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择视频", "", "视频 (*.mp4 *.avi *.mov *.mkv *.flv);;所有 (*)")
        if not files: return
        w = _UploadWorker(files)
        w.done.connect(lambda r: (Toast.success(self, f"上传{len(r['videos'])}个视频"), self._refresh_library()))
        w.failed.connect(lambda m: Toast.error(self, f"上传失败: {m}"))
        self._workers.append(w); w.start()

    def _del_video(self, vid):
        if QMessageBox.question(self, "确认", "删除此视频？") == QMessageBox.StandardButton.Yes:
            dm.delete_video(vid); self._refresh_library()

    def _check_ffmpeg(self):
        """检查FFmpeg状态，未安装则下载"""
        from .. import ffmpeg as ff
        if ff.is_ffmpeg_available():
            Toast.success(self, "✅ FFmpeg 已安装，无需重复安装")
            return
        # 未安装，弹窗确认后下载
        reply = QMessageBox.question(
            self, "FFmpeg 未安装",
            "检测到系统未安装 FFmpeg，视频裁切功能需要 FFmpeg 支持。\n\n是否自动下载安装？（约30MB）",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        # 创建进度对话框
        progress = QProgressBar(self)
        progress.setRange(0, 100)
        progress.setFixedWidth(300)
        progress.move(self.width() // 2 - 150, self.height() // 2 - 10)
        progress.show()
        status_label = QLabel("正在下载 FFmpeg...", self)
        status_label.move(self.width() // 2 - 100, self.height() // 2 + 10)
        status_label.show()
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()
        def _on_progress(percent, msg):
            progress.setValue(percent)
            status_label.setText(msg)
            QApplication.processEvents()
        ok = ff.download_ffmpeg(progress_callback=_on_progress)
        progress.hide()
        status_label.hide()
        if ok:
            ff._ffmpeg_path = None
            ff._ffprobe_path = None
            if ff.is_ffmpeg_available():
                Toast.success(self, "✅ FFmpeg 安装成功!")
            else:
                Toast.error(self, "FFmpeg 安装后仍无法使用，请手动安装")
        else:
            Toast.error(self, "FFmpeg 下载失败，请检查网络或手动安装")

    def _library_clear_all(self):
        videos = dm.get_videos()
        if not videos: return
        if QMessageBox.question(self, "确认", f"清空全部{len(videos)}个视频？此操作不可恢复！") == QMessageBox.StandardButton.Yes:
            dm.clear_all_videos(); self._refresh_library(); Toast.success(self, "已清空视频库")

    def _add_to_cut(self):
        vids = []
        for i in range(self._lib_table.rowCount()):
            cb = self._lib_table.cellWidget(i, 0)
            if cb and cb.isChecked():
                name = self._lib_table.item(i, 1).text()
                for v in dm.get_videos():
                    if v["name"] == name: vids.append(v["id"]); break
        if not vids: Toast.warning(self, "请勾选视频"); return
        gname = self._group_name.text().strip()
        mode = "segments" if self._cut_mode.currentIndex() == 0 else "duration"
        mix_seg = max(1, self._mix_seg.value())
        group = dm.create_cut_group(vids, mode, self._cut_val.value(), mix_seg, gname)
        dm.create_mix_task(group["basket_id"], self._mix_seg.value())
        Toast.success(self, f"已创建裁切组「{group['name']}」")
        self._group_name.clear()
        self._refresh_cut(); self._refresh_baskets(); self._refresh_mix()

    # ══════════════════════════════════════════════════════════
    # 裁切操作
    # ══════════════════════════════════════════════════════════

    def _cut_one(self, gid):
        w = _CutWorker(gid)
        w.progress.connect(lambda m, p: self._cut_pbar.setValue(p))
        w.done.connect(lambda: (Toast.success(self,"裁切完成!"), self._refresh_cut(), self._refresh_baskets()))
        w.failed.connect(lambda m: Toast.error(self, f"裁切失败: {m}"))
        self._workers.append(w); w.start()

    def _cut_selected(self):
        row = self._cut_table.currentRow()
        if row < 0: Toast.warning(self, "请选择一行"); return
        groups = dm.get_cut_groups()
        if row < len(groups) and groups[row]["status"] == "pending":
            self._cut_one(groups[row]["id"])

    def _cut_all(self):
        for g in dm.get_cut_groups():
            if g["status"] == "pending": self._cut_one(g["id"])

    def _del_cut(self, gid):
        if QMessageBox.question(self, "确认", "删除此裁切组及篮子？") == QMessageBox.StandardButton.Yes:
            dm.delete_cut_group(gid); self._refresh_cut(); self._refresh_baskets(); self._refresh_mix()

    def _cut_delete_selected(self):
        ids = []
        for i in range(self._cut_table.rowCount()):
            cb = self._cut_table.cellWidget(i, 0)
            if cb and cb.isChecked():
                groups = dm.get_cut_groups()
                if i < len(groups): ids.append(groups[i]["id"])
        if not ids: Toast.warning(self, "请勾选要删除的项"); return
        if QMessageBox.question(self, "确认", f"删除选中的{len(ids)}个裁切组？") == QMessageBox.StandardButton.Yes:
            for gid in ids: dm.delete_cut_group(gid)
            self._refresh_cut(); self._refresh_baskets(); self._refresh_mix()
            Toast.success(self, f"已删除{len(ids)}个裁切组")

    def _cut_clear_all(self):
        groups = dm.get_cut_groups()
        if not groups: return
        if QMessageBox.question(self, "确认", f"清空全部{len(groups)}个裁切组？") == QMessageBox.StandardButton.Yes:
            for g in groups: dm.delete_cut_group(g["id"])
            self._refresh_cut(); self._refresh_baskets(); self._refresh_mix()
            Toast.success(self, "已清空裁切队列")

    # ══════════════════════════════════════════════════════════
    # 篮子操作
    # ══════════════════════════════════════════════════════════

    def _basket_delete_selected(self):
        bid = self._basket_combo.currentData()
        if not bid: return
        clip_ids = []
        for i in range(self._basket_table.rowCount()):
            cb = self._basket_table.cellWidget(i, 0)
            if cb and cb.isChecked():
                cid = self._basket_table.item(i, 5).text()
                clip_ids.append(cid)
        if not clip_ids: Toast.warning(self, "请勾选片段"); return
        if QMessageBox.question(self, "确认", f"删除选中的{len(clip_ids)}个片段？") == QMessageBox.StandardButton.Yes:
            dm.delete_clips_from_basket(bid, clip_ids); self._refresh_baskets()
            Toast.success(self, f"已删除{len(clip_ids)}个片段")

    def _basket_clear(self):
        bid = self._basket_combo.currentData()
        if not bid: return
        basket = dm.get_basket(bid)
        if not basket: return
        cnt = len(basket.get("clips", []))
        if cnt == 0: return
        if QMessageBox.question(self, "确认", f"清空此篮子的{cnt}个片段？") == QMessageBox.StandardButton.Yes:
            dm.clear_basket(bid); self._refresh_baskets(); Toast.success(self, "已清空篮子")

    # ══════════════════════════════════════════════════════════
    # 混剪操作
    # ══════════════════════════════════════════════════════════

    def _edit_audio_combos(self):
        dlg = AudioComboDialog(self, self._audio_combos)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._audio_combos = dlg.get_combos()
            self._audio_count_label.setText(f"{len(self._audio_combos)}个组合")

    def _mix_one(self, tid):
        mode = "random" if self._audio_mode_combo.currentIndex() == 0 else "sequential"
        self._ai_insert["video_fixed_time"] = self._ai_video_time.value()
        self._ai_insert["audio_fixed_time"] = self._ai_audio_time.value()
        w = _MixWorker(tid, self._audio_combos, mode, self._ai_insert)
        w.progress.connect(lambda m, p: self._mix_pbar.setValue(p))
        w.done.connect(lambda: (Toast.success(self,"混剪完成!"), self._refresh_mix()))
        w.failed.connect(lambda m: Toast.error(self, f"混剪失败: {m}"))
        self._workers.append(w); w.start()

    def _mix_selected(self):
        row = self._mix_table.currentRow()
        if row < 0: Toast.warning(self, "请选择一行"); return
        tasks = dm.get_mix_tasks()
        if row < len(tasks) and tasks[row]["status"] == "pending":
            self._mix_one(tasks[row]["id"])

    def _export_mix(self, tid):
        if dm.is_mixed_exported(tid):
            Toast.warning(self, "此任务已导出到待发布库，请勿重复导出")
            return
        db = dm._load_db()
        results = [r for r in db.get("mixed_results",[]) if r.get("task_id")==tid]
        cnt = 0
        for r in results:
            if os.path.exists(r["path"]):
                dm.add_pending_video(r["name"], r["path"], source="mixed", task_id=tid, clip_ids=r.get("clip_ids", []))
                cnt += 1
        Toast.success(self, f"已导出{cnt}个视频到待发布库")
        self._refresh_mix(); self._refresh_publish()
        self._tabs.setCurrentIndex(5)

    def _del_mix(self, tid):
        if QMessageBox.question(self, "确认", "删除此混剪任务？") == QMessageBox.StandardButton.Yes:
            dm.delete_mix_task(tid); self._refresh_mix()

    def _mix_delete_selected(self):
        ids = []
        for i in range(self._mix_table.rowCount()):
            cb = self._mix_table.cellWidget(i, 0)
            if cb and cb.isChecked():
                tasks = dm.get_mix_tasks()
                if i < len(tasks): ids.append(tasks[i]["id"])
        if not ids: Toast.warning(self, "请勾选"); return
        if QMessageBox.question(self, "确认", f"删除{len(ids)}个混剪任务？") == QMessageBox.StandardButton.Yes:
            for tid in ids: dm.delete_mix_task(tid)
            self._refresh_mix(); Toast.success(self, f"已删除{len(ids)}个任务")

    def _mix_clear_all(self):
        tasks = dm.get_mix_tasks()
        if not tasks: return
        if QMessageBox.question(self, "确认", f"清空全部{len(tasks)}个混剪任务？") == QMessageBox.StandardButton.Yes:
            for t in tasks: dm.delete_mix_task(t["id"])
            self._refresh_mix(); Toast.success(self, "已清空混剪队列")

    # ══════════════════════════════════════════════════════════
    # 待发布库操作
    # ══════════════════════════════════════════════════════════

    def _del_pending(self, vid):
        if QMessageBox.question(self, "确认", "删除此视频？") == QMessageBox.StandardButton.Yes:
            dm.delete_pending_video(vid); self._refresh_publish()

    def _publish_delete_selected(self):
        ids = []
        for i in range(self._pub_table.rowCount()):
            cb = self._pub_table.cellWidget(i, 0)
            if cb and cb.isChecked():
                videos = dm.get_pending_videos()
                if i < len(videos): ids.append(videos[i]["id"])
        if not ids: Toast.warning(self, "请勾选要删除的项"); return
        if QMessageBox.question(self, "确认", f"删除选中的{len(ids)}个视频？") == QMessageBox.StandardButton.Yes:
            for vid in ids: dm.delete_pending_video(vid)
            self._refresh_publish(); Toast.success(self, f"已删除{len(ids)}个视频")

    def _publish_clear_all(self):
        videos = dm.get_pending_videos()
        if not videos: return
        if QMessageBox.question(self, "确认", f"清空全部{len(videos)}个待发布视频？") == QMessageBox.StandardButton.Yes:
            for v in videos: dm.delete_pending_video(v["id"])
            self._refresh_publish(); Toast.success(self, "已清空待发布库")
