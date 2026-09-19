"""卡3 · D4：生成 annotations.jsonl —— 合成图构造真值 + 采集图人工核对标注。

合成图：标注即构造真值（引擎按图上文字判定的期望结果）。
采集图：以 annotations_draft.json（视觉模型预转写）为底，逐张人工核对后定稿。

字段：image / source(collected|synthetic) / risk_level / violation_types /
      expected_articles / key_texts(转写真值，供转写完整率评测) / visual / note
用法：python eval/finalize_annotations.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMG_DIR = ROOT / "data" / "eval_images"

# —— 采集图人工核对结果（逐张判定；label 依据手册 6.2 清单与判定口径） ——
DECISIONS = {
    "01072aceb8127ff0fa81803648f52993.png": ("compliant", [], [], "图库水印（昵图网），著作权留存提示，非广告内容违规"),
    "0431bec571919a3d564f0f03266156e8.png": ("compliant", [], [], "「全场五折」属正常促销表达，无证据表明虚假"),
    "0ae63c4441f168ddc7d367cf2abd86d6.png": ("suspicious", ["虚假误导"], ["广告法·第九条", "广告法·第二十八条"], "角落人民网英文标识，涉嫌暗示官方媒体背书"),
    "2059cad1c0ee189bc2bb0b9f05516074.png": ("suspicious", ["极限词"], ["广告法·第九条"], "英文装饰语 PERFECT 属绝对化用语，执法实践中风险较低"),
    "3d125ef88d99bcbe45404eefe41c827c.png": ("compliant", [], [], "「第一波」为序数词非绝对化用语——关键词层误报陷阱样本"),
    "3d8e49b822a0ce49a6c2cfa42aeb13f3.png": ("compliant", [], [], "「部分商品」「限时」范围明确，规范促销"),
    "44e0c140968efadd59c0a7caacba2edb.png": ("compliant", [], [], "满减承诺明确，无误导"),
    "475a3f0bcf0b32a8b93ef0441a026aeb.png": ("suspicious", ["极限词"], ["广告法·第九条"], "英文标语含 best；模特肖像授权无法核实，不单独计违规"),
    "4ac208e8c88160e662b7ad9ae59beac2.png": ("compliant", [], [], "图库水印（昵享网），非广告内容违规"),
    "65117f3501ae850a6f46917749073b7a.png": ("compliant", [], [], "节庆卡通海报，无违规"),
    "6a73d4dc769a068d37b8cfda82d572e6.png": ("suspicious", ["虚假误导"], ["广告法·第十一条", "广告法·第二十八条"],
                                             "D9 复核修正：引擎指出促销时间「20:00AM-10.07 23.59AM」制式混用且起止矛盾，"
                                             "人工复核属实，GT 由 compliant 改为 suspicious"),
    "7f14bdc2c67017418119688e02243dc9.png": ("compliant", [], [], "品牌态度标语，「不做女神做自己」无违规"),
    "944f8afbc29315fd117241cd2d76b47b.png": ("compliant", [], [], "时装上新海报，无违规"),
    "a4ce7587e01a0217b057e62817139891.png": ("compliant", [], [], "品牌情感文案海报，无违规"),
    "d50fe18eb62986ce02db5f53a61b9e1f.png": ("compliant", [], [], "羊毛衫专场直播预告，无违规"),
    "f7d323e50e9f7edcb0a559fe2a657781.png": ("compliant", [], [], "经典百搭新品上市，无违规"),
    "ffce0adf7b09e3ddfef88857e4c4c04d.png": ("suspicious", ["低俗"], ["广告法·第九条"],
                                             "D9 复核修正：间隔字母「P E A C O C K L A K E」连读含不雅俚语，"
                                             "人工复核属可争议的边界案例，GT 由 compliant 改为 suspicious"),
}

# —— 合成图构造真值 ——
SYNTHETIC = {
    "syn_violation_extreme.png": ("violation", ["极限词"], ["广告法·第九条"],
                                  ["全场最低价", "行业第一品牌", "国家级工艺 值得拥有", "最终解释权归本店所有"],
                                  "构造样本：极限词促销海报"),
    "syn_violation_medical.png": ("violation", ["医疗功效"], ["广告法·第十七条"],
                                  ["根治痘痘", "消炎杀菌 一步到位", "医生推荐 临床验证", "使用效果因人而异"],
                                  "构造样本：化妆品暗示疗效"),
    "syn_violation_health.png": ("violation", ["保健食品"], ["广告法·第十八条"],
                                 ["安全无副作用", "有病治病 无病防病", "可长期替代药物", "本品不能代替药物"],
                                 "构造样本：保健食品违规断言（图中已印合规范声明，观察引擎能否只打违规断言）"),
    "syn_violation_disparage.png": ("violation", ["名誉权"], ["广告法·第十三条", "民法典·第一千零二十四条"],
                                    ["吊打同行大牌", "别家都是假货", "我们才是工厂正品", "活动最终解释权归本店所有"],
                                    "构造样本：贬损竞品"),
    "syn_dense_smalltext.png": ("violation", ["极限词"], ["广告法·第九条"],
                                ["史上最全优惠清单（小字压测1）", "全场最佳性价比之选（小字压测2）",
                                 "销量第一的王牌单品（小字压测3）", "独家顶级原料产地直供（小字压测4）",
                                 "国家专利配方技术支持（小字压测5）", "品质生活节", "匠心好物 焕新上线"],
                                "构造样本：小字密集压测转写完整率，6 处违规中 5 处在底部小字"),
}


def main() -> None:
    draft_path = IMG_DIR / "annotations_draft.json"
    draft = json.loads(draft_path.read_text(encoding="utf-8")) if draft_path.exists() else {}
    rows = []
    for name, v in draft.items():
        level, types, articles, note = DECISIONS[name]
        rows.append({
            "image": name, "source": "collected", "risk_level": level,
            "violation_types": types, "expected_articles": articles,
            "key_texts": v.get("texts", []), "visual": v.get("visual_elements", ""),
            "note": note,
        })
    for name, (level, types, articles, key_texts, note) in SYNTHETIC.items():
        rows.append({
            "image": name, "source": "synthetic", "risk_level": level,
            "violation_types": types, "expected_articles": articles,
            "key_texts": key_texts, "visual": "PIL 构造海报", "note": note,
        })
    out = IMG_DIR / "annotations.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    from collections import Counter
    lv = Counter(r["risk_level"] for r in rows)
    print(f"标注完成：{len(rows)} 张 → {out}")
    print(f"风险分布：{dict(lv)}")


if __name__ == "__main__":
    main()
