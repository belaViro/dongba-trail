"""Hash source, tests, dependencies and generated API contract for verification records."""

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
paths = [ROOT / name for name in ("pyproject.toml", ".env.example", ".dockerignore")]
paths.append(ROOT / "docs" / "contracts" / "openapi.json")
excluded = {"node_modules", "dist", "__pycache__", ".pytest_cache", ".ruff_cache"}
for folder in ("backend", "scripts", "data", "deploy", "miniprogram", "web", "tests"):
    paths.extend(
        path
        for path in (ROOT / folder).rglob("*")
        if path.is_file()
        and not excluded.intersection(path.relative_to(ROOT).parts)
        and path.name not in {".env", "project.private.config.json"}
        and not path.name.endswith((".md", ".log", ".pyc"))
        and "certs" not in path.relative_to(ROOT).parts
    )
digest = hashlib.sha256()
for path in sorted(paths, key=lambda item: item.relative_to(ROOT).as_posix()):
    digest.update(path.relative_to(ROOT).as_posix().encode("utf-8") + b"\0")
    digest.update(path.read_bytes().replace(b"\r\n", b"\n") + b"\0")
print(f"sha256:{digest.hexdigest()}")
print(f"files:{len(paths)}")
