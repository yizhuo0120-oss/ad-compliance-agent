"""卡3/D6 基线：40 条文案全量过文案通道，落盘报告 + 打印粗基线。

正式指标（拦截率/误报率/消融）在卡5 的 run_eval.py；本脚本只证明「跑通 + 有基线分」。
用法：python eval/run_baseline.py [--limit N]
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine.llm_client import LLMClient  # noqa: E402
from engine.pipeline import audit_text, finalize  # noqa: E402
from engine.rag_layer import LawIndex  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "eval" / "results" / "baseline_text.jsonl"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    cases = [json.loads(l) for l in (ROOT / "data" / "eval_cases.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.limit:
        cases = cases[: args.limit]

    llm = LLMClient()
    index = LawIndex(k=5)
    index.build()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    cross = Counter()  # (ground_truth, engine_risk)
    with OUT.open("w", encoding="utf-8") as f:
        for i, c in enumerate(cases, 1):
            try:
                report = finalize(audit_text(llm, c["text"], index))
            except Exception as e:  # 单条失败不中断基线
                report = {"error": str(e), "risk_level": "error", "findings": []}
            f.write(json.dumps({"id": c["id"], "ground_truth": c["label"],
                                "report": report}, ensure_ascii=False) + "\n")
            cross[(c["label"], report.get("risk_level", "error"))] += 1
            print(f"[{i}/{len(cases)}] {c['id']} 真值={c['label']} 引擎={report.get('risk_level')}"
                  f" findings={len(report.get('findings', []))}")

    print("\n==== 粗基线（真值 × 引擎） ====")
    for k, v in sorted(cross.items()):
        print(f"  {k[0]:<10} → {k[1]:<10} : {v}")
    viol = sum(v for (g, r), v in cross.items() if g == "violation" and r != "compliant")
    comp_err = sum(v for (g, r), v in cross.items() if g == "compliant" and r != "compliant")
    n_v = sum(v for (g, _), v in cross.items() if g == "violation")
    n_c = sum(v for (g, _), v in cross.items() if g == "compliant")
    if n_v and n_c:
        print(f"粗拦截率（violation 被判非合规）：{viol}/{n_v} = {viol / n_v:.0%}")
        print(f"粗误报率（compliant 被判非合规）：{comp_err}/{n_c} = {comp_err / n_c:.0%}")
    print(f"报告已写入 {OUT}")


if __name__ == "__main__":
    main()
