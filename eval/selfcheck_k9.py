"""卡9 通关自检：合成测试视频 → 报告定位到时间戳。

构造真值：~2.5s 画面+口播「全场最低价」；~10.5s 画面「行业第一品牌」+ 口播「行业第一」。
期望：报告 risk=violation，findings 含「最低价」「第一」且 location 标到画面/口播时间戳。
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.llm_client import LLMClient  # noqa: E402
from engine.pipeline import audit_video, finalize  # noqa: E402
from engine.rag_layer import LawIndex  # noqa: E402


def main() -> None:
    video = ROOT / "data" / "test_video.mp4"
    llm = LLMClient()
    idx = LawIndex(k=5)
    idx.build()

    t0 = time.time()
    r = finalize(audit_video(llm, video, idx))
    elapsed = time.time() - t0

    print(f"风险：{r['risk_level']} ｜ {r['summary']} ｜ 耗时 {elapsed:.0f}s（预算 90s）")
    for f in r["findings"]:
        print(f"  [{f['type']}|{f['source']}|{f.get('location') or '未定位'}] "
              f"{f['fragment'][:36]} → {f['law']['name']}·{f['law']['article']}")

    locs = [f.get("location") for f in r["findings"]]
    frags = " ".join(f["fragment"] for f in r["findings"])
    located = sum(1 for l in locs if l and ("画面" in l or "口播" in l))
    assert r["risk_level"] == "violation", "应判违规"
    assert elapsed <= 90, "超预算"
    assert located >= 2, f"时间戳定位不足：{locs}"
    assert "最低" in frags and "第一" in frags, f"构造真值关键词未全部命中：{frags}"
    print(f"时间戳定位：{located}/{len(r['findings'])} 条 findings 标到画面/口播位置")


if __name__ == "__main__":
    main()
