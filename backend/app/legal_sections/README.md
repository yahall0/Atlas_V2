# Legal Sections — IPC & BNS RAG Pipeline

## What this module is

Canonical representation of the **Indian Penal Code, 1860** and the **Bharatiya Nyaya Sanhita, 2023** extracted verbatim from official PDFs, plus the retrieval/recommendation pipeline that suggests applicable sections for a given FIR.

## Data files (`data/`)

| File | What | Count | Coverage |
|---|---|---|---|
| `ipc_sections.jsonl` | Every IPC section (1–511 + letter variants like 120A, 354A-E, 376A-F) | 585 | 99.65% of body text |
| `bns_sections.jsonl` | Every BNS section (1–358) | 358 | 99.71% of body text |
| `ipc_sections.body.txt` | Raw extracted body text (audit trail) | — | — |
| `bns_sections.body.txt` | Raw extracted body text (audit trail) | — | — |
| `extraction_report.json` | Extraction stats per act | — | — |

The 0.3% uncovered span is the act preamble and chapter headers before the first section — not section text.

### JSONL schema

```jsonc
{
  "id": "BNS_305",
  "act": "BNS",                         // "IPC" or "BNS"
  "section_number": "305",
  "section_title": "Theft in a dwelling house, or means of transportation or place of worship, etc.",
  "chapter_number": "XVII",
  "chapter_title": "OF OFFENCES AGAINST PROPERTY",
  "full_text": "305. Theft in a dwelling house ...—Whoever commits theft— (a) ... (b) ... (c) ... (d) ... (e) ... shall be punished with imprisonment ...",
  "sub_clauses": [                      // ADR-D15: addressable sub-units
    {
      "section_id": "BNS_305",
      "label": "(a)",
      "canonical_label": "(a)",
      "scheme": "alpha_lower",
      "depth": 1,
      "parent_path": [],
      "canonical_citation": "BNS 305(a)",
      "addressable_id": "BNS_305_a",
      "text": "(a) in any building, tent or vessel used as a human dwelling or used for the custody of property; or",
      "offset_start": 87,
      "offset_end": 192
    }
    /* (b) ... (e) follow */
  ],
  "illustrations": [],
  "explanations": [],
  "exceptions": [],
  "cross_references": [],
  "source_page_start": 74,
  "source_page_end": 74,
  "cognizable": null,                   // TODO: CrPC 1st Schedule enrichment
  "bailable": null,
  "triable_by": null,
  "compoundable": null,
  "punishment": null
}
```

**Sub-clause precision contract** is binding (ADR-D15). The recommender SHALL emit `canonical_citation` (e.g. `BNS 305(a)`) for every recommendation matched against an addressable sub-clause; emitting only the umbrella section is a defect. See [`docs/decisions/ADR-D15-subclause-precision.md`](../../../docs/decisions/ADR-D15-subclause-precision.md).

## Verification

Run at any time:
```
python scripts/verify_legal_sections.py
```

Current status: **PASS** (0 errors, 0 warnings). All 10 IPC + 10 BNS spot-check sections verified (murder, rape, theft, robbery, dacoity, cheating, cruelty, etc.).

## Re-extraction

The extraction is deterministic and idempotent:
```
python scripts/extract_legal_sections.py
```

The source PDFs live outside the repo at `C:/Users/HP/Desktop/RP2/{ipc sections pdf.pdf,bns sections.pdf}`. Move those into `data/source/` if you want a self-contained build.

## Pipeline status (ADR-D16)

The end-to-end recommender pipeline is implemented and exercised by `scripts/eval_recommender.py`. Status of each stage:

| Stage | Module | Status |
|---|---|---|
| Chunker | `chunker.py` | ✅ implemented; one chunk per sub-clause + header + illustrations / explanations / exceptions |
| Embedder abstraction | `embedder.py` | ✅ `TfidfEmbedder` (dev) and `Bge3Embedder` (production) |
| Retriever | `retriever.py` | ✅ `InMemoryRetriever` (dev); pgvector mirror is the Phase 2 substitution point |
| Recommender service | `recommender.py` | ✅ orchestrates retrieval → aggregation → conflict guard → borderline flagging |
| Conflict guard | `conflicts.py` | ✅ INC / REQ / OVR rule families; one-file extension surface |
| Gold standard | `data/gold_standard.jsonl` | ✅ 20 seed FIRs (status `model_generated_awaiting_sme`) |
| Eval harness | `scripts/eval_recommender.py` | ✅ top-K accuracy + sub-clause recall + over-charging rate |
| API endpoint | `routes.py` | 🟡 wiring stub — Phase 2 |
| Pgvector persistence | migration + `PgvectorRetriever` | 🟡 Phase 2 |
| Cross-encoder rerank | `reranker.py` | 🟡 Phase 2 (`BAAI/bge-reranker-v2-m3`) |

**Switching to bge-m3:** `export ATLAS_EMBEDDER=bge-m3` and ensure the model is locally available in `BGE_M3_PATH`. No code change required.

---

# RAG pipeline — implementation plan

## Goal
Given an FIR narrative (Gujarati or English), recommend all applicable IPC/BNS sections with confidence scores, evidence snippets, and borderline-case flags.

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│  FIR (Gujarati/English narrative + structured fields)          │
└──────────────┬─────────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────┐      ┌─────────────────────────┐
│  Query preparation           │      │  Act selection          │
│  - FIR narrative             │      │  occurrence_date ≥      │
│  - primary_sections          │──────▶   2024-07-01 → BNS      │
│  - stolen_property keywords  │      │  else                 → IPC │
│  - accused/complainant hints │      └─────────────────────────┘
└──────────────┬───────────────┘                │
               │                                │
               ▼                                ▼
┌────────────────────────────────────────────────────────────────┐
│  RETRIEVAL — Stage 1 (dense + sparse hybrid)                   │
│  - Embed query with BAAI/bge-m3 (multilingual, dense+sparse)   │
│  - pgvector cosine similarity over chunk embeddings            │
│  - BM25 lexical search over section titles + keywords          │
│  - Top-50 union, merged by reciprocal-rank-fusion (RRF)        │
└──────────────┬─────────────────────────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────────────────────────────┐
│  RE-RANKING — Stage 2 (cross-encoder)                          │
│  - BAAI/bge-reranker-v2-m3 scores (query, chunk) pairs         │
│  - Keep top-20                                                 │
└──────────────┬─────────────────────────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────────────────────────────┐
│  LEGAL-NLP CLASSIFIER — Stage 3 (existing module, augmented)   │
│  - backend/app/ml/legal_nlp_filter.py (MURIL + mDeBERTa NLI)   │
│  - Scoped to retrieved top-20 candidates only                  │
│  - Produces (section, probability) pairs                       │
└──────────────┬─────────────────────────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────────────────────────────┐
│  SECTION AGGREGATOR — Stage 4                                  │
│  - Combine chunk scores per section (max-pool)                 │
│  - Apply multi-label threshold (conf >= 0.4)                   │
│  - Flag borderline cases (top-2 within 10%)                    │
│  - Attach rationale: best-matching chunk + relevant FIR spans  │
└──────────────┬─────────────────────────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────────────────────────────┐
│  Recommendation output (JSON response)                         │
│  - list[{section, act, confidence, rationale,                  │
│          matching_facts, related_sections, borderline_with}]   │
│  - Persisted to chargesheet_mindmap_nodes.metadata             │
│  - Logged to audit_chain for compliance                        │
└────────────────────────────────────────────────────────────────┘
```

## Implementation steps (ordered)

### Step 1 — DB migration (new table)
Alembic migration `013_add_legal_sections_kb.py`:

```sql
CREATE TABLE legal_section_chunks (
    id UUID PRIMARY KEY,
    section_id TEXT NOT NULL,            -- "IPC_302" / "BNS_103"
    act TEXT NOT NULL,
    section_number TEXT NOT NULL,
    chunk_type TEXT NOT NULL,            -- 'header' | 'body' | 'illustration' | 'explanation' | 'exception'
    chunk_index INT NOT NULL,
    text TEXT NOT NULL,                  -- verbatim chunk text
    dense_embedding vector(1024),        -- bge-m3 dense dim
    keywords TEXT[],
    metadata JSONB,
    source_page INT,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ix_legal_section_chunks_section ON legal_section_chunks(section_id);
CREATE INDEX ix_legal_section_chunks_act ON legal_section_chunks(act);
CREATE INDEX ix_legal_section_chunks_dense ON legal_section_chunks
    USING ivfflat (dense_embedding vector_cosine_ops) WITH (lists = 100);

CREATE TABLE legal_sections (
    id TEXT PRIMARY KEY,                 -- "IPC_302"
    act TEXT NOT NULL,
    section_number TEXT NOT NULL,
    section_title TEXT,
    chapter_number TEXT,
    chapter_title TEXT,
    full_text TEXT NOT NULL,
    cognizable BOOLEAN,
    bailable BOOLEAN,
    triable_by TEXT,
    compoundable BOOLEAN,
    cross_references TEXT[],
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE UNIQUE INDEX ux_legal_sections_act_num ON legal_sections(act, section_number);
```

### Step 2 — Module skeleton
```
backend/app/legal_sections/
├── __init__.py
├── README.md                 ← this file
├── data/                     ← extracted JSONL
├── schemas.py                ← Pydantic models (SectionChunk, RecommendRequest, RecommendResponse)
├── embedder.py               ← bge-m3 wrapper (loaded once, GPU-optional)
├── chunker.py                ← section → chunks (header + body + each illustration/explanation/exception as its own chunk, linked via section_id)
├── ingest.py                 ← JSONL → DB with embeddings (idempotent, run once at deploy)
├── retrieval.py              ← hybrid dense+BM25+RRF
├── reranker.py               ← bge-reranker-v2-m3 cross-encoder
├── recommender.py            ← orchestrates retrieval → rerank → legal_nlp_filter → aggregator
├── routes.py                 ← FastAPI router
└── tests/
    ├── test_chunker.py
    ├── test_retrieval.py
    ├── test_recommender.py
    └── test_gold_standard.py
```

### Step 3 — Chunking (multi-chunk per section, parent-linked)
One section becomes N chunks:
- 1 × `header` chunk: section number + title + chapter (short, highly retrievable)
- 1 × `body` chunk: main definition/operative text where no enumeration exists
- **N × `sub_clause` chunks: one per addressable sub-clause** — each chunk is the verbatim `text` from the `sub_clauses` array (ADR-D15). The chunk metadata MUST carry `canonical_citation` and `addressable_id` so the recommender can emit them directly without re-parsing.
- K × `illustration` chunks: each illustration as its own chunk
- M × `explanation` chunks: each Explanation.— block
- L × `exception` chunks: each Exception.— block

All chunks share `section_id` so the aggregator can roll them back up to the parent section while preserving the sub-clause discriminator. Borderline cases (theft vs cheating vs criminal breach of trust) are distinguished by sub-clauses and illustrations — splitting them raises retrieval recall and is the mechanism by which sub-clause precision is achieved end-to-end.

### Step 4 — Embedding model
`BAAI/bge-m3`:
- Multilingual (supports Gujarati + English in same embedding space)
- Produces dense (1024-d), sparse (lexical), and multi-vector representations
- On-prem, CPU-capable (~200ms/chunk on CPU, batch of 64)
- Store dense in pgvector; compute sparse on-the-fly at query time
- Warm-up + cache in `backend/app/ml/` alongside MURIL

Load once at app startup (add to `backend/app/main.py` startup event).

### Step 5 — Hybrid retrieval with RRF

```python
# retrieval.py
def retrieve(query: str, act_filter: str | None, k: int = 50):
    dense_scores  = pgvector_cosine(embed(query), k=k)     # (chunk_id, score)
    sparse_scores = postgres_tsvector_bm25(query, k=k)     # (chunk_id, score)
    fused = reciprocal_rank_fusion(dense_scores, sparse_scores, k=60)
    return fused[:k]
```

RRF formula: `score = Σ 1 / (k_rrf + rank_in_source)`. Standard k_rrf=60.

### Step 6 — Re-ranking
`BAAI/bge-reranker-v2-m3` (cross-encoder, multilingual):
- Score (query, chunk_text) pairs
- Rerank top-50 → top-20
- Typical +5-10% accuracy over pure retrieval

### Step 7 — Plug existing legal_nlp_filter
Modify `backend/app/ml/legal_nlp_filter.py` to accept a **candidate scope** (list of section IDs) rather than scoring all sections globally:

```python
def classify_scoped(
    fir_text: str,
    candidate_sections: list[str],  # e.g. ["IPC_302", "IPC_201", ...]
) -> list[tuple[str, float]]:
    ...
```

This is (b) from Q5 — RAG retrieves, NLP re-ranks with domain-trained model.

### Step 8 — Aggregator
```python
# recommender.py
def recommend(fir: FIRRecord) -> list[SectionRecommendation]:
    act = decide_act(fir.occurrence_start)          # BNS if >= 2024-07-01 else IPC
    query = build_query(fir)                         # narrative + primary_act + stolen_property + …
    candidates = retrieve(query, act)                # top 50 chunks
    reranked = rerank(query, candidates)[:20]        # top 20 chunks
    section_ids = unique_section_ids(reranked)
    nlp_scores = legal_nlp_filter.classify_scoped(fir.narrative, section_ids)

    section_conf = {}
    for sid, score in nlp_scores:
        section_conf[sid] = max(section_conf.get(sid, 0), score)

    # predict every applicable section (Q11)
    recs = [r for sid, c in section_conf.items() if c >= 0.4
            for r in [build_recommendation(sid, c, fir, reranked)]]
    recs.sort(key=lambda r: -r.confidence)
    _flag_borderline(recs, pct_threshold=0.10)       # Q10
    return recs
```

### Step 9 — API endpoint

```python
# routes.py — registered in backend/app/main.py
POST /api/v1/firs/{fir_id}/recommend-sections
  → 202 Accepted if async, or 200 with RecommendationResponse

GET /api/v1/firs/{fir_id}/recommend-sections/latest
  → cached last recommendation
```

Schema (canonical — see `backend/app/legal_sections/schemas.py`):
```python
class SectionRecommendation(BaseModel):
    section_id: str              # parent, e.g. "BNS_305"
    act: Literal["IPC", "BNS"]
    section_number: str
    section_title: str
    sub_clause_label: str | None       # "(a)" / "(2)" / "Provided that" / None for umbrella
    canonical_citation: str            # "BNS 305(a)"  — court-ready, MUST be rendered verbatim
    addressable_id: str                # "BNS_305_a"   — URL-safe
    confidence: float
    rationale_quote: str               # verbatim sub-clause text (or section text if no sub-clause)
    matching_fir_facts: list[str]
    related_sections: list[str]
    borderline_with: list[str] = []
    operator_note: str | None = None
```

Per ADR-D15, the recommender SHALL emit `canonical_citation` at the smallest applicable addressable unit and the rendered IO interface SHALL display it verbatim in the chargeable list and any document export.

### Step 10 — Auto-run on FIR ingestion
Extend the NLP background task in `backend/app/api/v1/firs.py`:
- After NLP classification completes, fire `recommender.recommend(fir)`
- Persist result to `firs.nlp_metadata["recommended_sections"]`
- Generate mindmap nodes with new `node_type = "suggested_section"` via `backend/app/mindmap/generator.py`

### Step 11 — Surface in mindmap UI
In `frontend/src/components/mindmap/nodes/`:
- Add `SuggestedSectionNode.tsx`
- Display section_title + confidence badge + expandable rationale
- Accept/dismiss actions posted via existing gap-action audit endpoint

### Step 12 — Gold-standard validation set (Q12)
No reviewed FIRs currently in DB. To measure accuracy, we need a labelled set:

1. **Bootstrap (weeks 1–2):** Generate 200 synthetic FIRs using `scripts/generate_synthetic_training_data.py` (already exists), have a legal SME tag the applicable sections per FIR. Store in `backend/tests/fixtures/section_gold_standard.jsonl`.
2. **Ongoing (live):** Every chargesheet that passes IO/SHO review captures the "final confirmed sections" — use these as incremental training/validation data. Pipeline already logs reviews via `chargesheet_gap_reports`.
3. **Metrics:** top-1 accuracy, top-5 hit rate, mean confidence on correct label, borderline-flag precision.

Target: **top-5 ≥ 95%** (with IO confirmation covering the remaining 5%). Pure top-1 to 100% is not achievable without human-in-the-loop; with dual-pane review UI it's effectively achieved.

### Step 13 — Future enrichment (non-blocking)
- **CrPC First Schedule lookup**: fills `cognizable / bailable / triable_by / compoundable` fields. Needs the official CrPC/BNSS First Schedule PDF.
- **IPC↔BNS cross-mapping**: official MHA mapping document maps old IPC sections to new BNS sections. Enables dual-act suggestions.
- **Special acts** (NDPS, POCSO, IT Act, MV Act, Dowry Prohibition, Arms Act): same pipeline; just extend `data/` with more JSONL files. All mindmap templates already exist for these acts.

### Step 14 — Integration with existing modules
| Existing module | Change |
|---|---|
| `backend/app/main.py` | Register new `legal_sections.routes` router |
| `backend/app/ml/legal_nlp_filter.py` | Add `classify_scoped` method |
| `backend/app/api/v1/firs.py` | Auto-trigger recommender in FIR ingestion background task |
| `backend/app/mindmap/generator.py` | Emit `suggested_section` nodes |
| `backend/app/audit_chain.py` | Log SECTION_RECOMMENDED / SECTION_ACCEPTED / SECTION_DISMISSED actions |

### Step 15 — Rollout
1. Dev: migration → ingest all JSONL → compute embeddings → run tests on gold set
2. Staging: shadow-mode against 50 recent FIRs; compare recommendations to IO-confirmed sections
3. Prod: enable as second-opinion in dual-pane review UI (user can dismiss/accept per recommendation)

## Known limitations (honest list)

- **100% accuracy is a guideline, not a guarantee.** Legal section classification has inherent ambiguity (classic theft-vs-CBoT-vs-cheating borderlines) and expert lawyers disagree. The system aims for top-5 ≥ 95% with IO final confirmation.
- **State amendments** (e.g. IPC 382B-F Gujarat snatching sections) have non-standard formatting in the PDF — titles are imperfect but full_text is complete.
- **CrPC/BNSS First Schedule fields** (cognizable/bailable/triable) are null until enriched.
- **IPC↔BNS mapping** is not yet built; act is selected by date, not by cross-reference.
- **Special acts** (NDPS, POCSO etc.) not yet ingested.
- **Reviewer calibration**: embeddings quantify semantic similarity, not legal doctrine. A law clerk / SME needs to review initial recommendations on ~50 real FIRs before production rollout.
