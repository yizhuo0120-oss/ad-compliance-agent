"""卡9 · 视频通道原语：ffprobe 探时长、ffmpeg 抽帧、faster-whisper 语音转写。

编排逻辑见 pipeline.audit_video。ffmpeg/ffprobe 二进制优先取 tools/ 下静态包。
注意：ffmpeg 的 C 层不支持中文路径——所有输入输出统一经 ASCII 临时目录中转。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STAGE = Path(tempfile.gettempdir()) / "ad_ffmpeg"


def _bin(name: str) -> str:
    p = ROOT / "tools" / f"{name}.exe"
    return str(p) if p.exists() else name


def _stage(path: Path) -> Path:
    """把文件复制到 ASCII 临时目录（ffmpeg 只认这种路径）。目标名加唯一后缀防占用冲突。"""
    STAGE.mkdir(parents=True, exist_ok=True)
    dst = STAGE / f"{path.stem}-{time.time_ns() % 1000000}{path.suffix}"
    for attempt in range(5):  # 新建文件可能被 Defender 瞬时锁定，重试即可
        try:
            shutil.copy2(path, dst)
            return dst
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(1)


def video_duration(video: str | Path) -> float:
    """返回【视频流】时长（容器时长含纯音频尾巴，会让抽帧越过视频末端）。"""
    staged = _stage(Path(video))
    out = subprocess.run(
        [_bin("ffprobe"), "-v", "quiet", "-print_format", "json",
         "-select_streams", "v:0", "-show_streams", "-show_format", str(staged)],
        capture_output=True, text=True,
    ).stdout
    d = json.loads(out)
    for s in d.get("streams", []):
        if s.get("codec_type") == "video" and s.get("duration"):
            return float(s["duration"])
    return float(d["format"]["duration"])


def extract_frames(video: str | Path, max_frames: int = 6,
                   out_dir: Path | None = None) -> list[tuple[float, Path]]:
    """均匀采样抽帧（v1；场景切换检测是 D10+ 的升级项），返回 [(时间戳s, 帧图路径)]。"""
    video = Path(video)
    out_dir = out_dir or video.parent / "frames"
    out_dir.mkdir(parents=True, exist_ok=True)
    staged = _stage(video)
    dur = video_duration(staged)
    frames = []
    for i in range(max_frames):
        t = dur * (i + 0.5) / max_frames
        tmp = STAGE / f"{staged.stem}-f{i}.png"
        # -ss 放在 -i 之后（输出寻帧）：输入寻帧会吸附到稀疏关键帧导致画面错位
        subprocess.run(
            [_bin("ffmpeg"), "-y", "-i", str(staged), "-ss", f"{t:.2f}",
             "-frames:v", "1", "-update", "1", str(tmp)],
            check=True, capture_output=True,
        )
        final = out_dir / f"{video.stem}-f{i}.png"
        shutil.move(str(tmp), final)
        frames.append((round(t, 1), final))
    return frames


def transcribe_audio(video: str | Path, model_size: str | None = None) -> list[dict]:
    """faster-whisper 本地转写（中文），返回 [{start, end, text}]。免费零 API 成本。"""
    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    from faster_whisper import WhisperModel
    size = model_size or os.getenv("WHISPER_MODEL", "small")
    model = WhisperModel(size, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(str(video), language="zh", vad_filter=True)
    return [{"start": round(s.start, 1), "end": round(s.end, 1), "text": s.text.strip()}
            for s in segments if s.text.strip()]
