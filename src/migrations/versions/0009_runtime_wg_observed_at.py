"""Ensure versioned databases have the WG observation timestamp."""

import sqlalchemy as sa
from alembic import op

revision = "0009_runtime_wg_observed_at"
down_revision = "0008_runtime_observations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = sa.inspect(op.get_bind()).get_columns("endpoint_runtime_status")
    if "wg_observed_at" not in {column["name"] for column in columns}:
        op.add_column("endpoint_runtime_status", sa.Column("wg_observed_at", sa.String()))


def downgrade() -> None:
    # This column is also part of the 0008 contract. Repairing its absence must
    # not remove an existing column or its data when returning to that revision.
    pass
