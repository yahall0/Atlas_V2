"""Cross-encoder reranker.

After dense retrieval returns top-K candidates, a cross-encoder scores each
``(query, chunk)`` pair jointly and re-ranks the list. This step typically
buys 5–10 percentage points of top-K accuracy over pure retrieval and is
the single most cost-effective quality improvement in the pipeline.

Two backends:

* **``DevReranker``** — fully offline, no dependencies. Implements a
  lightweight scoring rule (cosine over the existing embedder + a
  keyword-overlap bonus). Deterministic. Useful for unit tests and CI.

* **``Bge3Reranker``** — production. Loads ``BAAI/bge-reranker-v2-m3``
  lazily. Activated by ``ATLAS_RERANKER=bge-reranker-v2-m3`` (or by passing
  ``backend="bge-reranker-v2-m3"`` to ``get_reranker``).

Both implement the ``Reranker`` protocol so the recommender is agnostic.
"""
from __future__ import annotations

import os
import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Protocol, Sequence

from .retriever import RetrievedChunk


class Reranker(Protocol):
    name: str

    def rerank(self, query: str, candidates: Sequence[RetrievedChunk], k: int) -> list[RetrievedChunk]:
        ...


_TOKEN_RE = re.compile(r"\b[\w\u0900-\u097F\u0A80-\u0AFF']+\b")


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text)}


# ---------- Dev reranker ---------- #


class DevReranker:
    """Heuristic reranker for development and tests.

    Final score = ``alpha * retrieval_score + (1 - alpha) * keyword_overlap``
    where ``keyword_overlap`` is the Jaccard overlap of the query tokens
    against the candidate text. This is *not* a substitute for a learned
    cross-encoder; it is enough to validate wiring and catch egregious
    mis-ranking.
    """

    name = "dev-reranker-v1"

    def __init__(self, alpha: float = 0.6) -> None:
        self.alpha = alpha

    def rerank(
        self,
        query: str,
        candidates: Sequence[RetrievedChunk],
        k: int = 20,
    ) -> list[RetrievedChunk]:
        q_toks = _tokens(query)
        if not q_toks:
            return list(candidates)[:k]
        scored: list[tuple[float, RetrievedChunk]] = []
        for c in candidates:
            c_toks = _tokens(c.chunk.text)
            inter = len(q_toks & c_toks)
            union = len(q_toks | c_toks) or 1
            jaccard = inter / union
            final = self.alpha * c.score + (1 - self.alpha) * jaccard
            scored.append((final, c))
        scored.sort(key=lambda x: -x[0])
        return [RetrievedChunk(chunk=c.chunk, score=s) for s, c in scored[:k]]


# ---------- Production cross-encoder ---------- #


class Bge3Reranker:
    """``BAAI/bge-reranker-v2-m3`` cross-encoder.

    Lazy import of ``sentence_transformers``; same operational pattern as
    the production embedder. Activated via ``ATLAS_RERANKER`` env var.
    """

    name = "bge-reranker-v2-m3"

    def __init__(self, model_path: str | None = None) -> None:
        self._model = None
        self._model_path = model_path or os.getenv(
            "BGE_RERANKER_PATH", "BAAI/bge-reranker-v2-m3"
        )

    def _load(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder  # type: ignore
            self._model = CrossEncoder(self._model_path)
        return self._model

    def rerank(
        self,
        query: str,
        candidates: Sequence[RetrievedChunk],
        k: int = 20,
    ) -> list[RetrievedChunk]:
        if not candidates:
            return []
        m = self._load()
        pairs = [[query, c.chunk.text] for c in candidates]
        scores = m.predict(pairs)
        rescored = [
            RetrievedChunk(chunk=c.chunk, score=float(s))
            for c, s in zip(candidates, scores)
        ]
        rescored.sort(key=lambda r: -r.score)
        return rescored[:k]


# ---------- Factory ---------- #


def get_reranker(backend: str | None = None) -> Reranker:
    name = (backend or os.getenv("ATLAS_RERANKER", "dev")).lower()
    if name in ("dev", "dev-reranker", "dev-reranker-v1"):
        return DevReranker()
    if name in ("bge-reranker-v2-m3", "bge-rerank", "bge-m3"):
        return Bge3Reranker()
    raise ValueError(f"unknown reranker backend: {name}")


__all__ = ["Reranker", "DevReranker", "Bge3Reranker", "get_reranker"]
