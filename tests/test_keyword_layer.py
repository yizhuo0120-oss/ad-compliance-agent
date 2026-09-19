"""keyword_layer 单测（D5 通关：单测通过）。"""
from engine.keyword_layer import audit, load_words, match, normalize


def test_normalize_fullwidth_and_traditional():
    assert normalize("全場最低價") == normalize("全场最低价")
    assert normalize("ＮＯ．１") == "no.1"


def test_category_header_parsed():
    words = load_words()
    by_word = {w["word"]: w for w in words}
    assert by_word["最低价"]["type"] == "极限词"
    assert "广告法·第九条" in by_word["最低价"]["law_refs"]
    assert by_word["根治"]["type"] == "医疗功效"
    assert "广告法·第十七条" in by_word["根治"]["law_refs"]


def test_match_hits_and_spans():
    words = load_words()
    hits = match("全网最低价，速抢", words)
    assert any(h["word"] == "最低价" for h in hits)
    assert all("span" in h for h in hits)


def test_first_person_trap_is_mechanically_hit():
    # 「第一人称」包含「第一」——关键词层命中后由语境白名单排除（D9），
    # 语义层同样应判合规；这正是双层+白名单设计的意义
    words = load_words()
    findings = audit("第一人称视角实拍，所见即所得", words)
    assert not findings, "「第一人称」应被语境白名单排除"


def test_real_violation_not_whitelisted():
    words = load_words()
    findings = audit("全网第一品牌，品质最好", words)
    frags = [f["fragment"] for f in findings]
    assert "第一" in frags, "真违规「全网第一」不能被白名单误伤"
    assert "最好" in frags
