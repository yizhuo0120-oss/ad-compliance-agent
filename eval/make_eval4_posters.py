"""补充 4 张评测海报：2 张明确违规 + 2 张疑似边缘（D9 口径：边缘表达转人工）。

直接输出到 data/eval_images/，命名 eval4_*。真值标注见 finalize_annotations.py SYNTHETIC。
用法：python eval/make_eval4_posters.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from engine.video_channel import STAGE  # noqa: E402  复用 ASCII 中转目录常量（本脚本仅 PIL，无 ffmpeg）

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

OUT = ROOT / "data" / "eval_images"
OUT.mkdir(parents=True, exist_ok=True)
FONT = "C:/Windows/Fonts/msyh.ttc"


def f(size):
    return ImageFont.truetype(FONT, size)


def poster(name, bg, lines):
    """lines: [(text, size, color, dy)]，垂直流式排版。"""
    W, H = 800, 600
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    total = sum(h for _, _, _, h in lines)
    y = (H - total) // 2
    for text, size, color, gap in lines:
        d.text((W // 2, y), text, font=f(size), fill=color, anchor="ma")
        y += size + gap
    img.save(OUT / name)
    print("OK", name)


# ① 违规：极限词（广告法·第九条）
poster(
    "eval4_violation_extreme.png", (200, 30, 24),
    [
        ("双11狂欢价", 40, (255, 220, 120), 40),
        ("全年最低价", 84, (255, 230, 60), 30),
        ("销量遥遥领先", 52, (255, 255, 255), 36),
        ("国家级品质保障", 40, (255, 255, 255), 0),
    ],
)

# ② 违规：医疗功效（广告法·第十七条）
poster(
    "eval4_violation_medical.png", (28, 90, 120),
    [
        ("战痘专家", 40, (180, 220, 255), 40),
        ("根治痘痘", 84, (255, 255, 255), 30),
        ("消炎杀菌 一步到位", 48, (255, 255, 255), 36),
        ("皮肤科医生推荐配方", 36, (170, 214, 255), 0),
    ],
)

# ③ 疑似：医疗边缘暗示（「医美级」「救星」「闭眼入」为边缘表达，转人工）
poster(
    "eval4_suspicious_medicalish.png", (120, 90, 130),
    [
        ("新品返场", 40, (230, 210, 255), 40),
        ("断货王来了", 84, (255, 255, 255), 30),
        ("医美级护理体验", 52, (230, 210, 255), 36),
        ("敏感肌闭眼入", 44, (255, 255, 255), 0),
    ],
)

# ④ 疑似：绝对化边缘（「颜值天花板」「公认标杆」为网络化边缘表达，转人工）
poster(
    "eval4_suspicious_superlative.png", (40, 110, 90),
    [
        ("国货之光", 40, (210, 240, 210), 40),
        ("颜值天花板", 84, (255, 255, 255), 30),
        ("圈层公认的品质标杆", 44, (210, 240, 210), 36),
        ("祖传配方 古法工艺", 40, (255, 255, 255), 0),
    ],
)
