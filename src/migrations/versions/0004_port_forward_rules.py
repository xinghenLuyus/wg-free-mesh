"""add managed port forward rules

Revision ID: 0004_port_forward_rules
Revises: 0003_mqtt_password
Create Date: 2026-05-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_port_forward_rules"
down_revision = "0003_mqtt_password"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "port_forward_rules",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("config_id", sa.String(), sa.ForeignKey("configs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_node_id", sa.String(), sa.ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_port", sa.Integer(), nullable=False),
        sa.Column("to_node_id", sa.String(), sa.ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("to_port", sa.Integer(), nullable=False),
        sa.Column("to_platform", sa.String(), nullable=False),
        sa.Column("protocol", sa.String(), nullable=False, server_default="tcp"),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_index("ix_port_forward_rules_config_id", "port_forward_rules", ["config_id"])
    op.create_index("uq_port_forward_rules_to_port", "port_forward_rules", ["to_node_id", "to_port", "protocol"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_port_forward_rules_to_port", table_name="port_forward_rules")
    op.drop_index("ix_port_forward_rules_config_id", table_name="port_forward_rules")
    op.drop_table("port_forward_rules")
