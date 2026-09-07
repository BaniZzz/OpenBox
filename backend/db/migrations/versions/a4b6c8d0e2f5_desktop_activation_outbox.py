"""Durable, payment-triggered desktop activation (no cloud operations in migration)."""
from alembic import op
import sqlalchemy as sa

revision = "a4b6c8d0e2f5"
down_revision = "f3a5b7c9d1e4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "desktop_activations",
        sa.Column("workspace_id", sa.String(64), sa.ForeignKey("workspaces.id"), primary_key=True),
        sa.Column("request_id", sa.String(64)),
        sa.Column("user_id", sa.String(64)),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("step", sa.String(24), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_owner", sa.String(64)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("purchase_kind", sa.String(16)),
        sa.Column("purchase_started_at", sa.DateTime(timezone=True)),
        sa.Column("purchase_baseline", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_desktop_activations_due", "desktop_activations", ["next_run_at", "lease_until"])


def downgrade():
    op.drop_table("desktop_activations")
