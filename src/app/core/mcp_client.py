"""Google Drive MCP client with OAuth2 authentication and retry logic."""

import io
import logging
import time
from typing import Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

logger = logging.getLogger(__name__)

# Mime type used by Google Docs
_GDOC_MIME = "application/vnd.google-apps.document"
# Export as plain text for resume extraction
_EXPORT_MIME = "text/plain"

_DEFAULT_BACKOFF_BASE = 2.0   # seconds
_DEFAULT_MAX_RETRIES = 3


class GDriveError(Exception):
    """Raised for unrecoverable Google Drive errors."""


class GoogleDriveMCPClient:
    """MCP client for Google Drive.

    Fetches resume documents from Google Drive using the Drive v3 API.
    All network calls are wrapped with exponential-backoff retry.
    """

    def __init__(
        self,
        credentials_path: str,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        backoff_base: float = _DEFAULT_BACKOFF_BASE,
    ) -> None:
        self.credentials_path = credentials_path
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.credentials: Optional[Credentials] = None
        self.service = None

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def authenticate(self) -> None:
        """Load OAuth2 credentials and build the Drive service."""
        self.credentials = Credentials.from_authorized_user_file(self.credentials_path)
        self.service = build("drive", "v3", credentials=self.credentials)
        logger.info("Google Drive MCP client authenticated")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_resume(self, doc_id: str) -> str:
        """Fetch plain-text content of a single Google Doc by its ID.

        Args:
            doc_id: The Google Drive document ID.

        Returns:
            Plain-text content of the document.

        Raises:
            GDriveError: When the document cannot be retrieved.
        """
        self._ensure_authenticated()
        logger.info("Fetching resume", extra={"doc_id": doc_id})
        return self._retry(self._export_doc_text, doc_id)

    def list_resumes(self) -> list[dict]:
        """List all Google Docs in the authenticated account's Drive.

        Returns:
            List of file metadata dicts with at least ``id`` and ``name``.
        """
        self._ensure_authenticated()
        logger.info("Listing all resume documents from Google Drive")
        return self._retry(self._list_docs)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_authenticated(self) -> None:
        if self.service is None:
            raise GDriveError("Client not authenticated. Call authenticate() first.")

    def _export_doc_text(self, doc_id: str) -> str:
        """Export a Google Doc as plain text."""
        request = self.service.files().export_media(fileId=doc_id, mimeType=_EXPORT_MIME)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return fh.getvalue().decode("utf-8", errors="replace")

    def _list_docs(self) -> list[dict]:
        """Query Drive for all Google Docs files."""
        results = (
            self.service.files()
            .list(
                q=f"mimeType='{_GDOC_MIME}' and trashed=false",
                fields="files(id, name)",
                pageSize=200,
            )
            .execute()
        )
        return results.get("files", [])

    def _retry(self, fn, *args, **kwargs):
        """Call *fn* with exponential backoff on transient HTTP errors."""
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return fn(*args, **kwargs)
            except HttpError as exc:
                status = exc.resp.status
                if status == 403:
                    raise GDriveError(
                        f"Permission denied accessing document. "
                        f"Ensure the doc is shared with the authenticated account."
                    ) from exc
                if status == 404:
                    raise GDriveError(f"Document not found (HTTP 404).") from exc
                # 429 / 5xx → retry
                wait = self.backoff_base ** attempt
                logger.warning(
                    "Drive API transient error, retrying",
                    extra={"attempt": attempt, "status": status, "wait_s": wait},
                )
                last_exc = exc
                time.sleep(wait)
            except Exception as exc:
                raise GDriveError(f"Unexpected error communicating with Google Drive: {exc}") from exc

        raise GDriveError(
            f"Google Drive request failed after {self.max_retries} retries."
        ) from last_exc