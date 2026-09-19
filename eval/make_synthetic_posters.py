"""卡3 · D4：补造合成违规海报（构造即真值，标注零争议）。

产出 data/eval_images/syn_*.png 共 5 张：
  extreme(极限词) / medical(医疗功效) / health(保健食品) / disparage(贬损竞品) / dense(小字密集压测)
用法：python eval/make_synthetic_posters.py
"""
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent / "data" / "eval_images"
FONT = "C:/Windows/Fonts/msyh.ttc"
random.seed(7)


def f(size: int):
    return ImageFont.truetype(FONT, size)


def poster(name, bg, blocks, small_lines=()):
    """blocks: [(y, text, size, color)]; small_lines: 底部小字（压测转写）"""
    W, H = 640, 860
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    for y, text, size, color in blocks:
        d.text((W // 2, y), text, font=f(size), fill=color, anchor="mm")
    y = H - 40 - len(small_lines) * 34
    for i, line in enumerate(small_lines):
        d.text((W // 2, y + i * 34), line, font=f(20), fill=(240, 240, 240), anchor="mm")
    img.save(OUT / name)
    print("OK", name)


random_top = random.choice(["618年中大促", "双11狂欢季", "周年庆"])

poster(
    "syn_violation_extreme.png", (200, 30, 24),
    [(80, random_top, 40, (255, 220, 120)), (230, "全场最低价", 96, (255, 230, 60)),
     (360, "行业第一品牌", 68, (255, 255, 255)), (560, "国家级工艺 值得拥有", 52, (255, 255, 255))],
    ["最终解释权归本店所有"],
)
poster(
    "syn_violation_medical.png", (28, 90, 120),
    [(80, "肌肤问题的克星", 44, (180, 220, 255)), (230, "根治痘痘", 96, (255, 255, 255)),
     (360, "消炎杀菌 一步到位", 56, (255, 255, 255)), (560, "医生推荐 临床验证", 48, (170, 214, 255))],
    ["使用效果因人而异"],
)
poster(
    "syn_violation_health.png", (30, 110, 60),
    [(80, "养生茶饮 温和调理", 44, (200, 240, 200)), (230, "安全无副作用", 84, (255, 255, 160)),
     (360, "有病治病 无病防病", 60, (255, 255, 255)), (560, "可长期替代药物", 52, (200, 240, 200))],
    ["本品不能代替药物", "请理性选购"],
)
poster(
    "syn_violation_disparage.png", (60, 40, 90),
    [(80, "选对不选贵", 44, (230, 200, 255)), (230, "吊打同行大牌", 90, (255, 255, 255)),
     (360, "别家都是假货", 66, (255, 200, 120)), (560, "我们才是工厂正品", 52, (230, 200, 255))],
    ["活动最终解释权归本店所有"],
)
poster(
    "syn_dense_smalltext.png", (40, 44, 60),
    [(90, "品质生活节", 72, (255, 255, 255)), (210, "匠心好物 焕新上线", 48, (255, 210, 140))],
    [
        "史上最全优惠清单（小字压测1）",
        "全场最佳性价比之选（小字压测2）",
        "销量第一的王牌单品（小字压测3）",
        "独家顶级原料产地直供（小字压测4）",
        "国家专利配方技术支持（小字压测5）",
        "活动详情请咨询门店客服（普通小字）",
    ],
)
