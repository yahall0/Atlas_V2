"""section_map.py — maps registered BNS / IPC sections to classifier categories.

Used for mismatch detection: if the NLP-predicted category disagrees with the
category implied by the *registered* sections, the FIR is flagged for review.

Category labels match label_map.json exactly:
  assault | cybercrime | dacoity_robbery | domestic_violence | fraud |
  kidnapping | murder | narcotics | other | rape_sexoff | theft
"""

from __future__ import annotations

from typing import Optional, Sequence

# ---------------------------------------------------------------------------
# BNS 2023 section → category
# The Bharatiya Nyaya Sanhita renumbers IPC offences, so the mapping is
# completely separate from the IPC one.
# ---------------------------------------------------------------------------
_BNS: dict[str, str] = {
    # Murder / culpable homicide
    "101": "murder", "103": "murder", "104": "murder", "105": "murder",
    "106": "murder",
    # Hurt / assault
    "115": "assault", "116": "assault", "117": "assault", "118": "assault",
    "119": "assault", "120": "assault", "121": "assault", "122": "assault",
    "123": "assault", "124": "assault", "125": "assault", "126": "assault",
    "129": "assault", "131": "assault",
    # Rape / sexual offences
    "63": "rape_sexoff", "64": "rape_sexoff", "65": "rape_sexoff",
    "66": "rape_sexoff", "67": "rape_sexoff", "68": "rape_sexoff",
    "69": "rape_sexoff", "70": "rape_sexoff", "71": "rape_sexoff",
    "72": "rape_sexoff", "73": "rape_sexoff", "74": "rape_sexoff",
    "75": "rape_sexoff", "76": "rape_sexoff", "77": "rape_sexoff",
    "78": "rape_sexoff", "79": "rape_sexoff",
    # Domestic violence / cruelty
    "85": "domestic_violence", "86": "domestic_violence",
    # Kidnapping / abduction
    "137": "kidnapping", "138": "kidnapping", "139": "kidnapping",
    "140": "kidnapping", "141": "kidnapping", "143": "kidnapping",
    "144": "kidnapping", "145": "kidnapping", "146": "kidnapping",
    # Theft
    "303": "theft", "304": "theft", "305": "theft", "306": "theft",
    # Robbery / dacoity
    "307": "dacoity_robbery", "308": "dacoity_robbery",
    "309": "dacoity_robbery", "310": "dacoity_robbery",
    "311": "dacoity_robbery", "312": "dacoity_robbery",
    "313": "dacoity_robbery", "314": "dacoity_robbery",
    # Fraud / cheating / criminal breach of trust
    "316": "fraud", "317": "fraud", "318": "fraud", "319": "fraud",
    "320": "fraud", "315": "fraud",
}

# ---------------------------------------------------------------------------
# IPC section → category
# ---------------------------------------------------------------------------
_IPC: dict[str, str] = {
    # Murder / culpable homicide
    "302": "murder", "304": "murder", "307": "murder", "308": "murder",
    "299": "murder", "300": "murder",
    # Hurt / assault
    "319": "assault", "320": "assault", "321": "assault", "322": "assault",
    "323": "assault", "324": "assault", "325": "assault", "326": "assault",
    "327": "assault", "328": "assault", "329": "assault", "330": "assault",
    "331": "assault", "332": "assault", "333": "assault", "334": "assault",
    "335": "assault", "351": "assault", "352": "assault",
    # Rape / sexual offences
    "375": "rape_sexoff", "376": "rape_sexoff",
    "354": "rape_sexoff", "354A": "rape_sexoff", "354B": "rape_sexoff",
    "354C": "rape_sexoff", "354D": "rape_sexoff", "509": "rape_sexoff",
    # Domestic violence / cruelty
    "498": "domestic_violence", "498A": "domestic_violence",
    # Kidnapping / abduction
    "359": "kidnapping", "360": "kidnapping", "361": "kidnapping",
    "362": "kidnapping", "363": "kidnapping", "364": "kidnapping",
    "365": "kidnapping", "366": "kidnapping", "367": "kidnapping",
    "368": "kidnapping", "369": "kidnapping",
    # Theft
    "378": "theft", "379": "theft", "380": "theft",
    "381": "theft", "382": "theft",
    # Robbery / dacoity
    "390": "dacoity_robbery", "391": "dacoity_robbery",
    "392": "dacoity_robbery", "393": "dacoity_robbery",
    "394": "dacoity_robbery", "395": "dacoity_robbery",
    "396": "dacoity_robbery", "397": "dacoity_robbery",
    "398": "dacoity_robbery", "399": "dacoity_robbery",
    "400": "dacoity_robbery", "401": "dacoity_robbery",
    "402": "dacoity_robbery",
    # Fraud / cheating / CBT
    "406": "fraud", "407": "fraud", "408": "fraud", "409": "fraud",
    "415": "fraud", "416": "fraud", "417": "fraud", "418": "fraud",
    "419": "fraud", "420": "fraud",
}

# ---------------------------------------------------------------------------
# Special acts (act-independent — triggered by primary_act keyword)
# ---------------------------------------------------------------------------
_NDPS_SECTIONS: frozenset[str] = frozenset({
    "20", "21", "22", "23", "24", "25", "27", "27A", "28", "29", "30",
})
_IT_SECTIONS: frozenset[str] = frozenset({
    "43", "45", "65", "66", "66A", "66B", "66C", "66D", "66E", "66F",
    "67", "67A", "67B", "72", "75",
})
_POCSO_SECTIONS: frozenset[str] = frozenset({
    "4", "6", "7", "8", "9", "10", "11", "12",
})


def infer_category_from_sections(
    primary_act: Optional[str],
    sections: Sequence[str],
) -> Optional[str]:
    """Return the crime category implied by the registered sections, or None.

    Returns *None* when sections are absent, unknown, or ambiguous — meaning
    no comparison should be made.

    When multiple sections map to different categories the most serious one
    wins (priority: murder > rape_sexoff > dacoity_robbery > kidnapping >
    domestic_violence > assault > fraud > narcotics > cybercrime > theft).
    """
    if not sections:
        return None

    act = (primary_act or "").upper().strip()

    # Whole-act mappings (NDPS / IT Act / POCSO override section lookup)
    if act in ("NDPS", "N.D.P.S"):
        return "narcotics"
    if "IT ACT" in act or act == "IT":
        return "cybercrime"
    if act == "POCSO":
        return "rape_sexoff"

    # Section-level lookup
    import re as _re
    table = _BNS if act == "BNS" else _IPC  # default IPC for unknown acts
    categories: set[str] = set()
    for sec in sections:
        # Normalise: remove spaces, then strip sub-clause suffixes like (a), (4),
        # (1)(ii) so that "305(a)" matches "305" and "331(4)" matches "331".
        sec_norm = sec.strip().replace(" ", "")
        sec_base = _re.sub(r'[\(\[].*$', '', sec_norm)  # strip from first ( or [
        for key in (sec_norm, sec_base):
            cat = table.get(key)
            if cat:
                categories.add(cat)
                break
        # NDPS / IT Act / POCSO sections embedded in a mixed registration
        for key in (sec_norm, sec_base):
            if key in _NDPS_SECTIONS:
                categories.add("narcotics")
            if key in _IT_SECTIONS:
                categories.add("cybercrime")
            if key in _POCSO_SECTIONS:
                categories.add("rape_sexoff")

    if not categories:
        return None
    if len(categories) == 1:
        return next(iter(categories))

    # Priority tiebreak
    _PRIORITY = [
        "murder", "rape_sexoff", "dacoity_robbery", "kidnapping",
        "domestic_violence", "assault", "fraud", "narcotics",
        "cybercrime", "theft", "other",
    ]
    for cat in _PRIORITY:
        if cat in categories:
            return cat
    return next(iter(categories))
