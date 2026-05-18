"""add tunnel protocol and amneziawg fields

Revision ID: 0002_tunnel_protocol_awg
Revises: 0001_initial_schema
Create Date: 2026-05-15
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection


revision = "0002_tunnel_protocol_awg"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def _existing_columns(connection: Connection, table_name: str) -> set[str]:
    return {str(column["name"]) for column in sa.inspect(connection).get_columns(table_name)}


def _add_missing_columns(table_name: str, columns: list[sa.Column]) -> None:
    existing = _existing_columns(op.get_bind(), table_name)
    missing = [column for column in columns if column.name not in existing]
    if not missing:
        return
    with op.batch_alter_table(table_name) as batch:
        for column in missing:
            batch.add_column(column)


def upgrade() -> None:
    _add_missing_columns(
        "configs",
        [
            sa.Column("tunnel_protocol", sa.String(), nullable=False, server_default="wireguard"),
            sa.Column("awg_s1", sa.Integer()),
            sa.Column("awg_s2", sa.Integer()),
            sa.Column("awg_s3", sa.Integer()),
            sa.Column("awg_s4", sa.Integer()),
            sa.Column("awg_h1", sa.String()),
            sa.Column("awg_h2", sa.String()),
            sa.Column("awg_h3", sa.String()),
            sa.Column("awg_h4", sa.String()),
        ],
    )

    _add_missing_columns(
        "nodes",
        [
            sa.Column("pre_up_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("post_up_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("pre_down_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("post_down_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("awg_jc", sa.Integer()),
            sa.Column("awg_jmin", sa.Integer()),
            sa.Column("awg_jmax", sa.Integer()),
            sa.Column("awg_i1", sa.Text()),
            sa.Column("awg_i2", sa.Text()),
            sa.Column("awg_i3", sa.Text()),
            sa.Column("awg_i4", sa.Text()),
            sa.Column("awg_i5", sa.Text()),
        ],
    )


def downgrade() -> None:
    with op.batch_alter_table("nodes") as batch:
        batch.drop_column("awg_i5")
        batch.drop_column("awg_i4")
        batch.drop_column("awg_i3")
        batch.drop_column("awg_i2")
        batch.drop_column("awg_i1")
        batch.drop_column("awg_jmax")
        batch.drop_column("awg_jmin")
        batch.drop_column("awg_jc")
        batch.drop_column("post_down_json")
        batch.drop_column("pre_down_json")
        batch.drop_column("post_up_json")
        batch.drop_column("pre_up_json")

    with op.batch_alter_table("configs") as batch:
        batch.drop_column("awg_h4")
        batch.drop_column("awg_h3")
        batch.drop_column("awg_h2")
        batch.drop_column("awg_h1")
        batch.drop_column("awg_s4")
        batch.drop_column("awg_s3")
        batch.drop_column("awg_s2")
        batch.drop_column("awg_s1")
        batch.drop_column("tunnel_protocol")
