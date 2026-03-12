"""Repository for storing and querying team member vector embeddings."""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models.models import TeamMemberEmbedding

logger = logging.getLogger(__name__)


class EmbeddingRepository:
    """Handles persistence of team member embeddings in PostgreSQL."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def upsert(
        self,
        *,
        team_member_id: str,
        embedding: list[float],
        profile_text: str,
        metadata: Optional[dict] = None,
    ) -> tuple[bool, TeamMemberEmbedding]:
        """Insert or replace the embedding for a team member.

        Args:
            team_member_id: The team member's primary key.
            embedding: Float vector produced by the embedding model.
            profile_text: Full profile text used to generate the embedding.
            metadata: JSON-serialisable dict of structured attributes.

        Returns:
            Tuple of (was_created, record).
        """
        existing: Optional[TeamMemberEmbedding] = (
            self.db.query(TeamMemberEmbedding)
            .filter(TeamMemberEmbedding.team_member_id == team_member_id)
            .first()
        )

        # Serialise vector as JSON string for the SQLite-compatible column.
        # In production PostgreSQL the Alembic migration creates the real
        # vector(300) column; the ORM model maps it identically.
        embedding_str = json.dumps(embedding)

        if existing:
            existing.embedding = embedding_str
            existing.profile_text = profile_text
            existing.metadata_json = metadata or {}
            existing.created_at = datetime.now(timezone.utc)
            self.db.flush()
            logger.info("Updated embedding", extra={"team_member_id": team_member_id})
            return False, existing

        record = TeamMemberEmbedding(
            team_member_id=team_member_id,
            embedding=embedding_str,
            profile_text=profile_text,
            metadata_json=metadata or {},
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(record)
        self.db.flush()
        logger.info("Inserted new embedding", extra={"team_member_id": team_member_id})
        return True, record

    def get_by_team_member(self, team_member_id: str) -> Optional[TeamMemberEmbedding]:
        """Return the embedding record for a team member, or None."""
        return (
            self.db.query(TeamMemberEmbedding)
            .filter(TeamMemberEmbedding.team_member_id == team_member_id)
            .first()
        )

    def get_by_source_doc_id(self, doc_id: str) -> Optional[TeamMemberEmbedding]:
        """Return the embedding record whose metadata_json.source_doc_id matches, or None.

        Uses a parameterised raw SQL snippet for the PostgreSQL ->> operator so
        the query works regardless of SQLAlchemy ORM version.
        """
        from sqlalchemy import text  # noqa: PLC0415
        return (
            self.db.query(TeamMemberEmbedding)
            .filter(
                text("metadata_json->>'source_doc_id' = :doc_id")
            )
            .params(doc_id=doc_id)
            .first()
        )

    def find_similar_by_vector(
        self,
        query_vector: list[float],
        top_k: int = 20,
    ) -> list[tuple[str, float]]:
        """Find team members with embeddings most similar to query_vector.

        Uses pgvector cosine distance (<=> operator).

        Args:
            query_vector: The query embedding (768-dim).
            top_k: Maximum number of results to return.

        Returns:
            List of (team_member_id, cosine_similarity) sorted by similarity desc.
            cosine_similarity is in [0.0, 1.0] where 1.0 = identical.
        """
        # Embed vector as a PostgreSQL literal; query_vector is internal data (safe)
        vec_literal = "[" + ",".join(f"{v:.8f}" for v in query_vector) + "]"
        sql = text(f"""
            SELECT team_member_id,
                   1 - (embedding <=> '{vec_literal}'::vector) AS similarity
            FROM team_member_embeddings
            ORDER BY embedding <=> '{vec_literal}'::vector
            LIMIT :k
        """)
        try:
            rows = self.db.execute(sql, {"k": top_k}).fetchall()
            return [(row[0], float(row[1])) for row in rows]
        except Exception as exc:
            logger.warning(
                "Vector similarity search failed (non-pgvector DB?): %s", exc
            )
            return []
