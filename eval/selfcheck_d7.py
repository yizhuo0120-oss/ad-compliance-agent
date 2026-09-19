"""卡4/D7 自查：T013/T014 复跑 + 三张海报（违规合成/小字密集/合规采集）全流程。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine.llm_client import LLMClient
from engine.pipeline import audit_text, audit_image, finalize
from engine.rag_layer import LawIndex

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    llm = LLMClient()
    idx = LawIndex(k=5)
    idx.build()

    print("=== T013/T014 复跑 ===")
    for text in ["吊打同行，别家都是假货，我们才是正品", "碾压大牌品质，隔壁家根本没法比"]:
        r = finalize(audit_text(llm, text, idx))
        arts = ["{}·{}".format(f["law"]["name"], f["law"]["article"]) for f in r["findings"]]
        print("  {} {}".format(r["risk_level"], arts))

    print("=== D7 三张海报自查 ===")
    for img in ["syn_violation_extreme.png", "syn_dense_smalltext.png",
                "01072aceb8127ff0fa81803648f52993.png"]:
        r = finalize(audit_image(llm, ROOT / "data" / "eval_images" / img, idx))
        arts = ["{}({})".format(f["type"], f["source"]) for f in r["findings"]]
        print("  {}… 风险={} 转写{}段 findings={}".format(
            img[:16], r["risk_level"], len(r["transcript"]["texts"]), arts))


if __name__ == "__main__":
    main()
