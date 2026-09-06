"""Join billing and the existing production cloud desktop fleet migrations.

Revision ID: e2f4a6b8c0d2
Revises: d1f3a5b7c9e1, a3f1e5c7d9b2

Both feature branches descend from c3e5a7b9d1f4. A merge revision lets a
deployment already using either branch apply only the missing migrations.
Existing fleet rows, desktop channels, and payment records are preserved.
"""

revision = "e2f4a6b8c0d2"
down_revision = ("d1f3a5b7c9e1", "a3f1e5c7d9b2")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
