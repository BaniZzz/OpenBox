"""add_platform_accounts

授权中心: platform accounts bound to a workspace (Douyin open-platform OAuth
first), publish jobs for the H5 share flow, and in-app notifications.

Revision ID: a5c0d1e2f3a4
Revises: f3a5b7c9d1e4
Create Date: 2026-09-07 18:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = 'a5c0d1e2f3a4'
down_revision: Union[str, None] = 'f3a5b7c9d1e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "platform_accounts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("workspace_id", sa.String(64), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("bound_by_user_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("auth_kind", sa.String(16), nullable=False, server_default=sa.text("'oauth'")),
        sa.Column("external_id", sa.String(128), nullable=False),
        sa.Column("union_id", sa.String(128), nullable=True),
        sa.Column("nickname", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.String(1024), nullable=True),
        sa.Column("scopes", sa.String(256), nullable=False, server_default=sa.text("''")),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'bound'")),
        sa.Column("access_token_ciphertext", sa.Text(), nullable=True),
        sa.Column("refresh_token_ciphertext", sa.Text(), nullable=True),
        sa.Column("access_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refresh_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("renew_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_refresh_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_probe_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_ok_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("bound_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "uq_platform_accounts_live",
        "platform_accounts",
        ["workspace_id", "platform", "external_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_platform_accounts_workspace", "platform_accounts", ["workspace_id", "platform"])
    op.create_index("ix_platform_accounts_access_due", "platform_accounts", ["status", "access_expires_at"])
    op.create_index("ix_platform_accounts_refresh_due", "platform_accounts", ["status", "refresh_expires_at"])

    op.create_table(
        "publish_jobs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("workspace_id", sa.String(64), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("platform_account_id", sa.String(64), nullable=True),
        sa.Column("file_asset_id", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False, server_default=sa.text("''")),
        sa.Column("hashtags", sa.JSON(), nullable=False),
        sa.Column("share_id", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("item_id", sa.String(128), nullable=True),
        sa.Column("video_id", sa.String(128), nullable=True),
        sa.Column("from_open_id", sa.String(128), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_publish_jobs_share", "publish_jobs", ["share_id"])
    op.create_index("ix_publish_jobs_workspace_created", "publish_jobs", ["workspace_id", "created_at"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("workspace_id", sa.String(64), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=True),
        sa.Column("kind", sa.String(48), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_notifications_workspace_created", "notifications", ["workspace_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_notifications_workspace_created", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_publish_jobs_workspace_created", table_name="publish_jobs")
    op.drop_index("ix_publish_jobs_share", table_name="publish_jobs")
    op.drop_table("publish_jobs")
    op.drop_index("ix_platform_accounts_refresh_due", table_name="platform_accounts")
    op.drop_index("ix_platform_accounts_access_due", table_name="platform_accounts")
    op.drop_index("ix_platform_accounts_workspace", table_name="platform_accounts")
    op.drop_index("uq_platform_accounts_live", table_name="platform_accounts")
    op.drop_table("platform_accounts")
