"""卡3 · D2 下午：法律语料按条结构化。

输入：../../广告法+民法典/*.md（用户提供）
输出：data/laws/guanggaofa.jsonl、data/laws/minfadian.jsonl
字段：law / article(条号原文) / article_no(数字) / text(条文原文) / scene_note(适用场景备注)

用法：python eval/build_laws.py
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT.parent / "广告法+民法典"
OUT = ROOT / "data" / "laws"

CN = "一二三四五六七八九十百千零〇两"
ART_RE = re.compile(rf"第[{CN}]+条")


def cn2int(s: str) -> int:
    d = {"零": 0, "〇": 0, "一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    u = {"十": 10, "百": 100, "千": 1000}
    total, num = 0, 0
    for ch in s:
        if ch in d:
            num = d[ch]
        elif ch in u:
            total += (num or 1) * u[ch]
            num = 0
    return total + num


def clean(t: str) -> str:
    t = re.sub(r"^#+\s*", "", t)
    return re.sub(r"\s+", "", t).strip()


def split_articles(chunk: str) -> list[tuple[str, str]]:
    """按行首「第X条」切分，返回 [(条号, 条文)]。行首锚定避免切到正文里的条引用。"""
    parts = re.split(rf"(?m)^(?=第[{CN}]+条)", chunk)
    out = []
    for p in parts:
        m = ART_RE.match(p.strip())
        if not m:
            continue
        body = clean(p)
        out.append((m.group(0), body[len(m.group(0)):]))
    return out


# 适用场景备注（重点条目；其余留空，D6 RAG 检索不受影响，D8 后按 badcase 补）
GGF_NOTES = {
    8: "宣传中的数据、资格、获奖等须真实准确清楚；「专利产品」「获奖」类表述需可证实",
    9: "极限词与禁止情形核心条款；海报文案出现「最/第一/国家级/顶级/独家」等绝对化用语即命中",
    11: "引用数据、调查结果须真实准确并标明出处；「销量领先」类无依据数据的判定依据",
    13: "广告不得贬低其他生产经营者的商品或服务；「吊打同行」「比XX好十倍」类贬损竞品的判定依据",
    17: "非医疗广告不得涉及疾病治疗功能、不得用医疗用语；化妆品/食品暗示疗效的判定依据",
    18: "保健食品广告不得有功效/安全性断言保证，须标明「本品不能代替药物」",
    28: "虚假广告定义；虚假或引人误解的内容欺骗误导消费者即构成，含功效无依据承诺",
}
MFD_NOTES = {
    990: "人格权定义与保护范围",
    1018: "肖像权定义：自然人有权依法制作、使用、公开或许可他人使用自己的肖像",
    1019: "未经同意不得制作/使用/公开他人肖像；禁止丑化污损或利用信息技术手段伪造（AI 换脸）——海报含真人形象未授权的判定依据",
    1020: "肖像合理使用的法定情形（个人学习、新闻报道等）",
    1024: "名誉权：不得以侮辱、诽谤等方式侵害他人名誉；贬损特定经营者商誉的判定依据",
    1032: "隐私权定义：任何组织或个人不得以刺探、侵扰、泄露、公开等方式侵害",
    1033: "隐私侵权禁止行为清单（私密空间、私密活动、私密部位等）",
    1034: "个人信息定义与保护；处理个人信息须合法正当必要",
    1035: "个人信息处理须征得同意、明示规则",
    1165: "过错侵权一般条款：因过错侵害他人民事权益造成损害的应担责",
    1166: "无过错侵权：法律规定无过错也应担责的情形",
}


def build_guanggaofa() -> list[dict]:
    raw = (SRC / "中华人民共和国广告法.md").read_text(encoding="utf-8")
    rows = []
    for art, body in split_articles(raw):
        no = cn2int(art[1:-1])
        rows.append({
            "law": "广告法", "article": art, "article_no": no,
            "text": body, "scene_note": GGF_NOTES.get(no, ""),
        })
    return rows


def build_minfadian() -> list[dict]:
    raw = (SRC / "中华人民共和国民法典.md").read_text(encoding="utf-8")
    # 按编标题切块，取第四编人格权（990~1039）与第七编侵权责任（1164~1258）
    parts = re.split(r"(?m)^##\s*(第[一二三四五六七八九十]+编.*)$", raw)
    chunks = dict(zip(parts[1::2], parts[2::2]))
    target = {name: rng for name, rng in chunks.items() if name.startswith(("第四编", "第七编"))}
    ranges = {"第四编": (990, 1039), "第七编": (1164, 1258)}
    rows = []
    for name, chunk in target.items():
        lo, hi = next(v for k, v in ranges.items() if name.startswith(k))
        for art, body in split_articles(chunk):
            no = cn2int(art[1:-1])
            if lo <= no <= hi:
                rows.append({
                    "law": "民法典", "article": art, "article_no": no,
                    "text": body, "scene_note": MFD_NOTES.get(no, ""),
                })
    return sorted(rows, key=lambda r: r["article_no"])


def dump(rows: list[dict], path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    gg = build_guanggaofa()
    mf = build_minfadian()
    dump(gg, OUT / "guanggaofa.jsonl")
    dump(mf, OUT / "minfadian.jsonl")
    noted = lambda rs: sum(1 for r in rs if r["scene_note"])
    print(f"广告法：{len(gg)} 条（备注 {noted(gg)} 条），条号范围 {gg[0]['article_no']}~{gg[-1]['article_no']}")
    print(f"民法典：{len(mf)} 条（备注 {noted(mf)} 条），编内条号范围 {mf[0]['article_no']}~{mf[-1]['article_no']}")
    gaps = [gg[i]["article_no"] for i in range(1, len(gg)) if gg[i]["article_no"] != gg[i - 1]["article_no"] + 1]
    print(f"广告法条号断档：{gaps or '无'}")
