"""Export DOCX paragraphs and tables without modifying the source document."""

import argparse
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def paragraph_text(element: ElementTree.Element) -> str:
    parts = []
    for node in element.iter():
        tag = node.tag.rsplit("}", 1)[-1]
        if tag == "t":
            parts.append(node.text or "")
        elif tag in {"br", "cr"}:
            parts.append("\n")
        elif tag == "tab":
            parts.append("\t")
    return "".join(parts).strip()


def export(source: Path) -> None:
    with ZipFile(source) as archive:
        document = ElementTree.fromstring(archive.read("word/document.xml"))
        image_count = sum(
            item.filename.startswith("word/media/") and not item.is_dir()
            for item in archive.infolist()
        )
    body = document.find("w:body", NS)
    if body is None:
        raise ValueError("Document body is missing")

    lines = [
        "# Original Requirements Text",
        "",
        f"Source: `{source.name}`",
        "",
        "Generated text/table extract. Embedded images remain in the original DOCX.",
        "Implementation changes are recorded separately in requirements.md and decisions.md.",
        "",
    ]
    for block in body:
        if block.tag.endswith("}p"):
            text = paragraph_text(block)
            if text:
                lines.extend([text, ""])
        elif block.tag.endswith("}tbl"):
            rows = []
            for row in block.findall("w:tr", NS):
                cells = []
                for cell in row.findall("w:tc", NS):
                    text = "<br>".join(paragraph_text(p) for p in cell.findall(".//w:p", NS))
                    cells.append(text.replace("|", "\\|").replace("\n", "<br>"))
                rows.append(cells)
            if rows:
                width = max(len(row) for row in rows)
                for index, row in enumerate(rows):
                    lines.append("| " + " | ".join(row + [""] * (width - len(row))) + " |")
                    if index == 0:
                        lines.append("| " + " | ".join(["---"] * width) + " |")
                lines.append("")

    metadata = {
        "source_file": source.name,
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "paragraphs_with_text": sum(bool(paragraph_text(p)) for p in body.findall(".//w:p", NS)),
        "tables": len(body.findall(".//w:tbl", NS)),
        "embedded_images": image_count,
        "note": "Images were not exported or visually validated by this text extraction.",
    }
    (ROOT / "docs" / "source-requirements.md").write_text("\n".join(lines), encoding="utf-8")
    (ROOT / "docs" / "source-manifest.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    export(parser.parse_args().source)
