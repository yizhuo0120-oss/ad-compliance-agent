"""卡5 · D8 正式评估：全指标 + 有/无 RAG 消融。

判定口径（写死）：
  拦截：GT=violation 的样本，引擎判为 violation 或 suspicious 均记拦截
  误报：GT=compliant 的样本，引擎判为非 compliant 即记误报
  疑似命中：GT=suspicious 的样本，引擎判为非 compliant 记命中（单列，不入 headline）

指标：
  文案侧（40 条）：拦截率 / 误报率 / 向量检索命中率 / 法条引用准确率
  图片侧（22 张）：拦截率 / 误报率 / 引用准确率 / 转写完整率（合成图真值）
  消融：use_rag full vs off 各跑一遍文案侧，对比拦截/误报/引用/溯源率

用法：python eval/run_eval.py [--skip-images] [--skip-ablation]
"""
import argparse
import json
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys_path = str(ROOT)
if sys_path not in __import__("sys").path:
    __import__("sys").path.insert(0, sys_path)

from engine.keyword_layer import normalize  # noqa: E402
from engine.llm_client import LLMClient  # noqa: E402
from engine.pipeline import audit_image, audit_text, finalize  # noqa: E402
from engine.rag_layer import LawIndex  # noqa: E402

OUT_DIR = ROOT / "eval" / "results"


def norm_ref(s: str) -> str:
    return s.replace(" ", "")


def cited_refs(report: dict) -> list[str]:
    return [norm_ref(f["law"]["name"] + "·" + f["law"]["article"])
            for f in report.get("findings", [])]


def eval_text(llm, index, cases, use_rag, tag):
    rows, cross = [], Counter()
    caught = fp = r_total = c_total = s_total = s_hit = 0
    cite_ok = cite_total = 0
    vec_hit = vec_total = 0
    t0 = time.time()
    for i, c in enumerate(cases, 1):
        report = None
        for attempt in (1, 2):  # 偶发 API/JSON 抖动重试一次
            try:
                report = finalize(audit_text(llm, c["text"], index, use_rag=use_rag))
                break
            except Exception as e:
                if attempt == 2:
                    report = {"risk_level": "error", "findings": [], "error": str(e)[:150]}
                else:
                    time.sleep(3)
        risk = report.get("risk_level", "error")
        exp = [norm_ref(a) for a in c.get("expected_articles", [])]

        if c["label"] == "violation":
            r_total += 1
            caught += risk in ("violation", "suspicious")
        elif c["label"] == "compliant":
            c_total += 1
            fp += risk != "compliant"
        else:
            s_total += 1
            s_hit += risk != "compliant"

        for ref in cited_refs(report):
            cite_total += 1
            cite_ok += ref in exp

        if c["label"] in ("violation", "suspicious") and exp:
            vec_total += 1
            top = {norm_ref(r["law"] + "·" + r["article"]) for r in index.search(c["text"], k=5)}
            vec_hit += any(e in top for e in exp)

        cross[(c["label"], risk)] += 1
        rows.append({"id": c["id"], "gt": c["label"], "risk": risk,
                     "cited": cited_refs(report), "expected": exp})
        print(f"  [{i}/{len(cases)}] {c['id']} {c['label']}→{risk}", flush=True)

    m = {
        "tag": tag,
        "n": len(cases),
        "catch_rate": round(caught / r_total, 4) if r_total else None,
        "fp_rate": round(fp / c_total, 4) if c_total else None,
        "suspicious_hit": f"{s_hit}/{s_total}",
        "vector_hit_rate": round(vec_hit / vec_total, 4) if vec_total else None,
        "citation_acc": round(cite_ok / cite_total, 4) if cite_total else None,
        "citations": cite_total,
        "cross": {f"{g}->{r}": v for (g, r), v in sorted(cross.items())},
        "elapsed_s": int(time.time() - t0),
    }
    print(f"== [{tag}] 拦截 {m['catch_rate']} 误报 {m['fp_rate']} "
          f"向量命中 {m['vector_hit_rate']} 引用准确 {m['citation_acc']} "
          f"({cite_total} 次引用) 用时 {m['elapsed_s']}s", flush=True)
    return m, rows


def eval_images(llm, index, annos):
    rows = []
    caught = fp = v_total = c_total = 0
    cite_ok = cite_total = 0
    comp_ok = comp_total = 0
    stab_ok = stab_total = 0
    t0 = time.time()
    for i, a in enumerate(annos, 1):
        img = ROOT / "data" / "eval_images" / a["image"]
        report = None
        for attempt in (1, 2):
            try:
                report = finalize(audit_image(llm, img, index))
                break
            except Exception as e:
                if attempt == 2:
                    report = {"risk_level": "error", "findings": [], "error": str(e)[:150]}
                else:
                    time.sleep(3)
        risk = report.get("risk_level", "error")
        exp = [norm_ref(x) for x in a.get("expected_articles", [])]

        if a["risk_level"] == "violation":
            v_total += 1
            caught += risk in ("violation", "suspicious")
        elif a["risk_level"] == "compliant":
            c_total += 1
            fp += risk != "compliant"

        for ref in cited_refs(report):
            cite_total += 1
            cite_ok += ref in exp

        # 转写完整率：合成图 key_texts 为构造真值；采集图对比上次转写稿（稳定性参考）
        got = normalize("".join((report.get("transcript") or {}).get("texts", [])))
        for kt in a.get("key_texts", []):
            if a["source"] == "synthetic":
                comp_total += 1
                comp_ok += normalize(kt) in got
            else:
                stab_total += 1
                stab_ok += normalize(kt) in got

        rows.append({"image": a["image"], "gt": a["risk_level"], "risk": risk,
                     "cited": cited_refs(report)})
        print(f"  [{i}/{len(annos)}] {a['image'][:14]} {a['risk_level']}→{risk} "
              f"转写{len((report.get('transcript') or {}).get('texts', []))}段", flush=True)

    m = {
        "tag": "image",
        "n": len(annos),
        "catch_rate": round(caught / v_total, 4) if v_total else None,
        "fp_rate": round(fp / c_total, 4) if c_total else None,
        "citation_acc": round(cite_ok / cite_total, 4) if cite_total else None,
        "citations": cite_total,
        "transcript_completeness": round(comp_ok / comp_total, 4) if comp_total else None,
        "transcript_total": comp_total,
        "transcript_stability_collected": round(stab_ok / stab_total, 4) if stab_total else None,
        "elapsed_s": int(time.time() - t0),
    }
    print(f"== [image] 拦截 {m['catch_rate']} 误报 {m['fp_rate']} 引用 {m['citation_acc']} "
          f"转写完整率 {m['transcript_completeness']} 用时 {m['elapsed_s']}s", flush=True)
    return m, rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-images", action="store_true")
    ap.add_argument("--skip-ablation", action="store_true")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cases = [json.loads(l) for l in (ROOT / "data" / "eval_cases.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    annos = [json.loads(l) for l in (ROOT / "data" / "eval_images" / "annotations.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]

    llm = LLMClient()
    index = LawIndex(k=5)
    index.build()

    all_metrics = {}
    all_metrics["text_rag_full"], rows_full = eval_text(llm, index, cases, "full", "text-RAG")
    with (OUT_DIR / "d8_text_full.jsonl").open("w", encoding="utf-8") as f:
        for r in rows_full:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    if not args.skip_ablation:
        all_metrics["text_rag_off"], rows_off = eval_text(llm, index, cases, "off", "text-无RAG")
        with (OUT_DIR / "d8_text_norag.jsonl").open("w", encoding="utf-8") as f:
            for r in rows_off:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    if not args.skip_images:
        all_metrics["image"], rows_img = eval_images(llm, index, annos)
        with (OUT_DIR / "d8_images.jsonl").open("w", encoding="utf-8") as f:
            for r in rows_img:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    (OUT_DIR / "d8_metrics.json").write_text(
        json.dumps(all_metrics, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n==== D8 指标汇总 ====")
    print(json.dumps(all_metrics, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
