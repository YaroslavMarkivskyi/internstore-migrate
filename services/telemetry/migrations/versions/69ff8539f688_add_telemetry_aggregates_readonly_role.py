"""add telemetry_aggregates_readonly role (STR-148)

Revision ID: 69ff8539f688
Revises: 9716313213d7
Create Date: 2026-08-11 00:00:00.000000

Found during STR-148's live verification of telemetry-aggregates: the
backfill job's TELEMETRY_DB_URL was documented as "read-only in intent"
(services/telemetry-aggregates/README.md) but actually connected as the
full read-write `telemetry` user — nothing had ever created a real
read-only role. This migration is telemetry-db's side of the fix: a
dedicated role that can only SELECT from the two tables backfill.py
reads (`temperature_readings`, `store_product_thresholds`), nothing else,
no writes. docker-compose.yml / k8s's telemetry-aggregates secret are
updated separately to connect as this role instead of `telemetry`.

DEV-ONLY plaintext password, same trade-off as every other credential in
this stack (see docker-compose.yml's existing POSTGRES_PASSWORD values).
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '69ff8539f688'
down_revision: Union[str, None] = '9716313213d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ROLE = "telemetry_readonly"


def upgrade() -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{ROLE}') THEN
                CREATE ROLE {ROLE} LOGIN PASSWORD 'telemetry-readonly';
            END IF;
        END
        $$;
        """
    )
    op.execute(f"GRANT CONNECT ON DATABASE telemetry TO {ROLE}")
    op.execute(f"GRANT USAGE ON SCHEMA public TO {ROLE}")
    op.execute(f"GRANT SELECT ON temperature_readings, store_product_thresholds TO {ROLE}")
    # No default-privileges grant on future tables — deliberately scoped to
    # exactly the two tables backfill.py reads today, not "everything this
    # schema ever grows." A future table this role should also read needs
    # its own explicit GRANT in a future migration.


def downgrade() -> None:
    op.execute(f"REVOKE SELECT ON temperature_readings, store_product_thresholds FROM {ROLE}")
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {ROLE}")
    op.execute(f"REVOKE CONNECT ON DATABASE telemetry FROM {ROLE}")
    op.execute(f"DROP ROLE IF EXISTS {ROLE}")
