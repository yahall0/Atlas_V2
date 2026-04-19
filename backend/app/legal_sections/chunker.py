"""Chunker — turns each statutory section into addressable retrieval chunks.

Per ADR-D15, the chunker emits one chunk per **addressable sub-clause** plus
auxiliary chunks for the section header and any illustrations / explanations
/ exceptions. Every chunk carries the canonical citation and addressable id
of the smallest unit it represents, so downstream retrieval and ranking
operate at sub-clause precision without re-parsing the source.

The chunk shape is the unit of work for the embedder, the retriever, and
the recommender. It is also the unit persisted into the
``legal_section_chunks`` table.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Iterable, Iterator, Literal

ChunkType = Literal[
    "header",         # section number + title + chapter (terse, highly retrievable)
    "section_body",   # umbrella section text when no sub-clauses exist
    "sub_clause",     # one per addressable sub-clause (preferred for sub-clause-precise retrieval)
    "illustration",
    "explanation",
    "exception",
]


@dataclass
class Chunk:
    chunk_id: str                 # globally unique (deterministic) e.g. "BNS_305_a__sub_clause"
    section_id: str               # parent section, e.g. "BNS_305"
    act: str                      # "IPC" or "BNS"
    section_number: str
    section_title: str | None
    chapter_number: str | None
    chapter_title: str | None
    chunk_type: ChunkType
    chunk_index: int              # order within the section
    text: str                     # verbatim text used as embedding input AND as rationale_quote
    canonical_citation: str       # smallest applicable citation form (e.g. "BNS 305(a)")
    addressable_id: str           # URL-safe id (e.g. "BNS_305_a")
    sub_clause_label: str | None  # "(a)", "(2)", "Provided that", or None
    keywords: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


def chunk_section(section: dict) -> list[Chunk]:
    """Decompose one section JSON record into retrieval chunks.

    Strategy (ADR-D15):
        - One ``header`` chunk: identifier-rich, used for section-level recall.
        - If the section has no sub_clauses: one ``section_body`` chunk with
          the entire full_text (excluding the header line itself, to avoid
          double-counting at retrieval time).
        - If the section has sub_clauses: one ``sub_clause`` chunk per entry
          (this is the precision lever).
        - One chunk per illustration / explanation / exception (these are
          discriminators on borderline cases like theft vs cheating).
    """
    section_id = section["id"]
    act = section["act"]
    section_number = section["section_number"]
    section_title = section.get("section_title")
    chapter_number = section.get("chapter_number")
    chapter_title = section.get("chapter_title")

    chunks: list[Chunk] = []
    idx = 0

    # --- header chunk --------------------------------------------------------
    header_text_parts: list[str] = []
    header_text_parts.append(f"{act} {section_number}")
    if section_title:
        header_text_parts.append(section_title)
    if chapter_title:
        header_text_parts.append(f"Chapter {chapter_number}: {chapter_title}" if chapter_number else f"Chapter {chapter_title}")
    header_text = " — ".join(header_text_parts)
    chunks.append(
        Chunk(
            chunk_id=f"{section_id}__header",
            section_id=section_id,
            act=act,
            section_number=section_number,
            section_title=section_title,
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            chunk_type="header",
            chunk_index=idx,
            text=header_text,
            canonical_citation=f"{act} {section_number}",
            addressable_id=section_id,
            sub_clause_label=None,
        )
    )
    idx += 1

    # --- sub-clauses (preferred) OR section body ----------------------------
    sub_clauses = section.get("sub_clauses") or []
    if sub_clauses:
        for sc in sub_clauses:
            # Some sections (e.g. IPC 499) repeat the same enumeration in
            # several illustration blocks attached to different exceptions,
            # producing multiple entries with the same addressable_id. Append
            # the running chunk_index to make chunk_ids globally unique while
            # leaving the canonical_citation untouched.
            chunks.append(
                Chunk(
                    chunk_id=f"{sc['addressable_id']}__sub_clause_{idx}",
                    section_id=section_id,
                    act=act,
                    section_number=section_number,
                    section_title=section_title,
                    chapter_number=chapter_number,
                    chapter_title=chapter_title,
                    chunk_type="sub_clause",
                    chunk_index=idx,
                    text=sc["text"],
                    canonical_citation=sc["canonical_citation"],
                    addressable_id=sc["addressable_id"],
                    sub_clause_label=sc.get("canonical_label"),
                    metadata={
                        "scheme": sc.get("scheme"),
                        "depth": sc.get("depth"),
                        "parent_path": sc.get("parent_path", []),
                    },
                )
            )
            idx += 1
    else:
        # No enumerated sub-clauses — emit the full body as one chunk.
        chunks.append(
            Chunk(
                chunk_id=f"{section_id}__body",
                section_id=section_id,
                act=act,
                section_number=section_number,
                section_title=section_title,
                chapter_number=chapter_number,
                chapter_title=chapter_title,
                chunk_type="section_body",
                chunk_index=idx,
                text=section["full_text"],
                canonical_citation=f"{act} {section_number}",
                addressable_id=section_id,
                sub_clause_label=None,
            )
        )
        idx += 1

    # --- illustrations / explanations / exceptions (discriminators) ---------
    for kind, key in (("illustration", "illustrations"),
                      ("explanation", "explanations"),
                      ("exception", "exceptions")):
        for j, text in enumerate(section.get(key) or []):
            chunks.append(
                Chunk(
                    chunk_id=f"{section_id}__{kind}_{j}",
                    section_id=section_id,
                    act=act,
                    section_number=section_number,
                    section_title=section_title,
                    chapter_number=chapter_number,
                    chapter_title=chapter_title,
                    chunk_type=kind,  # type: ignore[arg-type]
                    chunk_index=idx,
                    text=text,
                    canonical_citation=f"{act} {section_number}",
                    addressable_id=section_id,
                    sub_clause_label=None,
                    metadata={"sub_index": j},
                )
            )
            idx += 1

    return chunks


def iter_chunks(jsonl_paths: Iterable[Path]) -> Iterator[Chunk]:
    """Stream chunks from one or more *_sections.jsonl files."""
    for path in jsonl_paths:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                section = json.loads(line)
                yield from chunk_section(section)


def chunks_to_jsonl(chunks: Iterable[Chunk], path: Path) -> int:
    """Write chunks to JSONL. Returns count written."""
    n = 0
    with path.open("w", encoding="utf-8") as fh:
        for c in chunks:
            fh.write(json.dumps(asdict(c), ensure_ascii=False) + "\n")
            n += 1
    return n


__all__ = ["Chunk", "ChunkType", "chunk_section", "iter_chunks", "chunks_to_jsonl"]
