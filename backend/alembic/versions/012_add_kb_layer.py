"""Add 3-layer KB (Canonical Legal / Investigation Playbook / Case Law Intelligence).

Revision ID: 012
Revises: 011
Create Date: 2026-04-18

Refactors the 2-tier KB (canonical / judgment_derived) into an explicit
3-layer model on top of the existing schema. Adds:

  * kb_layer            — which of the three layers this node belongs to
  * authored_by_role    — provenance of the node (legal_advisor / sop_committee /
                          judgment_extraction)
  * update_cadence      — how often the node is expected to change
                          (rare / annual / continuous)

Existing rows are backfilled from (tier, branch_type) so the change is
non-breaking. The mapping is:

  canonical + legal_section                                  -> canonical_legal
  canonical + {immediate_action, panchnama, evidence,
               witness_bayan, forensic, procedural_safeguard} -> investigation_playbook
  canonical + gap_historical                                  -> case_law_intelligence
  judgment_derived (any branch)                               -> case_law_intelligence
"""

from __future__ import annotations

from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add nullable columns first so the backfill has a target.
    op.execute(
        """
        ALTER TABLE legal_kb_knowledge_nodes
            ADD COLUMN IF NOT EXISTS kb_layer         TEXT,
            ADD COLUMN IF NOT EXISTS authored_by_role TEXT,
            ADD COLUMN IF NOT EXISTS update_cadence   TEXT;
        """
    )

    # 2. Backfill kb_layer from existing (tier, branch_type) pairs.
    op.execute(
        """
        UPDATE legal_kb_knowledge_nodes
        SET kb_layer = CASE
            WHEN tier = 'judgment_derived'           THEN 'case_law_intelligence'
            WHEN branch_type = 'gap_historical'      THEN 'case_law_intelligence'
            WHEN branch_type = 'legal_section'       THEN 'canonical_legal'
            ELSE 'investigation_playbook'
        END
        WHERE kb_layer IS NULL;
        """
    )

    # 3. Backfill authored_by_role from kb_layer.
    op.execute(
        """
        UPDATE legal_kb_knowledge_nodes
        SET authored_by_role = CASE kb_layer
            WHEN 'canonical_legal'         THEN 'legal_advisor'
            WHEN 'investigation_playbook'  THEN 'sop_committee'
            WHEN 'case_law_intelligence'   THEN 'judgment_extraction'
        END
        WHERE authored_by_role IS NULL;
        """
    )

    # 4. Backfill update_cadence from kb_layer (matches the user-stated cadence).
    op.execute(
        """
        UPDATE legal_kb_knowledge_nodes
        SET update_cadence = CASE kb_layer
            WHEN 'canonical_legal'         THEN 'rare'
            WHEN 'investigation_playbook'  THEN 'annual'
            WHEN 'case_law_intelligence'   THEN 'continuous'
        END
        WHERE update_cadence IS NULL;
        """
    )

    # 5. Lock down the kb_layer column with NOT NULL + CHECK.
    op.execute(
        """
        ALTER TABLE legal_kb_knowledge_nodes
            ALTER COLUMN kb_layer SET NOT NULL;
        """
    )
    op.execute(
        """
        ALTER TABLE legal_kb_knowledge_nodes
            ADD CONSTRAINT chk_kb_layer
            CHECK (kb_layer IN (
                'canonical_legal',
                'investigation_playbook',
                'case_law_intelligence'
            ));
        """
    )
    op.execute(
        """
        ALTER TABLE legal_kb_knowledge_nodes
            ADD CONSTRAINT chk_authored_by_role
            CHECK (authored_by_role IN (
                'legal_advisor',
                'sop_committee',
                'judgment_extraction',
                'manual_curation'
            ));
        """
    )
    op.execute(
        """
        ALTER TABLE legal_kb_knowledge_nodes
            ADD CONSTRAINT chk_update_cadence
            CHECK (update_cadence IN ('rare', 'annual', 'continuous'));
        """
    )

    # 6. Index for fast layer-grouped retrieval.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_kb_nodes_layer
        ON legal_kb_knowledge_nodes (kb_layer, branch_type, approval_status);
        """
    )

    # 7. Add kb_layer + kb_node_ref to chargesheet_gaps so the gap analysis
    #    can attribute every gap to one of the three KB layers and link
    #    back to the canonical node that justifies the finding.
    op.execute(
        """
        ALTER TABLE chargesheet_gaps
            ADD COLUMN IF NOT EXISTS kb_layer    TEXT,
            ADD COLUMN IF NOT EXISTS kb_node_ref UUID;
        """
    )
    op.execute(
        """
        ALTER TABLE chargesheet_gaps
            ADD CONSTRAINT chk_gaps_kb_layer
            CHECK (kb_layer IS NULL OR kb_layer IN (
                'canonical_legal',
                'investigation_playbook',
                'case_law_intelligence'
            ));
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_gaps_kb_layer
        ON chargesheet_gaps (report_id, kb_layer, severity);
        """
    )

    # Allow gap categories that map to the playbook / case-law layers.
    op.execute("ALTER TABLE chargesheet_gaps DROP CONSTRAINT IF EXISTS chargesheet_gaps_category_check;")
    op.execute(
        """
        ALTER TABLE chargesheet_gaps
            ADD CONSTRAINT chargesheet_gaps_category_check
            CHECK (category IN (
                'legal','evidence','witness','procedural',
                'mindmap_divergence','completeness',
                'kb_playbook_gap','kb_caselaw_gap'
            ));
        """
    )
    op.execute("ALTER TABLE chargesheet_gaps DROP CONSTRAINT IF EXISTS chargesheet_gaps_source_check;")
    op.execute(
        """
        ALTER TABLE chargesheet_gaps
            ADD CONSTRAINT chargesheet_gaps_source_check
            CHECK (source IN (
                'T54_legal_validator','T55_evidence_ml',
                'mindmap_diff','completeness_rules','manual_review',
                'kb_playbook','kb_caselaw'
            ));
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_gaps_kb_layer;")
    op.execute(
        """
        ALTER TABLE chargesheet_gaps
            DROP CONSTRAINT IF EXISTS chargesheet_gaps_source_check,
            DROP CONSTRAINT IF EXISTS chargesheet_gaps_category_check,
            DROP CONSTRAINT IF EXISTS chk_gaps_kb_layer,
            DROP COLUMN IF EXISTS kb_node_ref,
            DROP COLUMN IF EXISTS kb_layer;
        """
    )
    # Restore original CHECK constraints on chargesheet_gaps for cleanliness.
    op.execute(
        """
        ALTER TABLE chargesheet_gaps
            ADD CONSTRAINT chargesheet_gaps_category_check
            CHECK (category IN (
                'legal','evidence','witness','procedural',
                'mindmap_divergence','completeness'
            )),
            ADD CONSTRAINT chargesheet_gaps_source_check
            CHECK (source IN (
                'T54_legal_validator','T55_evidence_ml',
                'mindmap_diff','completeness_rules','manual_review'
            ));
        """
    )

    op.execute("DROP INDEX IF EXISTS idx_kb_nodes_layer;")
    op.execute(
        """
        ALTER TABLE legal_kb_knowledge_nodes
            DROP CONSTRAINT IF EXISTS chk_update_cadence,
            DROP CONSTRAINT IF EXISTS chk_authored_by_role,
            DROP CONSTRAINT IF EXISTS chk_kb_layer,
            DROP COLUMN IF EXISTS update_cadence,
            DROP COLUMN IF EXISTS authored_by_role,
            DROP COLUMN IF EXISTS kb_layer;
        """
    )
