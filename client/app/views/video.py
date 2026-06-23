"""
视频处理模块 - 视频库、裁切队列、篮子、混剪队列
"""

import os
import itertools
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QLineEdit, QSpinBox, QComboBox, QFileDialog, QGridLayout, QScrollArea,
    QSizePolicy, QProgressBar, QCheckBox, QTabWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QFormLayout, QGroupBox, QMessageBox,
    QListWidget, QListWidgetItem, QAbstractItemView
)
from ..styles.theme import (
    BG_COLOR, CARD_STYLE, TEXT_COLOR, TEXT_SECONDARY, PRIMARY, SUCCESS,
    DANGER, WARNING, BORDER_COLOR, BTN_PRIMARY, BTN_DEFAULT, BTN_DANGER,
    BTN_PRIMARY_SM, INPUT_STYLE, SPINBOX_STYLE, TABLE_STYLE
)
from ..widgets.toast import Toast
from .. import ffmpeg
from .. import data_manager as dm


# ══════════════════════════════════════════════════════════════
# 工作线程
# ══════════════════════════════════════════════════════════════

class _UploadWorker(QThread):
    """上传视频到视频库"""
    done = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, file_paths: list):
        super().__init__()
        self.file_paths = file_paths

    def run(self):
        try:
            results = []
            for fp in self.file_paths:
                # 获取视频时长
                duration = 0
                try:
                    duration = ffmpeg.get_duration(fp)
                except Exception:
                    pass
                video = dm.add_video(fp, duration=duration)
                results.append(video)
            self.done.emit({"videos": results})
        except Exception as e:
            self.failed.emit(str(e))


class _CutWorker(QThread):
    """裁切视频"""
    progress = pyqtSignal(str, int)  # (message, percent)
    done = pyqtSignal(str)  # group_id
    failed = pyqtSignal(str)

    def __init__(self, group_id: str):
        super().__init__()
        self.group_id = group_id

    def run(self):
        try:
            group = dm.get_cut_group(self.group_id)
            if not group:
                self.failed.emit("裁切组不存在")
                return

            dm.update_cut_group_status(self.group_id, "cutting", 0)
            cut_rule = group["cut_rule"]
            basket_id = group["basket_id"]

            # 创建篮子目录
            basket_dir = dm.BASKETS_DIR / basket_id
            basket_dir.mkdir(parents=True, exist_ok=True)

            videos = [dm.get_video(vid) for vid in group["video_ids"]]
            videos = [v for v in videos if v]
            total = len(videos)

            for idx, video in enumerate(videos):
                self.progress.emit(f"正在裁切: {video['name']} ({idx+1}/{total})", int((idx) / total * 100))

                # 计算裁切参数
                if cut_rule["mode"] == "segments":
                    segments = cut_rule["value"]
                    clip_paths = ffmpeg.cut_video_segments(
                        video["path"], segments, str(basket_dir), video["name"]
                    )
                else:
                    segment_duration = cut_rule["value"]
                    clip_paths = ffmpeg.cut_video_by_duration(
                        video["path"], segment_duration, str(basket_dir), video["name"]
                    )

                # 记录片段到篮子
                for i, clip_path in enumerate(clip_paths):
                    clip_dur = 0
                    try:
                        clip_dur = ffmpeg.get_duration(clip_path)
                    except Exception:
                        pass
                    dm.add_clip_to_basket(basket_id, video["name"], i + 1, clip_path, clip_dur)

                dm.update_cut_group_status(self.group_id, "cutting", int((idx + 1) / total * 100))

            dm.update_cut_group_status(self.group_id, "done", 100)
            self.progress.emit("裁切完成!", 100)
            self.done.emit(self.group_id)
        except Exception as e:
            dm.update_cut_group_status(self.group_id, "error")
            self.failed.emit(str(e))


class _MixWorker(QThread):
    """混剪视频"""
    progress = pyqtSignal(str, int)  # (message, percent)
    done = pyqtSignal(str)  # task_id
    failed = pyqtSignal(str)

    def __init__(self, task_id: str):
        super().__init__()
        self.task_id = task_id

    def run(self):
        try:
            task = dm.get_mix_task(self.task_id)
            if not task:
                self._debug_log(f"混剪任务不存在: {self.task_id}")
                self.failed.emit("混剪任务不存在")
                return

            dm.update_mix_task_progress(self.task_id, 0, "running")
            combinations = task.get("combinations", [])
            total = len(combinations)
            basket_id = task["basket_id"]

            self._debug_log(f"混剪任务开始: task_id={self.task_id}, 组合数={total}, basket_id={basket_id}")

            if total == 0:
                self._debug_log("组合数为0，无法混剪")
                dm.update_mix_task_progress(self.task_id, 0, "error")
                self.failed.emit("组合数为0，请检查篮子中是否有裁切好的片段")
                return

            # 混剪输出目录
            mix_dir = dm.MIXED_DIR / self.task_id
            mix_dir.mkdir(parents=True, exist_ok=True)

            for idx, clip_ids in enumerate(combinations):
                self.progress.emit(
                    f"正在混剪: {idx+1}/{total}",
                    int((idx) / total * 100)
                )

                # 获取片段信息
                clips = dm.get_clips_by_ids(clip_ids)
                clip_paths = [c["path"] for c in clips]

                self._debug_log(f"混剪 {idx+1}/{total}: {len(clips)} 个片段")

                # 混剪文件名
                mix_name = f"混剪_{idx+1}"
                out_path = str(mix_dir / f"{mix_name}.mp4")

                # 执行混剪
                ffmpeg.mix_videos(clip_paths, out_path)

                # 记录结果
                dm.add_mixed_result(self.task_id, mix_name, out_path, clip_ids)
                dm.update_mix_task_progress(self.task_id, idx + 1)

            dm.update_mix_task_progress(self.task_id, total, "done")
            self.progress.emit("混剪完成!", 100)
            self.done.emit(self.task_id)
        except Exception as e:
            import traceback
            err_detail = traceback.format_exc()
            self._debug_log(f"混剪异常: {e}\n{err_detail}")
            dm.update_mix_task_progress(self.task_id, 0, "error")
            self.failed.emit(str(e))

    def _debug_log(self, msg):
        from ..api import _debug_log
        _debug_log(f"[MixWorker] {msg}")


# ══════════════════════════════════════════════════════════════
# 主界面
# ══════════════════════════════════════════════════════════════

class VideoView(QWidget):
    """视频处理主页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Tab widget
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet("""
            QTabWidget::pane { border: none; }
            QTabBar::tab {
                padding: 10px 24px; font-size: 14px;
                border: none; border-bottom: 2px solid transparent;
                color: #999;
            }
            QTabBar::tab:selected { color: #165DFF; border-bottom: 2px solid #165DFF; }
        """)

        self._tabs.addTab(self._create_library_tab(), "📁 视频库")
        self._tabs.addTab(self._create_cut_queue_tab(), "✂️ 裁切队列")
        self._tabs.addTab(self._create_baskets_tab(), "🧺 篮子")
        self._tabs.addTab(self._create_mix_queue_tab(), "🎞️ 混剪队列")

        layout.addWidget(self._tabs)

    # ── 视频库 Tab ─────────────────────────────────────────
    def _create_library_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        # 操作栏
        btn_bar = QHBoxLayout()
        upload_btn = QPushButton("📁 上传视频")
        upload_btn.setStyleSheet(BTN_PRIMARY)
        upload_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        upload_btn.clicked.connect(self._upload_videos)
        btn_bar.addWidget(upload_btn)

        btn_bar.addWidget(QLabel("  选中视频添加到裁切组:"))

        self._group_name_input = QLineEdit()
        self._group_name_input.setPlaceholderText("裁切组名称（可选）")
        self._group_name_input.setStyleSheet(INPUT_STYLE)
        self._group_name_input.setFixedWidth(150)
        btn_bar.addWidget(self._group_name_input)

        add_to_cut_btn = QPushButton("✂️ 添加到裁切队列")
        add_to_cut_btn.setStyleSheet(BTN_PRIMARY_SM)
        add_to_cut_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_to_cut_btn.clicked.connect(self._add_to_cut_queue)
        btn_bar.addWidget(add_to_cut_btn)

        btn_bar.addStretch()
        refresh_lib_btn = QPushButton("🔄 刷新")
        refresh_lib_btn.setStyleSheet(BTN_DEFAULT)
        refresh_lib_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_lib_btn.clicked.connect(self._refresh_library)
        btn_bar.addWidget(refresh_lib_btn)
        layout.addLayout(btn_bar)

        # 视频列表
        self._library_table = QTableWidget()
        self._library_table.setStyleSheet(TABLE_STYLE)
        self._library_table.setColumnCount(7)
        self._library_table.setHorizontalHeaderLabels(["选择", "文件名", "时长", "大小", "来源", "添加时间", "操作"])
        self._library_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._library_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._library_table.setColumnWidth(0, 40)
        self._library_table.verticalHeader().setVisible(False)
        self._library_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self._library_table, 1)

        return tab

    # ── 裁切队列 Tab ───────────────────────────────────────
    def _create_cut_queue_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        # 裁切规则设置
        rule_group = QGroupBox("裁切规则")
        rule_group.setStyleSheet(f"""
            QGroupBox {{
                {CARD_STYLE}
                font-size: 14px; font-weight: 600;
                padding-top: 16px; margin-top: 8px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 16px; padding: 0 8px;
            }}
        """)
        rule_layout = QFormLayout(rule_group)
        rule_layout.setSpacing(12)

        self._cut_mode = QComboBox()
        self._cut_mode.addItems(["按段数裁切", "按时长裁切（秒）"])
        self._cut_mode.setStyleSheet(INPUT_STYLE)
        rule_layout.addRow("裁切方式:", self._cut_mode)

        self._cut_value = QSpinBox()
        self._cut_value.setRange(1, 999)
        self._cut_value.setValue(5)
        self._cut_value.setStyleSheet(SPINBOX_STYLE)
        rule_layout.addRow("裁切值:", self._cut_value)

        self._mix_segments = QSpinBox()
        self._mix_segments.setRange(1, 20)
        self._mix_segments.setValue(1)
        self._mix_segments.setStyleSheet(SPINBOX_STYLE)
        rule_layout.addRow("每个混剪取几段:", self._mix_segments)

        layout.addWidget(rule_group)

        # 操作栏
        btn_bar = QHBoxLayout()
        start_cut_btn = QPushButton("▶️ 开始裁切选中组")
        start_cut_btn.setStyleSheet(BTN_PRIMARY)
        start_cut_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        start_cut_btn.clicked.connect(self._start_cut_selected)
        btn_bar.addWidget(start_cut_btn)

        start_all_btn = QPushButton("▶️ 裁切全部待处理")
        start_all_btn.setStyleSheet(BTN_DEFAULT)
        start_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        start_all_btn.clicked.connect(self._start_cut_all)
        btn_bar.addWidget(start_all_btn)

        btn_bar.addStretch()
        btn_bar.addWidget(QLabel("进度:"))
        self._cut_progress = QProgressBar()
        self._cut_progress.setFixedWidth(200)
        self._cut_progress.setFixedHeight(20)
        self._cut_progress.setValue(0)
        btn_bar.addWidget(self._cut_progress)
        layout.addLayout(btn_bar)

        # 裁切组列表
        self._cut_table = QTableWidget()
        self._cut_table.setStyleSheet(TABLE_STYLE)
        self._cut_table.setColumnCount(6)
        self._cut_table.setHorizontalHeaderLabels(["组名", "视频数", "裁切规则", "状态", "进度", "操作"])
        self._cut_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._cut_table.verticalHeader().setVisible(False)
        layout.addWidget(self._cut_table, 1)

        return tab

    # ── 篮子 Tab ───────────────────────────────────────────
    def _create_baskets_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        # 篮子选择
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("选择篮子:"))
        self._basket_combo = QComboBox()
        self._basket_combo.setStyleSheet(INPUT_STYLE)
        self._basket_combo.setMinimumWidth(200)
        self._basket_combo.currentIndexChanged.connect(self._on_basket_selected)
        top_bar.addWidget(self._basket_combo)

        top_bar.addStretch()

        self._basket_status_label = QLabel("")
        self._basket_status_label.setStyleSheet(f"color: {TEXT_SECONDARY};")
        top_bar.addWidget(self._basket_status_label)
        layout.addLayout(top_bar)

        # 篮子内容表格
        self._basket_table = QTableWidget()
        self._basket_table.setStyleSheet(TABLE_STYLE)
        self._basket_table.setColumnCount(5)
        self._basket_table.setHorizontalHeaderLabels(["来源视频", "片段序号", "时长", "路径", "ID"])
        self._basket_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._basket_table.verticalHeader().setVisible(False)
        layout.addWidget(self._basket_table, 1)

        return tab

    # ── 混剪队列 Tab ───────────────────────────────────────
    def _create_mix_queue_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        # 操作栏
        btn_bar = QHBoxLayout()
        start_mix_btn = QPushButton("▶️ 开始混剪选中任务")
        start_mix_btn.setStyleSheet(BTN_PRIMARY)
        start_mix_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        start_mix_btn.clicked.connect(self._start_mix_selected)
        btn_bar.addWidget(start_mix_btn)

        btn_bar.addStretch()

        btn_bar.addWidget(QLabel("进度:"))
        self._mix_progress = QProgressBar()
        self._mix_progress.setFixedWidth(200)
        self._mix_progress.setFixedHeight(20)
        self._mix_progress.setValue(0)
        btn_bar.addWidget(self._mix_progress)
        layout.addLayout(btn_bar)

        # 混剪任务列表
        self._mix_table = QTableWidget()
        self._mix_table.setStyleSheet(TABLE_STYLE)
        self._mix_table.setColumnCount(6)
        self._mix_table.setHorizontalHeaderLabels(["篮子", "每个取几段", "组合数", "已完成", "状态", "操作"])
        self._mix_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._mix_table.verticalHeader().setVisible(False)
        layout.addWidget(self._mix_table, 1)

        return tab

    # ══════════════════════════════════════════════════════════
    # 数据加载
    # ══════════════════════════════════════════════════════════

    def load_data(self):
        """刷新所有数据"""
        self._refresh_library()
        self._refresh_cut_queue()
        self._refresh_baskets()
        self._refresh_mix_queue()

    def _refresh_library(self):
        videos = dm.get_videos()
        self._library_table.setRowCount(len(videos))
        for i, v in enumerate(videos):
            # 选择复选框
            cb = QCheckBox()
            self._library_table.setCellWidget(i, 0, cb)

            self._library_table.setItem(i, 1, QTableWidgetItem(v["name"]))

            dur = v.get("duration", 0)
            dur_str = f"{int(dur//60)}:{int(dur%60):02d}" if dur > 0 else "--"
            self._library_table.setItem(i, 2, QTableWidgetItem(dur_str))

            size = v.get("size", 0)
            size_str = f"{size/1024/1024:.1f} MB" if size > 0 else "--"
            self._library_table.setItem(i, 3, QTableWidgetItem(size_str))

            source = "上传" if v.get("source") == "upload" else "混剪"
            self._library_table.setItem(i, 4, QTableWidgetItem(source))
            self._library_table.setItem(i, 5, QTableWidgetItem(v.get("added_at", "")))

            # 删除按钮
            del_btn = QPushButton("删除")
            del_btn.setStyleSheet(f"color: {DANGER}; border: none; font-size: 12px;")
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            vid_id = v["id"]
            del_btn.clicked.connect(lambda _, vid=vid_id: self._delete_video(vid))
            self._library_table.setCellWidget(i, 6, del_btn)

    def _refresh_cut_queue(self):
        groups = dm.get_cut_groups()
        self._cut_table.setRowCount(len(groups))
        for i, g in enumerate(groups):
            self._cut_table.setItem(i, 0, QTableWidgetItem(g["name"]))
            self._cut_table.setItem(i, 1, QTableWidgetItem(str(g.get("video_count", 0))))

            rule = g.get("cut_rule", {})
            rule_text = f"{'段数' if rule.get('mode') == 'segments' else '时长'}: {rule.get('value', 0)}"
            self._cut_table.setItem(i, 2, QTableWidgetItem(rule_text))

            status_map = {"pending": "待裁切", "cutting": "裁切中", "done": "已完成", "error": "错误"}
            status_text = status_map.get(g.get("status", ""), g.get("status", ""))
            status_item = QTableWidgetItem(status_text)
            if g.get("status") == "done":
                status_item.setForeground(QColor(SUCCESS))
            elif g.get("status") == "cutting":
                status_item.setForeground(QColor(WARNING))
            elif g.get("status") == "error":
                status_item.setForeground(QColor(DANGER))
            self._cut_table.setItem(i, 3, status_item)

            progress = g.get("progress", 0)
            self._cut_table.setItem(i, 4, QTableWidgetItem(f"{progress}%"))

            # 操作按钮
            op_layout = QHBoxLayout()
            op_widget = QWidget()
            if g.get("status") == "pending":
                cut_btn = QPushButton("裁切")
                cut_btn.setStyleSheet(f"color: {PRIMARY}; border: none; font-size: 12px;")
                cut_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                gid = g["id"]
                cut_btn.clicked.connect(lambda _, gid=gid: self._start_cut(gid))
                op_layout.addWidget(cut_btn)

            del_btn = QPushButton("删除")
            del_btn.setStyleSheet(f"color: {DANGER}; border: none; font-size: 12px;")
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            gid = g["id"]
            del_btn.clicked.connect(lambda _, gid=gid: self._delete_cut_group(gid))
            op_layout.addWidget(del_btn)

            op_layout.addStretch()
            op_widget.setLayout(op_layout)
            self._cut_table.setCellWidget(i, 5, op_widget)

    def _refresh_baskets(self):
        baskets = dm.get_baskets()
        self._basket_combo.clear()
        for b in baskets:
            clip_count = len(b.get("clips", []))
            self._basket_combo.addItem(f"{b['name']} ({clip_count}个片段)", b["id"])

    def _on_basket_selected(self, index):
        basket_id = self._basket_combo.currentData()
        if not basket_id:
            self._basket_table.setRowCount(0)
            self._basket_status_label.setText("")
            return

        basket = dm.get_basket(basket_id)
        if not basket:
            return

        status_map = {"empty": "空", "ready": "就绪", "mixing": "混剪中", "done": "完成"}
        self._basket_status_label.setText(f"状态: {status_map.get(basket.get('status', ''), '')}")

        clips = basket.get("clips", [])
        self._basket_table.setRowCount(len(clips))
        for i, c in enumerate(clips):
            self._basket_table.setItem(i, 0, QTableWidgetItem(c.get("source_video", "")))
            self._basket_table.setItem(i, 1, QTableWidgetItem(str(c.get("segment_index", 0))))

            dur = c.get("duration", 0)
            dur_str = f"{int(dur//60)}:{int(dur%60):02d}" if dur > 0 else "--"
            self._basket_table.setItem(i, 2, QTableWidgetItem(dur_str))
            self._basket_table.setItem(i, 3, QTableWidgetItem(c.get("path", "")))
            self._basket_table.setItem(i, 4, QTableWidgetItem(c.get("id", "")))

    def _refresh_mix_queue(self):
        tasks = dm.get_mix_tasks()
        self._mix_table.setRowCount(len(tasks))
        for i, t in enumerate(tasks):
            # 篮子名
            basket = dm.get_basket(t.get("basket_id", ""))
            basket_name = basket["name"] if basket else "--"
            self._mix_table.setItem(i, 0, QTableWidgetItem(basket_name))

            self._mix_table.setItem(i, 1, QTableWidgetItem(str(t.get("segments_per_video", 1))))
            self._mix_table.setItem(i, 2, QTableWidgetItem(str(t.get("total", 0))))
            self._mix_table.setItem(i, 3, QTableWidgetItem(str(t.get("completed", 0))))

            status_map = {"pending": "待处理", "running": "混剪中", "done": "已完成", "error": "错误"}
            status_text = status_map.get(t.get("status", ""), t.get("status", ""))
            status_item = QTableWidgetItem(status_text)
            if t.get("status") == "done":
                status_item.setForeground(QColor(SUCCESS))
            elif t.get("status") == "running":
                status_item.setForeground(QColor(WARNING))
            self._mix_table.setItem(i, 4, status_item)

            # 操作
            op_layout = QHBoxLayout()
            op_widget = QWidget()
            if t.get("status") == "pending":
                mix_btn = QPushButton("混剪")
                mix_btn.setStyleSheet(f"color: {PRIMARY}; border: none; font-size: 12px;")
                mix_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                tid = t["id"]
                mix_btn.clicked.connect(lambda _, tid=tid: self._start_mix(tid))
                op_layout.addWidget(mix_btn)

            if t.get("status") == "done":
                export_btn = QPushButton("导出到视频库")
                export_btn.setStyleSheet(f"color: {SUCCESS}; border: none; font-size: 12px;")
                export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                tid = t["id"]
                export_btn.clicked.connect(lambda _, tid=tid: self._export_mix_to_library(tid))
                op_layout.addWidget(export_btn)

            del_btn = QPushButton("删除")
            del_btn.setStyleSheet(f"color: {DANGER}; border: none; font-size: 12px;")
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            tid = t["id"]
            del_btn.clicked.connect(lambda _, tid=tid: self._delete_mix_task(tid))
            op_layout.addWidget(del_btn)

            op_layout.addStretch()
            op_widget.setLayout(op_layout)
            self._mix_table.setCellWidget(i, 5, op_widget)

    # ══════════════════════════════════════════════════════════
    # 操作
    # ══════════════════════════════════════════════════════════

    def _upload_videos(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择视频文件", "",
            "视频文件 (*.mp4 *.avi *.mov *.mkv *.flv);;所有文件 (*)")
        if not files:
            return
        w = _UploadWorker(files)
        w.done.connect(lambda r: (Toast.success(self, f"上传成功，共 {len(r['videos'])} 个视频"), self._refresh_library()))
        w.failed.connect(lambda m: Toast.error(self, f"上传失败: {m}"))
        self._workers.append(w)
        w.start()

    def _add_to_cut_queue(self):
        # 获取选中的视频
        selected_ids = []
        for i in range(self._library_table.rowCount()):
            cb = self._library_table.cellWidget(i, 0)
            if cb and cb.isChecked():
                vid_name = self._library_table.item(i, 1).text()
                videos = dm.get_videos()
                for v in videos:
                    if v["name"] == vid_name:
                        selected_ids.append(v["id"])
                        break

        if not selected_ids:
            Toast.warning(self, "请先在视频库中勾选要裁切的视频")
            return

        group_name = self._group_name_input.text().strip()
        cut_mode = "segments" if self._cut_mode.currentIndex() == 0 else "duration"
        cut_value = self._cut_value.value()
        mix_segments = self._mix_segments.value()

        group = dm.create_cut_group(selected_ids, cut_mode, cut_value, mix_segments, group_name)
        Toast.success(self, f"裁切组「{group['name']}」已创建，共 {len(selected_ids)} 个视频")

        # 同时创建混剪任务
        dm.create_mix_task(group["basket_id"], mix_segments)

        self._group_name_input.clear()
        self._refresh_cut_queue()
        self._refresh_baskets()
        self._refresh_mix_queue()

    def _start_cut(self, group_id: str):
        w = _CutWorker(group_id)
        w.progress.connect(lambda msg, pct: (self._cut_progress.setValue(pct), ))
        w.done.connect(lambda gid: (Toast.success(self, "裁切完成!"), self._refresh_cut_queue(), self._refresh_baskets(), self._refresh_mix_queue()))
        w.failed.connect(lambda m: Toast.error(self, f"裁切失败: {m}"))
        self._workers.append(w)
        w.start()

    def _start_cut_selected(self):
        selected = self._cut_table.currentRow()
        if selected < 0:
            Toast.warning(self, "请先选择一个裁切组")
            return
        groups = dm.get_cut_groups()
        if selected < len(groups):
            group = groups[selected]
            if group["status"] != "pending":
                Toast.warning(self, "该组已在处理或已完成")
                return
            self._start_cut(group["id"])

    def _start_cut_all(self):
        groups = dm.get_cut_groups()
        pending = [g for g in groups if g["status"] == "pending"]
        if not pending:
            Toast.warning(self, "没有待处理的裁切组")
            return
        for g in pending:
            self._start_cut(g["id"])

    def _start_mix(self, task_id: str):
        w = _MixWorker(task_id)
        w.progress.connect(lambda msg, pct: (self._mix_progress.setValue(pct), ))
        w.done.connect(lambda tid: (Toast.success(self, "混剪完成!"), self._refresh_mix_queue()))
        w.failed.connect(lambda m: Toast.error(self, f"混剪失败: {m}"))
        self._workers.append(w)
        w.start()

    def _start_mix_selected(self):
        selected = self._mix_table.currentRow()
        if selected < 0:
            Toast.warning(self, "请先选择一个混剪任务")
            return
        tasks = dm.get_mix_tasks()
        if selected < len(tasks):
            task = tasks[selected]
            if task["status"] != "pending":
                Toast.warning(self, "该任务已在处理或已完成")
                return
            self._start_mix(task["id"])

    def _export_mix_to_library(self, task_id: str):
        """将混剪结果导出到视频库"""
        db = dm._load_db()
        results = [r for r in db.get("mixed_results", []) if r.get("task_id") == task_id]
        count = 0
        for r in results:
            if os.path.exists(r["path"]):
                dm.add_mixed_video(
                    basket_id="",
                    mix_name=r["name"],
                    file_path=r["path"],
                    clips_used=r.get("clip_ids", [])
                )
                count += 1
        Toast.success(self, f"已导出 {count} 个混剪视频到视频库")
        self._refresh_library()

    def _delete_video(self, vid_id: str):
        reply = QMessageBox.question(self, "确认删除", "确定要删除这个视频吗？",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            dm.delete_video(vid_id)
            self._refresh_library()

    def _delete_cut_group(self, group_id: str):
        reply = QMessageBox.question(self, "确认删除", "确定要删除这个裁切组及其篮子吗？",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            dm.delete_cut_group(group_id)
            self._refresh_cut_queue()
            self._refresh_baskets()
            self._refresh_mix_queue()

    def _delete_mix_task(self, task_id: str):
        reply = QMessageBox.question(self, "确认删除", "确定要删除这个混剪任务吗？",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            dm.delete_mix_task(task_id)
            self._refresh_mix_queue()
