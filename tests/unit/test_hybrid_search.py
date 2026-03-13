"""Unit tests for HybridSearchEngine — score fusion, ranking order, and edge cases.

All FAISS calls are mocked so no GPU/index is needed.
"""

from __future__ import annotations

import math
from unittest.mock import MagicMock, patch
import pytest

from app.services.hybrid_search import (
    HybridSearchEngine,
    HybridSearchResult,
    _keyword_score,
    _skill_score,
    _tokenise,
)
from app.services.vector_store import ChunkMetadata, VectorSearchResult


# ---------------------------------------------------------------------------
# Helper to build a fake VectorSearchResult
# ---------------------------------------------------------------------------

def _make_vsr(
    candidate_id: str,
    section_type: str = "skills",
    score: float = 0.8,
    skills: list[str] | None = None,
    raw_text: str = "",
    yoe: float = 3.0,
    role: str = "Engineer",
    full_name: str = "",
    doc_id: str = "",
) -> VectorSearchResult:
    meta = ChunkMetadata(
        candidate_id=candidate_id,
        section_type=section_type,
        skills=skills or [],
        years_of_experience=yoe,
        role=role,
        full_name=full_name,
        doc_id=doc_id,
        raw_text=raw_text,
    )
    return VectorSearchResult(
        candidate_id=candidate_id,
        section_type=section_type,
        score=score,
        faiss_id=hash(candidate_id + section_type) & 0xFFFF,
        metadata=meta,
    )


# ---------------------------------------------------------------------------
# _tokenise
# ---------------------------------------------------------------------------

def test_tokenise_basic():
    tokens = _tokenise("Python FastAPI Docker")
    assert "python" in tokens
    assert "fastapi" in tokens
    assert "docker" in tokens


def test_tokenise_strips_short_tokens():
    tokens = _tokenise("a b Python")
    assert "a" not in tokens
    assert "b" not in tokens
    assert "python" in tokens


def test_tokenise_handles_empty():
    assert _tokenise("") == set()


# ---------------------------------------------------------------------------
# _keyword_score
# ---------------------------------------------------------------------------

def test_keyword_score_full_overlap():
    jd_tokens = _tokenise("Python FastAPI Docker")
    score = _keyword_score("python fastapi docker", jd_tokens)
    assert score == pytest.approx(1.0)


def test_keyword_score_zero_overlap():
    jd_tokens = _tokenise("Python FastAPI")
    score = _keyword_score("Java Spring Hibernate", jd_tokens)
    assert score == pytest.approx(0.0)


def test_keyword_score_partial():
    jd_tokens = _tokenise("Python FastAPI Docker Kubernetes")
    score = _keyword_score("python fastapi", jd_tokens)
    assert 0.0 < score < 1.0


def test_keyword_score_empty_jd():
    assert _keyword_score("python", set()) == 0.0


# ---------------------------------------------------------------------------
# _skill_score
# ---------------------------------------------------------------------------

def test_skill_score_all_mandatory_matched():
    score, matched = _skill_score(["Python", "FastAPI"], ["Python", "FastAPI"], [])
    assert score == pytest.approx(0.7 * 1.0 + 0.3 * 1.0)
    assert "Python" in matched
    assert "FastAPI" in matched


def test_skill_score_no_match():
    score, matched = _skill_score(["Java", "Spring"], ["Python", "FastAPI"], ["Docker"])
    assert score == pytest.approx(0.0)
    assert matched == []


def test_skill_score_partial_mandatory():
    # No preferred skills required → pref_score = 1.0 (full credit for unspecified requirement)
    # mand_score = 1/2 = 0.5  →  final = 0.7 * 0.5 + 0.3 * 1.0 = 0.65
    score, matched = _skill_score(["Python"], ["Python", "FastAPI"], [])
    assert score == pytest.approx(0.7 * 0.5 + 0.3 * 1.0)
    assert matched == ["Python"]


def test_skill_score_case_insensitive():
    score, matched = _skill_score(["python"], ["Python"], [])
    assert score > 0.0
    assert "Python" in matched


def test_skill_score_substring_matching():
    # "Python 3" should match JD skill "Python"
    score, matched = _skill_score(["Python 3", "FastAPI"], ["Python", "FastAPI"], [])
    assert score > 0.5
    assert len(matched) == 2


# ---------------------------------------------------------------------------
# HybridSearchEngine.search
# ---------------------------------------------------------------------------

def _build_engine_with_mock_store(raw_results: list[VectorSearchResult]) -> HybridSearchEngine:
    """Build a HybridSearchEngine whose FAISS store returns raw_results."""
    mock_store = MagicMock()
    mock_store.search.return_value = raw_results
    return HybridSearchEngine(vector_store=mock_store)


def test_search_returns_hybrid_results():
    vsrs = [
        _make_vsr("cand-1", skills=["Python", "FastAPI"], raw_text="Python FastAPI developer", score=0.85),
        _make_vsr("cand-2", skills=["Java", "Spring"], raw_text="Java Spring developer", score=0.60),
    ]
    engine = _build_engine_with_mock_store(vsrs)
    results = engine.search(
        query_vector=[0.1] * 10,
        jd_text="Python FastAPI developer",
        mandatory_skills=["Python", "FastAPI"],
        preferred_skills=["Docker"],
    )
    assert isinstance(results, list)
    assert all(isinstance(r, HybridSearchResult) for r in results)


def test_search_ranks_better_semantic_match_higher():
    """cand-1 has higher vector score AND relevant skills → should rank first."""
    vsrs = [
        _make_vsr("cand-1", skills=["Python", "FastAPI"], raw_text="Python FastAPI docker", score=0.90),
        _make_vsr("cand-2", skills=["Java", "Spring"], raw_text="Java Spring hibernate", score=0.30),
    ]
    engine = _build_engine_with_mock_store(vsrs)
    results = engine.search(
        query_vector=[0.1] * 10,
        jd_text="Python FastAPI developer",
        mandatory_skills=["Python"],
        preferred_skills=[],
        top_k=10,
    )
    assert results, "Expected at least one result"
    assert results[0].candidate_id == "cand-1", (
        f"Expected cand-1 to rank first, got {results[0].candidate_id}"
    )


def test_search_results_ordered_by_retrieval_score_desc():
    vsrs = [
        _make_vsr("cand-low",  skills=[], score=0.20),
        _make_vsr("cand-high", skills=["Python", "FastAPI"], raw_text="python fastapi", score=0.95),
        _make_vsr("cand-mid",  skills=["Python"], raw_text="python developer", score=0.60),
    ]
    engine = _build_engine_with_mock_store(vsrs)
    results = engine.search(
        query_vector=[0.1] * 10,
        jd_text="python fastapi",
        mandatory_skills=["Python"],
        preferred_skills=[],
        top_k=10,
        min_retrieval_score=0.01,
    )
    scores = [r.retrieval_score for r in results]
    assert scores == sorted(scores, reverse=True), f"Results not ordered: {scores}"


def test_search_filters_below_min_score():
    vsrs = [
        _make_vsr("cand-weak", skills=[], raw_text="unrelated text here", score=0.05),
    ]
    engine = _build_engine_with_mock_store(vsrs)
    results = engine.search(
        query_vector=[0.1] * 10,
        jd_text="Python senior developer",
        mandatory_skills=["Python"],
        preferred_skills=[],
        min_retrieval_score=0.40,
    )
    assert all(r.retrieval_score >= 0.40 for r in results)


def test_search_empty_store_returns_empty():
    engine = _build_engine_with_mock_store([])
    results = engine.search(
        query_vector=[0.1] * 10,
        jd_text="Python",
        mandatory_skills=["Python"],
        preferred_skills=[],
    )
    assert results == []


def test_search_returns_matched_skills():
    vsrs = [
        _make_vsr("cand-1", skills=["Python", "Docker"], raw_text="python docker engineer", score=0.85),
    ]
    engine = _build_engine_with_mock_store(vsrs)
    results = engine.search(
        query_vector=[0.1] * 10,
        jd_text="python docker",
        mandatory_skills=["Python"],
        preferred_skills=["Docker"],
        top_k=5,
    )
    assert results
    assert "Python" in results[0].matched_skills


def test_search_aggregates_multi_section_candidate():
    """Same candidate with multiple sections should appear once in results."""
    vsrs = [
        _make_vsr("cand-1", section_type="skills",     skills=["Python"], score=0.80),
        _make_vsr("cand-1", section_type="experience", skills=["Python"], score=0.75),
        _make_vsr("cand-1", section_type="projects",   skills=["Python"], score=0.70),
    ]
    engine = _build_engine_with_mock_store(vsrs)
    results = engine.search(
        query_vector=[0.1] * 10,
        jd_text="python engineer",
        mandatory_skills=["Python"],
        preferred_skills=[],
        top_k=10,
    )
    cand_ids = [r.candidate_id for r in results]
    assert cand_ids.count("cand-1") == 1, "cand-1 should appear exactly once"


def test_search_fused_score_in_range():
    vsrs = [_make_vsr("cand-1", skills=["Python"], raw_text="python dev", score=0.80)]
    engine = _build_engine_with_mock_store(vsrs)
    results = engine.search(
        query_vector=[0.1] * 10,
        jd_text="python",
        mandatory_skills=["Python"],
        preferred_skills=[],
        top_k=5,
    )
    for r in results:
        assert 0.0 <= r.retrieval_score <= 1.0, f"Score out of range: {r.retrieval_score}"


def test_search_respects_top_k():
    vsrs = [_make_vsr(f"cand-{i}", skills=["Python"], score=0.9 - i * 0.01) for i in range(20)]
    engine = _build_engine_with_mock_store(vsrs)
    results = engine.search(
        query_vector=[0.1] * 10,
        jd_text="python",
        mandatory_skills=["Python"],
        preferred_skills=[],
        top_k=5,
        min_retrieval_score=0.01,
    )
    assert len(results) <= 5
