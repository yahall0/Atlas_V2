# ADR-D06: Multilingual Pipeline for Gujarati FIR Processing

**Status:** Accepted  
**Date:** 2026-04-08  
**Deciders:** Amit (Lead), Aditya (Backend/ML), Prishav (Frontend/NLP)  
**Sprint Gate:** Sprint 2

## Context

Gujarat Police FIRs present a complex multilingual landscape:

1. **Native Gujarati script** — standard form in eGujCop system.
2. **Romanised Gujarati** — phonetically spelled Gujarati using Latin alphabet; common in handwritten/dictated narratives.
3. **Hindi** — sections of FIR referencing IPC/BNS provision names.
4. **English** — legal terminology, officer designations, place names.
5. **Code-mixed** — single sentence mixing all four above.

Any NLP pipeline must handle all variants reliably without expensive per-language branching.

## Decision

A **three-stage preprocessing pipeline** is adopted:

### Stage 1 — Normalisation (`app.nlp.language.normalise_text`)
- Apply Unicode NFC normalisation.
- Strip leading/trailing whitespace.
- Rationale: OCR output from Tesseract often contains decomposed Unicode characters that break tokenisation.

### Stage 2 — Language Detection (`app.nlp.language.detect_language`)
- **Tool:** fastText lid.176.bin (176-language model, 126 MB).
- Detects script/language at the document level.
- Result stored in `firs.nlp_metadata.detected_lang` JSONB column for audit.
- **Fallback:** If model file absent (CI/test environments), returns `"unknown"` — pipeline continues without language gating.

### Stage 3 — Transliteration (optional, `app.nlp.language.transliterate_romanised_gujarati`)
- **Tool:** IndicXlit (`xlit==1.2`) with `src_script="en"` and `lang_code="gu"`.
- Applied only when `transliterate=True` is passed in `POST /predict/classify`.
- Converts Romanised Gujarati (`amdavad`, `fariyadi`) to native script (`અમદાવાદ`, `ફરિયાદી`) before tokenisation.
- **Rationale:** IndicBERT vocabulary is Gujarati-script-optimised; native-script input improves classification.

### IndicNLP Sentence Tokenisation (`app.nlp.preprocessing.IndicBERTPreprocessor.split_sentences`)
- **Tool:** `indicnlp.tokenize.sentence_tokenize`.
- Falls back to period-split if indic-nlp-library is absent.
- Used during fine-tuning to create per-sentence training examples from long narratives.

### IndicBERT Tokenisation (`app.nlp.preprocessing.IndicBERTPreprocessor.tokenize`)
- HuggingFace `AutoTokenizer` for `ai4bharat/indic-bert`.
- `max_length=512`, `truncation=True`, `padding="max_length"`.
- `truncate_to_fit()` method pre-truncates narratives > 512 tokens before inference.

## Pipeline Diagram

```
Raw FIR text (Gujarati / Roman / Hindi / English / mixed)
        │
        ▼
normalise_text()        ← NFC + strip
        │
        ▼
detect_language()       ← fastText lid.176.bin
        │
        ├── if transliterate=True
        │        ▼
        │   transliterate_romanised_gujarati()   ← IndicXlit
        │
        ▼
split_sentences()       ← IndicNLP (or fallback)
        │
        ▼
tokenize()              ← IndicBERT AutoTokenizer (max 512)
        │
        ▼
ATLASClassifier.classify()  ← heuristic (Sprint 2) / fine-tuned checkpoint (Sprint 3+)
        │
        ▼
POST /predict/classify response
```

## Consequences

### Positive
- Graceful degradation at every stage: missing model files do not crash the server.
- fastText provides sub-100 ms language detection (CPU).
- IndicXlit improves classification accuracy for Roman-transliterated Gujarati inputs.

### Negative / Risks
- fastText `lid.176.bin` is 126 MB — gitignored; must be downloaded or mounted separately in Docker. Documented in README.
- IndicNLP sentence tokeniser does not handle code-mixed sentences perfectly; acceptable for Sprint 2.
- IndicBERT 512-token limit truncates very long narratives (> 4 pages); `truncate_to_fit()` mitigates silently dropping content.

## Sprint 2 Acceptance Criteria

- [ ] `preprocess_text("ફરિયાદી ઘરે ચોરી", detected_lang="gu")` returns `{"normalised": ..., "detected_lang": "gu", "transliterated": None}` without error.
- [ ] `transliterate_romanised_gujarati("amdavad")` returns a non-empty string (or the original if xlit unavailable).
- [ ] `IndicBERTPreprocessor().tokenize("test text")` returns a dict with `input_ids` key (or `None` if model unavailable).
- [ ] `POST /predict/classify` with `transliterate=true` in request body succeeds without error.
