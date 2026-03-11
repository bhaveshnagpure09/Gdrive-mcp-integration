"""resize_embedding_vector_to_768

Revision ID: b1c2d3e4f506
Revises: a9f31c52b107
Create Date: 2026-03-11 00:00:00.000000

Switches the embedding column from vector(300) (embedding-gemma-300m)
to vector(768) (nomic-embed-text), and rebuilds the IVFFlat index.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "b1c2d3e4f506"
down_revision: Union[str, None] = "a9f31c52b107"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the existing IVFFlat index before altering column type
    op.execute("DROP INDEX IF EXISTS ix_team_member_embeddings_vector")

    # Truncate existing rows (dimension change requires clean data)
    op.execute("TRUNCATE TABLE team_member_embeddings")

    # Alter embedding column from vector(300) to vector(768)
    op.execute(
        "ALTER TABLE team_member_embeddings "
        "ALTER COLUMN embedding TYPE vector(768) USING embedding::text::vector(768)"
    )

    # Recreate IVFFlat index for 768-dim cosine similarity search
    op.execute(
        """
        CREATE INDEX ix_team_member_embeddings_vector
        ON team_member_embeddings
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_team_member_embeddings_vector")
    op.execute("TRUNCATE TABLE team_member_embeddings")
    op.execute(
        "ALTER TABLE team_member_embeddings "
        "ALTER COLUMN embedding TYPE vector(300) USING embedding::text::vector(300)"
    )
    op.execute(
        """
        CREATE INDEX ix_team_member_embeddings_vector
        ON team_member_embeddings
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
        """
    )
