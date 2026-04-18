"""Smoke test for the 3-layer KB refactor.

No DB required. Validates that:

  1. The KBLayer enum, derivation helper, and Pydantic seed schema are
     internally consistent.
  2. Every existing seed YAML still parses with the new schema (i.e. the
     refactor is back-compat for unmodified seeds).
  3. The new Layer-2 (playbook) and Layer-3 (case-law) seed YAMLs declare
     the right kb_layer / authored_by_role / update_cadence triple.
  4. The auto-derivation logic in `derive_kb_layer` matches the SQL
     backfill in migration 012 for every (branch_type, tier) pair we use.
  5. The mindmap adapter's _BRANCH_ORDER_BY_LAYER includes every branch
     type that appears in seeds — so no node gets silently swallowed.

Run with:  python -m pytest backend/tests/test_kb_3layer_smoke.py -q
Or directly: python backend/tests/test_kb_3layer_smoke.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make `app.*` importable when run as a plain script.
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import yaml  # noqa: E402

from app.mindmap.kb.schemas import (  # noqa: E402
    AuthoredByRole,
    KBLayer,
    SeedOffence,
    UpdateCadence,
    derive_kb_layer,
)
from app.mindmap.kb.mindmap_adapter import _BRANCH_ORDER_BY_LAYER  # noqa: E402


_SEED_DIR = _BACKEND_ROOT / "app" / "mindmap" / "kb_seed"


def _load_all_seeds() -> list[tuple[Path, SeedOffence]]:
    seeds: list[tuple[Path, SeedOffence]] = []
    for fp in sorted(_SEED_DIR.rglob("*.yaml")):
        raw = yaml.safe_load(fp.read_text(encoding="utf-8"))
        if not raw:
            continue
        seeds.append((fp, SeedOffence.model_validate(raw)))
    return seeds


def test_derivation_matches_migration_backfill():
    """The Python helper must agree with the SQL CASE in 012_add_kb_layer.

    Migration mapping:
      tier=judgment_derived              -> case_law_intelligence
      branch_type=gap_historical (canon) -> case_law_intelligence
      branch_type=legal_section (canon)  -> canonical_legal
      otherwise (canonical)              -> investigation_playbook
    """
    cases = [
        ("legal_section",       "canonical",        KBLayer.CANONICAL_LEGAL),
        ("immediate_action",    "canonical",        KBLayer.INVESTIGATION_PLAYBOOK),
        ("panchnama",           "canonical",        KBLayer.INVESTIGATION_PLAYBOOK),
        ("evidence",            "canonical",        KBLayer.INVESTIGATION_PLAYBOOK),
        ("witness_bayan",       "canonical",        KBLayer.INVESTIGATION_PLAYBOOK),
        ("forensic",            "canonical",        KBLayer.INVESTIGATION_PLAYBOOK),
        ("procedural_safeguard","canonical",        KBLayer.INVESTIGATION_PLAYBOOK),
        ("gap_historical",      "canonical",        KBLayer.CASE_LAW_INTELLIGENCE),
        ("legal_section",       "judgment_derived", KBLayer.CASE_LAW_INTELLIGENCE),
        ("evidence",            "judgment_derived", KBLayer.CASE_LAW_INTELLIGENCE),
    ]
    for bt, tier, expected in cases:
        actual = derive_kb_layer(bt, tier)
        assert actual is expected, (
            f"derive_kb_layer({bt!r}, {tier!r}) == {actual.value} "
            f"(expected {expected.value}); SQL backfill in migration 012 "
            f"would diverge from runtime."
        )


def test_all_seeds_parse_with_new_schema():
    seeds = _load_all_seeds()
    assert seeds, "No seed YAMLs found — did the seed dir move?"
    for fp, seed in seeds:
        assert seed.offence_code, f"{fp.name}: missing offence_code"
        for n in seed.knowledge_nodes:
            # Every node must successfully resolve to a layer + author + cadence,
            # whether declared in YAML or auto-derived.
            layer = n.resolved_layer()
            author = n.resolved_author()
            cadence = n.resolved_cadence()
            assert isinstance(layer, KBLayer), f"{fp.name}: bad layer for {n.title_en!r}"
            assert isinstance(author, AuthoredByRole), f"{fp.name}: bad author"
            assert isinstance(cadence, UpdateCadence), f"{fp.name}: bad cadence"


def test_legacy_seeds_auto_derive_into_correct_layer():
    """The old murder seed (pre-refactor) declares no kb_layer fields.
    Auto-derivation must place its nodes correctly across all 3 layers.
    """
    fp = _SEED_DIR / "violent_crimes" / "bns_s103_murder.yaml"
    seed = SeedOffence.model_validate(yaml.safe_load(fp.read_text(encoding="utf-8")))

    by_layer: dict[KBLayer, int] = {l: 0 for l in KBLayer}
    for n in seed.knowledge_nodes:
        by_layer[n.resolved_layer()] += 1

    # The legacy murder seed has all three node families:
    #   - several legal_section nodes        -> Layer 1
    #   - many panchnama/evidence/etc nodes  -> Layer 2
    #   - several gap_historical nodes       -> Layer 3
    assert by_layer[KBLayer.CANONICAL_LEGAL] >= 3, (
        f"Expected >=3 statute nodes, got {by_layer[KBLayer.CANONICAL_LEGAL]}"
    )
    assert by_layer[KBLayer.INVESTIGATION_PLAYBOOK] >= 10, (
        f"Expected >=10 playbook nodes, got {by_layer[KBLayer.INVESTIGATION_PLAYBOOK]}"
    )
    assert by_layer[KBLayer.CASE_LAW_INTELLIGENCE] >= 1, (
        f"Expected >=1 case-law node, got {by_layer[KBLayer.CASE_LAW_INTELLIGENCE]}"
    )


def test_new_playbook_seed_is_pure_layer_2():
    fp = _SEED_DIR / "violent_crimes" / "playbook_blood_forensics_murder.yaml"
    seed = SeedOffence.model_validate(yaml.safe_load(fp.read_text(encoding="utf-8")))
    assert seed.knowledge_nodes, "Playbook seed has no nodes"
    for n in seed.knowledge_nodes:
        assert n.resolved_layer() is KBLayer.INVESTIGATION_PLAYBOOK, (
            f"Playbook node {n.title_en!r} resolved to {n.resolved_layer().value}, "
            f"expected investigation_playbook"
        )
        assert n.resolved_author() is AuthoredByRole.SOP_COMMITTEE
        assert n.resolved_cadence() is UpdateCadence.ANNUAL


def test_new_caselaw_seed_is_pure_layer_3():
    fp = _SEED_DIR / "violent_crimes" / "caselaw_murder_acquittal_patterns.yaml"
    seed = SeedOffence.model_validate(yaml.safe_load(fp.read_text(encoding="utf-8")))
    assert seed.knowledge_nodes, "Case-law seed has no nodes"
    for n in seed.knowledge_nodes:
        assert n.resolved_layer() is KBLayer.CASE_LAW_INTELLIGENCE, (
            f"Case-law node {n.title_en!r} resolved to {n.resolved_layer().value}"
        )
        assert n.resolved_author() is AuthoredByRole.JUDGMENT_EXTRACTION
        assert n.resolved_cadence() is UpdateCadence.CONTINUOUS


def test_mindmap_adapter_handles_every_branch_type():
    """Every branch_type that appears anywhere in the seeds must be present
    in at least one layer's _BRANCH_ORDER_BY_LAYER list, otherwise mindmap
    rendering would silently drop those nodes.
    """
    seeds = _load_all_seeds()
    seen_branches: set[str] = set()
    for _, seed in seeds:
        for n in seed.knowledge_nodes:
            seen_branches.add(n.branch_type.value)

    listed: set[str] = set()
    for branches in _BRANCH_ORDER_BY_LAYER.values():
        listed.update(branches)

    missing = seen_branches - listed
    assert not missing, (
        f"branch_types appear in seeds but not in _BRANCH_ORDER_BY_LAYER: {missing}. "
        f"The mindmap adapter would silently drop these nodes."
    )


def _summary() -> None:
    seeds = _load_all_seeds()
    counts = {l: 0 for l in KBLayer}
    for _, seed in seeds:
        for n in seed.knowledge_nodes:
            counts[n.resolved_layer()] += 1
    total_seeds = len(seeds)
    total_nodes = sum(counts.values())
    print(f"Loaded {total_seeds} seed files, {total_nodes} nodes total.")
    for layer, c in counts.items():
        print(f"  {layer.value:24s} {c:4d} nodes")


if __name__ == "__main__":
    # Manual run: execute every test_* function so we get a clear pass/fail
    # readout without requiring pytest to be installed in the dev env.
    import traceback

    failures = 0
    tests = [
        test_derivation_matches_migration_backfill,
        test_all_seeds_parse_with_new_schema,
        test_legacy_seeds_auto_derive_into_correct_layer,
        test_new_playbook_seed_is_pure_layer_2,
        test_new_caselaw_seed_is_pure_layer_3,
        test_mindmap_adapter_handles_every_branch_type,
    ]
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except AssertionError as exc:
            failures += 1
            print(f"  FAIL  {t.__name__}: {exc}")
        except Exception:
            failures += 1
            print(f"  ERROR {t.__name__}:")
            traceback.print_exc()
    print()
    _summary()
    sys.exit(0 if failures == 0 else 1)
