"""Repair starter projects created by registration after the first name migration.

Revision ID: f3a5b7c9d1e4
Revises: e2f4a6b8c0d2
"""
from alembic import op

revision = "f3a5b7c9d1e4"
down_revision = "e2f4a6b8c0d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE projects SET name = '默认空间' "
        "WHERE slug = 'default' AND name = 'Default'"
    )


def downgrade() -> None:
    # Display names cannot be reversed without also renaming projects that
    # already had this name. Keep the data repair when rolling back code.
    pass
