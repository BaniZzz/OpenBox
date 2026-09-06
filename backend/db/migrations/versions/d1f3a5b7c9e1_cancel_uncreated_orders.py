"""Distinguish merchant cancellations from confirmed gateway trade closures.

Revision ID: d1f3a5b7c9e1
Revises: c0e2f4a6b8d0
"""
from alembic import op
import sqlalchemy as sa

revision = "d1f3a5b7c9e1"
down_revision = "c0e2f4a6b8d0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("payment_orders", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("payment_orders", sa.Column("cancellation_reason", sa.String(32), nullable=True))
    op.execute("UPDATE payment_orders SET cancellation_reason = 'gateway_closed' WHERE status = 'cancelled'")


def downgrade():
    op.drop_column("payment_orders", "cancellation_reason")
    op.drop_column("payment_orders", "cancelled_at")
