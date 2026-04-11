#!/usr/bin/env python3
"""Generate architecture diagrams as PNG images for the ATLAS Architecture doc."""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np
from pathlib import Path

OUT = Path(__file__).parent / "_diagrams"
OUT.mkdir(exist_ok=True)

# ─── Color palette ────────────────────────────────────────────────────────
C = {
    "blue":    "#2563EB",
    "lblue":   "#DBEAFE",
    "green":   "#16A34A",
    "lgreen":  "#DCFCE7",
    "orange":  "#EA580C",
    "lorange": "#FFF7ED",
    "purple":  "#7C3AED",
    "lpurple": "#F3E8FF",
    "red":     "#DC2626",
    "lred":    "#FEE2E2",
    "slate":   "#334155",
    "lslate":  "#F1F5F9",
    "teal":    "#0D9488",
    "lteal":   "#CCFBF1",
    "indigo":  "#4F46E5",
    "lindigo": "#E0E7FF",
    "amber":   "#D97706",
    "lamber":  "#FEF3C7",
    "white":   "#FFFFFF",
    "bg":      "#F8FAFC",
}


def _box(ax, x, y, w, h, label, sublabel=None, color=C["blue"], fill=C["lblue"], fontsize=9, bold=True):
    """Draw a rounded box with label."""
    rect = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.15",
                          facecolor=fill, edgecolor=color, linewidth=1.5)
    ax.add_patch(rect)
    weight = "bold" if bold else "normal"
    ax.text(x + w/2, y + h/2 + (0.15 if sublabel else 0), label,
            ha="center", va="center", fontsize=fontsize, fontweight=weight, color=C["slate"])
    if sublabel:
        ax.text(x + w/2, y + h/2 - 0.25, sublabel,
                ha="center", va="center", fontsize=7, color="#64748B")


def _arrow(ax, x1, y1, x2, y2, color=C["slate"], style="->"):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle=style, color=color, lw=1.5))


def _label_arrow(ax, x1, y1, x2, y2, label, color=C["slate"]):
    _arrow(ax, x1, y1, x2, y2, color)
    mx, my = (x1+x2)/2, (y1+y2)/2
    ax.text(mx + 0.15, my, label, fontsize=7, color="#64748B", fontstyle="italic")


# ══════════════════════════════════════════════════════════════════════════
# DIAGRAM 1: System Architecture
# ══════════════════════════════════════════════════════════════════════════

def diagram_system_architecture():
    fig, ax = plt.subplots(figsize=(14, 9))
    ax.set_xlim(-0.5, 14)
    ax.set_ylim(-0.5, 9.5)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor(C["bg"])

    # Title
    ax.text(7, 9.1, "ATLAS Platform — System Architecture", ha="center",
            fontsize=16, fontweight="bold", color=C["slate"])

    # Frontend
    _box(ax, 0.3, 6.5, 3, 1.8, "Frontend", "Next.js 14 · React 18\nTailwind + shadcn/ui\nPort 3000", C["blue"], C["lblue"])

    # Backend
    _box(ax, 4.5, 5, 5.5, 4, "", color=C["indigo"], fill=C["lindigo"])
    ax.text(7.25, 8.7, "Backend — FastAPI", ha="center", fontsize=11, fontweight="bold", color=C["indigo"])
    ax.text(7.25, 8.35, "Python 3.11 · Uvicorn · Port 8000", ha="center", fontsize=7, color="#64748B")

    # Backend internal boxes
    _box(ax, 4.8, 7.2, 2.3, 1, "Ingestion", "pdf_parser\nfir_parser\ncs_parser", C["teal"], C["lteal"], 8)
    _box(ax, 7.4, 7.2, 2.3, 1, "NLP Pipeline", "classify.py\nzero_shot.py\nlanguage.py", C["purple"], C["lpurple"], 8)
    _box(ax, 4.8, 5.5, 2.3, 1, "Legal Engine", "validator (7 rules)\nsections.json (73)", C["orange"], C["lorange"], 8)
    _box(ax, 7.4, 5.5, 2.3, 1, "Evidence AI", "gap_model (2-tier)\ntaxonomy (20 cats)", C["green"], C["lgreen"], 8)

    # Auth/Audit row
    _box(ax, 4.8, 5.0, 2.3, 0.4, "JWT Auth · RBAC (6 roles)", color=C["red"], fill=C["lred"], fontsize=7)
    _box(ax, 7.4, 5.0, 2.3, 0.4, "Audit Chain · SHA-256", color=C["amber"], fill=C["lamber"], fontsize=7)

    # Databases
    _box(ax, 0.3, 2.5, 2.2, 1.5, "PostgreSQL 15", "Relational DB\n10 tables · UUID PKs\nJSONB + normalized", C["blue"], C["lblue"], 8)
    _box(ax, 2.8, 2.5, 2.2, 1.5, "MongoDB 7", "Document Store\nRaw OCR text\nFire-and-forget", C["green"], C["lgreen"], 8)
    _box(ax, 5.3, 2.5, 2.2, 1.5, "Redis 7", "Cache Layer\nSession state\nRate limiting", C["red"], C["lred"], 8)

    # Monitoring
    _box(ax, 8, 2.5, 2.2, 1.5, "Monitoring", "Prometheus v2.50\nGrafana 10.3\nstructlog JSON", C["amber"], C["lamber"], 8)
    _box(ax, 10.5, 2.5, 2.2, 1.5, "MLOps", "MLflow v2.11\nLabel Studio\nExperiment tracking", C["purple"], C["lpurple"], 8)

    # Arrows
    _arrow(ax, 3.3, 7.4, 4.5, 7.4, C["blue"])  # Frontend → Backend
    _arrow(ax, 4.5, 7.4, 3.3, 7.4, C["blue"])
    ax.text(3.9, 7.55, "REST\nAPI", ha="center", fontsize=6, color="#64748B")

    _arrow(ax, 6, 5.0, 3, 4.0, C["blue"])  # Backend → Postgres
    _arrow(ax, 7, 5.0, 4, 4.0, C["green"])  # Backend → Mongo
    _arrow(ax, 8, 5.0, 6.5, 4.0, C["red"])  # Backend → Redis

    # Legend
    ax.text(0.3, 0.8, "Design Principles:", fontsize=8, fontweight="bold", color=C["slate"])
    principles = ["On-premise only (no cloud APIs)", "CPU-only inference (16 GB RAM)",
                   "Polyglot persistence", "Graceful AI degradation"]
    for i, p in enumerate(principles):
        ax.text(0.3 + (i % 2) * 5, 0.3 - (i // 2) * 0.35, f"  {p}", fontsize=7, color="#64748B")

    fig.savefig(OUT / "01_system_architecture.png", dpi=180, bbox_inches="tight", facecolor=C["bg"])
    plt.close()
    print("  01_system_architecture.png")


# ══════════════════════════════════════════════════════════════════════════
# DIAGRAM 2: Classification Cascade
# ══════════════════════════════════════════════════════════════════════════

def diagram_classification_cascade():
    fig, ax = plt.subplots(figsize=(10, 12))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 13)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor(C["bg"])

    ax.text(5, 12.6, "4-Tier Classification Cascade", ha="center",
            fontsize=14, fontweight="bold", color=C["slate"])

    # Input
    _box(ax, 3, 11.3, 4, 0.8, "FIR Ingested", "Raw text extracted from PDF", C["slate"], C["lslate"])
    _arrow(ax, 5, 11.3, 5, 10.8)

    # Tier 1
    _box(ax, 1.5, 9.2, 7, 1.5, "Tier 1: Section Map", "section_map.py — deterministic IPC/BNS lookup\n~80 IPC + ~50 BNS sections mapped to 11 categories\nPriority tiebreak: murder > rape > robbery > ...", C["blue"], C["lblue"])
    ax.text(9, 10.2, "Confidence: 1.0\nSpeed: <1 ms", fontsize=7, color=C["blue"], fontweight="bold")
    _arrow(ax, 5, 10.8, 5, 10.7)

    # Decision 1
    diamond_x, diamond_y = 5, 8.7
    diamond = plt.Polygon([[diamond_x, diamond_y+0.4], [diamond_x+0.8, diamond_y],
                            [diamond_x, diamond_y-0.4], [diamond_x-0.8, diamond_y]],
                           facecolor=C["lamber"], edgecolor=C["amber"], linewidth=1.5)
    ax.add_patch(diamond)
    ax.text(diamond_x, diamond_y, "Sections\nfound?", ha="center", va="center", fontsize=6, fontweight="bold")

    _arrow(ax, 5, 9.2, 5, 9.1)  # tier1 → diamond
    ax.text(9.2, 8.7, "YES → return", fontsize=7, color=C["green"], fontweight="bold")
    _arrow(ax, 5, 8.3, 5, 8.0)  # diamond → tier2
    ax.text(4.2, 8.15, "NO", fontsize=7, color=C["red"], fontweight="bold")

    # Tier 2
    _box(ax, 1.5, 6.4, 7, 1.5, "Tier 2: Fine-Tuned MuRIL", "google/muril-base-cased — 237M parameters\nTrained on Gujarati/Hindi/English FIR narratives\nThreshold: confidence ≥ 0.25 (random = 0.091)", C["purple"], C["lpurple"])
    ax.text(9, 7.4, "Speed: 2-5s\nCPU only", fontsize=7, color=C["purple"], fontweight="bold")

    # Decision 2
    d2_y = 5.9
    diamond2 = plt.Polygon([[5, d2_y+0.4], [5.8, d2_y], [5, d2_y-0.4], [4.2, d2_y]],
                            facecolor=C["lamber"], edgecolor=C["amber"], linewidth=1.5)
    ax.add_patch(diamond2)
    ax.text(5, d2_y, "Conf\n≥ 0.25?", ha="center", va="center", fontsize=6, fontweight="bold")
    _arrow(ax, 5, 6.4, 5, 6.3)
    _arrow(ax, 5, 5.5, 5, 5.2)
    ax.text(4.2, 5.35, "NO", fontsize=7, color=C["red"], fontweight="bold")

    # Tier 3
    _box(ax, 1.5, 3.6, 7, 1.5, "Tier 3: Zero-Shot NLI", "mDeBERTa-v3-base-mnli-xnli — ~270 MB\nBilingual hypotheses (English + Gujarati)\nInput truncated to 600 chars · Threshold ≥ 0.20", C["teal"], C["lteal"])
    ax.text(9, 4.6, "Speed: 10-30s\nNo training needed", fontsize=7, color=C["teal"], fontweight="bold")

    # Decision 3
    d3_y = 3.1
    diamond3 = plt.Polygon([[5, d3_y+0.4], [5.8, d3_y], [5, d3_y-0.4], [4.2, d3_y]],
                            facecolor=C["lamber"], edgecolor=C["amber"], linewidth=1.5)
    ax.add_patch(diamond3)
    ax.text(5, d3_y, "Score\n≥ 0.20?", ha="center", va="center", fontsize=6, fontweight="bold")
    _arrow(ax, 5, 3.6, 5, 3.5)
    _arrow(ax, 5, 2.7, 5, 2.4)
    ax.text(4.2, 2.55, "NO", fontsize=7, color=C["red"], fontweight="bold")

    # Tier 4
    _box(ax, 1.5, 0.8, 7, 1.5, "Tier 4: Keyword Heuristics", "10 categories × 7+ keywords (English + Gujarati)\nConfidence = min(0.5 + matches×0.1, 0.85)\nAlways returns a result — never fails", C["orange"], C["lorange"])
    ax.text(9, 1.8, "Speed: <1 ms\nAlways available", fontsize=7, color=C["orange"], fontweight="bold")

    fig.savefig(OUT / "02_classification_cascade.png", dpi=180, bbox_inches="tight", facecolor=C["bg"])
    plt.close()
    print("  02_classification_cascade.png")


# ══════════════════════════════════════════════════════════════════════════
# DIAGRAM 3: PDF Extraction Pipeline
# ══════════════════════════════════════════════════════════════════════════

def diagram_pdf_extraction():
    fig, ax = plt.subplots(figsize=(11, 7))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 7.5)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor(C["bg"])

    ax.text(5.5, 7.1, "PDF Text Extraction — Three-Stage Fallback", ha="center",
            fontsize=14, fontweight="bold", color=C["slate"])

    # Input
    _box(ax, 4, 5.8, 3, 0.8, "PDF Bytes", "Uploaded by user", C["slate"], C["lslate"])
    _arrow(ax, 5.5, 5.8, 5.5, 5.3)

    # Stage 1
    _box(ax, 2.5, 3.8, 6, 1.4, "Stage 1: pdfplumber", "Fast text-layer extraction for digital PDFs\nNo OCR needed — reads embedded text directly\nThreshold: ≥ 50 non-whitespace characters", C["blue"], C["lblue"])
    ax.text(9, 4.8, "Speed: ~0.5s", fontsize=7, color=C["blue"], fontweight="bold")

    # Decision
    d_y = 3.3
    diamond = plt.Polygon([[5.5, d_y+0.35], [6.2, d_y], [5.5, d_y-0.35], [4.8, d_y]],
                           facecolor=C["lamber"], edgecolor=C["amber"], linewidth=1.5)
    ax.add_patch(diamond)
    ax.text(5.5, d_y, "≥50\nchars?", ha="center", va="center", fontsize=6, fontweight="bold")
    _arrow(ax, 5.5, 3.8, 5.5, 3.65)
    ax.text(6.5, 3.3, "YES → done", fontsize=7, color=C["green"], fontweight="bold")

    # Stage 2
    _box(ax, 0.5, 1.3, 4.5, 1.3, "Stage 2: pdf2image + Tesseract", "Poppler renders pages at 300 DPI\nTesseract OCR: eng + guj languages\nPSM mode 6 (uniform text block)", C["purple"], C["lpurple"], 8)
    _arrow(ax, 4.8, 2.95, 2.75, 2.6)
    ax.text(3.2, 2.8, "NO", fontsize=7, color=C["red"], fontweight="bold")

    # Stage 3
    _box(ax, 5.5, 1.3, 4.5, 1.3, "Stage 3: PyMuPDF + Tesseract", "Fallback when Poppler unavailable\nRenders at 200 DPI (lower quality)\nSame Tesseract eng+guj config", C["orange"], C["lorange"], 8)
    _arrow(ax, 2.75, 1.3, 2.75, 0.8)
    ax.text(3.5, 0.9, "Poppler missing?", fontsize=7, color=C["red"])
    _arrow(ax, 4.2, 0.7, 5.5, 1.3)

    # Output
    _box(ax, 3.5, 0, 4, 0.6, "Raw Text String", color=C["green"], fill=C["lgreen"], fontsize=9)
    _arrow(ax, 7.75, 1.3, 5.5, 0.6)
    _arrow(ax, 2.75, 0.75, 4.5, 0.6)

    fig.savefig(OUT / "03_pdf_extraction.png", dpi=180, bbox_inches="tight", facecolor=C["bg"])
    plt.close()
    print("  03_pdf_extraction.png")


# ══════════════════════════════════════════════════════════════════════════
# DIAGRAM 4: Evidence Gap Detection
# ══════════════════════════════════════════════════════════════════════════

def diagram_evidence_gap():
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8.5)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor(C["bg"])

    ax.text(6, 8.1, "Two-Tier Evidence Gap Detection", ha="center",
            fontsize=14, fontweight="bold", color=C["slate"])

    # Input
    _box(ax, 4, 6.8, 4, 0.8, "Chargesheet Data", "charges_json + evidence_json", C["slate"], C["lslate"])

    # Split arrows
    _arrow(ax, 5, 6.8, 2.5, 6.2)
    _arrow(ax, 7, 6.8, 9, 6.2)

    # Left: classify evidence
    _box(ax, 0.5, 5, 4, 1.1, "Classify Evidence Items", "37 keyword groups (EN + GU + HI)\nrapidfuzz fallback (≥75% match)\n→ Present categories (set)", C["green"], C["lgreen"], 8)

    # Right: get expected
    _box(ax, 7, 5, 4, 1.1, "Get Expected Evidence", "Crime type → taxonomy lookup\n20 categories × weight\n→ Expected categories (set)", C["blue"], C["lblue"], 8)

    # Tier 1
    _arrow(ax, 2.5, 5, 4.5, 4.2)
    _arrow(ax, 9, 5, 7.5, 4.2)
    _box(ax, 2.5, 2.8, 7, 1.3, "Tier 1: Rule-Based Gap Detection", "Gap = Expected − Present\nSeverity: critical (mandatory) / important (common)\nConfidence: 1.0 — deterministic", C["orange"], C["lorange"])
    ax.text(10, 3.6, "Always runs\nNo model needed", fontsize=7, color=C["orange"], fontweight="bold")

    # Tier 2
    _arrow(ax, 6, 2.8, 6, 2.3)
    _box(ax, 2.5, 0.8, 7, 1.4, "Tier 2: ML Pattern Detection", "TF-IDF (3000 features) + LogisticRegression\nPredicts P(category present) for each of 20 categories\nLow P + not in Tier 1 gaps → 'AI-suggested' gap\nModel: <10 MB · Inference: <1s CPU", C["purple"], C["lpurple"])
    ax.text(10, 1.6, "Runs if model\nis loaded", fontsize=7, color=C["purple"], fontweight="bold")
    ax.text(10, 0.9, "Macro-F1 ≥ 0.65", fontsize=7, color=C["green"], fontweight="bold")

    fig.savefig(OUT / "04_evidence_gap.png", dpi=180, bbox_inches="tight", facecolor=C["bg"])
    plt.close()
    print("  04_evidence_gap.png")


# ══════════════════════════════════════════════════════════════════════════
# DIAGRAM 5: Audit Hash Chain
# ══════════════════════════════════════════════════════════════════════════

def diagram_audit_chain():
    fig, ax = plt.subplots(figsize=(13, 5))
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 5.5)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor(C["bg"])

    ax.text(6.5, 5.1, "SHA-256 Tamper-Evident Audit Chain", ha="center",
            fontsize=14, fontweight="bold", color=C["slate"])

    # Entry 0
    _box(ax, 0.3, 1.8, 3.5, 2.5, "", color=C["blue"], fill=C["lblue"])
    ax.text(2.05, 4.0, "Entry 0", ha="center", fontsize=9, fontweight="bold", color=C["blue"])
    entries = [
        ("action:", "REVIEW_STARTED"),
        ("detail:", '{"reviewer": "sho"}'),
        ("timestamp:", "T0"),
        ("prev_hash:", "GENESIS"),
        ("entry_hash:", "a3f7c2..."),
    ]
    for i, (k, v) in enumerate(entries):
        y = 3.5 - i * 0.35
        ax.text(0.6, y, k, fontsize=7, fontweight="bold", color=C["slate"])
        ax.text(1.8, y, v, fontsize=7, color="#64748B", fontfamily="monospace")

    # Entry 1
    _box(ax, 4.5, 1.8, 3.5, 2.5, "", color=C["green"], fill=C["lgreen"])
    ax.text(6.25, 4.0, "Entry 1", ha="center", fontsize=9, fontweight="bold", color=C["green"])
    entries1 = [
        ("action:", "REC_ACCEPTED"),
        ("detail:", '{"rec_id": "R1"}'),
        ("timestamp:", "T1"),
        ("prev_hash:", "a3f7c2..."),
        ("entry_hash:", "8b21e5..."),
    ]
    for i, (k, v) in enumerate(entries1):
        y = 3.5 - i * 0.35
        ax.text(4.8, y, k, fontsize=7, fontweight="bold", color=C["slate"])
        ax.text(6.0, y, v, fontsize=7, color="#64748B", fontfamily="monospace")

    # Entry 2
    _box(ax, 8.7, 1.8, 3.5, 2.5, "", color=C["orange"], fill=C["lorange"])
    ax.text(10.45, 4.0, "Entry 2", ha="center", fontsize=9, fontweight="bold", color=C["orange"])
    entries2 = [
        ("action:", "REC_DISMISSED"),
        ("detail:", '{"reason": "N/A"}'),
        ("timestamp:", "T2"),
        ("prev_hash:", "8b21e5..."),
        ("entry_hash:", "f4d901..."),
    ]
    for i, (k, v) in enumerate(entries2):
        y = 3.5 - i * 0.35
        ax.text(9.0, y, k, fontsize=7, fontweight="bold", color=C["slate"])
        ax.text(10.2, y, v, fontsize=7, color="#64748B", fontfamily="monospace")

    # Chain arrows
    _arrow(ax, 3.8, 3.0, 4.5, 3.0, C["blue"])
    ax.text(4.15, 3.3, "H0", fontsize=8, fontweight="bold", color=C["blue"], fontfamily="monospace")
    _arrow(ax, 8.0, 3.0, 8.7, 3.0, C["green"])
    ax.text(8.35, 3.3, "H1", fontsize=8, fontweight="bold", color=C["green"], fontfamily="monospace")

    # Hash formula
    ax.text(6.5, 1.2, "Hash formula:  H = SHA-256( action | json(detail) | iso(timestamp) | previous_hash )",
            ha="center", fontsize=8, fontfamily="monospace", color=C["slate"],
            bbox=dict(boxstyle="round,pad=0.4", facecolor=C["lslate"], edgecolor="#CBD5E1"))

    fig.savefig(OUT / "05_audit_chain.png", dpi=180, bbox_inches="tight", facecolor=C["bg"])
    plt.close()
    print("  05_audit_chain.png")


# ══════════════════════════════════════════════════════════════════════════
# DIAGRAM 6: FIR Ingestion Control Flow
# ══════════════════════════════════════════════════════════════════════════

def diagram_fir_ingestion_flow():
    fig, ax = plt.subplots(figsize=(10, 14))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 15)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor(C["bg"])

    ax.text(5, 14.6, "FIR Ingestion — End-to-End Control Flow", ha="center",
            fontsize=14, fontweight="bold", color=C["slate"])

    steps = [
        (13.5, "User uploads PDF", "via /dashboard/fir", C["slate"], C["lslate"]),
        (12.3, "POST /api/v1/ingest", "FastAPI endpoint (IO/SHO/ADMIN)", C["blue"], C["lblue"]),
        (11.1, "extract_text_from_pdf()", "pdfplumber → OCR fallback chain", C["teal"], C["lteal"]),
        (9.9, "parse_fir_text()", "Anchor regex · Gujarati digits · OCR fixes", C["purple"], C["lpurple"]),
        (8.7, "create_fir()", "INSERT into PostgreSQL (parameterised)", C["blue"], C["lblue"]),
        (7.5, "MongoDB: store raw OCR", "Fire-and-forget (non-blocking)", C["green"], C["lgreen"]),
        (6.3, "normalise_text()", "Unicode NFC · IndicXlit transliteration", C["teal"], C["lteal"]),
        (5.1, "infer_category_from_sections()", "Tier 1: deterministic section lookup", C["blue"], C["lblue"]),
        (3.5, "classify_fir()", "Tiers 2-4: MuRIL → zero-shot → heuristics", C["purple"], C["lpurple"]),
        (2.3, "Mismatch detection", "Compare section-inferred vs NLP category", C["orange"], C["lorange"]),
        (1.1, "Return FIRResponse", "JSON with classification + mismatch flag", C["green"], C["lgreen"]),
    ]

    for y, title, sub, c, fc in steps:
        _box(ax, 2, y, 6, 0.8, title, sub, c, fc, 8)

    for i in range(len(steps) - 1):
        y_from = steps[i][0]
        y_to = steps[i+1][0] + 0.8
        _arrow(ax, 5, y_from, 5, y_to)

    # Side annotations
    ax.text(8.5, 4.0, "If sections found\n→ skip Tiers 2-4\n(confidence = 1.0)",
            fontsize=7, color=C["blue"], fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", facecolor=C["lblue"], edgecolor=C["blue"], alpha=0.7))
    _arrow(ax, 8, 4.0, 6.5, 5.1, C["blue"], "->")

    ax.text(8.5, 2.3, "If mismatch:\nstatus = 'review_needed'",
            fontsize=7, color=C["red"], fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", facecolor=C["lred"], edgecolor=C["red"], alpha=0.7))

    fig.savefig(OUT / "06_fir_ingestion_flow.png", dpi=180, bbox_inches="tight", facecolor=C["bg"])
    plt.close()
    print("  06_fir_ingestion_flow.png")


# ══════════════════════════════════════════════════════════════════════════
# DIAGRAM 7: Chargesheet Review Flow
# ══════════════════════════════════════════════════════════════════════════

def diagram_review_flow():
    fig, ax = plt.subplots(figsize=(10, 12))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 13)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor(C["bg"])

    ax.text(5, 12.6, "Chargesheet Review — End-to-End Flow", ha="center",
            fontsize=14, fontweight="bold", color=C["slate"])

    steps = [
        (11.5, "Navigate to /chargesheet/[id]", "Load parsed chargesheet data", C["slate"], C["lslate"]),
        (10.3, 'Click "Start Review"', "POST /review/chargesheet/{id}/start", C["blue"], C["lblue"]),
        (9.1, "Status → under_review", "Audit: REVIEW_STARTED logged", C["amber"], C["lamber"]),
        (7.9, "Legal Validation runs", "7 rules → findings (CRITICAL/ERROR/WARNING)", C["orange"], C["lorange"]),
        (6.7, "Evidence Gap Detection runs", "Tier 1 (rules) + Tier 2 (ML) → gaps", C["green"], C["lgreen"]),
        (5.5, "Reviewer acts on each finding", "Accept / Modify / Dismiss", C["purple"], C["lpurple"]),
        (4.3, "Each action → audit entry", "SHA-256 chained · recommendation_actions table", C["amber"], C["lamber"]),
        (3.1, 'Click "Complete Review"', "POST /review/chargesheet/{id}/complete", C["blue"], C["lblue"]),
        (1.9, "Status → reviewed or flagged", "Audit: REVIEW_COMPLETED / REVIEW_FLAGGED", C["green"], C["lgreen"]),
        (0.7, "Audit chain exportable as CSV", "Court-admissible with SHA-256 hashes", C["teal"], C["lteal"]),
    ]

    for y, title, sub, c, fc in steps:
        _box(ax, 1.5, y, 7, 0.8, title, sub, c, fc, 8)

    for i in range(len(steps) - 1):
        _arrow(ax, 5, steps[i][0], 5, steps[i+1][0] + 0.8)

    fig.savefig(OUT / "07_review_flow.png", dpi=180, bbox_inches="tight", facecolor=C["bg"])
    plt.close()
    print("  07_review_flow.png")


# ══════════════════════════════════════════════════════════════════════════
# Run all
# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Generating diagrams...")
    diagram_system_architecture()
    diagram_classification_cascade()
    diagram_pdf_extraction()
    diagram_evidence_gap()
    diagram_audit_chain()
    diagram_fir_ingestion_flow()
    diagram_review_flow()
    print(f"Done — {len(list(OUT.glob('*.png')))} diagrams in {OUT}")
