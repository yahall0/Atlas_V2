# ADR-D02: NLP Model Selection for FIR Classification

**Status:** Accepted  
**Date:** 2026-04-08  
**Deciders:** Amit (Lead), Aditya (Backend/ML), Prishav (Frontend/NLP)  
**Sprint Gate:** Sprint 2

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

- [ ] `ATLASClassifier` successfully loads `ai4bharat/indic-bert` tokeniser at startup.
- [ ] `POST /predict/classify` returns `method: "heuristic"` responses for all 11 categories.
- [ ] `app/ml/train.py --dry_run` passes without error.
- [ ] Model variant visible via `GET /predict/model-info`.
