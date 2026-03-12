import hashlib
import logging
import os

from langchain_ollama import OllamaEmbeddings

logger = logging.getLogger(__name__)

_DEV_FALLBACK = os.environ.get("EMBEDDING_DEV_FALLBACK", "").lower() in ("1", "true", "yes")
_OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
_EMBEDDING_DIM = 768


def _deterministic_random_vector(text: str, dim: int = _EMBEDDING_DIM) -> list[float]:
    """Return a deterministic pseudo-random unit vector derived from text hash.
    Used only when EMBEDDING_DEV_FALLBACK=true (no Ollama available in dev)."""
    seed = int(hashlib.sha256(text.encode()).hexdigest(), 16)
    vec = []
    for i in range(dim):
        seed = (seed * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
        vec.append(((seed >> 33) / 0x7FFFFFFF) - 1.0)
    magnitude = sum(x * x for x in vec) ** 0.5 or 1.0
    return [x / magnitude for x in vec]


class EmbeddingGenerator:
    """Generates text embeddings using nomic-embed-text via Ollama (768-dim).

    Set EMBEDDING_DEV_FALLBACK=true to use a deterministic random vector instead
    of calling Ollama — useful when Ollama is not installed locally.
    """

    MODEL_NAME = "nomic-embed-text"

    def __init__(self, model_name: str = MODEL_NAME):
        self._model_name = model_name
        if not _DEV_FALLBACK:
            self.model = OllamaEmbeddings(model=model_name, base_url=_OLLAMA_BASE_URL)
        else:
            self.model = None
            logger.warning(
                "EMBEDDING_DEV_FALLBACK=true: using deterministic random vectors "
                "(not suitable for production)"
            )

    def generate(self, profile_text: str) -> list[float]:
        """Generate embedding vector for the given profile text."""
        if self.model is None:
            return _deterministic_random_vector(profile_text)
        return self.model.embed_query(profile_text)

    def generate_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embedding vectors for a list of texts."""
        if self.model is None:
            return [_deterministic_random_vector(t) for t in texts]
        return self.model.embed_documents(texts)