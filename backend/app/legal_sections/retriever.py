"""Dense retriever over chunked legal sections.

Two operations:

* ``index(chunks)`` — build an in-memory matrix of chunk vectors. Wraps the
  configured embedder. Vectors are L2-normalised.

* ``retrieve(query, k, act_filter=...)`` — return the top-k chunks ranked by
  cosine similarity to the query. Optional act filter restricts the search
  space to ``IPC`` or ``BNS`` (used when the act has been pre-decided by
  the date-of-occurrence rule).

This module is the *substitution point* for production pgvector. The same
contract — ``Retriever.retrieve(query, k)`` — is implemented in both this
in-memory class and a future ``PgvectorRetriever``.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from .chunker import Chunk
from .embedder import Embedder


@dataclass
class RetrievedChunk:
    chunk: Chunk
    score: float


class InMemoryRetriever:
    def __init__(self, embedder: Embedder) -> None:
        self.embedder = embedder
        self._chunks: list[Chunk] = []
        self._vectors: list[list[float]] = []

    def index(self, chunks: Iterable[Chunk]) -> None:
        self._chunks = list(chunks)
        # Build embedding text with section-title context. The verbatim
        # ``text`` field remains the rationale_quote; the embedding-time
        # text is enriched with the parent section title so common-domain
        # terms (theft, murder, robbery, hurt, ...) match queries even
        # when a sub-clause text omits them.
        texts = [
            f"{c.section_title or ''}. {c.text}" if c.section_title else c.text
            for c in self._chunks
        ]
        if hasattr(self.embedder, "fit"):
            self.embedder.fit(texts)  # type: ignore[attr-defined]
        self._vectors = self.embedder.embed(texts)

    def retrieve(
        self,
        query: str,
        k: int = 50,
        act_filter: str | None = None,
        chunk_type_filter: tuple[str, ...] | None = None,
    ) -> list[RetrievedChunk]:
        if not self._chunks:
            return []
        q = self.embedder.embed_query(query)
        scored: list[RetrievedChunk] = []
        for c, v in zip(self._chunks, self._vectors):
            if act_filter and c.act != act_filter:
                continue
            if chunk_type_filter and c.chunk_type not in chunk_type_filter:
                continue
            s = _cosine(q, v)
            scored.append(RetrievedChunk(chunk=c, score=s))
        scored.sort(key=lambda r: -r.score)
        return scored[:k]

    def __len__(self) -> int:
        return len(self._chunks)


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Dot product of L2-normalised vectors == cosine similarity."""
    if len(a) != len(b):
        # Allow mismatch only when one is a sparse vector left as zero pad
        n = min(len(a), len(b))
        return sum(a[i] * b[i] for i in range(n))
    return sum(x * y for x, y in zip(a, b))


def reciprocal_rank_fusion(
    rankings: list[list[RetrievedChunk]],
    k_rrf: int = 60,
) -> list[RetrievedChunk]:
    """RRF over multiple ranking lists. Standard k=60.

    Useful when combining dense and sparse (lexical) retrieval. Currently
    only the dense path is wired; this is here for the sparse-path expansion
    described in the legal_sections README.
    """
    accum: dict[str, float] = {}
    chunk_by_id: dict[str, Chunk] = {}
    for ranking in rankings:
        for rank, rc in enumerate(ranking, start=1):
            cid = rc.chunk.chunk_id
            accum[cid] = accum.get(cid, 0.0) + 1.0 / (k_rrf + rank)
            chunk_by_id[cid] = rc.chunk
    fused = [
        RetrievedChunk(chunk=chunk_by_id[cid], score=score)
        for cid, score in accum.items()
    ]
    fused.sort(key=lambda r: -r.score)
    return fused


__all__ = ["RetrievedChunk", "InMemoryRetriever", "reciprocal_rank_fusion"]
