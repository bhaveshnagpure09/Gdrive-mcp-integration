import pytest
from unittest.mock import MagicMock, patch
from app.core.mcp_client import GoogleDriveMCPClient


@pytest.fixture
def mcp_client():
    with patch("app.core.mcp_client.build") as mock_build, \
         patch("app.core.mcp_client.Credentials") as mock_creds:
        mock_creds.from_authorized_user_file.return_value = MagicMock()
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        client = GoogleDriveMCPClient("path/to/credentials.json")
        client.authenticate()
        yield client


def test_fetch_resume(mcp_client):
    doc_id = "test_doc_id"
    with patch("app.core.mcp_client.MediaIoBaseDownload") as mock_dl_cls:
        def fake_downloader(fh, request):
            fh.write(b"John Doe\nSoftware Engineer")
            mock_dl = MagicMock()
            mock_dl.next_chunk.return_value = (None, True)
            return mock_dl

        mock_dl_cls.side_effect = fake_downloader
        document = mcp_client.fetch_resume(doc_id)

    assert isinstance(document, str)
    assert "John Doe" in document


def test_list_resumes(mcp_client):
    mcp_client.service.files.return_value.list.return_value.execute.return_value = {
        "files": [{"id": "abc", "name": "Resume1.docx"}]
    }
    resumes = mcp_client.list_resumes()
    assert isinstance(resumes, list)
    assert len(resumes) == 1


def test_list_resumes_empty(mcp_client):
    mcp_client.service.files.return_value.list.return_value.execute.return_value = {}
    resumes = mcp_client.list_resumes()
    assert resumes == []