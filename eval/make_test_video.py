"""卡9 · 合成测试视频：3 张幻灯片（4s/张，共 12s）+ 中文 TTS 口播。

构造真值（用于验证时间戳定位）：
  ~2.5s 画面「全场最低价」（违禁词） + 口播「全场最低价」
  ~10.5s 画面「行业第一品牌」（违禁词） + 口播「行业第一」
中间夹一张合规帧。所有产物写进 ASCII 临时目录（ffmpeg / System.Speech 均不认中文路径）。
用法：python eval/make_test_video.py
"""
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from engine.video_channel import _bin  # noqa: E402

STAGE = Path(tempfile.gettempdir()) / "ad_ffmpeg"  # ffmpeg 只认 ASCII 路径
OUT = ROOT / "data" / "test_video.mp4"
SLIDES = [
    ("限时促销\n全场最低价", (200, 30, 24)),
    ("天然维C\n每日一杯", (30, 110, 60)),
    ("行业第一品牌\n值得信赖", (60, 40, 90)),
]
TTS_TEXT = "家人们看过来，全场最低价，只有今天。这杯果汁，每天喝一杯，补充维C。我们品牌，行业第一，值得信赖。"


def main() -> None:
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 72)
    STAGE.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    staged_slides = []
    for i, (text, bg) in enumerate(SLIDES):
        img = Image.new("RGB", (960, 540), bg)
        d = ImageDraw.Draw(img)
        d.multiline_text((480, 270), text, font=font, fill=(255, 255, 255),
                         anchor="mm", align="center")
        p = STAGE / f"slide{i}.png"
        img.save(p)
        staged_slides.append(p)

    staged_wav = STAGE / "tts.wav"
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", str(ROOT / "tools" / "make_tts.ps1"), str(staged_wav), TTS_TEXT],
        check=True, capture_output=True,
    )
    print("TTS 口播完成（System.Speech）")

    concat = STAGE / "concat.txt"
    with concat.open("w", encoding="utf-8") as f:
        for p in staged_slides:
            seg = STAGE / (p.stem + ".mp4")
            # 每张幻灯片独立编码成 4s 片段（concat 对 PNG 的 duration 不可靠）
            subprocess.run(
                [_bin("ffmpeg"), "-y", "-loop", "1", "-i", str(p), "-t", "4",
                 "-r", "25", "-pix_fmt", "yuv420p", "-c:v", "libx264", str(seg)],
                check=True, capture_output=True,
            )
            f.write(f"file '{seg.as_posix()}'\n")

    out_staged = STAGE / "test_video.mp4"
    subprocess.run(
        [_bin("ffmpeg"), "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
         "-i", str(staged_wav), "-c:v", "libx264", "-c:a", "aac",
         "-map", "0:v:0", "-map", "1:a:0", str(out_staged)],
        check=True, capture_output=True,
    )
    shutil.move(str(out_staged), OUT)
    print(f"测试视频已生成：{OUT}（{time.time() - t0:.0f}s）")


if __name__ == "__main__":
    main()
