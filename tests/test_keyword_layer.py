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
    # 「第一人称」包含「第一」——关键词层必然命中（弱信号），
    # 最终合规判定由语义层裁定，这正是双层设计的意义
    words = load_words()
    findings = audit("第一人称视角实拍，所见即所得", words)
    assert findings, "关键词层应命中（弱信号）"
    assert findings[0]["source"] == "keyword"
