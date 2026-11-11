"""Remove previously revoked MCP credentials while retaining audit logs."""

from alembic import op

revision = "0010_delete_revoked_mcp_tokens"
down_revision = "0009_runtime_wg_observed_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DELETE FROM mcp_tokens WHERE revoked_at IS NOT NULL")


def downgrade() -> None:
    # Deleted credentials must remain invalid.
    pass
