"""Hybrid search engine: semantic vector + keyword + structured skill matching.

Retrieval pipeline
------------------
1. **Vector retrieval** — query the FAISS store with the JD embedding and
   pull the top-K candidate chunks.
2. **Keyword matching** — score the same chunks against JD keywords using a
   lightweight token-overlap (BM-25-style) measure.
3. **Skill matching** — exact / fuzzy skill ID and name overlap against the
   mandatory / preferred skill lists.
4. **Score fusion** — weighted combination of the three signals produces a
   *retrieval score* per (candidate, section) pair.
5. **Candidate aggregation** — merge section-level scores into a single
   per-candidate retrieval score (max-pool over sections of the same type,
   mean over section types).

The result is a list of :class:`HybridSearchResult` objects ordered by
retrieval score descending.  These are then passed to the cross-encoder
reranker (:mod:`app.services.reranker`) for a final fine-grained re-ranking.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from app.services.vector_store import FaissVectorStore, VectorSearchResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration — fusion weights (must sum to 1)
# ---------------------------------------------------------------------------
_VECTOR_WEIGHT  = float(0.50)     # semantic vector similarity
_KEYWORD_WEIGHT = float(0.25)     # keyword / token overlap
_SKILL_WEIGHT   = float(0.25)     # exact / fuzzy skill match

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class HybridSearchResult:
    """Aggregated per-candidate result from the hybrid retrieval stage."""

    candidate_id:        str
    retrieval_score:     float               # fused score (0-1)
    vector_score:        float = 0.0         # average semantic similarity
    keyword_score:       float = 0.0         # keyword match ratio
    skill_match_score:   float = 0.0         # skill overlap score
    matched_skills:      list[str] = field(default_factory=list)
    top_section_type:    str = ""            # section with highest vector score
    top_chunk_text:      str = ""            # text of the best-scoring chunk
    years_of_experience: float = 0.0
    role:                str = ""
    full_name:           str = ""
    doc_id:              str = ""
    raw_chunk_score_map: dict[str, float] = field(default_factory=dict)  # section_type → score


# ---------------------------------------------------------------------------
# Keyword scorer (lightweight BM25/TF-IDF approximation)
# ---------------------------------------------------------------------------

def _tokenise(text: str) -> set[str]:
    """Lower-case alpha-numeric tokens, length ≥ 2."""
    return {t for t in re.findall(r"[a-z0-9\+#\.]+", text.lower()) if len(t) >= 2}


def _keyword_score(chunk_text: str, jd_tokens: set[str]) -> float:
    """Token overlap of chunk against JD keyword set (Jaccard-like ratio)."""
    if not jd_tokens:
        return 0.0
    chunk_tokens = _tokenise(chunk_text)
    overlap = len(jd_tokens & chunk_tokens)
    return min(overlap / len(jd_tokens), 1.0)


# ---------------------------------------------------------------------------
# Skill scorer
# ---------------------------------------------------------------------------

def _skill_score(
    candidate_skills: list[str],
    mandatory_skill_names: list[str],
    preferred_skill_names: list[str],
) -> tuple[float, list[str]]:
    """Return (score, matched_skill_names).

    Score = 0.7 × mandatory_fraction + 0.3 × preferred_fraction.
    Matching is case-insensitive substring (e.g. "python" matches "Python 3").
    """
    cand_lower = [s.lower().strip() for s in candidate_skills]

    def _match(jd_skill: str) -> bool:
        jd_l = jd_skill.lower().strip()
        return any(jd_l in c or c in jd_l for c in cand_lower)

    matched_mandatory = [s for s in mandatory_skill_names if _match(s)]
    matched_preferred = [s for s in preferred_skill_names if _match(s)]

    mand_score = len(matched_mandatory) / len(mandatory_skill_names) if mandatory_skill_names else 1.0
    pref_score = len(matched_preferred) / len(preferred_skill_names) if preferred_skill_names else 1.0
    score = min(0.7 * mand_score + 0.3 * pref_score, 1.0)

    return score, matched_mandatory + matched_preferred


# ---------------------------------------------------------------------------
# Main hybrid search
# ---------------------------------------------------------------------------

class HybridSearchEngine:
    """Combines FAISS vector search, keyword matching, and skill matching."""

    def __init__(
        self,
        vector_store: Optional[FaissVectorStore] = None,
        vector_weight: float = _VECTOR_WEIGHT,
        keyword_weight: float = _KEYWORD_WEIGHT,
        skill_weight: float = _SKILL_WEIGHT,
    ):
        self._store          = vector_store or FaissVectorStore.get_instance()
        self._vector_weight  = vector_weight
        self._keyword_weight = keyword_weight
        self._skill_weight   = skill_weight

    def search(
        self,
        query_vector: list[float],
        jd_text: str,
        mandatory_skills: list[str],
        preferred_skills: list[str],
        top_k: int = 50,
        min_retrieval_score: float = 0.10,
        availability_candidate_ids: Optional[list[str]] = None,
    ) -> list[HybridSearchResult]:
        """Run the hybrid retrieval and return ranked candidates.

        Parameters
        ----------
        query_vector:
            Embedding of the full JD text (from :class:`EmbeddingGenerator`).
        jd_text:
            Raw JD text used for keyword matching.
        mandatory_skills / preferred_skills:
            Skill name lists from the parsed JD for structured matching.
        top_k:
            Maximum number of candidates to return.
        min_retrieval_score:
            Drop candidates whose fused score is below this threshold.
        availability_candidate_ids:
            When provided, restrict FAISS search to these candidate IDs only
            (pre-filter for availability).
        """
        # 1. Vector retrieval — fetch more raw chunks so aggregation has signal
        raw_results: list[VectorSearchResult] = self._store.search(
            query_vector=query_vector,
            top_k=top_k * 10,  # over-fetch; we aggregate + filter below
            filter_candidate_ids=availability_candidate_ids,
        )

        if not raw_results:
            logger.info("FAISS vector search returned 0 results")
            return []

        # 2. Keyword prep
        jd_tokens = _tokenise(jd_text or " ".join(mandatory_skills + preferred_skills))

        # 3. Aggregate chunk-level scores into per-candidate buckets
        #    bucket: candidate_id → list of (section_type, vec_score, kw_score, skill_score, meta)
        buckets: dict[str, list[tuple[str, float, float, float, float, str, object]]] = defaultdict(list)

        for r in raw_results:
            chunk_text = r.metadata.raw_text or ""
            candidate_skills = r.metadata.skills or []

            vec_s  = max(float(r.score), 0.0)
            kw_s   = _keyword_score(chunk_text, jd_tokens)
            sk_s, matched = _skill_score(candidate_skills, mandatory_skills, preferred_skills)

            buckets[r.candidate_id].append((
                r.section_type,
                vec_s,
                kw_s,
                sk_s,
                r.metadata.years_of_experience or 0.0,
                chunk_text,
                r.metadata,
                matched,
            ))

        # 4. Per-candidate aggregation
        results: list[HybridSearchResult] = []
        for cand_id, sections in buckets.items():
            # Group by section_type; take max vec/kw/skill score per section
            sec_map: dict[str, tuple[float, float, float, str, object, list]] = {}
            for sec_type, vec_s, kw_s, sk_s, yoe, text, meta, matched in sections:
                if sec_type not in sec_map or vec_s > sec_map[sec_type][0]:
                    sec_map[sec_type] = (vec_s, kw_s, sk_s, text, meta, matched)

            # Mean over section types
            avg_vec = sum(v[0] for v in sec_map.values()) / len(sec_map)
            avg_kw  = sum(v[1] for v in sec_map.values()) / len(sec_map)
            # Use max skill score across sections (skills may appear in many sections)
            max_sk, best_matched = max(
                ((v[2], v[5]) for v in sec_map.values()), key=lambda x: x[0]
            )

            fused = (
                self._vector_weight  * avg_vec
                + self._keyword_weight * avg_kw
                + self._skill_weight   * max_sk
            )

            if fused < min_retrieval_score:
                continue

            # Identify best section for snippet
            best_sec = max(sec_map.items(), key=lambda kv: kv[1][0])
            best_sec_type = best_sec[0]
            _, _, _, best_text, best_meta, _ = best_sec[1]

            results.append(HybridSearchResult(
                candidate_id        = cand_id,
                retrieval_score     = round(fused, 4),
                vector_score        = round(avg_vec, 4),
                keyword_score       = round(avg_kw, 4),
                skill_match_score   = round(max_sk, 4),
                matched_skills      = list(dict.fromkeys(best_matched)),  # dedup, preserve order
                top_section_type    = best_sec_type,
                top_chunk_text      = best_text[:600],
                years_of_experience = getattr(best_meta, "years_of_experience", 0.0) or 0.0,
                role                = getattr(best_meta, "role", ""),
                full_name           = getattr(best_meta, "full_name", ""),
                doc_id              = getattr(best_meta, "doc_id", ""),
                raw_chunk_score_map = {s: round(v[0], 4) for s, v in sec_map.items()},
            ))

        # Sort by fused score descending
        results.sort(key=lambda r: r.retrieval_score, reverse=True)
        logger.info(
            "Hybrid search → %d raw FAISS chunks → %d candidates (top retrieval_score=%.3f)",
            len(raw_results),
            len(results),
            results[0].retrieval_score if results else 0.0,
        )
        return results[:top_k]
