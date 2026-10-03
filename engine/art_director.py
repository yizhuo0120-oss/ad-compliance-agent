"""卡8 · 宣传图生成：卖点 → 生图提示词 → 生图 → 下载 → 叠加 AI 标识角标。

定位说明（诚实边界）：AI 生图无法精确还原真实商品外观，宣传图定位为「场景氛围图」，
正式主图仍需实拍；标识合规依据《人工智能生成合成内容标识办法》——
显式标识（画面角标）+ 模型自带水印 + 物料包 ai_disclosure 声明，三重落地。
"""
from __future__ import annotations

import json
import re
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from engine.llm_client import LLMClient, extract_json, image_client

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "generated"

AI_DISCLOSURE_TEXT = "本图片由 AI 生成，仅供参考，实际商品以实物为准"

ART_SYSTEM = (
    "你是电商海报艺术指导。为商品写一段给 AI 生图模型的中文提示词。"
    "要求：描述场景背景、商品的大致外观（按该类商品的常见形态描写）、陪衬道具、光线与风格；"
    "商业摄影质感；画面中不要出现任何文字或字母（避免生图乱码字）；"
    "一段话 60~120 字。只输出 JSON：{\"prompt\": \"...\"}"
)


def _extract_json(raw: str) -> dict:
    return extract_json(raw)


def make_image_prompt(llm, product: dict, copy_text: str = "") -> str:
    """艺术指导：卖点与文案基调 → 生图提示词。"""
    prompt = (
        f"商品：{product['name']}（{product.get('info', '')}）\n"
        f"核心卖点：{'；'.join(product.get('selling_points', []))}"
    )
    if copy_text:
        prompt += f"\n配套文案基调：{copy_text[:80]}"
    raw = llm.chat(prompt + "\n\n请输出 JSON。", system=ART_SYSTEM,
                   json_mode=True, temperature=0.5)
    return str(_extract_json(raw).get("prompt", "")).strip()


def add_ai_badge(img_path: Path, text: str = "AI生成") -> None:
    """显式标识：右下角半透明角标（PIL 叠加）。"""
    from PIL import Image, ImageDraw, ImageFont
    img = Image.open(img_path).convert("RGB")
    d = ImageDraw.Draw(img, "RGBA")
    font_size = max(16, min(40, img.width // 36))
    font = None
    for candidate in ("C:/Windows/Fonts/msyh.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"):
        try:
            font = ImageFont.truetype(candidate, font_size)
            break
        except OSError:
            pass
    if font is None:
        # Serverless Linux images do not ship Windows fonts. Keep the badge legible.
        text = "AI generated"
        font = ImageFont.load_default(size=font_size)
    bbox = d.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0] + 24, bbox[3] - bbox[1] + 14
    x, y = img.width - w - 24, img.height - h - 24
    d.rounded_rectangle((x, y, x + w, y + h), radius=10, fill=(0, 0, 0, 160))
    d.text((x + 12, y + 7), text, font=font, fill=(255, 255, 255, 255))
    img.save(img_path, "PNG")


def generate_promo(llm, product: dict, copy_text: str = "",
                   out_dir: Path = OUT_DIR, image_llm=None) -> dict:
    """全流程：提示词 → 生图 → 下载 → 叠标识。返回物料包 image_* 三字段。

    文字提示词用当前 llm；生图自动切换到有生图能力的供应商（如智谱 CogView）。
    """
    t0 = time.time()
    image_prompt = make_image_prompt(llm, product, copy_text)
    if not image_prompt:
        raise ValueError("生图提示词为空")
    img_llm = image_llm or (llm if llm.image_model else image_client())
    url = img_llm.generate_image(image_prompt)
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^\w]", "", product["name"])[:16] or "product"
    path = out_dir / f"{slug}-{datetime.now().strftime('%H%M%S')}.png"
    with urllib.request.urlopen(url, timeout=40) as response:
        image_data = response.read(20 * 1024 * 1024 + 1)
    if len(image_data) > 20 * 1024 * 1024:
        raise ValueError("生成图片超过 20 MB")
    path.write_bytes(image_data)
    add_ai_badge(path)
    return {
        "image_prompt": image_prompt,
        "image_path": str(path),
        "ai_disclosure": f"{AI_DISCLOSURE_TEXT}（生成耗时 {time.time() - t0:.0f}s）",
    }
