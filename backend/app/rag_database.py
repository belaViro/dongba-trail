"""Database wrapper for the separate RAG case store."""

from contextlib import contextmanager, nullcontext
from pathlib import Path
from threading import RLock

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from .rag_models import RagBase


class RagDatabase:
    def __init__(self, url: str, *, auto_create: bool = False):
        self.sqlite = url.startswith("sqlite")
        kwargs = {}
        if url.startswith("mysql"):
            kwargs["isolation_level"] = "READ COMMITTED"
        if self.sqlite:
            kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
            if url.endswith(":memory:"):
                kwargs["poolclass"] = StaticPool
            elif url.startswith("sqlite:///"):
                Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(url, pool_pre_ping=True, hide_parameters=True, **kwargs)
        self._lock = RLock()
        if self.sqlite:

            @event.listens_for(self.engine, "connect")
            def sqlite_settings(connection, _):
                connection.execute("PRAGMA foreign_keys=ON")
                connection.execute("PRAGMA busy_timeout=30000")

        if auto_create:
            self.create_schema()

    def create_schema(self):
        RagBase.metadata.create_all(self.engine)

    def dispose(self):
        self.engine.dispose()

    @contextmanager
    def session(self):
        with Session(self.engine, expire_on_commit=False) as session:
            yield session

    @contextmanager
    def write(self):
        with self._lock if self.sqlite else nullcontext(), self.session() as session:
            try:
                if self.sqlite:
                    session.connection().exec_driver_sql("BEGIN IMMEDIATE")
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
