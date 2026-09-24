from alembic import context
from sqlalchemy import create_engine

from backend.app.business.models import Base
from backend.app.config import Settings

configuration = context.config
target_metadata = Base.metadata


def run_migrations():
    supplied = configuration.attributes.get("connection")
    if supplied is not None:
        context.configure(connection=supplied, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
        return
    url = configuration.attributes.get("database_url") or Settings().database_url
    if context.is_offline_mode():
        context.configure(
            url=url,
            target_metadata=target_metadata,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
        )
        with context.begin_transaction():
            context.run_migrations()
    else:
        engine = create_engine(url, pool_pre_ping=True)
        try:
            with engine.connect() as connection:
                context.configure(
                    connection=connection, target_metadata=target_metadata, compare_type=True
                )
                with context.begin_transaction():
                    context.run_migrations()
        finally:
            engine.dispose()


run_migrations()
