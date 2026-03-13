"""Cross-encoder reranker using BAAI/bge-reranker-large.

After the initial hybrid retrieval stage produces a shortlist of candidates,
this module provides a deep semantic re-ranking step.  A cross-encoder scores
each **(query, candidate_text)** pair jointly, which is significantly more
accurate than bi-encoder (dot-product) similarity alone.

Model precedence
----------------
1. ``sentence-transformers`` `CrossEncoder` with ``BAAI/bge-reranker-large``
2. Fallback: normalised retrieval score from the hybrid stage (no model needed)

Environment variables
---------------------
RERANKER_MODEL   HuggingFace model id  (default: BAAI/bge-reranker-large)
RERANKER_DEVICE  "cpu" | "cuda" | "mps" (default: auto-detect, same as BGE)
RERANKER_TOP_N   Max candidates to keep after reranking (default: 20)
SKIP_RERANKER    "1" / "true" → bypass reranker entirely (useful in CI/dev)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
_RERANKER_MODEL  = os.environ.get("RERANKER_MODEL",  "BAAI/bge-reranker-large")
_RERANKER_DEVICE = os.environ.get("RERANKER_DEVICE", None)  # None → auto
_RERANKER_TOP_N  = int(os.environ.get("RERANKER_TOP_N", "20"))
_SKIP_RERANKER   = os.environ.get("SKIP_RERANKER", "").lower() in ("1", "true", "yes")


# ---------------------------------------------------------------------------
# Model loader (cached per process)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _load_cross_encoder():
    """Load BAAI/bge-reranker-large cross-encoder. Returns None on failure."""
    if _SKIP_RERANKER:
        logger.info("SKIP_RERANKER=true — reranker disabled")
        return None
    try:
        from sentence_transformers import CrossEncoder  # type: ignore
        device = _RERANKER_DEVICE
        if device is None:
            try:
                import torch  # type: ignore
                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"
        logger.info("Loading cross-encoder %s on device=%s", _RERANKER_MODEL, device)
        model = CrossEncoder(_RERANKER_MODEL, device=device, max_length=512)
        logger.info("Cross-encoder loaded successfully")
        return model
    except Exception as exc:
        logger.warning(
            "Could not load cross-encoder (%s) — reranking will use retrieval score only", exc
        )
        return None


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class RerankResult:
    candidate_id:      str
    rerank_score:      float         # cross-encoder logit (higher = more relevant)
    retrieval_score:   float         # original hybrid retrieval score
    final_score:       float         # blended score used for final ranking
    matched_skills:    list[str]
    years_of_experience: float
    role:              str
    full_name:         str
    doc_id:            str
    top_section_type:  str
    top_chunk_text:    str


# ---------------------------------------------------------------------------
# Reranker
# ---------------------------------------------------------------------------

class CandidateReranker:
    """Reranks a shortlist of candidates using a cross-encoder model.

    If the cross-encoder is unavailable the retrieval score is used directly.
    """

    # Weight of cross-encoder score vs retrieval score in the final blend.
    # 0.7/0.3 gives cross-encoder strong influence while preserving keyword /
    # skill signal from the retrieval stage.
    _CE_WEIGHT = 0.70
    _RT_WEIGHT = 0.30

    def rerank(
        self,
        query_text: str,
        candidates,  # list[HybridSearchResult]
        top_n: int = _RERANKER_TOP_N,
    ) -> list[RerankResult]:
        """Return the top *top_n* candidates reranked by cross-encoder score.

        Parameters
        ----------
        query_text:
            The full JD text used as the query side of the cross-encoder.
        candidates:
            List of :class:`~app.services.hybrid_search.HybridSearchResult`.
        top_n:
            Number of results to keep.
        """
        if not candidates:
            return []

        model = _load_cross_encoder()

        if model is None:
            # No cross-encoder — sort by retrieval score
            ranked = sorted(candidates, key=lambda c: c.retrieval_score, reverse=True)
            return [
                RerankResult(
                    candidate_id      = c.candidate_id,
                    rerank_score      = c.retrieval_score,
                    retrieval_score   = c.retrieval_score,
                    final_score       = round(c.retrieval_score, 4),
                    matched_skills    = c.matched_skills,
                    years_of_experience= c.years_of_experience,
                    role              = c.role,
                    full_name         = c.full_name,
                    doc_id            = c.doc_id,
                    top_section_type  = c.top_section_type,
                    top_chunk_text    = c.top_chunk_text,
                )
                for c in ranked[:top_n]
            ]

        # Build (query, passage) pairs for cross-encoder
        pairs = [
            (query_text, self._build_passage(c))
            for c in candidates
        ]

        try:
            # predict() returns raw logits; apply_softmax=True → [0,1]
            scores = model.predict(pairs, apply_softmax=True)
            # For binary models the positive class is index 1; for single-output
            # models it's a scalar — handle both.
            ce_scores: list[float] = []
            for s in scores:
                if hasattr(s, "__len__"):
                    ce_scores.append(float(s[1]) if len(s) > 1 else float(s[0]))
                else:
                    ce_scores.append(float(s))
        except Exception as exc:
            logger.warning("Cross-encoder predict() failed (%s) — falling back to retrieval score", exc)
            ce_scores = [c.retrieval_score for c in candidates]

        # Normalise CE scores to [0, 1] if not already
        ce_max = max(ce_scores) if ce_scores else 1.0
        ce_min = min(ce_scores) if ce_scores else 0.0
        ce_range = ce_max - ce_min or 1.0
        ce_normalised = [(s - ce_min) / ce_range for s in ce_scores]

        results: list[RerankResult] = []
        for c, ce_norm, ce_raw in zip(candidates, ce_normalised, ce_scores):
            final = self._CE_WEIGHT * ce_norm + self._RT_WEIGHT * c.retrieval_score
            results.append(RerankResult(
                candidate_id        = c.candidate_id,
                rerank_score        = round(float(ce_raw), 4),
                retrieval_score     = c.retrieval_score,
                final_score         = round(final, 4),
                matched_skills      = c.matched_skills,
                years_of_experience = c.years_of_experience,
                role                = c.role,
                full_name           = c.full_name,
                doc_id              = c.doc_id,
                top_section_type    = c.top_section_type,
                top_chunk_text      = c.top_chunk_text,
            ))

        results.sort(key=lambda r: r.final_score, reverse=True)
        logger.info(
            "Reranker: %d → %d candidates (top final_score=%.3f)",
            len(results), min(top_n, len(results)),
            results[0].final_score if results else 0.0,
        )
        return results[:top_n]

    @staticmethod
    def _build_passage(candidate) -> str:
        """Concatenate the most informative candidate text fields for the cross-encoder."""
        parts: list[str] = []
        if candidate.role:
            parts.append(f"Role: {candidate.role}")
        if candidate.years_of_experience:
            parts.append(f"Experience: {candidate.years_of_experience:.1f} years")
        if candidate.matched_skills:
            parts.append(f"Matched skills: {', '.join(candidate.matched_skills[:15])}")
        if candidate.top_chunk_text:
            parts.append(candidate.top_chunk_text[:400])
        return "\n".join(parts) or "No information available"
