"""Business application integration entry point."""

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
    app.include_router(auth_router)
    app.include_router(router)
    app.include_router(export_router)
    app.include_router(sample_router)
    return database
