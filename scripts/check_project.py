"""Check requirement coverage, accepted evidence, source integrity and API drift."""

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.config import Settings  # noqa: E402
from backend.app.dictionary import CharacterDictionary  # noqa: E402
from backend.app.main import create_app  # noqa: E402

REQUIRED_FILES = (
    "AGENTS.md",
    "docs/status.md",
    "docs/decisions.md",
    "docs/requirements.md",
    "docs/acceptance.md",
    "docs/roadmap.md",
    "docs/release.md",
    "docs/contracts/recognition.md",
    "docs/contracts/openapi.json",
    "docs/source-manifest.json",
    "docs/source-requirements.md",
)
ROW_PATTERN = re.compile(r"^\| ([A-Z]+-\d{2}) \| ([^|]+) \| (.+) \|$", re.MULTILINE)
VALID_STATES = {
    "\u5f85\u5f00\u53d1",
    "\u5b9e\u73b0\u4e2d",
    "\u5f85\u9a8c\u8bc1",
    "\u9a8c\u6536\u901a\u8fc7",
    "\u5f85\u5916\u90e8\u4f9d\u8d56",
}
ACCEPTED = "\u9a8c\u6536\u901a\u8fc7"


def check() -> int:
    errors = [f"Missing file: {name}" for name in REQUIRED_FILES if not (ROOT / name).is_file()]
    if errors:
        print("\n".join(errors))
        return 1

    requirements = ROW_PATTERN.findall((ROOT / "docs/requirements.md").read_text(encoding="utf-8"))
    acceptance = ROW_PATTERN.findall((ROOT / "docs/acceptance.md").read_text(encoding="utf-8"))
    expected_ids = {row[0] for row in requirements}
    actual_ids = {row[0] for row in acceptance}
    if not expected_ids:
        errors.append("No requirement IDs found")
    if expected_ids != actual_ids:
        errors.append(f"Requirement/acceptance mismatch: {sorted(expected_ids ^ actual_ids)}")
    for name, rows in (("requirements", requirements), ("acceptance", acceptance)):
        duplicates = [key for key, count in Counter(row[0] for row in rows).items() if count > 1]
        if duplicates:
            errors.append(f"Duplicate IDs in {name}: {duplicates}")
    for requirement_id, state, evidence in acceptance:
        if state.strip() not in VALID_STATES:
            errors.append(f"Invalid state: {requirement_id}")
        if state.strip() == ACCEPTED:
            links = re.findall(r"\]\(([^)]+)\)", evidence)
            if not links or any(not (ROOT / "docs" / link).is_file() for link in links):
                errors.append(
                    f"Accepted requirement has no existing evidence link: {requirement_id}"
                )

    manifest = json.loads((ROOT / "docs/source-manifest.json").read_text(encoding="utf-8"))
    source_path = ROOT / manifest["source_file"]
    if source_path.exists():
        if hashlib.sha256(source_path.read_bytes()).hexdigest() != manifest["sha256"]:
            errors.append("Original DOCX changed: review and regenerate the source baseline")
    else:
        print("Source DOCX absent in this checkout; source hash comparison skipped")

    expected_contract = create_app(
        settings=Settings(_env_file=None, environment="test", database_url="sqlite:///:memory:"),
        dictionary=CharacterDictionary([]),
    ).openapi()
    actual_contract = json.loads((ROOT / "docs/contracts/openapi.json").read_text(encoding="utf-8"))
    if actual_contract != expected_contract:
        errors.append("OpenAPI drift: run python scripts/export_openapi.py")

    if errors:
        print("\n".join(errors))
        return 1
    print(
        f"Project checks passed: {len(expected_ids)} requirements, evidence links, source and API"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(check())
