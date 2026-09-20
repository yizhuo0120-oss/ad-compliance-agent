"""卡8 通关自检：一个商品 → 物料包（4 平台文案 + 宣传图 + AI 标识），全链路 ≤60 秒。"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.art_director import generate_promo  # noqa: E402
from engine.copywriter import generate_materials, validate_materials  # noqa: E402
from engine.llm_client import LLMClient  # noqa: E402


def main() -> None:
    product = {"name": "便携榨汁杯", "info": "USB充电，300ml，杯身可冷冻，母婴级材质，60秒出汁"}
    llm = LLMClient()
    t0 = time.time()

    pack = generate_materials(llm, dict(product))
    first_copy = pack["platforms"][0]["copy"]
    promo = generate_promo(llm, product, copy_text=first_copy)
    pack.update(promo)
    validate_materials(pack)

    elapsed = time.time() - t0
    print(f"生图提示词：{promo['image_prompt'][:80]}…")
    print(f"宣传图：{promo['image_path']}")
    print(f"标识声明：{promo['ai_disclosure']}")
    print(f"全链路耗时：{elapsed:.1f}s（验收线 60s）{'✅' if elapsed <= 60 else '❌ 超时'}")


if __name__ == "__main__":
    main()
