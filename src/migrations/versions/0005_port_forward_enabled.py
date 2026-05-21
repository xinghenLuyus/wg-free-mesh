"""add port forward enabled flag

Revision ID: 0005_port_forward_enabled
Revises: 0004_port_forward_rules
Create Date: 2026-05-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0005_port_forward_enabled"
down_revision = "0004_port_forward_rules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("port_forward_rules", sa.Column("enabled", sa.Integer(), nullable=False, server_default="1"))


def downgrade() -> None:
    op.drop_column("port_forward_rules", "enabled")
