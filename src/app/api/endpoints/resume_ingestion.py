"""Resume ingestion endpoint: FastAPI route that drives the full MCP pipeline."""

import logging
import os
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.mcp_client import GoogleDriveMCPClient, GDriveError, extract_drive_id
from app.core.pii_scrubber import PIIScrubber
from app.db.models.models import ResumeChunkEmbedding, TeamMember as TeamMemberModel
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
    folder_id: Optional[str] = None  # GDrive folder ID; None = entire Drive


class IngestionResult(BaseModel):
    ingested: int
    skipped: int = 0
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


def _index_chunks_into_faiss(
    *,
    doc_id: str,
    effective_member_id: str,
    result,  # ProcessedResume
    embedder: EmbeddingGenerator,
    db: Session,
) -> None:
    """Index resume chunks into FAISS and persist metadata rows to PostgreSQL.

    This is a best-effort operation: any exception is logged but not re-raised
    so the main ingestion flow is never blocked by vector-store errors.
    """
    if not result.chunks:
        logger.debug("No chunks to index for doc_id=%s", doc_id)
        return

    try:
        from app.services.vector_store import FaissVectorStore, ChunkMetadata

        parsed_fields = result.parsed_fields
        skills_list: list[str] = parsed_fields.get("skills") or []
        years_exp: float = (parsed_fields.get("experience_months") or 0) / 12.0
        role: str = parsed_fields.get("designation") or ""
        full_name: str = parsed_fields.get("name") or ""

        chunk_texts = [c.text for c in result.chunks]
        vectors = embedder.generate_passage_batch(chunk_texts)

        chunk_metas = [
            ChunkMetadata(
                candidate_id=effective_member_id,
                section_type=c.section_type,
                skills=skills_list,
                years_of_experience=years_exp,
                role=role,
                full_name=full_name,
                doc_id=doc_id,
                raw_text=c.text[:512],
            )
            for c in result.chunks
        ]

        store = FaissVectorStore.get_instance(dim=embedder.dim)
        faiss_ids = store.upsert_chunks(
            candidate_id=effective_member_id,
            chunks_meta=chunk_metas,
            vectors=vectors,
        )

        # Persist ResumeChunkEmbedding rows to PostgreSQL for SQL-side filtering
        import json as _json
        try:
            # Remove any existing rows for this doc so re-ingestion stays idempotent
            db.query(ResumeChunkEmbedding).filter(
                ResumeChunkEmbedding.doc_id == doc_id
            ).delete()

            for chunk, meta, fid, vec in zip(result.chunks, chunk_metas, faiss_ids, vectors):
                db.add(ResumeChunkEmbedding(
                    team_member_id=effective_member_id,
                    doc_id=doc_id,
                    section_type=chunk.section_type,
                    chunk_text=chunk.text,
                    embedding=_json.dumps(vec.tolist() if hasattr(vec, "tolist") else list(vec)),
                    faiss_id=int(fid),
                    skills=skills_list,
                    years_of_experience=years_exp,
                    role=role,
                    full_name=full_name,
                    metadata_json={"doc_id": doc_id, "source": "gdrive"},
                ))
            db.commit()
            logger.info(
                "Indexed %d chunks for doc_id=%s (FAISS + DB)",
                len(result.chunks),
                doc_id,
            )
        except Exception as db_exc:
            db.rollback()
            logger.warning("Failed to persist chunk embeddings to DB: %s", db_exc)

    except Exception as exc:
        logger.warning("Chunk FAISS indexing failed for doc_id=%s: %s", doc_id, exc)


def _ingest_one(
    *,
    doc_id: str,
    team_member_id: Optional[str],
    file_name: Optional[str] = None,
    mime_type: Optional[str] = None,
    modified_time: Optional[str] = None,
    processor: ResumeProcessor,
    embedder: EmbeddingGenerator,
    repo: EmbeddingRepository,
    db: Session,
    storage: str,
) -> dict:
    """Run the full pipeline for a single document. Returns a status dict."""
    base = {"doc_id": doc_id, "file_name": file_name or doc_id}

    # ------------------------------------------------------------------ #
    # Idempotency pre-check: skip if already ingested and file unchanged   #
    # ------------------------------------------------------------------ #
    existing = repo.get_by_source_doc_id(doc_id)
    is_update = False
    if existing:
        stored_modified_time = (existing.metadata_json or {}).get("modified_time")
        if modified_time and stored_modified_time and stored_modified_time == modified_time:
            # File has not changed since last ingestion — skip
            return {
                **base,
                "status": "already_ingested",
                "team_member_id": existing.team_member_id,
                "extracted_name": (existing.metadata_json or {}).get("extracted_name", ""),
                "skills_found": len((existing.metadata_json or {}).get("skills", [])),
                "experience_months": (existing.metadata_json or {}).get("experience_months"),
                "reason": "Skipped — no changes since last ingestion",
            }
        # modified_time differs (or unknown) → will re-ingest
        is_update = True
        logger.info(
            "Resume changed since last ingestion, re-ingesting",
            extra={"doc_id": doc_id, "stored_mt": stored_modified_time, "new_mt": modified_time},
        )

    result = processor.process_single(doc_id=doc_id, storage_source=storage, mime_type=mime_type)
    if not result.success:
        return {**base, "status": "failed", "reason": result.error}

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
        return {**base, "status": "failed", "reason": f"Team member upsert error: {exc}"}

    try:
        embedding = embedder.generate(result.profile_text)
    except Exception as exc:
        logger.error("Embedding generation failed", extra={"doc_id": doc_id, "error": str(exc)})
        return {**base, "status": "failed", "reason": f"Embedding error: {exc}"}

    # Build rich metadata with all parsed fields
    rich_metadata = {
        **result.metadata,
        "source_doc_id": doc_id,
        "modified_time": modified_time,
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
        return {**base, "status": "failed", "reason": f"DB error: {exc}"}

    # ------------------------------------------------------------------ #
    # FAISS + DB chunk indexing (best-effort — does not fail the request)  #
    # ------------------------------------------------------------------ #
    _index_chunks_into_faiss(
        doc_id=doc_id,
        effective_member_id=effective_member_id,
        result=result,
        embedder=embedder,
        db=db,
    )

    return {
        **base,
        "status": "updated" if is_update else "ok",
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

    # Strip full GDrive URLs to bare IDs (safety net for both fields)
    if request.folder_id:
        request.folder_id = extract_drive_id(request.folder_id)
    if request.doc_id:
        request.doc_id = extract_drive_id(request.doc_id)

    mcp_client = _build_mcp_client()
    processor = ResumeProcessor(mcp_client=mcp_client)
    embedder = EmbeddingGenerator()
    repo = EmbeddingRepository(db=db)

    details: list[dict] = []

    if request.fetch_all:
        # Batch: process all documents from the selected storage
        try:
            files = mcp_client.list_resumes(folder_id=request.folder_id)
        except GDriveError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

        for f in files:
            doc_id = f.get("id", "")
            item = _ingest_one(
                doc_id=doc_id,
                team_member_id=None,  # batch mode: extract from resume
                file_name=f.get("name", ""),
                mime_type=f.get("mimeType"),
                modified_time=f.get("modifiedTime"),
                processor=processor,
                embedder=embedder,
                repo=repo,
                db=db,
                storage=request.storage,
            )
            details.append(item)
    else:
        # Single doc: fetch modifiedTime from Drive so idempotency check works
        modified_time: Optional[str] = None
        single_mime: Optional[str] = None
        try:
            file_info = mcp_client.get_file_info(request.doc_id)
            modified_time = file_info.get("modifiedTime")
            single_mime = file_info.get("mimeType")
        except Exception as exc:
            logger.warning("Could not fetch file info for idempotency check", extra={"doc_id": request.doc_id, "error": str(exc)})

        item = _ingest_one(
            doc_id=request.doc_id,
            team_member_id=request.team_member_id,  # None → auto-extracted
            file_name=None,
            mime_type=single_mime,
            modified_time=modified_time,
            processor=processor,
            embedder=embedder,
            repo=repo,
            db=db,
            storage=request.storage,
        )
        details.append(item)

    ingested = sum(1 for d in details if d["status"] in ("ok", "updated"))
    skipped = sum(1 for d in details if d["status"] == "already_ingested")
    failed = len(details) - ingested - skipped
    return IngestionResult(ingested=ingested, skipped=skipped, failed=failed, details=details)
