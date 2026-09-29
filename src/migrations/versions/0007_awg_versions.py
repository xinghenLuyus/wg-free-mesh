"""Separate AmneziaWG protocol and version, preserving existing AWG 2.0 configs."""
from alembic import op
import sqlalchemy as sa

revision = "0007_awg_versions"
down_revision = "0006_mcp_access"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name, columns in (
        ("configs", [sa.Column("awg_version", sa.String()), sa.Column("awg_options_json", sa.Text(), nullable=False, server_default="{}")]),
        ("nodes", [sa.Column("awg_options_json", sa.Text(), nullable=False, server_default="{}")]),
    ):
        existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns(name)}
        with op.batch_alter_table(name) as batch:
            for column in columns:
                if column.name not in existing:
                    batch.add_column(column)
    op.execute("UPDATE configs SET tunnel_protocol='amneziawg', awg_version='2.0' WHERE tunnel_protocol='amneziawg_2'")
    op.execute("UPDATE configs SET awg_version='2.0' WHERE tunnel_protocol='amneziawg' AND awg_version IS NULL")


def downgrade() -> None:
    # Newer AWG configs cannot safely be relabeled as AWG 2.0.
    connection = op.get_bind()
    if connection.execute(sa.text("SELECT id FROM configs WHERE awg_version IN ('1.5', '3.1') LIMIT 1")).first():
        raise RuntimeError("Convert AWG configs to 2.0 before downgrading")
    op.execute("UPDATE configs SET tunnel_protocol='amneziawg_2' WHERE tunnel_protocol='amneziawg'")
    with op.batch_alter_table("configs") as batch:
        batch.drop_column("awg_version")
        batch.drop_column("awg_options_json")
    with op.batch_alter_table("nodes") as batch:
        batch.drop_column("awg_options_json")
