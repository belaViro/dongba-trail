"""Create the independent RAG schema for a configured environment."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.config import Settings  # noqa: E402
from backend.app.rag_database import RagDatabase  # noqa: E402


def main() -> None:
    settings = Settings()
    if not settings.rag_database_url:
        raise SystemExit("DONGBA_RAG_DATABASE_URL must point to a separate MySQL database")
    if not settings.rag_database_url.startswith("mysql+pymysql://"):
        raise SystemExit("The production RAG database must use MySQL with PyMySQL")
    RagDatabase(settings.rag_database_url, auto_create=True).engine.dispose()
    print("RAG database schema created")


if __name__ == "__main__":
    main()
