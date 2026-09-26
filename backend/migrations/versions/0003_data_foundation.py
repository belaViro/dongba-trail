"""Reviewed image samples and immutable content revision snapshots."""

from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "0003_data_foundation"
down_revision = "0002_mysql_storage"
branch_labels = None
depends_on = None

OPTIONS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_bin"}


def upgrade():
    revisions = op.create_table(
        "entity_revisions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("entity_id", sa.String(64), sa.ForeignKey("entities.id"), nullable=False),
        sa.Column("resource", sa.String(30), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.UniqueConstraint("entity_id", "version"),
        **OPTIONS,
    )
    op.create_index("ix_entity_revisions_entity_id", "entity_revisions", ["entity_id"])
    op.create_index("ix_entity_revisions_resource", "entity_revisions", ["resource"])
    op.create_table(
        "samples",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "recognition_id", sa.String(64), sa.ForeignKey("recognitions.request_id"), nullable=True
        ),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("character_id", sa.String(64), sa.ForeignKey("entities.id"), nullable=True),
        sa.Column("image_uri", sa.String(1000), nullable=False),
        sa.Column("sample_type", sa.String(20), nullable=False),
        sa.Column("scene", sa.String(100), nullable=False),
        sa.Column("bbox", sa.JSON(), nullable=True),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("label_source", sa.String(30), nullable=False),
        sa.Column("review_status", sa.String(20), nullable=False),
        sa.Column("dataset_split", sa.String(20), nullable=False),
        sa.Column("dataset_version", sa.String(100), nullable=False),
        sa.Column("source_ref", sa.String(1000), nullable=False),
        sa.Column("review_note", sa.Text(), nullable=False),
        sa.Column("reviewed_by", sa.String(64), nullable=True),
        sa.Column("reviewed_at", sa.String(40), nullable=True),
        sa.Column("consent_version", sa.String(100), nullable=True),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        **OPTIONS,
    )
    for field in (
        "recognition_id",
        "user_id",
        "character_id",
        "review_status",
        "dataset_version",
        "created_at",
    ):
        op.create_index(f"ix_samples_{field}", "samples", [field])

    connection = op.get_bind()
    entities = sa.Table("entities", sa.MetaData(), autoload_with=connection)
    stock = sa.Table("coupon_stock", sa.MetaData(), autoload_with=connection)
    for row in connection.execute(sa.select(entities)).mappings():
        snapshot = {
            **row["data"],
            **{
                field: row[field]
                for field in (
                    "id",
                    "status",
                    "created_at",
                    "updated_at",
                    "reviewed_by",
                    "reviewed_at",
                )
            },
        }
        if row["kind"] == "characters":
            snapshot["character_id"] = row["id"]
            for key, default in (
                ("source_no", None),
                ("alias", []),
                ("keywords", []),
                ("commercial_tags", []),
            ):
                snapshot.setdefault(key, default)
        if row["kind"] == "coupons":
            inventory = (
                connection.execute(sa.select(stock).where(stock.c.coupon_id == row["id"]))
                .mappings()
                .first()
            )
            if inventory:
                snapshot.update(stock=inventory["stock"], claimed_count=inventory["claimed_count"])
        connection.execute(
            revisions.insert().values(
                id=str(uuid4()),
                entity_id=row["id"],
                resource=row["kind"],
                version=1,
                action="baseline",
                actor_id=None,
                created_at=row["updated_at"],
                snapshot=snapshot,
            )
        )


def downgrade():
    op.drop_table("samples")
    op.drop_table("entity_revisions")
