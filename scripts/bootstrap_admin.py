"""Create the first administrator offline without enabling public HTTP setup."""

import argparse
import getpass
import os
import sys
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.business.auth import password_hash  # noqa: E402
from backend.app.business.database import Database  # noqa: E402
from backend.app.business.models import Audit, Setting, User  # noqa: E402
from backend.app.business.schemas import Setup  # noqa: E402
from backend.app.config import Settings  # noqa: E402


def bootstrap(database, username, password, display_name):
    try:
        payload = Setup(username=username, password=password, display_name=display_name)
    except ValidationError:
        raise ValueError("Account fields do not meet the setup requirements") from None
    if len(password) < 12:
        raise ValueError("Administrator password must contain at least 12 characters")
    with database.write() as session:
        setting = session.scalar(select(Setting).where(Setting.key == "setup").with_for_update())
        if setting is None:
            raise ValueError("Run database migrations first")
        if setting.value.get("complete") or session.scalar(
            select(User.id).where(User.role == "admin").limit(1)
        ):
            raise ValueError("An administrator already exists; no changes made")
        user = User(
            username=payload.username,
            password_hash=password_hash(password),
            display_name=payload.display_name,
            role="admin",
        )
        session.add(user)
        session.flush()
        setting.value = {"complete": True}
        session.add(
            Audit(user_id=user.id, action="offline_setup", entity_type="users", entity_id=user.id)
        )
    return user.id


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", required=True)
    parser.add_argument("--display-name", default="Administrator")
    args = parser.parse_args()
    password = os.environ.pop("DONGBA_BOOTSTRAP_PASSWORD", None) or getpass.getpass(
        "New password: "
    )
    database = Database(Settings().database_url)
    try:
        bootstrap(database, args.username, password, args.display_name)
        print("First administrator created; password was not printed or persisted in configuration")
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    finally:
        database.engine.dispose()
