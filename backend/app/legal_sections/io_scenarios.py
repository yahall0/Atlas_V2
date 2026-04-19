"""IO Scenarios knowledge-base — segment + extract from the OCR'd Compendium.

Source: Delhi Police Academy *Compendium of Scenarios for Investigating
Officers, 2024* (188 scanned pages, OCR'd to JSONL by ``scripts/ocr_io_scenarios.py``).

This module:
  - splits the raw OCR text into 18 scenarios using TOC-driven page ranges
  - extracts per-scenario structured fields (title, sections, punishment,
    investigation steps, evidence catalogue, documentation, forms,
    deadlines, actor-role assignments)
  - emits a normalised ``io_scenarios.jsonl`` consumed by the mindmap
    engine and the chargesheet gap analyser

Schema (per scenario):

    {
      "scenario_id": "SCN_001",
      "scenario_name": "Rape with POCSO",
      "applicable_sections": ["BNS 65(1)", "POCSO 4"],
      "punishment_summary": "...",
      "case_facts_template": "...",
      "phases": [
        {
          "phase": "handling_call",
          "title": "HANDLING THE CALL / INFORMATION",
          "sub_blocks": [
            {
              "title": "Whether offense occurred or otherwise",
              "items": [
                { "marker": "(i)", "text": "...", "actor": "IO",
                  "legal_refs": [...], "forms": [...], "deadline": null }
              ]
            }
          ]
        },
        ...
      ],
      "evidence_catalogue": [...],         // derived from items mentioning evidence
      "documentation_required": [...],      // derived from items mentioning forms / artefacts
      "linked_acts": ["BNS","BNSS","BSA","POCSO"],
      "source_pages": [4..15],
      "source_authority": "Delhi Police Academy, Compendium 2024"
    }
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Iterable

DATA = Path(__file__).resolve().parent / "data"
# Source preference: text-extracted pages PDF (preferred) OR OCR fallback
PAGES_TEXT = DATA / "io_scenarios_pages.jsonl"
RAW_OCR = DATA / "io_scenarios_raw_ocr.jsonl"
OUT = DATA / "io_scenarios.jsonl"


# ---------- Scenario page ranges (from the Compendium TOC) ---------- #

# Each entry: scenario_id, name, applicable_sections, punishment_summary,
# page_start (PDF page, 1-indexed), page_end (inclusive)
SCENARIOS: list[dict] = [
    # Page ranges verified against the text-extracted ScenariosDelhiPolice.pdf (202 pages, 20 scenarios).
    {"id": "SCN_001", "name": "Rape with POCSO",
     "sections": ["BNS 65(1)", "POCSO 4"],
     "punishment": "Imprisonment not less than 20 years which may extend up to life imprisonment + fine",
     "page_start": 6, "page_end": 15},
    {"id": "SCN_002", "name": "Dowry Death",
     "sections": ["BNS 80(2)"],
     "punishment": "Imprisonment not less than 7 years; may extend to life imprisonment",
     "page_start": 16, "page_end": 25},
    {"id": "SCN_003", "name": "Murder",
     "sections": ["BNS 103(1)"],
     "punishment": "Death or imprisonment for life",
     "page_start": 26, "page_end": 33},
    {"id": "SCN_004", "name": "Mob Lynching",
     "sections": ["BNS 103(2)"],
     "punishment": "Up to 10 years + fine",
     "page_start": 34, "page_end": 44},
    {"id": "SCN_005", "name": "Accidental Death",
     "sections": ["BNS 106(2)"],
     "punishment": "Up to 10 years + fine",
     "page_start": 45, "page_end": 53},
    {"id": "SCN_006", "name": "Attempt to Murder",
     "sections": ["BNS 109(1)"],
     "punishment": "Death or imprisonment for life",
     "page_start": 54, "page_end": 62},
    {"id": "SCN_007", "name": "Attempt to commit Culpable Homicide",
     "sections": ["BNS 110"],
     "punishment": "Up to 7 years",
     "page_start": 63, "page_end": 70},
    {"id": "SCN_008", "name": "Voluntarily causing Hurt by dangerous weapon",
     "sections": ["BNS 118(1)"],
     "punishment": "Up to 3 years or fine up to Rs. 20,000 or both",
     "page_start": 71, "page_end": 79},
    {"id": "SCN_009", "name": "Voluntarily causing Grievous Hurt by dangerous weapon",
     "sections": ["BNS 118(2)"],
     "punishment": "Not less than 1 year; may extend up to 10 years + fine",
     "page_start": 80, "page_end": 88},
    {"id": "SCN_010", "name": "Causing Hurt by means of Poison",
     "sections": ["BNS 123"],
     "punishment": "Up to 10 years",
     "page_start": 89, "page_end": 98},
    {"id": "SCN_011", "name": "Kidnapping",
     "sections": ["BNS 137"],
     "punishment": "Up to 7 years + fine",
     "page_start": 99, "page_end": 109},
    {"id": "SCN_012", "name": "Kidnapping for ransom",
     "sections": ["BNS 140(2)"],
     "punishment": "Death or imprisonment for life + fine",
     "page_start": 110, "page_end": 120},
    {"id": "SCN_013", "name": "Riot Case",
     "sections": ["BNS 189", "BNS 190", "BNS 191", "BNS 192", "BNS 193", "BNS 194",
                  "BNS 117(5)", "BNS 61", "BNS 3(5)"],
     "punishment": "Imprisonment up to 7 years + fine",
     "page_start": 121, "page_end": 130},
    {"id": "SCN_014", "name": "Snatching",
     "sections": ["BNS 304"],
     "punishment": "Imprisonment up to 3 years + fine",
     "page_start": 131, "page_end": 138},
    {"id": "SCN_015", "name": "Attempt to commit robbery armed with deadly weapon",
     "sections": ["BNS 312"],
     "punishment": "Not less than 7 years",
     "page_start": 139, "page_end": 146},
    {"id": "SCN_016", "name": "Housebreaking by night",
     "sections": ["BNS 331(3)"],
     "punishment": "Up to 10 years",
     "page_start": 147, "page_end": 154},
    {"id": "SCN_017", "name": "Arms Act offences",
     "sections": ["Arms Act § 25", "Arms Act § 21"],
     "punishment": "Not less than 7 years; may extend to 14 years",
     "page_start": 155, "page_end": 161},
    {"id": "SCN_018", "name": "NDPS Act offences",
     "sections": ["NDPS Act"],
     "punishment": "Rigorous imprisonment not less than 10 years; may extend to 20 years",
     "page_start": 162, "page_end": 171},
    {"id": "SCN_019", "name": "Cyber Crime — Call Centre fraud",
     "sections": ["BNS 318(4)", "BNS 319(2)", "IT Act 66/66C/66D (cross-act)"],
     "punishment": "Per offence under BNS / IT Act",
     "page_start": 172, "page_end": 180},
    {"id": "SCN_020", "name": "Cheating-Fraud (general)",
     "sections": ["BNS 318(4)"],
     "punishment": "Per offence under BNS",
     "page_start": 181, "page_end": 202},
]


# ---------- Patterns for structural extraction ---------- #

# Phase header — `1. HANDLING THE CALL/INFORMATION:` (sometimes ends with
# a colon, sometimes not; title may carry parens, slash, dash). The number
# and the title can be on the same line or split across two lines.
PHASE_RE = re.compile(
    r"^(\d{1,2})\.\s+([A-Z][A-Z :/\-\(\)]{4,}?)\s*:?\s*$",
    re.MULTILINE,
)
SUB_BLOCK_RE = re.compile(
    r"^\s*([a-z])\.\s+([^\n]{4,})$",
    re.MULTILINE,
)
# Items use roman-numeral markers in the Compendium: (i), (ii), (iii)…
# Numeric markers like `(1)` only appear *inside* legal-section citations
# such as `section 122 (1)` — never as item prefixes — so excluding them
# from the item alphabet eliminates a major source of mid-sentence splits.
ITEM_RE = re.compile(
    r"^\s*\(([ivxlcdm]+)\)\s+(.+?)(?=^\s*\([ivxlcdm]+\)|^\s*[a-z]\.\s|^\s*\d{1,2}\.\s+[A-Z]|\Z)",
    re.MULTILINE | re.DOTALL,
)
# Page-footer noise injected by PDF text extraction. Stripped before parsing.
PAGE_FOOTER_RE = re.compile(
    r"\s*Delhi\s+Police\s+Academy\s+\d{1,3}\s+Scenarios\s*Handbook\s*",
    re.IGNORECASE,
)

# References inline in a sentence
LEGAL_REF_RE = re.compile(
    r"\b(?:Sec(?:tion)?\.?|Sec)\s*[-–]?\s*(\d+(?:\(\d+\))?(?:\([a-z]\))?)\s+(BNS|BNSS|BSA|POCSO|IPC|CrPC|IT\s+Act|Arms\s+Act|NDPS\s+Act|Indian\s+Evidence\s+Act)\b",
    re.IGNORECASE,
)
ALT_LEGAL_REF_RE = re.compile(
    r"\b(?:U/s|u/s)\s*(\d+(?:\(\d+\))?(?:\([a-z]\))?)\s*(?:of\s+)?(BNS|BNSS|BSA|POCSO|IPC|CrPC|IT\s+Act|Arms\s+Act|NDPS\s+Act)?\b",
    re.IGNORECASE,
)

# Forms / artefacts
FORM_RE = re.compile(
    r"\b(HIF[- ]?I+|IIF[- ]?I+|Parcha[- ]?\d+|MLC|FSL\s+Form|Site\s+Plan|Seizure\s+Memo|Sample\s+Seal|Road\s+Certificate|Arrest\s+Memo|Personal\s+Search\s+Memo|DD\s+Entry|LOC|RUKKA|Forwarding\s+Letter|TIP)\b",
    re.IGNORECASE,
)

# Deadlines (hours / days)
DEADLINE_RE = re.compile(
    r"\b(?:within|in)\s+(\d+)\s*(hours?|hrs?|days?|months?)\b",
    re.IGNORECASE,
)

# Actors
ACTOR_TOKENS = {
    "I.O.": "IO", "IO": "IO", "I.O": "IO", "Investigating Officer": "IO",
    "SHO": "SHO", "DCP": "DCP", "ACP": "ACP",
    "Magistrate": "MAGISTRATE",
    "Doctor": "DOCTOR", "Female Doctor": "DOCTOR",
    "FSL": "FSL", "Forensic": "FSL",
    "MHCR": "MHC", "MHCM": "MHC",
    "CCTNS": "CCTNS_OPERATOR",
    "CWC": "CWC",
}
EVIDENCE_KEYWORDS = re.compile(
    r"\b(MLC|PM\s+report|Post[- ]?Mortem|FSL|forensic|DNA|CCTV|CDR|IPDR|"
    r"weapon|exhibit|seizure|chain\s+of\s+custody|finger\s*print|hash\s+value|"
    r"sample\s+seal|video[- ]?graph|photograph)\b",
    re.IGNORECASE,
)


# ---------- Data classes ---------- #


@dataclass
class Item:
    marker: str
    text: str
    actors: list[str] = field(default_factory=list)
    legal_refs: list[dict] = field(default_factory=list)
    forms: list[str] = field(default_factory=list)
    deadline: str | None = None
    is_evidence: bool = False


@dataclass
class SubBlock:
    label: str
    title: str
    items: list[Item] = field(default_factory=list)


@dataclass
class Phase:
    number: int
    title: str
    sub_blocks: list[SubBlock] = field(default_factory=list)


@dataclass
class IOScenario:
    scenario_id: str
    scenario_name: str
    applicable_sections: list[str]
    punishment_summary: str
    page_start: int
    page_end: int
    case_facts_template: str = ""
    phases: list[Phase] = field(default_factory=list)
    evidence_catalogue: list[str] = field(default_factory=list)
    documentation_required: list[str] = field(default_factory=list)
    forms_required: list[str] = field(default_factory=list)
    deadlines: list[str] = field(default_factory=list)
    linked_acts: list[str] = field(default_factory=list)
    source_authority: str = "Delhi Police Academy, Compendium of Scenarios for Investigating Officers, 2024"


# ---------- Parsing ---------- #


def _join_pages(raw: list[dict], page_start: int, page_end: int) -> str:
    chunks: list[str] = []
    for r in raw:
        if page_start <= r["page"] <= page_end:
            chunks.append(r["text"])
    joined = "\n".join(chunks)
    # Strip page-footer noise that PDF extraction injects mid-body
    # (e.g. "Delhi Police Academy 73 Scenarios Handbook"). Replace with a
    # single space so we don't accidentally glue surrounding tokens.
    joined = PAGE_FOOTER_RE.sub(" ", joined)
    return joined


def _extract_legal_refs(text: str) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for m in LEGAL_REF_RE.finditer(text):
        sec, act = m.group(1), re.sub(r"\s+", " ", m.group(2)).upper()
        key = f"{act}|{sec}"
        if key not in seen:
            seen.add(key)
            out.append({"act": act, "section": sec})
    for m in ALT_LEGAL_REF_RE.finditer(text):
        sec = m.group(1)
        act = (m.group(2) or "BNS").upper()
        act = re.sub(r"\s+", " ", act).strip()
        key = f"{act}|{sec}"
        if key not in seen:
            seen.add(key)
            out.append({"act": act, "section": sec})
    return out


def _extract_forms(text: str) -> list[str]:
    found: list[str] = []
    for m in FORM_RE.finditer(text):
        v = re.sub(r"\s+", " ", m.group(0)).strip()
        if v not in found:
            found.append(v)
    return found


def _extract_deadline(text: str) -> str | None:
    m = DEADLINE_RE.search(text)
    if m:
        return f"{m.group(1)} {m.group(2)}"
    return None


def _extract_actors(text: str) -> list[str]:
    found: list[str] = []
    for token, code in ACTOR_TOKENS.items():
        if token.lower() in text.lower() and code not in found:
            found.append(code)
    return found


def _is_evidence(text: str) -> bool:
    return bool(EVIDENCE_KEYWORDS.search(text))


def parse_scenario(spec: dict, raw: list[dict]) -> IOScenario:
    text = _join_pages(raw, spec["page_start"], spec["page_end"])

    sc = IOScenario(
        scenario_id=spec["id"],
        scenario_name=spec["name"],
        applicable_sections=list(spec["sections"]),
        punishment_summary=spec["punishment"],
        page_start=spec["page_start"],
        page_end=spec["page_end"],
        linked_acts=sorted({a.split()[0] for a in spec["sections"]}),
    )

    # Locate phase headers
    phase_matches = list(PHASE_RE.finditer(text))
    if not phase_matches:
        # fallback: whole text as one unstructured phase
        sc.phases.append(Phase(number=1, title="UNSTRUCTURED",
                               sub_blocks=[SubBlock(label="a", title="(raw)",
                                                    items=[Item(marker="(0)", text=text[:4000])])]))
        return sc

    # Capture optional case-facts paragraph above the first phase
    pre = text[:phase_matches[0].start()].strip()
    facts = re.search(r'(?:Scenario|"|"|"|`")\s*[:\-]?\s*"?(.{60,800}?)"?(?:\n\n|$)', pre, re.DOTALL)
    if facts:
        sc.case_facts_template = re.sub(r"\s+", " ", facts.group(1)).strip()

    for i, pm in enumerate(phase_matches):
        phase_num = int(pm.group(1))
        phase_title = pm.group(2).strip()
        phase_start = pm.end()
        phase_end = phase_matches[i + 1].start() if i + 1 < len(phase_matches) else len(text)
        phase_text = text[phase_start:phase_end]
        phase = Phase(number=phase_num, title=phase_title)

        # Find sub-blocks (a. b. c.) within the phase. If none exist, parse
        # items directly under the phase as a single, unnamed group.
        sub_matches = list(SUB_BLOCK_RE.finditer(phase_text))
        if not sub_matches:
            sub_blocks_iter = [(0, len(phase_text), "", "")]
        else:
            sub_blocks_iter = []
            for j, sm in enumerate(sub_matches):
                end = sub_matches[j + 1].start() if j + 1 < len(sub_matches) else len(phase_text)
                sub_blocks_iter.append((sm.end(), end, sm.group(1), sm.group(2).strip()))

        for start, end, label, title in sub_blocks_iter:
            sub_text = phase_text[start:end]
            items: list[Item] = []
            for im in ITEM_RE.finditer(sub_text):
                marker = f"({im.group(1)})"
                item_text = re.sub(r"\s+", " ", im.group(2)).strip()
                if len(item_text) < 5:
                    continue
                items.append(Item(
                    marker=marker,
                    text=item_text,
                    actors=_extract_actors(item_text),
                    legal_refs=_extract_legal_refs(item_text),
                    forms=_extract_forms(item_text),
                    deadline=_extract_deadline(item_text),
                    is_evidence=_is_evidence(item_text),
                ))

            # Skip empty placeholder sub-blocks: nothing to label, nothing to
            # render. Cleaner to drop than to surface an "(default)" stub.
            if not items and not title:
                continue

            sb = SubBlock(
                label=label or "·",
                title=title or "(no sub-block heading in source)",
            )
            sb.items = items
            phase.sub_blocks.append(sb)

        sc.phases.append(phase)

    # Aggregate evidence + documentation + forms + deadlines from items
    for ph in sc.phases:
        for sb in ph.sub_blocks:
            for it in sb.items:
                if it.is_evidence and it.text not in sc.evidence_catalogue:
                    sc.evidence_catalogue.append(it.text)
                for f in it.forms:
                    if f not in sc.forms_required:
                        sc.forms_required.append(f)
                if it.deadline and it.deadline not in sc.deadlines:
                    sc.deadlines.append(it.deadline)

    return sc


def _scenario_to_jsonable(sc: IOScenario) -> dict:
    d = asdict(sc)
    return d


# ---------- Public API ---------- #


def build_kb(raw_path: Path | None = None, out_path: Path | None = None) -> int:
    # Prefer the text-extracted file; fall back to OCR output if only that
    # exists. Both share the {"page": int, "text": str} shape.
    if raw_path is None:
        if PAGES_TEXT.exists():
            raw_path = PAGES_TEXT
        elif RAW_OCR.exists():
            raw_path = RAW_OCR
        else:
            raise FileNotFoundError(
                "Run scripts/extract_io_scenarios.py (preferred) "
                "or scripts/ocr_io_scenarios.py first; no source available"
            )
    out_path = out_path or OUT
    raw = [json.loads(l) for l in raw_path.open(encoding="utf-8")]

    scenarios: list[IOScenario] = []
    for spec in SCENARIOS:
        try:
            scenarios.append(parse_scenario(spec, raw))
        except Exception as exc:
            print(f"[WARN] {spec['id']} parse failed: {exc}")

    with out_path.open("w", encoding="utf-8") as fh:
        for sc in scenarios:
            fh.write(json.dumps(_scenario_to_jsonable(sc), ensure_ascii=False) + "\n")
    return len(scenarios)


def load_kb(path: Path | None = None) -> list[dict]:
    p = path or OUT
    if not p.exists():
        return []
    return [json.loads(l) for l in p.open(encoding="utf-8")]


def find_scenarios_for_sections(citations: Iterable[str]) -> list[dict]:
    """Return KB entries whose ``applicable_sections`` overlap any of ``citations``.

    Used by the mindmap engine to pick a Compendium-grounded template, and by
    the chargesheet gap analyser to surface the per-scenario evidence and
    documentation checklist.
    """
    cites = {c.strip() for c in citations}
    out = []
    for sc in load_kb():
        if cites & set(sc.get("applicable_sections", [])):
            out.append(sc)
    return out


__all__ = [
    "SCENARIOS", "IOScenario", "Item", "Phase", "SubBlock",
    "build_kb", "load_kb", "find_scenarios_for_sections",
]
