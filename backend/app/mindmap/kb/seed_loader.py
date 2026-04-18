"""KB seed loader — T53-M-KB-2.

Loads YAML seed files into the legal_kb_offences and legal_kb_knowledge_nodes tables.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import psycopg2.extras
from psycopg2.extensions import connection as PgConnection

from app.mindmap.kb.schemas import SeedOffence

psycopg2.extras.register_uuid()
logger = logging.getLogger(__name__)

_GENESIS = "GENESIS"
_SEED_DIR = Path(__file__).parent.parent / "kb_seed"


def _compute_audit_hash(action: str, detail: str, timestamp: str, prev: str) -> str:
    payload = f"{action}|{detail}|{timestamp}|{prev}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _log_audit(
    conn: PgConnection, actor: str, action: str,
    target_type: str, target_id: uuid.UUID,
    after_state: Dict[str, Any],
) -> None:
    """Append an audit log entry."""
    now = datetime.now(timezone.utc).isoformat()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """SELECT hash_self FROM legal_kb_audit_log
               WHERE target_id = %s ORDER BY timestamp DESC LIMIT 1""",
            (target_id,),
        )
        prev = cur.fetchone()
        prev_hash = prev["hash_self"] if prev else _GENESIS

    hash_self = _compute_audit_hash(action, json.dumps(after_state, default=str), now, prev_hash)

    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO legal_kb_audit_log
               (actor_user_id, action, target_type, target_id,
                before_state, after_state, timestamp, hash_prev, hash_self)
               VALUES (%s, %s, %s, %s, NULL, %s::jsonb, %s, %s, %s)""",
            (None, action, target_type, target_id,
             json.dumps(after_state, default=str),
             datetime.now(timezone.utc).replace(tzinfo=None),
             prev_hash, hash_self),
        )


def load_seeds(
    conn: PgConnection,
    seed_dir: Path | None = None,
    version: str = "1.0.0",
) -> Dict[str, int]:
    """Load all YAML seed files into the KB.

    Returns counts: {offences_added, nodes_added}.
    Transactional: all or nothing.
    """
    try:
        import yaml
    except ImportError:
        raise RuntimeError("PyYAML is required for seed loading: pip install pyyaml")

    seed_path = seed_dir or _SEED_DIR
    if not seed_path.is_dir():
        raise RuntimeError(f"Seed directory not found: {seed_path}")

    yaml_files = sorted(seed_path.rglob("*.yaml"))
    if not yaml_files:
        raise RuntimeError(f"No YAML files found in {seed_path}")

    offences_added = 0
    nodes_added = 0

    for fp in yaml_files:
        try:
            raw = yaml.safe_load(fp.read_text(encoding="utf-8"))
            if not raw:
                continue
            seed = SeedOffence.model_validate(raw)
        except Exception as exc:
            raise RuntimeError(f"Invalid seed file {fp.name}: {exc}") from exc

        offence_id = uuid.uuid4()

        with conn.cursor() as cur:
            # Check if offence already exists
            cur.execute(
                "SELECT id FROM legal_kb_offences WHERE offence_code = %s",
                (seed.offence_code,),
            )
            if cur.fetchone():
                logger.info("Offence %s already exists, skipping", seed.offence_code)
                continue

            cur.execute(
                """INSERT INTO legal_kb_offences
                   (id, category_id, offence_code, bns_section, bns_subsection,
                    display_name_en, display_name_gu, short_description_md,
                    punishment, cognizable, bailable, triable_by, compoundable,
                    schedule_reference, related_offence_codes, special_acts,
                    kb_version, review_status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'draft')""",
                (offence_id, seed.category_id, seed.offence_code,
                 seed.bns_section, seed.bns_subsection,
                 seed.display_name_en, seed.display_name_gu,
                 seed.short_description_md, seed.punishment,
                 seed.cognizable, seed.bailable, seed.triable_by,
                 seed.compoundable, seed.schedule_reference,
                 seed.related_offence_codes, seed.special_acts,
                 version),
            )
            offences_added += 1

            _log_audit(conn, "system", "create_offence", "offence", offence_id,
                       {"offence_code": seed.offence_code, "version": version})

            for i, node in enumerate(seed.knowledge_nodes):
                node_id = uuid.uuid4()
                citations = [c.model_dump() for c in node.legal_basis_citations]
                layer = node.resolved_layer().value
                author = node.resolved_author().value
                cadence = node.resolved_cadence().value

                cur.execute(
                    """INSERT INTO legal_kb_knowledge_nodes
                       (id, offence_id, branch_type, tier, priority,
                        title_en, title_gu, description_md,
                        legal_basis_citations, procedural_metadata,
                        requires_disclaimer, display_order, kb_version,
                        created_by, approval_status,
                        kb_layer, authored_by_role, update_cadence)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                               %s::jsonb, %s::jsonb, %s, %s, %s, NULL, 'approved',
                               %s, %s, %s)""",
                    (node_id, offence_id, node.branch_type.value,
                     node.tier.value, node.priority.value,
                     node.title_en, node.title_gu, node.description_md,
                     json.dumps(citations, default=str),
                     json.dumps(node.procedural_metadata, default=str),
                     node.requires_disclaimer, i, version,
                     layer, author, cadence),
                )
                nodes_added += 1

                _log_audit(conn, "system", "add_node", "knowledge_node", node_id,
                           {"title": node.title_en, "offence": seed.offence_code})

        logger.info("Seeded offence %s with %d nodes", seed.offence_code, len(seed.knowledge_nodes))

    # Create version record
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO legal_kb_versions
               (version, released_by, changelog_md, offences_added, nodes_added)
               VALUES (%s, NULL, %s, %s, %s)
               ON CONFLICT (version) DO NOTHING""",
            (version, f"Initial seed: {offences_added} offences, {nodes_added} nodes",
             offences_added, nodes_added),
        )

    conn.commit()
    logger.info("KB seed complete: %d offences, %d nodes, version %s",
                offences_added, nodes_added, version)

    return {"offences_added": offences_added, "nodes_added": nodes_added}
