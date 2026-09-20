"""卡10 · 生成×审核闭环：生成 → 一期引擎审核 → 带法条改写 → 循环收敛（上限 3 轮）。

收敛数据（每轮风险、findings 数、改写次数、最终合规）即简历素材
「生成物料经审核回环自动改写至合规」的出处。
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
from engine.copywriter import generate_materials, validate_materials  # noqa: E402
from engine.pipeline import audit_text  # noqa: E402

MAX_ROUNDS = 3

REWRITE_SYSTEM = (
    "你是广告合规改写专家。根据审核报告（含命中的法条与改写建议）改写广告文案："
    "消除全部违规点，维持原平台腔调。改写规则：\n"
    "- 医疗功效/保健食品类：【直接删除】疾病治疗、功效断言与安全性保证（根治/见效/消炎/无副作用等），"
    "只保留清洁、保湿、舒缓等合规护肤表达；无法合规化的卖点直接舍弃\n"
    "- 极限词：删除或改为可验证表述（「全网最低价」→「限时优惠」）\n"
    "- 贬损竞品：删除一切与竞品的对比\n"
    "- 虚假误导：删除无法证实的承诺（无效退款、百分百）\n"
    "合规红线：不用绝对化用语；不涉及疾病治疗；不贬损竞品。"
    "只输出 JSON：{\"copy\": \"改写后的文案\", \"tags\": [\"话题标签\"]}"
)


def audit_pack(llm, index, pack: dict) -> dict:
    """整个物料包（4 平台文案合并）过一期审核引擎。keep_internal 附带违规级判据。"""
    joined = "\n".join(f"[{p['platform']}] {p['copy']}" for p in pack["platforms"])
    return audit_text(llm, joined, index, keep_internal=True)


def _rewrite_one(llm, platform: str, copy: str, findings_json: str) -> dict:
    prompt = f"【平台】{platform}\n【原文案】\n{copy}\n\n【审核报告】\n{findings_json}\n\n请输出改写后的 JSON。"
    import re
    raw = llm.chat(prompt, system=REWRITE_SYSTEM, json_mode=True, temperature=0.4)
    m = re.search(r"\{.*\}", raw, re.S)
    data = json.loads(m.group(0)) if m else {}
    return {"platform": platform, "copy": str(data.get("copy", copy)).strip(),
            "tags": [str(t) for t in data.get("tags", [])]}


def closed_loop(llm, index, product: dict, platforms: list[str] | None = None,
                max_rounds: int = MAX_ROUNDS) -> dict:
    """完整闭环。返回 {pack, trajectory, rounds, final_compliant}。"""
    pack = generate_materials(llm, dict(product), platforms)
    trajectory = []
    revisions = 0
    final_compliant = False
    round_no = 0

    for round_no in range(1, max_rounds + 1):
        report = audit_pack(llm, index, pack)
        has_violation = bool(report.get("_has_violation"))
        trajectory.append({
            "round": round_no, "risk": report["risk_level"],
            "n_findings": len(report["findings"]),
            "fragments": [f["fragment"][:30] for f in report["findings"]],
        })
        if not has_violation:
            # 收敛口径：无「违规级」发现即合规交付；疑似级按设计转人工，不作循环条件
            final_compliant = True
            break
        if round_no == max_rounds:
            break  # 超限：转人工（badcase 归档）

        findings_json = json.dumps(
            [{"类型": f["type"], "片段": f["fragment"],
              "法条": f"{f['law']['name']}·{f['law']['article']}",
              "理由": f["reason"], "改写建议": f["suggestion"]}
             for f in report["findings"]],
            ensure_ascii=False, indent=1)
        print(f"  第{round_no}轮 {report['risk_level']}（{len(report['findings'])} 项）→ 带法条改写…", flush=True)
        pack["platforms"] = [_rewrite_one(llm, p["platform"], p["copy"], findings_json)
                             for p in pack["platforms"]]
        revisions += 1

    pack["audit"] = {"risk_level": report["risk_level"], "revisions": revisions,
                     "final_compliant": final_compliant}
    validate_materials(pack)
    return {"pack": pack, "trajectory": trajectory,
            "rounds": round_no, "final_compliant": final_compliant}
