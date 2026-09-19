"""卡2 · hello_image：视觉通道最小链路（真实 API 调用）。

通关标准：喂一张海报图，能转写出画面文字。
用法：python hello_image.py [图片路径]    # 默认 data/test_poster.png
"""
import sys
from pathlib import Path

from engine.llm_client import LLMClient

ROOT = Path(__file__).resolve().parent
DEFAULT_POSTER = ROOT / "data" / "test_poster.png"

PROMPT = (
    "请分两段输出：\n"
    "1. 转写：逐字转写图中出现的所有文字，按出现顺序每行一条，不要翻译或改写；\n"
    "2. 画面：用一句话描述画面元素（人物/产品/场景/标识）。"
)


def main() -> None:
    image = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_POSTER
    if not image.exists():
        sys.exit(f"找不到图片：{image}")

    llm = LLMClient()
    print(f"图片：{image}")
    print(f"模型：{llm.provider} / {llm.vision_model}\n")
    print(llm.vision(PROMPT, image))


if __name__ == "__main__":
    main()
