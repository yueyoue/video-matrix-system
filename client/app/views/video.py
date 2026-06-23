"""
视频处理模块 v3 - 视频库、裁切队列、篮子、混剪队列、待发布库
修复：按钮显示、导出逻辑、文件夹路径、清空功能
"""

import os
import random
import itertools
import subprocess
import sys
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QLineEdit, QSpinBox, QComboBox, QFileDialog, QGridLayout, QScrollArea,
    QSizePolicy, QProgressBar, QCheckBox, QTabWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QFormLayout, QGroupBox, QMessageBox,
    QListWidget, QListWidgetItem, QAbstractItemView, QDialog, QDialogButtonBox
)
from ..styles.theme import (
    BG_COLOR, CARD_STYLE, TEXT_COLOR, TEXT_SECONDARY, PRIMARY, PRIMARY_HOVER,
    PRIMARY_PRESSED, SUCCESS, DANGER, DANGER_HOVER, WARNING, BORDER_COLOR,
    BTN_PRIMARY, BTN_PRIMARY_SM, BTN_DEFAULT, BTN_DANGER, BTN_DANGER_TEXT,
    BTN_SUCCESS, BTN_TEXT, INPUT_STYLE, SPINBOX_STYLE, TABLE_STYLE
)
from ..widgets.toast import Toast
from .. import ffmpeg
from .. import data_manager as dm


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
            from ..api import _debug_log
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
    def __init__(self, task_id, audio_combos=None, audio_mode="random"):
        super().__init__()
        self.task_id = task_id
        self.audio_combos = audio_combos or []
        self.audio_mode = audio_mode
    def run(self):
        try:
            from ..api import _debug_log
            task = dm.get_mix_task(self.task_id)
            if not task: self.failed.emit("混剪任务不存在"); return
            dm.update_mix_task_progress(self.task_id, 0, "running")
            basket_id = task["basket_id"]
            segments_per_video = task.get("segments_per_video", 1)
            if segments_per_video < 1:
                segments_per_video = 1
            clips_by_src = dm.get_basket_clips_by_source(basket_id)
            sources = sorted(clips_by_src.keys())
            if not sources:
                dm.update_mix_task_progress(self.task_id, 0, "error")
                self.failed.emit("篮子中没有片段，请先完成裁切"); return
            min_clips = min(len(clips_by_src[s]) for s in sources)
            if min_clips < 1:
                dm.update_mix_task_progress(self.task_id, 0, "error")
                self.failed.emit("篮子中没有可用片段"); return
            if segments_per_video > min_clips:
                segments_per_video = min_clips
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
                    for group in combo:
                        ids.extend([c["id"] for c in group])
                    combinations.append(ids)
            total = len(combinations)
            _debug_log(f"[MixWorker] 混剪开始: 组合数={total}, 篮子={basket_id}")
            if total == 0:
                dm.update_mix_task_progress(self.task_id, 0, "error")
                self.failed.emit("无法生成组合"); return
            dm.update_mix_task_total(self.task_id, total)
            mix_dir = dm.MIXED_DIR / self.task_id
            mix_dir.mkdir(parents=True, exist_ok=True)
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
                ffmpeg.mix_videos(clip_paths, out_path, bg_audio=audio_path)
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
            from ..api import _debug_log
            _debug_log(f"[MixWorker] 异常: {e}\n{traceback.format_exc()}")
            dm.update_mix_task_progress(self.task_id, 0, "error")
            self.failed.emit(str(e))


# ══════════════════════════════════════════════════════════════
# 文字+音频组合对话框
# ══════════════════════════════════════════════════════════════

class AudioComboDialog(QDialog):
    """编辑文字+音频组合"""
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
            del_btn.setStyleSheet(f"color: {DANGER}; border:none; font-size:12px;")
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            idx = i
            del_btn.clicked.connect(lambda _, ii=idx: (self.combos.pop(ii), self._refresh_list()))
            self._list.setCellWidget(i, 3, del_btn)

    def get_combos(self):
        return self.combos


# ══════════════════════════════════════════════════════════════
# 辅助函数
# ══════════════════════════════════════════════════════════════

def _action_btn(text, style, callback):
    """创建操作按钮 - 带完整样式"""
    btn = QPushButton(text)
    btn.setStyleSheet(style)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setMinimumHeight(32)
    btn.clicked.connect(callback)
    return btn


def _open_folder(path: str):
    """打开文件所在文件夹"""
    if not path or not os.path.exists(path):
        return
    folder = os.path.dirname(path) if os.path.isfile(path) else path
    if not os.path.isdir(folder):
        return
    if sys.platform == 'win32':
        os.startfile(folder)
    elif sys.platform == 'darwin':
        subprocess.Popen(['open', folder])
    else:
        subprocess.Popen(['xdg-open', folder])


def _open_file(path: str):
    """打开文件"""
    if not path or not os.path.exists(path):
        return
    if sys.platform == 'win32':
        os.startfile(path)
    elif sys.platform == 'darwin':
        subprocess.Popen(['open', path])
    else:
        subprocess.Popen(['xdg-open', path])


def _folder_link_widget(path: str):
    """创建可点击的文件夹路径标签"""
    if not path:
        return QLabel("--")
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
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet("""
            QTabWidget::pane { border: none; }
            QTabBar::tab { padding: 10px 24px; font-size: 14px; border: none; border-bottom: 2px solid transparent; color: #999; }
            QTabBar::tab:selected { color: #165DFF; border-bottom: 2px solid #165DFF; }
        """)
        self._tabs.addTab(self._create_library_tab(), "📁 视频库")
        self._tabs.addTab(self._create_cut_tab(), "✂️ 裁切队列")
        self._tabs.addTab(self._create_basket_tab(), "🧺 篮子")
        self._tabs.addTab(self._create_mix_tab(), "🎞️ 混剪队列")
        self._tabs.addTab(self._create_publish_tab(), "📤 待发布库")
        layout.addWidget(self._tabs)

    # ── 视频库 ─────────────────────────────────────────────
    def _create_library_tab(self):
        tab = QWidget(); layout = QVBoxLayout(tab); layout.setSpacing(12)

        # 文件夹路径提示
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

        # 操作栏
        bar = QHBoxLayout()
        bar.setSpacing(8)
        bar.addWidget(_action_btn("📁 上传视频", BTN_PRIMARY, self._upload_videos))
        self._group_name = QLineEdit(); self._group_name.setPlaceholderText("裁切组名称"); self._group_name.setStyleSheet(INPUT_STYLE); self._group_name.setFixedWidth(130)
        bar.addWidget(self._group_name)
        bar.addWidget(_action_btn("✂️ 添加到裁切队列", BTN_PRIMARY, self._add_to_cut))
        bar.addStretch()
        bar.addWidget(_action_btn("🗑️ 清空全部", BTN_DANGER, self._library_clear_all))
        bar.addWidget(_action_btn("🔄 刷新", BTN_DEFAULT, self._refresh_library))
        layout.addLayout(bar)

        self._lib_table = QTableWidget()
        self._lib_table.setStyleSheet(TABLE_STYLE)
        self._lib_table.setColumnCount(8)
        self._lib_table.setHorizontalHeaderLabels(["☑", "文件名", "时长", "大小", "来源", "路径", "时间", "操作"])
        self._lib_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._lib_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._lib_table.setColumnWidth(0, 35)
        self._lib_table.verticalHeader().setVisible(False)
        layout.addWidget(self._lib_table, 1)
        return tab

    # ── 裁切队列 ───────────────────────────────────────────
    def _create_cut_tab(self):
        tab = QWidget(); layout = QVBoxLayout(tab); layout.setSpacing(12)

        # 文件夹路径提示
        path_bar = QHBoxLayout()
        path_label = QLabel(f"📂 裁切文件夹: {dm.BASKETS_DIR}")
        path_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; padding: 4px 0;")
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path_bar.addWidget(path_label, 1)
        open_btn = QPushButton("打开文件夹")
        open_btn.setStyleSheet(BTN_TEXT)
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.clicked.connect(lambda: _open_folder(str(dm.BASKETS_DIR)))
        path_bar.addWidget(open_btn)
        layout.addLayout(path_bar)

        # 规则
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

        # 操作栏
        bar = QHBoxLayout()
        bar.setSpacing(8)
        bar.addWidget(_action_btn("▶️ 裁切选中", BTN_PRIMARY, self._cut_selected))
        bar.addWidget(_action_btn("▶️ 裁切全部", BTN_DEFAULT, self._cut_all))
        bar.addStretch()
        bar.addWidget(_action_btn("🗑️ 删除选中", BTN_DANGER, self._cut_delete_selected))
        bar.addWidget(_action_btn("🗑️ 清空全部", BTN_DANGER, self._cut_clear_all))
        bar.addWidget(QLabel("  进度:"))
        self._cut_pbar = QProgressBar(); self._cut_pbar.setFixedWidth(180); self._cut_pbar.setFixedHeight(18)
        bar.addWidget(self._cut_pbar)
        layout.addLayout(bar)

        self._cut_table = QTableWidget()
        self._cut_table.setStyleSheet(TABLE_STYLE)
        self._cut_table.setColumnCount(7)
        self._cut_table.setHorizontalHeaderLabels(["☑", "组名", "视频数", "规则", "状态", "进度", "操作"])
        self._cut_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._cut_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._cut_table.setColumnWidth(0, 35)
        self._cut_table.verticalHeader().setVisible(False)
        layout.addWidget(self._cut_table, 1)
        return tab

    # ── 篮子 ───────────────────────────────────────────────
    def _create_basket_tab(self):
        tab = QWidget(); layout = QVBoxLayout(tab); layout.setSpacing(12)

        # 文件夹路径提示
        path_bar = QHBoxLayout()
        path_label = QLabel(f"📂 篮子文件夹: {dm.BASKETS_DIR}")
        path_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; padding: 4px 0;")
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path_bar.addWidget(path_label, 1)
        open_btn = QPushButton("打开文件夹")
        open_btn.setStyleSheet(BTN_TEXT)
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.clicked.connect(lambda: _open_folder(str(dm.BASKETS_DIR)))
        path_bar.addWidget(open_btn)
        layout.addLayout(path_bar)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        bar.addWidget(QLabel("篮子:"))
        self._basket_combo = QComboBox(); self._basket_combo.setStyleSheet(INPUT_STYLE); self._basket_combo.setMinimumWidth(200)
        self._basket_combo.currentIndexChanged.connect(self._on_basket_sel)
        bar.addWidget(self._basket_combo)
        bar.addStretch()
        bar.addWidget(_action_btn("🗑️ 删除选中片段", BTN_DANGER, self._basket_delete_selected))
        bar.addWidget(_action_btn("🗑️ 清空当前篮子", BTN_DANGER, self._basket_clear))
        self._basket_status = QLabel(""); self._basket_status.setStyleSheet(f"color:{TEXT_SECONDARY};")
        bar.addWidget(self._basket_status)
        layout.addLayout(bar)

        self._basket_table = QTableWidget()
        self._basket_table.setStyleSheet(TABLE_STYLE)
        self._basket_table.setColumnCount(6)
        self._basket_table.setHorizontalHeaderLabels(["☑", "来源", "片段", "时长", "路径", "ID"])
        self._basket_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._basket_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._basket_table.setColumnWidth(0, 35)
        self._basket_table.verticalHeader().setVisible(False)
        layout.addWidget(self._basket_table, 1)
        return tab

    # ── 混剪队列 ───────────────────────────────────────────
    def _create_mix_tab(self):
        tab = QWidget(); layout = QVBoxLayout(tab); layout.setSpacing(12)

        # 文件夹路径提示
        path_bar = QHBoxLayout()
        path_label = QLabel(f"📂 混剪输出文件夹: {dm.MIXED_DIR}")
        path_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; padding: 4px 0;")
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path_bar.addWidget(path_label, 1)
        open_btn = QPushButton("打开文件夹")
        open_btn.setStyleSheet(BTN_TEXT)
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

        # 操作栏
        bar = QHBoxLayout()
        bar.setSpacing(8)
        bar.addWidget(_action_btn("▶️ 开始混剪", BTN_PRIMARY, self._mix_selected))
        bar.addStretch()
        bar.addWidget(_action_btn("🗑️ 删除选中", BTN_DANGER, self._mix_delete_selected))
        bar.addWidget(_action_btn("🗑️ 清空全部", BTN_DANGER, self._mix_clear_all))
        bar.addWidget(QLabel("  进度:"))
        self._mix_pbar = QProgressBar(); self._mix_pbar.setFixedWidth(180); self._mix_pbar.setFixedHeight(18)
        bar.addWidget(self._mix_pbar)
        layout.addLayout(bar)

        self._mix_table = QTableWidget()
        self._mix_table.setStyleSheet(TABLE_STYLE)
        self._mix_table.setColumnCount(7)
        self._mix_table.setHorizontalHeaderLabels(["☑", "篮子", "取几段", "组合数", "已完成", "状态", "操作"])
        self._mix_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._mix_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._mix_table.setColumnWidth(0, 35)
        self._mix_table.verticalHeader().setVisible(False)
        layout.addWidget(self._mix_table, 1)
        return tab

    # ── 待发布库 ───────────────────────────────────────────
    def _create_publish_tab(self):
        tab = QWidget(); layout = QVBoxLayout(tab); layout.setSpacing(12)

        # 文件夹路径提示
        path_bar = QHBoxLayout()
        path_label = QLabel(f"📂 待发布文件夹: {dm.PUBLISH_DIR}")
        path_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; padding: 4px 0;")
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path_bar.addWidget(path_label, 1)
        open_btn = QPushButton("打开文件夹")
        open_btn.setStyleSheet(BTN_TEXT)
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.clicked.connect(lambda: _open_folder(str(dm.PUBLISH_DIR)))
        path_bar.addWidget(open_btn)
        layout.addLayout(path_bar)

        # 说明
        info = QLabel("💡 混剪完成的视频导出后会出现在这里，后续将根据发布调度规则自动发布到各大视频平台。")
        info.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; padding: 4px 0;")
        info.setWordWrap(True)
        layout.addWidget(info)

        # 操作栏
        bar = QHBoxLayout()
        bar.setSpacing(8)
        bar.addWidget(_action_btn("🔄 刷新", BTN_DEFAULT, self._refresh_publish))
        bar.addStretch()
        bar.addWidget(_action_btn("🗑️ 删除选中", BTN_DANGER, self._publish_delete_selected))
        bar.addWidget(_action_btn("🗑️ 清空全部", BTN_DANGER, self._publish_clear_all))
        layout.addLayout(bar)

        self._pub_table = QTableWidget()
        self._pub_table.setStyleSheet(TABLE_STYLE)
        self._pub_table.setColumnCount(8)
        self._pub_table.setHorizontalHeaderLabels(["☑", "文件名", "大小", "来源", "路径", "发布时间", "状态", "操作"])
        self._pub_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._pub_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._pub_table.setColumnWidth(0, 35)
        self._pub_table.verticalHeader().setVisible(False)
        layout.addWidget(self._pub_table, 1)
        return tab

    # ══════════════════════════════════════════════════════════
    # 数据刷新
    # ══════════════════════════════════════════════════════════

    def load_data(self):
        self._refresh_library(); self._refresh_cut(); self._refresh_baskets(); self._refresh_mix(); self._refresh_publish()

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
            self._lib_table.setCellWidget(i, 7, _action_btn("删除", f"""
                QPushButton {{ background: {DANGER}; color: white; border: none; border-radius: 4px; padding: 4px 12px; font-size: 12px; min-height: 26px; }}
                QPushButton:hover {{ background: {DANGER_HOVER}; }}
            """, lambda _, vv=vid: self._del_video(vv)))

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
            # 操作按钮
            ow = QWidget(); ol = QHBoxLayout(ow); ol.setContentsMargins(4, 4, 4, 4); ol.setSpacing(6)
            gid = g["id"]
            if g.get("status") == "pending":
                ol.addWidget(_action_btn("裁切", BTN_PRIMARY_SM, lambda _, gg=gid: self._cut_one(gg)))
            ol.addWidget(_action_btn("删除", f"""
                QPushButton {{ background: {DANGER}; color: white; border: none; border-radius: 4px; padding: 4px 12px; font-size: 12px; min-height: 26px; }}
                QPushButton:hover {{ background: {DANGER_HOVER}; }}
            """, lambda _, gg=gid: self._del_cut(gg)))
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
            ow = QWidget(); ol = QHBoxLayout(ow); ol.setContentsMargins(4, 4, 4, 4); ol.setSpacing(6)
            if t.get("status") == "pending":
                ol.addWidget(_action_btn("混剪", BTN_PRIMARY_SM, lambda _, tt=tid: self._mix_one(tt)))
            if t.get("status") == "done":
                # 检查是否已导出
                exported_count = dm.get_mixed_exported_count(tid)
                if exported_count > 0:
                    already_label = QLabel(f"已导出{exported_count}个")
                    already_label.setStyleSheet(f"color: {SUCCESS}; font-size: 12px;")
                    ol.addWidget(already_label)
                else:
                    ol.addWidget(_action_btn("导出到待发布库", f"""
                        QPushButton {{ background: {SUCCESS}; color: white; border: none; border-radius: 4px; padding: 4px 12px; font-size: 12px; min-height: 26px; }}
                        QPushButton:hover {{ background: #23C343; }}
                    """, lambda _, tt=tid: self._export_mix(tt)))
            ol.addWidget(_action_btn("删除", f"""
                QPushButton {{ background: {DANGER}; color: white; border: none; border-radius: 4px; padding: 4px 12px; font-size: 12px; min-height: 26px; }}
                QPushButton:hover {{ background: {DANGER_HOVER}; }}
            """, lambda _, tt=tid: self._del_mix(tt)))
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
            self._pub_table.setCellWidget(i, 7, _action_btn("删除", f"""
                QPushButton {{ background: {DANGER}; color: white; border: none; border-radius: 4px; padding: 4px 12px; font-size: 12px; min-height: 26px; }}
                QPushButton:hover {{ background: {DANGER_HOVER}; }}
            """, lambda _, vv=vid: self._del_pending(vv)))

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

    def _library_clear_all(self):
        videos = dm.get_videos()
        if not videos: return
        if QMessageBox.question(self, "确认", f"清空全部{len(videos)}个视频？此操作不可恢复！") == QMessageBox.StandardButton.Yes:
            dm.clear_all_videos()
            self._refresh_library()
            Toast.success(self, "已清空视频库")

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
            dm.delete_clips_from_basket(bid, clip_ids)
            self._refresh_baskets()
            Toast.success(self, f"已删除{len(clip_ids)}个片段")

    def _basket_clear(self):
        bid = self._basket_combo.currentData()
        if not bid: return
        basket = dm.get_basket(bid)
        if not basket: return
        cnt = len(basket.get("clips", []))
        if cnt == 0: return
        if QMessageBox.question(self, "确认", f"清空此篮子的{cnt}个片段？") == QMessageBox.StandardButton.Yes:
            dm.clear_basket(bid)
            self._refresh_baskets()
            Toast.success(self, "已清空篮子")

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
        w = _MixWorker(tid, self._audio_combos, mode)
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
        # 检查是否已导出
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
        self._refresh_mix()
        self._refresh_publish()
        # 自动切换到待发布库标签
        self._tabs.setCurrentIndex(4)

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
            self._refresh_publish()
            Toast.success(self, f"已删除{len(ids)}个视频")

    def _publish_clear_all(self):
        videos = dm.get_pending_videos()
        if not videos: return
        if QMessageBox.question(self, "确认", f"清空全部{len(videos)}个待发布视频？") == QMessageBox.StandardButton.Yes:
            for v in videos: dm.delete_pending_video(v["id"])
            self._refresh_publish()
            Toast.success(self, "已清空待发布库")
