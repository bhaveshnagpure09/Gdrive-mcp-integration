"""Advanced embedding service using BGE-large-en-v1.5 (sentence-transformers).

Priority order
--------------
1. sentence-transformers BGE-large-en-v1.5   (best quality, local GPU/CPU)
2. sentence-transformers E5-large-v2          (alternative; set BGE_MODEL env)
3. Ollama nomic-embed-text                    (fallback when sentence-transformers
                                               is unavailable)
4. Deterministic hash vector                  (dev-only; set EMBEDDING_DEV_FALLBACK=1)

Environment variables
---------------------
BGE_MODEL          model name / HuggingFace repo id (default: BAAI/bge-large-en-v1.5)
BGE_DEVICE         "cpu" | "cuda" | "mps"  (default: auto-detect)
EMBEDDING_BACKEND  "bge" | "ollama" | "fallback"  (default: bge)
EMBEDDING_DEV_FALLBACK  "1" / "true"  forces deterministic fallback (dev only)
OLLAMA_BASE_URL    base URL for Ollama  (default: http://localhost:11434)
OLLAMA_MODEL       Ollama model name   (default: nomic-embed-text)
"""

from __future__ import annotations

import hashlib
import logging
import os
from functools import lru_cache

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
_DEV_FALLBACK    = os.environ.get("EMBEDDING_DEV_FALLBACK", "").lower() in ("1", "true", "yes")
_BACKEND         = os.environ.get("EMBEDDING_BACKEND", "bge").lower()
_BGE_MODEL       = os.environ.get("BGE_MODEL", "BAAI/bge-large-en-v1.5")
_BGE_DEVICE      = os.environ.get("BGE_DEVICE", None)  # None → auto-detect
_OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
_OLLAMA_MODEL    = os.environ.get("OLLAMA_MODEL", "nomic-embed-text")

# BGE-large-en-v1.5 produces 1024-dim vectors; nomic-embed-text → 768
_BGE_DIM = 1024
_OLD_DIM = 768

# ---------------------------------------------------------------------------
# Deterministic fallback (dev only)
# ---------------------------------------------------------------------------

def _deterministic_vector(text: str, dim: int = _BGE_DIM) -> list[float]:
    """Return a deterministic pseudo-random unit vector derived from text hash."""
    seed = int(hashlib.sha256(text.encode()).hexdigest(), 16)
    vec: list[float] = []
    for _ in range(dim):
        seed = (seed * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
        vec.append(((seed >> 33) / 0x7FFFFFFF) - 1.0)
    mag = sum(x * x for x in vec) ** 0.5 or 1.0
    return [x / mag for x in vec]


# Keep old name for any callers that imported it directly
_deterministic_random_vector = _deterministic_vector


# ---------------------------------------------------------------------------
# BGE / sentence-transformers backend
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _load_bge_model():
    """Load and cache the sentence-transformers model (loaded once per process)."""
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        device = _BGE_DEVICE
        if device is None:
            try:
                import torch  # type: ignore
                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"
        logger.info("Loading BGE embedding model %s on device=%s", _BGE_MODEL, device)
        model = SentenceTransformer(_BGE_MODEL, device=device)
        logger.info("BGE model loaded (dim=%d)", model.get_sentence_embedding_dimension())
        return model
    except Exception as exc:
        logger.warning("Could not load sentence-transformers (%s) — falling back to Ollama", exc)
        return None


def _bge_embed(text: str) -> list[float]:
    model = _load_bge_model()
    if model is None:
        return _ollama_embed(text)
    encoded = model.encode(
        "Represent this sentence for searching relevant passages: " + text,
        normalize_embeddings=True,
    )
    return encoded.tolist()


def _bge_embed_batch(texts: list[str]) -> list[list[float]]:
    model = _load_bge_model()
    if model is None:
        return _ollama_embed_batch(texts)
    prefixed = ["Represent this sentence for searching relevant passages: " + t for t in texts]
    encoded = model.encode(prefixed, normalize_embeddings=True, batch_size=32)
    return [v.tolist() for v in encoded]


# ---------------------------------------------------------------------------
# Ollama fallback backend
# ---------------------------------------------------------------------------

def _ollama_embed(text: str) -> list[float]:
    try:
        from langchain_ollama import OllamaEmbeddings  # type: ignore
        model = OllamaEmbeddings(model=_OLLAMA_MODEL, base_url=_OLLAMA_BASE_URL)
        return model.embed_query(text)
    except Exception as exc:
        logger.warning("Ollama embedding failed: %s — using deterministic fallback", exc)
        return _deterministic_vector(text, _OLD_DIM)


def _ollama_embed_batch(texts: list[str]) -> list[list[float]]:
    try:
        from langchain_ollama import OllamaEmbeddings  # type: ignore
        model = OllamaEmbeddings(model=_OLLAMA_MODEL, base_url=_OLLAMA_BASE_URL)
        return model.embed_documents(texts)
    except Exception as exc:
        logger.warning("Ollama batch embedding failed: %s", exc)
        return [_deterministic_vector(t, _OLD_DIM) for t in texts]


# ---------------------------------------------------------------------------
# Public EmbeddingGenerator (backward-compatible with existing usage)
# ---------------------------------------------------------------------------

class EmbeddingGenerator:
    """Generates text embeddings.

    Uses BGE-large-en-v1.5 by default; falls back gracefully to Ollama and
    then to a deterministic hash vector for dev environments.

    The ``dim`` property exposes the actual vector dimension so callers can
    store it correctly.
    """

    # Keep MODEL_NAME for backward-compat with any code that reads it
    MODEL_NAME = _BGE_MODEL

    def __init__(self, model_name: str | None = None):
        self._model_name = model_name or _BGE_MODEL
        if _DEV_FALLBACK:
            self._backend = "fallback"
            logger.warning(
                "EMBEDDING_DEV_FALLBACK=true — using deterministic vectors (not for production)"
            )
        else:
            self._backend = _BACKEND

    @property
    def dim(self) -> int:
        if self._backend == "bge":
            model = _load_bge_model()
            return model.get_sentence_embedding_dimension() if model else _OLD_DIM
        if self._backend == "ollama":
            return _OLD_DIM
        return _BGE_DIM  # fallback

    def generate(self, text: str) -> list[float]:
        """Generate a single embedding vector (query-style prefix applied)."""
        if self._backend == "fallback":
            return _deterministic_vector(text, _BGE_DIM)
        if self._backend == "bge":
            return _bge_embed(text)
        if self._backend == "ollama":
            return _ollama_embed(text)
        return _deterministic_vector(text, _BGE_DIM)

    def generate_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embedding vectors for a list of texts efficiently."""
        if not texts:
            return []
        if self._backend == "fallback":
            return [_deterministic_vector(t, _BGE_DIM) for t in texts]
        if self._backend == "bge":
            return _bge_embed_batch(texts)
        if self._backend == "ollama":
            return _ollama_embed_batch(texts)
        return [_deterministic_vector(t, _BGE_DIM) for t in texts]

    def generate_query(self, query_text: str) -> list[float]:
        """Encode a *query* (JD / job requirement) with the asymmetric query prefix."""
        if self._backend == "fallback":
            return _deterministic_vector(query_text, _BGE_DIM)
        if self._backend == "bge":
            model = _load_bge_model()
            if model is not None:
                encoded = model.encode(
                    "Represent this sentence for searching relevant passages: " + query_text,
                    normalize_embeddings=True,
                )
                return encoded.tolist()
            return _ollama_embed(query_text)
        if self._backend == "ollama":
            return _ollama_embed(query_text)
        return _deterministic_vector(query_text, _BGE_DIM)

    def generate_passage(self, passage_text: str) -> list[float]:
        """Encode a *passage* (resume chunk) — BGE passages use no query prefix."""
        if self._backend == "fallback":
            return _deterministic_vector(passage_text, _BGE_DIM)
        if self._backend == "bge":
            model = _load_bge_model()
            if model is not None:
                encoded = model.encode(passage_text, normalize_embeddings=True)
                return encoded.tolist()
            return _ollama_embed(passage_text)
        if self._backend == "ollama":
            return _ollama_embed(passage_text)
        return _deterministic_vector(passage_text, _BGE_DIM)

    def generate_passage_batch(self, passages: list[str]) -> list[list[float]]:
        """Encode a batch of *passages* (resume chunks) without query prefix."""
        if not passages:
            return []
        if self._backend == "fallback":
            return [_deterministic_vector(t, _BGE_DIM) for t in passages]
        if self._backend == "bge":
            model = _load_bge_model()
            if model is not None:
                encoded = model.encode(passages, normalize_embeddings=True, batch_size=32)
                return [v.tolist() for v in encoded]
            return _ollama_embed_batch(passages)
        if self._backend == "ollama":
            return _ollama_embed_batch(passages)
        return [_deterministic_vector(t, _BGE_DIM) for t in passages]
