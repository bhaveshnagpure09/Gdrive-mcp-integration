"""Semantic retrieval pipeline — end-to-end candidate ranking.

This module is the single entry point for the advanced matching flow.

Full pipeline
-------------
1. Chunk the JD into a structured query embedding (BGE query prefix).
2. Hybrid retrieval: FAISS vector search + keyword + skill matching.
3. Cross-encoder reranking of the shortlist.
4. Weighted final scoring combining:
   * semantic similarity (from reranker)
   * skill match score
   * experience relevance
   * availability score
5. Return ranked :class:`SemanticCandidate` list.

The pipeline integrates with the existing LangGraph ``matching_scoring_node``
via a **drop-in call**: call :func:`run_semantic_pipeline` and it returns the
same dict shape expected by ``result_aggregation_node``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from app.ai.scoring import calculate_experience_score
from app.db.models.models import TeamMember
from app.services.embedding_generator import EmbeddingGenerator
from app.services.hybrid_search import HybridSearchEngine
from app.services.reranker import CandidateReranker
from app.services.vector_store import FaissVectorStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Final scoring weights (must sum to 1.0)
# ---------------------------------------------------------------------------
_W_SEMANTIC    = 0.40   # reranked semantic score
_W_SKILL       = 0.30   # structured skill match
_W_EXPERIENCE  = 0.15   # experience relevance
_W_AVAILABILITY= 0.15   # availability capacity


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class SemanticCandidate:
    """Final ranked candidate returned by the semantic pipeline."""

    team_member_id:      str
    full_name:           str
    designation:         str
    role:                str
    years_of_experience: float
    experience_months:   int

    # Scores
    semantic_score:      float      # reranked semantic similarity (0-1)
    skill_score:         float      # structured skill overlap (0-1)
    experience_score:    float      # experience relevance (0-1)
    availability_score:  float      # allocation capacity (0-1)
    final_score:         float      # weighted combination (0-1)
    match_percentage:    float      # final_score × 100

    # Detail
    matched_skills:        list[str] = field(default_factory=list)
    is_available:          bool = True
    available_capacity:    float = 100.0     # percentage
    top_section_type:      str = ""
    top_chunk_text:        str = ""
    doc_id:                str = ""
    retrieval_score:       float = 0.0
    rerank_score:          float = 0.0

    def to_dict(self) -> dict:
        return {
            "team_member_id":      self.team_member_id,
            "full_name":           self.full_name,
            "designation":         self.designation,
            "role":                self.role,
            "years_of_experience": self.years_of_experience,
            "experience_months":   self.experience_months,
            "semantic_score":      self.semantic_score,
            "skill_score":         self.skill_score,
            "experience_score":    self.experience_score,
            "availability_score":  self.availability_score,
            "final_score":         self.final_score,
            "match_percentage":    self.match_percentage,
            "matched_skills":      self.matched_skills,
            "is_available":        self.is_available,
            "available_capacity":  self.available_capacity,
            "top_section_type":    self.top_section_type,
            "top_chunk_text":      self.top_chunk_text,
            "doc_id":              self.doc_id,
            "retrieval_score":     self.retrieval_score,
            "rerank_score":        self.rerank_score,
            # Backward-compat aliases used by result_aggregation_node
            "vector_similarity":   self.semantic_score,
            "match_reasons": {
                "skills_matched":    self.matched_skills,
                "semantic_score":    self.semantic_score,
                "experience_score":  self.experience_score,
                "availability":      self.available_capacity,
            },
        }


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class SemanticRetrievalPipeline:
    """Orchestrates the full semantic retrieval and ranking pipeline."""

    def __init__(
        self,
        embedder: Optional[EmbeddingGenerator] = None,
        hybrid_engine: Optional[HybridSearchEngine] = None,
        reranker: Optional[CandidateReranker] = None,
        vector_store: Optional[FaissVectorStore] = None,
    ):
        self._embedder = embedder or EmbeddingGenerator()
        _store = vector_store or FaissVectorStore.get_instance(dim=self._embedder.dim)
        self._hybrid   = hybrid_engine or HybridSearchEngine(vector_store=_store)
        self._reranker = reranker or CandidateReranker()

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(
        self,
        *,
        jd_text: str,
        jd_title: str = "",
        jd_role: str = "",
        mandatory_skills: list[str],
        preferred_skills: list[str],
        min_experience_months: Optional[int] = None,
        max_experience_months: Optional[int] = None,
        db: Session,
        top_k: int = 20,
        availability_filter: dict[str, float] | None = None,
    ) -> list[SemanticCandidate]:
        """Run the full pipeline and return ranked candidates.

        Parameters
        ----------
        jd_text:
            Full job description free text.
        jd_title / jd_role:
            Structured fields for richer JD encoding.
        mandatory_skills / preferred_skills:
            Skill name lists from the parsed JD.
        min_experience_months / max_experience_months:
            Experience constraints from the JD.
        db:
            SQLAlchemy session for loading TeamMember metadata.
        top_k:
            Number of final candidates to return.
        availability_filter:
            Dict of {team_member_id: available_capacity_pct} pre-computed
            by the availability agent.  If None, all candidates assumed 100%
            available.
        """
        # ------------------------------------------------------------------ #
        # 1. Encode query                                                      #
        # ------------------------------------------------------------------ #
        combined_query = self._build_jd_query(jd_text, jd_title, jd_role, mandatory_skills, preferred_skills)
        query_vector = self._embedder.generate_query(combined_query)

        # ------------------------------------------------------------------ #
        # 2. Hybrid retrieval                                                  #
        # ------------------------------------------------------------------ #
        avail_ids: Optional[list[str]] = (
            list(availability_filter.keys()) if availability_filter is not None else None
        )
        hybrid_results = self._hybrid.search(
            query_vector      = query_vector,
            jd_text           = combined_query,
            mandatory_skills  = mandatory_skills,
            preferred_skills  = preferred_skills,
            top_k             = max(top_k * 5, 100),
            availability_candidate_ids = avail_ids,
        )

        if not hybrid_results:
            logger.info("Hybrid search returned no candidates")
            return []

        # ------------------------------------------------------------------ #
        # 3. Cross-encoder reranking                                          #
        # ------------------------------------------------------------------ #
        reranked = self._reranker.rerank(
            query_text = combined_query,
            candidates = hybrid_results,
            top_n      = max(top_k * 3, 60),
        )

        # ------------------------------------------------------------------ #
        # 4. Load DB metadata for reranked candidates                         #
        # ------------------------------------------------------------------ #
        candidate_ids = [r.candidate_id for r in reranked]
        members: dict[str, TeamMember] = {
            m.team_member_id: m
            for m in db.query(TeamMember).filter(
                TeamMember.team_member_id.in_(candidate_ids)
            ).all()
        }

        # ------------------------------------------------------------------ #
        # 5. Weighted final scoring                                            #
        # ------------------------------------------------------------------ #
        final: list[SemanticCandidate] = []
        for rr in reranked:
            member = members.get(rr.candidate_id)
            exp_months = (member.experience_in_months or 0) if member else int(
                (rr.years_of_experience or 0) * 12
            )
            designation = (
                (member.designation or rr.role) if member else rr.role
            )
            full_name = (
                (member.full_name or rr.full_name) if member else rr.full_name
            )

            exp_score = calculate_experience_score(
                exp_months, min_experience_months, max_experience_months
            )

            avail_pct = 100.0
            is_available = True
            if availability_filter is not None:
                avail_pct = availability_filter.get(rr.candidate_id, 0.0)
                is_available = avail_pct > 0

            avail_score = min(avail_pct / 100.0, 1.0)

            # Semantic score: blend reranker final_score with raw retrieval
            semantic = rr.final_score

            weighted_final = min(
                _W_SEMANTIC    * semantic
                + _W_SKILL       * rr.retrieval_score  # hybrid already includes skill
                + _W_EXPERIENCE  * exp_score
                + _W_AVAILABILITY* avail_score,
                1.0,
            )

            final.append(SemanticCandidate(
                team_member_id      = rr.candidate_id,
                full_name           = full_name,
                designation         = designation,
                role                = rr.role,
                years_of_experience = rr.years_of_experience,
                experience_months   = exp_months,
                semantic_score      = round(semantic, 4),
                skill_score         = round(rr.retrieval_score, 4),
                experience_score    = round(exp_score, 4),
                availability_score  = round(avail_score, 4),
                final_score         = round(weighted_final, 4),
                match_percentage    = round(weighted_final * 100, 1),
                matched_skills      = rr.matched_skills,
                is_available        = is_available,
                available_capacity  = avail_pct,
                top_section_type    = rr.top_section_type,
                top_chunk_text      = rr.top_chunk_text,
                doc_id              = rr.doc_id,
                retrieval_score     = rr.retrieval_score,
                rerank_score        = rr.rerank_score,
            ))

        final.sort(key=lambda c: c.final_score, reverse=True)
        logger.info(
            "Semantic pipeline complete: %d candidates, top match=%.1f%%",
            len(final[:top_k]),
            final[0].match_percentage if final else 0.0,
        )
        return final[:top_k]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_jd_query(
        jd_text: str,
        title: str,
        role: str,
        mandatory: list[str],
        preferred: list[str],
    ) -> str:
        parts: list[str] = []
        if title:
            parts.append(f"Job Title: {title}")
        if role:
            parts.append(f"Role: {role}")
        if mandatory:
            parts.append(f"Required Skills: {', '.join(mandatory)}")
        if preferred:
            parts.append(f"Preferred Skills: {', '.join(preferred)}")
        if jd_text:
            parts.append(f"Job Description: {jd_text[:1500]}")
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Convenience function used by matching_scoring_node
# ---------------------------------------------------------------------------

def run_semantic_pipeline(
    *,
    jd_text: str,
    jd_title: str = "",
    jd_role: str = "",
    mandatory_skills: list[str],
    preferred_skills: list[str],
    min_experience_months: Optional[int] = None,
    max_experience_months: Optional[int] = None,
    db: Session,
    top_k: int = 20,
    availability_filter: dict[str, float] | None = None,
) -> list[dict]:
    """Run the semantic pipeline and return results as plain dicts.

    The dict shape is identical to what the existing ``result_aggregation_node``
    expects, plus additional semantic fields.
    """
    pipeline = SemanticRetrievalPipeline()
    candidates = pipeline.run(
        jd_text               = jd_text,
        jd_title              = jd_title,
        jd_role               = jd_role,
        mandatory_skills      = mandatory_skills,
        preferred_skills      = preferred_skills,
        min_experience_months = min_experience_months,
        max_experience_months = max_experience_months,
        db                    = db,
        top_k                 = top_k,
        availability_filter   = availability_filter,
    )
    return [c.to_dict() for c in candidates]
