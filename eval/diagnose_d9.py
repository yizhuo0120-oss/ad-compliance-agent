"""D9 诊断：复现 T012 的 error + 检查 2 张图片误报的 findings 来源。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine.llm_client import LLMClient
from engine.pipeline import audit_image, audit_text, finalize
from engine.rag_layer import LawIndex

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    llm = LLMClient()
    idx = LawIndex(k=5)
    idx.build()

    print("=== T012 复跑（看是否稳定复现 error） ===")
    text = "保健茶安全无副作用，有病治病无病防病"
    try:
        r = finalize(audit_text(llm, text, idx))
        print("  风险:", r["risk_level"], "| findings:", len(r["findings"]))
    except Exception as e:
        print("  仍然 error:", str(e)[:300])

    print("=== 2 张图片误报 findings 来源 ===")
    for img in ["6a73d4dc769a068d37b8cfda82d572e6.png", "ffce0adf7b09e3ddfef88857e4c4c04d.png"]:
        r = finalize(audit_image(llm, ROOT / "data" / "eval_images" / img, idx))
        print(" ", img[:14], r["risk_level"])
        for f in r["findings"]:
            print("    [{}:{}] {} <- {}".format(f["type"], f["source"], f["fragment"][:40], f["reason"][:60]))


if __name__ == "__main__":
    main()
