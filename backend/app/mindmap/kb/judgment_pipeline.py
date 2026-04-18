"""Judgment ingestion pipeline — T53-M-KB-5.

Handles: upload → chunk → extract insights → review queue → apply to KB.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2.extras
from psycopg2.extensions import connection as PgConnection

psycopg2.extras.register_uuid()
logger = logging.getLogger(__name__)

# Binding authority scores
COURT_AUTHORITY = {
    "supreme_court": 100,
    "gujarat_hc": 80,
    "other_hc": 60,
    "district": 40,
}

# Simple regex patterns for extracting BNS sections from judgment text
_BNS_PATTERN = re.compile(
    r"(?:Section|S\.|Sec\.?)\s*(\d+(?:\([^)]*\))?)\s*(?:of\s+)?(?:BNS|Bharatiya Nyaya Sanhita)",
    re.IGNORECASE,
)
_BNSS_PATTERN = re.compile(
    r"(?:Section|S\.|Sec\.?)\s*(\d+(?:\([^)]*\))?)\s*(?:of\s+)?(?:BNSS|Bharatiya Nagarik Suraksha Sanhita)",
    re.IGNORECASE,
)


def _dict_cursor(conn: PgConnection):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


def _audit_log(conn: PgConnection, action: str, target_type: str,
               target_id: uuid.UUID, detail: Dict) -> None:
    """Simplified audit log entry."""
    now = datetime.now(timezone.utc)
    with _dict_cursor(conn) as cur:
        cur.execute(
            """SELECT hash_self FROM legal_kb_audit_log
               WHERE target_id = %s ORDER BY timestamp DESC LIMIT 1""",
            (target_id,),
        )
        prev = cur.fetchone()
        prev_hash = prev["hash_self"] if prev else "GENESIS"

    payload = f"{action}|{json.dumps(detail, default=str)}|{now.isoformat()}|{prev_hash}"
    hash_self = hashlib.sha256(payload.encode()).hexdigest()

    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO legal_kb_audit_log
               (actor_user_id, action, target_type, target_id,
                after_state, timestamp, hash_prev, hash_self)
               VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s)""",
            (None, action, target_type, target_id,
             json.dumps(detail, default=str),
             now.replace(tzinfo=None), prev_hash, hash_self),
        )


# ── Step 1: Ingest judgment ──────────────────────────────────────────────────

def ingest_judgment(
    conn: PgConnection,
    *,
    citation: str,
    case_name: Optional[str],
    court: str,
    jurisdiction: Optional[str],
    judgment_date: Optional[str],
    bench: Optional[str],
    full_text: str,
    summary_md: Optional[str],
    related_bns_sections: List[str],
    source_url: Optional[str],
    ingested_by: Optional[str],
) -> Dict[str, Any]:
    """Ingest a judgment into the KB. Returns the created judgment record."""
    judgment_id = uuid.uuid4()
    authority = COURT_AUTHORITY.get(court, 40)

    # Auto-extract BNS sections from text if not provided
    if not related_bns_sections:
        found = set()
        for m in _BNS_PATTERN.finditer(full_text):
            found.add(m.group(1))
        related_bns_sections = sorted(found)

    with _dict_cursor(conn) as cur:
        # Check for duplicate citation
        cur.execute(
            "SELECT id FROM legal_kb_judgments WHERE citation = %s", (citation,),
        )
        if cur.fetchone():
            raise ValueError(f"Judgment with citation '{citation}' already exists")

        cur.execute(
            """INSERT INTO legal_kb_judgments
               (id, citation, case_name, court, jurisdiction, judgment_date,
                bench, binding_authority, source_url, full_text, summary_md,
                related_bns_sections, ingested_by, review_status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'ingested')
               RETURNING *""",
            (judgment_id, citation, case_name, court, jurisdiction,
             judgment_date, bench, authority, source_url, full_text,
             summary_md, related_bns_sections, ingested_by),
        )
        result = dict(cur.fetchone())

    _audit_log(conn, "ingest_judgment", "judgment", judgment_id,
               {"citation": citation, "court": court})
    conn.commit()

    logger.info("Ingested judgment: %s (%s)", citation, court)
    return result


# ── Step 2: Chunk judgment text ──────────────────────────────────────────────

def chunk_judgment(
    conn: PgConnection,
    judgment_id: uuid.UUID,
    chunk_size: int = 1000,
) -> int:
    """Split judgment full_text into paragraph-level chunks for RAG."""
    with _dict_cursor(conn) as cur:
        cur.execute(
            "SELECT full_text FROM legal_kb_judgments WHERE id = %s",
            (judgment_id,),
        )
        row = cur.fetchone()
        if not row or not row["full_text"]:
            return 0

        text = row["full_text"]

    # Split by double newlines (paragraphs)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    # Merge short paragraphs to reach chunk_size
    chunks: List[Dict] = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) > chunk_size and current:
            chunks.append(current)
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current:
        chunks.append(current)

    # Classify chunk types heuristically
    with conn.cursor() as cur:
        for i, chunk_text in enumerate(chunks):
            chunk_type = _classify_chunk(chunk_text)
            chunk_id = uuid.uuid4()
            cur.execute(
                """INSERT INTO legal_kb_judgment_chunks
                   (id, judgment_id, chunk_index, chunk_text, chunk_type)
                   VALUES (%s, %s, %s, %s, %s)""",
                (chunk_id, judgment_id, i, chunk_text, chunk_type),
            )

    conn.commit()
    logger.info("Chunked judgment %s into %d chunks", judgment_id, len(chunks))
    return len(chunks)


def _classify_chunk(text: str) -> str:
    """Simple heuristic classification of judgment chunk type."""
    lower = text.lower()
    if any(kw in lower for kw in ["order", "hereby", "appeal is", "conviction", "acquittal", "sentence"]):
        return "operative"
    if any(kw in lower for kw in ["the prosecution case", "facts of the case", "brief facts", "complainant stated"]):
        return "facts"
    if any(kw in lower for kw in ["we hold", "ratio", "principle of law", "settled position"]):
        return "ratio"
    if any(kw in lower for kw in ["in passing", "obiter", "we observe", "we may note"]):
        return "obiter"
    return "other"


# ── Step 3: Extract insights (rule-based for MVP) ───────────────────────────

def extract_insights(
    conn: PgConnection,
    judgment_id: uuid.UUID,
) -> List[Dict]:
    """Extract structured insights from judgment chunks.

    MVP uses rule-based extraction. Future: LLM-based extraction.
    """
    with _dict_cursor(conn) as cur:
        cur.execute(
            """SELECT * FROM legal_kb_judgment_chunks
               WHERE judgment_id = %s ORDER BY chunk_index""",
            (judgment_id,),
        )
        chunks = [dict(r) for r in cur.fetchall()]

        cur.execute(
            "SELECT related_bns_sections FROM legal_kb_judgments WHERE id = %s",
            (judgment_id,),
        )
        j = cur.fetchone()
        bns_sections = (j["related_bns_sections"] or []) if j else []

    insights: List[Dict] = []

    # Find relevant offences
    target_offence_id = None
    if bns_sections:
        with _dict_cursor(conn) as cur:
            cur.execute(
                "SELECT id FROM legal_kb_offences WHERE bns_section = ANY(%s) LIMIT 1",
                (bns_sections,),
            )
            off = cur.fetchone()
            if off:
                target_offence_id = off["id"]

    for chunk in chunks:
        text = chunk["chunk_text"]
        chunk_idx = chunk["chunk_index"]

        # Look for procedural requirements
        if chunk["chunk_type"] == "ratio":
            # Extract sentences that look like legal requirements
            sentences = re.split(r"[.!?]+", text)
            for sent in sentences:
                sent = sent.strip()
                if len(sent) < 30:
                    continue

                # Match patterns like "it is mandatory", "must be", "shall"
                if any(kw in sent.lower() for kw in ["mandatory", "must be", "shall be", "is required", "essential"]):
                    insight_id = uuid.uuid4()
                    insight = {
                        "id": insight_id,
                        "judgment_id": judgment_id,
                        "target_offence_id": target_offence_id,
                        "insight_type": "new_procedural_requirement",
                        "branch_type": "procedural_safeguard",
                        "title_en": sent[:120],
                        "description_md": sent,
                        "extracted_quote": sent,
                        "extracted_quote_paragraph": chunk_idx,
                        "extraction_confidence": 0.6,
                        "extraction_model_version": "rule_based_v1",
                        "proposed_action": "add_new_node",
                    }
                    insights.append(insight)

                # Match acquittal patterns
                elif any(kw in sent.lower() for kw in ["acquitted", "acquittal", "benefit of doubt", "prosecution failed"]):
                    insight_id = uuid.uuid4()
                    insight = {
                        "id": insight_id,
                        "judgment_id": judgment_id,
                        "target_offence_id": target_offence_id,
                        "insight_type": "acquittal_pattern",
                        "branch_type": "gap_historical",
                        "title_en": f"Acquittal pattern: {sent[:100]}",
                        "description_md": sent,
                        "extracted_quote": sent,
                        "extracted_quote_paragraph": chunk_idx,
                        "extraction_confidence": 0.5,
                        "extraction_model_version": "rule_based_v1",
                        "proposed_action": "add_new_node",
                    }
                    insights.append(insight)

    # Persist insights
    with conn.cursor() as cur:
        for ins in insights:
            cur.execute(
                """INSERT INTO legal_kb_judgment_insights
                   (id, judgment_id, target_offence_id, insight_type,
                    branch_type, title_en, description_md, extracted_quote,
                    extracted_quote_paragraph, extraction_confidence,
                    extraction_model_version, proposed_action, review_status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')""",
                (ins["id"], ins["judgment_id"], ins.get("target_offence_id"),
                 ins["insight_type"], ins.get("branch_type"),
                 ins["title_en"], ins.get("description_md"),
                 ins.get("extracted_quote"), ins.get("extracted_quote_paragraph"),
                 ins.get("extraction_confidence", 0),
                 ins.get("extraction_model_version"),
                 ins.get("proposed_action")),
            )

        # Update judgment status
        cur.execute(
            "UPDATE legal_kb_judgments SET review_status = 'extracted' WHERE id = %s",
            (judgment_id,),
        )

    _audit_log(conn, "extract_insight", "judgment", judgment_id,
               {"insights_count": len(insights)})
    conn.commit()

    logger.info("Extracted %d insights from judgment %s", len(insights), judgment_id)
    return insights


# ── Step 4: Review & apply insights ──────────────────────────────────────────

def approve_insight(
    conn: PgConnection,
    insight_id: uuid.UUID,
    reviewer_id: str,
    review_notes: Optional[str] = None,
) -> Dict:
    """Approve an insight and optionally apply it to the KB."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with _dict_cursor(conn) as cur:
        cur.execute(
            "SELECT * FROM legal_kb_judgment_insights WHERE id = %s", (insight_id,),
        )
        insight = cur.fetchone()
        if not insight:
            raise ValueError(f"Insight {insight_id} not found")
        insight = dict(insight)

        # Update insight status
        cur.execute(
            """UPDATE legal_kb_judgment_insights
               SET review_status = 'approved', reviewed_by = %s,
                   reviewed_at = %s, review_notes = %s
               WHERE id = %s""",
            (reviewer_id, now, review_notes, insight_id),
        )

        # If proposed_action is add_new_node, create a knowledge node
        applied_node_id = None
        if insight.get("proposed_action") == "add_new_node" and insight.get("target_offence_id"):
            applied_node_id = uuid.uuid4()

            # Get max display_order
            cur.execute(
                "SELECT COALESCE(MAX(display_order), 0) + 1 AS next_ord FROM legal_kb_knowledge_nodes WHERE offence_id = %s",
                (insight["target_offence_id"],),
            )
            next_ord = cur.fetchone()["next_ord"]

            citations = []
            if insight.get("judgment_id"):
                cur.execute(
                    "SELECT citation FROM legal_kb_judgments WHERE id = %s",
                    (insight["judgment_id"],),
                )
                j = cur.fetchone()
                if j:
                    citations = [{"case_citation": j["citation"], "source_authority": "Judgment"}]

            cur.execute(
                """INSERT INTO legal_kb_knowledge_nodes
                   (id, offence_id, branch_type, tier, priority,
                    title_en, description_md, legal_basis_citations,
                    requires_disclaimer, display_order,
                    created_by, approval_status)
                   VALUES (%s, %s, %s, 'judgment_derived', 'medium',
                           %s, %s, %s::jsonb, true, %s, %s, 'approved')""",
                (applied_node_id, insight["target_offence_id"],
                 insight.get("branch_type", "gap_historical"),
                 insight["title_en"], insight.get("description_md"),
                 json.dumps(citations, default=str),
                 next_ord, reviewer_id),
            )

            cur.execute(
                """UPDATE legal_kb_judgment_insights
                   SET applied_at = %s, applied_as_node_id = %s
                   WHERE id = %s""",
                (now, applied_node_id, insight_id),
            )

    _audit_log(conn, "approve_insight", "insight", insight_id,
               {"reviewer": reviewer_id, "applied_node": str(applied_node_id)})
    conn.commit()

    logger.info("Approved insight %s, applied as node %s", insight_id, applied_node_id)
    return {"insight_id": str(insight_id), "applied_node_id": str(applied_node_id)}


def reject_insight(
    conn: PgConnection,
    insight_id: uuid.UUID,
    reviewer_id: str,
    review_notes: Optional[str] = None,
) -> None:
    """Reject an insight."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE legal_kb_judgment_insights
               SET review_status = 'rejected', reviewed_by = %s,
                   reviewed_at = %s, review_notes = %s
               WHERE id = %s""",
            (reviewer_id, now, review_notes, insight_id),
        )
    _audit_log(conn, "reject_insight", "insight", insight_id,
               {"reviewer": reviewer_id, "notes": review_notes})
    conn.commit()
