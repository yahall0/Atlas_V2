"""Conflict detection and over-charging guard.

This module is the difference between an "AI suggestion" and a tool a
prosecutor will trust. It encodes three classes of rule, all reviewable by
the legal panel:

1. **Incompatible pairs.** Two sections that cannot legally co-exist as
   primary charges in the same chargesheet without an explicit alternative
   pleading (``Or, in the alternative, ...``). Example: BNS 101 (murder)
   and BNS 105 (culpable homicide not amounting to murder) on the same
   victim and incident.

2. **Required companions.** When a particular condition is present, a
   companion section MUST be added. Example: when a recommendation set
   contains substantive offences AND the FIR names two or more accused
   acting in concert, BNS 3(5) (or IPC 34) MUST be present.

3. **Over-charging guards.** Pre-conditions that gate a section. If the
   FIR facts do not satisfy the gate, the section is flagged as a likely
   over-charge. Example: BNS 305(a) (theft in a dwelling) requires the FIR
   to mention a dwelling / building / vessel used for human dwelling or
   custody of property.

The output is a list of ``ConflictFinding`` objects. The recommender layer
uses these to (a) drop over-charges below the recommendation floor,
(b) add required companions, and (c) attach a ``conflicts`` array to each
recommendation so the IO sees the warning before filing.

Adding a new rule only requires editing this file. No other module changes
are necessary.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Iterable, Literal

Severity = Literal["block", "warn", "info"]


@dataclass
class ConflictFinding:
    rule_id: str
    severity: Severity
    affected_citations: list[str]
    message: str
    remediation: str | None = None


# ---------- Rule registry ---------- #


@dataclass
class IncompatiblePair:
    rule_id: str
    a: str                   # canonical citation, e.g. "BNS 101"
    b: str                   # canonical citation, e.g. "BNS 105"
    reason: str
    remediation: str
    severity: Severity = "warn"


@dataclass
class RequiredCompanion:
    rule_id: str
    if_any_of: list[str]              # if recommendation set includes any of these
    when: Callable[["RecommendContext"], bool]  # additional condition over context
    must_include: list[str]           # then these citations must be in the set
    reason: str
    severity: Severity = "block"


@dataclass
class OverChargingGuard:
    rule_id: str
    citation: str                                      # e.g. "BNS 305(a)"
    requires_facts_matching: list[str]                 # regex patterns over FIR narrative
    fail_message: str
    severity: Severity = "warn"
    remediation: str = "Re-evaluate this section against the FIR narrative."


@dataclass
class RecommendContext:
    """Inputs to conflict checking."""
    fir_narrative: str
    occurrence_date_iso: str | None = None
    accused_count: int = 1
    fir_metadata: dict = field(default_factory=dict)


# ---------- Built-in rules (legal-panel reviewable) ---------- #

INCOMPATIBLE_PAIRS: list[IncompatiblePair] = [
    IncompatiblePair(
        rule_id="INC-001",
        a="BNS 101",  # Murder
        b="BNS 105",  # Culpable homicide not amounting to murder
        reason="Murder (BNS 101) and culpable homicide not amounting to murder (BNS 105) describe the same act with different mens rea. Charging both as primary, on the same incident and the same victim, is impermissible without an explicit alternative pleading.",
        remediation="Either choose the section that matches the evidence of intention/knowledge, or plead one in the alternative under BNSS § 240 (charge-framing).",
    ),
    IncompatiblePair(
        rule_id="INC-002",
        a="IPC 302",
        b="IPC 304",
        reason="IPC 302 (murder) and IPC 304 (culpable homicide not amounting to murder) describe the same act with different mens rea. Same logic as INC-001.",
        remediation="Charge in the alternative under CrPC § 221, or pick the section that matches the evidence.",
    ),
    IncompatiblePair(
        rule_id="INC-003",
        a="BNS 303",  # Theft (general)
        b="BNS 316",  # Criminal breach of trust
        reason="Theft requires absence of consent at the moment of taking; criminal breach of trust requires entrustment followed by dishonest conversion. The same factual transaction cannot satisfy both.",
        remediation="Choose based on whether the property was entrusted to the accused (CBT) or taken without consent (theft).",
    ),
    IncompatiblePair(
        rule_id="INC-004",
        a="BNS 309",  # Robbery
        b="BNS 310",  # Dacoity
        reason="Robbery (BNS 309) and dacoity (BNS 310) differ by the number of offenders (≥ 5 for dacoity). Both cannot apply to the same incident.",
        remediation="Choose by accused count: ≥ 5 → dacoity; otherwise robbery.",
    ),
]


REQUIRED_COMPANIONS: list[RequiredCompanion] = [
    RequiredCompanion(
        rule_id="REQ-001",
        if_any_of=["BNS 115(2)", "BNS 117(2)", "BNS 118(1)", "BNS 118(2)",
                   "BNS 305(a)", "BNS 305(b)", "BNS 305(c)", "BNS 305(d)", "BNS 305(e)",
                   "BNS 309", "BNS 310",
                   "IPC 323", "IPC 324", "IPC 325", "IPC 326",
                   "IPC 379", "IPC 380", "IPC 392", "IPC 395"],
        when=lambda ctx: ctx.accused_count >= 2,
        must_include=["BNS 3(5)"],  # IPC 34 swap handled by the recommender
        reason="When two or more accused acted in concert, common intention attaches under BNS 3(5) (or IPC 34 for pre-01-Jul-2024 offences). Failure to add the common-intention section weakens joint liability at trial.",
        severity="block",
    ),
    RequiredCompanion(
        rule_id="REQ-002",
        if_any_of=["BNS 305(a)", "BNS 305(b)", "BNS 305(c)", "BNS 305(d)", "BNS 305(e)",
                   "IPC 380"],
        when=lambda ctx: re.search(r"\b(broke|breaking|broken)\b.*\b(lock|door|window|gate|patara|receptacle|box)\b", ctx.fir_narrative, re.IGNORECASE) is not None,
        must_include=["BNS 331(3)"],  # housebreaking-with-intent — IPC 454/457 handled by recommender
        reason="When theft involves breaking a lock or forced entry, housebreaking sections must accompany the theft section.",
        severity="warn",
    ),
    RequiredCompanion(
        rule_id="REQ-003",
        if_any_of=["BNS 305(a)", "BNS 305(b)", "BNS 305(c)", "BNS 305(d)", "BNS 305(e)",
                   "IPC 380"],
        when=lambda ctx: re.search(r"\b(receptacle|steel\s+box|cash\s+box|safe|locker|patara)\b.*\b(broke|broken|forced)\b", ctx.fir_narrative, re.IGNORECASE) is not None,
        must_include=["BNS 334(1)"],
        reason="When the theft involved breaking open a closed receptacle (steel box, safe, locker), BNS 334 should accompany the theft section.",
        severity="warn",
    ),
]


OVER_CHARGING_GUARDS: list[OverChargingGuard] = [
    OverChargingGuard(
        rule_id="OVR-001",
        citation="BNS 305(a)",
        requires_facts_matching=[
            r"\b(house|residence|home|dwelling|building|tent|vessel|patara|locker|safe)\b",
        ],
        fail_message="BNS 305(a) (theft in a dwelling house) requires the FIR to describe a building, tent or vessel used as a human dwelling or for custody of property. The narrative does not appear to describe a dwelling-context.",
        remediation="If the theft was not from a dwelling, charge under BNS 303 (general theft) instead.",
    ),
    OverChargingGuard(
        rule_id="OVR-002",
        citation="BNS 305(d)",
        requires_facts_matching=[
            r"\b(idol|icon|temple|mosque|gurudwara|church|place\s+of\s+worship|dargah|mandir)\b",
        ],
        fail_message="BNS 305(d) (theft of idol/icon from place of worship) requires explicit mention of a place of worship.",
        remediation="If the theft is from a residence, use BNS 305(a) instead.",
    ),
    OverChargingGuard(
        rule_id="OVR-003",
        citation="BNS 117(2)",
        requires_facts_matching=[
            r"\b(grievous|fracture|fractured|dislocation|permanent|disfigur|MLC|medico-?legal|admitted|hospital)\b",
        ],
        fail_message="BNS 117(2) (voluntarily causing grievous hurt) is conditional on the injury qualifying as grievous under BNS 116. The FIR narrative does not describe a grievous injury and no Medico-Legal Certificate (MLC) is referenced.",
        remediation="Defer this section until MLC is obtained. Charge under BNS 115(2) (simple hurt) at FIR registration.",
    ),
    OverChargingGuard(
        rule_id="OVR-004",
        citation="BNS 118(2)",
        requires_facts_matching=[
            r"\b(grievous|fracture|fractured|dislocation|permanent|disfigur|MLC|medico-?legal|admitted|hospital)\b",
        ],
        fail_message="BNS 118(2) (grievous hurt by dangerous weapon) requires both (a) MLC-confirmed grievous hurt AND (b) the weapon to be one likely to cause death.",
        remediation="If MLC is unavailable or injury is simple hurt, charge under BNS 118(1) instead.",
    ),
    OverChargingGuard(
        rule_id="OVR-005",
        citation="BNS 351(3)",
        requires_facts_matching=[
            r"\b(kill|death|murder|cut\s+off|grievous|chop|fire|destroy)\b",
        ],
        fail_message="BNS 351(3) (criminal intimidation by threat of death or grievous hurt) requires the threat to be of that specific kind.",
        remediation="If the threat is of mere injury or annoyance, charge under BNS 351(2) only.",
    ),
    OverChargingGuard(
        rule_id="OVR-006",
        citation="BNS 310",
        requires_facts_matching=[
            r"\b(five|six|seven|eight|nine|ten|gang|group|together|jointly|conjointly)\b",
        ],
        fail_message="BNS 310 (dacoity) requires the offence to be committed by five or more persons. The narrative does not satisfy this threshold.",
        remediation="If accused are fewer than five, use BNS 309 (robbery) instead.",
    ),
]


# ---------- Engine ---------- #


def evaluate(
    recommended_citations: Iterable[str],
    ctx: RecommendContext,
) -> list[ConflictFinding]:
    """Return the union of findings from all three rule families.

    The recommender consumes this list and decides:
      - ``severity = block`` → fix the recommendation set before returning
      - ``severity = warn``  → keep, attach as a flag on each affected entry
      - ``severity = info``  → attach as a soft note
    """
    citations = set(recommended_citations)
    findings: list[ConflictFinding] = []

    # Incompatible pairs
    for rule in INCOMPATIBLE_PAIRS:
        if rule.a in citations and rule.b in citations:
            findings.append(
                ConflictFinding(
                    rule_id=rule.rule_id,
                    severity=rule.severity,
                    affected_citations=[rule.a, rule.b],
                    message=f"{rule.a} and {rule.b} are incompatible: {rule.reason}",
                    remediation=rule.remediation,
                )
            )

    # Required companions
    for rule in REQUIRED_COMPANIONS:
        if not any(c in citations for c in rule.if_any_of):
            continue
        try:
            cond = rule.when(ctx)
        except Exception:
            cond = False
        if not cond:
            continue
        missing = [c for c in rule.must_include if c not in citations]
        if missing:
            findings.append(
                ConflictFinding(
                    rule_id=rule.rule_id,
                    severity=rule.severity,
                    affected_citations=missing,
                    message=f"Required companion section(s) missing: {missing}. {rule.reason}",
                    remediation=f"Add {', '.join(missing)} to the chargeable list.",
                )
            )

    # Over-charging guards
    for rule in OVER_CHARGING_GUARDS:
        if rule.citation not in citations:
            continue
        ok = all(re.search(p, ctx.fir_narrative, re.IGNORECASE) is not None
                 for p in rule.requires_facts_matching)
        if not ok:
            findings.append(
                ConflictFinding(
                    rule_id=rule.rule_id,
                    severity=rule.severity,
                    affected_citations=[rule.citation],
                    message=rule.fail_message,
                    remediation=rule.remediation,
                )
            )

    return findings


__all__ = [
    "Severity",
    "ConflictFinding",
    "RecommendContext",
    "IncompatiblePair",
    "RequiredCompanion",
    "OverChargingGuard",
    "INCOMPATIBLE_PAIRS",
    "REQUIRED_COMPANIONS",
    "OVER_CHARGING_GUARDS",
    "evaluate",
]
