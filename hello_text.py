"""卡2 · hello_text：违禁词最小链路（纯本地，不调 API，零成本）。

通关标准：违规文案能输出命中的违禁词。
说明：这里是最简子串匹配；D5 将升级为全半角/繁简归一化 + 正则变体 + 单测。
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORDS_PATH = ROOT / "data" / "banned_words.txt"


def load_words(path: Path = WORDS_PATH) -> list[str]:
    """加载违禁词库：一行一词，# 开头为注释。"""
    words = []
    for line in path.read_text(encoding="utf-8").splitlines():
        w = line.strip()
        if w and not w.startswith("#"):
            words.append(w)
    return words


def match(text: str, words: list[str]) -> list[str]:
    """返回命中的违禁词列表。"""
    return [w for w in words if w in text]


if __name__ == "__main__":
    words = load_words()
    print(f"违禁词库已加载 {len(words)} 词\n")

    samples = [
        ("全网最低价，行业第一品牌，点击抢购！", True),   # 期望命中
        ("品质好物，限时特惠，欢迎选购", False),          # 期望干净（注意「最终」不含裸「最」所以不误伤）
        ("根治痘痘的神奇面霜，消炎杀菌", True),           # 期望命中医疗类
    ]
    for text, _ in samples:
        hits = match(text, words)
        print(f"[{'违规' if hits else '合规'}] {text}")
        if hits:
            print(f"       命中：{'、'.join(hits)}")
