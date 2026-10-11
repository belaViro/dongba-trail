"""D-068 step 1: DB1404 PDF index cleaning rules (offline, no PDF required)."""

import pytest

from scripts.parse_db1404_catalog import MAX_SOURCE_NO, classify


@pytest.mark.parametrize(
    ("raw", "status", "cleaned", "flags"),
    [
        # Plain names pass through untouched.
        ("天", "clean", "天", []),
        ("麦芽糖", "clean", "麦芽糖", []),
        # Parenthetical explanations are cut, never truncated mid-word.
        ("倒（水、饭）", "note", "倒", ["annotation"]),
        ("黑月亮（鬼世界的月亮）", "note", "黑月亮", ["annotation"]),
        ("秽气（有丈量的意思）（同156）", "note", "秽气", ["annotation"]),
        # Editorial brackets and quoted colloquial names are stripped.
        ("森林【两个字】", "note", "森林", ["bracket_note"]),
        ("“猫儿屎”果", "note", "猫儿屎果", ["quoted_name"]),
        ("祭天族群“古徐”", "note", "祭天族群古徐", ["quoted_name"]),
        # 二十八星宿 series: the name is the parenthetical or post-comma star.
        ("纳西二十八星宿之一（天狼星）", "note", "天狼星", ["star_series"]),
        ("纳西二十八星宿之一，红眼星（只有1 个字）", "note", "红眼星", ["star_series"]),
        # Merged numbering is never auto-published as a standalone entry.
        ("月份不吉利和978 合并", "review", "月份不吉利", ["merged_with_978"]),
        # Pure Chinese text longer than the display limit stays overlong.
        ("人类第一代祖先", "overlong", "人类第一代祖先", []),
        ("黑鞋子被水冲去（不吉利的梦）", "overlong", "黑鞋子被水冲去", ["annotation"]),
        # Punctuation-only tails are flagged as possible PDF truncation.
        (
            "暗（写2 个，就是将上个字“亮”的中心涂黑，",
            "note",
            "暗",
            ["truncated_source", "quoted_name", "annotation"],
        ),
        ("", "empty", "", []),
    ],
)
def test_tc_db1404_001_classify_rules(raw, status, cleaned, flags):
    assert classify(raw) == (status, cleaned, flags)


def test_tc_db1404_002_cleaned_name_is_never_empty_for_non_empty_raw():
    for raw in ("、", "（说明）", "【注】", "“”"):
        status, cleaned, _ = classify(raw)
        assert status == "review"
        assert cleaned == raw


def test_tc_db1404_003_source_range_matches_dataset_folder_count():
    assert MAX_SOURCE_NO == 1404
