"""Deterministic scoring logic for candidate matching."""

from typing import Optional


# Configurable weights
SKILL_WEIGHT_MANDATORY = 0.7
SKILL_WEIGHT_PREFERRED = 0.3
# Blended final score: 40% skill, 40% vector similarity, 20% experience
FINAL_SCORE_SKILL_WEIGHT = 0.4
FINAL_SCORE_VECTOR_WEIGHT = 0.4
FINAL_SCORE_EXPERIENCE_WEIGHT = 0.2


def calculate_skill_score(
    team_member_skill_ids: list[str],
    mandatory_skill_ids: list[str],
    preferred_skill_ids: list[str],
    mandatory_weight: float = SKILL_WEIGHT_MANDATORY,
    preferred_weight: float = SKILL_WEIGHT_PREFERRED,
) -> dict:
    """Calculate skill matching score for a team member.
    
    Args:
        team_member_skill_ids: List of skill IDs the team member possesses
        mandatory_skill_ids: List of required skill IDs from requisition
        preferred_skill_ids: List of preferred skill IDs from requisition
        mandatory_weight: Weight for mandatory skills (default 0.7)
        preferred_weight: Weight for preferred skills (default 0.3)
    
    Returns:
        Dictionary with:
        - skill_score: Combined skill score (0.0 to 1.0)
        - mandatory_score: Mandatory skills score
        - preferred_score: Preferred skills score
        - matched_mandatory: List of matched mandatory skill IDs
        - matched_preferred: List of matched preferred skill IDs
    """
    # Convert to sets for efficient intersection
    member_skills = set(team_member_skill_ids)
    mandatory_skills = set(mandatory_skill_ids)
    preferred_skills = set(preferred_skill_ids)
    
    # Find matched skills
    matched_mandatory = list(member_skills & mandatory_skills)
    matched_preferred = list(member_skills & preferred_skills)
    
    # Calculate mandatory score (avoid division by zero)
    if len(mandatory_skills) > 0:
        mandatory_score = len(matched_mandatory) / len(mandatory_skills)
    else:
        mandatory_score = 1.0  # No mandatory skills means full score
    
    # Calculate preferred score (avoid division by zero)
    if len(preferred_skills) > 0:
        preferred_score = len(matched_preferred) / len(preferred_skills)
    else:
        preferred_score = 1.0  # No preferred skills means full score
    
    # Calculate combined skill score
    skill_score = (mandatory_weight * mandatory_score) + (preferred_weight * preferred_score)
    
    return {
        "skill_score": skill_score,
        "mandatory_score": mandatory_score,
        "preferred_score": preferred_score,
        "matched_mandatory": matched_mandatory,
        "matched_preferred": matched_preferred,
    }


def calculate_experience_score(
    team_member_experience_months: int,
    min_experience_months: Optional[int],
    max_experience_months: Optional[int],
) -> float:
    """Calculate experience matching score for a team member.
    
    Args:
        team_member_experience_months: Team member's experience in months
        min_experience_months: Minimum required experience (None = no minimum)
        max_experience_months: Maximum preferred experience (None = no maximum)
    
    Returns:
        Experience score (0.0 to 1.0+)
        - 0.0 if below minimum
        - 1.0 if within range or no constraints
        - 1.0 if above maximum (could be configurable to allow higher scores)
    """
    # If no experience requirements specified, return perfect score
    if min_experience_months is None and max_experience_months is None:
        return 1.0
    
    # If only minimum specified
    if min_experience_months is not None and max_experience_months is None:
        return 1.0 if team_member_experience_months >= min_experience_months else 0.0
    
    # If only maximum specified (unusual case)
    if min_experience_months is None and max_experience_months is not None:
        return 1.0 if team_member_experience_months <= max_experience_months else 1.0
    
    # Both min and max specified
    if min_experience_months is not None and max_experience_months is not None:
        if team_member_experience_months < min_experience_months:
            return 0.0
        elif team_member_experience_months <= max_experience_months:
            return 1.0
        else:
            # Above max - still give full score (could be made configurable)
            return 1.0
    
    return 1.0


def calculate_final_score(
    skill_score: float,
    experience_score: float,
    vector_similarity: float = 0.0,
    skill_weight: float = FINAL_SCORE_SKILL_WEIGHT,
    vector_weight: float = FINAL_SCORE_VECTOR_WEIGHT,
    experience_weight: float = FINAL_SCORE_EXPERIENCE_WEIGHT,
) -> float:
    """Calculate final aggregated score for a candidate.

    Args:
        skill_score: Skill matching score (0.0 to 1.0)
        experience_score: Experience matching score (0.0 to 1.0)
        vector_similarity: Cosine similarity between JD and resume embeddings (0.0–1.0)
        skill_weight: Weight for skill score (default 0.4)
        vector_weight: Weight for vector similarity (default 0.4)
        experience_weight: Weight for experience score (default 0.2)

    Returns:
        Final score (0.0 to 1.0)
    """
    final_score = (
        skill_weight * skill_score
        + vector_weight * vector_similarity
        + experience_weight * experience_score
    )
    return min(final_score, 1.0)


def calculate_candidate_score(
    team_member_id: str,
    team_member_skill_ids: list[str],
    team_member_experience_months: int,
    mandatory_skill_ids: list[str],
    preferred_skill_ids: list[str],
    min_experience_months: Optional[int],
    max_experience_months: Optional[int],
    is_available: bool,
    available_capacity: float,
    vector_similarity: float = 0.0,
) -> dict:
    """Calculate complete candidate score.
    
    Convenience function that combines skill and experience scoring.
    
    Args:
        team_member_id: Team member ID
        team_member_skill_ids: Skills possessed by team member
        team_member_experience_months: Experience in months
        mandatory_skill_ids: Required skills from requisition
        preferred_skill_ids: Preferred skills from requisition
        min_experience_months: Minimum required experience
        max_experience_months: Maximum preferred experience
        is_available: Availability flag
        available_capacity: Available capacity percentage
    
    Returns:
        Dictionary with complete scoring details
    """
    # Calculate skill score
    skill_result = calculate_skill_score(
        team_member_skill_ids,
        mandatory_skill_ids,
        preferred_skill_ids,
    )
    
    # Calculate experience score
    experience_score = calculate_experience_score(
        team_member_experience_months,
        min_experience_months,
        max_experience_months,
    )
    
    # Calculate final blended score (skill + vector similarity + experience)
    final_score = calculate_final_score(
        skill_result["skill_score"],
        experience_score,
        vector_similarity=vector_similarity,
    )

    return {
        "team_member_id": team_member_id,
        "skill_score": skill_result["skill_score"],
        "experience_score": experience_score,
        "vector_similarity": vector_similarity,
        "availability_score": available_capacity / 100.0,
        "final_score": final_score,
        "match_percentage": round(final_score * 100, 1),
        "is_available": is_available,
        "match_reasons": {
            "skills_matched": skill_result["matched_mandatory"] + skill_result["matched_preferred"],
            "mandatory_matched": skill_result["matched_mandatory"],
            "preferred_matched": skill_result["matched_preferred"],
            "mandatory_score": skill_result["mandatory_score"],
            "preferred_score": skill_result["preferred_score"],
        },
    }
