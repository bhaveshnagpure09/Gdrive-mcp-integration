"""Matching and scoring agent."""

import logging

from sqlalchemy.orm import Session

from app.ai.availability import evaluate_availability
from app.ai.scoring import calculate_candidate_score
from app.ai.state import GraphState
from app.db.models import TeamMember, TeamMemberSkill
from app.db.repositories.embedding_repository import EmbeddingRepository
from app.db.session import SessionLocal
from app.services.embedding_generator import EmbeddingGenerator

logger = logging.getLogger(__name__)


def matching_scoring_node(state: GraphState) -> GraphState:
    """Execute deterministic matching and scoring for all team members.
    
    This node:
    1. Retrieves all active team members from the database
    2. Evaluates availability for each member
    3. Calculates skill and experience scores
    4. Populates state.candidate_scores with ranked results
    """
    logger.info("Executing Matching_Scoring_Agent node")
    
    # Extract required data from state
    normalized_skills = state.get("normalized_skills")
    requisition_input = state.get("requisition_input")
    parsed_jd = state.get("parsed_jd")
    
    if not normalized_skills or not requisition_input:
        logger.error("Missing required state: normalized_skills or requisition_input")
        state["error_message"] = "Missing normalized_skills or requisition_input"
        return state
    
    # Extract requisition parameters
    mandatory_skill_ids = normalized_skills.get("mandatory_skill_ids", [])
    preferred_skill_ids = normalized_skills.get("preferred_skill_ids", [])
    
    # Extract experience requirements from parsed_jd
    min_experience_months = None
    max_experience_months = None
    if parsed_jd and parsed_jd.get("experience"):
        min_experience_months = parsed_jd["experience"].get("min_months")
        max_experience_months = parsed_jd["experience"].get("max_months")
    
    # Extract date requirements for availability check
    expected_start_date = None
    requisition_duration_month = None
    if parsed_jd:
        expected_start_date = parsed_jd.get("expected_start_date")
        requisition_duration_month = parsed_jd.get("requisition_duration_month")
    
    # Query database for all active team members
    db: Session = SessionLocal()
    try:
        team_members = db.query(TeamMember).filter(TeamMember.is_active == True).all()

        logger.info(f"Found {len(team_members)} active team members to evaluate")

        # --- Vector similarity: generate JD embedding and compare to stored resume embeddings ---
        vector_similarity_map: dict[str, float] = {}
        try:
            jd_info = requisition_input.get("job_description", {})
            jd_text = (
                jd_info.get("jd_text", "") if isinstance(jd_info, dict) else str(jd_info)
            )
            if jd_text:
                embedder = EmbeddingGenerator()
                jd_embedding = embedder.generate(jd_text)
                embedding_repo = EmbeddingRepository(db)
                similar = embedding_repo.find_similar_by_vector(jd_embedding, top_k=50)
                vector_similarity_map = {tid: sim for tid, sim in similar}
                logger.info(
                    f"Vector similarity computed for {len(vector_similarity_map)} members"
                )
        except Exception as e:
            logger.warning(f"JD embedding/similarity failed, skipping: {e}")

        candidate_scores = []
        
        for member in team_members:
            try:
                # Get member's skills
                member_skill_ids = [
                    skill.skill_id 
                    for skill in db.query(TeamMemberSkill)
                    .filter(TeamMemberSkill.team_member_id == member.team_member_id)
                    .all()
                ]
                
                # Evaluate availability
                availability_result = evaluate_availability(
                    db,
                    member.team_member_id,
                    expected_start_date,
                    requisition_duration_month,
                    threshold_percentage=80.0,
                )
                
                # Calculate complete candidate score (include vector similarity if available)
                score_result = calculate_candidate_score(
                    team_member_id=member.team_member_id,
                    team_member_skill_ids=member_skill_ids,
                    team_member_experience_months=member.experience_in_months or 0,
                    mandatory_skill_ids=mandatory_skill_ids,
                    preferred_skill_ids=preferred_skill_ids,
                    min_experience_months=min_experience_months,
                    max_experience_months=max_experience_months,
                    is_available=availability_result["is_available"],
                    available_capacity=availability_result["available_capacity"],
                    vector_similarity=vector_similarity_map.get(member.team_member_id, 0.0),
                )
                
                candidate_scores.append(score_result)
                
            except Exception as e:
                logger.error(f"Error scoring team member {member.team_member_id}: {str(e)}", exc_info=True)
                continue
        
        # Sort candidates by final_score descending
        candidate_scores.sort(key=lambda x: x["final_score"], reverse=True)
        
        state["candidate_scores"] = candidate_scores
        logger.info(f"Matching_Scoring_Agent completed with {len(candidate_scores)} scored candidates")
        
    except Exception as e:
        logger.error(f"Error in matching_scoring_node: {str(e)}", exc_info=True)
        state["error_message"] = f"Matching scoring failed: {str(e)}"
    finally:
        db.close()
    
    return state
