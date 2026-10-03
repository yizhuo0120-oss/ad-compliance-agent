"""卡7 · 文案生成流水线：策划角色 → 文案角色 → 物料包。

流程：商品信息 → 策划（卖点/人群/策略）→ 逐平台生成（平台风格 + few-shot 范文）→ 物料包。
卡8 填入 image_* 字段，卡10 闭环填入 audit 字段。

合规约束：生成阶段即要求「不用绝对化用语、不涉及医疗功效、不贬损竞品」，
输出后仍须过一期审核引擎（卡10），两层防线。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.llm_client import LLMClient, extract_json  # noqa: E402

SAMPLES_DIR = ROOT / "data" / "style_samples"
SCHEMA_PATH = ROOT / "engine" / "material_schema.json"

PLATFORMS = ["小红书", "抖音口播", "淘宝主图", "朋友圈"]

PLANNER_SYSTEM = (
    "你是电商广告策划。根据商品信息提炼卖点与投放策略，只输出 JSON："
    '{"selling_points": ["卖点短语，3~5条，口语化"],'
    ' "audience": "目标人群一句话", "strategy": "一句投放策略"}'
)

COPY_SYSTEM = (
    "你是平台资深文案。严格模仿给定范例的腔调、长度和排版风格，为指定平台写商品推广文案。"
    "合规红线：不用绝对化用语（最/第一/国家级/顶级等）；不涉及医疗功效表述；不贬损竞品。"
    "必须覆盖给定的核心卖点。只输出 JSON："
    '{"copy": "正文（排版风格贴近范例）", "tags": ["话题标签，仅小红书/朋友圈需要，其余平台给空数组"]}'
)


def load_samples(platform: str) -> list[str]:
    """读取平台范文：空行分隔的多段样本。"""
    path = SAMPLES_DIR / f"{platform}.txt"
    raw = path.read_text(encoding="utf-8")
    return [s.strip() for s in re.split(r"\n\s*\n", raw) if s.strip()]


def _extract_json(raw: str) -> dict:
    return extract_json(raw)


def plan(llm, product: dict) -> dict:
    """策划角色：商品信息 → 卖点/人群/策略。"""
    prompt = (
        f"商品名称：{product['name']}\n商品信息：{product.get('info', '')}\n\n请输出 JSON。"
    )
    raw = llm.chat(prompt, system=PLANNER_SYSTEM, json_mode=True, temperature=0.3)
    plan_data = _extract_json(raw)
    product.update({
        "selling_points": [str(p) for p in plan_data.get("selling_points", [])][:5],
        "audience": str(plan_data.get("audience", "")),
        "strategy": str(plan_data.get("strategy", "")),
    })
    return product


def write_copy(llm, platform: str, product: dict) -> dict:
    """文案角色：按平台风格 + few-shot 范文生成。"""
    samples = load_samples(platform)
    few_shot = "\n\n---\n\n".join(samples)
    prompt = (
        f"【商品】{product['name']}\n"
        f"【核心卖点】{'；'.join(product.get('selling_points', []))}\n"
        f"【人群与策略】{product.get('audience', '')}；{product.get('strategy', '')}\n\n"
        f"【{platform} 风格范例（共{len(samples)}条，模仿腔调与排版，禁止抄内容）】\n{few_shot}\n\n"
        f"请为【{platform}】撰写推广文案，只输出 JSON。"
    )
    raw = llm.chat(prompt, system=COPY_SYSTEM, json_mode=True, temperature=0.7)
    data = _extract_json(raw)
    if not isinstance(data.get("copy"), str) or not data["copy"].strip():
        raise ValueError("模型未返回有效的广告文案")
    return {
        "platform": platform,
        "copy": str(data.get("copy", "")).strip(),
        "tags": [str(t) for t in data.get("tags", [])],
    }


def generate_materials(llm, product: dict, platforms: list[str] | None = None) -> dict:
    """完整流水线：策划 → 逐平台文案 → 物料包（image_*/audit 字段留待卡8/卡10 填入）。"""
    platforms = platforms or PLATFORMS
    product = dict(product)
    if not product.get("selling_points"):
        plan(llm, product)
    platforms_out = [write_copy(llm, p, product) for p in platforms]
    return {
        "product": product,
        "platforms": platforms_out,
        "image_prompt": None,
        "image_path": None,
        "ai_disclosure": None,
        "audit": None,
    }


def validate_materials(pack: dict) -> None:
    """物料包 schema 校验，不通过抛异常。"""
    import jsonschema
    jsonschema.validate(pack, json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))


if __name__ == "__main__":
    demo = {"name": "便携榨汁杯", "info": "USB充电，300ml，杯身可冷冻，母婴级材质，60秒出汁"}
    llm = LLMClient()
    pack = generate_materials(llm, demo)
    validate_materials(pack)
    for p in pack["platforms"]:
        print(f"[{p['platform']}] {p['copy'][:50]}… 标签:{p['tags']}")
    print("✅ 物料包 schema 校验通过")
