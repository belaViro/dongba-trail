"""Export the contract from an isolated application, without runtime credentials."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.config import Settings  # noqa: E402
from backend.app.dictionary import CharacterDictionary  # noqa: E402
from backend.app.main import create_app  # noqa: E402

application = create_app(
    settings=Settings(_env_file=None, environment="test", database_url="sqlite:///:memory:"),
    dictionary=CharacterDictionary([]),
)
target = ROOT / "docs" / "contracts" / "openapi.json"
target.write_text(
    json.dumps(application.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
print(f"Exported {len(application.openapi()['paths'])} paths to {target.relative_to(ROOT)}")
