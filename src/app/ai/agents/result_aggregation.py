"""Result aggregation agent."""

import logging

from app.ai.state import GraphState

logger = logging.getLogger(__name__)


def determine_fit_level(final_score: float) -> str:
    """Determine fit level based on final score.
    
    Args:
        final_score: Final score (0.0 to 1.0)
    
    Returns:
        Fit level: HIGH, MEDIUM, or LOW
    """
    if final_score >= 0.75:
        return "HIGH"
    elif final_score >= 0.50:
        return "MEDIUM"
    else:
        return "LOW"


def result_aggregation_node(state: GraphState) -> GraphState:
    """Format final ranked list of candidates for API response.
    
    This node:
    1. Takes candidate_scores from state
    2. Formats each candidate for API response
    3. Derives fit_level from final_score
    4. Includes availability information
    5. Populates state.final_results with sorted list
    """
    logger.info("Executing Result_Aggregation_Agent node")
    
    candidate_scores = state.get("candidate_scores")
    if not candidate_scores:
        logger.warning(
            "No candidate_scores found in state — either no candidates passed the "
            "relevance filter or the matching node produced no results. "
            "Returning empty match list."
        )
        state["final_results"] = []
        return state
    
    # Format results for API response
    final_results = []
    
    for candidate in candidate_scores:
        # Determine fit level from score
        fit_level = determine_fit_level(candidate["final_score"])
        
        # Build explanation list
        explanation = []
        
        # Add overall score explanation
        match_pct = candidate.get("match_percentage", round(candidate["final_score"] * 100, 1))
        explanation.append(
            f"Overall match: {match_pct:.1f}% ({fit_level} fit)"
        )
        
        # Add skill match details
        skill_score = candidate.get("skill_score", 0.0)
        matched_skills = candidate.get("match_reasons", {}).get("skills_matched", [])
        # Fall back to skills_matched_names (includes fuzzy/metadata matches)
        if not matched_skills:
            matched_skills = candidate.get("skills_matched_names", [])
        if matched_skills:
            explanation.append(
                f"Skills matched: {', '.join(matched_skills)} (score: {skill_score:.2f})"
            )
        else:
            explanation.append(f"Skill match score: {skill_score:.2f}")
        
        # Add experience details
        experience_score = candidate.get("experience_score", 0.0)
        explanation.append(f"Experience match score: {experience_score:.2f}")
        
        # Add vector/semantic similarity if available
        vec_sim = candidate.get("vector_similarity", 0.0)
        if vec_sim > 0:
            explanation.append(f"Resume semantic similarity: {vec_sim * 100:.1f}%")

        # Add availability details
        is_available = candidate.get("is_available", False)
        availability_score = candidate.get("availability_score", 0.0)
        availability_pct = availability_score * 100
        explanation.append(
            f"Availability: {availability_pct:.0f}% capacity "
            f"({'Available' if is_available else 'Limited availability'})"
        )
        
        # Create result entry
        result_entry = {
            "team_member_id": candidate["team_member_id"],
            "full_name": candidate.get("full_name"),
            "profile_url": candidate.get("profile_url"),
            "match_percentage": candidate.get("match_percentage", round(candidate["final_score"] * 100, 1)),
            "profile_score": round(candidate["final_score"], 4),
            "fit_level": fit_level,
            "availability_match": is_available,
            "skill_score": round(candidate.get("skill_score", 0.0), 4),
            "experience_score": round(candidate.get("experience_score", 0.0), 4),
            "vector_similarity": round(candidate.get("vector_similarity", 0.0), 4),
            "availability_score": round(candidate.get("availability_score", 0.0), 4),
            "skills_matched": candidate.get("skills_matched_names", []),
            "skill_gaps": candidate.get("skill_gaps_names", []),
            "explanation": explanation,
        }
        
        final_results.append(result_entry)
    
    # Results are already sorted by final_score from matching_scoring_node
    state["final_results"] = final_results
    
    logger.info(f"Result_Aggregation_Agent completed with {len(final_results)} results")
    logger.debug(f"Top 3 candidates: {[r['team_member_id'] for r in final_results[:3]]}")
    
    return state
