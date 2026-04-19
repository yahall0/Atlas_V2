"""Gap aggregation service — T56-E1.

Unifies outputs from T54 legal validator, T55 evidence gap classifier,
mindmap diff (T53-M), and static completeness rules into a single
GapReport snapshot.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psycopg2.extras
from psycopg2.extensions import connection as PgConnection

psycopg2.extras.register_uuid()
logger = logging.getLogger(__name__)

_GENESIS = "GENESIS"
_GENERATOR_VERSION = "gap-aggregator-v2-3layer"
_COMPLETENESS_RULES_DIR = Path(__file__).parent / "completeness_rules"

# Severity ordering for sort
_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "advisory": 4}
# Map T54 severities to our enum
_T54_SEVERITY_MAP = {"CRITICAL": "critical", "ERROR": "high", "WARNING": "medium"}
# Map T55 severities
_T55_SEVERITY_MAP = {"critical": "critical", "important": "high", "suggested": "medium"}

# 3-layer KB attribution. Each gap category names which KB layer the finding
# argues from — so a "legal" gap is anchored in Layer 1 (statute) while an
# "evidence" gap is anchored in Layer 2 (SOP playbook).
_CATEGORY_TO_LAYER = {
    "legal": "canonical_legal",
    "evidence": "investigation_playbook",
    "witness": "investigation_playbook",
    "procedural": "investigation_playbook",
    "completeness": "investigation_playbook",
    "mindmap_divergence": "investigation_playbook",  # refined per-node below
    "kb_playbook_gap": "investigation_playbook",
    "kb_caselaw_gap": "case_law_intelligence",
}

# Minimum severity for KB-driven gaps surfaced from Layer 2/3 missing items.
_KB_GAP_DEFAULT_SEVERITY = {
    "investigation_playbook": "high",
    "case_law_intelligence": "medium",
}

# Keyword-based "is this Layer 2/3 KB node already addressed in the
# chargesheet?" matching. Conservative — we only fire a gap when we are
# fairly sure the chargesheet text doesn't mention it.
_TITLE_TOKEN_MIN_LEN = 4
_MIN_TOKENS_FOR_MATCH = 2


def _dict_cursor(conn: PgConnection):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


def _compute_action_hash(
    gap_id: str, user_id: str, action: str,
    note: str, timestamp: str, previous_hash: str,
) -> str:
    payload = f"{gap_id}|{user_id}|{action}|{note}|{timestamp}|{previous_hash}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ── Source fetchers ──────────────────────────────────────────────────────────

def _fetch_chargesheet(conn: PgConnection, cs_id: uuid.UUID) -> Optional[Dict]:
    with _dict_cursor(conn) as cur:
        cur.execute("SELECT * FROM chargesheets WHERE id = %s", (cs_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def _fetch_linked_fir(conn: PgConnection, cs: Dict) -> Optional[Dict]:
    fir_id = cs.get("fir_id")
    if not fir_id:
        return None
    with _dict_cursor(conn) as cur:
        cur.execute("SELECT * FROM firs WHERE id = %s", (fir_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def _fetch_legal_findings(conn: PgConnection, cs_id: uuid.UUID) -> List[Dict]:
    """Fetch T54 legal validator findings from validation_reports."""
    try:
        with _dict_cursor(conn) as cur:
            cur.execute(
                """SELECT * FROM validation_reports
                   WHERE chargesheet_id = %s
                   ORDER BY created_at DESC LIMIT 1""",
                (cs_id,),
            )
            row = cur.fetchone()
            if not row:
                return []

            report_data = row.get("report_data") or row.get("findings_json") or {}
            if isinstance(report_data, str):
                report_data = json.loads(report_data)

            findings = report_data.get("findings", [])
            if isinstance(findings, list):
                return findings
            return []
    except Exception:
        logger.warning("Could not fetch T54 legal findings for chargesheet %s", cs_id)
        return []


def _fetch_evidence_gaps(conn: PgConnection, cs_id: uuid.UUID) -> List[Dict]:
    """Fetch T55 evidence gap classifier output."""
    try:
        with _dict_cursor(conn) as cur:
            cur.execute(
                """SELECT * FROM evidence_gap_reports
                   WHERE chargesheet_id = %s
                   ORDER BY created_at DESC LIMIT 1""",
                (cs_id,),
            )
            row = cur.fetchone()
            if not row:
                return []

            gaps_data = row.get("gaps_json") or []
            if isinstance(gaps_data, str):
                gaps_data = json.loads(gaps_data)
            return gaps_data if isinstance(gaps_data, list) else []
    except Exception:
        logger.warning("Could not fetch T55 evidence gaps for chargesheet %s", cs_id)
        return []


def _fetch_mindmap_for_fir(conn: PgConnection, fir_id: uuid.UUID) -> Optional[Dict]:
    """Fetch latest active mindmap and its nodes for the linked FIR."""
    try:
        with _dict_cursor(conn) as cur:
            cur.execute(
                """SELECT id FROM chargesheet_mindmaps
                   WHERE fir_id = %s AND status = 'active'
                   ORDER BY generated_at DESC LIMIT 1""",
                (fir_id,),
            )
            mm = cur.fetchone()
            if not mm:
                return None

            cur.execute(
                """SELECT n.*,
                          (SELECT s.status FROM mindmap_node_status s
                           WHERE s.node_id = n.id
                           ORDER BY s.updated_at DESC LIMIT 1) AS current_status
                   FROM mindmap_nodes n
                   WHERE n.mindmap_id = %s""",
                (mm["id"],),
            )
            nodes = [dict(r) for r in cur.fetchall()]
            return {"mindmap_id": mm["id"], "nodes": nodes}
    except Exception:
        logger.warning("Could not fetch mindmap for FIR %s", fir_id)
        return None


# ── Gap converters ───────────────────────────────────────────────────────────

def _convert_legal_findings(findings: List[Dict]) -> List[Dict]:
    """Convert T54 legal validator findings to unified gap format.

    Legal validator findings argue from statute → tagged Layer 1.
    """
    gaps = []
    for f in findings:
        severity = _T54_SEVERITY_MAP.get(f.get("severity", ""), "medium")
        section = f.get("section", "")
        gaps.append({
            "category": "legal",
            "severity": severity,
            "source": "T54_legal_validator",
            "requires_disclaimer": False,
            "title": f.get("description", f.get("rule_id", "Legal finding")),
            "description_md": f.get("recommendation", ""),
            "legal_refs": [{"framework": "IPC", "section": section}] if section else [],
            "remediation": {
                "summary": f.get("recommendation", ""),
                "steps": [],
                "estimated_effort": "minutes",
            },
            "confidence": f.get("confidence", 0.9),
            "tags": [f.get("rule_id", "")] if f.get("rule_id") else [],
            "kb_layer": "canonical_legal",
            "_dedup_key": ("legal", section, f.get("rule_id", "")),
        })
    return gaps


def _convert_evidence_gaps(evidence_gaps: List[Dict]) -> List[Dict]:
    """Convert T55 evidence gap classifier output to unified gap format.

    Evidence-collection failures argue from SOP best practice → Layer 2.
    """
    gaps = []
    for eg in evidence_gaps:
        severity = _T55_SEVERITY_MAP.get(eg.get("severity", ""), "medium")
        gaps.append({
            "category": "evidence",
            "severity": severity,
            "source": "T55_evidence_ml",
            "requires_disclaimer": True,
            "title": f"Evidence Gap: {eg.get('category', 'Unknown')}",
            "description_md": eg.get("recommendation", ""),
            "legal_refs": (
                [{"framework": "CrPC", "section": eg["legal_basis"]}]
                if eg.get("legal_basis") else []
            ),
            "remediation": {
                "summary": eg.get("recommendation", ""),
                "steps": [],
                "estimated_effort": "hours",
            },
            "confidence": eg.get("confidence", 0.7),
            "tags": [eg.get("tier", ""), eg.get("category", "")],
            "kb_layer": "investigation_playbook",
            "_dedup_key": ("evidence", eg.get("category", ""), ""),
        })
    return gaps


def _compute_mindmap_divergences(
    mindmap_data: Dict, cs: Dict,
) -> List[Dict]:
    """Diff: find 'addressed' mindmap nodes with no chargesheet counterpart."""
    if not mindmap_data:
        return []

    cs_text = (cs.get("raw_text") or "").lower()
    cs_evidence = cs.get("evidence_json") or []
    cs_witnesses = cs.get("witnesses_json") or []
    cs_charges = cs.get("charges_json") or []

    divergences = []
    for node in mindmap_data["nodes"]:
        if node.get("current_status") != "addressed":
            continue

        node_type = node.get("node_type", "")
        title = (node.get("title") or "").lower()
        matched = False
        confidence = 0.0

        if node_type == "panchnama":
            if any(kw in cs_text for kw in ["panchnama", "panchnam", title[:20]]):
                matched = True
                confidence = 0.7
        elif node_type == "evidence":
            for ev in cs_evidence if isinstance(cs_evidence, list) else []:
                ev_desc = (ev.get("description") or ev.get("type") or "").lower()
                if any(w in ev_desc for w in title.split()[:3] if len(w) > 3):
                    matched = True
                    confidence = 0.6
                    break
        elif node_type == "witness_bayan":
            if cs_witnesses and len(cs_witnesses) > 0:
                matched = True
                confidence = 0.5
        elif node_type == "forensic":
            if any(kw in cs_text for kw in ["forensic", "fsl", "dna", "ballistic"]):
                matched = True
                confidence = 0.6
        elif node_type == "legal_section":
            bns = node.get("bns_section", "")
            ipc = node.get("ipc_section", "")
            for charge in cs_charges if isinstance(cs_charges, list) else []:
                sec = (charge.get("section") or "").strip()
                if (bns and bns in sec) or (ipc and ipc in sec):
                    matched = True
                    confidence = 0.9
                    break
        else:
            if title[:15] in cs_text:
                matched = True
                confidence = 0.4

        if not matched:
            label = "likely_divergence" if confidence < 0.5 else "possible_divergence"
            # Inherit the KB layer of the mindmap node so the gap shows
            # up in the right authority column on the frontend.
            node_meta = node.get("metadata") or {}
            if isinstance(node_meta, str):
                try:
                    node_meta = json.loads(node_meta)
                except (json.JSONDecodeError, TypeError):
                    node_meta = {}
            kb_layer = node_meta.get("kb_layer") or "investigation_playbook"
            kb_node_ref = node_meta.get("kb_node_id")

            divergences.append({
                "category": "mindmap_divergence",
                "severity": "medium",
                "source": "mindmap_diff",
                "requires_disclaimer": True,
                "title": f"Mindmap Divergence: {node.get('title', 'Unknown')}",
                "description_md": (
                    f"Mindmap node '{node.get('title')}' (type: {node_type}) was marked "
                    f"as 'addressed' in the investigation mindmap, but no corresponding "
                    f"artifact was found in the chargesheet. Classification: {label}."
                ),
                "remediation": {
                    "summary": f"Verify whether {node.get('title')} is reflected in the chargesheet",
                    "steps": [
                        f"Check if {node_type} content is present under a different name",
                        "If missing, add the relevant content to the chargesheet",
                        "If intentionally excluded, document the reason",
                    ],
                    "estimated_effort": "minutes",
                },
                "related_mindmap_node_id": str(node["id"]),
                "confidence": max(0.1, 1.0 - confidence),
                "tags": [label, node_type],
                "kb_layer": kb_layer,
                "kb_node_ref": kb_node_ref,
                "_dedup_key": ("mindmap_divergence", str(node["id"]), ""),
            })

    return divergences


def _run_completeness_rules(cs: Dict, case_category: str) -> List[Dict]:
    """Run static completeness rules against chargesheet data."""
    gaps = []
    rules = _load_completeness_rules(case_category)

    for rule in rules:
        check_type = rule.get("check_type", "")
        config = rule.get("check_config", {})
        failed = False

        if check_type == "field_present":
            field = config.get("field", "")
            val = cs.get(field)
            allow_null = config.get("allow_null", True)
            min_entries = config.get("min_entries", 0)

            if not allow_null and val is None:
                failed = True
            elif min_entries > 0:
                if isinstance(val, list):
                    failed = len(val) < min_entries
                elif isinstance(val, str):
                    try:
                        parsed = json.loads(val) if val else []
                        failed = len(parsed) < min_entries
                    except (json.JSONDecodeError, TypeError):
                        failed = not bool(val)
                else:
                    failed = val is None

        elif check_type == "text_contains":
            raw = (cs.get("raw_text") or "").lower()
            keywords = [k.lower() for k in config.get("keywords", [])]
            min_matches = config.get("min_matches", 1)
            matches = sum(1 for kw in keywords if kw in raw)
            failed = matches < min_matches

        if failed:
            remediation = rule.get("remediation", {})
            category = rule.get("category", "completeness")
            # Each completeness rule may name its own KB layer; otherwise
            # we derive from category so legal-flavoured rules light up
            # Layer 1, evidence/witness rules light up Layer 2, etc.
            layer = rule.get("kb_layer") or _CATEGORY_TO_LAYER.get(category, "investigation_playbook")
            gaps.append({
                "category": category,
                "severity": rule.get("severity", "medium"),
                "source": "completeness_rules",
                "requires_disclaimer": False,
                "title": rule.get("title", "Completeness Issue"),
                "description_md": rule.get("description", ""),
                "remediation": {
                    "summary": remediation.get("summary", ""),
                    "steps": remediation.get("steps", []),
                    "estimated_effort": remediation.get("estimated_effort", "minutes"),
                },
                "confidence": 1.0,
                "tags": [rule.get("id", "")],
                "kb_layer": layer,
                "_dedup_key": (category, rule.get("id", ""), ""),
            })

    return gaps


def _kb_driven_gaps(
    conn: PgConnection,
    cs: Dict,
    case_category: str,
) -> List[Dict]:
    """Pull Layer-2/3 KB nodes for the charged offences and flag the ones
    the chargesheet text doesn't mention.

    This is the wiring that makes the 3-layer KB *consequential* for the
    chargesheet review: every Layer-2 SOP and Layer-3 case-law standard
    becomes a candidate gap. The IO sees not just "what's missing" but
    "what authority says it should have been there."
    """
    # Local import to avoid a hard cross-package import at module load.
    try:
        from app.mindmap.kb.retrieval import get_knowledge_for_mindmap
    except Exception:
        logger.warning("KB retrieval not available; skipping KB-driven gaps")
        return []

    bns_sections = _extract_bns_sections(cs)
    try:
        bundle = get_knowledge_for_mindmap(
            category_id=case_category or "generic",
            detected_bns_sections=bns_sections,
            fir_extracted_data={},
            conn=conn,
        )
    except Exception as exc:
        logger.warning("KB retrieval failed for cs %s: %s", cs.get("id"), exc)
        return []

    cs_text = (cs.get("raw_text") or "").lower()
    cs_evidence = cs.get("evidence_json") or []
    if isinstance(cs_evidence, str):
        try:
            cs_evidence = json.loads(cs_evidence)
        except (json.JSONDecodeError, TypeError):
            cs_evidence = []
    cs_evidence_text = " ".join(
        (ev.get("description") or ev.get("type") or "")
        for ev in cs_evidence
        if isinstance(ev, dict)
    ).lower()

    haystack = cs_text + " " + cs_evidence_text

    grouped = bundle.nodes_by_layer()
    out: List[Dict] = []

    # Only Layer 2 and Layer 3 are surfaced as KB-driven gaps. Layer 1
    # (statute) is already covered by the T54 legal validator and the
    # legal completeness rules.
    for layer_value, category, source in (
        ("investigation_playbook", "kb_playbook_gap", "kb_playbook"),
        ("case_law_intelligence", "kb_caselaw_gap", "kb_caselaw"),
    ):
        from app.mindmap.kb.schemas import KBLayer  # local import
        layer_enum = KBLayer(layer_value)
        nodes = grouped.get(layer_enum, [])

        for node in nodes:
            if not _is_kb_node_addressed(node, haystack):
                title = node.title_en
                priority = (
                    node.priority.value if hasattr(node.priority, "value")
                    else node.priority
                )
                # Critical/high KB nodes pass through their own severity.
                # Medium/low/advisory get capped at the layer default to
                # avoid drowning the IO in advisory noise.
                severity = priority if priority in ("critical", "high") else \
                    _KB_GAP_DEFAULT_SEVERITY[layer_value]

                citations = []
                for cit in (node.legal_basis_citations or []):
                    if hasattr(cit, "framework"):
                        fw, sec = cit.framework, cit.section
                    elif isinstance(cit, dict):
                        fw, sec = cit.get("framework"), cit.get("section")
                    else:
                        continue
                    if fw and sec:
                        citations.append({"framework": fw, "section": sec})

                out.append({
                    "category": category,
                    "severity": severity,
                    "source": source,
                    "requires_disclaimer": True,
                    "title": (
                        f"Missing from chargesheet — {title}"
                        if layer_value == "investigation_playbook"
                        else f"Court-set standard not addressed — {title}"
                    ),
                    "description_md": (node.description_md or "")[:2000],
                    "legal_refs": citations,
                    "remediation": {
                        "summary": (
                            "Chargesheet does not appear to address this "
                            "KB-mandated item. Add the relevant content or "
                            "document why it does not apply."
                        ),
                        "steps": [
                            f"Confirm whether '{title}' is addressed under "
                            f"a different heading.",
                            "If genuinely missing, take corrective action "
                            "(re-record bayan, send sample to FSL, prepare "
                            "supplementary panchnama).",
                            "Attach the additional artifact and update the "
                            "chargesheet evidence schedule.",
                        ],
                        "estimated_effort": "hours",
                    },
                    "confidence": 0.75,
                    "tags": [
                        layer_value,
                        node.branch_type.value if hasattr(node.branch_type, "value") else node.branch_type,
                    ],
                    "kb_layer": layer_value,
                    "kb_node_ref": str(node.id),
                    "_dedup_key": (category, str(node.id), ""),
                })

    return out


def _playbook_driven_gaps(cs: Dict, fir: Optional[Dict]) -> List[Dict]:
    """Compendium-playbook gap detection (ADR-D19).

    For the chargesheet's recommended sections, look up the matching Delhi
    Police Academy Compendium scenarios, aggregate the required forms /
    evidence / deadlines / actors, and emit a gap entry for each item that
    is not detectably present in the chargesheet's text or structured fields.

    The Compendium is the authority — when a Compendium scenario says
    *"FSL Form must be filled and forwarded with Sample Seal"*, the
    chargesheet must show evidence of compliance or the gap surfaces.
    """
    try:
        from app.legal_sections.io_scenarios import (  # noqa: PLC0415
            find_scenarios_for_sections,
        )
        from app.legal_sections.scenario_adapter import (  # noqa: PLC0415
            checklist_for_scenarios,
        )
    except Exception:
        return []

    # Sections to ground the lookup: prefer recommender output (sub-clause precise)
    # then chargesheet's own charges_json.
    citations: list[str] = []
    if fir:
        meta = fir.get("nlp_metadata") or {}
        for r in meta.get("recommended_sections") or []:
            if isinstance(r, str):
                citations.append(r)
            elif isinstance(r, dict) and r.get("canonical_citation"):
                citations.append(r["canonical_citation"])
    if not citations:
        for s in _extract_bns_sections(cs):
            citations.append(s if s.startswith(("BNS ", "IPC ")) else f"BNS {s}")
    if not citations:
        return []

    scenarios = find_scenarios_for_sections(citations)
    if not scenarios:
        return []

    checklist = checklist_for_scenarios(scenarios)

    # Build a single haystack from chargesheet fields the IO would write into
    haystack_parts = [
        cs.get("raw_text") or "",
        json.dumps(cs.get("evidence_json") or [], ensure_ascii=False),
        json.dumps(cs.get("witnesses_json") or [], ensure_ascii=False),
        cs.get("reviewer_notes") or "",
    ]
    haystack = " ".join(haystack_parts).lower()

    gaps: List[Dict] = []

    # Form / artefact gaps — the highest-ROI surface
    for form in checklist.get("forms_required", []):
        form_norm = form.lower()
        if form_norm in haystack:
            continue
        gaps.append({
            "category": "playbook_form_missing",
            "severity": "high",
            "tier": "playbook",
            "description": (
                f"The Delhi Police Academy investigation playbook for this "
                f"offence requires the form / artefact: '{form}'. The "
                f"chargesheet does not appear to record it."
            ),
            "legal_refs": [],
            "remediation": {
                "action": "complete_and_attach",
                "artefact": form,
                "guidance": (
                    "Refer to the Compendium scenario for the precise step in "
                    "which this form is filled / sealed / forwarded."
                ),
            },
            "location": {"source": "playbook"},
            "confidence": 0.85,
            "source": "compendium_playbook",
            "playbook_reference": [
                {"scenario_id": sc["scenario_id"], "name": sc["scenario_name"],
                 "page_start": sc["page_start"], "page_end": sc["page_end"]}
                for sc in scenarios
            ],
        })

    # Critical evidence gaps — items the playbook flagged as evidence
    for ev in checklist.get("evidence_to_collect", []):
        # Reduce noise: only flag items short enough to be actionable
        ev_short = ev[:160].strip()
        # Use first 5 distinctive tokens to test presence
        tokens = [t for t in ev_short.lower().replace(",", " ").split() if len(t) >= 5][:5]
        if tokens and sum(1 for t in tokens if t in haystack) >= 2:
            continue
        gaps.append({
            "category": "playbook_evidence_missing",
            "severity": "medium",
            "tier": "playbook",
            "description": (
                f"Playbook step likely not addressed: \"{ev_short}\""
            ),
            "legal_refs": [],
            "remediation": {
                "action": "address_playbook_step",
                "step_text": ev_short,
            },
            "location": {"source": "playbook"},
            "confidence": 0.55,
            "source": "compendium_playbook",
        })

    # Deadline reminders (informational — surfaces statutory clocks)
    for dl in checklist.get("deadlines", []):
        gaps.append({
            "category": "playbook_deadline_reminder",
            "severity": "low",
            "tier": "playbook",
            "description": (
                f"Statutory clock applicable to this offence: '{dl}'. "
                f"Confirm the chargesheet is filed within this window."
            ),
            "legal_refs": [],
            "remediation": {"action": "verify_deadline_compliance", "deadline": dl},
            "location": {"source": "playbook"},
            "confidence": 1.00,
            "source": "compendium_playbook",
        })

    return gaps


def _extract_bns_sections(cs: Dict) -> list[str]:
    """Best-effort BNS section extraction from the chargesheet.

    Looks at charges_json first (structured) then falls back to a regex
    over raw_text. Used only to seed the KB query — false positives are
    cheap because retrieval has its own category fallback.
    """
    sections: list[str] = []
    charges = cs.get("charges_json") or []
    if isinstance(charges, str):
        try:
            charges = json.loads(charges)
        except (json.JSONDecodeError, TypeError):
            charges = []
    for ch in charges if isinstance(charges, list) else []:
        sec = (ch.get("section") or "").strip() if isinstance(ch, dict) else ""
        if sec:
            sections.append(sec)
    return sections


def _is_kb_node_addressed(node, haystack: str) -> bool:
    """True if the chargesheet appears to mention this KB node already.

    Tokenises the title, drops short tokens, and checks whether at least
    `_MIN_TOKENS_FOR_MATCH` distinctive tokens appear in the haystack.
    Also checks any cited section number.
    """
    title = (node.title_en or "").lower()
    tokens = [
        t for t in title.replace("/", " ").replace("(", " ").replace(")", " ").split()
        if len(t) >= _TITLE_TOKEN_MIN_LEN and t.isalpha()
    ]
    hits = sum(1 for t in tokens if t in haystack)
    if hits >= _MIN_TOKENS_FOR_MATCH:
        return True

    for cit in (node.legal_basis_citations or []):
        if hasattr(cit, "section"):
            sec = (cit.section or "").lower()
        elif isinstance(cit, dict):
            sec = (cit.get("section") or "").lower()
        else:
            continue
        if sec and sec in haystack:
            return True
    return False


def _load_completeness_rules(case_category: str) -> List[Dict]:
    """Load completeness rules for generic + case-specific."""
    rules = []
    for name in ["generic", case_category]:
        fp = _COMPLETENESS_RULES_DIR / f"{name}.json"
        if fp.is_file():
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
                rules.extend(data.get("rules", []))
            except Exception:
                logger.warning("Could not load completeness rules from %s", fp)
    return rules


# ── Dedup + merge ────────────────────────────────────────────────────────────

def _deduplicate(gaps: List[Dict]) -> List[Dict]:
    """Deduplicate gaps by (category, key1, key2). Merge sources if overlapping."""
    seen: Dict[tuple, int] = {}
    result = []

    for gap in gaps:
        key = gap.pop("_dedup_key", None)
        if key and key in seen:
            idx = seen[key]
            existing = result[idx]
            # Merge: keep higher severity
            if _SEVERITY_ORDER.get(gap["severity"], 4) < _SEVERITY_ORDER.get(existing["severity"], 4):
                existing["severity"] = gap["severity"]
            # Combine tags
            existing["tags"] = list(set(existing.get("tags", []) + gap.get("tags", [])))
            # Note combined source
            if gap["source"] not in existing.get("combined_sources", [existing["source"]]):
                existing.setdefault("combined_sources", [existing["source"]])
                existing["combined_sources"].append(gap["source"])
        else:
            if key:
                seen[key] = len(result)
            result.append(gap)

    return result


# ── Persist ──────────────────────────────────────────────────────────────────

def _persist_report(
    conn: PgConnection,
    cs_id: uuid.UUID,
    gaps: List[Dict],
    duration_ms: int,
    partial_sources: List[str],
) -> uuid.UUID:
    """Persist gap report and gaps to database. Returns report ID."""
    report_id = uuid.uuid4()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "advisory": 0}
    for g in gaps:
        sev = g.get("severity", "medium")
        if sev in severity_counts:
            severity_counts[sev] += 1

    version = _GENERATOR_VERSION
    if partial_sources:
        version += "+partial(" + ",".join(partial_sources) + ")"

    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO chargesheet_gap_reports
               (id, chargesheet_id, generated_at, generator_version,
                gap_count, critical_count, high_count, medium_count,
                low_count, advisory_count, generation_duration_ms)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (report_id, cs_id, now, version,
             len(gaps), severity_counts["critical"], severity_counts["high"],
             severity_counts["medium"], severity_counts["low"],
             severity_counts["advisory"], duration_ms),
        )

        for i, gap in enumerate(gaps):
            gap_id = uuid.uuid4()
            legal_refs = gap.get("legal_refs", [])
            remediation = gap.get("remediation", {})
            location = gap.get("location")
            related_node = gap.get("related_mindmap_node_id")
            kb_layer = gap.get("kb_layer")
            kb_node_ref = gap.get("kb_node_ref")

            cur.execute(
                """INSERT INTO chargesheet_gaps
                   (id, report_id, category, severity, source,
                    requires_disclaimer, title, description_md,
                    location, legal_refs, remediation,
                    related_mindmap_node_id, confidence, tags, display_order,
                    kb_layer, kb_node_ref)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                           %s::jsonb, %s::jsonb, %s::jsonb,
                           %s, %s, %s, %s, %s, %s)""",
                (gap_id, report_id, gap["category"], gap["severity"],
                 gap["source"], gap.get("requires_disclaimer", False),
                 gap["title"], gap.get("description_md", ""),
                 json.dumps(location) if location else None,
                 json.dumps(legal_refs),
                 json.dumps(remediation),
                 uuid.UUID(related_node) if related_node else None,
                 gap.get("confidence", 0.0),
                 gap.get("tags", []),
                 i,
                 kb_layer,
                 uuid.UUID(kb_node_ref) if kb_node_ref else None),
            )

    conn.commit()
    return report_id


# ── Fetch helpers ────────────────────────────────────────────────────────────

def _fetch_report(conn: PgConnection, report_id: uuid.UUID) -> Optional[Dict]:
    with _dict_cursor(conn) as cur:
        cur.execute(
            "SELECT * FROM chargesheet_gap_reports WHERE id = %s", (report_id,),
        )
        report = cur.fetchone()
        if not report:
            return None
        report = dict(report)

        cur.execute(
            """SELECT g.*,
                      (SELECT a.action FROM chargesheet_gap_actions a
                       WHERE a.gap_id = g.id
                       ORDER BY a.created_at DESC LIMIT 1) AS current_action
               FROM chargesheet_gaps g
               WHERE g.report_id = %s
               ORDER BY g.display_order""",
            (report_id,),
        )
        gaps = [dict(r) for r in cur.fetchall()]
        report["gaps"] = gaps

        # Per-KB-layer roll-up so the frontend can render three columns.
        layer_counts = {
            "canonical_legal": 0,
            "investigation_playbook": 0,
            "case_law_intelligence": 0,
            "unattributed": 0,
        }
        for g in gaps:
            layer = g.get("kb_layer")
            if layer in layer_counts:
                layer_counts[layer] += 1
            else:
                layer_counts["unattributed"] += 1
        report["layer_counts"] = layer_counts
        return report


# ── Public API ───────────────────────────────────────────────────────────────

def aggregate_gaps(
    chargesheet_id: uuid.UUID,
    *,
    conn: PgConnection,
    regenerate: bool = False,
) -> Dict:
    """Generate (or return existing) gap analysis report.

    Idempotent by default. Set regenerate=True for a new version.
    """
    start = time.monotonic()
    partial_sources: List[str] = []

    cs = _fetch_chargesheet(conn, chargesheet_id)
    if cs is None:
        raise ValueError(f"Chargesheet {chargesheet_id} not found")

    # Idempotency check
    if not regenerate:
        with _dict_cursor(conn) as cur:
            cur.execute(
                """SELECT id FROM chargesheet_gap_reports
                   WHERE chargesheet_id = %s
                   ORDER BY generated_at DESC LIMIT 1""",
                (chargesheet_id,),
            )
            existing = cur.fetchone()
            if existing:
                return _fetch_report(conn, existing["id"])

    # Determine case category from linked FIR
    fir = _fetch_linked_fir(conn, cs)
    case_category = (fir.get("nlp_classification") or "generic") if fir else "generic"

    # 1. T54 legal validator findings
    legal_findings = _fetch_legal_findings(conn, chargesheet_id)
    if not legal_findings:
        partial_sources.append("T54_legal_validator")

    # 2. T55 evidence gap classifier
    evidence_gaps = _fetch_evidence_gaps(conn, chargesheet_id)
    if not evidence_gaps:
        partial_sources.append("T55_evidence_ml")

    # 3. Mindmap diff
    mindmap_data = None
    if fir:
        mindmap_data = _fetch_mindmap_for_fir(conn, fir["id"])
        if not mindmap_data:
            partial_sources.append("mindmap_diff")

    # 4. Static completeness rules
    completeness_gaps = _run_completeness_rules(cs, case_category)

    # 5. KB-driven gaps — Layer 2 (SOP) and Layer 3 (case law) items
    #    that the chargesheet does not appear to address.
    kb_gaps = _kb_driven_gaps(conn, cs, case_category)
    if not kb_gaps:
        partial_sources.append("kb_3layer")

    # 6. Compendium-playbook gaps (ADR-D19) — items from the Delhi Police
    #    Academy investigation playbook that the chargesheet's evidence /
    #    documentation appear to be missing.
    playbook_gaps = _playbook_driven_gaps(cs, fir)
    if not playbook_gaps:
        partial_sources.append("playbook_compendium")

    # Convert and unify
    all_gaps = []
    all_gaps.extend(_convert_legal_findings(legal_findings))
    all_gaps.extend(_convert_evidence_gaps(evidence_gaps))
    if mindmap_data:
        all_gaps.extend(_compute_mindmap_divergences(mindmap_data, cs))
    all_gaps.extend(completeness_gaps)
    all_gaps.extend(kb_gaps)
    all_gaps.extend(playbook_gaps)

    # Deduplicate
    all_gaps = _deduplicate(all_gaps)

    # Sort by severity desc, then confidence desc
    all_gaps.sort(key=lambda g: (
        _SEVERITY_ORDER.get(g["severity"], 4),
        -g.get("confidence", 0),
    ))

    duration_ms = int((time.monotonic() - start) * 1000)

    # Persist
    report_id = _persist_report(conn, chargesheet_id, all_gaps, duration_ms, partial_sources)

    logger.info(
        "Gap report generated: cs=%s, gaps=%d, duration=%dms, partial=%s",
        chargesheet_id, len(all_gaps), duration_ms, partial_sources,
    )

    return _fetch_report(conn, report_id)


def get_latest_report(conn: PgConnection, cs_id: uuid.UUID) -> Optional[Dict]:
    with _dict_cursor(conn) as cur:
        cur.execute(
            """SELECT id FROM chargesheet_gap_reports
               WHERE chargesheet_id = %s
               ORDER BY generated_at DESC LIMIT 1""",
            (cs_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return _fetch_report(conn, row["id"])


def list_reports(conn: PgConnection, cs_id: uuid.UUID) -> List[Dict]:
    with _dict_cursor(conn) as cur:
        cur.execute(
            """SELECT id, chargesheet_id, generated_at, generator_version,
                      gap_count, critical_count, high_count
               FROM chargesheet_gap_reports
               WHERE chargesheet_id = %s
               ORDER BY generated_at DESC""",
            (cs_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def get_report_by_id(conn: PgConnection, report_id: uuid.UUID) -> Optional[Dict]:
    return _fetch_report(conn, report_id)


def add_gap_action(
    conn: PgConnection,
    gap_id: uuid.UUID,
    user_id: str,
    action: str,
    note: str = "",
    modification_diff: str = "",
    evidence_ref: str = "",
    hash_prev: str = "",
) -> Dict:
    """Append a gap action to the hash chain. Returns the new action entry."""
    with _dict_cursor(conn) as cur:
        cur.execute("SELECT id FROM chargesheet_gaps WHERE id = %s", (gap_id,))
        if cur.fetchone() is None:
            raise ValueError(f"Gap {gap_id} not found")

        cur.execute(
            """SELECT hash_self FROM chargesheet_gap_actions
               WHERE gap_id = %s ORDER BY created_at DESC LIMIT 1""",
            (gap_id,),
        )
        latest = cur.fetchone()
        actual_prev = latest["hash_self"] if latest else _GENESIS

        if hash_prev != actual_prev:
            raise ValueError(
                f"Hash chain conflict: expected {actual_prev}, got {hash_prev}"
            )

        now = datetime.now(timezone.utc)
        entry_id = uuid.uuid4()
        hash_self = _compute_action_hash(
            str(gap_id), user_id, action,
            note or "", now.isoformat(), actual_prev,
        )

        cur.execute(
            """INSERT INTO chargesheet_gap_actions
               (id, gap_id, user_id, action, note, modification_diff,
                evidence_ref, created_at, hash_prev, hash_self)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING *""",
            (entry_id, gap_id, user_id, action,
             note or None, modification_diff or None,
             evidence_ref or None, now.replace(tzinfo=None),
             actual_prev, hash_self),
        )
        row = dict(cur.fetchone())
        conn.commit()

    return row


def get_gap_action_history(conn: PgConnection, gap_id: uuid.UUID) -> List[Dict]:
    with _dict_cursor(conn) as cur:
        cur.execute(
            """SELECT * FROM chargesheet_gap_actions
               WHERE gap_id = %s ORDER BY created_at ASC""",
            (gap_id,),
        )
        return [dict(r) for r in cur.fetchall()]
