"""Workspace credit accounts, immutable usage and payment orders.

Revision ID: a8c0e2f4b6d9
Revises: c3e5a7b9d1f4
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a8c0e2f4b6d9"
down_revision = "c3e5a7b9d1f4"
branch_labels = None
depends_on = None


def upgrade():
    credits = sa.Numeric(28, 12)
    js = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
    op.create_table("credit_balances",
        sa.Column("workspace_id", sa.String(64), sa.ForeignKey("workspaces.id"), primary_key=True),
        sa.Column("balance", credits, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("usage_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("idempotency_key", sa.String(160), nullable=False, unique=True),
        sa.Column("workspace_id", sa.String(64), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.Column("message_id", sa.String(64), nullable=True),
        sa.Column("session_title", sa.String(255), nullable=False),
        sa.Column("model_id", sa.String(160), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("tokens", js, nullable=False),
        sa.Column("total_tokens", sa.BigInteger(), nullable=False),
        sa.Column("credits", credits, nullable=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("pricing", js, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("total_tokens >= 0", name="ck_usage_tokens_nonnegative"),
        sa.CheckConstraint("credits IS NULL OR credits >= 0", name="ck_usage_credits_nonnegative"))
    op.create_index("ix_usage_workspace_created", "usage_events", ["workspace_id", "created_at", "id"])
    op.create_index("ix_usage_message", "usage_events", ["message_id"])
    op.create_table("credit_ledger",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("workspace_id", sa.String(64), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False, unique=True),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("amount", credits, nullable=False),
        sa.Column("balance_after", credits, nullable=False),
        sa.Column("reference_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_ledger_workspace_created", "credit_ledger", ["workspace_id", "created_at", "id"])
    op.create_table("payment_orders",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("workspace_id", sa.String(64), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("request_key", sa.String(128), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("amount_fen", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("credits", credits, nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("checkout_url", sa.String(2048), nullable=True),
        sa.Column("provider_order_id", sa.String(160), nullable=True),
        sa.Column("provider_payment_id", sa.String(160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("workspace_id", "request_key", name="uq_payment_request"),
        sa.UniqueConstraint("provider", "provider_payment_id", name="uq_provider_payment"),
        sa.CheckConstraint("amount_fen > 0 AND credits > 0", name="ck_payment_positive"))
    op.create_index("ix_payment_workspace_created", "payment_orders", ["workspace_id", "created_at"])


def downgrade():
    for table in ("payment_orders", "credit_ledger", "usage_events", "credit_balances"):
        op.drop_table(table)
