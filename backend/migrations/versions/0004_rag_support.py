"""Store observed recognition text and RAG retrieval hits."""

import sqlalchemy as sa
from alembic import op

revision = "0004_rag_support"
down_revision = "0003_data_foundation"
branch_labels = None
depends_on = None


def upgrade():
    # Add the columns as nullable first so existing recognition rows can be migrated safely.
    op.add_column("recognitions", sa.Column("observed_text", sa.Text(), nullable=True))
    op.add_column("recognitions", sa.Column("rag_hits", sa.JSON(), nullable=True))

    op.execute(
        sa.text(
            "UPDATE recognitions SET observed_text = :empty_text, rag_hits = :empty_json"
        ).bindparams(empty_text="", empty_json="[]")
    )

    with op.batch_alter_table("recognitions") as batch_op:
        batch_op.alter_column(
            "observed_text",
            existing_type=sa.Text(),
            nullable=False,
        )
        batch_op.alter_column(
            "rag_hits",
            existing_type=sa.JSON(),
            nullable=False,
        )


def downgrade():
    with op.batch_alter_table("recognitions") as batch_op:
        batch_op.drop_column("rag_hits")
        batch_op.drop_column("observed_text")
