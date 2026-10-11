"""D-069 step 2: manifest field derivation and exemplar selection (offline)."""

import json
from pathlib import Path

from PIL import Image

from scripts.build_db1404_full import (
    build_aliases,
    build_entry,
    classify_category,
    natural_key,
    select_images,
    split_alternatives,
)


def spec(source_no, raw, cleaned, page=1, flags=None, cross_refs=None, folder=None):
    return {
        "source_no": source_no,
        "page": page,
        "raw": raw,
        "cleaned": cleaned,
        "clean_status": "clean",
        "flags": flags or [],
        "repeat_raw": [],
        "notes": [],
        "cross_refs": cross_refs or [],
        "folder": folder or f"{source_no:04d}",
        "image_count": 3,
        "primary_file": f"{source_no:04d}+1.jpg",
        "variant_file": f"{source_no:04d}+2.jpg",
    }


def test_tc_db1404_101_longest_keyword_wins_over_generic_character():
    # 裙子 used to be captured by the亲属 keyword 子;服饰 must win.
    assert classify_category("裙子") == ("器物", "服饰", True)
    assert classify_category("桌子") == ("器物", "工具", True)
    assert classify_category("三百六十") == ("数量", "数目", True)
    assert classify_category("长命富实") == ("性状", "状态", True)


def test_tc_db1404_102_category_covers_every_name_without_fallback():
    names = (
        "天",
        "星",
        "飞",
        "母",
        "心",
        "爱",
        "东巴",
        "银",
        "哈达",
        "路",
        "房子",
        "茶",
        "剪刀",
        "春",
        "东方",
        "一",
    )
    for name in names:
        l1, l2, matched = classify_category(name)
        assert matched, name
        assert l1 != "其他", name
        assert l2 != "待分类", name


def test_tc_db1404_103_unmatched_name_is_explicit_not_guessed():
    assert classify_category("嗷嗷嗷嗷") == ("其他", "待分类", False)


def test_tc_db1404_104_alias_split_keeps_meaning_before_explanations():
    assert split_alternatives("置、放") == ["置", "放"]
    assert split_alternatives("倒（水、饭）") == ["倒"]
    assert build_aliases(spec(386, "置、放", "置")) == ["放"]


def test_tc_db1404_105_cross_reference_becomes_alias_not_name_change():
    entry = spec(217, "碗", "碗", cross_refs=[{"target_no": 227, "text": "盘"}])
    assert build_aliases(entry) == ["盘"]
    assert build_entry(entry, "0217+1.jpg", "0217+2.jpg")["name"] == "碗"


def test_tc_db1404_106_merged_number_is_draft_not_published():
    odd = spec(979, "月份不吉利和978 合并", "月份不吉利", flags=["merged_with_978"])
    assert build_entry(odd, "0979+1.jpg", "0979+2.jpg")["status"] == "draft"
    normal = spec(1, "天", "天")
    assert build_entry(normal, "0001+1.jpg", "0001+2.jpg")["status"] == "published"


def test_tc_db1404_107_entry_fields_match_import_contract():
    entry = build_entry(spec(1, "天", "天"), "0001+1.jpg", "0001+2.jpg")
    assert set(entry) == {
        "source_no",
        "name",
        "page",
        "category_l1",
        "category_l2",
        "aliases",
        "primary_file",
        "variant_file",
        "intro",
        "visual",
        "usage",
        "status",
    }
    assert entry["source_no"] == 1 and entry["page"] == 1
    blocked = ("未审核", "程序", "非文化鉴定")
    assert any(word in entry["intro"] for word in blocked)


def test_tc_db1404_108_natural_key_sorts_capture_prefixed_files():
    files = ["19011423_0099_1.jpg", "0001+10.jpg", "0001+2.jpg"]
    assert sorted(files, key=natural_key) == [
        "0001+2.jpg",
        "0001+10.jpg",
        "19011423_0099_1.jpg",
    ]


def test_tc_db1404_109_image_selection_is_deterministic_and_distinct(tmp_path):
    folder = tmp_path / "0001"
    folder.mkdir()
    # A near-uniform image and two contrasting glyph-like shapes.
    shapes = {
        "0001+1.jpg": "blank",
        "0001+2.jpg": "left",
        "0001+3.jpg": "right",
    }
    for name, kind in shapes.items():
        image = Image.new("L", (64, 64), 255)
        pixels = image.load()
        if kind == "left":
            for x in range(4, 20):
                for y in range(4, 60):
                    pixels[x, y] = 0
        elif kind == "right":
            for x in range(44, 60):
                for y in range(4, 60):
                    pixels[x, y] = 0
        image.save(folder / name)
    first = select_images(folder, {})
    second = select_images(folder, {})
    assert first == second
    assert first[0] != first[1]
    assert set(first) <= set(shapes)
    assert "0001+1.jpg" in first  # the blank sample is the outlier


def test_tc_db1404_110_single_image_folder_reuses_the_only_sample(tmp_path):
    folder = tmp_path / "0002"
    folder.mkdir()
    Image.new("L", (64, 64), 200).save(folder / "0002+1.jpg")
    assert select_images(folder, {}) == ("0002+1.jpg", "0002+1.jpg")


def test_tc_db1404_111_cache_is_reused_without_rescanning(tmp_path):
    folder = tmp_path / "0003"
    folder.mkdir()
    Image.new("L", (64, 64), 30).save(folder / "0003+1.jpg")
    Image.new("L", (64, 64), 220).save(folder / "0003+2.jpg")
    cache: dict = {}
    first = select_images(folder, cache)
    assert cache["0003"] == {"primary": first[0], "variant": first[1]}
    # A poisoned cache entry proves the second call does not touch the disk.
    cache["0003"] = {"primary": "cached-a.jpg", "variant": "cached-b.jpg"}
    assert select_images(folder, cache) == ("cached-a.jpg", "cached-b.jpg")


def test_tc_db1404_112_manifest_report_paths_are_inside_project():
    import scripts.build_db1404_full as module

    for path in (module.OUTPUT, module.REPORT, module.REVIEW_CSV, module.IMAGE_CACHE):
        assert Path(path).is_absolute()
        assert module.ROOT in Path(path).parents
    assert module.COLLECTION == "DB1404_FULL_V3"


def test_tc_db1404_113_manifest_json_roundtrips_unicode(tmp_path):
    entry = build_entry(spec(1, "天", "天"), "0001+1.jpg", "0001+2.jpg")
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"entries": [entry]}, ensure_ascii=False), encoding="utf-8")
    assert json.loads(path.read_text(encoding="utf-8"))["entries"][0]["name"] == "天"
