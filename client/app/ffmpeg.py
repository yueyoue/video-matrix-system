"""Local FFmpeg video processing utilities."""

import os
import subprocess
import json
import shutil
from pathlib import Path
from datetime import datetime

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


# FFmpeg binary path - check common locations
def _find_ffmpeg() -> str:
    """Find FFmpeg binary path."""
    _debug_log("[FFmpeg] 开始查找 ffmpeg...")
    
    # Check if ffmpeg is in PATH via shutil.which
    found = shutil.which('ffmpeg')
    if found:
        _debug_log(f"[FFmpeg] 在 PATH 中找到 ffmpeg: {found}")
        return found
    
    # Check common Windows locations
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
    
    # Check local directory
    local = Path(__file__).parent.parent / 'ffmpeg' / 'ffmpeg.exe'
    if local.exists():
        _debug_log(f"[FFmpeg] 在本地目录找到 ffmpeg: {local}")
        return str(local)
    
    _debug_log("[FFmpeg] 未找到 ffmpeg，将尝试使用 'ffmpeg' 命令")
    return 'ffmpeg'


_ffmpeg = None

def get_ffmpeg() -> str:
    global _ffmpeg
    if _ffmpeg is None:
        _ffmpeg = _find_ffmpeg()
    return _ffmpeg


def _find_ffprobe() -> str:
    """Find ffprobe binary path."""
    _debug_log("[FFmpeg] 开始查找 ffprobe...")
    
    # Check if ffprobe is in PATH via shutil.which
    found = shutil.which('ffprobe')
    if found:
        _debug_log(f"[FFmpeg] 在 PATH 中找到 ffprobe: {found}")
        return found
    
    # Try replacing ffmpeg with ffprobe in the found ffmpeg path
    ffmpeg_path = get_ffmpeg()
    if ffmpeg_path and ffmpeg_path != 'ffmpeg':
        ffprobe_path = ffmpeg_path.replace('ffmpeg', 'ffprobe')
        if ffprobe_path != ffmpeg_path and os.path.exists(ffprobe_path):
            _debug_log(f"[FFmpeg] 通过 ffmpeg 路径推导出 ffprobe: {ffprobe_path}")
            return ffprobe_path
    
    # Check common Windows locations
    common_paths = [
        os.path.join(os.environ.get('PROGRAMFILES', ''), 'ffmpeg', 'bin', 'ffprobe.exe'),
        os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'ffmpeg', 'bin', 'ffprobe.exe'),
        os.path.join(os.path.expanduser('~'), 'ffmpeg', 'bin', 'ffprobe.exe'),
        os.path.join(os.path.expanduser('~'), 'AppData', 'Local', 'ffmpeg', 'bin', 'ffprobe.exe'),
        r'C:\ffmpeg\bin\ffprobe.exe',
        r'D:\ffmpeg\bin\ffprobe.exe',
    ]
    for p in common_paths:
        if p and os.path.exists(p):
            _debug_log(f"[FFmpeg] 在常见路径找到 ffprobe: {p}")
            return p
    
    # Check local directory
    local = Path(__file__).parent.parent / 'ffmpeg' / 'ffprobe.exe'
    if local.exists():
        _debug_log(f"[FFmpeg] 在本地目录找到 ffprobe: {local}")
        return str(local)
    
    _debug_log("[FFmpeg] 未找到 ffprobe，将尝试使用 'ffprobe' 命令")
    return 'ffprobe'


def get_duration(file_path: str) -> float:
    """Get video duration in seconds."""
    ffprobe = _find_ffprobe()
    _debug_log(f"[FFmpeg] 获取视频时长: {file_path}")
    _debug_log(f"[FFmpeg] 使用 ffprobe: {ffprobe}")
    
    try:
        result = subprocess.run(
            [ffprobe, '-v', 'quiet', '-print_format', 'json', '-show_format', file_path],
            capture_output=True, text=True, timeout=30
        )
        _debug_log(f"[FFmpeg] ffprobe 返回码: {result.returncode}")
        if result.returncode != 0:
            _debug_log(f"[FFmpeg] ffprobe stderr: {result.stderr[:300]}")
            raise RuntimeError(f"ffprobe 返回错误 (code {result.returncode}): {result.stderr[:200]}")
        info = json.loads(result.stdout)
        duration = float(info['format']['duration'])
        _debug_log(f"[FFmpeg] 视频时长: {duration}秒")
        return duration
    except FileNotFoundError as e:
        _debug_log(f"[FFmpeg] ffprobe 未找到: {e}")
        raise RuntimeError(f"找不到 ffprobe 程序 ({ffprobe})，请确保已安装 FFmpeg 并添加到 PATH")
    except (json.JSONDecodeError, KeyError) as e:
        _debug_log(f"[FFmpeg] 解析视频信息失败: {e}")
        _debug_log(f"[FFmpeg] ffprobe stdout: {result.stdout[:300]}")
        raise RuntimeError(f"解析视频信息失败: {e}")
    except subprocess.TimeoutExpired:
        _debug_log("[FFmpeg] ffprobe 超时")
        raise RuntimeError("ffprobe 超时，视频文件可能过大或损坏")
    except Exception as e:
        _debug_log(f"[FFmpeg] 未知错误: {type(e).__name__}: {e}")
        raise RuntimeError(f"获取视频时长失败: {e}")


def cut_video(file_path: str, segments: int, name_rule: str, output_dir: str = None) -> list:
    """Cut a video into equal segments using stream copy (fast, no re-encoding).

    Returns list of output file paths.
    """
    _debug_log(f"[FFmpeg] 开始裁切: {file_path}, 段数: {segments}")
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"视频文件不存在: {file_path}")

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
    ffmpeg = get_ffmpeg()

    for i in range(segments):
        start = i * seg_duration
        # Generate output filename
        name = name_rule.replace('{原名}', base_name).replace('{序号}', str(i + 1))
        if '{' in name:
            name = f"{base_name}_片段{i + 1}"
        out_path = os.path.join(output_dir, f"{name}{ext}")

        cmd = [
            ffmpeg, '-y',
            '-ss', str(start),
            '-i', file_path,
            '-t', str(seg_duration),
            '-c', 'copy',  # Stream copy - no re-encoding
            '-avoid_negative_ts', 'make_zero',
            out_path
        ]

        _debug_log(f"[FFmpeg] 裁切第 {i+1} 段: {' '.join(cmd[:6])}...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            _debug_log(f"[FFmpeg] 裁切失败: {result.stderr[:300]}")
            raise RuntimeError(f"裁切失败: {result.stderr[:200]}")

        outputs.append(out_path)
        _debug_log(f"[FFmpeg] 第 {i+1} 段完成: {out_path}")

    _debug_log(f"[FFmpeg] 裁切完成，共 {len(outputs)} 个片段")
    return outputs


def mix_videos(video_paths: list, output_path: str, bg_audio: str = None, volume: int = 50) -> str:
    """Concatenate multiple video clips into one.

    Returns output file path.
    """
    if not video_paths:
        raise ValueError("没有要混剪的视频")

    output_dir = os.path.dirname(output_path)
    os.makedirs(output_dir, exist_ok=True)

    # Create concat list file
    list_file = os.path.join(output_dir, '_concat_list.txt')
    with open(list_file, 'w', encoding='utf-8') as f:
        for vp in video_paths:
            f.write(f"file '{os.path.abspath(vp)}'\n")

    ffmpeg = get_ffmpeg()
    cmd = [ffmpeg, '-y', '-f', 'concat', '-safe', '0', '-i', list_file]

    if bg_audio and bg_audio != '无' and os.path.exists(bg_audio):
        cmd.extend(['-i', bg_audio, '-filter_complex',
                     f'[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=2,volume={volume/100}'])

    cmd.extend(['-c', 'copy', output_path])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            raise RuntimeError(f"混剪失败: {result.stderr[:200]}")
    finally:
        if os.path.exists(list_file):
            os.remove(list_file)

    return output_path
