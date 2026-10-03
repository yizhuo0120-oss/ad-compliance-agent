"""Serverless 法条检索：中文二元词 BM25，不加载本地模型或 FAISS。

与本地 BGE 索引使用相同 search / get_by_ref 接口；关键词指向的法条
仍由 audit_semantic 合并。该检索模式应独立评测，不继承 BGE 版指标。
"""
from __future__ import annotations

import math
import re
from collections import Counter

from engine.rag_layer import load_corpus


def _terms(text: str) -> list[str]:
    terms = []
    for run in re.findall(r"[\u3400-\u9fff]+|[a-z0-9]+", text.lower()):
        if re.fullmatch(r"[a-z0-9]+", run) or len(run) == 1:
            terms.append(run)
        else:
            terms.extend(run[i:i + 2] for i in range(len(run) - 1))
    return terms


class WebLawIndex:
    def __init__(self, k: int = 6):
        self.k = k
        self.rows = load_corpus()
        self._by_ref = {(r["law"], r["article"]): r for r in self.rows}
        self._docs = [Counter(_terms(f"{r['scene_note']} {r['scene_note']} {r['text']}"))
                      for r in self.rows]
        self._lengths = [sum(doc.values()) for doc in self._docs]
        self._average = sum(self._lengths) / max(1, len(self.rows))
        df = Counter(term for doc in self._docs for term in doc)
        self._idf = {term: math.log(1 + (len(self.rows) - count + .5) / (count + .5))
                     for term, count in df.items()}

    def get_by_ref(self, law: str, article: str) -> dict | None:
        return self._by_ref.get((law, article))

    def search(self, query: str, k: int | None = None) -> list[dict]:
        query_terms = set(_terms(query))
        scores = []
        for i, doc in enumerate(self._docs):
            score = 0.0
            for term in query_terms:
                freq = doc.get(term, 0)
                if freq:
                    denominator = freq + 1.5 * (.25 + .75 * self._lengths[i] / max(self._average, 1))
                    score += self._idf[term] * freq * 2.5 / denominator
            scores.append((score, i))
        ranked = sorted(scores, key=lambda item: (-item[0], item[1]))[:k or self.k]
        return [{**self.rows[i], "score": score} for score, i in ranked]
