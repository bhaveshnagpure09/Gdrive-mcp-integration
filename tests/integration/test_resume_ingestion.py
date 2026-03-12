"""Integration tests for the resume ingestion endpoint."""

from unittest.mock import MagicMock, patch

import sqlalchemy.pool
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.endpoints.resume_ingestion import router
from app.db.base import Base
from app.db.session import get_db

# Import all models so Base.metadata knows about them
import app.db.models.models as _  # noqa: F401

# ---------------------------------------------------------------------------
# In-memory test database
# ---------------------------------------------------------------------------
TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=sqlalchemy.pool.StaticPool,
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    Base.metadata.create_all(bind=engine)
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


# Stand-alone test app (no auth middleware)
test_app = FastAPI()
test_app.include_router(router)
test_app.dependency_overrides[get_db] = override_get_db

client = TestClient(test_app)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
FAKE_RESUME_TEXT = "John Doe\nSoftware Engineer\nskills: Python, FastAPI"
FAKE_EMBEDDING = [0.1] * 300


def _mock_mcp_single(doc_id: str = "doc_123"):
    mock = MagicMock()
    mock.fetch_resume.return_value = FAKE_RESUME_TEXT
    mock.list_resumes.return_value = [{"id": doc_id, "name": "Resume.docx"}]
    mock.get_file_info.return_value = {"modifiedTime": None, "mimeType": None}
    return mock


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------

def test_invalid_storage():
    response = client.post(
        "/ingest-resume",
        json={"doc_id": "test_doc_id", "storage": "invalid_storage"},
    )
    assert response.status_code == 400
    assert "Only Google Drive is supported" in response.json()["detail"]


def test_missing_doc_id_and_fetch_all():
    response = client.post("/ingest-resume", json={"storage": "gdrive"})
    assert response.status_code == 400


def test_missing_storage_field():
    response = client.post("/ingest-resume", json={"doc_id": "test_doc_id"})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Single resume ingestion
# ---------------------------------------------------------------------------

@patch("app.api.endpoints.resume_ingestion.EmbeddingGenerator")
@patch("app.api.endpoints.resume_ingestion._build_mcp_client")
def test_ingest_resume_single(mock_build_client, mock_embedder_cls):
    mock_build_client.return_value = _mock_mcp_single("doc_abc")
    mock_embedder_cls.return_value.generate.return_value = FAKE_EMBEDDING

    response = client.post("/ingest-resume", json={"doc_id": "doc_abc", "storage": "gdrive"})
    assert response.status_code == 200
    body = response.json()
    assert body["ingested"] == 1
    assert body["failed"] == 0
    assert body["details"][0]["doc_id"] == "doc_abc"
    assert body["details"][0]["status"] == "ok"


# ---------------------------------------------------------------------------
# Batch ingestion
# ---------------------------------------------------------------------------

@patch("app.api.endpoints.resume_ingestion.EmbeddingGenerator")
@patch("app.api.endpoints.resume_ingestion._build_mcp_client")
def test_ingest_resume_batch(mock_build_client, mock_embedder_cls):
    mock_client = MagicMock()
    mock_client.list_resumes.return_value = [
        {"id": "d1", "name": "R1.docx"},
        {"id": "d2", "name": "R2.docx"},
    ]
    mock_client.fetch_resume.return_value = FAKE_RESUME_TEXT
    mock_build_client.return_value = mock_client
    mock_embedder_cls.return_value.generate.return_value = FAKE_EMBEDDING

    response = client.post("/ingest-resume", json={"fetch_all": True, "storage": "gdrive"})
    assert response.status_code == 200
    body = response.json()
    assert body["ingested"] == 2
    assert body["failed"] == 0


# ---------------------------------------------------------------------------
# Error / edge-case tests
# ---------------------------------------------------------------------------

@patch("app.api.endpoints.resume_ingestion.EmbeddingGenerator")
@patch("app.api.endpoints.resume_ingestion._build_mcp_client")
def test_ingest_empty_document_counted_as_failure(mock_build_client, mock_embedder_cls):
    mock_client = MagicMock()
    mock_client.fetch_resume.return_value = "   "  # whitespace only
    mock_build_client.return_value = mock_client
    mock_embedder_cls.return_value.generate.return_value = FAKE_EMBEDDING

    response = client.post("/ingest-resume", json={"doc_id": "empty_doc", "storage": "gdrive"})
    assert response.status_code == 200
    body = response.json()
    assert body["failed"] == 1
    assert body["ingested"] == 0


@patch("app.api.endpoints.resume_ingestion.EmbeddingGenerator")
@patch("app.api.endpoints.resume_ingestion._build_mcp_client")
def test_ingest_duplicate_updates_existing(mock_build_client, mock_embedder_cls):
    mock_build_client.return_value = _mock_mcp_single("dup_doc")
    mock_embedder_cls.return_value.generate.return_value = FAKE_EMBEDDING

    # First call -> insert
    r1 = client.post("/ingest-resume", json={"doc_id": "dup_doc", "storage": "gdrive"})
    # Second call -> upsert (must not raise)
    r2 = client.post("/ingest-resume", json={"doc_id": "dup_doc", "storage": "gdrive"})
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r2.json()["ingested"] == 1


@patch("app.api.endpoints.resume_ingestion._build_mcp_client")
def test_gdrive_auth_failure_returns_503(mock_build_client):
    from fastapi import HTTPException

    mock_build_client.side_effect = HTTPException(status_code=503, detail="auth failed")

    response = client.post("/ingest-resume", json={"doc_id": "x", "storage": "gdrive"})
    assert response.status_code == 503