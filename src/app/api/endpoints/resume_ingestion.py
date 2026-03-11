"""Resume ingestion endpoint: FastAPI route that drives the full MCP pipeline."""

import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.mcp_client import GoogleDriveMCPClient, GDriveError
from app.core.pii_scrubber import PIIScrubber
from app.db.models.models import TeamMember as TeamMemberModel
from app.db.repositories.embedding_repository import EmbeddingRepository
from app.db.session import get_db
from app.services.embedding_generator import EmbeddingGenerator
from app.services.resume_processor import ResumeProcessor

logger = logging.getLogger(__name__)

router = APIRouter()

# Path to OAuth2 credentials; override via GDRIVE_CREDENTIALS_PATH env var
_CREDENTIALS_PATH = os.environ.get("GDRIVE_CREDENTIALS_PATH", "credentials.json")


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class ResumeIngestionRequest(BaseModel):
    doc_id: Optional[str] = None
    team_member_id: Optional[str] = None  # system ID; defaults to doc_id if omitted
    fetch_all: Optional[bool] = False
    storage: str


class IngestionResult(BaseModel):
    ingested: int
    failed: int
    details: list[dict]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_mcp_client() -> GoogleDriveMCPClient:
    client = GoogleDriveMCPClient(credentials_path=_CREDENTIALS_PATH)
    try:
        client.authenticate()
    except Exception as exc:
        logger.error("GDrive authentication failed", extra={"error": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Google Drive authentication failed: {exc}",
        ) from exc
    return client


def _ensure_team_member(db: Session, team_member_id: str, parsed_fields: dict) -> None:
    """Auto-create a team_member row from parsed resume data if it doesn't exist."""
    existing = (
        db.query(TeamMemberModel)
        .filter(TeamMemberModel.team_member_id == team_member_id)
        .first()
    )
    if existing:
        # Update experience and designation if we extracted better data
        if parsed_fields.get("experience_months"):
            existing.experience_in_months = parsed_fields["experience_months"]
        if parsed_fields.get("designation") and not existing.designation:
            existing.designation = parsed_fields["designation"]
        db.flush()
    else:
        new_member = TeamMemberModel(
            team_member_id=team_member_id,
            designation=parsed_fields.get("designation", ""),
            experience_in_months=parsed_fields.get("experience_months", 0),
            is_active=True,
        )
        db.add(new_member)
        db.flush()
        logger.info("Auto-created team_member", extra={"team_member_id": team_member_id})


def _ingest_one(
    *,
    doc_id: str,
    team_member_id: Optional[str],
    processor: ResumeProcessor,
    embedder: EmbeddingGenerator,
    repo: EmbeddingRepository,
    db: Session,
    storage: str,
) -> dict:
    """Run the full pipeline for a single document. Returns a status dict."""
    result = processor.process_single(doc_id=doc_id, storage_source=storage)
    if not result.success:
        return {"doc_id": doc_id, "status": "failed", "reason": result.error}

    # Resolve team_member_id: provided > extracted from resume > fallback to doc_id
    effective_member_id = (
        team_member_id
        or result.extracted_team_member_id
        or doc_id
    )

    # Auto-ensure team_member row exists
    try:
        _ensure_team_member(db, effective_member_id, result.parsed_fields)
    except Exception as exc:
        db.rollback()
        logger.error("Failed to upsert team_member", extra={"team_member_id": effective_member_id, "error": str(exc)})
        return {"doc_id": doc_id, "status": "failed", "reason": f"Team member upsert error: {exc}"}

    try:
        embedding = embedder.generate(result.profile_text)
    except Exception as exc:
        logger.error("Embedding generation failed", extra={"doc_id": doc_id, "error": str(exc)})
        return {"doc_id": doc_id, "status": "failed", "reason": f"Embedding error: {exc}"}

    # Build rich metadata with all parsed fields
    rich_metadata = {
        **result.metadata,
        "extracted_name": result.parsed_fields.get("name", ""),
        "designation": result.parsed_fields.get("designation", ""),
        "experience_months": result.parsed_fields.get("experience_months", 0),
        "skills": result.parsed_fields.get("skills", []),
        "team_member_id_source": "provided" if team_member_id else "extracted",
    }

    try:
        repo.upsert(
            team_member_id=effective_member_id,
            embedding=embedding,
            profile_text=result.profile_text,
            metadata=rich_metadata,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("DB insertion failed", extra={"doc_id": doc_id, "error": str(exc)})
        return {"doc_id": doc_id, "status": "failed", "reason": f"DB error: {exc}"}

    return {
        "doc_id": doc_id,
        "status": "ok",
        "team_member_id": effective_member_id,
        "extracted_name": result.parsed_fields.get("name", ""),
        "skills_found": len(result.parsed_fields.get("skills", [])),
        "experience_months": result.parsed_fields.get("experience_months", 0),
    }


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/ingest-resume", response_model=IngestionResult)
async def ingest_resume(
    request: ResumeIngestionRequest,
    db: Session = Depends(get_db),
) -> IngestionResult:
    """Trigger resume ingestion from a connected MCP storage source.

    - **doc_id** + **storage="gdrive"** → ingest a single Google Doc.
    - **fetch_all=true** + **storage="gdrive"** → ingest all Google Docs.
    - **storage="all"** → ingest from all connected MCP servers (future).
    """
    if request.storage not in ("gdrive", "all"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only Google Drive is supported in this implementation.",
        )

    if not request.fetch_all and not request.doc_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either 'doc_id' or set 'fetch_all' to true.",
        )

    mcp_client = _build_mcp_client()
    processor = ResumeProcessor(mcp_client=mcp_client)
    embedder = EmbeddingGenerator()
    repo = EmbeddingRepository(db=db)

    details: list[dict] = []

    if request.fetch_all:
        # Batch: process all documents from the selected storage
        try:
            files = mcp_client.list_resumes()
        except GDriveError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

        for f in files:
            doc_id = f.get("id", "")
            item = _ingest_one(
                doc_id=doc_id,
                team_member_id=None,  # batch mode: extract from resume
                processor=processor,
                embedder=embedder,
                repo=repo,
                db=db,
                storage=request.storage,
            )
            details.append(item)
    else:
        item = _ingest_one(
            doc_id=request.doc_id,
            team_member_id=request.team_member_id,  # None → auto-extracted
            processor=processor,
            embedder=embedder,
            repo=repo,
            db=db,
            storage=request.storage,
        )
        details.append(item)

    ingested = sum(1 for d in details if d["status"] == "ok")
    failed = len(details) - ingested
    return IngestionResult(ingested=ingested, failed=failed, details=details)
