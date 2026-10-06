"""Business application integration entry point."""

import logging

from sqlalchemy.exc import SQLAlchemyError

from .auth import current_user
from .database import Database
from .models import User

__all__ = ["Database", "User", "current_user", "install_business"]


def install_business(app, settings):
    from .api import router
    from .auth import router as auth_router
    from .exports import router as export_router
    from .samples import router as sample_router

    database = Database(settings.database_url, getattr(settings, "auto_create_schema", False))
    app.state.database = database
    app.state.business_settings = settings
    rag_database = None
    if getattr(settings, "rag_database_url", ""):
        from backend.app.rag_database import RagDatabase

        rag_database = RagDatabase(settings.rag_database_url)
        if getattr(settings, "auto_create_schema", False):
            try:
                rag_database.create_schema()
            except SQLAlchemyError:
                logging.getLogger(__name__).warning("rag_schema_unavailable")
    app.state.rag_database = rag_database
    app.include_router(auth_router)
    app.include_router(router)
    app.include_router(export_router)
    app.include_router(sample_router)
    from backend.app.rag import router as rag_router

    app.include_router(rag_router)
    return database
