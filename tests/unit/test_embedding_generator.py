import pytest
from unittest.mock import patch
from app.services.embedding_generator import EmbeddingGenerator, _BGE_DIM


@pytest.fixture
def embedding_generator():
    """Return an EmbeddingGenerator using the deterministic fallback so no ML model is needed."""
    with patch("app.services.embedding_generator._DEV_FALLBACK", True):
        yield EmbeddingGenerator()


def test_generate_embedding(embedding_generator):
    profile_text = "Software Engineer with 5 years of experience in Python."
    embedding = embedding_generator.generate(profile_text)
    assert isinstance(embedding, list)
    assert len(embedding) == _BGE_DIM


def test_generate_batch(embedding_generator):
    texts = ["Profile A", "Profile B"]
    embeddings = embedding_generator.generate_batch(texts)
    assert len(embeddings) == 2
    assert all(len(e) == _BGE_DIM for e in embeddings)


def test_default_model_name():
    assert EmbeddingGenerator.MODEL_NAME == "BAAI/bge-large-en-v1.5"
