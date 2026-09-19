"""流水线（D7）：双通道合并 → schema v1.0 报告。

风险等级裁定口径（v1）：
  violation  —— 语义层/视觉层任一给出 violation 判定
  suspicious —— 仅有弱信号（关键词命中）或语义/视觉层给 suspicious
  compliant  —— 两层均无发现
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

import jsonschema

from engine import image_channel, keyword_layer, rag_layer

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((ROOT / "engine" / "report_schema.json").read_text(encoding="utf-8"))


def _merge(*finding_lists: list[dict]) -> list[dict]:
    """合并去重：rag/visual 的富片段优先于 keyword 的单词命中；同 type+近似片段去重。"""
    strong = [f for lst in finding_lists for f in lst if f["source"] != "keyword"]
    weak = [f for lst in finding_lists for f in lst if f["source"] == "keyword"]
    out: list[dict] = []
    for f in strong:
        f.pop("_law_refs", None)
        if not any(o["type"] == f["type"] and o["source"] != "keyword" and
                   (f["fragment"] in o["fragment"] or o["fragment"] in f["fragment"])
                   for o in out):
            out.append(f)
    for f in weak:
        f.pop("_law_refs", None)
        covered = any(o["type"] == f["type"] and
                      (f["fragment"] in o["fragment"] or o["fragment"] in f["fragment"])
                      for o in out)
        if not covered:
            out.append(f)
    return out


def _risk_level(findings: list[dict]) -> str:
    strengths = {f.get("_strength") for f in findings}
    if "violation" in strengths:
        return "violation"
    if findings:
        return "suspicious"
    return "compliant"


def _strip_internal(report: dict) -> dict:
    for f in report["findings"]:
        f.pop("_strength", None)
    return report


def _fill_quote(findings: list[dict]) -> None:
    """关键词层 finding 的法条原文为空，从语料回填。"""
    for f in findings:
        law = f["law"]
        if not law.get("quote") and law.get("name") and law.get("article"):
            for row in rag_layer.load_corpus():
                if row["law"] == law["name"] and row["article"] == law["article"]:
                    law["quote"] = row["text"]
                    break


def audit_text(llm, text: str, index: rag_layer.LawIndex, use_rag: str = "full") -> dict:
    """文案通道全流程：关键词层 + 语义层 → 合并 → 报告。

    use_rag="full"：混合检索法条进提示词 + 回填条文引用（正式模式）
    use_rag="off" ：同模型但不含法条、凭自身知识判断（消融模式，quote 恒为空）
    """
    t0 = time.time()
    kw = keyword_layer.audit(text)
    # 关键词命中的「预期法条」并入语义层候选（混合检索，弥合语义鸿沟）
    extra_refs = [tuple(r.split("·", 1)) for f in kw for r in f.get("_law_refs", [])]
    if use_rag == "full":
        rag = rag_layer.audit_semantic(text, index, llm, extra_refs=extra_refs)
    else:
        rag = rag_layer.audit_semantic(text, index, llm, include_laws=False)
    findings = _merge(rag, kw)
    _fill_quote(findings)
    report = {
        "input_type": "text",
        "transcript": None,
        "risk_level": _risk_level(findings),
        "findings": findings,
        "summary": (f"检出 {len(findings)} 项问题，风险等级 {_risk_level(findings)}"
                    if findings else "未发现违规风险"),
        "meta": {"schema_version": "1.0", "model": llm.text_model,
                 "latency_ms": int((time.time() - t0) * 1000),
                 "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
                 "cost_cny": None},
    }
    return _strip_internal(report)


def audit_image(llm, image_path: str | Path, index: rag_layer.LawIndex) -> dict:
    """图片通道：转写 → 转写文字走文案通道 + 视觉判定 → 合并报告。"""
    t0 = time.time()
    tr = image_channel.transcribe(llm, image_path)
    joined = "\n".join(f"{i}. {t}" for i, t in enumerate(tr["texts"], 1))
    kw = keyword_layer.audit(joined)
    extra_refs = [tuple(r.split("·", 1)) for f in kw for r in f.get("_law_refs", [])]
    rag = rag_layer.audit_semantic(joined, index, llm, extra_refs=extra_refs)
    vis = image_channel.audit_visual(llm, tr["texts"], tr["visual_elements"], index)
    findings = _merge(vis, rag, kw)
    _fill_quote(findings)
    report = {
        "input_type": "image",
        "transcript": {"texts": tr["texts"], "visual_elements": tr["visual_elements"]},
        "risk_level": _risk_level(findings),
        "findings": findings,
        "summary": (f"画面文字 {len(tr['texts'])} 段，检出 {len(findings)} 项问题"
                    if findings else f"画面文字 {len(tr['texts'])} 段，未发现违规风险"),
        "meta": {"schema_version": "1.0", "model": llm.vision_model,
                 "latency_ms": int((time.time() - t0) * 1000),
                 "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
                 "cost_cny": None},
    }
    return _strip_internal(report)


def finalize(report: dict) -> dict:
    """schema 校验（不通过直接抛异常，D6/D7 自检与 D8 评测共用）。"""
    jsonschema.validate(report, SCHEMA)
    return report
