"""Act registry — the substitution surface for adding new statutes.

Today the platform ships IPC and BNS. Phase 2.7 makes adding a new act —
NDPS, POCSO, IT Act, MV Act, Dowry Prohibition, Arms Act, SC/ST
(Atrocities) Act, Domestic Violence Act, Prohibition Act, Gambling Act —
a *mechanical* operation: drop a configured ``ActSpec`` into the registry
and the rest of the pipeline (extractor, chunker, retriever, recommender)
just works.

Each registered act declares:

* ``code`` — short identifier used as the section-id prefix (e.g. ``NDPS``)
* ``title`` — full title for display and citations
* ``commencement`` — date the act takes effect (used by ``act_for`` if a
  date-driven selection rule is added)
* ``source_pdf`` — path to the official text PDF
* ``act_no`` — formal act-number string for the body-page detector
* ``data_path`` — JSONL output path under ``data/``
* ``date_filter`` — optional callable that decides whether the act is in
  scope for a given FIR (e.g. NDPS only for narcotics-context FIRs)

The extractor, chunker, retriever and recommender consume this registry.
Adding NDPS is now: ``register(ActSpec(code="NDPS", ...))`` and supplying
the source PDF — no other code changes.

Status legend:
    ``ingested``    — corpus extracted, chunks indexed
    ``scaffolded``  — registered but corpus not yet extracted (awaiting PDF)
    ``planned``     — slot reserved
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable, Literal

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

ActStatus = Literal["ingested", "scaffolded", "planned"]


@dataclass(frozen=True)
class ActSpec:
    code: str                       # e.g. "BNS", "IPC", "NDPS"
    title: str
    short_name: str
    act_no: str | None              # formal "ACT NO. X OF YYYY" string
    commencement: date | None
    source_pdf: Path | None         # path to canonical source PDF
    data_path: Path                 # JSONL output path
    status: ActStatus
    chapter: str = ""               # category (substantive | procedural | evidence | special)
    notes: str = ""


# ---------- Built-in registry ---------- #

_REGISTRY: dict[str, ActSpec] = {}


def register(spec: ActSpec) -> None:
    if spec.code in _REGISTRY:
        raise ValueError(f"act already registered: {spec.code}")
    _REGISTRY[spec.code] = spec


def get(code: str) -> ActSpec | None:
    return _REGISTRY.get(code)


def all_acts() -> list[ActSpec]:
    return list(_REGISTRY.values())


def ingested_acts() -> list[ActSpec]:
    return [s for s in _REGISTRY.values() if s.status == "ingested"]


# Pre-register the substantive criminal codes (currently ingested).

register(ActSpec(
    code="BNS",
    title="The Bharatiya Nyaya Sanhita, 2023",
    short_name="BNS",
    act_no="ACT NO. 45 OF 2023",
    commencement=date(2024, 7, 1),
    source_pdf=Path(r"C:/Users/HP/Desktop/RP2/bns sections.pdf"),
    data_path=DATA / "bns_sections.jsonl",
    status="ingested",
    chapter="substantive",
))

register(ActSpec(
    code="IPC",
    title="The Indian Penal Code, 1860",
    short_name="IPC",
    act_no="ACT NO. 45 OF 1860",
    commencement=date(1862, 1, 1),
    source_pdf=Path(r"C:/Users/HP/Desktop/RP2/ipc sections pdf.pdf"),
    data_path=DATA / "ipc_sections.jsonl",
    status="ingested",
    chapter="substantive",
    notes="Superseded by BNS for offences on or after 01-Jul-2024; retained for legacy caseload.",
))

# Special acts — scaffolded slots. Provide source_pdf and re-extract to
# move from ``planned``/``scaffolded`` to ``ingested``.

_SPECIAL_ACTS: list[tuple[str, str, str, str | None, date | None, str]] = [
    # (code, title, short_name, act_no, commencement, notes)
    ("BNSS", "The Bharatiya Nagarik Suraksha Sanhita, 2023", "BNSS", "ACT NO. 46 OF 2023", date(2024, 7, 1),
     "Procedural code (replaces CrPC). Required for arrest/search/cognizance citations."),
    ("BSA", "The Bharatiya Sakshya Adhiniyam, 2023", "BSA", "ACT NO. 47 OF 2023", date(2024, 7, 1),
     "Evidence law (replaces Indian Evidence Act). Required for chain-of-custody and electronic evidence citations."),
    ("CRPC", "The Code of Criminal Procedure, 1973", "CrPC", "ACT NO. 2 OF 1974", date(1974, 4, 1),
     "Legacy procedural code; cited for pre-01-Jul-2024 offences."),
    ("NDPS", "The Narcotic Drugs and Psychotropic Substances Act, 1985", "NDPS Act", "ACT NO. 61 OF 1985", date(1985, 11, 14),
     "Substantive special act — narcotics offences."),
    ("POCSO", "The Protection of Children from Sexual Offences Act, 2012", "POCSO Act", "ACT NO. 32 OF 2012", date(2012, 11, 14),
     "Sexual offences against children."),
    ("IT_ACT", "The Information Technology Act, 2000", "IT Act", "ACT NO. 21 OF 2000", date(2000, 10, 17),
     "Cyber offences, electronic evidence."),
    ("MV_ACT", "The Motor Vehicles Act, 1988", "MV Act", "ACT NO. 59 OF 1988", date(1989, 7, 1),
     "Road traffic, rash driving, hit-and-run."),
    ("DOWRY", "The Dowry Prohibition Act, 1961", "Dowry Act", "ACT NO. 28 OF 1961", date(1961, 7, 1),
     "Demanding/accepting dowry."),
    ("ARMS", "The Arms Act, 1959", "Arms Act", "ACT NO. 54 OF 1959", date(1959, 12, 23),
     "Possession/use of unauthorised firearms."),
    ("SCST", "The Scheduled Castes and Scheduled Tribes (Prevention of Atrocities) Act, 1989", "SC/ST Act",
     "ACT NO. 33 OF 1989", date(1990, 1, 30),
     "Caste-based offences. Often the primary charge over BNS sections."),
    ("DV", "The Protection of Women from Domestic Violence Act, 2005", "DV Act", "ACT NO. 43 OF 2005", date(2006, 10, 26),
     "Domestic violence civil protection regime."),
    ("PROHIBITION_GJ", "The Gujarat Prohibition Act, 1949 (as amended)", "Gujarat Prohibition Act", None, None,
     "State law on prohibition of liquor."),
    ("GAMBLING_GJ", "The Gujarat Prevention of Gambling Act, 1887 (as amended)", "Gujarat Gambling Act", None, None,
     "State law on gambling offences."),
]

for code, title, short, act_no, commencement, notes in _SPECIAL_ACTS:
    register(ActSpec(
        code=code, title=title, short_name=short, act_no=act_no,
        commencement=commencement,
        source_pdf=None,                       # supply when ingesting
        data_path=DATA / f"{code.lower()}_sections.jsonl",
        status="planned",
        chapter="procedural" if code in {"BNSS", "CRPC"}
                else "evidence" if code == "BSA"
                else "special",
        notes=notes,
    ))


__all__ = [
    "ActSpec", "ActStatus", "register", "get", "all_acts", "ingested_acts",
]
