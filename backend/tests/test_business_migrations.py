import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from dotenv import dotenv_values
from sqlalchemy import MetaData, Table, create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from backend.app.business.models import Base, Entity, Favorite, SessionToken, User

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(params=["sqlite", "mysql"])
def migration_target(request, tmp_path):
    if request.param == "mysql":
        if os.getenv("DONGBA_RUN_MYSQL_TESTS") != "1":
            pytest.skip("Explicit opt-in is required for isolated MySQL tests")
        url = os.getenv("DONGBA_TEST_DATABASE_URL") or dotenv_values(ROOT / ".env").get(
            "DONGBA_TEST_DATABASE_URL"
        )
        assert url and make_url(url).database == "dongba_test"
    else:
        url = f"sqlite:///{(tmp_path / 'migrations.sqlite').as_posix()}"
    engine = create_engine(url, hide_parameters=True)
    Base.metadata.drop_all(engine)
    Table("alembic_version", MetaData()).drop(engine, checkfirst=True)
    config = Config(str(ROOT / "backend" / "alembic.ini"))
    config.attributes["database_url"] = url
    yield engine, config
    engine.dispose()


def test_upgrade_repeat_downgrade_and_schema_drift(migration_target):
    engine, config = migration_target
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT `value` FROM settings WHERE `key`='setup'")).scalar()
        assert connection.execute(text("SELECT COUNT(*) FROM users")).scalar() == 0
        assert connection.execute(text("SELECT COUNT(*) FROM entities")).scalar() == 0
    assert set(Base.metadata.tables).issubset(inspect(engine).get_table_names())
    command.check(config)
    command.downgrade(config, "base")
    assert not (set(Base.metadata.tables) & set(inspect(engine).get_table_names()))
    command.upgrade(config, "head")
    command.check(config)
    if engine.dialect.name == "mysql":
        with engine.connect() as connection:
            tables = connection.execute(
                text(
                    "SELECT ENGINE, TABLE_COLLATION FROM information_schema.TABLES "
                    "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='coupon_claims'"
                )
            ).one()
            assert tables[0] == "InnoDB"
            assert tables[1] == "utf8mb4_bin"


def test_storage_upgrade_preserves_records_and_foreign_keys(migration_target):
    engine, config = migration_target
    command.upgrade(config, "0001_business")
    with Session(engine) as session:
        session.add(User(id="fixture-user", username="fixture", display_name="Fixture"))
        session.add(Entity(id="fixture-glyph", kind="characters", status="draft", data={}))
        session.flush()
        session.add(Favorite(user_id="fixture-user", character_id="fixture-glyph"))
        session.add(
            SessionToken(
                token_hash="f" * 64, user_id="fixture-user", expires_at="2099-01-01T00:00:00+00:00"
            )
        )
        session.commit()
    if engine.dialect.name == "mysql":
        with engine.connect() as connection:
            connection.execute(text("SET FOREIGN_KEY_CHECKS=0"))
            try:
                for table in Base.metadata.tables:
                    connection.execute(
                        text(
                            f"ALTER TABLE `{table}` CONVERT TO CHARACTER SET utf8mb4 "
                            "COLLATE utf8mb4_unicode_ci"
                        )
                    )
            finally:
                connection.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    command.check(config)
    with Session(engine) as session:
        assert session.get(User, "fixture-user").username == "fixture"
        assert session.get(Entity, "fixture-glyph").data == {}
        assert session.get(Favorite, ("fixture-user", "fixture-glyph")) is not None
        assert session.get(SessionToken, "f" * 64).user_id == "fixture-user"
