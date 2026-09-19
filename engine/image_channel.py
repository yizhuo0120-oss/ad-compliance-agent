"""图片通道（D7）：VL 转写画面文字与元素 → 文字送文案通道复用 + 视觉风险判定。"""
from __future__ import annotations

import json
import re
from pathlib import Path

from engine.rag_layer import norm_type

TRANSCRIBE_PROMPT = (
    "你是广告合规标注助手。只输出一个 JSON 对象，不要任何多余文字，结构如下：\n"
    '{"texts": ["图中出现的每一段文字，按顺序逐字转写"],'
    ' "visual_elements": "一句话描述画面元素：人物/产品/场景/标识"}\n'
    "texts 必须包含角落小字与免责声明，不要翻译或改写。"
)

VISUAL_SYSTEM = (
    "你是广告合规审核员，依据给定法条判断海报画面（画面文字与视觉元素）是否违规。"
    "重点：真人肖像未授权、画面夸大误导、低俗内容；转写文字本身的判定已由文案通道完成，不要重复。"
    "拿不准给 suspicious。只输出 JSON："
    '{"findings": [{"type": "八类之一:极限词|虚假误导|医疗功效|保健食品|肖像权|名誉权|隐私|低俗",'
    ' "fragment": "依据的画面元素或文字片段", "article": "法条，须来自给定列表",'
    ' "verdict": "violation|suspicious|not", "reason": "一句话", "suggestion": "一句话"}]}'
)


def transcribe(llm, image_path: str | Path) -> dict:
    """VL 转写：返回 {texts: [...], visual_elements: str}。"""
    raw = llm.vision(TRANSCRIBE_PROMPT, image_path)
    m = re.search(r"\{.*\}", raw, re.S)
    data = json.loads(m.group(0)) if m else {}
    return {"texts": [str(t) for t in data.get("texts", [])],
            "visual_elements": str(data.get("visual_elements", ""))}


def audit_visual(llm, texts: list[str], visual_elements: str, index, k: int | None = None) -> list[dict]:
    """视觉风险判定：画面元素 + 转写文字联合检索法条 → LLM 判定。"""
    query = " ".join(texts[:5]) + " " + visual_elements
    articles = index.search(query, k or 6)
    law_block = "\n".join(
        f"- {r['law']}·{r['article']}（适用场景：{r['scene_note'] or '见条文'}）\n  原文：{r['text']}"
        for r in articles
    )
    prompt = (
        f"画面元素：{visual_elements}\n"
        f"画面文字：{' | '.join(texts)}\n\n给定法条：\n{law_block}\n\n请输出 JSON 判定。"
    )
    raw = llm.chat(prompt, system=VISUAL_SYSTEM, json_mode=True, temperature=0.1)
    m = re.search(r"\{.*\}", raw, re.S)
    data = json.loads(m.group(0)) if m else {}
    corpus = {(r["law"], r["article"]): r["text"] for r in articles}
    findings = []
    for f in data.get("findings", []):
        if f.get("verdict") == "not":
            continue
        name, _, art = f.get("article", "").partition("·")
        findings.append({
            "type": norm_type(f.get("type", "")),
            "fragment": f.get("fragment", "")[:60],
            "law": {"name": name, "article": art, "quote": corpus.get((name, art), "")},
            "reason": f.get("reason", ""),
            "suggestion": f.get("suggestion", ""),
            "source": "visual",
            "_strength": f.get("verdict", "suspicious"),
        })
    return findings
