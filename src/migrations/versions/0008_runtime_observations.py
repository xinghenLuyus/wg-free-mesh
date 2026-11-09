"""Latest bounded runtime observation per endpoint."""

from alembic import op
from app.data.schema import node_runtime_observations

revision = "0008_runtime_observations"
down_revision = "0007_awg_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    import sqlalchemy as sa

    if "wg_observed_at" not in {
        c["name"] for c in sa.inspect(op.get_bind()).get_columns("endpoint_runtime_status")
    }:
        op.add_column("endpoint_runtime_status", sa.Column("wg_observed_at", sa.String()))
    node_runtime_observations.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    node_runtime_observations.drop(op.get_bind(), checkfirst=True)
    with op.batch_alter_table("endpoint_runtime_status") as batch:
        batch.drop_column("wg_observed_at")
