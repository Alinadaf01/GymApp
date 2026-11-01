"""more exercise dictionary entries (from the first real voices)

Revision ID: 5b7e2c9d4a10
Revises: 00ad1eeed67c
Create Date: 2026-11-01 14:00:00

"""
import json
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# Real exercises the coach used in the first voices. Added only if missing,
# so names/aliases the coach already edited in the panel are left alone.
ENTRIES = [
    ("پرس سینه دمبل", ["پرس سینه با دمبل"]),
    ("جلو بازو چکشی", ["جلوبازو چکشی", "جلو بازو دمبل چکشی", "جلو بازو چکشی دمبل"]),
]

revision: str = "5b7e2c9d4a10"
down_revision: Union[str, Sequence[str], None] = "00ad1eeed67c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    for name, aliases in ENTRIES:
        exists = conn.execute(
            sa.text("SELECT 1 FROM exercise_dictionary WHERE canonical_name = :name"), {"name": name}
        ).first()
        if not exists:
            conn.execute(
                sa.text("INSERT INTO exercise_dictionary (id, canonical_name, aliases) "
                        "VALUES (:id, :name, CAST(:aliases AS jsonb))"),
                {"id": uuid.uuid4(), "name": name, "aliases": json.dumps(aliases, ensure_ascii=False)},
            )


def downgrade() -> None:
    """Dictionary rows are kept: the coach may have edited them."""
