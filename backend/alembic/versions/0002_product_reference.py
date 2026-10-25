"""справочник продуктов: поля из CSV и таблица некредитных продуктов

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-22 23:40:00
"""

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("products") as batch:
        batch.add_column(sa.Column("segment", sa.String(length=16), nullable=False, server_default="msb"))
        batch.add_column(sa.Column("family", sa.String(length=40), nullable=False, server_default=""))
        batch.add_column(sa.Column("purpose_tags", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("pricing_type", sa.String(length=32), nullable=False, server_default=""))
        batch.add_column(
            sa.Column("collateral_policy", sa.String(length=24), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column("new_business_allowed", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch.add_column(
            sa.Column("marketplace_required", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch.add_column(sa.Column("effective_at", sa.String(length=10), nullable=False, server_default=""))
        batch.add_column(sa.Column("calculable", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_table(
        "bank_products",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("segment", sa.String(length=16), nullable=False),
        sa.Column("family", sa.String(length=40), nullable=False),
        sa.Column("purpose_tags", sa.JSON(), nullable=False),
        sa.Column("eligibility_tags", sa.JSON(), nullable=False),
        sa.Column("source_url", sa.String(length=160), nullable=False),
        sa.Column("effective_at", sa.String(length=10), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("bank_products")
    with op.batch_alter_table("products") as batch:
        for col in (
            "calculable",
            "effective_at",
            "marketplace_required",
            "new_business_allowed",
            "collateral_policy",
            "pricing_type",
            "purpose_tags",
            "family",
            "segment",
        ):
            batch.drop_column(col)
