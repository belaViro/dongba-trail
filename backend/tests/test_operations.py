import json

import pytest
from alembic import command
from sqlalchemy import MetaData, Table, select

from backend.app.business.auth import password_matches
from backend.app.business.database import Database
from backend.app.business.models import Base, Entity, User
from backend.tests.test_business_migrations import migration_target  # noqa: F401
from scripts.backup import backup, capture, restore
from scripts.bootstrap_admin import bootstrap


def test_offline_setup_creates_first_admin_only():
    database = Database("sqlite:///:memory:", auto_create=True)
    try:
        identifier = bootstrap(database, "test_admin", "Test-only-password-42", "Fixture admin")
        with database.session() as session:
            user = session.get(User, identifier)
            assert user.role == "admin"
            assert password_matches("Test-only-password-42", user.password_hash)
        with pytest.raises(ValueError, match="already exists"):
            bootstrap(database, "second_admin", "Test-only-password-43", "Second")
    finally:
        database.engine.dispose()


def test_mysql_backup_restore_matches_database_and_media(migration_target, tmp_path):  # noqa: F811
    engine, config = migration_target
    if engine.dialect.name != "mysql":
        pytest.skip("Backup is a MySQL-only operation")
    command.upgrade(config, "head")
    database = Database(config.attributes["database_url"])
    try:
        bootstrap(database, "backup_admin", "Test-only-password-42", "Fixture admin")
        with database.write() as session:
            session.add(
                Entity(
                    id="backup-fixture",
                    kind="characters",
                    data={"cn_name": "恢复测试", "tags": ["fixture"]},
                )
            )
        media = tmp_path / "source"
        media.mkdir()
        (media / ("a" * 32 + ".png")).write_bytes(b"test-only-asset")
        archive = tmp_path / "backup.zip"
        result = backup(database, media, archive)
        expected = capture(database)["tables"]
        assert result["rows"] >= 4
        assert result["media_files"] == 1
        with pytest.raises(ValueError, match="non-empty"):
            restore(database, tmp_path / "destination", archive)
        Base.metadata.drop_all(engine)
        Table("alembic_version", MetaData()).drop(engine, checkfirst=True)
        command.upgrade(config, "head")
        restored = restore(database, tmp_path / "destination", archive)
        assert restored == result
        assert json.dumps(capture(database)["tables"], sort_keys=True) == json.dumps(
            expected, sort_keys=True
        )
        assert (tmp_path / "destination" / ("a" * 32 + ".png")).read_bytes() == b"test-only-asset"
        with database.session() as session:
            assert session.scalar(select(User)).username == "backup_admin"
    finally:
        database.engine.dispose()
