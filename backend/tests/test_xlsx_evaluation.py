"""AI-02: evaluation bookkeeping fixtures, NOT recognition accuracy evidence."""

import json
import zipfile
from io import BytesIO

import pytest
from PIL import Image

from scripts.evaluate_db1404_xlsx import NS, prepare, sha, stop_reason, summary
from scripts.xlsx_reference_sheets import build_sheets, message_content


def test_sheet_experiment_preserves_all_200_ids_and_query_last():
    from backend.app.glyph_refs import GlyphReference
    from backend.app.volcengine_provider import image_part

    raw = BytesIO()
    Image.new("RGB", (128, 128), "black").save(raw, "PNG")
    refs = tuple(GlyphReference(f"DB1404_{i:04d}", "测试", raw.getvalue()) for i in range(200))
    sheets = build_sheets(refs)
    assert len(sheets) == 10
    assert tuple(ref for group, _ in sheets for ref in group) == refs
    with Image.open(BytesIO(sheets[0][1])) as sheet:
        assert sheet.size == (640, 800)
        assert (
            sheet.crop((16, 25, 144, 153)).tobytes()
            == Image.open(BytesIO(raw.getvalue())).tobytes()
        )
    parts = message_content("prompt", raw.getvalue(), "image/png", refs)
    assert sum(part["type"] == "image_url" for part in parts) == 11
    assert parts[-1] == image_part(raw.getvalue(), "image/png")
    text = "\n".join(p.get("text", "") for p in parts)
    assert all(text.count(ref.character_id) == 1 for ref in refs)


def test_sheet_experiment_empty_partial_and_rejects_unreadable_labels():
    from backend.app.glyph_refs import GlyphReference

    raw = BytesIO()
    Image.new("RGB", (128, 128), "white").save(raw, "PNG")
    assert build_sheets([]) == []
    one = GlyphReference("DB1404_0001", "天", raw.getvalue())
    assert len(build_sheets([one])[0][0]) == 1
    with pytest.raises(ValueError, match="cannot fit"):
        build_sheets([GlyphReference("X" * 100, "天", raw.getvalue())])


def test_failed_probe_stops_and_transient_failure_does_not():
    assert stop_reason([]) is None
    assert stop_reason([{"status": "ERROR"}]) == "first_probe_failed"
    assert stop_reason([{"status": "UNKNOWN"}]) is None
    assert stop_reason([{"status": "UNKNOWN"}, {"status": "ERROR"}]) is None
    assert stop_reason([{"status": "UNKNOWN"}] + [{"status": "ERROR"}] * 3) == (
        "three_consecutive_errors"
    )


def test_summary_counts_failures_in_denominator_and_distinguishes_candidates():
    rows = [
        {"cn": "天", "status": "NEED_USER_CONFIRM", "candidates": [{"cn_name": "天"}]},
        {
            "cn": "月",
            "status": "NEED_USER_CONFIRM",
            "candidates": [{"cn_name": "船"}, {"cn_name": "月"}],
        },
        {"cn": "云", "status": "UNKNOWN", "candidates": []},
        {"cn": "山", "status": "ERROR", "candidates": [{"cn_name": "山"}]},
    ]
    result = summary(rows)
    assert (result["total"], result["top1"], result["top5"]) == (4, 1, 2)
    assert result["unknown"] == result["errors"] == 1
    assert result["dictionary_coverage"] == 0


def test_summary_top5_cap_and_empty_run():
    assert summary([])["total"] == 0
    row = {
        "cn": "山",
        "status": "NEED_USER_CONFIRM",
        "candidates": [{"cn_name": "地"}] * 5 + [{"cn_name": "山"}],
        "expected_ids": ["one", "two"],
        "shortlist_has_correct": True,
        "original_quality": "IMAGE_TOO_SMALL",
    }
    result = summary([row])
    assert result["top5"] == 0
    assert result["dictionary_coverage"] == result["shortlist_recall"] == 1
    assert result["original_quality"] == {"IMAGE_TOO_SMALL": 1}


def test_prepare_selects_column_b_preserves_original_and_records_hashes(tmp_path):
    image = BytesIO()
    Image.new("RGB", (100, 80), "black").save(image, "PNG")
    raw = image.getvalue()
    workbook = tmp_path / "samples.xlsx"
    with zipfile.ZipFile(workbook, "w") as archive:
        archive.writestr(
            "xl/sharedStrings.xml",
            f'<sst xmlns="{NS["m"]}"><si><t>天</t></si><si><t>否</t></si></sst>',
        )
        archive.writestr(
            "xl/_rels/cellimages.xml.rels",
            '<Relationships><Relationship Id="r1" Target="media/input.png"/></Relationships>',
        )
        archive.writestr(
            "xl/cellimages.xml",
            f'<root xmlns:x="{NS["x"]}" '
            f'xmlns:a="{NS["a"]}" xmlns:r="{NS["r"]}">'
            '<x:pic><x:cNvPr name="INPUT"/><a:blip r:embed="r1"/></x:pic></root>',
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            f'<worksheet xmlns="{NS["m"]}">'
            '<sheetData><row r="2"><c r="A2"><v>1</v></c>'
            '<c r="B2"><f>DISPIMG("INPUT",1)</f><v>cached</v></c>'
            '<c r="D2" t="s"><v>0</v></c>'
            '<c r="E2"><f>DISPIMG("RESULT_NOT_AN_INPUT",1)</f></c>'
            '<c r="G2" t="s"><v>1</v></c></row></sheetData></worksheet>',
        )
        archive.writestr("xl/media/input.png", raw)
    output = tmp_path / "bundle"
    prepare(workbook, output)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["workbook_sha256"] == sha(workbook.read_bytes())
    case = manifest["cases"][0]
    assert (case["seq"], case["cn"], case["old_wrong"]) == (1, "天", "否")
    assert (output / case["original"]).read_bytes() == raw
    assert case["original_size"] == [100, 80]
    assert case["sent_size"] == [512, 410]
    assert case["image_sha256"] == sha((output / case["image"]).read_bytes())
    with pytest.raises(FileExistsError):
        prepare(workbook, output)
