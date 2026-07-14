"""add cancelled status to requests status check constraint

Revision ID: 35378dad8280
Revises: b84a3e05b655
Create Date: 2026-07-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '35378dad8280'
down_revision: Union[str, Sequence[str], None] = 'b84a3e05b655'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_STATUS_VALUES = ("open", "in-progress", "closed", "approved", "rejected")
NEW_STATUS_VALUES = ("open", "in-progress", "closed", "approved", "rejected", "cancelled")


def upgrade() -> None:
    """Upgrade schema."""
    # Lets a requester withdraw their own request via PATCH /requests/{id}/cancel
    # (request_service.cancel_request_for_user), distinct from "closed" so a
    # requester-initiated cancellation isn't conflated with any other closure reason.
    op.drop_constraint("requests_status_check", "requests", type_="check")
    op.create_check_constraint(
        "requests_status_check",
        "requests",
        "status IN (" + ", ".join(f"'{s}'" for s in NEW_STATUS_VALUES) + ")",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("requests_status_check", "requests", type_="check")
    op.create_check_constraint(
        "requests_status_check",
        "requests",
        "status IN (" + ", ".join(f"'{s}'" for s in OLD_STATUS_VALUES) + ")",
    )
