"""make timestamp columns timezone-aware

Revision ID: 219b7e533423
Revises: 35378dad8280
Create Date: 2026-07-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '219b7e533423'
down_revision: Union[str, Sequence[str], None] = '35378dad8280'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (table, column) pairs populated via server_default=func.now() as naive
# "timestamp without time zone" columns. The DB session's timezone has always
# been Etc/UTC (confirmed via SHOW TIMEZONE), so the existing naive values
# are already UTC wall-clock readings — reinterpreting them via
# `AT TIME ZONE 'UTC'` is lossless, just adds the missing tz tag. Without it,
# psycopg2 returns naive datetimes, which Pydantic serializes with no UTC
# offset/'Z' suffix, so the browser's `new Date(...)` misreads them as local
# time instead of UTC — shifting every displayed timestamp by the viewer's
# UTC offset (this is what surfaced as request timestamps showing hours off).
COLUMNS = [
    ("requests", "created_at"),
    ("reviews", "reviewed_at"),
    ("comments", "created_at"),
]


def upgrade() -> None:
    """Upgrade schema."""
    for table, column in COLUMNS:
        op.execute(
            f'ALTER TABLE "{table}" ALTER COLUMN "{column}" '
            f"TYPE timestamptz USING \"{column}\" AT TIME ZONE 'UTC'"
        )


def downgrade() -> None:
    """Downgrade schema."""
    for table, column in COLUMNS:
        op.execute(
            f'ALTER TABLE "{table}" ALTER COLUMN "{column}" '
            f"TYPE timestamp USING \"{column}\" AT TIME ZONE 'UTC'"
        )
