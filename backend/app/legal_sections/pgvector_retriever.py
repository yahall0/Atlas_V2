"""Pgvector retriever — production substitute for ``InMemoryRetriever``.

Reads chunks and embeddings from ``legal_section_chunks`` (created by
migration ``013_add_legal_sections_kb``). Uses pgvector's
``<=>`` cosine-distance operator to retrieve the top-K nearest chunks for
a query embedding.

Both retrievers honour the same surface:

    retrieve(query, k, act_filter=..., chunk_type_filter=...) -> list[RetrievedChunk]

so the recommender is agnostic to which one is in use. The substitution
point is governed by an environment flag (``ATLAS_RETRIEVER`` —
``inmemory`` (default) or ``pgvector``).

Ingestion side:

    PgvectorIngestor.ingest(chunks)

writes the chunk store and computes the embedding column. Run once after
each corpus update; can be invoked from a CLI or an Alembic data
migration. Idempotent: re-running with the same chunk_id replaces the row.
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterable, Sequence

from .chunker import Chunk
from .embedder import Embedder, get_embedder
from .retriever import RetrievedChunk

logger = logging.getLogger(__name__)


@contextmanager
def _connect():
    """Yield a psycopg connection from ``DATABASE_URL``.

    Imported lazily so the module remains importable without a live DB
    (e.g. in unit tests, the eval harness, or a CI runner without psycopg).
    """
    try:
        import psycopg  # type: ignore
    except ImportError as exc:                                       # pragma: no cover
        raise RuntimeError(
            "psycopg is required for PgvectorRetriever; install psycopg[binary]"
        ) from exc
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL is not set")
    conn = psycopg.connect(dsn)
    try:
        yield conn
    finally:
        conn.close()


def _vector_literal(vec: Sequence[float]) -> str:
    """Render a Python list as a pgvector literal string."""
    return "[" + ",".join(f"{float(v):.6f}" for v in vec) + "]"


# ---------- Ingestor ---------- #


class PgvectorIngestor:
    def __init__(self, embedder: Embedder | None = None) -> None:
        self.embedder = embedder or get_embedder()

    def ingest_sections(self, sections: Iterable[dict]) -> int:
        """Upsert section umbrella records into ``legal_sections``."""
        n = 0
        with _connect() as conn:
            with conn.cursor() as cur:
                for s in sections:
                    cur.execute(
                        """
                        INSERT INTO legal_sections
                          (id, act, section_number, section_title, chapter_number,
                           chapter_title, full_text, sub_clauses, illustrations,
                           explanations, exceptions, cross_references,
                           cognizable, bailable, triable_by, compoundable,
                           punishment, source_page_start, source_page_end)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s,
                                %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO UPDATE SET
                          full_text = EXCLUDED.full_text,
                          sub_clauses = EXCLUDED.sub_clauses,
                          updated_at = now();
                        """,
                        (
                            s["id"], s["act"], s["section_number"], s.get("section_title"),
                            s.get("chapter_number"), s.get("chapter_title"), s["full_text"],
                            _json(s.get("sub_clauses") or []),
                            s.get("illustrations") or [], s.get("explanations") or [],
                            s.get("exceptions") or [], s.get("cross_references") or [],
                            s.get("cognizable"), s.get("bailable"),
                            s.get("triable_by"), s.get("compoundable"),
                            s.get("punishment"),
                            s.get("source_page_start"), s.get("source_page_end"),
                        ),
                    )
                    n += 1
            conn.commit()
        return n

    def ingest_chunks(self, chunks: Iterable[Chunk], batch: int = 256) -> int:
        """Upsert chunks and compute their dense embeddings.

        The embedder receives the same context-enriched text used by the
        in-memory retriever to keep behaviour consistent across backends.
        """
        chunks = list(chunks)
        if not chunks:
            return 0
        # Fit if the embedder requires
        texts = [
            f"{c.section_title or ''}. {c.text}" if c.section_title else c.text
            for c in chunks
        ]
        if hasattr(self.embedder, "fit"):
            self.embedder.fit(texts)  # type: ignore[attr-defined]

        n = 0
        with _connect() as conn:
            with conn.cursor() as cur:
                for start in range(0, len(chunks), batch):
                    batch_chunks = chunks[start: start + batch]
                    batch_texts = texts[start: start + batch]
                    vectors = self.embedder.embed(batch_texts)
                    for c, v in zip(batch_chunks, vectors):
                        cur.execute(
                            """
                            INSERT INTO legal_section_chunks
                              (chunk_id, section_id, act, section_number, section_title,
                               chapter_number, chapter_title, chunk_type, chunk_index,
                               text, canonical_citation, addressable_id, sub_clause_label,
                               keywords, metadata, dense_embedding)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                    %s, %s::jsonb, %s::vector)
                            ON CONFLICT (chunk_id) DO UPDATE SET
                              text = EXCLUDED.text,
                              dense_embedding = EXCLUDED.dense_embedding;
                            """,
                            (
                                c.chunk_id, c.section_id, c.act, c.section_number,
                                c.section_title, c.chapter_number, c.chapter_title,
                                c.chunk_type, c.chunk_index, c.text,
                                c.canonical_citation, c.addressable_id, c.sub_clause_label,
                                c.keywords or None, _json(c.metadata or {}),
                                _vector_literal(v),
                            ),
                        )
                        n += 1
            conn.commit()
        return n


def _json(obj) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False)


# ---------- Retriever ---------- #


@dataclass
class _Row:
    chunk: Chunk
    score: float


class PgvectorRetriever:
    """Top-K dense retriever backed by pgvector.

    Mirror of ``InMemoryRetriever``. ``index`` is a no-op; ingestion is
    driven by ``PgvectorIngestor`` (typically run once, not on every
    process start).
    """

    def __init__(self, embedder: Embedder | None = None) -> None:
        self.embedder = embedder or get_embedder()

    def index(self, chunks: Iterable[Chunk]) -> None:                 # noqa: ARG002
        """No-op: pgvector index is built once via the migration + ingestor."""
        return None

    def retrieve(
        self,
        query: str,
        k: int = 50,
        act_filter: str | None = None,
        chunk_type_filter: tuple[str, ...] | None = None,
    ) -> list[RetrievedChunk]:
        q_vec = self.embedder.embed_query(query)

        where = []
        params: list = []
        if act_filter:
            where.append("act = %s")
            params.append(act_filter)
        if chunk_type_filter:
            placeholders = ", ".join(["%s"] * len(chunk_type_filter))
            where.append(f"chunk_type IN ({placeholders})")
            params.extend(chunk_type_filter)
        where_sql = ("WHERE " + " AND ".join(where)) if where else ""
        params.append(_vector_literal(q_vec))
        params.append(k)
        sql = f"""
            SELECT chunk_id, section_id, act, section_number, section_title,
                   chapter_number, chapter_title, chunk_type, chunk_index,
                   text, canonical_citation, addressable_id, sub_clause_label,
                   1.0 - (dense_embedding <=> %s::vector) AS score
            FROM legal_section_chunks
            {where_sql}
            ORDER BY dense_embedding <=> %s::vector
            LIMIT %s
        """
        # Two query-vector binds (one for score, one for ORDER BY) at the
        # end of params:
        params = params[:-2] + [_vector_literal(q_vec), _vector_literal(q_vec), k]

        out: list[RetrievedChunk] = []
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                for row in cur.fetchall():
                    chunk = Chunk(
                        chunk_id=row[0],
                        section_id=row[1],
                        act=row[2],
                        section_number=row[3],
                        section_title=row[4],
                        chapter_number=row[5],
                        chapter_title=row[6],
                        chunk_type=row[7],
                        chunk_index=row[8],
                        text=row[9],
                        canonical_citation=row[10],
                        addressable_id=row[11],
                        sub_clause_label=row[12],
                    )
                    out.append(RetrievedChunk(chunk=chunk, score=float(row[13])))
        return out


__all__ = ["PgvectorRetriever", "PgvectorIngestor"]
