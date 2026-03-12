"""Skill availability router."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.api.schemas.team_member import BulkUpsertRequest, BulkUpsertResponse, UpsertSummary
from app.db.repositories.team_member_repository import TeamMemberRepository
from app.db.session import get_db

router = APIRouter(prefix="/team-members/skill-availability", tags=["skill-availability"])


@router.post("/bulk-upsert", response_model=BulkUpsertResponse, status_code=202)
async def bulk_upsert_skill_availability(request: BulkUpsertRequest, db: Session = Depends(get_db)):
    """
    Bulk upsert team member skill availability data.

    This endpoint accepts batches of team member data including skills,
    allocations, and certifications. It implements idempotent upsert logic.
    """
    repo = TeamMemberRepository(db)

    # Ensure default category exists
    repo.ensure_default_category()

    # Statistics
    team_members_inserted = 0
    team_members_updated = 0
    skills_inserted = 0
    skills_updated = 0
    allocations_inserted = 0
    allocations_updated = 0
    records_failed = 0

    try:
        for member_data in request.team_members:
            try:
                # Create a savepoint so a single member failure doesn't kill the batch
                savepoint = db.begin_nested()
                try:
                    # Upsert team member
                    was_created, member = repo.upsert_team_member(member_data)
                    if was_created:
                        team_members_inserted += 1
                    else:
                        team_members_updated += 1

                    # Upsert skills
                    if member_data.skills:
                        s_inserted, s_updated = repo.upsert_skills(
                            member_data.team_member_id, member_data.skills
                        )
                        skills_inserted += s_inserted
                        skills_updated += s_updated

                    # Upsert allocations
                    if member_data.allocations:
                        a_inserted, a_updated = repo.upsert_allocations(
                            member_data.team_member_id, member_data.allocations
                        )
                        allocations_inserted += a_inserted
                        allocations_updated += a_updated

                    savepoint.commit()
                except Exception as inner_e:
                    savepoint.rollback()
                    records_failed += 1
                    logger.error("Error processing team member %s: %s", member_data.team_member_id, inner_e)

            except Exception as e:
                records_failed += 1
                logger.error("Savepoint error for %s: %s", member_data.team_member_id, e)

        # Commit all changes
        db.commit()

        # Create response summary
        summary = UpsertSummary(
            records_received=len(request.team_members),
            team_members_inserted=team_members_inserted,
            team_members_updated=team_members_updated,
            skills_inserted=skills_inserted,
            skills_updated=skills_updated,
            allocations_inserted=allocations_inserted,
            allocations_updated=allocations_updated,
            records_failed=records_failed,
            batch_id=request.metadata.batch_id,
            processed_at=datetime.now(timezone.utc),
        )

        return BulkUpsertResponse(
            status="ACCEPTED",
            message=f"Batch {request.metadata.batch_id} processed successfully",
            summary=summary,
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
