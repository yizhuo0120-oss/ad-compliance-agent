"""卡3 验收：双形态评测集加载器 + 自检。

用法：python eval/eval_dataset.py
验收线：两类评测集可加载、字段完整、图片文件齐全、分布达标。
"""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMG_DIR = ROOT / "data" / "eval_images"


def load_text_cases(path: Path = ROOT / "data" / "eval_cases.jsonl") -> list[dict]:
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    for r in rows:
        assert r["label"] in {"violation", "suspicious", "compliant"}, f"{r['id']} label 非法"
        assert isinstance(r["expected_articles"], list), f"{r['id']} expected_articles 须为数组"
    return rows


def load_image_cases(annotations: Path = IMG_DIR / "annotations.jsonl") -> list[dict]:
    rows = [json.loads(l) for l in annotations.read_text(encoding="utf-8").splitlines() if l.strip()]
    missing = [r["image"] for r in rows if not (IMG_DIR / r["image"]).exists()]
    assert not missing, f"缺失图片文件：{missing}"
    return rows


def main() -> None:
    texts = load_text_cases()
    images = load_image_cases()

    tl = Counter(r["label"] for r in texts)
    ttypes = Counter(r["violation_type"] for r in texts if r["violation_type"])
    il = Counter(r["risk_level"] for r in images)
    isrc = Counter(r["source"] for r in images)

    print(f"文案评测集：{len(texts)} 条  分布 {dict(tl)}")
    print(f"  违规类型覆盖：{dict(ttypes)}")
    print(f"海报评测集：{len(images)} 张  风险分布 {dict(il)}  来源 {dict(isrc)}")
    n_violation_images = il.get("violation", 0)
    assert tl.get("violation") and tl.get("compliant"), "文本集缺 violation/compliant 样本"
    assert n_violation_images > 0, "图片集无违规样本，无法测拦截率"
    assert il.get("compliant", 0) >= 5, "图片集合规对照不足"
    print("✅ 验收通过：双形态评测集可加载、字段完整、图片齐全、分布达标")


if __name__ == "__main__":
    main()
