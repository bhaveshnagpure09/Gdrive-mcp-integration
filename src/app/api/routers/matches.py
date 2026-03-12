"""Matches router."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.repositories.requisition_repository import RequisitionRepository
from app.db.session import get_db

router = APIRouter(prefix="/jd-skill-mapping", tags=["matches"])


class MatchResult(BaseModel):
    """Individual match result."""

    team_member_id: str
    full_name: Optional[str] = None
    profile_url: Optional[str] = None
    profile_score: float
    match_percentage: Optional[float] = None
    fit_level: str
    availability_match: bool
    skill_score: Optional[float] = None
    experience_score: Optional[float] = None
    vector_similarity: Optional[float] = None
    availability_score: Optional[float] = None
    skills_matched: Optional[List[str]] = None
    skill_gaps: Optional[List[str]] = None
    explanation: List[str]


class MatchesResponse(BaseModel):
    """Response model for matches endpoint."""

    correlation_id: str
    status: str
    total_matches: int
    matches: List[MatchResult]
    message: Optional[str] = None


@router.get("/{correlation_id}/matches", response_model=MatchesResponse)
async def get_matches(correlation_id: str, db: Session = Depends(get_db)):
    """
    Get match results for a requisition.

    Returns the ranked list of candidates with scores and explanations.
    """
    repo = RequisitionRepository(db)

    # Verify requisition exists
    requisition = repo.get_requisition_by_correlation_id(correlation_id)
    if not requisition:
        raise HTTPException(status_code=404, detail="Requisition not found")

    # Retrieve results from DB (shared across all uvicorn workers)
    final_results = repo.get_match_results(correlation_id)

    if final_results is None:
        # Results not yet available - still processing
        return MatchesResponse(
            correlation_id=correlation_id,
            status="PROCESSING",
            total_matches=0,
            matches=[],
        )
    
    # Format results for response
    matches = [
        MatchResult(
            team_member_id=result["team_member_id"],
            full_name=result.get("full_name"),
            profile_url=result.get("profile_url"),
            profile_score=result["profile_score"],
            match_percentage=result.get("match_percentage"),
            fit_level=result["fit_level"],
            availability_match=result["availability_match"],
            skill_score=result.get("skill_score"),
            experience_score=result.get("experience_score"),
            vector_similarity=result.get("vector_similarity"),
            availability_score=result.get("availability_score"),
            skills_matched=result.get("skills_matched"),
            skill_gaps=result.get("skill_gaps"),
            explanation=result["explanation"],
        )
        for result in final_results
    ]
    
    return MatchesResponse(
        correlation_id=correlation_id,
        status="COMPLETED" if matches else "NO_MATCH",
        total_matches=len(matches),
        matches=matches,
        message=(
            None if matches
            else "No candidates found matching this requisition. "
                 "None of the team members had sufficient skill or semantic similarity "
                 "to the job description. Consider broadening the required skills or "
                 "updating team member profiles."
        ),
    )

