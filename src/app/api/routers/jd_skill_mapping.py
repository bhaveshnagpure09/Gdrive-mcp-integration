"""Job description to skill mapping router."""

import logging

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.api.schemas.requisition import RequisitionRequest, RequisitionResponse
from app.db.repositories.requisition_repository import RequisitionRepository
from app.db.session import get_db, SessionLocal
from app.ai.graph_executor import execute_graph_with_audit

router = APIRouter(prefix="/jd-skill-mapping", tags=["jd-skill-mapping"])
logger = logging.getLogger(__name__)


def process_requisition_with_graph(correlation_id: str, request: RequisitionRequest, request_id: str):
    """Background task to process requisition through LangGraph with audit trail."""
    # Create a new database session for the background task
    db = SessionLocal()
    
    try:
        logger.info(f"Starting graph processing for correlation_id={correlation_id}")
        
        # Prepare initial state
        jd = request.job_description
        initial_state = {
            "requisition_input": {
                "request_id": request_id,
                "job_description": {
                    "title": jd.title,
                    "role": jd.role,
                    "jd_text": jd.jd_text,
                    "mandatory_skills": jd.mandatory_skills or [],
                    "preferred_skills": jd.preferred_skills or [],
                    "expected_start_date": str(jd.expected_start_date) if jd.expected_start_date else None,
                    "requisition_duration_month": jd.requisition_duration_month,
                    "experience": {
                        "min_months": jd.experience.min_months if jd.experience else None,
                        "max_months": jd.experience.max_months if jd.experience else None,
                    },
                },
                "requested_team_ids": [],  # TODO: Add team filtering support
                "min_availability_percentage": 50,  # Default value
                "correlation_id": correlation_id,
            },
            "parsed_jd": None,
            "normalized_skills": None,
            "candidate_scores": None,
            "final_results": None,
            "error_message": None,
        }
        
        # Run graph with audit trail
        final_state = execute_graph_with_audit(initial_state, request_id, db)
        
        logger.info(f"Graph processing completed for correlation_id={correlation_id}")
        
        # Persist results to DB (works across all uvicorn workers)
        final_results = final_state.get("final_results", []) or []
        repo_bg = RequisitionRepository(db)
        repo_bg.save_match_results(correlation_id, final_results)
        db.commit()
        logger.info(f"Stored {len(final_results)} results for {correlation_id}")
        
        # Log any errors
        error_message = final_state.get("error_message")
        if error_message:
            logger.error(f"Graph execution error for {correlation_id}: {error_message}")
        
    except Exception as e:
        logger.error(f"Error processing requisition with graph: {str(e)}", exc_info=True)
    finally:
        db.close()


@router.post("/", response_model=RequisitionResponse, status_code=202)
async def create_jd_skill_mapping(
    request: RequisitionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Create a job description to skill mapping requisition.

    This endpoint accepts a requisition request, validates it, persists it,
    and queues it for AI processing.
    """
    repo = RequisitionRepository(db)

    # Check for duplicate request_id
    existing = repo.get_requisition_by_request_id(request.request_id)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Request with request_id {request.request_id} already exists",
        )

    try:
        # Create requisition (using default auth_client_id=1 for now)
        req, correlation_id = repo.create_requisition(request, auth_client_id=1)
        db.commit()

        # Queue graph processing as background task
        background_tasks.add_task(
            process_requisition_with_graph,
            correlation_id,
            request,
            request.request_id  # Pass request_id for audit trail
        )
        
        logger.info(f"Queued graph processing for correlation_id={correlation_id}")

        return RequisitionResponse(
            correlation_id=correlation_id,
            status="QUEUED_FOR_PROCESSING",
            received_at=req.received_at,
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
