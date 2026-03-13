"""FAISS-backed vector store for resume chunk embeddings.

Architecture
------------
* Each resume is split into sections (skills, experience, projects, …).
* Every section is stored as a separate FAISS vector with a metadata dict.
* The FAISS index is persisted to disk under VECTOR_STORE_DIR (default:
  ``./data/faiss_index``).
* A companion JSON file (``metadata.json``) maps integer FAISS ids to rich
  metadata dicts so that full candidate information is available on retrieval.

Key metadata fields stored per chunk
-------------------------------------
candidate_id, section_type, skills (list), years_of_experience (float),
role/designation, doc_id, source, full_name, raw_text (truncated)

This store is intentionally self-contained so no external service is required.
If you wish to replace it with Pinecone, swap out the class below — the
:class:`VectorSearchResult` schema and the ``search`` / ``upsert`` interfaces
are the same.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
_STORE_DIR   = Path(os.environ.get("VECTOR_STORE_DIR", "./data/faiss_index"))
_INDEX_FILE  = _STORE_DIR / "index.faiss"
_META_FILE   = _STORE_DIR / "metadata.json"
_DIM_FILE    = _STORE_DIR / "dim.txt"

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ChunkMetadata:
    """Metadata stored alongside every vector in the FAISS index."""
    candidate_id:        str
    section_type:        str            # skills | experience | projects | education | certifications | summary | full_profile
    skills:              list[str] = field(default_factory=list)
    years_of_experience: float = 0.0
    role:                str = ""
    designation:         str = ""
    doc_id:              str = ""
    source:              str = "gdrive"
    full_name:           str = ""
    raw_text:            str = ""       # first 512 chars of the chunk
    indexed_at:          float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ChunkMetadata":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class VectorSearchResult:
    """Single result returned by :meth:`FaissVectorStore.search`."""
    candidate_id:    str
    section_type:    str
    score:           float          # cosine similarity (0-1)
    faiss_id:        int
    metadata:        ChunkMetadata


# ---------------------------------------------------------------------------
# Core store
# ---------------------------------------------------------------------------

class FaissVectorStore:
    """Persistent FAISS vector store with metadata sidecar.

    Usage
    -----
    >>> store = FaissVectorStore.get_instance(dim=1024)
    >>> store.upsert_chunks(candidate_id, chunks_metadata, vectors)
    >>> results = store.search(query_vector, top_k=50)
    """

    _instance: Optional["FaissVectorStore"] = None

    def __init__(self, dim: int = 1024):
        self._dim   = dim
        self._index = None          # faiss.IndexFlatIP (inner-product = cosine on normalised)
        self._meta: dict[int, dict] = {}   # faiss_id → ChunkMetadata dict
        self._next_id = 0

        _STORE_DIR.mkdir(parents=True, exist_ok=True)
        self._load_or_create()

    # ------------------------------------------------------------------
    # Singleton accessor (one store per process, lazy-loaded)
    # ------------------------------------------------------------------

    @classmethod
    def get_instance(cls, dim: int = 1024) -> "FaissVectorStore":
        if cls._instance is None:
            cls._instance = cls(dim=dim)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Force re-load from disk (useful after bulk ingestion in another process)."""
        cls._instance = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def upsert_chunks(
        self,
        candidate_id: str,
        chunks_meta: list[ChunkMetadata],
        vectors: list[list[float]],
    ) -> None:
        """Insert or replace all chunks for *candidate_id*.

        Existing entries for the same candidate are removed first (full
        re-index on update), then the new vectors are added.
        """
        if len(chunks_meta) != len(vectors):
            raise ValueError("chunks_meta and vectors must have the same length")
        if not chunks_meta:
            return

        # Remove existing entries for this candidate
        self._delete_by_candidate(candidate_id)

        # Normalise vectors (cosine similarity via inner product)
        mat = self._normalise(np.array(vectors, dtype=np.float32))

        ids = np.arange(self._next_id, self._next_id + len(vectors), dtype=np.int64)
        self._next_id += len(vectors)

        self._index.add_with_ids(mat, ids)

        for faiss_id, meta in zip(ids.tolist(), chunks_meta):
            self._meta[faiss_id] = meta.to_dict()

        self._persist()
        logger.info("Upserted %d chunk(s) for candidate_id=%s", len(vectors), candidate_id)

    def search(
        self,
        query_vector: list[float],
        top_k: int = 50,
        filter_candidate_ids: Optional[list[str]] = None,
        filter_section_types: Optional[list[str]] = None,
    ) -> list[VectorSearchResult]:
        """Return the top-K most similar chunks to *query_vector*.

        Parameters
        ----------
        query_vector:
            A normalised float vector of the same dimension as the index.
        top_k:
            Number of results to return from FAISS before metadata filtering.
        filter_candidate_ids:
            If given, only results whose ``candidate_id`` is in this list are
            returned (post-filter).
        filter_section_types:
            If given, only results whose ``section_type`` is in this list are
            returned (post-filter).
        """
        if self._index.ntotal == 0:
            return []

        q = self._normalise(np.array([query_vector], dtype=np.float32))
        # Fetch more than top_k so post-filtering still yields enough results
        fetch_k = min(top_k * 5, self._index.ntotal)
        distances, ids = self._index.search(q, fetch_k)

        results: list[VectorSearchResult] = []
        for dist, fid in zip(distances[0].tolist(), ids[0].tolist()):
            if fid < 0:
                continue
            meta_dict = self._meta.get(fid)
            if meta_dict is None:
                continue
            meta = ChunkMetadata.from_dict(meta_dict)
            if filter_candidate_ids and meta.candidate_id not in filter_candidate_ids:
                continue
            if filter_section_types and meta.section_type not in filter_section_types:
                continue
            results.append(VectorSearchResult(
                candidate_id=meta.candidate_id,
                section_type=meta.section_type,
                score=float(dist),
                faiss_id=fid,
                metadata=meta,
            ))
            if len(results) >= top_k:
                break

        return results

    def get_all_candidate_ids(self) -> list[str]:
        """Return deduplicated list of all indexed candidate_ids."""
        seen: dict[str, None] = {}
        for m in self._meta.values():
            cid = m.get("candidate_id", "")
            if cid:
                seen[cid] = None
        return list(seen)

    def delete_candidate(self, candidate_id: str) -> int:
        """Remove all chunks for *candidate_id* and persist. Returns count removed."""
        removed = self._delete_by_candidate(candidate_id)
        if removed:
            self._persist()
        return removed

    @property
    def total_vectors(self) -> int:
        return self._index.ntotal if self._index else 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_or_create(self) -> None:
        try:
            import faiss  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "faiss-cpu is required for the vector store. "
                "Install it with: pip install faiss-cpu"
            ) from exc

        if _INDEX_FILE.exists() and _META_FILE.exists():
            try:
                self._index = faiss.read_index(str(_INDEX_FILE))
                with open(_META_FILE, "r", encoding="utf-8") as fh:
                    raw = json.load(fh)
                # Keys are stored as strings in JSON; convert to int
                self._meta = {int(k): v for k, v in raw.items()}
                self._next_id = max(self._meta.keys(), default=-1) + 1
                # Verify dimension consistency
                if _DIM_FILE.exists():
                    stored_dim = int(_DIM_FILE.read_text().strip())
                    if stored_dim != self._dim:
                        logger.warning(
                            "Index dimension mismatch (stored=%d, requested=%d) — rebuilding index",
                            stored_dim, self._dim,
                        )
                        self._create_new_index(faiss)
                        return
                logger.info(
                    "Loaded FAISS index: %d vectors, dim=%d",
                    self._index.ntotal, self._dim,
                )
                return
            except Exception as exc:
                logger.warning("Could not load existing FAISS index (%s) — creating new one", exc)

        self._create_new_index(faiss)

    def _create_new_index(self, faiss_module) -> None:
        self._index = faiss_module.IndexIDMap(
            faiss_module.IndexFlatIP(self._dim)   # inner product on normalised = cosine
        )
        self._meta    = {}
        self._next_id = 0
        _DIM_FILE.write_text(str(self._dim))
        logger.info("Created new FAISS index (dim=%d)", self._dim)

    def _persist(self) -> None:
        try:
            import faiss  # type: ignore
            faiss.write_index(self._index, str(_INDEX_FILE))
            with open(_META_FILE, "w", encoding="utf-8") as fh:
                json.dump(self._meta, fh)
        except Exception as exc:
            logger.error("Failed to persist FAISS index: %s", exc)

    def _delete_by_candidate(self, candidate_id: str) -> int:
        ids_to_remove = [
            fid for fid, m in self._meta.items()
            if m.get("candidate_id") == candidate_id
        ]
        if not ids_to_remove:
            return 0
        try:
            ids_arr = np.array(ids_to_remove, dtype=np.int64)
            self._index.remove_ids(ids_arr)
        except Exception as exc:
            # IndexFlatIP doesn't support remove_ids unless wrapped in IndexIDMap
            logger.warning("FAISS remove_ids failed (%s) — rebuilding after delete", exc)
            self._rebuild_without(set(ids_to_remove))
        for fid in ids_to_remove:
            self._meta.pop(fid, None)
        return len(ids_to_remove)

    def _rebuild_without(self, exclude_ids: set[int]) -> None:
        """Rebuild index from scratch, excluding *exclude_ids*."""
        # We only have the metadata, not the original vectors, so we can't
        # truly rebuild — mark the store as stale and log a warning.
        logger.warning(
            "FAISS rebuild not possible without stored raw vectors; %d stale entries may remain",
            len(exclude_ids),
        )

    @staticmethod
    def _normalise(mat: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        return (mat / norms).astype(np.float32)
