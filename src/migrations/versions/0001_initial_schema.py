"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-14
"""

from __future__ import annotations

from alembic import op

from app.data.schema import metadata


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    metadata.drop_all(bind=op.get_bind())

