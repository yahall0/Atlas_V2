"""Unit tests for the conflict and over-charging guard."""
from __future__ import annotations

from backend.app.legal_sections.conflicts import (
    RecommendContext,
    evaluate,
)


def test_incompatible_pair_bns_101_and_105_flagged():
    ctx = RecommendContext(fir_narrative="...", accused_count=1)
    findings = evaluate(["BNS 101", "BNS 105"], ctx)
    rule_ids = {f.rule_id for f in findings}
    assert "INC-001" in rule_ids


def test_incompatible_pair_only_one_present_no_flag():
    ctx = RecommendContext(fir_narrative="...", accused_count=1)
    findings = evaluate(["BNS 101"], ctx)
    rule_ids = {f.rule_id for f in findings}
    assert "INC-001" not in rule_ids


def test_required_companion_common_intention_when_multiple_accused():
    ctx = RecommendContext(
        fir_narrative="three accused beat the complainant",
        accused_count=3,
    )
    findings = evaluate(["BNS 115(2)", "BNS 118(1)"], ctx)
    rule_ids = {f.rule_id for f in findings}
    assert "REQ-001" in rule_ids
    req = next(f for f in findings if f.rule_id == "REQ-001")
    assert "BNS 3(5)" in req.affected_citations


def test_required_companion_not_triggered_for_single_accused():
    ctx = RecommendContext(
        fir_narrative="single attacker",
        accused_count=1,
    )
    findings = evaluate(["BNS 115(2)"], ctx)
    rule_ids = {f.rule_id for f in findings}
    assert "REQ-001" not in rule_ids


def test_overcharging_guard_bns_305a_without_dwelling_facts():
    ctx = RecommendContext(
        fir_narrative="theft of cattle from open field",
        accused_count=1,
    )
    findings = evaluate(["BNS 305(a)"], ctx)
    rule_ids = {f.rule_id for f in findings}
    assert "OVR-001" in rule_ids


def test_overcharging_guard_bns_305a_satisfied_when_dwelling_present():
    ctx = RecommendContext(
        fir_narrative="theft from a residence at night, lock of door broken",
        accused_count=1,
    )
    findings = evaluate(["BNS 305(a)"], ctx)
    rule_ids = {f.rule_id for f in findings}
    assert "OVR-001" not in rule_ids


def test_overcharging_guard_bns_117_2_without_grievous_facts():
    # Narrative deliberately omits any keyword from the guard's regex set
    # (grievous, fracture, MLC, hospital, etc.) — so the guard should fire.
    ctx = RecommendContext(
        fir_narrative="accused slapped the complainant once on the cheek during an argument",
        accused_count=1,
    )
    findings = evaluate(["BNS 117(2)"], ctx)
    rule_ids = {f.rule_id for f in findings}
    assert "OVR-003" in rule_ids


def test_overcharging_guard_bns_310_without_five_or_more():
    ctx = RecommendContext(
        fir_narrative="three accused robbed the complainant",
        accused_count=3,
    )
    findings = evaluate(["BNS 310"], ctx)
    rule_ids = {f.rule_id for f in findings}
    assert "OVR-006" in rule_ids


def test_overcharging_guard_bns_310_satisfied_when_six_accused():
    ctx = RecommendContext(
        fir_narrative="six accused armed with sticks surrounded the complainant and snatched property by force",
        accused_count=6,
    )
    findings = evaluate(["BNS 310"], ctx)
    rule_ids = {f.rule_id for f in findings}
    assert "OVR-006" not in rule_ids


def test_required_companion_housebreak_when_lock_broken():
    ctx = RecommendContext(
        fir_narrative="thief broke the lock of the front door and entered the dwelling",
        accused_count=1,
    )
    findings = evaluate(["BNS 305(a)"], ctx)
    rule_ids = {f.rule_id for f in findings}
    assert "REQ-002" in rule_ids
