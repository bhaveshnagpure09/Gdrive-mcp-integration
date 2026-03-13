"""add_resume_chunk_embeddings

Revision ID: a1b2c3d4e5f6
Revises: e8a217c84204
Create Date: 2026-03-13 00:00:00.000000

Adds the resume_chunk_embeddings table which stores per-section embeddings
for advanced semantic retrieval (BGE-large-en-v1.5 + FAISS + cross-encoder).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "e8a217c84204"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "resume_chunk_embeddings",
        sa.Column("id",             sa.Integer(),     primary_key=True, autoincrement=True),
        sa.Column("team_member_id", sa.String(50),    sa.ForeignKey("team_member.team_member_id"),
                  nullable=False),
        sa.Column("doc_id",         sa.String(255),   nullable=True),
        sa.Column("section_type",   sa.String(50),    nullable=False),
        sa.Column("chunk_text",     sa.Text(),        nullable=False),
        # Stored as a TEXT JSON array; can be migrated to vector(1024) once pg vector is confirmed
        sa.Column("embedding",      sa.Text(),        nullable=True),
        sa.Column("faiss_id",       sa.Integer(),     nullable=True),
        sa.Column("skills",         JSONB(),          nullable=True),
        sa.Column("years_of_experience", sa.Numeric(5, 1), nullable=True),
        sa.Column("role",           sa.String(200),   nullable=True),
        sa.Column("full_name",      sa.String(200),   nullable=True),
        sa.Column("metadata_json",  JSONB(),          nullable=True),
        sa.Column("created_at",     sa.DateTime(),    nullable=False,
                  server_default=sa.text("NOW()")),
    )

    # Indexes for fast candidate and doc filtering
    op.create_index(
        "ix_resume_chunk_embeddings_team_member_id",
        "resume_chunk_embeddings",
        ["team_member_id"],
    )
    op.create_index(
        "ix_resume_chunk_embeddings_doc_id",
        "resume_chunk_embeddings",
        ["doc_id"],
    )
    op.create_index(
        "ix_resume_chunk_embeddings_section_type",
        "resume_chunk_embeddings",
        ["section_type"],
    )
    op.create_index(
        "ix_resume_chunk_embeddings_faiss_id",
        "resume_chunk_embeddings",
        ["faiss_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_resume_chunk_embeddings_faiss_id",       table_name="resume_chunk_embeddings")
    op.drop_index("ix_resume_chunk_embeddings_section_type",   table_name="resume_chunk_embeddings")
    op.drop_index("ix_resume_chunk_embeddings_doc_id",         table_name="resume_chunk_embeddings")
    op.drop_index("ix_resume_chunk_embeddings_team_member_id", table_name="resume_chunk_embeddings")
    op.drop_table("resume_chunk_embeddings")
