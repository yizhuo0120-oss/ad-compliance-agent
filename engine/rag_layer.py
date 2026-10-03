"""语义层（D6）：BGE + FAISS 法条检索 → LLM 逐条比对判断。

检索口径：passing 向量 = 条号 + 适用场景备注 + 条文原文（备注在前，弥合
口语化违规表达 ↔ 法条术语的语义鸿沟，如「全网最低价」↔ 第九条「最高级」）。
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from engine.llm_client import extract_json

ROOT = Path(__file__).resolve().parent.parent
LAWS_DIR = ROOT / "data" / "laws"
VEC_PATH = LAWS_DIR / "index_vectors.npy"
META_PATH = LAWS_DIR / "index_meta.json"
MODEL_NAME = "BAAI/bge-small-zh-v1.5"
QUERY_INSTRUCTION = "为这条广告文案检索可能被违反的法律条文："

EIGHT_TYPES = ["极限词", "虚假误导", "医疗功效", "保健食品", "肖像权", "名誉权", "隐私", "低俗"]

# 模型输出的常见同义标签 → 八类规范名（schema enum 只认八类）
TYPE_ALIASES = {
    "绝对化用语": "极限词", "夸大宣传": "虚假误导", "虚假宣传": "虚假误导",
    "误导消费者": "虚假误导", "医疗用语": "医疗功效", "医疗广告": "医疗功效",
    "疾病治疗": "医疗功效", "贬损竞品": "名誉权", "商业诋毁": "名誉权",
    "损害商誉": "名誉权", "肖像侵权": "肖像权", "盗用肖像": "肖像权",
    "低俗内容": "低俗", "导向问题": "低俗", "个人信息": "隐私",
}


def norm_type(t: str) -> str:
    if t in EIGHT_TYPES:
        return t
    return TYPE_ALIASES.get(t, "虚假误导")


def load_corpus() -> list[dict]:
    rows = []
    for f in sorted(LAWS_DIR.glob("*.jsonl")):
        rows += [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
    return rows


class LawIndex:
    """法条向量库：build 一次落盘，之后加载使用。"""

    def __init__(self, k: int = 5):
        self.k = k
        self.rows: list[dict] = []
        self._index = None
        self._model = None

    def _ensure_model(self):
        if self._model is None:
            os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
            if (ROOT / "models").exists():
                # 模型已缓存：跳过对镜像的在线版本检查（镜像不稳定时会挂起数分钟）
                os.environ.setdefault("HF_HUB_OFFLINE", "1")
                os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(MODEL_NAME, cache_folder=str(ROOT / "models"))
        return self._model

    def _encode_passages(self, rows: list[dict]) -> list[str]:
        return [f"【{r['law']}·{r['article']}】{r['scene_note']} {r['text']}" for r in rows]

    def build(self, force: bool = False) -> None:
        import faiss
        import numpy as np
        self.rows = load_corpus()
        # 持久化用 .npy（faiss 的 C++ 写盘不支持中文路径），检索仍用 faiss
        if VEC_PATH.exists() and META_PATH.exists() and not force:
            vecs = np.load(VEC_PATH)
            self.rows = json.loads(META_PATH.read_text(encoding="utf-8"))
        else:
            model = self._ensure_model()
            vecs = model.encode(self._encode_passages(self.rows), normalize_embeddings=True,
                                show_progress_bar=False)
            np.save(VEC_PATH, np.asarray(vecs, dtype="float32"))
            META_PATH.write_text(json.dumps(self.rows, ensure_ascii=False), encoding="utf-8")
        self._index = faiss.IndexFlatIP(vecs.shape[1])
        self._index.add(np.asarray(vecs, dtype="float32"))
        self._by_ref = {(r["law"], r["article"]): r for r in self.rows}

    def get_by_ref(self, law: str, article: str) -> dict | None:
        return self._by_ref.get((law, article))

    def search(self, query: str, k: int | None = None) -> list[dict]:
        if self._index is None:
            self.build()
        model = self._ensure_model()
        import numpy as np
        qv = model.encode([QUERY_INSTRUCTION + query], normalize_embeddings=True,
                          show_progress_bar=False)
        scores, ids = self._index.search(np.asarray(qv, dtype="float32"), k or self.k)
        out = []
        for score, i in zip(scores[0], ids[0]):
            if i < 0:
                continue
            out.append({**self.rows[int(i)], "score": float(score)})
        return out


JUDGE_SYSTEM = (
    "你是电商广告合规审核员，严格依据给定的法律条文判断广告文案是否违规。"
    "不要使用给定法条之外的常识扩张认定；拿不准时 verdict 给 suspicious 而不是 violation。"
    "以下属于常见合法表达，不要判违规：\n"
    "- 正常促销：限时优惠、满减、买一送一、第二件半价、新店开业折扣\n"
    "- 日化常规清洁表述：深层清洁、控油、去角质、洗后不紧绷（属化妆品清洁功效，非疾病治疗）\n"
    "- 序数词与比喻：「第一人称」「第一波上新」「颜值天花板」不是绝对化用语；"
    "绝对化用语指对商品的排他性最高级评价（最X、第一品牌、国家级）\n"
    "- 资质类正常表述：正品保障、支持验货、七天无理由退换\n"
    "只输出一个 JSON 对象，格式："
    '{"findings": [{"type": "八类之一:极限词|虚假误导|医疗功效|保健食品|肖像权|名誉权|隐私|低俗（贬损竞品/商业诋毁归入名誉权）",'
    ' "fragment": "文案中违规的原句片段", "article": "如 广告法·第九条（必须来自给定法条列表）",'
    ' "verdict": "violation|suspicious|not", "reason": "一句话判定理由",'
    ' "suggestion": "一句话改写建议"}]}'
    "无命中时 findings 为空数组。"
)


def audit_semantic(text: str, index: LawIndex, llm, k: int | None = None,
                   extra_refs: list[tuple[str, str]] | None = None,
                   include_laws: bool = True) -> list[dict]:
    """语义通道：混合检索（向量 top-k ∪ 关键词层指向的法条）→ LLM 一次比对 → findings。

    extra_refs：keyword 层给出的（法名, 条号）——口语↔法条术语存在语义鸿沟，
    词库的「预期法条」映射是最可靠的lexical桥，直接并入候选集并置前。
    include_laws=False：消融模式，不给法条凭模型自身知识判断（quote 恒为空）。
    """
    if include_laws:
        candidates = index.search(text, k or index.k)
        if extra_refs:
            seen = {(r["law"], r["article"]) for r in candidates}
            for law, article in extra_refs:
                row = index.get_by_ref(law, article)
                if row and (row["law"], row["article"]) not in seen:
                    candidates.insert(0, {**row, "score": 1.0, "via": "keyword"})
                    seen.add((row["law"], row["article"]))
    else:
        candidates = []  # 消融模式：无候选、无引用回填，判定完全依赖模型自身知识
    law_block = "\n".join(
        f"- {r['law']}·{r['article']}（适用场景：{r['scene_note'] or '见条文'}）\n  原文：{r['text']}"
        for r in candidates
    ) if include_laws else "（无 RAG 消融模式：本次不提供法条，仅凭你的法律知识判断，article 给出你认为适用的法条名即可）"
    prompt = f"待审文案：\n{text}\n\n给定法条：\n{law_block}\n\n请输出 JSON 判定。"
    raw = llm.chat(prompt, system=JUDGE_SYSTEM, json_mode=True, temperature=0.1)
    data = extract_json(raw)
    if not isinstance(data.get("findings"), list):
        raise ValueError("模型审核响应缺少 findings 数组")

    corpus = {(r["law"], r["article"]): r["text"] for r in candidates}
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
            "source": "rag",
            "_strength": f.get("verdict", "suspicious"),  # violation / suspicious
        })
    return findings
