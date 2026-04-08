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
"""

from __future__ import annotations

import re
from typing import Any, Dict

_PHONE_RE = re.compile(r"(?:\+91|91|0)?[6-9]\d{9}")
_AADHAAR_RE = re.compile(r"\b\d{4}[\s\-]\d{4}[\s\-]\d{4}\b")

# Roles that receive unredacted data
_UNRESTRICTED = {"SP", "ADMIN"}

# Free-text fields whose content must be scanned for PII patterns
_TEXT_FIELDS = ("narrative", "raw_text", "place_address")


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
    if role in _UNRESTRICTED:
        return fir

    result = dict(fir)

    # Sanitise free-text fields
    for field in _TEXT_FIELDS:
        if result.get(field):
            result[field] = _sanitise_text(result[field])

    # Name masking for lower-privilege roles
    if role not in ("IO", "SHO"):
        if result.get("complainant_name"):
            result["complainant_name"] = _mask_name(result["complainant_name"])
        # Also mask complainants list entries
        if result.get("complainants"):
            masked = []
            for c in result["complainants"]:
                c = dict(c)
                if c.get("name"):
                    c["name"] = _mask_name(c["name"])
                masked.append(c)
            result["complainants"] = masked

    return result
