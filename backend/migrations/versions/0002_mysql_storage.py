"""Normalize existing MySQL table storage without deleting business records."""

import sqlalchemy as sa
from alembic import op

revision = "0002_mysql_storage"
down_revision = "0001_business"
branch_labels = None
depends_on = None

TABLES = (
    "audit",
    "entities",
    "events",
    "login_attempts",
    "settings",
    "users",
    "coupon_claims",
    "coupon_stock",
    "favorites",
    "quest_enrollments",
    "recognitions",
    "sessions",
    "stamps",
    "tag_claims",
    "feedback",
)


def upgrade():
    connection = op.get_bind()
    if connection.dialect.name != "mysql":
        return
    # Collation changes on referenced columns must happen together on this connection.
    connection.execute(sa.text("SET FOREIGN_KEY_CHECKS=0"))
    try:
        for table in TABLES:
            connection.execute(
                sa.text(
                    f"ALTER TABLE `{table}` ENGINE=InnoDB, "
                    "CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_bin"
                )
            )
    finally:
        connection.execute(sa.text("SET FOREIGN_KEY_CHECKS=1"))


def downgrade():
    # Keeping exact string comparison is safe for old code. Reintroducing a case-insensitive
    # collation could reject data created since upgrade and must be a separate reviewed migration.
    pass
