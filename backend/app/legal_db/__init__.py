"""Legal database — IPC/BNS/CrPC/BNSS cross-reference lookup.

Loads ``sections.json`` once at import time and exposes typed helpers
for section lookup, act conversion, and evidence requirements.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Load JSON database
# ─────────────────────────────────────────────────────────────────────────────

_DB_PATH = Path(__file__).parent / "sections.json"

_RAW: Dict[str, Any] = {}
_BY_IPC: Dict[str, Dict[str, Any]] = {}
_BY_BNS: Dict[str, Dict[str, Any]] = {}
_BNS_COMMENCEMENT = "2024-07-01"

try:
    _RAW = json.loads(_DB_PATH.read_text(encoding="utf-8"))
    _BNS_COMMENCEMENT = _RAW.get("metadata", {}).get(
        "bns_commencement_date", _BNS_COMMENCEMENT
    )
    for entry in _RAW.get("sections", []):
        ipc = entry.get("ipc_section")
        bns = entry.get("bns_section")
        if ipc:
            _BY_IPC[ipc] = entry
        if bns:
            _BY_BNS[bns] = entry
    logger.info(
        "Legal DB loaded: %d IPC sections, %d BNS sections.",
        len(_BY_IPC),
        len(_BY_BNS),
    )
except Exception:
    logger.error("Failed to load legal database from %s", _DB_PATH, exc_info=True)


# ─────────────────────────────────────────────────────────────────────────────
# Normalisation helper
# ─────────────────────────────────────────────────────────────────────────────

def _normalise_section(section: str) -> str:
    """Strip sub-clause suffixes so '302(1)' matches '302'."""
    s = section.strip().replace(" ", "")
    return re.sub(r"[\(\[].*$", "", s)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def get_section(section_number: str, act: str = "ipc") -> Optional[Dict[str, Any]]:
    """Look up a section by number and act.

    Parameters
    ----------
    section_number : str
        E.g. ``"302"``, ``"376A"``, ``"103(1)"``.
    act : str
        ``"ipc"`` (default) or ``"bns"``.

    Returns ``None`` if the section is not in the database.
    """
    norm = _normalise_section(section_number)
    table = _BY_BNS if act.lower() == "bns" else _BY_IPC
    return table.get(section_number) or table.get(norm)


def get_bns_equivalent(ipc_section: str) -> Optional[str]:
    """Return the BNS equivalent of an IPC section, or ``None``."""
    entry = get_section(ipc_section, act="ipc")
    if entry:
        return entry.get("bns_section")
    return None


def get_ipc_equivalent(bns_section: str) -> Optional[str]:
    """Return the IPC equivalent of a BNS section, or ``None``."""
    entry = get_section(bns_section, act="bns")
    if entry:
        return entry.get("ipc_section")
    return None


def get_mandatory_evidence(section_number: str, act: str = "ipc") -> List[str]:
    """Return the list of mandatory evidence items for a section."""
    entry = get_section(section_number, act)
    return list(entry.get("mandatory_evidence", [])) if entry else []


def get_companion_sections(section_number: str, act: str = "ipc") -> List[str]:
    """Return companion sections typically charged alongside this one."""
    entry = get_section(section_number, act)
    return list(entry.get("companion_sections", [])) if entry else []


def get_mutually_exclusive(section_number: str, act: str = "ipc") -> List[str]:
    """Return sections that are mutually exclusive with this one."""
    entry = get_section(section_number, act)
    return list(entry.get("mutually_exclusive_with", [])) if entry else []


def get_procedural_requirements(section_number: str, act: str = "ipc") -> List[str]:
    """Return procedural requirements for a section."""
    entry = get_section(section_number, act)
    return list(entry.get("procedural_requirements", [])) if entry else []


def get_bns_commencement_date() -> str:
    """Return the BNS commencement date as ISO string."""
    return _BNS_COMMENCEMENT


def get_all_sections() -> List[Dict[str, Any]]:
    """Return all section entries."""
    return list(_RAW.get("sections", []))


def get_procedural_sections() -> List[Dict[str, Any]]:
    """Return all CrPC/BNSS procedural section entries."""
    return list(_RAW.get("procedural_sections", []))
