"""drop unused resolved value from requests status check constraint

Revision ID: 49fd33dc99c3
Revises: 880cf8adb7a1
Create Date: 2026-07-10 18:24:06.959700

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '49fd33dc99c3'
down_revision: Union[str, Sequence[str], None] = '880cf8adb7a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


STATUS_VALUES = ("open", "in-progress", "closed", "approved", "rejected")
OLD_STATUS_VALUES = ("open", "in-progress", "resolved", "closed", "approved", "rejected")


def upgrade() -> None:
    """Upgrade schema."""
    # "resolved" was never reachable through any code path — no route ever
    # sets it — so it's dropped here to match models.py rather than left in
    # the DB as a value the app can never actually produce.
    op.drop_constraint("requests_status_check", "requests", type_="check")
    op.create_check_constraint(
        "requests_status_check",
        "requests",
        "status IN (" + ", ".join(f"'{s}'" for s in STATUS_VALUES) + ")",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("requests_status_check", "requests", type_="check")
    op.create_check_constraint(
        "requests_status_check",
        "requests",
        "status IN (" + ", ".join(f"'{s}'" for s in OLD_STATUS_VALUES) + ")",
    )
