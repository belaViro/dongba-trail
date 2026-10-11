import json
import zipfile

import pytest

from scripts.export_xlsx_recognition_results import export


def _completed_results(source_bundle):
    manifest = json.loads((source_bundle / "manifest.json").read_text(encoding="utf-8"))
    cases = []
    for case in manifest["cases"]:
        cases.append(
            {
                **case,
                "status": "NEED_USER_CONFIRM",
                "shortlist_has_correct": True,
                "shortlist_rank_0based": 0,
                "latency_ms": 123,
                "candidates": [{"cn_name": case["cn"]}],
            }
        )
    return {"complete": True, "planned_cases": len(cases), "model": "test-model", "cases": cases}


def test_export_preserves_wps_images_and_adds_result_cells(tmp_path):
    project = __import__("pathlib").Path(__file__).resolve().parents[2]
    workbook = project / "寻迹东巴新数据统计(1).xlsx"
    source_bundle = project / "runtime/db1404/xlsx-current-prototypes-20261008"
    if not workbook.exists() or not source_bundle.exists():
        pytest.skip("local source workbook is not part of a clean checkout")
    results = tmp_path / "results.json"
    results.write_text(
        json.dumps(_completed_results(source_bundle), ensure_ascii=False), encoding="utf-8"
    )
    output = tmp_path / "result.xlsx"

    export(workbook, results, output, "test run")

    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        assert "xl/cellimages.xml" in archive.namelist()
        sheet = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert 'ref="A1:X301"' in sheet
    assert "当前Top-1" in sheet
    assert sheet.count("Top-1正确") == 1
    assert sheet.count("test run") == 50


def test_export_rejects_incomplete_results(tmp_path):
    results = tmp_path / "results.json"
    results.write_text('{"complete": false, "cases": []}', encoding="utf-8")
    with pytest.raises(ValueError, match="incomplete"):
        export(tmp_path / "missing.xlsx", results, tmp_path / "out.xlsx", "test")
