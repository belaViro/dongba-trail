"""Parse the DB1404 PDF index into a draft catalog (D-068, step 1).

Step 1 of the DB1404 expansion is read-only and local: it turns the source PDF
("手写东巴文数据集DB1404文件夹名字对应释义") into a machine-readable draft plus a
cleaning report. It never touches the network, the database, or the source
dataset, and it never selects images.

The source PDF is a hand-made index, so a minority of names carry trailing
annotations in parentheses or brackets, explanatory clauses after a comma,
editorial quotes around a colloquial name, or OCR padding. ``raw`` always keeps
the source text verbatim; ``cleaned`` is only a *proposal*, and every entry that
needed an edit carries ``flags`` so step 2 can review it deliberately instead of
guessing.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SOURCE_PDF = ROOT / "数据集" / "手写东巴文数据集DB1404文件夹名字对应释义.pdf"
SOURCE_DIR = ROOT / "数据集" / "DB1404"
OUTPUT = ROOT / "runtime" / "db1404" / "catalog-draft.json"
REPORT = ROOT / "runtime" / "db1404" / "catalog-cleaning-report.md"
REVIEW_CSV = ROOT / "runtime" / "db1404" / "catalog-review.csv"

ENTRY_RE = re.compile(r"^\s*(\d{1,4})\s*、\s*(.*\S)\s*$")
CJK_RE = re.compile(r"^[\u3400-\u4dbf\u4e00-\u9fff]+$")
MAX_SOURCE_NO = 1404
# A display name that fits the existing dictionary style. Longer text is an
# explanation that must be shortened deliberately, never truncated silently.
MAX_DISPLAY_LENGTH = 6
# Annotation starts: everything from here on explains the name, it is not a name.
CUT_MARKERS = ("（", "(", "，", ",", "、", "。", "；", ";", "！", "!", "：", ":")
BRACKET_RE = re.compile(r"[【\[][^】\]]*[】\]]")
QUOTE_CHARS = "“”‘’「」『』\"'"
TRUNCATION_TAIL = ("，", ",", "、", "（", "(", "【", "[")
STAR_PREFIX = "纳西二十八星宿之一"
STAR_COMMA_RE = re.compile(rf"^{STAR_PREFIX}\s*[，,]\s*(.+)$")
STAR_PAREN_RE = re.compile(rf"^{STAR_PREFIX}\s*[（(]\s*([^）)]*)\s*[）)]\s*$")
MERGE_RE = re.compile(r"^(.+?)\s*和\s*(\d{1,4})\s*合并\s*$")
EDGE_CHARS = "　 .,，。、；;！!：:"
# Cross-reference footnotes printed between entries, e.g. "（227 盘）" or
# "0165.线" — they point at another entry that shares the glyph.
CROSS_REF_RE = re.compile(r"^[（(]?\s*(0?\d{1,4})\s*[.．、\s]\s*(.+?)\s*[）)]?$")
DOT_REF_RE = re.compile(r"^(0?\d{1,4})\.(\S.*)$")
DANGLING_RE = re.compile(r"^[）)]")


def _note_kind(line: str) -> tuple[str, dict | None]:
    """Classify one non-entry line against the entry printed just above it."""
    stripped = line.strip()
    if not stripped or set(stripped) <= {",", "、", "，", " "}:
        return "skip", None
    if DANGLING_RE.match(stripped):
        # Continuation of the previous entry's explanation ("被北斗七星偷吃）").
        return "continuation", None
    match = DOT_REF_RE.match(stripped) or CROSS_REF_RE.match(stripped)
    if match:
        return "cross_ref", {"target_no": int(match.group(1)), "text": match.group(2).strip()}
    return "note", None


def parse_pdf(path: Path) -> tuple[dict[int, dict], int]:
    document = pymupdf.open(path)
    entries: dict[int, dict] = {}
    for page_index, page in enumerate(document, start=1):
        current: dict | None = None
        for line in page.get_text().splitlines():
            match = ENTRY_RE.match(line)
            if not match:
                kind, payload = _note_kind(line)
                if kind == "skip" or current is None:
                    continue
                if kind == "continuation":
                    current["raw"] = f"{current['raw']} {line.strip()}"
                elif kind == "cross_ref":
                    current["cross_refs"].append(payload)
                else:
                    current["notes"].append(line.strip())
                continue
            number = int(match.group(1))
            text = match.group(2).strip()
            if number in entries:
                # Legacy re-listings (0129/0136/0402/0638) and OCR repeats.
                if text not in entries[number]["repeat_raw"]:
                    entries[number]["repeat_raw"].append(text)
                continue
            entries[number] = {
                "source_no": number,
                "page": page_index,
                "raw": text,
                "repeat_raw": [],
                "notes": [],
                "cross_refs": [],
            }
            current = entries[number]
    return entries, document.page_count


def _cut_at_marker(text: str) -> tuple[str, bool]:
    cut = len(text)
    for marker in CUT_MARKERS:
        position = text.find(marker)
        if position > 0:
            cut = min(cut, position)
    return text[:cut].strip(EDGE_CHARS), cut < len(text)


def _star_name(text: str) -> str:
    """Names in the 二十八星宿 series sit after the comma or inside the brackets."""
    paren = STAR_PAREN_RE.match(text)
    if paren:
        return paren.group(1).strip()
    comma = STAR_COMMA_RE.match(text)
    if comma:
        name, _ = _cut_at_marker(comma.group(1))
        return name
    return ""


def classify(raw: str) -> tuple[str, str, list[str]]:
    """Return (status, cleaned candidate, flags). ``cleaned`` is a proposal."""
    text = (raw or "").strip()
    if not text:
        return "empty", "", []

    flags: list[str] = []
    if text.endswith(TRUNCATION_TAIL):
        flags.append("truncated_source")

    merge = MERGE_RE.match(text)
    if merge:
        return "review", merge.group(1).strip(), [*flags, f"merged_with_{merge.group(2)}"]

    if text.startswith(STAR_PREFIX):
        name = _star_name(text)
        if name:
            return "note", name, [*flags, "star_series"]

    candidate = text
    if BRACKET_RE.search(candidate):
        candidate = BRACKET_RE.sub("", candidate)
        flags.append("bracket_note")
    if any(char in candidate for char in QUOTE_CHARS):
        candidate = candidate.translate({ord(char): None for char in QUOTE_CHARS})
        flags.append("quoted_name")

    head, had_annotation = _cut_at_marker(candidate)
    if had_annotation:
        flags.append("annotation")

    if not head:
        return "review", text, [*flags, "no_lead_name"]
    if not CJK_RE.match(head):
        return "review", head, [*flags, "non_cjk"]
    if len(head) > MAX_DISPLAY_LENGTH:
        return "overlong", head, flags
    if flags:
        return "note", head, flags
    return "clean", head, []


def build(pdf_path: Path, source_dir: Path) -> dict:
    entries, page_count = parse_pdf(pdf_path)
    numbers = sorted(entries)
    missing = [number for number in range(1, MAX_SOURCE_NO + 1) if number not in entries]
    extras = [number for number in numbers if number > MAX_SOURCE_NO]
    folders = {
        int(folder.name): folder
        for folder in source_dir.iterdir()
        if folder.is_dir() and folder.name.isdigit()
    }
    records = []
    for number in numbers:
        entry = entries[number]
        status, cleaned, flags = classify(entry["raw"])
        folder = folders.get(number)
        images = sorted(item.name for item in folder.iterdir() if item.is_file()) if folder else []
        records.append(
            {
                "source_no": number,
                "page": entry["page"],
                "raw": entry["raw"],
                "cleaned": cleaned,
                "clean_status": status,
                "flags": flags,
                "repeat_raw": entry["repeat_raw"],
                "notes": entry["notes"],
                "cross_refs": entry["cross_refs"],
                "folder": f"{number:04d}",
                "image_count": len(images),
                "primary_file": images[0] if images else None,
                "variant_file": images[1] if len(images) > 1 else None,
            }
        )
    return {
        "source": {
            "pdf": pdf_path.name,
            "pdf_pages": page_count,
            "dataset_dir": source_dir.name,
        },
        "counts": {
            "entries": len(records),
            "by_status": dict(Counter(item["clean_status"] for item in records)),
            "by_flag": dict(Counter(flag for item in records for flag in item["flags"])),
            "missing_numbers": missing,
            "extras_over_max": extras,
            "total_images": sum(item["image_count"] for item in records),
            "cross_ref_pages": sorted(item["source_no"] for item in records if item["cross_refs"]),
            "folders_under_two_images": [
                item["source_no"] for item in records if item["image_count"] < 2
            ],
        },
        "entries": records,
    }


STATUS_MEANINGS = {
    "clean": "纯汉字且≤6字，无任何批注，可直接用",
    "note": "已剥掉括号/逗号/引号批注，建议名需确认",
    "overlong": "纯汉字但超过6字，需定短名",
    "review": "无法自动得到可靠名称，必须人工处理",
    "empty": "空文本",
}

FLAG_MEANINGS = {
    "annotation": "原文有括号/逗号/句号等说明，已截取说明前的主体",
    "bracket_note": "原文有【】等编者注，已删除",
    "quoted_name": "原文用引号标出口语名，已去掉引号",
    "star_series": "二十八星宿系列，名称取自括号或逗号后的星名",
    "merged_with_978": "原文标注“和978合并”，疑似没有独立字形",
    "truncated_source": "原文以标点结尾，疑似 PDF 换行被截断",
    "no_lead_name": "说明前没有可用主体",
    "non_cjk": "主体含非汉字字符",
}


def write_report(catalog: dict, path: Path) -> None:
    counts = catalog["counts"]
    lines = [
        "# DB1404 词条清单清洗报告（第一步，只读）",
        "",
        f"来源：`{catalog['source']['pdf']}`（{catalog['source']['pdf_pages']} 页）、"
        f"`数据集/{catalog['source']['dataset_dir']}`。",
        "",
        "本步骤只解析、不选图、不写数据库、不联网。`cleaned` 是脚本给出的**建议名**，",
        "只要 `flags` 非空，就说明原文带括号说明、引号、编者注或编号合并等，",
        "必须由第二步或人工确认后才能入库。",
        "",
        "## 汇总",
        "",
        f"- 解析到词条：{counts['entries']}（编号 1–{MAX_SOURCE_NO}）",
        f"- 缺失编号：{len(counts['missing_numbers'])}",
        f"- 数据集图片总数：{counts['total_images']}",
        f"- 不足 2 张图的编号：{len(counts['folders_under_two_images'])}",
        "",
        "| 状态 | 含义 | 数量 |",
        "| --- | --- | ---: |",
    ]
    for status, meaning in STATUS_MEANINGS.items():
        lines.append(f"| `{status}` | {meaning} | {counts['by_status'].get(status, 0)} |")

    if counts["missing_numbers"]:
        lines += ["", "## 缺失编号", "", "、".join(str(n) for n in counts["missing_numbers"])]

    lines += ["", "## 标记分布", "", "| 标记 | 含义 | 数量 |", "| --- | --- | ---: |"]
    for flag, meaning in FLAG_MEANINGS.items():
        lines.append(f"| `{flag}` | {meaning} | {counts['by_flag'].get(flag, 0)} |")

    lines += ["", "## 需处理词条", ""]
    for item in catalog["entries"]:
        if item["clean_status"] == "clean":
            continue
        marks = "、".join(item["flags"]) or "-"
        lines.append(
            f"- {item['source_no']:>4}（p{item['page']}，{item['clean_status']}）"
            f"`{item['raw']}` → 建议 `{item['cleaned']}`；标记：{marks}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_review_csv(catalog: dict, path: Path) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "source_no",
                "page",
                "clean_status",
                "flags",
                "raw",
                "cleaned",
                "folder",
                "image_count",
            ]
        )
        for item in catalog["entries"]:
            if item["clean_status"] == "clean":
                continue
            writer.writerow(
                [
                    item["source_no"],
                    item["page"],
                    item["clean_status"],
                    "|".join(item["flags"]),
                    item["raw"],
                    item["cleaned"],
                    item["folder"],
                    item["image_count"],
                ]
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, default=SOURCE_PDF)
    parser.add_argument("--source-dir", type=Path, default=SOURCE_DIR)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--review-csv", type=Path, default=REVIEW_CSV)
    args = parser.parse_args()
    catalog = build(args.pdf, args.source_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(catalog, args.report)
    write_review_csv(catalog, args.review_csv)
    print(
        json.dumps(
            {
                "entries": catalog["counts"]["entries"],
                "by_status": catalog["counts"]["by_status"],
                "by_flag": catalog["counts"]["by_flag"],
                "missing": len(catalog["counts"]["missing_numbers"]),
                "total_images": catalog["counts"]["total_images"],
                "output": str(args.output),
                "report": str(args.report),
                "review_csv": str(args.review_csv),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
