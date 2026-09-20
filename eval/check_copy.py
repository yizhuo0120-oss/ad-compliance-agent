"""卡7/第二步：风格自检——3 商品 × 4 平台全量生成 + LLM-as-judge 打分。

指标：平台风格符合度（1~5）、卖点覆盖度（1~5）、合规自检（绝对化/医疗/贬损）。
产出：eval/results/k7_copy_check.json；低分平台回灌调 prompt（第二步的迭代依据）。
用法：python eval/check_copy.py
"""
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.copywriter import PLATFORMS, generate_materials, validate_materials  # noqa: E402
from engine.llm_client import LLMClient  # noqa: E402

OUT = ROOT / "eval" / "results" / "k7_copy_check.json"

PRODUCTS = [
    {"name": "便携榨汁杯", "info": "USB充电，300ml，杯身可冷冻，母婴级材质，60秒出汁"},
    {"name": "加厚野餐垫", "info": "防潮层加厚，一抖不粘草屑，折叠后书本大小，奶油色"},
    {"name": "手冲咖啡磨豆机", "info": "40档研磨可调，工作音量约55分贝，铝合金机身，新手友好"},
]

JUDGE_SYSTEM = (
    "你是资深电商内容编辑，熟悉各内容平台的文案惯例。对给定文案打分，只输出 JSON："
    '{"style_score": 1~5整数, "coverage_score": 1~5整数,'
    ' "compliance_ok": true或false,'
    ' "compliance_issue": "若出现绝对化用语(最/第一/国家级等)、医疗功效表述、贬损竞品则具体说明，否则给空串",'
    ' "comment": "一句话点评"}\n'
    "打分标准——style_score：5=完全像该平台原生内容，3=基本像但有生硬感，1=完全不像；"
    "coverage_score：5=核心卖点全部自然融入，1=基本没覆盖。"
)


def judge_copy(llm, platform: str, points: list[str], copy: str) -> dict:
    prompt = (
        f"【平台】{platform}\n【核心卖点】{'；'.join(points)}\n【文案】\n{copy}\n\n请输出 JSON 评分。"
    )
    raw = llm.chat(prompt, system=JUDGE_SYSTEM, json_mode=True, temperature=0.1)
    import re
    m = re.search(r"\{.*\}", raw, re.S)
    data = json.loads(m.group(0)) if m else {}
    return {
        "style_score": int(data.get("style_score", 0)),
        "coverage_score": int(data.get("coverage_score", 0)),
        "compliance_ok": bool(data.get("compliance_ok", True)),
        "compliance_issue": str(data.get("compliance_issue", "")),
        "comment": str(data.get("comment", "")),
    }


def main() -> None:
    llm = LLMClient()
    results = []
    t0 = time.time()
    for pi, product in enumerate(PRODUCTS, 1):
        pack = generate_materials(llm, dict(product))
        try:
            validate_materials(pack)
            fmt_ok = True
        except Exception as e:
            fmt_ok = False
            print(f"格式失败：{product['name']} → {str(e)[:120]}")
        for p in pack["platforms"]:
            j = judge_copy(llm, p["platform"], pack["product"].get("selling_points", []), p["copy"])
            results.append({"product": product["name"], "platform": p["platform"],
                            "copy": p["copy"], "tags": p["tags"], "judge": j})
            print(f"[{pi}/3] {product['name']} · {p['platform']} "
                  f"风格{j['style_score']} 覆盖{j['coverage_score']} "
                  f"合规{'✓' if j['compliance_ok'] else '✗ ' + j['compliance_issue'][:40]}",
                  flush=True)

    by_platform: dict[str, list[dict]] = {}
    for r in results:
        by_platform.setdefault(r["platform"], []).append(r["judge"])
    summary = {}
    for plat, js in by_platform.items():
        summary[plat] = {
            "style_avg": round(statistics.mean(j["style_score"] for j in js), 2),
            "coverage_avg": round(statistics.mean(j["coverage_score"] for j in js), 2),
            "compliance_fail": sum(1 for j in js if not j["compliance_ok"]),
        }
    out = {"summary": summary, "elapsed_s": int(time.time() - t0), "results": results}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n==== 平台维度汇总 ====")
    for plat, s in summary.items():
        print(f"  {plat}: 风格{s['style_avg']} 覆盖{s['coverage_avg']} 违规{ s['compliance_fail']}")
    print(f"用时 {out['elapsed_s']}s → {OUT}")


if __name__ == "__main__":
    main()
