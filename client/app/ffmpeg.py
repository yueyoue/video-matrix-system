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
    """Download FFmpeg essentials (ffmpeg.exe + ffprobe.exe) from GitHub.

    Args:
        progress_callback: Optional function(percent, message) for progress updates

    Returns:
        True if download succeeded, False otherwise
    """
    _debug_log("[FFmpeg] 开始下载 FFmpeg...")
    LOCAL_FFMPEG_DIR.mkdir(parents=True, exist_ok=True)

    # Use a lightweight FFmpeg Windows build from GitHub
    # This is the essentials build (~30MB)
    url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"

    try:
        if progress_callback:
            progress_callback(0, "正在下载 FFmpeg...")

        _debug_log(f"[FFmpeg] 下载地址: {url}")
        req = Request(url, headers={'User-Agent': 'VideoMatrix/1.0'})

        # Download with progress
        response = urlopen(req, timeout=120)
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
        _debug_log(f"[FFmpeg] 下载失败: {e}")
        if progress_callback:
            progress_callback(0, f"下载失败: {e}")
        return False


_ffmpeg_path = None
_ffprobe_path = None

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

        cmd = [ffmpeg_path, '-y', '-ss', str(start), '-i', file_path,
               '-t', str(seg_duration), '-c', 'copy',
               '-avoid_negative_ts', 'make_zero', out_path]

        use_shell = os.name == 'nt'
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                                shell=use_shell,
                                creationflags=subprocess.CREATE_NO_WINDOW if use_shell else 0)
        if result.returncode != 0:
            raise RuntimeError(f"裁切失败: {(result.stderr or '')[:200]}")
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
        out_name = f"{base_name}_{segment_num}{ext}"
        out_path = os.path.join(output_dir, out_name)

        cmd = [ffmpeg_path, '-y', '-ss', str(start), '-i', file_path,
               '-t', str(segment_duration), '-c', 'copy',
               '-avoid_negative_ts', 'make_zero', out_path]

        use_shell = os.name == 'nt'
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                                shell=use_shell,
                                creationflags=subprocess.CREATE_NO_WINDOW if use_shell else 0)
        if result.returncode != 0:
            raise RuntimeError(f"裁切失败: {(result.stderr or '')[:200]}")
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

        cmd = [
            ffmpeg, '-y',
            '-ss', str(start),
            '-i', file_path,
            '-t', str(seg_duration),
            '-c', 'copy',
            '-avoid_negative_ts', 'make_zero',
            out_path
        ]

        _debug_log(f"[FFmpeg] 裁切第 {i+1} 段...")
        use_shell = os.name == 'nt'
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                                shell=use_shell,
                                creationflags=subprocess.CREATE_NO_WINDOW if use_shell else 0)
        if result.returncode != 0:
            _debug_log(f"[FFmpeg] 裁切失败: {result.stderr[:300]}")
            raise RuntimeError(f"裁切失败: {result.stderr[:200]}")

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

    cmd = [ffmpeg, '-y', '-f', 'concat', '-safe', '0', '-i', list_file]

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
            raise RuntimeError(f"混剪失败: {result.stderr[:200]}")
    finally:
        if os.path.exists(list_file):
            os.remove(list_file)

    return output_path
