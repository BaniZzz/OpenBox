"""Plan order snapshots and prepaid subscription periods.

Revision ID: b9d1f3a5c7e9
Revises: a8c0e2f4b6d9
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b9d1f3a5c7e9"
down_revision = "a8c0e2f4b6d9"
branch_labels = None
depends_on = None


def upgrade():
    js = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
    op.add_column("payment_orders", sa.Column("kind", sa.String(24), nullable=False, server_default="topup"))
    op.add_column("payment_orders", sa.Column("product", js, nullable=True))
    op.create_table("billing_subscriptions",
        sa.Column("order_id", sa.String(64), sa.ForeignKey("payment_orders.id"), primary_key=True),
        sa.Column("workspace_id", sa.String(64), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("plan_id", sa.String(24), nullable=False),
        sa.Column("cycle", sa.String(16), nullable=False),
        sa.Column("plan", js, nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("ends_at > starts_at", name="ck_subscription_dates"))
    op.create_index("ix_subscription_workspace_dates", "billing_subscriptions", ["workspace_id", "starts_at", "ends_at"])


def downgrade():
    op.drop_table("billing_subscriptions")
    op.drop_column("payment_orders", "product")
    op.drop_column("payment_orders", "kind")
