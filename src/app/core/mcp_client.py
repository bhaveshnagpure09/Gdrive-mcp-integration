"""Google Drive MCP client with OAuth2 authentication and retry logic."""

import io
import logging
import re
import time
from typing import Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

logger = logging.getLogger(__name__)

# MIME types for Google-native and binary resume formats
_GDOC_MIME = "application/vnd.google-apps.document"
_PDF_MIME = "application/pdf"
_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_DOC_MIME = "application/msword"

# All resume-capable MIME types listed in a single Drive query
_RESUME_MIME_TYPES = [_GDOC_MIME, _PDF_MIME, _DOCX_MIME, _DOC_MIME]

# Export format for Google Docs
_EXPORT_MIME = "text/plain"

_DEFAULT_BACKOFF_BASE = 2.0   # seconds
_DEFAULT_MAX_RETRIES = 3


def extract_drive_id(raw: str) -> str:
    """Extract a Google Drive file or folder ID from a full URL, or return as-is.

    Handles patterns:
    - https://drive.google.com/drive/folders/FOLDER_ID
    - https://drive.google.com/drive/u/0/folders/FOLDER_ID
    - https://docs.google.com/document/d/DOC_ID/edit
    - https://drive.google.com/file/d/FILE_ID/view
    """
    if not raw:
        return raw
    stripped = raw.strip()
    if not stripped.startswith("http"):
        return stripped
    m = re.search(r"/(?:folders|d|file/d)/([a-zA-Z0-9_-]{10,})", stripped)
    return m.group(1) if m else stripped


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

    def fetch_resume(self, doc_id: str, mime_type: Optional[str] = None) -> str:
        """Fetch plain-text content of a resume document.

        Dispatches to the correct download+extraction method based on MIME type:
        - Google Docs  → Drive export API (text/plain)
        - PDF          → raw download + pypdf text extraction
        - DOCX / DOC   → raw download + python-docx text extraction

        Args:
            doc_id: The Google Drive document ID.
            mime_type: MIME type of the file. Defaults to Google Docs if omitted.

        Returns:
            Plain-text content of the document.

        Raises:
            GDriveError: When the document cannot be retrieved or parsed.
        """
        self._ensure_authenticated()
        effective_mime = mime_type or _GDOC_MIME
        logger.info("Fetching resume", extra={"doc_id": doc_id, "mime_type": effective_mime})

        if effective_mime == _GDOC_MIME:
            return self._retry(self._export_doc_text, doc_id)
        elif effective_mime == _PDF_MIME:
            raw = self._retry(self._download_file_bytes, doc_id)
            return self._extract_pdf_text(raw)
        elif effective_mime in (_DOCX_MIME, _DOC_MIME):
            raw = self._retry(self._download_file_bytes, doc_id)
            return self._extract_docx_text(raw)
        else:
            raise GDriveError(f"Unsupported resume format: {effective_mime}")

    def list_resumes(self, folder_id: Optional[str] = None) -> list[dict]:
        """List resume files from Drive, optionally scoped to a folder.

        Returns dicts with keys: ``id``, ``name``, ``mimeType``, ``modifiedTime``.
        """
        self._ensure_authenticated()
        if folder_id:
            logger.info(
                "Listing resume documents from folder",
                extra={"folder_id": folder_id},
            )
        else:
            logger.info("Listing all resume documents from Google Drive")
        return self._retry(self._list_docs, folder_id)

    def get_file_info(self, doc_id: str) -> dict:
        """Return lightweight metadata (id, name, mimeType, modifiedTime) for a single file."""
        self._ensure_authenticated()
        return self._retry(self._fetch_file_info, doc_id)

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

    def _download_file_bytes(self, doc_id: str) -> bytes:
        """Download raw binary content of a non-Google-native file (PDF, DOCX, etc.)."""
        request = self.service.files().get_media(fileId=doc_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return fh.getvalue()

    def _extract_pdf_text(self, raw_bytes: bytes) -> str:
        """Extract plain text from PDF bytes using pypdf."""
        try:
            from pypdf import PdfReader  # noqa: PLC0415
        except ImportError as exc:
            raise GDriveError("pypdf is required for PDF ingestion. Install it via: pip install pypdf") from exc
        reader = PdfReader(io.BytesIO(raw_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages).strip()

    def _extract_docx_text(self, raw_bytes: bytes) -> str:
        """Extract plain text from DOCX/DOC bytes using python-docx."""
        try:
            from docx import Document  # noqa: PLC0415
        except ImportError as exc:
            raise GDriveError("python-docx is required for DOCX ingestion. Install it via: pip install python-docx") from exc
        doc = Document(io.BytesIO(raw_bytes))
        lines: list[str] = [p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(c.text.strip() for c in row.cells if c.text.strip())
                if row_text:
                    lines.append(row_text)
        return "\n".join(lines).strip()

    def _list_docs(self, folder_id: Optional[str] = None) -> list[dict]:
        """Query Drive for resume files (Google Docs, PDF, DOCX, DOC), optionally within a folder."""
        mime_q = " or ".join(f"mimeType='{m}'" for m in _RESUME_MIME_TYPES)
        query = f"({mime_q}) and trashed=false"
        if folder_id:
            query += f" and '{folder_id}' in parents"
        results = (
            self.service.files()
            .list(
                q=query,
                fields="files(id, name, mimeType, modifiedTime)",
                pageSize=500,
            )
            .execute()
        )
        return results.get("files", [])

    def _fetch_file_info(self, doc_id: str) -> dict:
        """Fetch lightweight metadata for a single file."""
        return (
            self.service.files()
            .get(fileId=doc_id, fields="id,name,mimeType,modifiedTime")
            .execute()
        )

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