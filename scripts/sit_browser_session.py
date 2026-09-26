"""Issue a short-lived SIT browser session through an encrypted SSH stdout pipe only.

Never invoke directly in a visible terminal or redirect output to an evidence file.
The caller must consume the token in memory and must forward HTTP inside SSH.
"""

import argparse
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import delete, select
from sqlalchemy.engine import make_url

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.business.auth import digest, token_response  # noqa: E402
from backend.app.business.database import Database  # noqa: E402
from backend.app.business.models import Audit, SessionToken, User  # noqa: E402
from backend.app.config import Settings  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-database", required=True)
    args = parser.parse_args()
    if sys.stdout.isatty():
        raise SystemExit("Refusing to expose a session in a terminal")
    settings = Settings()
    if make_url(settings.database_url).database != args.confirm_database:
        raise SystemExit("Database confirmation mismatch")
    database = Database(settings.database_url)
    token = None
    try:
        with database.write() as session:
            identity = session.execute(
                select(
                    User.id,
                    User.username,
                    User.display_name,
                    User.role,
                    User.merchant_id,
                    User.status,
                    User.created_at,
                )
                .where(User.role == "admin", User.status == "active")
                .limit(1)
            ).one()
            actor = SimpleNamespace(**identity._mapping)
            response = token_response(session, actor, SimpleNamespace(session_hours=0.05))
            token = response["access_token"]
            session.add(
                Audit(
                    user_id=actor.id,
                    action="sit_browser_check",
                    entity_type="test_suite",
                    entity_id="SIT_V1",
                    detail={"expires_seconds": 180},
                )
            )
        print(json.dumps(response), flush=True)
        # Keep forwarding alive; revoke when the browser logs out or this lease ends.
        for _ in range(90):
            time.sleep(2)
            with database.session() as session:
                if not session.scalar(
                    select(SessionToken.token_hash).where(SessionToken.token_hash == digest(token))
                ):
                    break
    finally:
        if token:
            with database.write() as session:
                session.execute(
                    delete(SessionToken).where(SessionToken.token_hash == digest(token))
                )
        database.engine.dispose()


if __name__ == "__main__":
    main()
