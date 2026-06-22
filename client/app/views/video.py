"""Video processing view with clip, mix, and video library."""

import os
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QLineEdit, QSpinBox, QComboBox, QTextEdit, QSlider, QFileDialog,
    QGridLayout, QScrollArea, QSizePolicy, QProgressBar, QCheckBox
)
from ..styles.theme import (
    BG_COLOR, CARD_STYLE, TEXT_COLOR, TEXT_SECONDARY, PRIMARY, SUCCESS,
    DANGER, WARNING, BORDER_COLOR, BTN_PRIMARY, BTN_DEFAULT, BTN_DANGER,
    BTN_PRIMARY_SM, INPUT_STYLE, TEXTAREA_STYLE, SLIDER_STYLE, SPINBOX_STYLE
)
from ..widgets.toast import Toast
from .. import api


class _VideoWorker(QThread):
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


class VideoView(QWidget):
    """Video processing page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers: list[_VideoWorker] = []
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # ── Top row: Clip + Mix ────────────────────────────────
        top_row = QHBoxLayout()
        top_row.setSpacing(16)

        # Left card: Clip
        clip_card = QFrame()
        clip_card.setStyleSheet(f"QFrame {{{CARD_STYLE} padding: 16px;}}")
        clip_layout = QVBoxLayout(clip_card)
        clip_layout.setSpacing(12)

        clip_title = QLabel("✂️ 原视频裁切")
        clip_title.setStyleSheet(f"font-size: 15px; font-weight: 600; color: {TEXT_COLOR};")
        clip_layout.addWidget(clip_title)

        # upload area
        self._upload_area = QLabel("📁 点击或拖拽视频文件到此处")
        self._upload_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._upload_area.setFixedHeight(100)
        self._upload_area.setStyleSheet(f"""
            QLabel {{
                background: #F7F8FA;
                border: 2px dashed {BORDER_COLOR};
                border-radius: 8px;
                color: {TEXT_SECONDARY};
                font-size: 14px;
            }}
            QLabel:hover {{
                border-color: {PRIMARY};
                color: {PRIMARY};
            }}
        """)
        self._upload_area.setCursor(Qt.CursorShape.PointingHandCursor)
        self._upload_area.mousePressEvent = lambda _: self._select_file()
        clip_layout.addWidget(self._upload_area)

        self._file_label = QLabel("未选择文件")
        self._file_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        clip_layout.addWidget(self._file_label)

        # clip settings
        seg_layout = QHBoxLayout()
        seg_layout.addWidget(QLabel("裁切段数:"))
        self._segments = QSpinBox()
        self._segments.setRange(1, 20)
        self._segments.setValue(3)
        self._segments.setStyleSheet(SPINBOX_STYLE)
        seg_layout.addWidget(self._segments)
        seg_layout.addStretch()
        clip_layout.addLayout(seg_layout)

        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("命名规则:"))
        self._name_rule = QLineEdit("{原名}_片段{序号}")
        self._name_rule.setStyleSheet(INPUT_STYLE)
        name_layout.addWidget(self._name_rule)
        clip_layout.addLayout(name_layout)

        clip_btn = QPushButton("开始裁切")
        clip_btn.setStyleSheet(BTN_PRIMARY)
        clip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clip_btn.clicked.connect(self._on_clip)
        clip_layout.addWidget(clip_btn)

        clip_layout.addStretch()
        top_row.addWidget(clip_card)

        # Right card: Mix
        mix_card = QFrame()
        mix_card.setStyleSheet(f"QFrame {{{CARD_STYLE} padding: 16px;}}")
        mix_layout = QVBoxLayout(mix_card)
        mix_layout.setSpacing(12)

        mix_title = QLabel("🎞️ 混剪与配音")
        mix_title.setStyleSheet(f"font-size: 15px; font-weight: 600; color: {TEXT_COLOR};")
        mix_layout.addWidget(mix_title)

        # mix rule
        rule_layout = QHBoxLayout()
        rule_layout.addWidget(QLabel("混剪规则:"))
        self._mix_rule = QComboBox()
        self._mix_rule.addItems(["随机拼接", "顺序拼接", "交替混剪", "自定义模板"])
        self._mix_rule.setStyleSheet(INPUT_STYLE)
        rule_layout.addWidget(self._mix_rule)
        mix_layout.addLayout(rule_layout)

        # AI voice
        voice_label = QLabel("🎙️ AI配音")
        voice_label.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {TEXT_COLOR};")
        mix_layout.addWidget(voice_label)

        self._voice_text = QTextEdit()
        self._voice_text.setPlaceholderText("输入配音文案...")
        self._voice_text.setMaximumHeight(60)
        self._voice_text.setStyleSheet(TEXTAREA_STYLE)
        mix_layout.addWidget(self._voice_text)

        voice_row = QHBoxLayout()
        voice_row.addWidget(QLabel("音色:"))
        self._voice_type = QComboBox()
        self._voice_type.addItems(["女声-温柔", "女声-活力", "男声-沉稳", "男声-阳光"])
        self._voice_type.setStyleSheet(INPUT_STYLE)
        voice_row.addWidget(self._voice_type)
        mix_layout.addLayout(voice_row)

        speed_layout = QHBoxLayout()
        speed_layout.addWidget(QLabel("语速:"))
        self._speed_slider = QSlider(Qt.Orientation.Horizontal)
        self._speed_slider.setRange(50, 200)
        self._speed_slider.setValue(100)
        self._speed_slider.setStyleSheet(SLIDER_STYLE)
        speed_layout.addWidget(self._speed_slider)
        self._speed_label = QLabel("1.0x")
        self._speed_slider.valueChanged.connect(
            lambda v: self._speed_label.setText(f"{v/100:.1f}x"))
        speed_layout.addWidget(self._speed_label)
        mix_layout.addLayout(speed_layout)

        voice_btns = QHBoxLayout()
        preview_btn = QPushButton("试听")
        preview_btn.setStyleSheet(BTN_DEFAULT)
        preview_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        voice_btns.addWidget(preview_btn)
        gen_voice_btn = QPushButton("生成配音")
        gen_voice_btn.setStyleSheet(BTN_PRIMARY_SM)
        gen_voice_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        voice_btns.addWidget(gen_voice_btn)
        mix_layout.addLayout(voice_btns)

        # bg audio
        bg_layout = QHBoxLayout()
        bg_layout.addWidget(QLabel("背景音频:"))
        self._bg_audio = QComboBox()
        self._bg_audio.addItems(["无", "轻音乐", "动感节拍", "古风", "自定义..."])
        self._bg_audio.setStyleSheet(INPUT_STYLE)
        bg_layout.addWidget(self._bg_audio)
        mix_layout.addLayout(bg_layout)

        vol_layout = QHBoxLayout()
        vol_layout.addWidget(QLabel("音量:"))
        self._vol_slider = QSlider(Qt.Orientation.Horizontal)
        self._vol_slider.setRange(0, 100)
        self._vol_slider.setValue(50)
        self._vol_slider.setStyleSheet(SLIDER_STYLE)
        vol_layout.addWidget(self._vol_slider)
        self._vol_label = QLabel("50%")
        self._vol_slider.valueChanged.connect(
            lambda v: self._vol_label.setText(f"{v}%"))
        vol_layout.addWidget(self._vol_label)
        mix_layout.addLayout(vol_layout)

        # subtitle
        self._subtitle_cb = QCheckBox("添加字幕")
        self._subtitle_cb.setStyleSheet(f"""
            QCheckBox {{ font-size: 13px; color: {TEXT_COLOR}; spacing: 6px; }}
            QCheckBox::indicator {{
                width: 16px; height: 16px; border: 1px solid {BORDER_COLOR};
                border-radius: 3px; background: white;
            }}
            QCheckBox::indicator:checked {{ background: {PRIMARY}; border-color: {PRIMARY}; }}
        """)
        mix_layout.addWidget(self._subtitle_cb)

        mix_btn = QPushButton("开始混剪")
        mix_btn.setStyleSheet(BTN_PRIMARY)
        mix_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        mix_btn.clicked.connect(self._on_mix)
        mix_layout.addWidget(mix_btn)

        top_row.addWidget(mix_card)
        main_layout.addLayout(top_row)

        # ── Video Library ──────────────────────────────────────
        lib_label = QLabel("📁 视频库")
        lib_label.setStyleSheet(f"font-size: 15px; font-weight: 600; color: {TEXT_COLOR};")
        main_layout.addWidget(lib_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._video_grid = QWidget()
        self._grid_layout = QGridLayout(self._video_grid)
        self._grid_layout.setSpacing(12)
        scroll.setWidget(self._video_grid)
        main_layout.addWidget(scroll, 1)

    def _select_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择视频文件", "",
            "视频文件 (*.mp4 *.avi *.mov *.mkv *.flv);;所有文件 (*)")
        if path:
            self._file_label.setText(path)
            self._upload_area.setText(f"📁 {os.path.basename(path)}")

    def _on_clip(self):
        file_path = self._file_label.text()
        if not file_path or file_path == "未选择文件":
            Toast.warning(self, "请先选择视频文件")
            return
        data = {
            "filePath": file_path,
            "segments": self._segments.value(),
            "nameRule": self._name_rule.text(),
        }
        w = _VideoWorker(api.start_clip, data)
        w.done.connect(lambda r: Toast.success(self, "裁切任务已提交"))
        w.failed.connect(lambda m: Toast.error(self, f"裁切失败: {m}"))
        self._workers.append(w)
        w.start()

    def _on_mix(self):
        data = {
            "rule": self._mix_rule.currentText(),
            "voiceText": self._voice_text.toPlainText(),
            "voiceType": self._voice_type.currentText(),
            "speed": self._speed_slider.value() / 100,
            "bgAudio": self._bg_audio.currentText(),
            "volume": self._vol_slider.value(),
            "subtitle": self._subtitle_cb.isChecked(),
        }
        w = _VideoWorker(api.start_mix, data)
        w.done.connect(lambda r: Toast.success(self, "混剪任务已提交"))
        w.failed.connect(lambda m: Toast.error(self, f"混剪失败: {m}"))
        self._workers.append(w)
        w.start()

    def load_data(self):
        """Load video library."""
        w = _VideoWorker(api.get_videos)
        w.done.connect(self._on_videos)
        w.failed.connect(lambda m: Toast.error(self, f"加载视频库失败: {m}"))
        self._workers.append(w)
        w.start()

    def _on_videos(self, data: dict):
        d = data.get("data", data)
        videos = d.get("list", d.get("records", [])) if isinstance(d, dict) else d

        # clear grid
        while self._grid_layout.count():
            child = self._grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        cols = 4
        for i, v in enumerate(videos[:20]):
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    {CARD_STYLE}
                    padding: 12px;
                }}
                QFrame:hover {{
                    border-color: {PRIMARY};
                }}
            """)
            card.setFixedSize(200, 200)
            cl = QVBoxLayout(card)
            cl.setSpacing(6)

            # preview placeholder
            preview = QLabel("🎬")
            preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            preview.setFixedHeight(80)
            preview.setStyleSheet(f"""
                background: #F7F8FA;
                border-radius: 6px;
                font-size: 32px;
            """)
            cl.addWidget(preview)

            name = QLabel(str(v.get("filename", v.get("name", "未命名"))))
            name.setStyleSheet(f"font-size: 12px; color: {TEXT_COLOR}; font-weight: 500;")
            name.setWordWrap(True)
            cl.addWidget(name)

            size = str(v.get("size", v.get("fileSize", "--")))
            size_label = QLabel(f"📦 {size}")
            size_label.setStyleSheet(f"font-size: 11px; color: {TEXT_SECONDARY};")
            cl.addWidget(size_label)

            add_btn = QPushButton("移入发布队列")
            add_btn.setStyleSheet(BTN_PRIMARY_SM)
            add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            vid = str(v.get("id", v.get("_id", "")))
            add_btn.clicked.connect(lambda _, vid_id=vid: self._add_to_queue(vid_id))
            cl.addWidget(add_btn)

            self._grid_layout.addWidget(card, i // cols, i % cols)

        if not videos:
            empty = QLabel("暂无视频，请先裁切或混剪生成")
            empty.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 14px; padding: 40px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._grid_layout.addWidget(empty, 0, 0, 1, cols)

    def _add_to_queue(self, video_id: str):
        w = _VideoWorker(api.add_to_publish_queue, [video_id])
        w.done.connect(lambda _: Toast.success(self, "已移入发布队列"))
        w.failed.connect(lambda m: Toast.error(self, f"添加失败: {m}"))
        self._workers.append(w)
        w.start()
