"""卡3 · D4：海报评测图批量预转写（半自动标注的第一步）。

对 data/eval_images/ 下每张图调用视觉模型，产出结构化转写草稿：
data/eval_images/annotations_draft.json —— 人工核对后整理为 annotations.jsonl。

支持断点续跑（已转写的图自动跳过）。用法：python eval/pretranscribe_images.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine.llm_client import LLMClient  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
IMG_DIR = ROOT / "data" / "eval_images"
DRAFT = IMG_DIR / "annotations_draft.json"

PROMPT = (
    "你是广告合规标注助手。只输出一个 JSON 对象，不要任何多余文字，结构如下：\n"
    '{"texts": ["图中出现的每一段文字，按顺序逐字转写"],'
    ' "visual_elements": "一句话描述画面元素：人物/产品/场景/标识",'
    ' "suspected": [{"type": "疑似违规类型(极限词|虚假误导|医疗功效|保健食品|肖像权|名誉权|隐私|低俗)",'
    ' "fragment": "依据片段", "why": "一句话理由"}]}\n'
    "若无疑似违规，suspected 为空数组。texts 必须包含角落小字与免责声明。"
)


def main() -> None:
    draft = json.loads(DRAFT.read_text(encoding="utf-8")) if DRAFT.exists() else {}
    llm = LLMClient()
    images = sorted(p for p in IMG_DIR.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg"})
    print(f"共 {len(images)} 张图，已转写 {len(draft)} 张")
    for i, img in enumerate(images, 1):
        if img.name in draft:
            continue
        try:
            raw = llm.vision(PROMPT, img)
            data = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
            draft[img.name] = data
            DRAFT.write_text(json.dumps(draft, ensure_ascii=False, indent=1), encoding="utf-8")
            n = len(data.get("suspected", []))
            print(f"[{i}/{len(images)}] OK {img.name} 文字{len(data.get('texts', []))}段 疑似{n}项")
        except Exception as e:
            print(f"[{i}/{len(images)}] FAIL {img.name}: {e}")
    print(f"草稿已写入 {DRAFT}")


if __name__ == "__main__":
    main()
