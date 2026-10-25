"""структурированный запрос банка: пункты, ответы клиента и привязка документов к пунктам

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-23 14:00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("applications") as batch:
        batch.add_column(sa.Column("info_request", sa.JSON(), nullable=True))
    with op.batch_alter_table("documents") as batch:
        batch.add_column(sa.Column("request_item", sa.String(length=20), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("documents") as batch:
        batch.drop_column("request_item")
    with op.batch_alter_table("applications") as batch:
        batch.drop_column("info_request")
