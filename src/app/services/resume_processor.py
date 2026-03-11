"""Resume processing pipeline: MCP fetch → PII scrub → profile text → embedding."""

import logging
from dataclasses import dataclass, field
from typing import Optional

from app.core.mcp_client import GoogleDriveMCPClient, GDriveError
from app.core.pii_scrubber import PIIScrubber, ResumeParser

logger = logging.getLogger(__name__)


@dataclass
class ProcessedResume:
    """Output of the resume processing pipeline for a single document."""

    doc_id: str
    profile_text: str
    scrubbed_text: str
    parsed_fields: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None

    @property
    def extracted_team_member_id(self) -> str:
        return self.parsed_fields.get("team_member_id", "")


class ResumeProcessor:
    """Orchestrates resume retrieval, PII scrubbing, and profile text construction."""

    def __init__(self, mcp_client: GoogleDriveMCPClient) -> None:
        self.mcp_client = mcp_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_single(self, doc_id: str, storage_source: str = "gdrive") -> ProcessedResume:
        """Fetch and process a single resume document.

        Args:
            doc_id: Google Drive document ID.
            storage_source: Label for the storage origin (stored in metadata).

        Returns:
            :class:`ProcessedResume` — check ``result.success`` before using.
        """
        logger.info("Processing single resume", extra={"doc_id": doc_id})
        try:
            raw_text = self.mcp_client.fetch_resume(doc_id)
        except GDriveError as exc:
            logger.error("Failed to fetch resume from Google Drive", extra={"doc_id": doc_id, "error": str(exc)})
            return ProcessedResume(doc_id=doc_id, profile_text="", scrubbed_text="", error=str(exc))

        return self._build_result(doc_id=doc_id, raw_text=raw_text, storage_source=storage_source)

    def process_all(self, storage_source: str = "gdrive") -> list[ProcessedResume]:
        """Fetch and process all resume documents from Google Drive.

        Returns:
            List of :class:`ProcessedResume` objects (may contain failed items).
        """
        logger.info("Processing all resumes from Google Drive")
        try:
            files = self.mcp_client.list_resumes()
        except GDriveError as exc:
            logger.error("Failed to list resumes from Google Drive", extra={"error": str(exc)})
            return []

        results: list[ProcessedResume] = []
        for f in files:
            doc_id = f.get("id", "")
            result = self.process_single(doc_id=doc_id, storage_source=storage_source)
            results.append(result)
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_result(self, *, doc_id: str, raw_text: str, storage_source: str) -> ProcessedResume:
        if not raw_text.strip():
            msg = f"Empty resume document: {doc_id}"
            logger.warning(msg)
            return ProcessedResume(doc_id=doc_id, profile_text="", scrubbed_text="", error=msg)

        try:
            scrubbed = PIIScrubber.scrub(raw_text)
            # Extract structured fields from the resume text
            parsed_fields = ResumeParser.extract_all(scrubbed)
            # Build rich profile text with all extracted structured data
            profile_text = PIIScrubber.build_profile_text(
                designation=parsed_fields.get("designation", ""),
                experience_months=parsed_fields.get("experience_months", 0),
                skills=parsed_fields.get("skills") or [],
                resume_text=scrubbed,
            )
        except Exception as exc:
            msg = f"Resume processing error for {doc_id}: {exc}"
            logger.error(msg)
            return ProcessedResume(doc_id=doc_id, profile_text="", scrubbed_text="", error=msg)

        metadata = {
            "storage_source": storage_source,
            "document_id": doc_id,
        }
        return ProcessedResume(
            doc_id=doc_id,
            profile_text=profile_text,
            scrubbed_text=scrubbed,
            parsed_fields=parsed_fields,
            metadata=metadata,
        )
