"""Store restorable MQTT node credentials.

Revision ID: 0003_mqtt_password
Revises: 0002_tunnel_protocol_awg
Create Date: 2026-05-15
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection


revision = "0003_mqtt_password"
down_revision = "0002_tunnel_protocol_awg"
branch_labels = None
depends_on = None


def _existing_columns(connection: Connection, table_name: str) -> set[str]:
    return {str(column["name"]) for column in sa.inspect(connection).get_columns(table_name)}


def upgrade() -> None:
    if "mqtt_password" in _existing_columns(op.get_bind(), "node_client_state"):
        return
    with op.batch_alter_table("node_client_state") as batch:
        batch.add_column(sa.Column("mqtt_password", sa.String(), nullable=False, server_default=""))


def downgrade() -> None:
    with op.batch_alter_table("node_client_state") as batch:
        batch.drop_column("mqtt_password")
