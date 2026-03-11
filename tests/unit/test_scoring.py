"""Unit tests for scoring logic."""

import pytest

from app.ai.scoring import (
    calculate_candidate_score,
    calculate_experience_score,
    calculate_final_score,
    calculate_skill_score,
)


def test_calculate_skill_score_all_mandatory_matched():
    """Test skill score when all mandatory skills are matched."""
    result = calculate_skill_score(
        team_member_skill_ids=["PYTHON", "FASTAPI", "POSTGRESQL"],
        mandatory_skill_ids=["PYTHON", "FASTAPI"],
        preferred_skill_ids=["DOCKER"],
    )
    
    assert result["mandatory_score"] == 1.0
    assert result["preferred_score"] == 0.0
    assert result["skill_score"] == 0.7  # 0.7 * 1.0 + 0.3 * 0.0
    assert set(result["matched_mandatory"]) == {"PYTHON", "FASTAPI"}
    assert result["matched_preferred"] == []


def test_calculate_skill_score_partial_mandatory():
    """Test skill score with partial mandatory match."""
    result = calculate_skill_score(
        team_member_skill_ids=["PYTHON", "DOCKER"],
        mandatory_skill_ids=["PYTHON", "FASTAPI", "POSTGRESQL"],
        preferred_skill_ids=["DOCKER", "K8S"],
    )
    
    assert result["mandatory_score"] == pytest.approx(1 / 3)
    assert result["preferred_score"] == 0.5
    assert result["skill_score"] == pytest.approx(0.7 * (1/3) + 0.3 * 0.5)
    assert result["matched_mandatory"] == ["PYTHON"]
    assert result["matched_preferred"] == ["DOCKER"]


def test_calculate_skill_score_no_mandatory():
    """Test skill score when no mandatory skills specified."""
    result = calculate_skill_score(
        team_member_skill_ids=["PYTHON", "DOCKER"],
        mandatory_skill_ids=[],
        preferred_skill_ids=["DOCKER", "K8S"],
    )
    
    assert result["mandatory_score"] == 1.0  # No requirements = full score
    assert result["preferred_score"] == 0.5
    assert result["skill_score"] == 0.7 * 1.0 + 0.3 * 0.5


def test_calculate_skill_score_no_preferred():
    """Test skill score when no preferred skills specified."""
    result = calculate_skill_score(
        team_member_skill_ids=["PYTHON", "FASTAPI"],
        mandatory_skill_ids=["PYTHON"],
        preferred_skill_ids=[],
    )
    
    assert result["mandatory_score"] == 1.0
    assert result["preferred_score"] == 1.0  # No requirements = full score
    assert result["skill_score"] == 1.0


def test_calculate_skill_score_custom_weights():
    """Test skill score with custom weights."""
    result = calculate_skill_score(
        team_member_skill_ids=["PYTHON"],
        mandatory_skill_ids=["PYTHON"],
        preferred_skill_ids=["DOCKER"],
        mandatory_weight=0.6,
        preferred_weight=0.4,
    )
    
    assert result["skill_score"] == 0.6  # 0.6 * 1.0 + 0.4 * 0.0


def test_calculate_experience_score_within_range():
    """Test experience score within required range."""
    score = calculate_experience_score(
        team_member_experience_months=48,
        min_experience_months=36,
        max_experience_months=60,
    )
    
    assert score == 1.0


def test_calculate_experience_score_below_minimum():
    """Test experience score below minimum."""
    score = calculate_experience_score(
        team_member_experience_months=24,
        min_experience_months=36,
        max_experience_months=60,
    )
    
    assert score == 0.0


def test_calculate_experience_score_above_maximum():
    """Test experience score above maximum."""
    score = calculate_experience_score(
        team_member_experience_months=72,
        min_experience_months=36,
        max_experience_months=60,
    )
    
    assert score == 1.0  # Currently gives full score for overqualified


def test_calculate_experience_score_no_requirements():
    """Test experience score with no requirements."""
    score = calculate_experience_score(
        team_member_experience_months=48,
        min_experience_months=None,
        max_experience_months=None,
    )
    
    assert score == 1.0


def test_calculate_experience_score_only_minimum():
    """Test experience score with only minimum specified."""
    score_pass = calculate_experience_score(
        team_member_experience_months=48,
        min_experience_months=36,
        max_experience_months=None,
    )
    
    score_fail = calculate_experience_score(
        team_member_experience_months=24,
        min_experience_months=36,
        max_experience_months=None,
    )
    
    assert score_pass == 1.0
    assert score_fail == 0.0


def test_calculate_final_score_default_weights():
    """Test final score calculation with default weights (40% skill + 40% vector + 20% exp)."""
    final_score = calculate_final_score(
        skill_score=0.8,
        experience_score=0.6,
    )
    # vector_similarity defaults to 0.0; formula: 0.4*skill + 0.4*vector + 0.2*exp
    assert final_score == pytest.approx(0.4 * 0.8 + 0.4 * 0.0 + 0.2 * 0.6)


def test_calculate_final_score_custom_weights():
    """Test final score calculation with custom weights."""
    final_score = calculate_final_score(
        skill_score=0.8,
        experience_score=0.6,
        skill_weight=0.5,
        experience_weight=0.5,
    )
    
    assert final_score == 0.5 * 0.8 + 0.5 * 0.6


def test_calculate_candidate_score_full_match():
    """Test complete candidate score calculation with full match."""
    result = calculate_candidate_score(
        team_member_id="tm-001",
        team_member_skill_ids=["PYTHON", "FASTAPI", "POSTGRESQL", "DOCKER"],
        team_member_experience_months=48,
        mandatory_skill_ids=["PYTHON", "FASTAPI"],
        preferred_skill_ids=["DOCKER"],
        min_experience_months=36,
        max_experience_months=60,
        is_available=True,
        available_capacity=50.0,
    )
    
    assert result["team_member_id"] == "tm-001"
    assert result["skill_score"] == 1.0  # All skills matched
    assert result["experience_score"] == 1.0  # Within range
    assert result["availability_score"] == 0.5  # 50/100
    # No vector_similarity provided (defaults 0.0): 0.4*1.0 + 0.4*0.0 + 0.2*1.0 = 0.6
    assert result["final_score"] == pytest.approx(0.6)
    assert result["match_percentage"] == pytest.approx(60.0)
    assert result["is_available"] is True
    assert set(result["match_reasons"]["mandatory_matched"]) == {"PYTHON", "FASTAPI"}
    assert result["match_reasons"]["preferred_matched"] == ["DOCKER"]


def test_calculate_candidate_score_partial_match():
    """Test candidate score with partial skill match."""
    result = calculate_candidate_score(
        team_member_id="tm-002",
        team_member_skill_ids=["PYTHON"],
        team_member_experience_months=24,
        mandatory_skill_ids=["PYTHON", "FASTAPI", "POSTGRESQL"],
        preferred_skill_ids=["DOCKER", "K8S"],
        min_experience_months=36,
        max_experience_months=60,
        is_available=False,
        available_capacity=10.0,
    )
    
    assert result["team_member_id"] == "tm-002"
    assert result["skill_score"] == pytest.approx(0.7 * (1/3))  # Only 1 of 3 mandatory
    assert result["experience_score"] == 0.0  # Below minimum
    assert result["availability_score"] == 0.1  # 10/100
    assert result["is_available"] is False
    assert len(result["match_reasons"]["mandatory_matched"]) == 1
    assert len(result["match_reasons"]["preferred_matched"]) == 0


def test_calculate_candidate_score_no_skills_required():
    """Test candidate score when no skills are specified."""
    result = calculate_candidate_score(
        team_member_id="tm-003",
        team_member_skill_ids=["PYTHON", "JAVA"],
        team_member_experience_months=60,
        mandatory_skill_ids=[],
        preferred_skill_ids=[],
        min_experience_months=None,
        max_experience_months=None,
        is_available=True,
        available_capacity=100.0,
    )
    
    assert result["skill_score"] == 1.0
    assert result["experience_score"] == 1.0
    # No vector_similarity (defaults 0.0): 0.4*1.0 + 0.4*0.0 + 0.2*1.0 = 0.6
    assert result["final_score"] == pytest.approx(0.6)
    assert result["match_percentage"] == pytest.approx(60.0)
