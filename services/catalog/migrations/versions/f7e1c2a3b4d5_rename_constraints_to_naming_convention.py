"""rename constraints to the naming convention

Revision ID: f7e1c2a3b4d5
Revises: f1a2b3c4d5e6
Create Date: 2026-09-03 13:00:00.000000

Converge the constraint names on a database created before
db.NAMING_CONVENTION existed (its constraints carry PostgreSQL's own
defaults: `categories_pkey`, `products_category_id_fkey`, ...) onto the names
SQLAlchemy's metadata now generates.

Conditional on the old name still being present: a database created *after*
the convention was added already has the target names (Alembic's
`op.create_table` picks the convention up from target_metadata), so there is
nothing to rename there. Runtime behaviour is unchanged either way.
`alembic_version_pkc` is left alone -- Alembic owns it.
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'f7e1c2a3b4d5'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (table, legacy name, convention name)
_RENAMES: list[tuple[str, str, str]] = [
    ("categories", "categories_pkey", "pk_categories"),
    ("categories", "categories_name_key", "uq_categories_name"),
    ("products", "products_pkey", "pk_products"),
    ("products", "products_category_id_fkey", "fk_products_category_id_categories"),
    ("product_images", "product_images_pkey", "pk_product_images"),
    ("product_images", "product_images_product_id_fkey", "fk_product_images_product_id_products"),
    ("outbox_events", "outbox_events_pkey", "pk_outbox_events"),
]

_RENAME_IF_PRESENT = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = '{src}' AND conrelid = '{table}'::regclass) THEN
        ALTER TABLE "{table}" RENAME CONSTRAINT "{src}" TO "{dst}";
    END IF;
END $$;
"""


def _rename(pairs: list[tuple[str, str, str]]) -> None:
    for table, src, dst in pairs:
        op.execute(_RENAME_IF_PRESENT.format(table=table, src=src, dst=dst))


def upgrade() -> None:
    _rename([(table, legacy, convention) for table, legacy, convention in _RENAMES])


def downgrade() -> None:
    _rename([(table, convention, legacy) for table, legacy, convention in _RENAMES])
