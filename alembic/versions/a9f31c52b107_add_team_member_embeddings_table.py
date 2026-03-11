"""add_team_member_embeddings_table

Revision ID: a9f31c52b107
Revises: e8a217c84204
Create Date: 2026-03-11 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a9f31c52b107"
down_revision: Union[str, None] = "e8a217c84204"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Embedding dimension for embedding-gemma-300m
EMBEDDING_DIM = 300


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create team_member_embeddings table
    op.execute(
        f"""
        CREATE TABLE team_member_embeddings (
            team_member_id  VARCHAR(50) PRIMARY KEY
                            REFERENCES team_member(team_member_id) ON DELETE CASCADE,
            embedding       vector({EMBEDDING_DIM}) NOT NULL,
            profile_text    TEXT NOT NULL,
            metadata_json   JSONB,
            created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Create an IVFFlat index for approximate nearest-neighbour search
    op.execute(
        """
        CREATE INDEX ix_team_member_embeddings_vector
        ON team_member_embeddings
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS team_member_embeddings")
