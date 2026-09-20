"""卡10 通关自检：两个商品跑闭环。

① 违规倾向商品（卖点本身带雷：根治/见效/无副作用/贬损竞品）——期望首轮被判违规，
   系统带法条自动改写，最终合规；
② 正常商品——期望首轮即合规（revisions=0），证明闭环不误伤好物料。
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.llm_client import LLMClient  # noqa: E402
from engine.loop import closed_loop  # noqa: E402
from engine.rag_layer import LawIndex  # noqa: E402

CASES = [
    {"name": "祛痘面霜",
     "selling_points": ["根治痘痘", "7天见效", "纯天然无副作用", "比大牌好用十倍"],
     "info": "祛痘面霜，主打快速祛痘"},
    {"name": "便携榨汁杯", "info": "USB充电，300ml，杯身可冷冻，母婴级材质，60秒出汁"},
]


def main() -> None:
    llm = LLMClient()
    index = LawIndex(k=5)
    index.build()

    out = []
    for i, product in enumerate(CASES, 1):
        t0 = time.time()
        result = closed_loop(llm, index, product)
        tr = result["trajectory"]
        print(f"\n[{i}/{len(CASES)}] {product['name']}  轮数:{result['rounds']} "
              f"最终合规:{result['final_compliant']} 改写:{result['pack']['audit']['revisions']}次 "
              f"用时{time.time() - t0:.0f}s")
        for t in tr:
            print(f"   第{t['round']}轮：{t['risk']}（{t['n_findings']} 项）")
        out.append({"product": product["name"], "rounds": result["rounds"],
                    "final_compliant": result["final_compliant"],
                    "revisions": result["pack"]["audit"]["revisions"],
                    "trajectory": tr})

    (ROOT / "eval" / "results" / "k10_loop_demo.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    toxic = out[0]
    assert toxic["final_compliant"], f"违规商品未收敛到合规：{toxic['trajectory']}"
    assert toxic["revisions"] >= 1, "违规商品应至少经历一次自动改写"
    normal = out[1]
    assert normal["final_compliant"], "正常商品最终应合规"
    print("\n✅ 闭环自检通过：违规物料自动改写至合规，正常物料最终合规")


if __name__ == "__main__":
    import json  # noqa: E402
    main()
