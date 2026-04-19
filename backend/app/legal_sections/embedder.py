"""Embedder abstraction.

Production target (per the legal_sections README) is ``BAAI/bge-m3``: a
multilingual dense + sparse + multi-vector model that runs on CPU and
covers Gujarati and English in the same vector space.

For the current build phase — and to keep the package importable on
machines without ``sentence-transformers`` / ``torch`` installed — we ship
two backends:

* ``TfidfEmbedder`` — a fully-offline, deterministic, no-dependency backend
  used for development, unit tests, and the eval harness. It is good enough
  to validate end-to-end wiring and produce calibrated relative scores
  within a single corpus. NOT a substitute for a true multilingual model
  in production.

* ``Bge3Embedder`` — production backend. Loads ``BAAI/bge-m3`` lazily and
  caches it. Activated by setting ``ATLAS_EMBEDDER=bge-m3`` (or by passing
  ``backend="bge-m3"`` to ``get_embedder``).

Both backends implement the ``Embedder`` protocol so the retriever and the
recommender are agnostic to which one is in use.
"""
from __future__ import annotations

import math
import os
import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Protocol, Sequence


class Embedder(Protocol):
    """Embedder contract."""

    name: str
    dim: int

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return a dense vector per input text, normalised to unit length."""
        ...

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string. Equivalent to ``embed([text])[0]`` but
        a separate hook lets production embedders use a different prompt
        template for queries vs documents."""
        ...


# ---------- TF-IDF dev backend ---------- #


_TOKEN_RE = re.compile(r"\b[\w\u0900-\u097F\u0A80-\u0AFF']+\b")


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


@dataclass
class _Vocab:
    term_to_idx: dict[str, int]
    idf: list[float]


class TfidfEmbedder:
    """Pure-Python TF-IDF embedder. Deterministic. Fast. Offline.

    Use for development and unit tests. Vector dimension equals vocabulary
    size (sparse-feeling, but stored dense for uniform retriever interface).
    Cosine similarity over these vectors is a well-known competitive
    baseline for legal text retrieval.
    """

    name = "tfidf-v1"

    def __init__(self) -> None:
        self._vocab: _Vocab | None = None
        self.dim = 0

    def fit(self, corpus_texts: Iterable[str]) -> "TfidfEmbedder":
        """Build vocabulary and IDF table over a fixed corpus.

        Must be called once before ``embed`` / ``embed_query``. Idempotent in
        the sense that a fresh fit replaces any previous vocabulary.
        """
        df: Counter[str] = Counter()
        n_docs = 0
        for text in corpus_texts:
            n_docs += 1
            unique = set(_tokenize(text))
            for term in unique:
                df[term] += 1
        # Sort terms for determinism
        terms = sorted(df.keys())
        term_to_idx = {t: i for i, t in enumerate(terms)}
        # Smoothed IDF: log((1 + N) / (1 + df)) + 1
        idf = [math.log((1.0 + n_docs) / (1.0 + df[t])) + 1.0 for t in terms]
        self._vocab = _Vocab(term_to_idx=term_to_idx, idf=idf)
        self.dim = len(terms)
        return self

    def _vector(self, text: str) -> list[float]:
        if self._vocab is None:
            raise RuntimeError("TfidfEmbedder.fit() must be called before embedding")
        tokens = _tokenize(text)
        if not tokens:
            return [0.0] * self.dim
        tf = Counter(tokens)
        max_tf = max(tf.values())
        vec = [0.0] * self.dim
        for term, count in tf.items():
            idx = self._vocab.term_to_idx.get(term)
            if idx is None:
                continue
            tf_norm = 0.5 + 0.5 * (count / max_tf)
            vec[idx] = tf_norm * self._vocab.idf[idx]
        # L2 normalise
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


# ---------- Production backend (lazy-loaded) ---------- #


class Bge3Embedder:
    """``BAAI/bge-m3`` backend.

    Lazy import of ``sentence_transformers`` — keeps the package importable
    in environments that haven't installed the heavy ML dependency.
    """

    name = "bge-m3"
    dim = 1024  # bge-m3 dense dimension

    def __init__(self, model_path: str | None = None) -> None:
        self._model = None
        self._model_path = model_path or os.getenv("BGE_M3_PATH", "BAAI/bge-m3")

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # type: ignore
            self._model = SentenceTransformer(self._model_path)
        return self._model

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        m = self._load()
        return m.encode(list(texts), normalize_embeddings=True).tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.embed([text])[0]


# ---------- Factory ---------- #


def get_embedder(backend: str | None = None) -> Embedder:
    """Return an embedder. Reads ``ATLAS_EMBEDDER`` env var if ``backend`` is
    ``None``. Defaults to ``tfidf`` for development.
    """
    name = (backend or os.getenv("ATLAS_EMBEDDER", "tfidf")).lower()
    if name in ("tfidf", "tfidf-v1"):
        return TfidfEmbedder()
    if name in ("bge-m3", "bge3"):
        return Bge3Embedder()
    raise ValueError(f"unknown embedder backend: {name}")


__all__ = ["Embedder", "TfidfEmbedder", "Bge3Embedder", "get_embedder"]
