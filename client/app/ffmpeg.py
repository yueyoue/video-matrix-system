"""Local FFmpeg video processing utilities with auto-download."""

import os
import subprocess
import json
import shutil
import zipfile
import io
from pathlib import Path
from datetime import datetime
from urllib.request import urlopen, Request

# Debug logging
_debug_log_path = os.path.join(os.path.expanduser('~'), '.video-matrix', 'debug.log')

def _debug_log(msg: str):
    """Write debug info to log file."""
    try:
        os.makedirs(os.path.dirname(_debug_log_path), exist_ok=True)
        with open(_debug_log_path, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


# Local FFmpeg directory
LOCAL_FFMPEG_DIR = Path.home() / '.video-matrix' / 'ffmpeg'


def _find_ffmpeg() -> str:
    """Find FFmpeg binary path."""
    _debug_log("[FFmpeg] 开始查找 ffmpeg...")

    # 1. Check local downloaded copy first
    local_ffmpeg = LOCAL_FFMPEG_DIR / 'ffmpeg.exe'
    if local_ffmpeg.exists():
        _debug_log(f"[FFmpeg] 找到本地 ffmpeg: {local_ffmpeg}")
        return str(local_ffmpeg)

    # 2. Check if ffmpeg is in PATH
    found = shutil.which('ffmpeg')
    if found:
        _debug_log(f"[FFmpeg] 在 PATH 中找到 ffmpeg: {found}")
        return found

    # 3. Check common Windows locations
    common_paths = [
        os.path.join(os.environ.get('PROGRAMFILES', ''), 'ffmpeg', 'bin', 'ffmpeg.exe'),
        os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'ffmpeg', 'bin', 'ffmpeg.exe'),
        os.path.join(os.path.expanduser('~'), 'ffmpeg', 'bin', 'ffmpeg.exe'),
        os.path.join(os.path.expanduser('~'), 'AppData', 'Local', 'ffmpeg', 'bin', 'ffmpeg.exe'),
        r'C:\ffmpeg\bin\ffmpeg.exe',
        r'D:\ffmpeg\bin\ffmpeg.exe',
    ]
    for p in common_paths:
        if p and os.path.exists(p):
            _debug_log(f"[FFmpeg] 在常见路径找到 ffmpeg: {p}")
            return p

    # 4. Check app directory
    local = Path(__file__).parent.parent / 'ffmpeg' / 'ffmpeg.exe'
    if local.exists():
        _debug_log(f"[FFmpeg] 在应用目录找到 ffmpeg: {local}")
        return str(local)

    _debug_log("[FFmpeg] 未找到 ffmpeg")
    return ''


def _find_ffprobe() -> str:
    """Find ffprobe binary path."""
    _debug_log("[FFmpeg] 开始查找 ffprobe...")

    # 1. Check local downloaded copy first
    local_ffprobe = LOCAL_FFMPEG_DIR / 'ffprobe.exe'
    if local_ffprobe.exists():
        _debug_log(f"[FFmpeg] 找到本地 ffprobe: {local_ffprobe}")
        return str(local_ffprobe)

    # 2. Check if ffprobe is in PATH
    found = shutil.which('ffprobe')
    if found:
        _debug_log(f"[FFmpeg] 在 PATH 中找到 ffprobe: {found}")
        return found

    # 3. Try from ffmpeg location
    ffmpeg_path = _find_ffmpeg()
    if ffmpeg_path and os.path.exists(ffmpeg_path):
        ffprobe_path = os.path.join(os.path.dirname(ffmpeg_path), 'ffprobe.exe')
        if os.path.exists(ffprobe_path):
            _debug_log(f"[FFmpeg] 通过 ffmpeg 路径找到 ffprobe: {ffprobe_path}")
            return ffprobe_path

    _debug_log("[FFmpeg] 未找到 ffprobe")
    return ''


def is_ffmpeg_available() -> bool:
    """Check if FFmpeg is actually working (not just file exists)."""
    ffprobe = _find_ffprobe()
    if not ffprobe or not os.path.exists(ffprobe):
        return False
    try:
        use_shell = os.name == 'nt'
        result = subprocess.run(
            [ffprobe, '-version'],
            capture_output=True, text=True, timeout=10,
            shell=use_shell,
            creationflags=subprocess.CREATE_NO_WINDOW if use_shell else 0
        )
        return result.returncode == 0 and 'ffprobe' in (result.stdout or '')
    except Exception as e:
        _debug_log(f"[FFmpeg] ffprobe 验证失败: {e}")
        return False


def download_ffmpeg(progress_callback=None) -> bool:
    """Download FFmpeg essentials (ffmpeg.exe + ffprobe.exe) with multiple mirror fallbacks.

    Args:
        progress_callback: Optional function(percent, message) for progress updates

    Returns:
        True if download succeeded, False otherwise
    """
    _debug_log("[FFmpeg] 开始下载 FFmpeg...")
    LOCAL_FFMPEG_DIR.mkdir(parents=True, exist_ok=True)

    # 多个下载源，按优先级排列（国内镜像优先）
    urls = [
        # GitHub 直连（通过 ghproxy 代理加速）
        "https://mirror.ghproxy.com/https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
        # GitHub 直连
        "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
        # gyan.dev  essentials build
        "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
        # 备用：GitHub release 版本
        "https://mirror.ghproxy.com/https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-n7.1-latest-win64-gpl-7.1.zip",
    ]

    last_error = None
    for url_idx, url in enumerate(urls):
        try:
            if progress_callback:
                source_name = "镜像加速" if "ghproxy" in url else ("gyan.dev" if "gyan" in url else "GitHub")
                progress_callback(0, f"正在从 {source_name} 下载 FFmpeg... ({url_idx+1}/{len(urls)})")

            _debug_log(f"[FFmpeg] 尝试下载源 {url_idx+1}: {url}")
            req = Request(url, headers={'User-Agent': 'VideoMatrix/1.0'})

            # Download with progress
            response = urlopen(req, timeout=180)
            total_size = int(response.headers.get('Content-Length', 0))
            downloaded = 0
            chunks = []

            while True:
                chunk = response.read(8192)
                if not chunk:
                    break
                chunks.append(chunk)
                downloaded += len(chunk)
                if total_size > 0 and progress_callback:
                    percent = int(downloaded * 100 / total_size)
                    progress_callback(min(percent, 90), f"正在下载 FFmpeg... {percent}%")

            if progress_callback:
                progress_callback(90, "正在解压 FFmpeg...")

            _debug_log(f"[FFmpeg] 下载完成，大小: {downloaded} 字节，正在解压...")

            # Extract ffmpeg.exe and ffprobe.exe
            data = b''.join(chunks)
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                for name in zf.namelist():
                    if name.endswith('ffmpeg.exe') or name.endswith('ffprobe.exe'):
                        # Extract to local dir
                        basename = os.path.basename(name)
                        target = LOCAL_FFMPEG_DIR / basename
                        with zf.open(name) as src, open(target, 'wb') as dst:
                            dst.write(src.read())
                        _debug_log(f"[FFmpeg] 解压: {basename}")

            if progress_callback:
                progress_callback(100, "FFmpeg 安装完成!")

            _debug_log("[FFmpeg] FFmpeg 下载安装成功")
            return True

        except Exception as e:
            last_error = e
            _debug_log(f"[FFmpeg] 下载源 {url_idx+1} 失败: {e}")
            if progress_callback:
                progress_callback(0, f"下载源 {url_idx+1} 失败，尝试下一个...")
            continue

    _debug_log(f"[FFmpeg] 所有下载源均失败，最后错误: {last_error}")
    if progress_callback:
        progress_callback(0, f"所有下载源均失败: {last_error}")
    return False


_ffmpeg_path = None
_ffprobe_path = None
_hw_encoder_cache = None  # 缓存硬件编码器检测结果

def get_ffmpeg() -> str:
    global _ffmpeg_path
    if _ffmpeg_path is None:
        _ffmpeg_path = _find_ffmpeg()
    return _ffmpeg_path


def get_ffprobe() -> str:
    global _ffprobe_path
    if _ffprobe_path is None:
        _ffprobe_path = _find_ffprobe()
    return _ffprobe_path


def detect_hw_encoder() -> str:
    """检测可用的硬件视频编码器，返回最佳编码器名称。
    
    优先级：NVIDIA NVENC > AMD AMF > Intel QSV > CPU (libx264)
    
    Returns:
        编码器名称字符串，如 'h264_nvenc', 'h264_amf', 'h264_qsv', 'libx264'
    """
    global _hw_encoder_cache
    if _hw_encoder_cache is not None:
        return _hw_encoder_cache

    ffmpeg_path = get_ffmpeg()
    if not ffmpeg_path:
        _hw_encoder_cache = 'libx264'
        return _hw_encoder_cache

    # 硬件编码器优先级列表
    hw_encoders = [
        ('h264_nvenc',  'NVIDIA NVENC (GPU)'),
        ('h264_amf',    'AMD AMF (GPU)'),
        ('h264_qsv',    'Intel QSV (GPU)'),
    ]

    try:
        use_shell = os.name == 'nt'
        result = subprocess.run(
            [ffmpeg_path, '-encoders'],
            capture_output=True, text=True, timeout=15,
            shell=use_shell,
            creationflags=subprocess.CREATE_NO_WINDOW if use_shell else 0
        )
        output = result.stdout or ''

        for encoder_name, encoder_desc in hw_encoders:
            if encoder_name in output:
                _debug_log(f"[FFmpeg] 检测到硬件编码器: {encoder_desc} ({encoder_name})")
                _hw_encoder_cache = encoder_name
                return _hw_encoder_cache

    except Exception as e:
        _debug_log(f"[FFmpeg] 硬件编码器检测失败: {e}")

    _debug_log("[FFmpeg] 未检测到硬件编码器，使用 CPU 编码 (libx264)")
    _hw_encoder_cache = 'libx264'
    return _hw_encoder_cache


def get_encoder_info() -> dict:
    """获取当前编码器信息，用于UI显示。
    
    Returns:
        {"encoder": str, "type": "GPU"|"CPU", "name": str}
    """
    encoder = detect_hw_encoder()
    encoder_names = {
        'h264_nvenc': 'NVIDIA NVENC',
        'h264_amf':   'AMD AMF',
        'h264_qsv':   'Intel QSV',
        'libx264':    'CPU 软编码',
    }
    return {
        'encoder': encoder,
        'type': 'GPU' if encoder != 'libx264' else 'CPU',
        'name': encoder_names.get(encoder, encoder),
    }


def ensure_ffmpeg(progress_callback=None) -> bool:
    """Ensure FFmpeg is available, download if needed.

    Returns:
        True if FFmpeg is available (either found or downloaded)
    """
    global _ffmpeg_path, _ffprobe_path

    if is_ffmpeg_available():
        return True

    _debug_log("[FFmpeg] FFmpeg 未找到，尝试自动下载...")
    if download_ffmpeg(progress_callback):
        # Refresh paths
        _ffmpeg_path = _find_ffmpeg()
        _ffprobe_path = _find_ffprobe()
        return is_ffmpeg_available()

    return False


def get_duration(file_path: str) -> float:
    """Get video duration in seconds."""
    ffprobe = get_ffprobe()
    if not ffprobe:
        raise RuntimeError("找不到 ffprobe 程序，请在设置中点击「下载 FFmpeg」或手动安装")

    _debug_log(f"[FFmpeg] 获取视频时长: {file_path}")
    _debug_log(f"[FFmpeg] 使用 ffprobe: {ffprobe}")

    try:
        # On Windows, use shell=True for better compatibility with Chinese paths
        use_shell = os.name == 'nt'
        # Quote the file path to handle spaces and Chinese characters
        cmd = [ffprobe, '-v', 'quiet', '-print_format', 'json', '-show_format', file_path]
        _debug_log(f"[FFmpeg] 执行命令: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=30,
            shell=use_shell,
            creationflags=subprocess.CREATE_NO_WINDOW if use_shell else 0
        )
        _debug_log(f"[FFmpeg] ffprobe 返回码: {result.returncode}")
        _debug_log(f"[FFmpeg] ffprobe stdout长度: {len(result.stdout or '')}")
        _debug_log(f"[FFmpeg] ffprobe stderr: {(result.stderr or '')[:300]}")
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe 返回错误 (code {result.returncode}): {(result.stderr or '')[:200]}")
        if not result.stdout or not result.stdout.strip():
            # Try alternative approach: write output to temp file
            _debug_log("[FFmpeg] stdout为空，尝试写入临时文件方式...")
            import tempfile
            tmp = os.path.join(tempfile.gettempdir(), 'ffprobe_out.json')
            cmd2 = f'"{ffprobe}" -v quiet -print_format json -show_format "{file_path}" > "{tmp}"'
            subprocess.run(cmd2, shell=True, timeout=30,
                          creationflags=subprocess.CREATE_NO_WINDOW)
            if os.path.exists(tmp):
                with open(tmp, 'r', encoding='utf-8') as f:
                    result_stdout = f.read()
                os.remove(tmp)
                if result_stdout.strip():
                    info = json.loads(result_stdout)
                    duration = float(info['format']['duration'])
                    _debug_log(f"[FFmpeg] 视频时长(临时文件方式): {duration}秒")
                    return duration
            raise RuntimeError(f"ffprobe 没有输出，请检查文件是否存在: {file_path}")
        info = json.loads(result.stdout)
        duration = float(info['format']['duration'])
        _debug_log(f"[FFmpeg] 视频时长: {duration}秒")
        return duration
    except FileNotFoundError:
        _debug_log(f"[FFmpeg] ffprobe 未找到: {ffprobe}")
        raise RuntimeError("找不到 ffprobe 程序，请在设置中点击「下载 FFmpeg」或手动安装")
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        _debug_log(f"[FFmpeg] 解析视频信息失败: {e}")
        _debug_log(f"[FFmpeg] ffprobe stdout: {(result.stdout or 'None')[:300]}")
        raise RuntimeError(f"解析视频信息失败: {e}")
    except subprocess.TimeoutExpired:
        _debug_log("[FFmpeg] ffprobe 超时")
        raise RuntimeError("ffprobe 超时，视频文件可能过大或损坏")
    except Exception as e:
        _debug_log(f"[FFmpeg] 未知错误: {type(e).__name__}: {e}")
        raise RuntimeError(f"获取视频时长失败: {e}")


def cut_video_segments(file_path: str, segments: int, output_dir: str, base_name: str = None) -> list:
    """将视频平均分成N段，返回输出文件路径列表"""
    _debug_log(f"[FFmpeg] 按段数裁切: {file_path}, 段数: {segments}")

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"视频文件不存在: {file_path}")

    ffmpeg_path = get_ffmpeg()
    if not ffmpeg_path:
        raise RuntimeError("找不到 ffmpeg 程序")

    duration = get_duration(file_path)
    if duration <= 0:
        raise ValueError("无法获取视频时长")

    os.makedirs(output_dir, exist_ok=True)
    if base_name is None:
        base_name = Path(file_path).stem
    ext = Path(file_path).suffix
    seg_duration = duration / segments
    outputs = []

    for i in range(segments):
        start = i * seg_duration
        out_name = f"{base_name}_{i+1}{ext}"
        out_path = os.path.join(output_dir, out_name)

        # 使用 trim 滤镜精确裁切（最可靠的方案）
        # 自动检测硬件编码器（GPU优先，CPU回退）
        venc = detect_hw_encoder()
        end = start + seg_duration
        cmd = [ffmpeg_path, '-y', '-hide_banner', '-loglevel', 'error',
               '-i', file_path,
               '-vf', f'trim=start={start}:end={end},setpts=PTS-STARTPTS',
               '-af', f'atrim=start={start}:end={end},asetpts=PTS-STARTPTS',
               '-c:v', venc, '-c:a', 'aac', out_path]
        # 硬件编码器需要额外参数
        if venc == 'h264_nvenc':
            cmd.extend(['-preset', 'p4', '-rc', 'vbr'])
        elif venc == 'h264_qsv':
            cmd.extend(['-preset', 'medium'])

        use_shell = os.name == 'nt'
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600,
                                shell=use_shell,
                                creationflags=subprocess.CREATE_NO_WINDOW if use_shell else 0)
        if result.returncode != 0:
            err_msg = (result.stderr or '').strip()
            _debug_log(f"[FFmpeg] 裁切第{i+1}段失败: {err_msg[:500]}")
            raise RuntimeError(f"裁切失败: {err_msg[:500] or '未知错误'}")
        outputs.append(out_path)

    _debug_log(f"[FFmpeg] 裁切完成，共 {len(outputs)} 个片段")
    return outputs


def cut_video_by_duration(file_path: str, segment_duration: float, output_dir: str, base_name: str = None) -> list:
    """按时长裁切视频（每N秒一段），返回输出文件路径列表"""
    _debug_log(f"[FFmpeg] 按时长裁切: {file_path}, 每段{segment_duration}秒")

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"视频文件不存在: {file_path}")

    ffmpeg_path = get_ffmpeg()
    if not ffmpeg_path:
        raise RuntimeError("找不到 ffmpeg 程序")

    duration = get_duration(file_path)
    if duration <= 0:
        raise ValueError("无法获取视频时长")

    os.makedirs(output_dir, exist_ok=True)
    if base_name is None:
        base_name = Path(file_path).stem
    ext = Path(file_path).suffix
    outputs = []
    start = 0
    segment_num = 1

    while start < duration:
        # 计算本段实际时长（最后一段可能不足 segment_duration）
        actual_duration = min(segment_duration, duration - start)
        out_name = f"{base_name}_{segment_num}{ext}"
        out_path = os.path.join(output_dir, out_name)

        # 使用 trim 滤镜精确裁切（最可靠的方案）
        # 自动检测硬件编码器（GPU优先，CPU回退）
        venc = detect_hw_encoder()
        end = start + actual_duration
        cmd = [ffmpeg_path, '-y', '-hide_banner', '-loglevel', 'error',
               '-i', file_path,
               '-vf', f'trim=start={start}:end={end},setpts=PTS-STARTPTS',
               '-af', f'atrim=start={start}:end={end},asetpts=PTS-STARTPTS',
               '-c:v', venc, '-c:a', 'aac', out_path]
        # 硬件编码器需要额外参数
        if venc == 'h264_nvenc':
            cmd.extend(['-preset', 'p4', '-rc', 'vbr'])
        elif venc == 'h264_qsv':
            cmd.extend(['-preset', 'medium'])

        use_shell = os.name == 'nt'
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600,
                                shell=use_shell,
                                creationflags=subprocess.CREATE_NO_WINDOW if use_shell else 0)
        if result.returncode != 0:
            err_msg = (result.stderr or '').strip()
            _debug_log(f"[FFmpeg] 裁切第{segment_num}段失败: {err_msg[:500]}")
            raise RuntimeError(f"裁切失败: {err_msg[:500] or '未知错误'}")
        outputs.append(out_path)
        start += segment_duration
        segment_num += 1

    _debug_log(f"[FFmpeg] 裁切完成，共 {len(outputs)} 个片段")
    return outputs


def cut_video(file_path: str, segments: int, name_rule: str, output_dir: str = None) -> list:
    """Cut a video into equal segments using stream copy (fast, no re-encoding)."""
    _debug_log(f"[FFmpeg] 开始裁切: {file_path}, 段数: {segments}")

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"视频文件不存在: {file_path}")

    ffmpeg = get_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("找不到 ffmpeg 程序，请在设置中点击「下载 FFmpeg」或手动安装")

    duration = get_duration(file_path)
    if duration <= 0:
        raise ValueError("无法获取视频时长")

    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(file_path), 'clips')
    os.makedirs(output_dir, exist_ok=True)

    base_name = Path(file_path).stem
    ext = Path(file_path).suffix
    seg_duration = duration / segments
    outputs = []

    for i in range(segments):
        start = i * seg_duration
        name = name_rule.replace('{原名}', base_name).replace('{序号}', str(i + 1))
        if '{' in name:
            name = f"{base_name}_片段{i + 1}"
        out_path = os.path.join(output_dir, f"{name}{ext}")

        # 使用 trim 滤镜精确裁切（最可靠的方案）
        # 自动检测硬件编码器（GPU优先，CPU回退）
        venc = detect_hw_encoder()
        end = start + seg_duration
        cmd = [
            ffmpeg, '-y', '-hide_banner', '-loglevel', 'error',
            '-i', file_path,
            '-vf', f'trim=start={start}:end={end},setpts=PTS-STARTPTS',
            '-af', f'atrim=start={start}:end={end},asetpts=PTS-STARTPTS',
            '-c:v', venc, '-c:a', 'aac',
            out_path
        ]
        # 硬件编码器需要额外参数
        if venc == 'h264_nvenc':
            cmd.extend(['-preset', 'p4', '-rc', 'vbr'])
        elif venc == 'h264_qsv':
            cmd.extend(['-preset', 'medium'])

        _debug_log(f"[FFmpeg] 裁切第 {i+1} 段...")
        use_shell = os.name == 'nt'
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                                shell=use_shell,
                                creationflags=subprocess.CREATE_NO_WINDOW if use_shell else 0)
        if result.returncode != 0:
            err_msg = (result.stderr or '').strip()
            _debug_log(f"[FFmpeg] 裁切第{i+1}段失败: {err_msg[:500]}")
            raise RuntimeError(f"裁切失败: {err_msg[:500] or '未知错误'}")

        outputs.append(out_path)
        _debug_log(f"[FFmpeg] 第 {i+1} 段完成: {out_path}")

    _debug_log(f"[FFmpeg] 裁切完成，共 {len(outputs)} 个片段")
    return outputs


def mix_videos(video_paths: list, output_path: str, bg_audio: str = None, volume: int = 50) -> str:
    """Concatenate multiple video clips into one."""
    if not video_paths:
        raise ValueError("没有要混剪的视频")

    ffmpeg = get_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("找不到 ffmpeg 程序，请在设置中点击「下载 FFmpeg」或手动安装")

    output_dir = os.path.dirname(output_path)
    os.makedirs(output_dir, exist_ok=True)

    list_file = os.path.join(output_dir, '_concat_list.txt')
    with open(list_file, 'w', encoding='utf-8') as f:
        for vp in video_paths:
            f.write(f"file '{os.path.abspath(vp)}'\n")

    cmd = [ffmpeg, '-y', '-hide_banner', '-loglevel', 'error',
           '-f', 'concat', '-safe', '0', '-i', list_file]

    if bg_audio and bg_audio != '无' and os.path.exists(bg_audio):
        cmd.extend(['-i', bg_audio, '-filter_complex',
                     f'[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=2,volume={volume/100}'])

    cmd.extend(['-c', 'copy', output_path])

    try:
        use_shell = os.name == 'nt'
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600,
                                shell=use_shell,
                                creationflags=subprocess.CREATE_NO_WINDOW if use_shell else 0)
        if result.returncode != 0:
            err_msg = (result.stderr or '').strip()
            raise RuntimeError(f"混剪失败: {err_msg[:500] or '未知错误'}")
    finally:
        if os.path.exists(list_file):
            os.remove(list_file)

    return output_path


def add_subtitle(video_path: str, text: str, position: str = 'bottom'):
    """给视频添加文字字幕（使用 drawtext 滤镜）"""
    if not text:
        return
    ffprobe = get_ffmpeg()
    if not ffprobe:
        return
    import tempfile
    tmp_out = video_path + '.sub.mp4'
    safe_text = text.replace("'", "'" * 2).replace(":", "\\:")
    y_pos = 'h-th-20' if position == 'bottom' else '20'
    filter_str = f"drawtext=text='{safe_text}':fontsize=24:fontcolor=white:borderw=2:bordercolor=black:x=(w-tw)/2:y={y_pos}"
    cmd = [ffprobe, '-y', '-hide_banner', '-loglevel', 'error',
           '-i', video_path, '-vf', filter_str, '-c:a', 'copy', tmp_out]
    use_shell = os.name == 'nt'
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                            shell=use_shell,
                            creationflags=subprocess.CREATE_NO_WINDOW if use_shell else 0)
    if result.returncode == 0:
        os.replace(tmp_out, video_path)
    elif os.path.exists(tmp_out):
        os.remove(tmp_out)


def insert_audio(video_path: str, audio_path: str, position: str = "head", fixed_time: float = 5):
    """将音频插入到视频的指定位置
    position: head(片头), tail(片尾), random(随机), fixed(固定时间点)
    """
    if not audio_path or not os.path.exists(audio_path):
        return
    ffmpeg_path = get_ffmpeg()
    if not ffmpeg_path:
        return

    duration = get_duration(video_path)
    audio_dur = 0
    try:
        audio_dur = get_duration(audio_path)
    except Exception:
        pass

    tmp_out = video_path + '.audio.mp4'

    if position == "head":
        # 片头：音频放在视频开头
        cmd = [ffmpeg_path, '-y', '-hide_banner', '-loglevel', 'error',
               '-i', audio_path, '-i', video_path,
               '-filter_complex',
               f'[0:a]apad=pad_dur={duration}[a0];[1:a][a0]amix=inputs=2:duration=first:dropout_transition=0[aout]',
               '-map', '1:v', '-map', '[aout]', '-c:v', 'copy', '-shortest', tmp_out]
    elif position == "tail":
        # 片尾：音频放在视频末尾
        cmd = [ffmpeg_path, '-y', '-hide_banner', '-loglevel', 'error',
               '-i', video_path, '-i', audio_path,
               '-filter_complex',
               f'[0:a]apad=pad_dur={duration + audio_dur}[a0];[a0][1:a]amix=inputs=2:duration=longest:dropout_transition=0[aout]',
               '-map', '0:v', '-map', '[aout]', '-c:v', 'copy', '-shortest', tmp_out]
    elif position == "fixed":
        # 固定时间点插入
        cmd = [ffmpeg_path, '-y', '-hide_banner', '-loglevel', 'error',
               '-i', video_path, '-i', audio_path,
               '-filter_complex',
               f'[1:a]adelay={int(fixed_time*1000)}|{int(fixed_time*1000)}[delayed];[0:a][delayed]amix=inputs=2:duration=first:dropout_transition=0[aout]',
               '-map', '0:v', '-map', '[aout]', '-c:v', 'copy', '-shortest', tmp_out]
    else:
        # random - 在随机时间点插入
        import random as _rnd
        rand_t = _rnd.uniform(1, max(1, duration - audio_dur - 1))
        cmd = [ffmpeg_path, '-y', '-hide_banner', '-loglevel', 'error',
               '-i', video_path, '-i', audio_path,
               '-filter_complex',
               f'[1:a]adelay={int(rand_t*1000)}|{int(rand_t*1000)}[delayed];[0:a][delayed]amix=inputs=2:duration=first:dropout_transition=0[aout]',
               '-map', '0:v', '-map', '[aout]', '-c:v', 'copy', '-shortest', tmp_out]

    try:
        use_shell = os.name == 'nt'
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                                shell=use_shell,
                                creationflags=subprocess.CREATE_NO_WINDOW if use_shell else 0)
        if result.returncode == 0:
            os.replace(tmp_out, video_path)
        elif os.path.exists(tmp_out):
            os.remove(tmp_out)
    except Exception:
        if os.path.exists(tmp_out):
            os.remove(tmp_out)
