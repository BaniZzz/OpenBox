"""Preserve retry keys when multiple checkout attempts share a pending order.

Revision ID: c0e2f4a6b8d0
Revises: b9d1f3a5c7e9
"""
from alembic import op
import sqlalchemy as sa

revision = "c0e2f4a6b8d0"
down_revision = "b9d1f3a5c7e9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("payment_order_requests",
        sa.Column("workspace_id", sa.String(64), sa.ForeignKey("workspaces.id"), primary_key=True),
        sa.Column("request_key", sa.String(128), primary_key=True),
        sa.Column("order_id", sa.String(64), sa.ForeignKey("payment_orders.id"), nullable=False))
    op.execute("INSERT INTO payment_order_requests (workspace_id, request_key, order_id) "
               "SELECT workspace_id, request_key, id FROM payment_orders")


def downgrade():
    op.drop_table("payment_order_requests")
