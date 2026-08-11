"""Read-only Core table definitions mirroring telemetry-db's schema
(services/telemetry/src/telemetry/models.py) — used exclusively by
backfill.py's read-only queries against `Settings.telemetry_db_url`.

Deliberately plain SQLAlchemy Core `Table`s on their own `MetaData`, not
ORM models on this service's `Base` (telemetry_aggregates.db.Base): this
service does not own telemetry-db's schema, doesn't migrate it, and must
never have `alembic revision --autogenerate` here pick these tables up as
if they belonged to `telemetry-aggregates-db`. Only the columns backfill.py
actually reads are declared.
"""

from sqlalchemy import Column, DateTime, MetaData, Numeric, Table, Uuid

metadata = MetaData()

temperature_readings = Table(
    "temperature_readings",
    metadata,
    Column("store_id", Uuid, nullable=False),
    Column("temperature", Numeric, nullable=False),
    Column("recorded_at", DateTime(timezone=True), nullable=False),
)

store_product_thresholds = Table(
    "store_product_thresholds",
    metadata,
    Column("store_id", Uuid, primary_key=True),
    Column("product_id", Uuid, primary_key=True),
    # STR-148: when this {store, product} pairing started being tracked —
    # never updated after insert (unlike updated_at, which also bumps on
    # ProductThresholdUpdated). backfill.py uses this to avoid folding a
    # store's pre-existing readings into a product's aggregate before that
    # product was ever associated with the store.
    Column("tracked_since", DateTime(timezone=True), nullable=False),
)
