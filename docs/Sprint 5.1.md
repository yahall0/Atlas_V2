# Sprint 5.1

## Scope

This sprint focused on improving charge-sheet robustness and evidence gap analysis without introducing heavy local model requirements or changing frontend contracts.

## What Changed

### 1. Charge-sheet parsing was upgraded to a hybrid parser

- The parser now combines anchor-based extraction with block-oriented section parsing.
- It is more tolerant of noisy OCR, reordered sections, and mixed layouts.
- It extracts accused, charges, evidence, and witnesses using section blocks first and then falls back to broader line scanning when needed.
- Gujarati numeral normalization remains supported.

### 2. Parser metadata was added for reviewability

- `document_family` identifies the rough document style.
- `extraction_strategy` records which parser family produced the result.
- `field_confidence` gives lightweight confidence estimates per extracted field.
- `field_sources` records whether values came from header anchors, section blocks, or fallback scans.
- `quality_flags` highlights likely weak parses such as missing FIR reference, missing accused list, or low OCR text volume.

These additions are additive and do not change the existing API fields used by the frontend.

### 3. Evidence gap analysis now includes a lightweight semantic recovery tier

- The existing rule-based gap detection remains the primary legal baseline.
- A new semantic recovery layer checks raw text, witness summaries, and extracted evidence descriptions for likely evidence mentions that strict keyword classification may miss.
- This semantic layer uses compact TF-IDF similarity over curated evidence phrases, which is much lighter than running a large local LLM.
- It helps reduce false gap reports for varied charge-sheet formats and non-standard evidence wording such as bank transaction records or WhatsApp chat exports.
- The trained scikit-learn ML tier remains available for non-blocking suggestion-style gaps.

### 4. Backend startup was made more resilient

- FIR classification no longer hard-fails if `mlflow` is not installed.
- MLflow logging is now treated as optional so the backend and tests can still run in lighter environments.

## Files Updated

- `backend/app/ingestion/chargesheet_parser.py`
- `backend/app/ml/evidence_gap_model.py`
- `backend/app/nlp/classify.py`
- `backend/tests/test_chargesheet.py`
- `backend/tests/test_evidence_gap.py`

## Validation

Focused backend tests were run successfully:

- `backend/tests/test_chargesheet.py`
- `backend/tests/test_evidence_gap.py`
- `backend/tests/test_legal_validator.py`

At the end of the implementation, the targeted suite passed successfully.

## Notes

- No frontend API route or existing response contract was intentionally broken.
- The new semantic layer is CPU-friendly and intended for modest hardware.
- This is still a hybrid system, not a fully learned document understanding pipeline. It is more flexible than the previous rules-only behavior, but it is not yet equivalent to a full document VLM or hosted LLM workflow.
