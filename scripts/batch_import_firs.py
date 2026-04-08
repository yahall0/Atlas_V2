#!/usr/bin/env python3
"""Batch import anonymised eGujCop FIR PDFs into the ATLAS platform.

Usage
-----
    python scripts/batch_import_firs.py \\
        --input_dir /data/egujcop_firs \\
        --api_url   http://localhost:8000 \\
        --token     <jwt_token>

The script walks *input_dir* for ``*.pdf`` files, posts each to
``POST /api/v1/ingest``, and writes a summary CSV to
``batch_import_<timestamp>.csv`` in the current directory.

IPC→BNS section mapping is applied to the ``primary_sections`` field
before the result is committed.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import logging
import os
import sys
import time
from pathlib import Path

import requests

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

# ---------------------------------------------------------------------------
# IPC → BNS section mapping (common homologous sections)
# ---------------------------------------------------------------------------

IPC_TO_BNS: dict[str, str] = {
    "302": "101",   # Murder
    "304A": "106",  # Causing death by negligence
    "307": "109",   # Attempt to murder
    "376": "63",    # Rape
    "354": "74",    # Assault on woman
    "379": "303",   # Theft
    "380": "305",   # Theft in dwelling
    "382": "309",   # Theft after preparation for hurt
    "392": "309",   # Robbery
    "395": "310",   # Dacoity
    "396": "311",   # Dacoity with murder
    "420": "318",   # Cheating
    "323": "115",   # Voluntarily causing hurt
    "324": "117",   # Hurt with dangerous weapon
    "325": "118",   # Grievous hurt
    "326": "119",   # Grievous hurt with weapon
    "365": "137",   # Kidnapping
    "366": "140",   # Abduction
    "363": "137",   # Kidnapping from lawful guardianship
    "498A": "85",   # Cruelty by husband
}


def map_ipc_to_bns(sections: list[str]) -> list[str]:
    """Replace known IPC section numbers with their BNS equivalents."""
    return [IPC_TO_BNS.get(s.strip(), s.strip()) for s in sections if s.strip()]


# ---------------------------------------------------------------------------
# Import helpers
# ---------------------------------------------------------------------------


def ingest_pdf(
    pdf_path: Path,
    api_url: str,
    token: str,
    session: requests.Session,
    max_retries: int = 3,
    retry_delay: float = 2.0,
) -> dict:
    """POST a single PDF to /api/v1/ingest and return the JSON response."""
    url = f"{api_url}/api/v1/ingest"
    headers = {"Authorization": f"Bearer {token}"}

    for attempt in range(1, max_retries + 1):
        try:
            with pdf_path.open("rb") as fh:
                resp = session.post(
                    url,
                    headers=headers,
                    files={"file": (pdf_path.name, fh, "application/pdf")},
                    timeout=60,
                )
            if resp.status_code in (200, 201):
                data = resp.json()
                # Remap IPC → BNS sections
                if "primary_sections" in data and isinstance(
                    data["primary_sections"], list
                ):
                    data["primary_sections"] = map_ipc_to_bns(data["primary_sections"])
                return data
            logger.warning(
                "Attempt %d/%d: HTTP %d for %s",
                attempt, max_retries, resp.status_code, pdf_path.name,
            )
        except requests.RequestException as exc:
            logger.warning("Attempt %d/%d: %s for %s", attempt, max_retries, exc, pdf_path.name)
        if attempt < max_retries:
            time.sleep(retry_delay)

    return {"error": "max_retries_exceeded", "file": pdf_path.name}


def run_batch_import(
    input_dir: str,
    api_url: str,
    token: str,
    delay: float = 0.5,
) -> None:
    """Walk *input_dir* and import all PDFs."""
    pdf_files = sorted(Path(input_dir).rglob("*.pdf"))
    if not pdf_files:
        logger.error("No PDF files found in %s", input_dir)
        sys.exit(1)

    logger.info("Found %d PDF files in %s", len(pdf_files), input_dir)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_csv = Path(f"batch_import_{timestamp}.csv")

    results: list[dict] = []
    session = requests.Session()

    for i, pdf in enumerate(pdf_files, start=1):
        logger.info("[%d/%d] Importing %s …", i, len(pdf_files), pdf.name)
        result = ingest_pdf(pdf, api_url, token, session)
        result["source_file"] = pdf.name
        results.append(result)
        if delay > 0:
            time.sleep(delay)

    # Write summary CSV
    fieldnames = [
        "source_file", "id", "fir_number", "district", "police_station",
        "primary_sections", "completeness_pct", "error",
    ]
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            if "primary_sections" in r and isinstance(r["primary_sections"], list):
                r["primary_sections"] = "; ".join(r["primary_sections"])
            writer.writerow(r)

    success = sum(1 for r in results if "error" not in r)
    logger.info(
        "Import complete: %d/%d succeeded. Summary written to %s",
        success, len(results), out_csv,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch import eGujCop FIR PDFs into ATLAS.")
    parser.add_argument("--input_dir", required=True, help="Directory containing FIR PDFs.")
    parser.add_argument("--api_url", default="http://localhost:8000", help="ATLAS API base URL.")
    parser.add_argument("--token", required=True, help="JWT bearer token.")
    parser.add_argument("--delay", type=float, default=0.5, help="Seconds between requests.")
    args = parser.parse_args()
    run_batch_import(args.input_dir, args.api_url, args.token, args.delay)
