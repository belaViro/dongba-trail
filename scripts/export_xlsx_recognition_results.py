"""AI-02: append a completed recognition evaluation to the source WPS workbook.

The source workbook stores its Dongba images with WPS ``DISPIMG`` extensions.
Rebuilding it with a generic spreadsheet library can discard those extensions,
so this exporter changes only ``sheet1.xml`` inside a byte-for-byte copy of the
remaining XLSX package.
"""

import argparse
import json
import os
import re
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS = {"m": MAIN_NS}
ET.register_namespace("", MAIN_NS)
ET.register_namespace("r", "http://schemas.openxmlformats.org/officeDocument/2006/relationships")
ET.register_namespace("x14ac", "http://schemas.microsoft.com/office/spreadsheetml/2009/9/ac")

RESULT_COLUMNS = (
    ("O", "当前Top-1"),
    ("P", "当前Top-5"),
    ("Q", "Top-1正确"),
    ("R", "Top-5正确"),
    ("S", "短名单命中"),
    ("T", "短名单排名"),
    ("U", "状态/错误"),
    ("V", "模型"),
    ("W", "时延(ms)"),
    ("X", "运行说明"),
)


def _column(cell_reference: str) -> str:
    match = re.match(r"[A-Z]+", cell_reference)
    if not match:
        raise ValueError("invalid cell reference")
    return match[0]


def _column_number(column: str) -> int:
    value = 0
    for character in column:
        value = value * 26 + ord(character) - ord("A") + 1
    return value


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    return ["".join(node.itertext()) for node in root.findall("m:si", NS)]


def _cell_value(cell: ET.Element, strings: list[str]) -> str:
    if cell.get("t") == "inlineStr":
        inline = cell.find("m:is", NS)
        return "" if inline is None else "".join(inline.itertext())
    value = cell.findtext("m:v", default="", namespaces=NS)
    if cell.get("t") == "s" and value:
        return strings[int(value)]
    return value


def _set_cell(row: ET.Element, reference: str, value, numeric: bool = False) -> None:
    target_column = _column(reference)
    for existing in list(row.findall("m:c", NS)):
        if _column(existing.get("r", "")) == target_column:
            row.remove(existing)
    cell = ET.Element(f"{{{MAIN_NS}}}c", {"r": reference})
    if numeric and value not in (None, ""):
        ET.SubElement(cell, f"{{{MAIN_NS}}}v").text = str(value)
    else:
        cell.set("t", "inlineStr")
        inline = ET.SubElement(cell, f"{{{MAIN_NS}}}is")
        ET.SubElement(inline, f"{{{MAIN_NS}}}t").text = "" if value is None else str(value)
    target_number = _column_number(target_column)
    cells = list(row.findall("m:c", NS))
    position = next(
        (
            index
            for index, existing in enumerate(cells)
            if _column_number(_column(existing.get("r", ""))) > target_number
        ),
        len(cells),
    )
    row.insert(position, cell)


def _rows_by_sequence(sheet: ET.Element, strings: list[str]) -> dict[int, tuple[ET.Element, str]]:
    rows = {}
    for row in sheet.findall(".//m:sheetData/m:row", NS):
        values = {
            _column(cell.get("r", "")): _cell_value(cell, strings)
            for cell in row.findall("m:c", NS)
        }
        if values.get("A", "").isdigit():
            rows[int(values["A"])] = (row, values.get("D", "").strip())
    return rows


def _case_values(case: dict, model: str, run_note: str) -> dict[str, object]:
    candidates = case.get("candidates") or []
    names = [str(candidate.get("cn_name", "")).strip() for candidate in candidates]
    expected = str(case.get("cn", "")).strip()
    status = str(case.get("status", "ERROR"))
    if status == "ERROR":
        status = str(case.get("error_code") or case.get("error_type") or status)
    rank = case.get("shortlist_rank_0based")
    return {
        "O": names[0] if names else "",
        "P": "、".join(name for name in names[:5] if name),
        "Q": "是" if names and names[0] == expected else "否",
        "R": "是" if expected in names[:5] else "否",
        "S": "是" if case.get("shortlist_has_correct") else "否",
        "T": "" if rank is None else int(rank) + 1,
        "U": status,
        "V": str(case.get("model_version") or model or ""),
        "W": case.get("latency_ms", ""),
        "X": run_note,
    }


def export(workbook: Path, results_path: Path, output: Path, run_note: str) -> None:
    results = json.loads(results_path.read_text(encoding="utf-8"))
    if not results.get("complete"):
        raise ValueError("recognition evaluation is incomplete")
    cases = results.get("cases") or []
    if len(cases) != results.get("planned_cases") or not cases:
        raise ValueError("recognition case count mismatch")
    sequences = [case.get("seq") for case in cases]
    if len(sequences) != len(set(sequences)):
        raise ValueError("duplicate recognition sequence")

    with zipfile.ZipFile(workbook) as source:
        strings = _shared_strings(source)
        sheet = ET.fromstring(source.read("xl/worksheets/sheet1.xml"))
        rows = _rows_by_sequence(sheet, strings)
        header = sheet.find(".//m:sheetData/m:row[@r='1']", NS)
        if header is None:
            raise ValueError("missing workbook header row")
        for column, title in RESULT_COLUMNS:
            _set_cell(header, f"{column}1", title)
        for case in cases:
            sequence = int(case["seq"])
            if sequence not in rows:
                raise ValueError(f"workbook sequence missing: {sequence}")
            row, workbook_name = rows[sequence]
            if workbook_name != str(case.get("cn", "")).strip():
                raise ValueError(f"meaning mismatch at sequence {sequence}")
            values = _case_values(case, str(results.get("model", "")), run_note)
            for column, _ in RESULT_COLUMNS:
                _set_cell(
                    row,
                    f"{column}{row.get('r')}",
                    values[column],
                    numeric=column in {"T", "W"},
                )
        dimension = sheet.find("m:dimension", NS)
        if dimension is not None:
            _, last_row = dimension.get("ref", "A1:A1").split(":", maxsplit=1)
            last_row_number = re.search(r"\d+$", last_row)[0]
            dimension.set("ref", f"A1:X{last_row_number}")
        sheet_bytes = ET.tostring(sheet, encoding="utf-8", xml_declaration=True)

        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            prefix=output.stem + "-", suffix=".xlsx", dir=output.parent, delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
        try:
            with zipfile.ZipFile(temporary_path, "w") as destination:
                for item in source.infolist():
                    payload = (
                        sheet_bytes
                        if item.filename == "xl/worksheets/sheet1.xml"
                        else source.read(item.filename)
                    )
                    destination.writestr(item, payload)
            os.replace(temporary_path, output)
        finally:
            temporary_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path)
    parser.add_argument("results", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--run-note",
        default=(
            "小程序相册裁剪结果模拟；JPEG质量95、长边512评测归一化；"
            "调用线上同款识别核心，不写生产用户历史，非真机实拍准确率"
        ),
    )
    args = parser.parse_args()
    export(args.workbook, args.results, args.output, args.run_note)


if __name__ == "__main__":
    main()
