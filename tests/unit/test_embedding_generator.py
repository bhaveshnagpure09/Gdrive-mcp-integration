import pytest
from unittest.mock import MagicMock, patch
from app.services.embedding_generator import EmbeddingGenerator


@pytest.fixture
def embedding_generator():
    with patch("app.services.embedding_generator.OllamaEmbeddings") as mock_ollama:
        mock_instance = MagicMock()
        mock_instance.embed_query.return_value = [0.1] * 300
        mock_instance.embed_documents.return_value = [[0.1] * 300, [0.2] * 300]
        mock_ollama.return_value = mock_instance
        yield EmbeddingGenerator()


def test_generate_embedding(embedding_generator):
    profile_text = "Software Engineer with 5 years of experience in Python."
    embedding = embedding_generator.generate(profile_text)
    assert isinstance(embedding, list)
    assert len(embedding) == 300


def test_generate_batch(embedding_generator):
    texts = ["Profile A", "Profile B"]
    embeddings = embedding_generator.generate_batch(texts)
    assert len(embeddings) == 2
    assert all(len(e) == 300 for e in embeddings)


def test_default_model_name():
    assert EmbeddingGenerator.MODEL_NAME == "nomic-embed-text"