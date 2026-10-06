from contextlib import contextmanager, nullcontext
from pathlib import Path
from threading import RLock

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from .models import Base, Entity, Favorite, RecognitionRecord, Setting


class Database:
    def __init__(self, url: str, auto_create: bool = False):
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
        Base.metadata.create_all(self.engine)
        with self.write() as session:
            if session.get(Setting, "setup") is None:
                session.add(Setting(key="setup", value={"complete": False}))

    @contextmanager
    def session(self):
        with Session(self.engine, expire_on_commit=False) as session:
            yield session

    @contextmanager
    def write(self):
        # SQLite needs an immediate write reservation before read/modify/write.
        with self._lock if self.sqlite else nullcontext(), self.session() as session:
            try:
                if self.sqlite:
                    session.connection().exec_driver_sql("BEGIN IMMEDIATE")
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    def published_characters(self) -> list[dict]:
        from .content import serialize

        with self.session() as session:
            rows = session.scalars(
                select(Entity).where(Entity.kind == "characters", Entity.status == "published")
            ).all()
            return [serialize(row) for row in rows]

    def record_recognition(
        self,
        *,
        request_id: str,
        user_id: str,
        status: str,
        provider: str,
        model: str,
        candidates: list,
        observed_text: str = "",
        rag_hits: list | None = None,
        latency_ms: int,
        scene: str = "camera",
        error_code: str | None = None,
    ):
        with self.write() as session:
            if session.get(RecognitionRecord, request_id) is None:
                session.add(
                    RecognitionRecord(
                        request_id=request_id,
                        user_id=user_id,
                        status=status,
                        provider=provider,
                        model=model,
                        candidates=candidates,
                        observed_text=observed_text,
                        rag_hits=rag_hits or [],
                        latency_ms=latency_ms,
                        scene=scene,
                        error_code=error_code,
                    )
                )

    def allowed_poster_character_ids(self, user_id: str) -> set[str]:
        with self.session() as session:
            favorites = session.scalars(
                select(Favorite.character_id).where(Favorite.user_id == user_id)
            ).all()
            recognized = session.scalars(
                select(RecognitionRecord.confirmed_character_id).where(
                    RecognitionRecord.user_id == user_id,
                    RecognitionRecord.history_deleted.is_(False),
                    RecognitionRecord.confirmed_character_id.is_not(None),
                )
            ).all()
            return set(favorites) | set(recognized)
