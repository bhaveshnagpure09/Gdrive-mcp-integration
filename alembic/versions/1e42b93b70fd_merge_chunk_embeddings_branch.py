"""merge_chunk_embeddings_branch

Revision ID: 1e42b93b70fd
Revises: a1b2c3d4e5f6, b1c2d3e4f506
Create Date: 2026-03-13 12:17:39.672657

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1e42b93b70fd'
down_revision: Union[str, None] = ('a1b2c3d4e5f6', 'b1c2d3e4f506')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
