#!/usr/bin/env python3
"""Set up Label Studio annotation projects for ATLAS Sprint 2.

Creates two projects:
  1. FIR_NER        — Named entity recognition for FIR parties and locations
  2. FIR_Category   — Text classification into ATLAS crime categories

Usage
-----
    python scripts/setup_labelstudio.py \\
        --url   http://localhost:8080 \\
        --email atlas@atlas.local \\
        --password atlasadmin

Requires ``label-studio-sdk`` (installed via requirements.txt).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

# ---------------------------------------------------------------------------
# Label config templates
# ---------------------------------------------------------------------------

# NER project — labels match common FIR entities
NER_CONFIG = """<View>
  <Header value="Mark named entities in the FIR text"/>
  <Text name="text" value="$text"/>
  <Labels name="label" toName="text">
    <Label value="PERSON"          background="#FFA39E"/>
    <Label value="LOCATION"        background="#ADC6FF"/>
    <Label value="POLICE_STATION"  background="#B7EB8F"/>
    <Label value="DATE_TIME"       background="#FFD591"/>
    <Label value="IPC_SECTION"     background="#D3ADF7"/>
    <Label value="BNS_SECTION"     background="#87E8DE"/>
    <Label value="VEHICLE"         background="#FFE58F"/>
    <Label value="WEAPON"          background="#FFA940"/>
  </Labels>
</View>"""

# Classification project — ATLAS crime categories
CLASSIFICATION_CONFIG = """<View>
  <Header value="Select the primary crime category for this FIR"/>
  <Text name="text" value="$text"/>
  <Choices name="category" toName="text" choice="single" showInLine="true">
    <Choice value="theft"/>
    <Choice value="assault"/>
    <Choice value="fraud"/>
    <Choice value="murder"/>
    <Choice value="rape_sexoff"/>
    <Choice value="cybercrime"/>
    <Choice value="narcotics"/>
    <Choice value="kidnapping"/>
    <Choice value="dacoity_robbery"/>
    <Choice value="domestic_violence"/>
    <Choice value="other"/>
  </Choices>
</View>"""


# ---------------------------------------------------------------------------
# Setup logic
# ---------------------------------------------------------------------------


def create_projects(url: str, email: str, password: str) -> None:
    """Authenticate and create the two annotation projects."""
    try:
        from label_studio_sdk import Client  # type: ignore
    except ImportError:
        logger.error(
            "label-studio-sdk is not installed. "
            "Run: pip install label-studio-sdk>=0.8.0"
        )
        sys.exit(1)

    try:
        ls = Client(url=url, api_key=None)
        ls.check_connection()
    except Exception:
        # SDK versions differ — try email/password auth
        try:
            ls = Client(url=url, email=email, password=password)
        except Exception as exc:
            logger.error("Could not connect to Label Studio at %s: %s", url, exc)
            sys.exit(1)

    # ── Project 1: NER ────────────────────────────────────────────────────
    try:
        ner_project = ls.start_project(
            title="FIR_NER",
            label_config=NER_CONFIG,
        )
        logger.info("Created NER project (id=%s)", ner_project.id)
    except Exception as exc:
        logger.warning("FIR_NER project may already exist or failed: %s", exc)

    # ── Project 2: Classification ─────────────────────────────────────────
    try:
        cls_project = ls.start_project(
            title="FIR_Category",
            label_config=CLASSIFICATION_CONFIG,
        )
        logger.info("Created Category project (id=%s)", cls_project.id)
    except Exception as exc:
        logger.warning("FIR_Category project may already exist or failed: %s", exc)

    logger.info(
        "Label Studio setup complete. "
        "Open %s to start annotating.",
        url,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create ATLAS annotation projects in Label Studio."
    )
    parser.add_argument("--url", default="http://localhost:8080", help="Label Studio URL.")
    parser.add_argument("--email", default="atlas@atlas.local")
    parser.add_argument("--password", default="atlasadmin")
    args = parser.parse_args()
    create_projects(args.url, args.email, args.password)
