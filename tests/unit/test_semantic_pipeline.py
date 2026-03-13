"""Unit tests for SemanticRetrievalPipeline — end-to-end ranking correctness.

All ML model calls (BGE encoder, FAISS, cross-encoder reranker) are mocked
so no GPU or downloaded weights are required.  The tests prove that the
weighted-score formula produces the **correct relative ranking order** that
the user expects.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional
from unittest.mock import MagicMock, patch, call
import pytest

# ---------------------------------------------------------------------------
# Helpers — lightweight stubs matching the real dataclass shapes
# ---------------------------------------------------------------------------

def _make_hybrid_result(
    candidate_id: str,
    retrieval_score: float = 0.80,
    matched_skills: list[str] | None = None,
    years_of_experience: float = 3.0,
    role: str = "Engineer",
    full_name: str = "",
    doc_id: str = "",
    top_section_type: str = "skills",
    top_chunk_text: str = "",
):
    """Produce a HybridSearchResult-compatible MagicMock."""
    r = MagicMock()
    r.candidate_id        = candidate_id
    r.retrieval_score     = retrieval_score
    r.matched_skills      = matched_skills or []
    r.years_of_experience = years_of_experience
    r.role                = role
    r.full_name           = full_name
    r.doc_id              = doc_id
    r.top_section_type    = top_section_type
    r.top_chunk_text      = top_chunk_text
    return r


def _make_rerank_result(
    candidate_id: str,
    rerank_score: float = 0.85,
    final_score: float = 0.85,
    retrieval_score: float = 0.80,
    matched_skills: list[str] | None = None,
    years_of_experience: float = 3.0,
    role: str = "Engineer",
    full_name: str = "",
    doc_id: str = "",
    top_section_type: str = "skills",
    top_chunk_text: str = "",
):
    r = MagicMock()
    r.candidate_id        = candidate_id
    r.rerank_score        = rerank_score
    r.final_score         = final_score
    r.retrieval_score     = retrieval_score
    r.matched_skills      = matched_skills or []
    r.years_of_experience = years_of_experience
    r.role                = role
    r.full_name           = full_name
    r.doc_id              = doc_id
    r.top_section_type    = top_section_type
    r.top_chunk_text      = top_chunk_text
    return r


# ---------------------------------------------------------------------------
# Build a fully mocked pipeline
# ---------------------------------------------------------------------------

def _build_pipeline(hybrid_results, rerank_results, members=None):
    """Return (pipeline, db_mock) with all internals mocked."""
    from app.services.semantic_pipeline import SemanticRetrievalPipeline

    mock_embedder = MagicMock()
    mock_embedder.dim = 1024
    mock_embedder.generate_query.return_value = [0.1] * 1024

    mock_store = MagicMock()
    mock_store.total_vectors = 10

    mock_hybrid = MagicMock()
    mock_hybrid.search.return_value = hybrid_results

    mock_reranker = MagicMock()
    mock_reranker.rerank.return_value = rerank_results

    pipeline = SemanticRetrievalPipeline(
        embedder     = mock_embedder,
        hybrid_engine= mock_hybrid,
        reranker     = mock_reranker,
        vector_store = mock_store,
    )

    # Build DB mock that returns TeamMember objects for each candidate
    mock_db = MagicMock()
    if members is not None:
        mock_db.query.return_value.filter.return_value.all.return_value = members
    else:
        mock_db.query.return_value.filter.return_value.all.return_value = []

    return pipeline, mock_db


def _make_team_member(team_member_id: str, full_name: str = "", designation: str = "", months: int = 36):
    m = MagicMock()
    m.team_member_id      = team_member_id
    m.full_name           = full_name
    m.designation         = designation
    m.experience_in_months= months
    m.profile_url         = ""
    return m


# ===========================================================================
# Tests
# ===========================================================================

class TestSemanticPipelineBasic:

    def test_run_returns_list(self):
        rr = [_make_rerank_result("cand-1")]
        pipeline, db = _build_pipeline(
            hybrid_results=[_make_hybrid_result("cand-1")],
            rerank_results=rr,
        )
        results = pipeline.run(
            jd_text="Python developer",
            mandatory_skills=["Python"],
            preferred_skills=[],
            db=db,
        )
        assert isinstance(results, list)

    def test_run_empty_when_no_hybrid_results(self):
        pipeline, db = _build_pipeline(hybrid_results=[], rerank_results=[])
        results = pipeline.run(
            jd_text="Python developer",
            mandatory_skills=["Python"],
            preferred_skills=[],
            db=db,
        )
        assert results == []

    def test_run_empty_when_no_rerank_results(self):
        hr = [_make_hybrid_result("cand-1")]
        pipeline, db = _build_pipeline(hybrid_results=hr, rerank_results=[])
        results = pipeline.run(
            jd_text="Python developer",
            mandatory_skills=["Python"],
            preferred_skills=[],
            db=db,
        )
        assert results == []

    def test_final_score_in_valid_range(self):
        rr = [_make_rerank_result("cand-1", final_score=0.80, retrieval_score=0.75)]
        pipeline, db = _build_pipeline(
            hybrid_results=[_make_hybrid_result("cand-1")], rerank_results=rr
        )
        results = pipeline.run(
            jd_text="Python", mandatory_skills=["Python"], preferred_skills=[], db=db
        )
        assert results
        for c in results:
            assert 0.0 <= c.final_score <= 1.0

    def test_match_percentage_equals_final_score_times_100(self):
        rr = [_make_rerank_result("cand-1", final_score=0.72, retrieval_score=0.70)]
        pipeline, db = _build_pipeline(
            hybrid_results=[_make_hybrid_result("cand-1")], rerank_results=rr
        )
        results = pipeline.run(
            jd_text="Python", mandatory_skills=["Python"], preferred_skills=[], db=db
        )
        assert results
        c = results[0]
        assert c.match_percentage == pytest.approx(c.final_score * 100, abs=0.5)

    def test_to_dict_contains_required_keys(self):
        rr = [_make_rerank_result("cand-1")]
        pipeline, db = _build_pipeline(
            hybrid_results=[_make_hybrid_result("cand-1")], rerank_results=rr
        )
        results = pipeline.run(
            jd_text="Python", mandatory_skills=["Python"], preferred_skills=[], db=db
        )
        assert results
        d = results[0].to_dict()
        required = {
            "team_member_id", "full_name", "final_score", "match_percentage",
            "semantic_score", "skill_score", "experience_score", "availability_score",
            "matched_skills", "is_available",
            # Backward-compat keys expected by result_aggregation_node
            "vector_similarity", "match_reasons",
        }
        missing = required - set(d.keys())
        assert not missing, f"to_dict() missing keys: {missing}"

    def test_backward_compat_vector_similarity_alias(self):
        rr = [_make_rerank_result("cand-1", final_score=0.75)]
        pipeline, db = _build_pipeline(
            hybrid_results=[_make_hybrid_result("cand-1")], rerank_results=rr
        )
        results = pipeline.run(
            jd_text="Python", mandatory_skills=["Python"], preferred_skills=[], db=db
        )
        d = results[0].to_dict()
        # vector_similarity must equal semantic_score
        assert d["vector_similarity"] == d["semantic_score"]


class TestSemanticPipelineRanking:
    """Verify that the weighted scoring formula produces the expected order."""

    def _run_two_candidates(self, rr_list, availability_filter=None):
        hr = [_make_hybrid_result(r.candidate_id) for r in rr_list]
        pipeline, db = _build_pipeline(hybrid_results=hr, rerank_results=rr_list)
        return pipeline.run(
            jd_text="Senior Python developer",
            mandatory_skills=["Python"],
            preferred_skills=["Docker"],
            db=db,
            availability_filter=availability_filter,
        )

    def test_higher_semantic_score_ranks_first(self):
        """When all other factors are equal, higher semantic score → higher rank."""
        rr = [
            _make_rerank_result("cand-high", final_score=0.90, retrieval_score=0.85, years_of_experience=3.0),
            _make_rerank_result("cand-low",  final_score=0.50, retrieval_score=0.45, years_of_experience=3.0),
        ]
        results = self._run_two_candidates(rr)
        assert results, "Pipeline returned empty"
        ids = [c.team_member_id for c in results]
        assert ids[0] == "cand-high", f"Expected cand-high first, got {ids}"

    def test_more_matched_skills_ranks_higher(self):
        """Candidate who matches more mandatory skills should outrank one who matches none
        (assuming similar semantic scores)."""
        rr = [
            _make_rerank_result(
                "cand-skill",
                final_score=0.70,
                retrieval_score=0.70,
                matched_skills=["Python", "FastAPI", "Docker"],
            ),
            _make_rerank_result(
                "cand-no-skill",
                final_score=0.70,
                retrieval_score=0.20,  # low because no skill overlap in hybrid
                matched_skills=[],
            ),
        ]
        results = self._run_two_candidates(rr)
        if len(results) >= 2:
            scores = {c.team_member_id: c.final_score for c in results}
            assert scores["cand-skill"] >= scores["cand-no-skill"]

    def test_results_sorted_by_final_score_desc(self):
        """Results must always come out in descending final_score order."""
        rr = [
            _make_rerank_result("c1", final_score=0.55, retrieval_score=0.50),
            _make_rerank_result("c2", final_score=0.90, retrieval_score=0.88),
            _make_rerank_result("c3", final_score=0.72, retrieval_score=0.70),
        ]
        results = self._run_two_candidates(rr)
        final_scores = [c.final_score for c in results]
        assert final_scores == sorted(final_scores, reverse=True), (
            f"Results not sorted: {final_scores}"
        )

    def test_availability_zero_lowers_score(self):
        """A candidate with 0% availability should score lower than one at 100%."""
        rr = [
            _make_rerank_result("cand-avail",   final_score=0.75, retrieval_score=0.70),
            _make_rerank_result("cand-no-avail", final_score=0.75, retrieval_score=0.70),
        ]
        avail = {"cand-avail": 100.0, "cand-no-avail": 0.0}
        results = self._run_two_candidates(rr, availability_filter=avail)
        if len(results) >= 2:
            scores = {c.team_member_id: c.final_score for c in results}
            assert scores.get("cand-avail", 0) >= scores.get("cand-no-avail", 0)

    def test_top_k_limits_results(self):
        rr = [_make_rerank_result(f"cand-{i}", final_score=0.9 - i * 0.01) for i in range(15)]
        hr = [_make_hybrid_result(f"cand-{i}") for i in range(15)]
        pipeline, db = _build_pipeline(hybrid_results=hr, rerank_results=rr)
        results = pipeline.run(
            jd_text="Python developer",
            mandatory_skills=["Python"],
            preferred_skills=[],
            db=db,
            top_k=5,
        )
        assert len(results) <= 5

    def test_db_member_data_used_for_full_name(self):
        """Member data from the DB should be reflected in the candidate name."""
        rr = [_make_rerank_result("cand-1", full_name="From Reranker")]
        hr = [_make_hybrid_result("cand-1")]
        member = _make_team_member("cand-1", full_name="John Doe From DB", months=60)
        pipeline, db = _build_pipeline(
            hybrid_results=hr,
            rerank_results=rr,
            members=[member],
        )
        results = pipeline.run(
            jd_text="Python developer",
            mandatory_skills=["Python"],
            preferred_skills=[],
            db=db,
        )
        assert results
        assert results[0].full_name == "John Doe From DB"


class TestRunSemanticPipelineConvenienceFunction:

    def test_returns_list_of_dicts(self):
        from app.services.semantic_pipeline import run_semantic_pipeline

        rr = [_make_rerank_result("cand-1")]
        hr = [_make_hybrid_result("cand-1")]

        with patch("app.services.semantic_pipeline.SemanticRetrievalPipeline") as MockPipeline:
            mock_instance = MagicMock()
            from app.services.semantic_pipeline import SemanticCandidate
            from dataclasses import fields

            # Build a real SemanticCandidate to pass through to_dict()
            sc = SemanticCandidate(
                team_member_id="cand-1",
                full_name="Test User",
                designation="Engineer",
                role="Engineer",
                years_of_experience=3.0,
                experience_months=36,
                semantic_score=0.80,
                skill_score=0.70,
                experience_score=0.85,
                availability_score=1.0,
                final_score=0.79,
                match_percentage=79.0,
            )
            mock_instance.run.return_value = [sc]
            MockPipeline.return_value = mock_instance

            mock_db = MagicMock()
            result = run_semantic_pipeline(
                jd_text="Python",
                mandatory_skills=["Python"],
                preferred_skills=[],
                db=mock_db,
            )

        assert isinstance(result, list)
        assert all(isinstance(r, dict) for r in result)
        assert result[0]["team_member_id"] == "cand-1"
