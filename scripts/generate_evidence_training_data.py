#!/usr/bin/env python3
"""Generate synthetic training data for the evidence gap ML model.

For each of the 11 ATLAS crime categories, generates 200 synthetic
charge-sheet feature vectors with realistic evidence presence/absence
patterns. Outputs a CSV with ~2200 rows.

Usage:
    python scripts/generate_evidence_training_data.py \
        --output_dir data/evidence_training \
        --samples_per_class 200
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.ml.evidence_taxonomy import (
    ALL_CATEGORIES,
    ALL_CRIME_TYPES,
    EVIDENCE_CATEGORIES,
    get_expected_evidence,
)

# Section templates per crime category (realistic IPC section combos)
_SECTION_TEMPLATES: dict[str, list[list[str]]] = {
    "murder": [["302", "201", "34"], ["302", "120B"], ["302", "34"], ["304", "34"], ["304B", "498A"]],
    "attempt_to_murder": [["307", "324", "34"], ["307", "34"], ["308", "323"]],
    "robbery": [["392", "397", "34"], ["392", "34"], ["393", "34"], ["394", "34"]],
    "dacoity": [["395", "396", "149"], ["395", "397", "34"], ["395", "149"]],
    "kidnapping": [["363", "365", "34"], ["364A", "34"], ["366", "376"], ["364", "34"]],
    "sexual_offences": [["376", "354", "506"], ["354A", "509"], ["376D", "34"], ["375", "506"]],
    "fraud": [["420", "468", "471"], ["406", "420", "34"], ["420", "34"], ["409", "420"]],
    "cybercrime": [["66", "66C"], ["66D", "420"], ["67A", "66"]],
    "narcotics": [["20", "29"], ["21", "22"], ["20", "27"]],
    "property_crime": [["379", "411", "34"], ["380", "457"], ["436", "34"], ["427", "34"]],
    "missing_persons": [["363", "34"], ["365"], ["346"]],
}

# Narrative snippets per crime category
_NARRATIVE_TEMPLATES: dict[str, list[str]] = {
    "murder": [
        "The accused attacked the deceased with a sharp weapon resulting in death",
        "Body found with multiple stab wounds near the residence of the accused",
        "Deceased was found hanging victim of homicide disguised as suicide",
        "Accused poured kerosene and set fire leading to burn injuries and death",
    ],
    "attempt_to_murder": [
        "The accused attacked with a knife causing grievous injuries",
        "Accused fired gunshots but victim survived with critical injuries",
        "The victim was assaulted with iron rod causing fractures",
    ],
    "robbery": [
        "Armed robbery at jewellery shop looting gold ornaments worth lakhs",
        "Highway robbery by three persons snatching cash and mobile phones",
        "Accused robbed the victim at knife point taking valuables",
    ],
    "dacoity": [
        "Gang of five persons committed dacoity at petrol pump at night",
        "Armed gang robbed a bank looting cash and injuring guard",
        "Group of armed men entered house and looted property",
    ],
    "kidnapping": [
        "Minor child kidnapped from school premises ransom demanded",
        "Young woman abducted for forced marriage by accused",
        "Child was kidnapped by unknown persons for ransom",
    ],
    "sexual_offences": [
        "Victim was sexually assaulted by the accused known to her",
        "Accused committed rape on threat of harm to family",
        "Minor victim assaulted at workplace by supervisor",
    ],
    "fraud": [
        "Accused cheated victim of Rs 50 lakhs through bogus investment scheme",
        "Land deal fraud involving forged documents and fake identity",
        "Online banking fraud through phishing emails and fake websites",
    ],
    "cybercrime": [
        "Hacking of email accounts and stealing confidential data",
        "Identity theft using stolen credentials for financial fraud",
        "Morphed photos circulated on social media for extortion",
    ],
    "narcotics": [
        "Recovery of 5kg charas from the possession of the accused",
        "Manufacturing unit of synthetic drugs raided and dismantled",
        "Accused found in possession of banned narcotic substance",
    ],
    "property_crime": [
        "Theft of jewellery from locked residence during daytime",
        "House breaking at night and theft of electronic items",
        "Arson attack on property causing extensive damage",
    ],
    "missing_persons": [
        "Person missing since last week family suspects foul play",
        "Young girl went missing from home circumstances unknown",
        "Missing person case later found to involve kidnapping",
    ],
}


def _generate_evidence_vector(
    crime: str,
    strength: str,
    rng: random.Random,
) -> dict[str, int]:
    """Generate evidence presence/absence vector for a case.

    strength:
        "strong" — most expected evidence present (80-100%)
        "medium" — moderate evidence present (50-79%)
        "weak"   — sparse evidence (20-49%)
    """
    expected = get_expected_evidence(crime)
    expected_cats = {e["category"] for e in expected}

    # Base probabilities by strength
    p_map = {"strong": 0.9, "medium": 0.65, "weak": 0.30}
    base_p = p_map[strength]

    vector: dict[str, int] = {}
    for cat in ALL_CATEGORIES:
        if cat in expected_cats:
            # Expected evidence: present based on case strength
            weight = EVIDENCE_CATEGORIES[cat]["weight"]
            # Critical evidence more likely present
            if weight == "critical":
                p = min(base_p + 0.1, 1.0)
            elif weight == "important":
                p = base_p
            else:
                p = max(base_p - 0.15, 0.1)
            vector[cat] = 1 if rng.random() < p else 0
        else:
            # Non-expected evidence: occasionally present in strong cases
            if strength == "strong":
                vector[cat] = 1 if rng.random() < 0.15 else 0
            else:
                vector[cat] = 1 if rng.random() < 0.05 else 0

    return vector


def generate_dataset(
    samples_per_class: int = 200,
    seed: int = 42,
) -> list[dict]:
    """Generate the full synthetic dataset."""
    rng = random.Random(seed)
    rows: list[dict] = []

    for crime in ALL_CRIME_TYPES:
        templates = _SECTION_TEMPLATES.get(crime, [["379"]])
        narratives = _NARRATIVE_TEMPLATES.get(crime, ["General case narrative"])

        for i in range(samples_per_class):
            # Vary case strength
            strength = rng.choice(["strong", "medium", "weak"])
            sections = rng.choice(templates)
            narrative = rng.choice(narratives)

            # Build text features
            text_features = f"{crime} {' '.join(sections)} {narrative}"

            # Evidence vector
            evidence = _generate_evidence_vector(crime, strength, rng)

            row = {
                "text_features": text_features,
                "crime_category": crime,
                "section_features": " ".join(sections),
                "strength": strength,
                **evidence,
            }
            rows.append(row)

    rng.shuffle(rows)
    return rows


def main():
    parser = argparse.ArgumentParser(description="Generate evidence training data")
    parser.add_argument("--output_dir", default="data/evidence_training")
    parser.add_argument("--samples_per_class", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating {args.samples_per_class} samples per class "
          f"x {len(ALL_CRIME_TYPES)} categories...")
    rows = generate_dataset(args.samples_per_class, args.seed)

    # Write CSV
    train_path = output_dir / "evidence_training.csv"
    fieldnames = ["text_features", "crime_category", "section_features", "strength"] + ALL_CATEGORIES

    with open(train_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {len(rows)} rows -> {train_path}")
    print(f"Categories: {len(ALL_CATEGORIES)}")
    print(f"Crime types: {len(ALL_CRIME_TYPES)}")


if __name__ == "__main__":
    main()
