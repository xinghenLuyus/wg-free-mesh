"""add mcp access tables

Revision ID: 0006_mcp_access
Revises: 0005_port_forward_enabled
Create Date: 2026-05-22
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0006_mcp_access"
down_revision = "0005_port_forward_enabled"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mcp_tokens",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("token", sa.Text(), nullable=False, unique=True),
        sa.Column("permission", sa.String(), nullable=False),
        sa.Column("expires_at", sa.String(), nullable=False),
        sa.Column("revoked_at", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_table(
        "mcp_audit_logs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("token_id", sa.String(), sa.ForeignKey("mcp_tokens.id", ondelete="SET NULL"), nullable=True),
        sa.Column("token_name", sa.String(), nullable=False, server_default=""),
        sa.Column("permission", sa.String(), nullable=False, server_default=""),
        sa.Column("target_kind", sa.String(), nullable=False),
        sa.Column("target_name", sa.String(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("impact", sa.Text(), nullable=False, server_default=""),
        sa.Column("confirmation_required", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("confirmation_result", sa.String(), nullable=False, server_default=""),
        sa.Column("result", sa.String(), nullable=False),
        sa.Column("error_code", sa.String(), nullable=False, server_default=""),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_index("ix_mcp_audit_logs_token_id", "mcp_audit_logs", ["token_id"])


def downgrade() -> None:
    op.drop_index("ix_mcp_audit_logs_token_id", table_name="mcp_audit_logs")
    op.drop_table("mcp_audit_logs")
    op.drop_table("mcp_tokens")
