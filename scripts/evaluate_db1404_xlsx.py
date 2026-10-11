"""AI-02: repeatable Excel-screenshot evaluation, never a real-camera accuracy claim.

prepare WORKBOOK OUTPUT extracts only column B inputs, not recognition screenshots.
evaluate BUNDLE runs in the deployed project, using its existing runtime provider.
It writes only evaluation artifacts, disables RAG, and never changes business data.
"""

import argparse
import asyncio
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

from PIL import Image

NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "x": "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def prepare(workbook, output):
    output.mkdir(parents=True, exist_ok=False)
    cases = []
    with zipfile.ZipFile(workbook) as archive:
        strings = [
            "".join(node.itertext()) for node in ET.fromstring(archive.read("xl/sharedStrings.xml"))
        ]
        relations = {
            node.get("Id"): node.get("Target")
            for node in ET.fromstring(archive.read("xl/_rels/cellimages.xml.rels"))
        }
        images = {}
        for pic in ET.fromstring(archive.read("xl/cellimages.xml")).iter(f"{{{NS['x']}}}pic"):
            name = pic.find(".//x:cNvPr", NS).get("name")
            relation = pic.find(".//a:blip", NS).get(f"{{{NS['r']}}}embed")
            target = relations[relation].lstrip("/")
            images[name] = target if target.startswith("xl/") else "xl/" + target
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        for row in sheet.findall(".//m:row", NS):
            cells = {}
            for cell in row.findall("m:c", NS):
                col = re.match(r"[A-Z]+", cell.get("r"))[0]
                value = cell.findtext("m:v", default="", namespaces=NS)
                formula = cell.findtext("m:f", default="", namespaces=NS)
                if "DISPIMG" in formula:
                    cells[col] = re.search(r'"([^\"]+)"', formula)[1]
                else:
                    cells[col] = strings[int(value)] if cell.get("t") == "s" else value
            if not cells.get("A", "").isdigit():
                continue
            seq = int(cells["A"])
            part = images[cells["B"]]
            raw = archive.read(part)
            original = f"{seq:02d}-original{Path(part).suffix}"
            (output / original).write_bytes(raw)
            with Image.open(BytesIO(raw)) as opened:
                image = opened.convert("RGB")
                size = list(image.size)
                scale = 512 / max(image.size)
                if scale > 1:
                    image = image.resize(
                        tuple(max(1, round(v * scale)) for v in size), Image.Resampling.LANCZOS
                    )
                sent = f"{seq:02d}.jpg"
                image.save(output / sent, format="JPEG", quality=95)
                sent_size = list(image.size)
            cases.append(
                {
                    "seq": seq,
                    "cn": cells["D"].strip(),
                    "old_wrong": cells.get("G"),
                    "original": original,
                    "original_sha256": sha(raw),
                    "original_size": size,
                    "image": sent,
                    "image_sha256": sha((output / sent).read_bytes()),
                    "sent_size": sent_size,
                }
            )
    if not cases or len({c["seq"] for c in cases}) != len(cases):
        raise ValueError("missing or duplicate cases")
    manifest = {"workbook_sha256": sha(workbook.read_bytes()), "cases": cases}
    write_json(output / "manifest.json", manifest)
    print(
        json.dumps(
            {
                "prepared": len(cases),
                "old_wrong": dict(Counter(c["old_wrong"] for c in cases)),
                "original_below_200": sum(min(c["original_size"]) < 200 for c in cases),
            }
        )
    )


def summary(rows):
    top1 = top5 = 0
    for row in rows:
        names = [c["cn_name"] for c in row.get("candidates", [])]
        if row["status"] != "ERROR":
            top1 += bool(names) and names[0] == row["cn"]
            top5 += row["cn"] in names[:5]
    return {
        "total": len(rows),
        "top1": top1,
        "top5": top5,
        "errors": sum(r["status"] == "ERROR" for r in rows),
        "unknown": sum(r["status"] == "UNKNOWN" for r in rows),
        "shortlist_recall": sum(bool(r.get("shortlist_has_correct")) for r in rows),
        "dictionary_coverage": sum(bool(r.get("expected_ids")) for r in rows),
        "original_quality": dict(Counter(r.get("original_quality") for r in rows)),
    }


def stop_reason(rows):
    """Do not repeat a failed first probe or hammer an unavailable provider."""
    if len(rows) == 1 and rows[0]["status"] == "ERROR":
        return "first_probe_failed"
    if len(rows) >= 3 and all(r["status"] == "ERROR" for r in rows[-3:]):
        return "three_consecutive_errors"
    return None


async def evaluate(bundle, expected_model=None, contact_sheets=False):
    # CWD must be the deployed project. Do not print settings or provider exceptions.
    sys.path.insert(0, str(Path.cwd()))
    from backend.app.business.database import Database
    from backend.app.config import Settings
    from backend.app.dictionary import CharacterDictionary
    from backend.app.errors import ApiError
    from backend.app.glyph_refs import MAX_REFERENCES, load_references
    from backend.app.recognition import assess_image_quality, recognize, validate_image
    from backend.app.schemas import Character
    from backend.app.system_config import active_provider

    if (bundle / "results.json").exists():
        raise ValueError("refusing to overwrite a previous evaluation")
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    settings = Settings()
    database = Database(settings.database_url, auto_create=False)
    with database.session() as session:
        provider, active = active_provider(session, settings)
    if expected_model and active.provider_model != expected_model:
        print(
            json.dumps(
                {
                    "configured_model": active.provider_model,
                    "expected_model": expected_model,
                    "model_match": False,
                }
            ),
            flush=True,
        )
        raise RuntimeError("runtime_model_mismatch")
    if not provider.configured:
        raise RuntimeError("provider_unavailable")
    sheet_hash = None
    if contact_sheets:
        # Only this isolated evaluation process changes; the deployed app is untouched.
        # Prefer the uploaded sibling so the server need not install experimental code.
        import importlib.util

        path = Path(__file__).with_name("xlsx_reference_sheets.py")
        spec = importlib.util.spec_from_file_location("xlsx_reference_sheets", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        sheet_hash = sha(path.read_bytes())
        provider._message_content = module.message_content
    characters = [
        Character.model_validate({k: v for k, v in r.items() if k in Character.model_fields})
        for r in database.published_characters()
    ]
    dictionary = CharacterDictionary(characters)
    published = dictionary.published()
    source_hashes = {
        p.as_posix(): sha(p.read_bytes().replace(b"\r\n", b"\n"))
        for p in sorted(Path("backend/app").rglob("*.py"))
    }
    result = {
        "started_at": datetime.now(UTC).isoformat(),
        "complete": False,
        "workbook_sha256": manifest["workbook_sha256"],
        "manifest_sha256": sha((bundle / "manifest.json").read_bytes()),
        "provider": provider.name,
        "model": active.provider_model,
        "rag_enabled": False,
        "provider_timeout_seconds": active.provider_timeout_seconds,
        "published": len(published),
        "planned_cases": len(manifest["cases"]),
        "max_references": MAX_REFERENCES,
        "quality_min_edge": active.quality_min_edge,
        "code_sha256": source_hashes,
        "evaluator_sha256": sha(Path(__file__).read_bytes()),
        "contact_sheets_experiment": contact_sheets,
        "contact_sheets_script_sha256": sheet_hash,
        "billing_cost": None,
        "billing_note": "adapter does not expose billed usage",
        "cases": [],
    }
    write_json(bundle / "results.json", result)
    for case in manifest["cases"]:
        raw = (bundle / case["original"]).read_bytes()
        image = (bundle / case["image"]).read_bytes()
        if sha(raw) != case["original_sha256"] or sha(image) != case["image_sha256"]:
            raise ValueError("input fingerprint mismatch")
        row = dict(case)
        row["original_quality"] = "PASS"
        try:
            validate_image(raw, active)
            assess_image_quality(raw, active)
        except ApiError as exc:
            row["original_quality"] = exc.code
        correct = {c.character_id for c in published if c.cn_name == case["cn"]}
        row["expected_ids"] = sorted(correct)
        refs = load_references(published, active.media_directory, query=image)
        row["reference_count"] = len(refs)
        row["shortlist_rank_0based"] = next(
            (i for i, r in enumerate(refs) if r.character_id in correct), None
        )
        row["shortlist_has_correct"] = row["shortlist_rank_0based"] is not None
        try:
            response = await recognize(
                image=image,
                media_type=validate_image(image, active),
                request_id=f"xlsx-recheck-{case['seq']:02d}",
                provider=provider,
                dictionary=dictionary,
                settings=active,
                rag_database=None,
                business_database=None,
            )
            row.update(
                status=response.status,
                latency_ms=response.latency_ms,
                model_version=response.model_version,
                candidates=[
                    {"character_id": c.character_id, "cn_name": c.cn_name}
                    for c in response.candidates
                ],
            )
        except Exception as exc:
            row.update(status="ERROR", error_type=type(exc).__name__)
            if isinstance(exc, ApiError):
                row["error_code"] = exc.code
        result["cases"].append(row)
        result["summary"] = summary(result["cases"])
        write_json(bundle / "results.json", result)
        print(json.dumps({"seq": case["seq"], **result["summary"]}), flush=True)
        reason = stop_reason(result["cases"])
        if reason:
            result.update(stopped_reason=reason, finished_at=datetime.now(UTC).isoformat())
            write_json(bundle / "results.json", result)
            return
    result.update(complete=True, finished_at=datetime.now(UTC).isoformat())
    write_json(bundle / "results.json", result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["prepare", "evaluate"])
    parser.add_argument("path", type=Path)
    parser.add_argument("output", type=Path, nargs="?")
    parser.add_argument("--expected-model")
    parser.add_argument("--contact-sheets", action="store_true")
    args = parser.parse_args()
    if args.mode == "prepare":
        if args.output is None:
            parser.error("prepare requires an output directory")
        prepare(args.path, args.output)
    else:
        asyncio.run(evaluate(args.path, args.expected_model, args.contact_sheets))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"fatal_error_type": type(exc).__name__}), flush=True)
        raise SystemExit(1) from None
