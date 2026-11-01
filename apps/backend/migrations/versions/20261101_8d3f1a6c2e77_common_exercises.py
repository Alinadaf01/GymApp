"""common gym exercises for the dictionary

Revision ID: 8d3f1a6c2e77
Revises: 5b7e2c9d4a10
Create Date: 2026-11-01 16:00:00

"""
import json
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# Standard Persian gym vocabulary (also fed to Whisper as a spelling hint).
# Added only if the name is missing, so the coach's own edits are kept.
ENTRIES = [
    ("پرس بالا سینه هالتر", ["بالا سینه هالتر", "پرس بالاسینه هالتر"]),
    ("پرس زیر سینه هالتر", ["زیر سینه هالتر"]),
    ("پرس زیر سینه دمبل", ["زیر سینه دمبل"]),
    ("قفسه سینه دمبل", ["قفسه دمبل"]),
    ("پک دک", ["دستگاه پک دک"]),
    ("دیپ", ["پارالل"]),
    ("شنا سوئدی", ["شنا"]),
    ("بارفیکس", []),
    ("زیر بغل سیم‌کش", ["لت از جلو"]),
    ("زیر بغل هالتر خم", ["هالتر خم", "رویینگ هالتر"]),
    ("زیر بغل دمبل تک خم", ["دمبل تک خم"]),
    ("پول اور", ["پلاور"]),
    ("ددلیفت", ["ددلیفت هالتر"]),
    ("پرس سرشانه هالتر", ["سرشانه هالتر"]),
    ("پرس سرشانه دمبل", ["سرشانه دمبل"]),
    ("نشر جانب دمبل", ["نشر جانب"]),
    ("نشر جلو دمبل", ["نشر جلو"]),
    ("نشر خم دمبل", ["نشر خم"]),
    ("فیس پول", []),
    ("شراگ", ["شراگ دمبل", "شراگ هالتر"]),
    ("جلو بازو هالتر", ["جلوبازو هالتر"]),
    ("جلو بازو لاری", ["جلوبازو لاری"]),
    ("جلو بازو تمرکزی", ["جلوبازو تمرکزی"]),
    ("پشت بازو سیم‌کش", ["پشت‌بازو سیم‌کش", "پشت بازو طناب"]),
    ("پشت بازو هالتر خوابیده", ["پشت بازو خوابیده"]),
    ("پشت بازو دمبل جفت", ["پشت بازو دمبل"]),
    ("پشت بازو دیپ", []),
    ("جلو پا دستگاه", ["جلو پا", "جلوپا"]),
    ("پشت پا دستگاه", ["پشت پا", "پشت‌پا"]),
    ("لانج", ["لانج دمبل"]),
    ("اسکوات هاک", ["هاک"]),
    ("اسکوات اسمیت", []),
    ("ددلیفت رومانیایی", ["رومانیایی"]),
    ("ساق پا ایستاده", ["ساق ایستاده"]),
    ("ساق پا نشسته", ["ساق نشسته"]),
    ("کرانچ", ["کرانچ شکم"]),
    ("پلانک", []),
    ("زیر شکم خلبانی", ["زیر شکم", "خلبانی"]),
]

revision: str = "8d3f1a6c2e77"
down_revision: Union[str, Sequence[str], None] = "5b7e2c9d4a10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    for name, aliases in ENTRIES:
        if conn.execute(sa.text("SELECT 1 FROM exercise_dictionary WHERE canonical_name = :n"), {"n": name}).first():
            continue
        conn.execute(
            sa.text("INSERT INTO exercise_dictionary (id, canonical_name, aliases) "
                    "VALUES (:id, :name, CAST(:aliases AS jsonb))"),
            {"id": uuid.uuid4(), "name": name, "aliases": json.dumps(aliases, ensure_ascii=False)},
        )


def downgrade() -> None:
    """Dictionary rows are kept: the coach may have edited them."""
