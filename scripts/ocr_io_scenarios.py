"""OCR the Delhi Police Academy Compendium of Scenarios (188 pages).

Output: ``backend/app/legal_sections/data/io_scenarios_raw_ocr.jsonl``
        one line per page: {"page": int, "text": str, "regions": int}

Idempotent: pages already present in the output file are skipped.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

import fitz
import numpy as np
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

SOURCE = Path(r"C:/Users/HP/Desktop/ScenariosOfIO.pdf")
OUT = Path(__file__).resolve().parents[1] / "backend" / "app" / "legal_sections" / "data" / "io_scenarios_raw_ocr.jsonl"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    done: set[int] = set()
    if OUT.exists():
        for line in OUT.open(encoding="utf-8"):
            try:
                done.add(json.loads(line)["page"])
            except (json.JSONDecodeError, KeyError):
                pass
    print(f"[OCR] Already done: {len(done)} pages")

    ocr = RapidOCR()
    doc = fitz.open(SOURCE)
    print(f"[OCR] Source: {SOURCE} ({len(doc)} pages)")

    with OUT.open("a", encoding="utf-8") as fh:
        for pg in range(len(doc)):
            if (pg + 1) in done:
                continue
            pix = doc[pg].get_pixmap(dpi=200)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            arr = np.array(img)
            result, _ = ocr(arr)
            regions = result or []
            text = "\n".join(r[1] for r in regions)
            record = {"page": pg + 1, "text": text, "regions": len(regions)}
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            fh.flush()
            print(f"[OCR] page {pg+1:3d}: {len(regions)} regions, {len(text)} chars")
    doc.close()
    print("[OCR] DONE.")


if __name__ == "__main__":
    main()
