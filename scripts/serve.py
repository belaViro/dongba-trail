"""Run the API with explicit development or isolated UI-acceptance data."""

import argparse
import sys
from pathlib import Path

import uvicorn
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.config import Settings  # noqa: E402
from backend.app.main import create_app  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", choices=("development", "ui"), default="development")
    parser.add_argument("--port", type=int, default=8010)
    args = parser.parse_args()
    overrides = {"public_base_url": f"http://127.0.0.1:{args.port}"}
    if args.database == "ui":
        values = dotenv_values(ROOT / ".env")
        url = values.get("DONGBA_UI_DATABASE_URL")
        if not url or "/dongba_ui?" not in url:
            raise SystemExit("Initialize the isolated UI database with scripts/mysql_local.py")
        overrides.update(database_url=url, environment="test", request_limit_per_minute=2000)
    app = create_app(settings=Settings(**overrides))
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="info")
