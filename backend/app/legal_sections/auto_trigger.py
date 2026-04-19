"""Auto-trigger: run the section recommender on a freshly-ingested FIR.

Wired into ``backend/app/api/v1/firs.py`` and ``backend/app/api/v1/ingest.py``
as a FastAPI background task. Persists the recommendation set to
``firs.nlp_metadata['recommended_sections']`` and the matched Compendium
scenarios to ``firs.nlp_metadata['compendium_scenarios']``, so the
mindmap engine (per ADR-D19) can route to the playbook path on its next
generation call.

This module is best-effort: failures never block the FIR-creation
response. Errors are logged and the FIR remains usable; the recommender
can be re-triggered manually via ``POST /api/v1/firs/{id}/recommend-sections``.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from .chunker import iter_chunks
from .embedder import get_embedder
from .io_scenarios import find_scenarios_for_sections
from .recommender import recommend
from .retriever import InMemoryRetriever

logger = logging.getLogger(__name__)

_RETRIEVER: InMemoryRetriever | None = None


def _get_retriever() -> InMemoryRetriever:
    """Lazy-initialise + cache the retriever for the process lifetime."""
    global _RETRIEVER
    if _RETRIEVER is None:
        from pathlib import Path
        data = Path(__file__).resolve().parent / "data"
        chunks = list(iter_chunks([
            data / "ipc_sections.jsonl",
            data / "bns_sections.jsonl",
        ]))
        embedder = get_embedder()
        r = InMemoryRetriever(embedder)
        r.index(chunks)
        _RETRIEVER = r
        logger.info(
            "auto_trigger.retriever_ready",
            extra={"chunk_count": len(chunks), "embedder": embedder.name},
        )
    return _RETRIEVER


def run_recommender_for_fir(
    fir_id: str,
    narrative: str,
    occurrence_date_iso: str | None,
    accused_count: int,
    *,
    conn=None,
) -> dict[str, Any]:
    """Run the recommender on the FIR's narrative and persist the result.

    Returns a summary dict ``{recommended_sections, compendium_scenarios,
    persisted}``. Safe to call from a background task.
    """
    try:
        retriever = _get_retriever()
        resp = recommend(
            fir_id=fir_id,
            fir_narrative=narrative,
            retriever=retriever,
            occurrence_date_iso=occurrence_date_iso,
            accused_count=accused_count,
        )
    except Exception:
        logger.exception("auto_trigger.recommend_failed", extra={"fir_id": fir_id})
        return {"recommended_sections": [], "compendium_scenarios": [], "persisted": False}

    rec_payload = [
        {
            "canonical_citation": r.canonical_citation,
            "section_id": r.section_id,
            "act": r.act,
            "section_number": r.section_number,
            "sub_clause_label": r.sub_clause_label,
            "addressable_id": r.addressable_id,
            "confidence": r.confidence,
            "rationale_quote": r.rationale_quote[:500],
        }
        for r in resp.recommendations
    ]

    citations = [r["canonical_citation"] for r in rec_payload]
    scenarios = find_scenarios_for_sections(citations)
    scenario_payload = [
        {
            "scenario_id": sc["scenario_id"],
            "scenario_name": sc["scenario_name"],
            "page_start": sc["page_start"],
            "page_end": sc["page_end"],
            "applicable_sections": sc["applicable_sections"],
        }
        for sc in scenarios
    ]

    persisted = False
    if conn is not None:
        try:
            _persist(conn, fir_id, rec_payload, scenario_payload, resp.act_basis)
            persisted = True
        except Exception:
            logger.exception("auto_trigger.persist_failed", extra={"fir_id": fir_id})

    logger.info(
        "auto_trigger.completed",
        extra={
            "fir_id": fir_id,
            "n_recommendations": len(rec_payload),
            "n_scenarios": len(scenario_payload),
            "persisted": persisted,
        },
    )
    return {
        "recommended_sections": rec_payload,
        "compendium_scenarios": scenario_payload,
        "act_basis": resp.act_basis,
        "persisted": persisted,
    }


def _persist(conn, fir_id: str, recommendations: list[dict],
             scenarios: list[dict], act_basis: str) -> None:
    """Write recommendation + scenarios into ``firs.nlp_metadata``.

    Merges with any existing metadata; does not overwrite unrelated keys.
    """
    from datetime import datetime, timezone  # noqa: PLC0415
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with conn.cursor() as cur:
        cur.execute("SELECT nlp_metadata FROM firs WHERE id = %s", (fir_id,))
        row = cur.fetchone()
        existing = (row[0] if row and row[0] else {}) or {}
        if isinstance(existing, str):
            existing = json.loads(existing)
        existing["recommended_sections"] = recommendations
        existing["compendium_scenarios"] = scenarios
        existing["recommender_act_basis"] = act_basis
        existing["recommender_run_at"] = now.isoformat()
        cur.execute(
            """UPDATE firs
               SET nlp_metadata = %s::jsonb
               WHERE id = %s""",
            (json.dumps(existing, ensure_ascii=False), fir_id),
        )
    conn.commit()


__all__ = ["run_recommender_for_fir"]
