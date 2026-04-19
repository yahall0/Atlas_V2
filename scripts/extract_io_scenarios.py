"""Extract the Delhi Police Academy Compendium of Scenarios into JSONL.

Source: ScenariosDelhiPolice.pdf (text-based, 202 pages, 20 scenarios).
Output: ``backend/app/legal_sections/data/io_scenarios_pages.jsonl``
        one line per page: {"page": int, "text": str}

This is the text-extraction step. The structured per-scenario JSONL is
produced by ``backend.app.legal_sections.io_scenarios.build_kb()``.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import fitz  # PyMuPDF

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SOURCE = Path(r"C:/Users/HP/Desktop/ScenariosDelhiPolice.pdf")
OUT = ROOT / "backend" / "app" / "legal_sections" / "data" / "io_scenarios_pages.jsonl"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(SOURCE)
    n = 0
    with OUT.open("w", encoding="utf-8") as fh:
        for pg in range(len(doc)):
            text = doc[pg].get_text()
            fh.write(json.dumps({"page": pg + 1, "text": text}, ensure_ascii=False) + "\n")
            n += 1
    doc.close()
    total_chars = sum(len(json.loads(l)["text"]) for l in OUT.open(encoding="utf-8"))
    print(f"Extracted {n} pages, {total_chars} total characters")
    print(f"Output: {OUT}")


if __name__ == "__main__":
    main()
