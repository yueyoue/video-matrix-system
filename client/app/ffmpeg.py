"""Local FFmpeg video processing utilities."""

import os
import subprocess
import json
from pathlib import Path

# FFmpeg binary path - check common locations
def _find_ffmpeg() -> str:
    """Find FFmpeg binary path."""
    # Check if ffmpeg is in PATH
    for p in ['ffmpeg', 'ffmpeg.exe']:
        try:
            subprocess.run([p, '-version'], capture_output=True, timeout=5)
            return p
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    # Check local directory
    local = Path(__file__).parent.parent / 'ffmpeg' / 'ffmpeg.exe'
    if local.exists():
        return str(local)
    return 'ffmpeg'  # Hope it's in PATH


_ffmpeg = None

def get_ffmpeg() -> str:
    global _ffmpeg
    if _ffmpeg is None:
        _ffmpeg = _find_ffmpeg()
    return _ffmpeg


def _find_ffprobe() -> str:
    """Find ffprobe binary path."""
    # Try ffprobe in PATH first
    for p in ['ffprobe', 'ffprobe.exe']:
        try:
            subprocess.run([p, '-version'], capture_output=True, timeout=5)
            return p
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    # Try replacing ffmpeg with ffprobe in the found ffmpeg path
    ffmpeg_path = get_ffmpeg()
    ffprobe_path = ffmpeg_path.replace('ffmpeg', 'ffprobe')
    if ffprobe_path != ffmpeg_path:
        try:
            subprocess.run([ffprobe_path, '-version'], capture_output=True, timeout=5)
            return ffprobe_path
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    # Try local directory
    local = Path(__file__).parent.parent / 'ffmpeg' / 'ffprobe.exe'
    if local.exists():
        return str(local)
    return 'ffprobe'  # Hope it's in PATH


def get_duration(file_path: str) -> float:
    """Get video duration in seconds."""
    ffprobe = _find_ffprobe()
    try:
        result = subprocess.run(
            [ffprobe, '-v', 'quiet', '-print_format', 'json', '-show_format', file_path],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe 返回错误: {result.stderr[:200]}")
        info = json.loads(result.stdout)
        return float(info['format']['duration'])
    except FileNotFoundError:
        raise RuntimeError(f"找不到 ffprobe 程序，请确保已安装 FFmpeg 并添加到 PATH")
    except (json.JSONDecodeError, KeyError) as e:
        raise RuntimeError(f"解析视频信息失败: {e}")
    except subprocess.TimeoutExpired:
        raise RuntimeError("ffprobe 超时，视频文件可能过大或损坏")


def cut_video(file_path: str, segments: int, name_rule: str, output_dir: str = None) -> list:
    """Cut a video into equal segments using stream copy (fast, no re-encoding).

    Returns list of output file paths.
    """
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

    for i in range(segments):
        start = i * seg_duration
        # Generate output filename
        name = name_rule.replace('{原名}', base_name).replace('{序号}', str(i + 1))
        if '{' in name:
            name = f"{base_name}_片段{i + 1}"
        out_path = os.path.join(output_dir, f"{name}{ext}")

        cmd = [
            get_ffmpeg(), '-y',
            '-ss', str(start),
            '-i', file_path,
            '-t', str(seg_duration),
            '-c', 'copy',  # Stream copy - no re-encoding
            '-avoid_negative_ts', 'make_zero',
            out_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"裁切失败: {result.stderr[:200]}")

        outputs.append(out_path)

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

    cmd = [get_ffmpeg(), '-y', '-f', 'concat', '-safe', '0', '-i', list_file]

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
