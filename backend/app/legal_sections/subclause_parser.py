"""Sub-clause parser for IPC and BNS sections.

Production contract (ADR-D15):
    Every section recommendation produced by the platform must cite the
    smallest applicable addressable unit of the statute. For sections that
    contain enumerated alternatives or numbered sub-sections, this means the
    recommender SHALL identify the matching sub-clause(s) and emit the
    section identifier in canonical sub-clause form
    (e.g. ``BNS 305(a)``, ``BNS 331(3)``, ``BNS 332 Provided that``).

This module performs the structural parse of a section's verbatim text into
addressable sub-clauses. It is invoked at extraction time so that downstream
retrieval and recommendation always operate on sub-clause-granular records.

Recognised marker shapes
------------------------

================  =========================================  ========================
Shape             Examples                                   Scheme code
================  =========================================  ========================
Numbered          ``(1)``, ``(2)`` … ``(99)``                ``num``
Lettered (lower)  ``(a)``, ``(b)`` … ``(z)``, ``(aa)``       ``alpha_lower``
Lettered (upper)  ``(A)``, ``(B)`` …                         ``alpha_upper``
Roman (lower)     ``(i)``, ``(ii)``, ``(iii)`` …             ``roman_lower``
Roman (upper)     ``(I)``, ``(II)`` …                        ``roman_upper``
Ordinal           ``First.``, ``Secondly.``, ``Thirdly.`` …  ``ordinal``
Proviso           ``Provided that``, ``Provided further``    ``proviso``
================  =========================================  ========================

Nesting model
-------------

Markers are visited in document order. A ``current_path`` stack tracks the
enumeration scheme(s) currently active. When a marker is encountered:

* If the marker matches the scheme at the top of the stack, the top entry is
  advanced (same depth).
* If the marker's scheme exists deeper in the stack, the stack is popped down
  to that level, then advanced (returning to a shallower depth).
* Otherwise, the marker is a *new, deeper* enumeration — a fresh entry is
  pushed onto the stack (depth increases by one).

This produces correct nested citations such as ``BNS 376(2)(a)`` while
keeping flat-enumerated sections (e.g. ``BNS 305(a)``) at depth 1.

Provisos
--------

Provisos are first-class addressable units. They are emitted with the
canonical citation ``<section> Proviso`` (or ``<section> Proviso N`` for
multiple provisos) and a stable addressable id ``..._proviso_N``. They do
not alter the enumeration stack — they pop the stack only down to the
section root.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Iterable

EM_DASH = "\u2014"
EN_DASH = "\u2013"
DASH_CLASS = f"[{EN_DASH}{EM_DASH}]"

ORDINAL_WORDS = (
    "First", "Secondly", "Thirdly", "Fourthly", "Fifthly", "Sixthly",
    "Seventhly", "Eighthly", "Ninthly", "Tenthly",
)
ORDINAL_INDEX = {w.lower(): i + 1 for i, w in enumerate(ORDINAL_WORDS)}

# Combined marker regex. Anchored to a position that is either the start of a
# logical paragraph (line-start with optional whitespace) OR immediately after
# the section's opening em-dash (which captures inline first-subsection like
# ``303. Theft.\u2014(1) Whoever ...``).
_MARKER_PATTERN = re.compile(
    r"(?P<paren>\((?P<inner>[A-Za-z]{1,4}|\d{1,3})\))"  # (a) (1) (ii) (AA)
    r"|(?P<ord>(?:" + "|".join(ORDINAL_WORDS) + r")[.,])"  # First. Secondly.
    r"|(?P<proviso>Provided\s+(?:further|also\b)?\s*that\b)",
)

_ROMAN_LOWER = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x",
                "xi", "xii", "xiii", "xiv", "xv", "xvi", "xvii", "xviii", "xix", "xx"}
_ROMAN_UPPER = {r.upper() for r in _ROMAN_LOWER}


@dataclass
class SubClause:
    """One addressable sub-unit of a section."""

    section_id: str            # parent section id, e.g. "BNS_305"
    label: str                 # raw marker as it appears: "(a)", "(1)", "Provided that", "First."
    canonical_label: str       # normalised form: "(a)", "(1)", "Provided that", "First"
    scheme: str                # one of: num | alpha_lower | alpha_upper | roman_lower | roman_upper | ordinal | proviso
    depth: int                 # 1 for top-level, 2 for nested, ...
    parent_path: list[str]     # ["(2)"] for a (2)(a) clause; [] for top-level
    canonical_citation: str    # human-readable, e.g. "BNS 305(a)" or "BNS 332 Provided that"
    addressable_id: str        # url-safe, e.g. "BNS_305_a", "BNS_332_proviso_1"
    text: str                  # verbatim text of this sub-clause (from marker through to next sibling/ancestor or end)
    offset_start: int          # offset within the section's full_text
    offset_end: int            # exclusive end offset


# Letters whose single-character form is also a Roman numeral.
_ROMAN_AMBIGUOUS_LOWER = {"i", "v", "x", "l", "c", "d", "m"}
_ROMAN_AMBIGUOUS_UPPER = {c.upper() for c in _ROMAN_AMBIGUOUS_LOWER}

# Map of letter → its alphabetical predecessor; used to disambiguate
# single-letter Roman tokens from continuations of an alphabetic enumeration.
_ALPHA_PREDECESSOR = {chr(c): chr(c - 1) for c in range(ord("b"), ord("z") + 1)}
_ALPHA_PREDECESSOR.update({chr(c): chr(c - 1) for c in range(ord("B"), ord("Z") + 1)})


def _classify_scheme(token: str, *, previous_letter: str | None = None) -> str:
    """Return the enumeration scheme for a marker token.

    ``token`` is the *inside* of a parenthesised marker (``"a"``, ``"1"``,
    ``"ii"``) or the bare ordinal/proviso phrase.

    Single-letter Roman markers (``i``, ``v``, ``x``, ``l``, ``c``, ``d``,
    ``m`` and uppercase counterparts) are inherently ambiguous with
    alphabetic enumeration. ``previous_letter`` resolves this: if the prior
    same-level marker was the alphabetical predecessor (e.g. ``h`` then
    ``i``, ``u`` then ``v``), the token is classified as a continuing
    letter rather than a Roman numeral.
    """
    if token.isdigit():
        return "num"

    is_lower = token.isalpha() and token.islower()
    is_upper = token.isalpha() and token.isupper()

    # Multi-character Roman tokens (ii, iii, iv, vi, vii, viii, ...)
    if token in _ROMAN_LOWER and len(token) > 1:
        return "roman_lower"
    if token in _ROMAN_UPPER and len(token) > 1:
        return "roman_upper"

    # Single-character ambiguous tokens — disambiguate via predecessor
    if is_lower and token in _ROMAN_AMBIGUOUS_LOWER:
        if previous_letter and previous_letter == _ALPHA_PREDECESSOR.get(token):
            return "alpha_lower"
        return "roman_lower"
    if is_upper and token in _ROMAN_AMBIGUOUS_UPPER:
        if previous_letter and previous_letter == _ALPHA_PREDECESSOR.get(token):
            return "alpha_upper"
        return "roman_upper"

    if is_lower:
        return "alpha_lower"
    if is_upper:
        return "alpha_upper"
    return "alpha_lower"  # safe default


def _scheme_priority(scheme: str) -> int:
    """Conventional ordering used as a tie-breaker.

    Lower number = outer level. Used only when the runtime stack is empty
    (so we cannot infer from context). For sections that begin with letters
    such as BNS 305, this ensures ``(a)`` is treated as depth 1 rather than
    being miscategorised as nested.
    """
    return {"num": 1, "alpha_lower": 2, "alpha_upper": 2,
            "roman_lower": 3, "roman_upper": 3, "ordinal": 1, "proviso": 1}.get(scheme, 99)


def _addressable_token(label: str, scheme: str, proviso_index: int = 0) -> str:
    """Return the URL-safe token for one path step."""
    if scheme == "proviso":
        return f"proviso_{proviso_index}"
    if scheme == "ordinal":
        # Strip trailing "." or ","
        cleaned = label.rstrip(".,").lower()
        return f"ord_{ORDINAL_INDEX.get(cleaned, 0)}"
    inner = label.strip("()")
    return inner


def _canonical_label(raw: str, scheme: str) -> str:
    if scheme == "proviso":
        # Normalise whitespace
        return re.sub(r"\s+", " ", raw.strip())
    if scheme == "ordinal":
        return raw.rstrip(".,")
    return raw  # parenthesised markers already canonical


def _build_section_header(section_id: str, section_number: str | None = None) -> tuple[str, str]:
    """Return (citation_root, addressable_root) for a section_id like ``BNS_305``.

    Example: ``("BNS 305", "BNS_305")``. ``section_number`` is preferred for
    citation; the suffix of ``section_id`` is used as fallback.
    """
    act, _, num = section_id.partition("_")
    return f"{act} {section_number or num}", section_id


def _strip_section_header(full_text: str, section_number: str) -> tuple[str, int]:
    """Remove the ``<num>. <title>.\u2014`` prefix.

    Returns ``(body_text, header_length)``. ``header_length`` is the number of
    characters removed, used to translate offsets back to the original
    full_text.
    """
    pattern = re.compile(
        rf"^\s*(?:\d+\[)?{re.escape(section_number)}\.?\s*(?:{DASH_CLASS})?[^\n]*?{DASH_CLASS}",
        re.DOTALL,
    )
    m = pattern.match(full_text)
    if m:
        return full_text[m.end():], m.end()
    return full_text, 0


def parse_subclauses(
    section_id: str,
    section_number: str,
    full_text: str,
) -> list[SubClause]:
    """Parse a section's verbatim text into addressable sub-clauses.

    Every visible enumeration marker — including the inline first marker
    (e.g. ``303. Theft.\u2014(1) Whoever ...``) — produces one SubClause.
    Sections without enumeration return an empty list (the section itself is
    the only addressable unit).
    """
    body, header_len = _strip_section_header(full_text, section_number)

    # Locate every marker
    matches: list[re.Match] = list(_MARKER_PATTERN.finditer(body))
    # Filter out matches that are clearly not statute markers (e.g. an
    # ordinal mid-sentence). Heuristic: require either start-of-line OR
    # immediately following the section's opening em-dash, OR (for `(label)`)
    # the previous non-whitespace character is a punctuation/dash.
    accepted: list[re.Match] = []
    for m in matches:
        if _is_genuine_marker(body, m):
            accepted.append(m)

    if not accepted:
        return []

    citation_root, addressable_root = _build_section_header(section_id, section_number)

    # Walk markers maintaining a path stack.
    # Each path entry: dict with keys: scheme, label, addressable_token,
    # canonical_label, is_proviso.
    path: list[dict] = []
    proviso_count = 0

    sub_clauses: list[SubClause] = []
    for i, m in enumerate(accepted):
        if m.group("paren"):
            inner = m.group("inner")
            # Look at the most recent letter at the current top-of-stack to
            # disambiguate single-letter Roman vs continuation of an alphabetic
            # enumeration (e.g. (h) then (i) → letter 'i', not Roman 'i').
            previous_letter = None
            if path and path[-1]["scheme"] in ("alpha_lower", "alpha_upper"):
                previous_letter = path[-1]["label"].strip("()")
            scheme = _classify_scheme(inner, previous_letter=previous_letter)
            label = m.group("paren")
        elif m.group("ord"):
            scheme = "ordinal"
            label = m.group("ord")
        else:
            scheme = "proviso"
            label = m.group("proviso")

        canonical_label = _canonical_label(label, scheme)

        # Determine where this marker sits in the path
        if scheme == "proviso":
            # Proviso resets the stack to depth 0 (it is a section-level qualifier)
            path = []
            proviso_count += 1
            entry = {
                "scheme": scheme,
                "label": label,
                "canonical_label": canonical_label,
                "addressable_token": _addressable_token(label, scheme, proviso_count),
            }
            path.append(entry)
        else:
            # Same scheme as top of stack → advance
            if path and path[-1]["scheme"] == scheme:
                path[-1] = {
                    "scheme": scheme,
                    "label": label,
                    "canonical_label": canonical_label,
                    "addressable_token": _addressable_token(label, scheme),
                }
            # Scheme exists deeper in the stack → pop until we match, then advance
            elif any(p["scheme"] == scheme for p in path):
                while path and path[-1]["scheme"] != scheme:
                    path.pop()
                path[-1] = {
                    "scheme": scheme,
                    "label": label,
                    "canonical_label": canonical_label,
                    "addressable_token": _addressable_token(label, scheme),
                }
            # New scheme — push (deeper) UNLESS the existing top has lower
            # priority (in which case we replace at the same depth).
            else:
                if path and _scheme_priority(scheme) <= _scheme_priority(path[-1]["scheme"]):
                    # Pop levels of equal-or-shallower priority, then replace
                    while path and _scheme_priority(path[-1]["scheme"]) >= _scheme_priority(scheme):
                        path.pop()
                path.append({
                    "scheme": scheme,
                    "label": label,
                    "canonical_label": canonical_label,
                    "addressable_token": _addressable_token(label, scheme),
                })

        # Build citation and addressable id from the current path.
        # Word-style markers (ordinal, proviso) are joined with a space; paren
        # markers are concatenated directly. ``BNS 305(a)`` vs ``IPC 300 First``.
        def _join_label(prev_path: list[dict], entry: dict) -> str:
            if entry["scheme"] in ("ordinal", "proviso"):
                return f" {entry['canonical_label']}"
            return entry["canonical_label"]

        if scheme == "proviso":
            tail = path[-1]
            canonical_citation = f"{citation_root} {tail['canonical_label']}"
            addressable_id = f"{addressable_root}_{tail['addressable_token']}"
            parent_path: list[str] = []
        else:
            canonical_citation = citation_root + "".join(_join_label(path[:i], p) for i, p in enumerate(path))
            addressable_id = addressable_root + "".join(f"_{p['addressable_token']}" for p in path)
            parent_path = [p["canonical_label"] for p in path[:-1]]

        # Determine text span: from this marker's start to the next accepted
        # marker's start (or end of body).
        text_start_in_body = m.start()
        text_end_in_body = accepted[i + 1].start() if i + 1 < len(accepted) else len(body)
        text = body[text_start_in_body:text_end_in_body].rstrip()

        sub_clauses.append(
            SubClause(
                section_id=section_id,
                label=label,
                canonical_label=canonical_label,
                scheme=scheme,
                depth=len(path),
                parent_path=parent_path,
                canonical_citation=canonical_citation,
                addressable_id=addressable_id,
                text=text,
                offset_start=header_len + text_start_in_body,
                offset_end=header_len + text_end_in_body,
            )
        )

    return sub_clauses


def _is_genuine_marker(body: str, m: re.Match) -> bool:
    """Reject false-positive markers found mid-sentence.

    Genuine markers are at the start of a logical clause: either at line
    start (with optional whitespace) or immediately after the section's
    opening em-dash, or after a list-introducing dash like ``offence\u2014``.
    """
    start = m.start()
    if start == 0:
        return True
    # Look backwards over whitespace
    j = start - 1
    while j >= 0 and body[j] in " \t":
        j -= 1
    if j < 0:
        return True
    prev = body[j]
    if prev in "\n\r":
        return True
    if prev in (EM_DASH, EN_DASH):
        return True
    # Provisos may follow a colon
    if m.group("proviso") and prev == ":":
        return True
    # Ordinals usually preceded by a comma
    if m.group("ord") and prev in ",:;":
        return True
    return False


def to_jsonable(sub_clauses: Iterable[SubClause]) -> list[dict]:
    return [asdict(sc) for sc in sub_clauses]


__all__ = ["SubClause", "parse_subclauses", "to_jsonable"]
