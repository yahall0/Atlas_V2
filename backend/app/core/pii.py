"""Role-based PII masking for FIR response data.

Applied to FIR dicts before sending to API clients.  Masking level
depends on the caller's role so that sensitive identifiers are only
visible to roles that require them.

Masking table
-------------
Role        Aadhaar   Phone                   Complainant name
SP, ADMIN   None      None                    Full
IO, SHO     [AADHAAR] [PHONE-XXXX] last 4     Full
DYSP,       [AADHAAR] [PHONE-XXXX] last 4     First + last initial
READONLY    [AADHAAR] [PHONE-XXXX] last 4     First + last initial
(any other) [AADHAAR] [PHONE-XXXX] last 4     First + last initial

Victim identity (BNS Chapter V — §63-99 sexual offences)
---------------------------------------------------------
For FIRs whose primary_sections contain any BNS Ch.V section (63-99)
the complainant_name and place_address fields are always masked
regardless of role (Section 228A CrPC / BNS §73 prohibition).
"""

from __future__ import annotations

import re
from typing import Any, Dict

_PHONE_RE = re.compile(r"(?:\+91|91|0)?[6-9]\d{9}")
_AADHAAR_RE = re.compile(r"\b\d{4}[\s\-]\d{4}[\s\-]\d{4}\b")

# Roles that receive unredacted data (except victim identity — always masked)
_UNRESTRICTED = {"SP", "ADMIN"}

# Free-text fields whose content must be scanned for PII patterns
_TEXT_FIELDS = ("narrative", "raw_text", "place_address")

# BNS Chapter V sections (sexual offences) — victim identity always protected
# Includes legacy IPC 376 family for FIRs not yet BNS-mapped.
_SEXUAL_OFFENCE_SECTIONS = {
    # BNS §63-99
    *[str(i) for i in range(63, 100)],
    # Legacy IPC equivalents
    "376", "376A", "376B", "376C", "376D", "376DA", "376DB", "354", "354A",
    "354B", "354C", "354D",
}


def _is_sexual_offence_fir(fir: Dict[str, Any]) -> bool:
    """Return True if any primary_section belongs to the sexual offence list."""
    sections = fir.get("primary_sections") or []
    if isinstance(sections, str):
        sections = [s.strip() for s in sections.split(",") if s.strip()]
    return any(s.strip() in _SEXUAL_OFFENCE_SECTIONS for s in sections)


def _redact_phone(m: re.Match) -> str:
    digits = re.sub(r"\D", "", m.group())
    return f"[PHONE-{digits[-4:]}]"


def _sanitise_text(text: str) -> str:
    """Remove Aadhaar patterns and partially-mask phone numbers in *text*."""
    text = _AADHAAR_RE.sub("[AADHAAR]", text)
    text = _PHONE_RE.sub(_redact_phone, text)
    return text


def _mask_name(full_name: str) -> str:
    """Return 'Firstname L.' from a full name."""
    parts = full_name.strip().split()
    if len(parts) > 1:
        return f"{parts[0]} {parts[-1][0]}."
    return full_name  # single-word name — leave as-is


def mask_pii_for_role(fir: Dict[str, Any], role: str) -> Dict[str, Any]:
    """Apply role-appropriate PII masking to a FIR dict.

    The input dict is never mutated; a shallow copy with masked values is
    returned.

    Parameters
    ----------
    fir:
        Raw FIR dict as returned by the CRUD layer.
    role:
        The caller's role string (e.g. ``"IO"``, ``"ADMIN"``).

    Returns
    -------
    dict
        Copy of *fir* with PII fields replaced according to role policy.
    """
    result = dict(fir)

    # ── Victim identity masking (BNS §73 / Section 228A CrPC) ────────────
    # Applied BEFORE role-based masking and for ALL roles including SP/ADMIN.
    if _is_sexual_offence_fir(result):
        result["complainant_name"] = "[VICTIM-PROTECTED]"
        if result.get("place_address"):
            result["place_address"] = "[ADDRESS-PROTECTED]"
        if result.get("complainants"):
            masked_complainants = []
            for c in result["complainants"]:
                c = dict(c)
                c["name"] = "[VICTIM-PROTECTED]"
                if c.get("address"):
                    c["address"] = "[ADDRESS-PROTECTED]"
                masked_complainants.append(c)
            result["complainants"] = masked_complainants

    if role in _UNRESTRICTED:
        return result

    # ── Role-based PII masking ─────────────────────────────────────────────
    # Sanitise free-text fields
    for field in _TEXT_FIELDS:
        if result.get(field):
            result[field] = _sanitise_text(result[field])

    # Name masking for lower-privilege roles
    if role not in ("IO", "SHO"):
        # Only mask if not already victim-protected
        if result.get("complainant_name") and result["complainant_name"] != "[VICTIM-PROTECTED]":
            result["complainant_name"] = _mask_name(result["complainant_name"])
        # Also mask complainants list entries
        if result.get("complainants"):
            masked = []
            for c in result["complainants"]:
                c = dict(c)
                if c.get("name") and c["name"] != "[VICTIM-PROTECTED]":
                    c["name"] = _mask_name(c["name"])
                masked.append(c)
            result["complainants"] = masked

    return result
