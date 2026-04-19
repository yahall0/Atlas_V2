"""Extract IPC and BNS sections from official PDFs into JSONL (verbatim).

Reads:
    C:/Users/HP/Desktop/RP2/ipc sections pdf.pdf
    C:/Users/HP/Desktop/RP2/bns sections.pdf

Writes:
    backend/app/legal_sections/data/ipc_sections.jsonl
    backend/app/legal_sections/data/bns_sections.jsonl
    backend/app/legal_sections/data/extraction_report.json
    backend/app/legal_sections/data/{act}_sections.body.txt  (audit copy)

Design:
    - PyMuPDF (fitz) for text extraction (clean Unicode).
    - TOC pages skipped by finding the second occurrence of the act's formal
      header alongside "ACT NO.".
    - Section boundary = any line start matching `<num>.` followed by optional
      em/en-dash. This handles three title/body separators seen in the PDFs:
        1. `102. Culpable homicide.\u2014<body>` (standard)
        2. `217. Title line 1\n title line 2\u2014<body>` (no period before dash)
        3. `255.\u2014Title.\u2014<body>` (dash right after number)
    - `full_text` spans verbatim from section start to next section start.
    - Sub-components (illustrations/explanations/exceptions) are secondary
      metadata; full_text remains authoritative.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

import fitz  # PyMuPDF

# Make backend.* importable when running this script standalone.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.legal_sections.subclause_parser import (  # noqa: E402
    parse_subclauses,
    to_jsonable as subclauses_to_jsonable,
)

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "backend" / "app" / "legal_sections" / "data"
OUT_DIR.mkdir(parents=True, exist_ok=True)

IPC_PDF = Path(r"C:/Users/HP/Desktop/RP2/ipc sections pdf.pdf")
BNS_PDF = Path(r"C:/Users/HP/Desktop/RP2/bns sections.pdf")

EM_DASH = "\u2014"
EN_DASH = "\u2013"
DASH_CLASS = f"[{EN_DASH}{EM_DASH}]"

# Line-start section number. Accepts optional amendment-footnote bracket
# prefix like `9[` or `11[` that wraps sections inserted/substituted by later
# amendment acts. The terminator is normally `.`, but a few amended sections
# drop the period before the quoted definition title
# (e.g. IPC `1[17 "Government"...`), so we also accept ` "` / ` '`.
SECTION_HEAD_RE = re.compile(
    rf"(?m)^[ \t]*(?:\d+\[)?(?P<num>\d{{1,3}}[A-Z]{{0,2}})"
    rf"(?:\.(?P<immediate_dash>{DASH_CLASS})?|(?=\s+[\u2018\u201C]))"
)

CHAPTER_RE = re.compile(
    r"^\s*CHAPTER\s+([IVXLCDM]+[A-Z]{0,2})\s*\n([^\n]+)", re.MULTILINE
)

ILLUSTRATION_BLOCK_RE = re.compile(
    r"Illustrations?\s*\.?\s*\n(.+?)(?=\n(?:\d{1,3}[A-Z]{0,2}\.\s|Explanation|Exception|CHAPTER|$))",
    re.DOTALL,
)
EXPLANATION_RE = re.compile(
    rf"Explanation(?:\s+\d+)?\s*\.?\s*{DASH_CLASS}(.+?)(?=\n(?:Explanation\b|Exception\b|Illustration\b|\d{{1,3}}[A-Z]{{0,2}}\.\s|CHAPTER\b|$))",
    re.DOTALL,
)
EXCEPTION_RE = re.compile(
    rf"Exception(?:\s+\d+)?\s*\.?\s*{DASH_CLASS}(.+?)(?=\n(?:Exception\b|Explanation\b|Illustration\b|\d{{1,3}}[A-Z]{{0,2}}\.\s|CHAPTER\b|$))",
    re.DOTALL,
)


@dataclass
class SectionRecord:
    id: str
    act: str
    section_number: str
    section_title: str
    chapter_number: str | None
    chapter_title: str | None
    full_text: str
    sub_clauses: list[dict] = field(default_factory=list)
    illustrations: list[str] = field(default_factory=list)
    explanations: list[str] = field(default_factory=list)
    exceptions: list[str] = field(default_factory=list)
    cross_references: list[str] = field(default_factory=list)
    source_page_start: int | None = None
    source_page_end: int | None = None
    cognizable: bool | None = None
    bailable: bool | None = None
    triable_by: str | None = None
    compoundable: bool | None = None
    punishment: str | None = None


# Footnote block starts after a run of at least 40 spaces (the PDF separator
# line renders as whitespace) followed by "\n1. " or similar. The pattern
# captures up to end of page.
FOOTNOTE_BLOCK_RE = re.compile(
    r"\n[ \t]{20,}\n\s*1\.\s.+",
    re.DOTALL,
)


def extract_body_pages(pdf_path: Path, act_header: str) -> tuple[str, list[tuple[int, int]]]:
    doc = fitz.open(pdf_path)
    body_start_pg = _find_body_start(doc, act_header)
    offsets: list[tuple[int, int]] = []
    chunks: list[str] = []
    cursor = 0
    for pg in range(body_start_pg, len(doc)):
        text = doc[pg].get_text()
        # Strip per-page footnote block to prevent footnote "1. Subs. ..."
        # entries from being mistaken for sections.
        text = FOOTNOTE_BLOCK_RE.sub("\n", text)
        offsets.append((pg + 1, cursor))
        chunks.append(text)
        cursor += len(text)
    doc.close()
    return "".join(chunks), offsets


def _find_body_start(doc: fitz.Document, act_header: str) -> int:
    header_seen = 0
    for pg in range(len(doc)):
        text_upper = doc[pg].get_text().upper()
        if act_header in text_upper:
            header_seen += 1
            if "ACT NO." in text_upper and header_seen >= 2:
                return pg
    for pg in range(len(doc)):
        if "ACT NO." in doc[pg].get_text().upper() and pg > 3:
            return pg
    return 0


def _char_to_page(offsets: list[tuple[int, int]], char_idx: int) -> int:
    pg = offsets[0][0]
    for pn, start in offsets:
        if start <= char_idx:
            pg = pn
        else:
            break
    return pg


def _find_chapters(body: str) -> list[tuple[int, str, str]]:
    return [
        (m.start(), m.group(1), m.group(2).strip())
        for m in CHAPTER_RE.finditer(body)
    ]


def split_sections(body: str, offsets: list[tuple[int, int]], act: str) -> list[SectionRecord]:
    chapters = _find_chapters(body)

    def chapter_at(offset: int) -> tuple[str | None, str | None]:
        current: tuple[str, str] | None = None
        for start, num, title in chapters:
            if start <= offset:
                current = (num, title)
            else:
                break
        return current if current else (None, None)

    # Step 1: collect all candidate section starts with their title extraction
    candidates: list[tuple[str, str, int, int]] = []  # (num, title, start, title_end)
    for m in SECTION_HEAD_RE.finditer(body):
        num = m.group("num")
        has_immediate_dash = m.group("immediate_dash") is not None
        after = m.end()
        window = body[after:after + 600]
        dash_m = re.search(DASH_CLASS, window)
        if dash_m:
            title_raw = window[:dash_m.start()]
            title = title_raw.rstrip().rstrip(".").strip()
            title_end = after + dash_m.start()
            # Handle "255.\u2014Title.\u2014Body" (empty title before 1st dash)
            if not title and has_immediate_dash:
                next_window = body[after + dash_m.end():after + 600]
                dash2 = re.search(DASH_CLASS, next_window)
                if dash2:
                    title = next_window[:dash2.start()].rstrip().rstrip(".").strip()
                    title_end = after + dash_m.end() + dash2.start()
        else:
            # Repealed or bracketed short section (e.g. "15. [Definition ...] Rep. by X")
            # Take a reasonable title window: up to first period ending a clause
            short_m = re.search(r"^([^\n]{1,250}?\.)", window)
            title = (short_m.group(1) if short_m else window[:120]).strip().rstrip(".").strip()
            title_end = after + (short_m.end() if short_m else 120)
        # Skip footnote-style "1. <lowercase>" that is clearly not a section
        if title and title[0].islower():
            continue
        candidates.append((num, title, m.start(), title_end))

    if not candidates:
        raise RuntimeError(f"No sections found for act={act}")

    # Step 2: filter out footnote references.
    # IPC/BNS PDFs include numbered footnotes at page bottoms that look
    # syntactically identical to sections. Distinguishing features:
    #   - Footnote titles often start with abbreviations ("Ins.", "Subs.",
    #     "Omitted", "Cl.", "S.", "The words", "Repl.", "Added", "Repealed",
    #     "Subs", "Sec.")
    #   - Section numbers ALWAYS appear in ascending order (including letter
    #     subsections like 120A > 120); footnote numbers do not.
    FOOTNOTE_PREFIXES = (
        "Ins.", "Subs.", "Omitted", "Cl.", "S.", "Sec.", "The words",
        "The word", "Repl.", "Added", "Repealed", "Subs", "Rep.",
    )

    def sec_key(num: str) -> tuple[int, str]:
        m = re.match(r"(\d+)([A-Z]*)", num)
        return (int(m.group(1)), m.group(2) or "")

    prev_key: tuple[int, str] = (0, "")
    ordered: list[tuple[str, str, int, int]] = []
    seen_nums: set[str] = set()
    for cand in candidates:
        num, title, start, title_end = cand
        if num in seen_nums:
            continue
        if title.startswith(FOOTNOTE_PREFIXES):
            continue
        key = sec_key(num)
        # Accept only if strictly greater than previous accepted section
        if key <= prev_key:
            continue
        ordered.append(cand)
        seen_nums.add(num)
        prev_key = key

    # Step 3: compute full_text spans (from start to next section's start)
    records: list[SectionRecord] = []
    for i, (num, title, start, title_end) in enumerate(ordered):
        end = ordered[i + 1][2] if i + 1 < len(ordered) else len(body)
        full_text = body[start:end].rstrip()
        chap_num, chap_title = chapter_at(start)
        # Collapse internal newlines in title for a clean title field,
        # but preserve in full_text
        clean_title = " ".join(title.split())
        rec = SectionRecord(
            id=f"{act}_{num}",
            act=act,
            section_number=num,
            section_title=clean_title,
            chapter_number=chap_num,
            chapter_title=chap_title,
            full_text=full_text,
            source_page_start=_char_to_page(offsets, start),
            source_page_end=_char_to_page(offsets, end),
        )
        _enrich_subcomponents(rec)
        # Sub-clause structural decomposition (ADR-D15).
        rec.sub_clauses = subclauses_to_jsonable(
            parse_subclauses(rec.id, rec.section_number, rec.full_text)
        )
        records.append(rec)

    return records


def _enrich_subcomponents(rec: SectionRecord) -> None:
    body = rec.full_text
    # Strip the header span so sub-regex patterns don't trip on the section
    # title itself. Header = from section-number up to first dash.
    header_m = re.match(
        rf"\s*{re.escape(rec.section_number)}\.\s*{DASH_CLASS}?.*?{DASH_CLASS}",
        body,
        re.DOTALL,
    )
    if header_m:
        body = body[header_m.end():]

    for m in EXPLANATION_RE.finditer(body):
        rec.explanations.append(m.group(0).strip())
    for m in EXCEPTION_RE.finditer(body):
        rec.exceptions.append(m.group(0).strip())
    for m in ILLUSTRATION_BLOCK_RE.finditer(body):
        block = m.group(1)
        items = re.split(r"\n\s*\((?:[a-z]{1,2}|\d+)\)\s+", block)
        items = [it.strip() for it in items if it.strip()]
        rec.illustrations.extend(items)

    xrefs: set[str] = set()
    for m in re.finditer(r"sections?\s+(\d{1,3}[A-Z]{0,2})", body):
        xrefs.add(m.group(1))
    rec.cross_references = sorted(xrefs, key=lambda x: (int(re.match(r"(\d+)", x).group(1)), x))


def process(pdf: Path, act: str, act_header: str, out_path: Path) -> dict:
    body, offsets = extract_body_pages(pdf, act_header)
    (out_path.with_suffix(".body.txt")).write_text(body, encoding="utf-8")

    records = split_sections(body, offsets, act)

    with out_path.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")

    total_body_chars = len(body)
    total_section_chars = sum(len(r.full_text) for r in records)
    coverage = total_section_chars / total_body_chars if total_body_chars else 0

    section_numbers = [r.section_number for r in records]
    sub_clause_total = sum(len(r.sub_clauses) for r in records)
    sections_with_subclauses = sum(1 for r in records if r.sub_clauses)
    return {
        "act": act,
        "sections": len(records),
        "total_body_chars": total_body_chars,
        "total_section_chars": total_section_chars,
        "coverage_ratio": round(coverage, 4),
        "first_section": records[0].section_number if records else None,
        "last_section": records[-1].section_number if records else None,
        "section_numbers_sample": section_numbers[:10] + ["..."] + section_numbers[-10:],
        "sub_clauses_total": sub_clause_total,
        "sections_with_sub_clauses": sections_with_subclauses,
    }


def main() -> None:
    report: dict = {}
    report["IPC"] = process(
        IPC_PDF, "IPC", "THE INDIAN PENAL CODE", OUT_DIR / "ipc_sections.jsonl"
    )
    report["BNS"] = process(
        BNS_PDF,
        "BNS",
        "THE BHARATIYA NYAYA SANHITA, 2023",
        OUT_DIR / "bns_sections.jsonl",
    )
    (OUT_DIR / "extraction_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
