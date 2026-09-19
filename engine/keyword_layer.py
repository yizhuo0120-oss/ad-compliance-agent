"""关键词层（D5）：违禁词匹配 + 变体归一化。

词库 data/banned_words.txt 的分类头（# ===== 类名（法条引用） =====）同时提供
每类词的默认违规类型与预期法条，命中即产出带类型的 finding。

口径：词命中 ≠ 必违规（如「第一人称」），关键词层结论保守记为 suspicious 级信号，
最终风险等级由 pipeline 结合语义层合并裁定。
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from zhconv import convert as zh2hans

from engine.rag_layer import norm_type

ROOT = Path(__file__).resolve().parent.parent
WORDS_PATH = ROOT / "data" / "banned_words.txt"

_HEADER_RE = re.compile(r"^#\s*=+\s*(.+?)\s*=+\s*$")


def normalize(text: str) -> str:
    """全角→半角（NFKC）、繁→简、小写。命中判定一律在归一化文本上进行。"""
    t = unicodedata.normalize("NFKC", text)
    t = zh2hans(t, "zh-hans")
    return t.lower()


def load_words(path: Path = WORDS_PATH) -> list[dict]:
    """加载词库，返回 [{word, type, law_refs}]，分类头携带类型与预期法条。"""
    words: list[dict] = []
    cur_type, cur_laws = "其他", []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            m = _HEADER_RE.match(line)
            if m:
                head = m.group(1)
                name, _, ref = head.partition("（")
                cur_type = name.split("/")[0].strip()  # 「低俗/导向」→「低俗」
                ref = ref.rstrip("）").strip()
                cur_laws = []
                for part in ref.split("/"):
                    part = part.strip()
                    if not part:
                        continue
                    if not part.startswith(("广告法", "民法典")):
                        part = f"广告法·{part}"
                    m2 = re.match(r"((?:广告法|民法典)·[^，。）]+?条)", part)
                    cur_laws.append(m2.group(1) if m2 else part)
            continue
        words.append({"word": line, "type": cur_type, "law_refs": list(cur_laws)})
    return words


def match(text: str, words: list[dict] | None = None) -> list[dict]:
    """归一化后子串匹配，返回命中 [{word, type, law_refs, span}]。"""
    t = normalize(text)
    hits = []
    for w in words or load_words():
        w_n = normalize(w["word"])
        if not w_n:
            continue
        start = 0
        while True:
            i = t.find(w_n, start)
            if i < 0:
                break
            hits.append({**w, "span": (i, i + len(w_n))})
            start = i + len(w_n)
    return hits


def audit(text: str, words: list[dict] | None = None) -> list[dict]:
    """关键词通道：命中 → schema 形状的 findings（source=keyword，片段取命中词）。"""
    findings = []
    for h in match(text, words):
        findings.append({
            "type": norm_type(h["type"]),
            "fragment": h["word"],
            "law": {"name": h["law_refs"][0].split("·")[0] if h["law_refs"] else "",
                    "article": h["law_refs"][0].split("·")[-1] if h["law_refs"] else "",
                    "quote": ""},
            "reason": f"命中违禁词「{h['word']}」（{h['type']}类）",
            "suggestion": "",
            "source": "keyword",
            "_law_refs": h["law_refs"],
            "_strength": "weak",  # 词命中为弱信号，合并阶段结合语义层裁定
        })
    return findings
