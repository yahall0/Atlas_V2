# ADR-D02: NLP Model Selection for FIR Classification

**Status:** Amended (see Sprint 4 update below)  
**Date:** 2026-04-08 | **Amended:** 2026-04-09  
**Deciders:** Amit (Lead), Aditya (Backend/ML), Prishav (Frontend/NLP)  
**Sprint Gate:** Sprint 2 → Sprint 4

## Context

The ATLAS Platform must classify First Information Reports (FIRs) written in Gujarati, Hindi, and English into one of eleven ATLAS crime categories (BNS-aligned). Constraints include:

- **Privacy:** No data may leave Gujarat Police on-premise infrastructure — cloud model APIs (OpenAI, Google Cloud NLP) are prohibited.
- **Languages:** eGujCop FIRs contain native Gujarati script, Roman-transliterated Gujarati, Hindi, and code-mixed text.
- **Hardware:** Local GPU available at district hub servers; model must fit in ≤ 12 GB VRAM.
- **Team capacity:** 2-person team; model must be fine-tune-able without MLOps infrastructure beyond HuggingFace + MLflow.
- **Dataset:** ~200 manually-annotated gold standard FIRs available for Sprint 2; target for fine-tuning is 500 labelled examples.

## Candidates Evaluated

| Model | Params | Gujarati support | On-prem | Notes |
|---|---|---|---|---|
| IndicBERT (ai4bharat/indic-bert) | 110M | ✅ native | ✅ | Trained on 12 Indic scripts incl. Gujarati |
| MuRIL (google/muril-base-cased) | 237M | ✅ native | ✅ | Google; strong multilingual |
| XLM-RoBERTa-base | 270M | ⚠ partial | ✅ | Limited Gujarati coverage |
| mBERT | 110M | ⚠ partial | ✅ | Older; weaker Indic performance |
| Sarvam-2B | 2B | ✅ | ✅ | Too large for classification; reserved for SOP |

## Decision

**Selected: `ai4bharat/indic-bert` (IndicBERT)**

Rationale:
1. Smallest model (110M) with native Gujarati pretraining.
2. Fits comfortably in 4 GB VRAM — leaves headroom for Sarvam-30B on same server.
3. HuggingFace `AutoModelForSequenceClassification` API — standard fine-tuning pipeline with `Trainer`.
4. Sprint 2 operates in **heuristic-fallback mode** (keyword matching) while annotation corpus is built; fine-tuned checkpoint introduced in Sprint 3.

## Consequences

### Positive
- Lightweight inference; classification P99 latency < 200 ms on CPU.
- Standard HuggingFace Trainer API — no bespoke training infrastructure.
- Active upstream (AI4Bharat) — model improvements available.

### Negative / Risks
- IndicBERT base model has ~110M parameters; may underfit on small datasets. Mitigate: data augmentation, class weighting.
- Sprint 2 heuristic fallback has ~65% accuracy — acceptable scaffold but must reach ≥ 80% F1 by Sprint 3 gate.

## Sprint 2 Acceptance Criteria

- [x] `ATLASClassifier` successfully loads `ai4bharat/indic-bert` tokeniser at startup.
- [x] `POST /predict/classify` returns `method: "heuristic"` responses for all 11 categories.
- [x] `app/ml/train.py --dry_run` passes without error.
- [x] Model variant visible via `GET /predict/model-info`.

---

## Sprint 4 Amendment — Classification Architecture Overhaul (2026-04-09)

### Motivation

The Sprint 3 fine-tuned MuRIL checkpoint (264 samples, macro-F1 = 0.41) exhibited
**mode collapse**: 5 of 11 classes were never predicted, and the model defaulted to
`rape_sexoff` for all inputs (confidence ≈ 9% ≈ 1/11 random chance). Root causes:

1. **Insufficient data**: 264 samples across 11 classes (≈ 24/class after split) is far
   below the 500–1000/class minimum needed to fine-tune a 110 M-parameter model.
2. **Synthetic training data**: Machine-generated FIRs do not reproduce the linguistic
   complexity of real eGujCop documents.
3. **Dataset access blocked**: Bureaucratic hurdles prevent access to labelled real FIRs.

### New Classification Hierarchy

Classification is now a **four-tier priority cascade**:

| Priority | Source | Trigger | Method field |
|---|---|---|---|
| 1 | `section_map.py` | Registered BNS/IPC sections present | `section_map` |
| 2 | Fine-tuned MuRIL | Checkpoint present AND `confidence ≥ 0.25` | `model` |
| 3 | Zero-shot NLI | Any text without reliable model prediction | `zero_shot` |
| 4 | Keyword heuristics | All else fails | `heuristic` |

**Sections are ground truth**: when the FIR has registered BNS/IPC sections the
`section_map` result is stored as `nlp_classification` with `confidence = 1.0`.
NLP methods are only invoked when no sections are registered.

### Changes Made

#### `backend/app/nlp/section_map.py` (new)
- Deterministic mapping of BNS 2023 and IPC section numbers to ATLAS categories.
- Sub-clause suffixes (`(a)`, `(4)`, `[1]`) are stripped before lookup so `305(a)`
  correctly resolves to `305 → theft`.
- Priority tiebreak when multiple sections map to different categories:
  `murder > rape_sexoff > dacoity_robbery > kidnapping > domestic_violence > assault
  > fraud > narcotics > cybercrime > theft`.

#### `backend/app/nlp/zero_shot.py` (new)
- Uses `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli` (~270 MB, multilingual NLI).
- No training data required — classifies via natural-language hypotheses.
- Candidate labels are bilingual (English + Gujarati) for cross-lingual transfer.
- Input truncated to 600 chars (`ZERO_SHOT_MAX_CHARS`) to bound CPU inference time.
- Inference runs in `asyncio.run_in_executor` to avoid blocking the uvicorn event loop.
- Configurable via `ZERO_SHOT_MODEL` and `ZERO_SHOT_THRESHOLD` env vars.

#### `backend/app/nlp/classify.py` (amended)
- Added `_MODEL_CONFIDENCE_THRESHOLD = 0.25` (env: `NLP_CONFIDENCE_THRESHOLD`).
  Model predictions below this threshold are discarded and zero-shot is tried instead.
- Zero-shot is now the second fallback in the chain, before keyword heuristics.

#### `backend/app/api/v1/ingest.py` (amended)
- `section_map.infer_category_from_sections()` called first on every ingest.
- If section_map returns a result: stored as `nlp_classification`, `nlp_classified_by = "section_map"`, `confidence = 1.0`.
- If section_map returns `None`: NLP cascade runs in a thread executor.
- `nlp_metadata` now stores both `section_inferred_category` and `nlp_category` for mismatch audit display in the FIR review UI.

### Model Size Comparison

| Model | Size | Requires training data | Gujarati support |
|---|---|---|---|
| MuRIL fine-tuned (Sprint 3) | 953 MB | Yes (264 samples, F1=0.41) | ✅ native |
| mDeBERTa-v3 zero-shot (Sprint 4) | ~270 MB | **No** | ✅ 100+ languages |

### Path to Improvement

Once labelled real FIRs become available (≥ 500/class):
1. Retrain MuRIL checkpoint — expected F1 > 0.75 at 500 samples/class.
2. Raise `NLP_CONFIDENCE_THRESHOLD` so model takes precedence over zero-shot.
3. Consider TF-IDF + LogisticRegression as a lightweight alternative at < 1000 samples.

