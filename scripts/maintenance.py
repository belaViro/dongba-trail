"""Preview retained data cleanup; use --apply to delete expired records and media."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.business.database import Database  # noqa: E402
from backend.app.config import Settings  # noqa: E402
from backend.app.maintenance import purge_expired  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    settings = Settings()
    database = Database(settings.database_url)
    try:
        result = purge_expired(database, settings, dry_run=not args.apply)
        print(json.dumps({"dry_run": not args.apply, **result}))
    finally:
        database.engine.dispose()
