# ATLAS Deliberation Session Prompts — D01 through D12

**Project:** ATLAS (Advanced Technology for Law-enforcement Analytics & Surveillance)
**Prepared by:** ATLAS Decision Architecture Facilitator
**Date:** 2 April 2026
**Governing Standard:** Agile Sprint Planning (Lecture 9, §3.1) + Architecture Decision Record (ADR) Standard
**Team:** Amit (Lead/Facilitator) · Prishiv (Backend/ML/DevOps) · Aditya (Frontend/Data/NLP)

---

## HOW TO USE THIS DOCUMENT

Each D-Prompt below is a **self-contained facilitation script**. Amit opens the session by reading the PROBLEM FRAMING section aloud, then follows the timed agenda. Every session must end with a signed ADR committed to the wiki. If the team cannot reach consensus within the timebox, Amit exercises the casting vote and records the dissenting rationale in the ADR's "Consequences" section.

**Pre-session checklist (all items):**
- [ ] Room/call booked with screen-sharing capability
- [ ] Pre-read materials distributed ≥ 24 hours before session
- [ ] Claude.ai open in a shared browser tab for live research queries
- [ ] ADR template pre-loaded in the wiki editor
- [ ] Jira board visible for real-time ticket creation

---
---

# D01-PROMPT — Architecture ADR: Modular Monolith vs. Microservices

**STORE AT:** `/atlas-project/docs/decisions/ADR-D01-system-architecture.md`
**Sprint Gate:** Sprint 1 — No development begins until this ADR is signed.

---

### ROLE ASSIGNMENTS

| Role | Person | Responsibility |
|------|--------|---------------|
| Facilitator | Amit | Timekeep, frame trade-offs, casting vote if deadlocked |
| Decision-maker (Infrastructure) | Prishiv | Assess deployment complexity, CI/CD, DevOps capacity for each option |
| Decision-maker (Application) | Aditya | Assess frontend integration patterns, data pipeline coupling, NLP service boundaries |
| Research Reference | Claude.ai | On-call for real-time lookups on framework benchmarks, deployment patterns |

**Timebox:** 75 minutes

---

### PRE-READ (distribute ≥ 24 hours before)

1. R01-fir-legal-standards.md — §7.4 Recommended Pipeline Architecture (identifies five processing stages)
2. BITS Pilani capstone infrastructure policy — what cloud/on-prem resources are allocated
3. Article: "Modular Monoliths vs. Microservices for 2-Person Teams" (ThoughtWorks Technology Radar 2025)
4. eGujCop integration documentation (available portions) — API surface, data export formats
5. Team velocity baseline: estimated 40 story points/sprint across both developers

---

### SESSION AGENDA

| Time | Block | Activity | Output |
|------|-------|----------|--------|
| 0:00–0:15 | **Problem Framing** | Amit reads context below. Each team member states their #1 concern about architecture choice. | Shared understanding of constraints |
| 0:15–0:45 | **Option Analysis** | Walk through each option using the decision matrix. Prishiv presents infra view, Aditya presents app view. | Scored matrix on whiteboard/screen |
| 0:45–1:00 | **Trade-off Discussion** | Identify the "regret minimisation" scenario: which choice hurts most if wrong at Sprint 6? | Ranked risk register (top 3 risks per option) |
| 1:00–1:10 | **Decision** | Amit calls for consensus. If split, Amit casts and documents. | Verbal commitment recorded |
| 1:10–1:15 | **ADR Draft** | Amit screen-shares ADR template; team fills in real-time. | ADR-D01 committed to wiki |

---

### PROBLEM FRAMING (Amit reads aloud)

> "We are a 2-developer team building a system that must ingest FIR data from eGujCop, run NLP classification across Gujarati and English text, serve a role-based dashboard, and eventually integrate with 3+ external government systems — ICJS, e-Prison, and NCRB-CCTNS. We have 8 sprints to reach MVP.
>
> The architecture decision made today determines whether we build a single deployable unit with well-defined internal module boundaries (modular monolith) or decompose into independently deployable services from Day 1 (microservices). This is a one-way door at Sprint 1 — reversing at Sprint 5 would cost 2+ sprints of rework.
>
> Our binding constraints are: (a) 2 developers total, (b) likely deployment on Gujarat State Data Centre infrastructure or NIC cloud (not AWS/GCP managed Kubernetes), (c) compliance requirements for data residency within Indian government infrastructure, (d) the system must handle multilingual NLP which is compute-intensive."

**Prompt each team member:** "In one sentence, what is the single biggest risk you see in making the wrong architecture choice?"

---

### DECISION OPTIONS

#### Option A: Modular Monolith (Django/FastAPI single deployment)

**Description:** Single deployable application with strict internal module boundaries (ingestion module, NLP module, analytics module, dashboard module, auth module). Modules communicate via in-process function calls and a shared database with schema-per-module isolation. Deploy as a single container or systemd service.

**Pros specific to ATLAS:**
- 2-developer team can debug, deploy, and monitor a single application without orchestration overhead
- No inter-service network latency for NLP pipeline calls (ingestion → preprocessing → classification happens in-process)
- Single database simplifies FIR data consistency — no distributed transaction problem when linking FIR records to NLP outputs
- Deployable on basic VM infrastructure at Gujarat State Data Centre without requiring Kubernetes or Docker Swarm
- Faster Sprint 1–3 velocity: no time spent on service discovery, API gateway, or inter-service auth
- Can extract modules into services later if scale demands it (monolith-first pattern)

**Cons specific to ATLAS:**
- NLP model inference (potentially GPU-bound) shares resources with the web server; a heavy classification batch could degrade dashboard responsiveness
- If Prishiv and Aditya are working on tightly coupled modules, merge conflicts increase
- Scaling the NLP component independently is not possible without extracting it later
- Testing requires spinning up the entire application even for module-specific tests

**Risk if wrong:** At Sprint 6, if NLP inference load requires GPU scaling independent of the web tier, extracting the NLP module into a separate service will cost ~1 sprint of refactoring.

#### Option B: Microservices (3–4 independent services from Day 1)

**Description:** Decompose into: (1) API Gateway + Auth Service, (2) Data Ingestion Service, (3) NLP/ML Processing Service, (4) Dashboard/Frontend Service. Each deployed independently, communicating via REST/gRPC and a message queue (RabbitMQ/Redis Streams).

**Pros specific to ATLAS:**
- NLP service can be deployed on a GPU node independently while dashboard runs on a standard VM
- Clear ownership: Prishiv owns Services 1–3, Aditya owns Service 4 — minimal merge conflicts
- Each service can use the best-fit technology (Python+PyTorch for NLP, Node/React for dashboard)
- Independent scaling and failure isolation

**Cons specific to ATLAS:**
- 2-developer team will spend 25–35% of Sprint 1–2 on infrastructure scaffolding (Docker Compose, service discovery, API contracts, health checks) rather than feature development
- Distributed debugging is significantly harder — a failed FIR classification requires tracing across 3 services
- Gujarat State Data Centre may not support container orchestration; deployment complexity increases
- Inter-service communication adds latency and failure modes to the NLP pipeline
- Message queue adds an operational dependency that neither developer has spare capacity to babysit
- Overkill for current data volumes (Gujarat processes ~2–3 lakh FIRs/year; well within single-service capacity)

**Risk if wrong:** Sprint 1–3 velocity drops by 30–40% due to infrastructure overhead, pushing MVP past Sprint 8. Team burns out on plumbing instead of features.

#### Option C: Modular Monolith with NLP Worker Extraction (Hybrid)

**Description:** Start as a modular monolith (Option A) but design the NLP module with a clean async interface from Day 1 (Celery/RQ task queue). The NLP worker can be run in-process during development and extracted to a separate deployment unit at Sprint 4–5 if GPU scaling is needed.

**Pros specific to ATLAS:**
- Gets the velocity benefit of Option A in Sprint 1–3
- The async boundary means NLP inference doesn't block the web server even in monolith mode
- Extraction to a separate worker is a deployment change, not a code refactor
- Prishiv can manage the worker extraction as a DevOps task without touching Aditya's frontend code

**Cons specific to ATLAS:**
- Requires disciplined interface design for the NLP module from Sprint 1 (risk of shortcuts under time pressure)
- Celery/RQ adds a Redis dependency even in monolith mode
- Not a "true" microservice — won't satisfy reviewers who expect microservices architecture (if applicable)

**Risk if wrong:** If the team takes shortcuts on the async interface under Sprint 1–3 time pressure, the "clean extraction" at Sprint 5 becomes a messy refactor anyway.

---

### DECISION CRITERIA (weight these during the session)

| Criterion | Weight | Description |
|-----------|--------|-------------|
| Sprint 1–3 Velocity Impact | 30% | Which option lets us ship the most features in the first 3 sprints? |
| Team Capacity Fit | 25% | Which option is realistic for a 2-developer team with no dedicated DevOps? |
| Deployment Environment Compatibility | 20% | Which option works on Gujarat State Data Centre / NIC infrastructure? |
| Scaling Headroom | 15% | Which option handles 10× data growth without re-architecture? |
| Reversibility | 10% | Which option is easiest to change if we're wrong at Sprint 6? |

---

### ADR TEMPLATE

```markdown
# ADR-D01: System Architecture Pattern

**Status:** [Proposed | Accepted | Superseded]
**Date:** [Session date]
**Deciders:** Amit (Lead), Prishiv (Backend/ML/DevOps), Aditya (Frontend/Data/NLP)

## Context
ATLAS is a 2-developer, 8-sprint project deploying on Indian government infrastructure.
The system requires FIR data ingestion, multilingual NLP processing, role-based dashboards,
and integration with 3+ external government systems. [Additional context from session.]

## Decision
We will adopt **[Option A / B / C]** because [rationale from weighted criteria scoring].

## Consequences
### Positive
- [List from session discussion]

### Negative
- [List from session discussion]

### Risks Accepted
- [Specific risks the team is consciously accepting]

## Dissent (if any)
[Name] preferred [alternative] because [rationale]. This was overruled because [reason].

## Review Trigger
This ADR will be reviewed at Sprint [N] if [condition].

## Sign-off
- [ ] Amit (Lead) — Date: ___
- [ ] Prishiv — Date: ___
- [ ] Aditya — Date: ___
```

---

### DONE WHEN

- [ ] ADR-D01 drafted in session and all three members have signed off
- [ ] ADR committed to `/atlas-project/docs/decisions/ADR-D01-system-architecture.md`
- [ ] Jira epic "ATLAS-ARCH" created with sub-tasks reflecting the chosen architecture
- [ ] Sprint 1 backlog items updated to align with architecture decision
- [ ] If Option C chosen: Jira spike ticket created for Sprint 4 NLP extraction assessment

### ESCALATION

If no consensus after 75 minutes, Amit has casting vote. Amit must state the deciding factor aloud, and the dissenting view must be recorded verbatim in the ADR "Dissent" section. The dissenter may request a formal review trigger (e.g., "revisit at Sprint 4 retrospective").

---
---

# D02-PROMPT — Model Selection ADR: IndicBERT vs. LLaMA-3 vs. GPT-4o vs. Mistral-7B

**STORE AT:** `/atlas-project/docs/decisions/ADR-D02-model-selection.md`
**Sprint Gate:** Sprint 2 — NLP pipeline design depends on this decision.

---

### ROLE ASSIGNMENTS

| Role | Person | Responsibility |
|------|--------|---------------|
| Facilitator | Amit | Timekeep, frame compliance constraints, casting vote |
| Decision-maker (ML/Infra) | Prishiv | Assess inference costs, GPU requirements, fine-tuning feasibility |
| Decision-maker (NLP/Data) | Aditya | Assess Gujarati language performance, annotation pipeline fit, output quality |
| Research Reference | Claude.ai | On-call for benchmark lookups, Gujarati NLP corpus availability, licensing terms |

**Timebox:** 90 minutes (this is the most technically complex decision)

---

### PRE-READ

1. R01-fir-legal-standards.md — §6 (data quality issues: Gujarati/English mixing, free-text inconsistencies)
2. IndicBERT / IndicNLP benchmark papers — Gujarati language performance on NER and classification tasks
3. LLaMA-3 model card — license terms (Meta Community License), multilingual benchmarks
4. Mistral-7B model card — Apache 2.0 license, inference requirements
5. GPT-4o API pricing sheet — per-token costs at projected ATLAS query volumes
6. Gujarat Police data residency requirements — can FIR text be sent to external APIs?
7. ATLAS NLP task inventory: (a) crime-type classification, (b) named entity recognition, (c) section number extraction, (d) MO code suggestion, (e) language detection

---

### SESSION AGENDA

| Time | Block | Activity | Output |
|------|-------|----------|--------|
| 0:00–0:15 | **Problem Framing** | Define the 5 NLP tasks. Clarify data residency constraint. Quantify expected inference volume. | Task × constraint matrix |
| 0:15–0:50 | **Option Analysis** | Walk through each model against each NLP task. Prishiv presents infra/cost view, Aditya presents quality/language view. | 4×5 scoring matrix |
| 0:50–1:10 | **Trade-off Discussion** | Data residency showstopper analysis. Fine-tuning feasibility with available labelled data. Fallback strategy if primary model underperforms on Gujarati. | Go/no-go flags per option |
| 1:10–1:20 | **Decision** | Consensus call. May decide on a tiered strategy (different models for different tasks). | Verbal commitment |
| 1:20–1:30 | **ADR Draft** | Fill ADR template in real-time. | ADR-D02 committed |

---

### PROBLEM FRAMING (Amit reads aloud)

> "Our NLP pipeline must handle five distinct tasks on FIR text that is predominantly Gujarati with English legal terminology mixed in. The text quality ranges from well-structured narratives to one-line entries. We estimate ~2–3 lakh FIRs per year in Gujarat, meaning our batch processing volume is modest, but real-time classification for new FIRs requires sub-5-second inference.
>
> The critical constraint is **data residency**: Gujarat Police FIR text is sensitive law-enforcement data. We must determine whether any of this text can be sent to external cloud APIs (GPT-4o), or whether all inference must happen on-premise. This is not a technical question — it is a compliance question that Amit must validate with the Gujarat Police IT Cell.
>
> Secondary constraint: our labelled training data is currently zero. Whatever model we choose, we must either (a) fine-tune it on annotated FIR data we create ourselves, or (b) use it in a zero-shot/few-shot mode, or (c) use it to bootstrap annotations for a simpler model."

---

### DECISION OPTIONS

#### Option A: IndicBERT (ai4bharat) — Fine-tuned on FIR data

| Dimension | Assessment |
|-----------|-----------|
| Gujarati performance | Strong — pre-trained on IndicCorp with Gujarati included; designed for Indian languages |
| Data residency | Full compliance — runs entirely on-premise; model weights are open-source |
| Infrastructure | Runs on CPU or single consumer GPU; ~110M parameters; inference in milliseconds |
| Fine-tuning feasibility | Requires 2,000–5,000 labelled FIR examples per task; feasible within Sprints 2–4 |
| Licensing | MIT license — no restrictions |
| Limitation | Encoder-only model — good for classification and NER; cannot generate text (e.g., MO code suggestions from narrative) |
| Cost | Zero marginal cost after fine-tuning |

#### Option B: LLaMA-3-8B (Meta) — Fine-tuned or few-shot

| Dimension | Assessment |
|-----------|-----------|
| Gujarati performance | Moderate — multilingual but not Indic-optimised; may need Indic adapter layers |
| Data residency | Compliant if self-hosted — Meta Community License allows on-premise deployment |
| Infrastructure | Requires 1× A100 or equivalent GPU for inference; quantised versions (GGUF) can run on 16GB VRAM |
| Fine-tuning feasibility | QLoRA fine-tuning feasible on single GPU; requires 1,000+ examples for reasonable task performance |
| Licensing | Meta Community License — free for organisations with <700M MAU (ATLAS qualifies easily) |
| Capability | Generative model — can handle all 5 NLP tasks including MO code suggestion and section extraction via prompting |
| Limitation | Gujarati tokenisation is suboptimal; longer inference time than IndicBERT |
| Cost | GPU infrastructure cost (estimated ₹15,000–25,000/month for cloud GPU if on-prem GPU unavailable) |

#### Option C: GPT-4o (OpenAI) — API-based, zero-shot/few-shot

| Dimension | Assessment |
|-----------|-----------|
| Gujarati performance | Strong — GPT-4o handles Gujarati well in zero-shot mode |
| Data residency | **POTENTIAL SHOWSTOPPER** — FIR text would be sent to OpenAI's API servers (US-based); requires explicit Gujarat Police approval |
| Infrastructure | No on-prem infra needed; API calls only |
| Fine-tuning feasibility | Fine-tuning available but expensive; few-shot prompting is the primary mode |
| Licensing | Proprietary; pay-per-token |
| Capability | Best raw performance across all 5 tasks; excellent at zero-shot classification and NER |
| Limitation | (1) Data residency risk, (2) Per-token cost at scale: ~$0.005/1K input tokens × avg 500 tokens/FIR × 300K FIRs = ~$750/year for batch processing (affordable but ongoing), (3) API dependency — system fails if API is down |
| Cost | ~₹60,000–75,000/year at projected volumes; zero infrastructure cost |

#### Option D: Mistral-7B — Self-hosted, general-purpose

| Dimension | Assessment |
|-----------|-----------|
| Gujarati performance | Weaker than IndicBERT and GPT-4o on Gujarati; primarily English/European-language optimised |
| Data residency | Fully compliant — Apache 2.0 license, self-hosted |
| Infrastructure | Similar to LLaMA-3-8B; runs on single GPU |
| Licensing | Apache 2.0 — most permissive |
| Limitation | Poorest Gujarati performance of all options; would require significant fine-tuning with Gujarati data |
| Cost | GPU infrastructure cost only |

#### Option E: Tiered Hybrid Strategy

| Component | Model | Rationale |
|-----------|-------|-----------|
| Classification + NER (Tasks a, b) | IndicBERT fine-tuned | Best Gujarati encoder performance; fast inference; on-prem |
| Section extraction (Task c) | Rule-based regex + lookup table | Deterministic; IPC↔BNS mapping from R01 Appendix A |
| MO code suggestion (Task d) | LLaMA-3-8B few-shot or fine-tuned | Requires generative capability; on-prem compliant |
| Language detection (Task e) | fastText langdetect | Lightweight; proven for Indic script detection |

---

### DECISION CRITERIA

| Criterion | Weight | Notes |
|-----------|--------|-------|
| Data Residency Compliance | 25% | Non-negotiable if Gujarat Police prohibits external API calls |
| Gujarati Language Quality | 25% | FIRs are predominantly Gujarati; poor Gujarati = unusable system |
| Team Capacity to Fine-tune | 20% | Can we realistically fine-tune within Sprint 2–4 given annotation timelines? |
| Infrastructure Feasibility | 15% | Available GPU resources at BITS Pilani lab and Gujarat deployment site |
| Ongoing Cost | 10% | Recurring API costs vs. one-time infrastructure investment |
| Licensing Risk | 5% | Government deployment — any license restrictions? |

---

### ADR TEMPLATE

```markdown
# ADR-D02: NLP Model Selection

**Status:** [Proposed | Accepted]
**Date:** [Session date]
**Deciders:** Amit, Prishiv, Aditya

## Context
ATLAS requires NLP processing of Gujarati/English FIR text across 5 tasks:
classification, NER, section extraction, MO code suggestion, and language detection.
Data residency status: [Confirmed compliant / Pending Gujarat Police confirmation].
Available GPU resources: [Specify].

## Decision
We will adopt **[Option _]** because [rationale].

[If tiered:] The model allocation is:
| Task | Model | Deployment |
|------|-------|-----------|
| ... | ... | ... |

## Consequences
### Positive
- [List]
### Negative
- [List]
### Dependencies Created
- [Annotation pipeline dependency if fine-tuning chosen]
- [GPU procurement dependency if self-hosted LLM chosen]

## Open Questions (to be resolved by Sprint [N])
- Data residency confirmation from Gujarat Police IT Cell
- GPU availability at deployment site

## Sign-off
- [ ] Amit — Date: ___
- [ ] Prishiv — Date: ___
- [ ] Aditya — Date: ___
```

---

### DONE WHEN

- [ ] ADR-D02 signed off by all three members
- [ ] If data residency is unresolved: Jira action item assigned to Amit to get written confirmation from Gujarat Police IT Cell by Sprint 2 standup
- [ ] If fine-tuning chosen: annotation pipeline task (links to D04) added to Sprint 2 backlog
- [ ] If GPU-dependent: procurement/provisioning task assigned to Prishiv with deadline
- [ ] Sprint 2 NLP pipeline stories updated to reference chosen model(s)

---
---

# D03-PROMPT — RBAC Matrix Design: 6 Roles

**STORE AT:** `/atlas-project/docs/decisions/ADR-D03-rbac-matrix.md`
**Sprint Gate:** Sprint 2 — Auth module design depends on this.

---

### ROLE ASSIGNMENTS

| Role | Person | Responsibility |
|------|--------|---------------|
| Facilitator | Amit | Frame operational hierarchy; validate against Gujarat Police org structure |
| Decision-maker (Backend) | Prishiv | Assess implementation complexity in auth framework (Django/FastAPI permissions) |
| Decision-maker (Frontend) | Aditya | Assess UI/UX implications — which views/actions are gated per role |

**Timebox:** 60 minutes

---

### PRE-READ

1. R01-fir-legal-standards.md — §1.1 (officer hierarchy: IO, SHO, DySP, SP)
2. Gujarat Police organisational chart — ranks and reporting lines
3. eGujCop role-based access documentation (if available from IT Cell)
4. OWASP RBAC design guidelines
5. Django Guardian / FastAPI permission model documentation

---

### SESSION AGENDA

| Time | Block | Activity | Output |
|------|-------|----------|--------|
| 0:00–0:10 | **Problem Framing** | Define the 6 roles. Map each to Gujarat Police operational reality. | Role definition table |
| 0:10–0:35 | **Permission Matrix Construction** | For each system feature, assign Create/Read/Update/Delete per role. Use a shared spreadsheet or whiteboard. | Complete CRUD × Role matrix |
| 0:35–0:50 | **Edge Cases & Escalation** | What happens when an IO transfers? Can SHO override IO's classification? Data masking for sensitive fields (victim identity in sexual offence cases). | Edge case register |
| 0:50–0:55 | **Decision** | Confirm the matrix. Identify any cells needing Gujarat Police input. | Locked matrix |
| 0:55–1:00 | **ADR Draft** | Commit. | ADR-D03 committed |

---

### PROBLEM FRAMING

> "ATLAS serves users across the Gujarat Police hierarchy. Each role has different operational needs and data sensitivity requirements. Critically, victim identity in sexual offence cases (BNS Ch.V) is subject to legal restrictions — S.72 of BNS and Supreme Court guidelines prohibit disclosure of victim identity. Our RBAC must enforce these restrictions at the data layer, not just the UI layer.
>
> We must also decide whether ATLAS roles map 1:1 to Gujarat Police ranks, or whether we create abstract functional roles that can be assigned to any rank."

---

### DECISION OPTIONS

#### Option A: Rank-Mapped Roles (1:1 with police hierarchy)

Each ATLAS role corresponds exactly to a Gujarat Police rank. Promotions and transfers automatically change ATLAS permissions via HR system sync.

**Roles:**
1. **IO (Investigating Officer)** — Constable to Sub-Inspector assigned to a case
2. **SHO (Station House Officer)** — Inspector in charge of a police station
3. **DySP (Deputy Superintendent)** — Supervisory; oversees multiple stations
4. **SP (Superintendent of Police)** — District-level authority
5. **Admin** — IT Cell / SCRB technical administrators
6. **Read-only** — Training, audit, or judicial observers

#### Option B: Functional Roles (decoupled from rank)

Abstract roles that can be assigned regardless of rank. A Sub-Inspector could be assigned "Supervisor" role if acting as SHO.

**Roles:**
1. **Case-Worker** — Assigned to specific FIRs; can view/edit only their cases
2. **Station-Supervisor** — Can view/manage all cases at their station
3. **District-Supervisor** — Can view/manage all cases in their district
4. **State-Analyst** — Can view aggregate analytics across all districts
5. **System-Admin** — Full technical access; no case-level edit rights
6. **Auditor** — Read-only across all data; audit log access

---

### PERMISSION MATRIX TEMPLATE (to be filled during session)

| Feature / Action | IO/Case-Worker | SHO/Station-Sup | DySP/District-Sup | SP/State-Analyst | Admin | Read-only |
|-----------------|:-:|:-:|:-:|:-:|:-:|:-:|
| View own-station FIRs | R | R | R | R | — | R |
| View cross-station FIRs | — | — | R | R | — | R* |
| View NLP classification results | R | R | R | R | — | R |
| Override NLP classification | — | U | U | U | — | — |
| View victim identity (sexual offences) | R* | R* | R* | R* | — | — |
| Export data (CSV/PDF) | — | R | R | R | — | — |
| Manage user accounts | — | — | — | — | CRUD | — |
| View system logs / audit trail | — | — | — | R | R | R |
| Configure NLP model parameters | — | — | — | — | U | — |
| View bias audit reports | — | — | R | R | R | R |

*R\* = Restricted — masked by default, requires explicit justification to unmask*

---

### DECISION CRITERIA

| Criterion | Weight |
|-----------|--------|
| Alignment with Gujarat Police operational reality | 35% |
| Legal compliance (victim identity protection, data sensitivity) | 25% |
| Implementation simplicity for 2-developer team | 20% |
| Flexibility for future role additions | 10% |
| Auditability (can we prove who accessed what?) | 10% |

---

### ADR TEMPLATE

```markdown
# ADR-D03: Role-Based Access Control Matrix

**Status:** [Proposed | Accepted]
**Date:** [Session date]
**Deciders:** Amit, Prishiv, Aditya

## Context
ATLAS serves 6 user roles across Gujarat Police hierarchy. Victim identity in
sexual offence cases requires legal protection under BNS S.72. The system must
enforce data-layer access controls, not merely UI-level hiding.

## Decision
We will adopt **[Option A: Rank-Mapped / Option B: Functional]** roles.
The complete permission matrix is: [embed or link to spreadsheet].

## Data Masking Rules
- Victim name, address, and photo in BNS Ch.V offences: masked for all roles
  except [specify conditions for unmasking].
- [Additional masking rules from session.]

## Sign-off
- [ ] Amit — Date: ___
- [ ] Prishiv — Date: ___
- [ ] Aditya — Date: ___
```

---

### DONE WHEN

- [ ] Complete CRUD × Role matrix finalised and attached to ADR
- [ ] Data masking rules for sensitive fields documented
- [ ] Auth module stories in Sprint 2 backlog updated with specific permission rules
- [ ] ADR-D03 committed to wiki

---
---

# D04-PROMPT — Annotation Strategy: Tools, Team, and Protocol

**STORE AT:** `/atlas-project/docs/decisions/ADR-D04-annotation-strategy.md`
**Sprint Gate:** Sprint 2 — Annotation must begin by Sprint 3 for model fine-tuning in Sprint 4.

---

### ROLE ASSIGNMENTS

| Role | Person | Responsibility |
|------|--------|---------------|
| Facilitator | Amit | Budget constraints, timeline pressure, quality standards |
| Decision-maker (ML Pipeline) | Prishiv | Model training requirements — how many labels, what format, what quality threshold |
| Decision-maker (NLP/Data) | Aditya | Annotation UI/UX, guideline design, inter-annotator agreement measurement |

**Timebox:** 60 minutes

---

### PRE-READ

1. ADR-D02 (Model Selection) — determines annotation volume requirements
2. R01 §6 (data quality issues — what the annotators will encounter)
3. Label Studio documentation — features, deployment, export formats
4. Prodigy documentation — active learning workflow, pricing ($490 perpetual license)
5. ATLAS NLP task definitions (classification taxonomy, NER entity types, BNS section list)
6. Budget allocation for annotation (if any external annotators are budgeted)

---

### SESSION AGENDA

| Time | Block | Activity | Output |
|------|-------|----------|--------|
| 0:00–0:10 | **Problem Framing** | Quantify annotation needs per model decision. Timeline: when must labels be ready? | Volume × timeline matrix |
| 0:10–0:30 | **Tool Comparison** | Label Studio vs. Prodigy feature-by-feature for ATLAS tasks | Tool scorecard |
| 0:30–0:45 | **Annotator Strategy** | In-house (team members + BITS students) vs. external (legal domain experts) vs. hybrid | Annotator plan |
| 0:45–0:55 | **Quality Protocol** | Inter-annotator agreement threshold, adjudication process, gold-standard set | Quality protocol document |
| 0:55–1:00 | **ADR Draft** | Commit. | ADR-D04 committed |

---

### DECISION OPTIONS

#### Tool Selection

| Criterion | Label Studio (OSS) | Prodigy (Explosion AI) |
|-----------|-------------------|----------------------|
| Cost | Free (self-hosted) | $490 one-time (perpetual) |
| Deployment | Docker container; self-hosted | Local Python install; self-hosted |
| Active Learning | Limited (manual batch) | Built-in — model-in-the-loop annotation |
| Multi-user | Yes (team annotation, IAA) | Limited (primarily single-annotator optimised) |
| Export formats | COCO, Pascal VOC, YOLO, spaCy, JSON | spaCy, JSONL |
| Gujarati/Unicode | Supported | Supported |
| NER annotation | Good UI | Excellent UI (stream-based) |
| Classification | Good | Excellent (binary/multi-choice stream) |
| Custom workflows | Highly configurable via XML templates | Python recipe-based (flexible but requires coding) |
| **Best fit for ATLAS** | Better for multi-annotator team with IAA measurement | Better for rapid single-annotator active learning |

#### Annotator Strategy

| Option | Description | Pros | Cons |
|--------|------------|------|------|
| A: Team-only | Prishiv + Aditya annotate during Sprints 2–3 | Zero cost; domain knowledge builds organically | Diverts 30–40% of developer time from coding; 2 annotators is insufficient for IAA |
| B: BITS Students | Recruit 4–6 BITS Pilani students as annotators | Low cost (stipend-based); scalable; good IAA with multiple annotators | Require training; no legal domain expertise; may introduce noise |
| C: Legal Experts | Hire 2–3 law students/paralegals familiar with BNS/IPC | High quality; understand legal terminology | Higher cost (₹500–800/hour); recruitment time |
| D: Hybrid | Prishiv + Aditya create gold standard (200 FIRs); BITS students annotate bulk (2,000+); legal expert adjudicates disagreements | Balanced quality/cost/speed | Coordination overhead |

---

### DECISION CRITERIA

| Criterion | Weight |
|-----------|--------|
| Annotation quality (measured by IAA ≥ 0.8 Cohen's κ) | 30% |
| Timeline fit (labels ready by Sprint 4 start) | 25% |
| Developer time impact (how much coding time is lost) | 20% |
| Cost | 15% |
| Tool ecosystem fit with chosen ML framework | 10% |

---

### ADR TEMPLATE

```markdown
# ADR-D04: Annotation Strategy

**Status:** [Proposed | Accepted]
**Date:** [Session date]

## Decision
**Tool:** [Label Studio / Prodigy]
**Annotator Model:** [Option A/B/C/D]
**Target Volume:** [N] labelled FIRs by Sprint [M]
**Quality Threshold:** Cohen's κ ≥ [0.8]

## Annotation Guidelines Location
/atlas-project/docs/annotation/guidelines-v1.md

## Sign-off
- [ ] Amit — Date: ___
- [ ] Prishiv — Date: ___
- [ ] Aditya — Date: ___
```

---

### DONE WHEN

- [ ] Tool selected and deployment task in Sprint 2 backlog (assigned to Prishiv)
- [ ] Annotator recruitment plan documented with timeline
- [ ] Annotation guidelines draft assigned (to Aditya, due Sprint 2 end)
- [ ] Gold standard FIR set identified (source: eGujCop sample data request to Gujarat Police)
- [ ] ADR-D04 committed to wiki

---
---

# D05-PROMPT — Bias Remediation Protocol

**STORE AT:** `/atlas-project/docs/decisions/ADR-D05-bias-remediation.md`
**Sprint Gate:** Sprint 3 — Must be in place before any model is deployed to users.

---

### ROLE ASSIGNMENTS

| Role | Person | Responsibility |
|------|--------|---------------|
| Facilitator | Amit | Frame ethical/compliance requirements; reference NITI Aayog AI guidelines |
| Decision-maker (ML) | Prishiv | Technical bias detection methods — fairness metrics, threshold calibration |
| Decision-maker (Data/NLP) | Aditya | Data-level bias sources — caste/religion/gender representation in training data |

**Timebox:** 75 minutes

---

### PRE-READ

1. NITI Aayog "Responsible AI" principles document (2021)
2. R01 §2.5 — victim demographic fields (religion, caste/tribe) that could introduce proxy bias
3. Fairlearn library documentation — bias metrics and mitigation algorithms
4. "Fairness in Criminal Justice Risk Assessment" — ProPublica COMPAS analysis (for cautionary context)
5. Supreme Court guidelines on caste-based discrimination in policing
6. ADR-D02 (Model Selection) — which model's biases are we inheriting?

---

### SESSION AGENDA

| Time | Block | Activity | Output |
|------|-------|----------|--------|
| 0:00–0:15 | **Problem Framing** | Define what "bias" means in the ATLAS context. Identify which model outputs could cause real-world harm if biased. | Harm taxonomy |
| 0:15–0:35 | **Bias Source Mapping** | Map every point in the pipeline where bias can enter: data collection → annotation → model training → inference → display. | Pipeline bias map |
| 0:35–0:55 | **Protocol Design** | For each bias source: (a) detection metric, (b) threshold for flagging, (c) who has authority to intervene, (d) remediation options. | Bias remediation protocol table |
| 0:55–1:05 | **Authority & Escalation** | Who can halt model deployment if bias is detected? What is the escalation path? | Authority matrix |
| 1:05–1:15 | **ADR Draft** | Commit. | ADR-D05 committed |

---

### PROBLEM FRAMING

> "ATLAS classifies FIRs and may eventually inform resource allocation and case prioritisation decisions. If the NLP model systematically misclassifies FIRs from certain communities, police stations, or offence types, this could result in discriminatory policing outcomes.
>
> Specific bias risks in ATLAS:
> 1. **Caste/community bias in classification:** If the training data over-represents certain communities in certain crime categories (e.g., SC/ST cases disproportionately classified as 'property crime' vs. 'caste atrocity'), the model may perpetuate this misclassification.
> 2. **Geographic bias:** Urban police stations may produce higher-quality FIR narratives than rural stations, leading to better NLP performance for urban areas.
> 3. **Gender bias:** Crimes against women may be under-classified if the model is trained on historically under-reported data.
> 4. **Language bias:** If the model performs better on English-heavy FIRs than Gujarati-heavy FIRs, stations with more English-literate officers get better classification.
>
> We must decide on thresholds, authority, and remediation mechanisms BEFORE any model touches production data."

---

### PROTOCOL DESIGN TEMPLATE (fill during session)

| Bias Vector | Detection Metric | Threshold for Flag | Detection Authority | Remediation Options |
|-------------|-----------------|-------------------|--------------------|--------------------|
| Caste/community disparity in classification accuracy | Demographic Parity Difference (DPD) across caste categories | DPD > 0.05 | Automated (Fairlearn pipeline) + Amit quarterly review | (a) Retrain with balanced data, (b) Post-processing calibration, (c) Flag for human review |
| Geographic disparity | Per-district F1 score variance | Coefficient of variation > 0.15 | Prishiv (Sprint retrospective review) | (a) Station-specific fine-tuning, (b) Data augmentation for low-performing districts |
| Gender-based under-classification | Recall disparity for Ch.V offences by victim gender | Recall gap > 0.10 | Aditya (monthly NLP quality report) | (a) Targeted annotation of under-represented cases, (b) Threshold adjustment |
| Language performance gap | F1 score: Gujarati-only FIRs vs. English-heavy FIRs | F1 gap > 0.08 | Automated test suite | (a) Gujarati-specific fine-tuning data, (b) Translation preprocessing |
| [Additional vectors from session] | | | | |

---

### DECISION CRITERIA

| Criterion | Weight |
|-----------|--------|
| Harm prevention (does this protocol catch real-world discriminatory outcomes?) | 35% |
| Implementability (can a 2-person team actually run this protocol?) | 25% |
| Compliance (NITI Aayog, Supreme Court directives, Gujarat Police policy) | 20% |
| Transparency (can we explain our bias mitigation to external auditors?) | 15% |
| Performance impact (does bias mitigation degrade overall model accuracy?) | 5% |

---

### ADR TEMPLATE

```markdown
# ADR-D05: Bias Remediation Protocol

**Status:** [Proposed | Accepted]
**Date:** [Session date]

## Context
ATLAS NLP models classify FIR data involving sensitive demographic attributes.
Biased classification could result in discriminatory policing outcomes.

## Decision
We adopt the following bias remediation protocol:

### Detection
| Bias Vector | Metric | Threshold | Detection Frequency | Owner |
|-------------|--------|-----------|--------------------:|-------|
| [From session] | | | | |

### Remediation Menu
| Remediation Action | When Applied | Authority to Trigger |
|-------------------|-------------|---------------------|
| [From session] | | |

### Escalation
- Level 1: Automated flag → assigned developer reviews within [N] days
- Level 2: Amit reviews and decides retrain/recalibrate/halt
- Level 3: Gujarat Police stakeholder briefing if bias affects operational decisions

### Model Deployment Gate
No model version may be promoted to production without passing all bias
detection thresholds on the held-out test set. Gate owner: [Name].

## Sign-off
- [ ] Amit — Date: ___
- [ ] Prishiv — Date: ___
- [ ] Aditya — Date: ___
```

---

### DONE WHEN

- [ ] Bias remediation protocol table completed with all vectors, metrics, thresholds, and owners
- [ ] Fairlearn integration task added to Sprint 3 backlog (assigned to Prishiv)
- [ ] Bias test suite specification written (assigned to Aditya)
- [ ] Model deployment gate criteria documented
- [ ] ADR-D05 committed to wiki

---
---

# D06-PROMPT — Multilingual NLP Pipeline Architecture

**STORE AT:** `/atlas-project/docs/decisions/ADR-D06-multilingual-pipeline.md`
**Sprint Gate:** Sprint 2–3 — Pipeline design must be locked before annotation begins.

---

### ROLE ASSIGNMENTS

| Role | Person | Responsibility |
|------|--------|---------------|
| Facilitator | Amit | Frame the linguistic landscape; reference R01 data quality findings |
| Decision-maker (ML Pipeline) | Prishiv | Assess computational cost of each pipeline stage; integration with model choice (D02) |
| Decision-maker (NLP/Linguistics) | Aditya | Assess Gujarati NLP tool availability; transliteration accuracy; code-mixing handling |

**Timebox:** 75 minutes

---

### PRE-READ

1. R01 §6.2 — Multilingual data entry analysis (Gujarati/English mixing patterns)
2. ADR-D02 (Model Selection) — chosen model's multilingual capabilities
3. IndicNLP Library documentation — Gujarati tokenisation, transliteration
4. Google CLD3 / fastText langdetect — language identification benchmarks for Gujarati
5. Sample FIR texts (5–10 examples showing code-mixing patterns) — request from Gujarat Police or use publicly available FIR samples
6. Unicode Consortium: Gujarati script specification (U+0A80–U+0AFF)

---

### SESSION AGENDA

| Time | Block | Activity | Output |
|------|-------|----------|--------|
| 0:00–0:15 | **Problem Framing** | Characterise the 4 text patterns in FIR data: pure Gujarati, pure English, Gujarati with English legal terms, Romanised Gujarati. Estimate frequency of each. | Text pattern taxonomy with estimated distribution |
| 0:15–0:40 | **Pipeline Stage Design** | Design each stage: (1) Language detection, (2) Script normalisation, (3) Transliteration (if needed), (4) Tokenisation, (5) NLP model input preparation. For each stage, evaluate tools and decide. | Stage-by-stage architecture diagram |
| 0:40–0:55 | **Code-Mixing Strategy** | How do we handle sentences like "Accused એ victim ને BNS Section 303 હેઠળ threat કરી"? Split? Translate? Pass as-is to multilingual model? | Code-mixing decision |
| 0:55–1:05 | **Decision & Integration** | Lock the pipeline. Assign implementation to sprints. | Pipeline spec locked |
| 1:05–1:15 | **ADR Draft** | Commit. | ADR-D06 committed |

---

### PROBLEM FRAMING

> "FIR text in Gujarat exhibits four distinct patterns:
>
> 1. **Pure Gujarati (Gujarati script):** Estimated 40–50% of FIR narratives. Full Gujarati prose with Gujarati numerals or standard Arabic numerals.
> 2. **Pure English:** Estimated 10–15%. Typically from English-medium-educated officers in urban stations.
> 3. **Code-mixed Gujarati-English (Gujarati script dominant):** Estimated 30–35%. Gujarati narrative with English legal terms ('FIR', 'accused', 'Section 303 BNS'), proper nouns, and technical vocabulary embedded.
> 4. **Romanised Gujarati:** Estimated 5–10%. Gujarati words written in Latin script — prevalent in SMS/WhatsApp-origin e-FIR complaints.
>
> Our NLP pipeline must handle all four patterns and produce consistent feature vectors for the downstream classification and NER models. The pipeline must decide: do we normalise everything to one language/script before model input, or do we use a multilingual model that handles mixed input natively?"

---

### DECISION OPTIONS

#### Option A: Translate-to-English Pipeline

All non-English text is machine-translated to English before NLP processing. Model operates on English text only.

| Pro | Con |
|-----|-----|
| Simplifies model selection — any English NLP model works | Translation errors compound — legal terms may be mistranslated |
| Single-language feature vectors | Translation latency added to pipeline |
| Easier for English-literate developers to debug | Loses Gujarati-specific semantic nuances |
| | Google Translate API = data residency concern |

#### Option B: Normalise-to-Gujarati Pipeline

All English text is transliterated/translated to Gujarati. Model operates on Gujarati text.

| Pro | Con |
|-----|-----|
| Preserves original language of most FIRs | Limited Gujarati NLP tooling |
| No data residency issues | English legal terms lose precision when translated |
| Cultural/semantic context preserved | Smaller pre-trained model ecosystem for Gujarati |

#### Option C: Multilingual-Native Pipeline

Use a multilingual model (IndicBERT, mBERT, or LLaMA-3) that handles mixed-language input. Minimal preprocessing — language detection + script normalisation only.

| Pro | Con |
|-----|-----|
| No translation errors — model sees original text | Model must handle 4 text patterns — may underperform on rare patterns |
| Fastest pipeline (fewer stages) | Code-mixed input may confuse attention mechanisms |
| Best fit with IndicBERT (if chosen in D02) | Requires multilingual evaluation metrics |

#### Option D: Detect-and-Route Pipeline

Language detection at sentence level. Pure Gujarati → Gujarati model. Pure English → English model. Code-mixed → multilingual model. Romanised → transliterate to Gujarati script → Gujarati model.

| Pro | Con |
|-----|-----|
| Each model operates in its strongest mode | 3 model instances to maintain — overkill for 2-person team |
| Best theoretical accuracy | Routing errors propagate (wrong language detection → wrong model) |
| | Significantly more complex infrastructure |

---

### DECISION CRITERIA

| Criterion | Weight |
|-----------|--------|
| Accuracy across all 4 text patterns | 30% |
| Implementation complexity (2-developer team) | 25% |
| Latency (sub-5-second per-FIR for real-time classification) | 15% |
| Data residency compliance (no external API for translation) | 15% |
| Maintainability (can a future team understand and modify this?) | 15% |

---

### ADR TEMPLATE

```markdown
# ADR-D06: Multilingual NLP Pipeline Architecture

**Status:** [Proposed | Accepted]
**Date:** [Session date]

## Context
Gujarat FIR text exhibits 4 patterns: pure Gujarati (40-50%), pure English (10-15%),
code-mixed (30-35%), and Romanised Gujarati (5-10%).

## Decision
We will adopt **[Option _]** with the following pipeline stages:

### Pipeline Architecture
```
[Input FIR Text]
  → Stage 1: [Tool/method]
  → Stage 2: [Tool/method]
  → Stage 3: [Tool/method]
  → [Model Input]
```

### Tool Selections
| Stage | Tool | Fallback |
|-------|------|----------|
| Language Detection | [Tool] | [Fallback] |
| Script Normalisation | [Tool] | [Fallback] |
| Tokenisation | [Tool] | [Fallback] |

## Sign-off
- [ ] Amit — Date: ___
- [ ] Prishiv — Date: ___
- [ ] Aditya — Date: ___
```

---

### DONE WHEN

- [ ] Pipeline architecture diagram created and attached to ADR
- [ ] Tool selections for each stage documented with version numbers
- [ ] Sprint 2–3 backlog stories created for each pipeline stage implementation
- [ ] Sample FIR text test cases documented (at least 2 examples per text pattern)
- [ ] ADR-D06 committed to wiki

---
---

# D07-PROMPT — Integration Sequencing: eGujCop, ICJS, e-Prison, NCRB

**STORE AT:** `/atlas-project/docs/decisions/ADR-D07-integration-sequencing.md`
**Sprint Gate:** Sprint 3 — Integration work begins Sprint 4; sequencing must be locked.

---

### ROLE ASSIGNMENTS

| Role | Person | Responsibility |
|------|--------|---------------|
| Facilitator | Amit | External stakeholder relationships; which agencies will respond fastest; political capital allocation |
| Decision-maker (Backend/Integration) | Prishiv | API design, data sync architecture, error handling, fallback mechanisms |
| Decision-maker (Data/Frontend) | Aditya | Data mapping from external schemas to ATLAS schema; UI implications of partial integration |

**Timebox:** 75 minutes

---

### PRE-READ

1. R01 — §4 (Cross-referencing requirements: FIR → chargesheet → NCRB statistical returns)
2. eGujCop technical documentation (available portions from Gujarat Police IT Cell)
3. ICJS (Inter-operable Criminal Justice System) API specification — request from NIC
4. e-Prison portal documentation — data fields for undertrial/convict records
5. NCRB-CCTNS data exchange format specification
6. ADR-D01 (Architecture) — determines integration pattern (in-process vs. service call)
7. Gujarat Police IT Cell contact availability and expected response timelines

---

### SESSION AGENDA

| Time | Block | Activity | Output |
|------|-------|----------|--------|
| 0:00–0:15 | **Problem Framing** | Map all 4 integration targets. For each: what data flows in, what flows out, who owns the API, what is the current access status. | Integration landscape map |
| 0:15–0:40 | **Priority Ranking** | Force-rank the 4 integrations by: (a) value to MVP, (b) technical readiness, (c) stakeholder accessibility. Use weighted scoring. | Priority-ordered list |
| 0:40–0:55 | **Fallback Design** | For each integration: what does ATLAS do if the API is unavailable, delayed, or denied? Design degraded-mode operation. | Fallback matrix |
| 0:55–1:05 | **Sprint Allocation** | Map each integration to a sprint. Identify long-lead procurement items (API keys, MoUs, VPN tunnels). | Sprint × Integration timeline |
| 1:05–1:15 | **ADR Draft** | Commit. | ADR-D07 committed |

---

### PROBLEM FRAMING

> "ATLAS must eventually consume data from and/or push data to four external government systems. Each has a different technical maturity, a different owning agency, and a different political pathway to obtain access. We cannot integrate all four simultaneously — we must sequence them.
>
> The critical insight is: **integration is not just a technical task — it's a stakeholder management task.** Getting API access to eGujCop requires Gujarat Police IT Cell approval. ICJS is a national platform managed by NIC. e-Prison is a state system under the Home Department. NCRB-CCTNS has its own data exchange protocols.
>
> We must decide: (1) which integration is the MVP-critical path, (2) which can be deferred post-MVP, and (3) what does ATLAS do when an integration is unavailable."

---

### INTEGRATION TARGET PROFILES

| System | Owner | Data Direction | ATLAS Dependency | Access Status (estimated) |
|--------|-------|---------------|-----------------|--------------------------|
| **eGujCop** | Gujarat Police IT Cell (TCS-developed) | IN: FIR data, accused records, case status | **Critical** — primary data source for all NLP and analytics | Likely accessible — same department; requires IT Cell cooperation |
| **ICJS** | NIC (National Informatics Centre) | IN: Court orders, prosecution status; OUT: Case analytics | High value but not MVP-blocking | Requires NIC approval + MoU; 3–6 month lead time typical |
| **e-Prison** | Gujarat Home Department | IN: Undertrial/convict data, bail status | Medium value — enriches case lifecycle view | State-level approval; may piggyback on eGujCop relationship |
| **NCRB-CCTNS** | NCRB, MHA | OUT: Statistical returns, FIR data in CCTNS format; IN: Crime codes, MO codes | Medium — already integrated via eGujCop's CCTNS module | May not require separate integration if eGujCop exports include CCTNS data |

---

### DECISION OPTIONS

#### Option A: eGujCop-First, Rest Post-MVP

Sprint 4–5: eGujCop integration (data ingestion). Sprints 6–8: MVP with eGujCop data only. Post-MVP: ICJS, e-Prison, NCRB in subsequent project phases.

#### Option B: eGujCop + NCRB in Parallel

Sprint 4: eGujCop data ingestion. Sprint 5: NCRB code master synchronisation (crime heads, MO codes — these are reference data, not transactional). Sprint 6–8: MVP with both. ICJS and e-Prison post-MVP.

#### Option C: Full Integration Attempt (Aggressive)

Sprint 4: eGujCop. Sprint 5: NCRB. Sprint 6: ICJS. Sprint 7: e-Prison. Sprint 8: MVP.

Risk: Any integration delay cascades into MVP slip.

---

### FALLBACK DESIGN TEMPLATE (fill during session)

| Integration | Primary Mode | Fallback Mode | Data Quality Impact |
|-------------|-------------|---------------|-------------------|
| eGujCop | Real-time API / DB replica | Manual CSV upload by Gujarat Police data operator | Loss of real-time; batch processing only |
| NCRB-CCTNS | API sync of code masters | Static code master tables loaded at deployment | Codes may become stale; manual update required |
| ICJS | API integration | Manual court order entry by case worker | Significant data gap; case lifecycle incomplete |
| e-Prison | API integration | Not available — feature disabled in MVP | Undertrial tracking unavailable |

---

### DECISION CRITERIA

| Criterion | Weight |
|-----------|--------|
| MVP value (does this integration make the MVP meaningfully better?) | 30% |
| Technical readiness (is the API accessible and documented?) | 25% |
| Stakeholder accessibility (can we get approval within sprint timeline?) | 20% |
| Fallback robustness (can ATLAS function without this integration?) | 15% |
| Implementation effort (story points estimate) | 10% |

---

### ADR TEMPLATE

```markdown
# ADR-D07: Integration Sequencing

**Status:** [Proposed | Accepted]
**Date:** [Session date]

## Decision
Integration priority order:
1. [System] — Sprint [N] — Owner: [Name]
2. [System] — Sprint [N] — Owner: [Name]
3. [System] — Post-MVP — Contingent on: [condition]
4. [System] — Post-MVP — Contingent on: [condition]

## Fallback Matrix
| Integration | Fallback Mode | Trigger for Fallback | Acceptable Duration |
|-------------|--------------|---------------------|-------------------|
| [From session] | | | |

## Long-Lead Action Items
| Action | Owner | Deadline | Blocker? |
|--------|-------|----------|----------|
| Request eGujCop API access | Amit | Sprint 3 Day 1 | Yes — MVP-blocking |
| Initiate ICJS MoU process | Amit | Sprint 4 | No — post-MVP acceptable |
| [Others from session] | | | |

## Sign-off
- [ ] Amit — Date: ___
- [ ] Prishiv — Date: ___
- [ ] Aditya — Date: ___
```

---

### DONE WHEN

- [ ] Priority-ordered integration sequence locked
- [ ] Fallback mode defined for each integration
- [ ] Long-lead action items assigned with deadlines (especially eGujCop API access request)
- [ ] Sprint 4+ backlog updated with integration stories in priority order
- [ ] ADR-D07 committed to wiki

---
---

# D08-PROMPT — SPIKE Scoping: Conviction Probability Indicator — Go/No-Go/Descope

**STORE AT:** `/atlas-project/docs/decisions/ADR-D08-conviction-probability-spike.md`
**Sprint Gate:** Sprint 5 — SPIKE results determine whether this feature enters Sprint 6–8 backlog.

**⚠ SPECIAL RULE:** This session cannot conclude until a **data availability assessment sub-task** has been created and assigned. The team must determine whether Gujarat Police possesses historical outcome data (conviction/acquittal/discharge for FIRs) before any go/no-go decision is made.

---

### ROLE ASSIGNMENTS

| Role | Person | Responsibility |
|------|--------|---------------|
| Facilitator | Amit | Ethical framing; stakeholder risk assessment; casting vote on go/no-go |
| Decision-maker (ML Feasibility) | Prishiv | Model architecture for outcome prediction; minimum data requirements; confidence calibration |
| Decision-maker (Data/Ethics) | Aditya | Data availability assessment; bias implications; UI design for probability display |

**Timebox:** 90 minutes (extended due to ethical complexity and data assessment requirement)

---

### PRE-READ

1. R01 — §4.1 (FIR-to-chargesheet linkage — what outcome data theoretically exists)
2. ProPublica COMPAS analysis — "Machine Bias" (2016) — cautionary case study
3. "Pretrial Risk Assessment Tools: A Primer for Judges" — National Center for State Courts
4. NITI Aayog Responsible AI principles — Section on "high-risk AI applications"
5. ADR-D05 (Bias Remediation Protocol) — how would bias detection apply to this feature?
6. Gujarat High Court annual reports — conviction rates by offence type (if publicly available)
7. European AI Act risk classification — would this feature be classified as "high-risk" or "unacceptable"?

---

### SESSION AGENDA

| Time | Block | Activity | Output |
|------|-------|----------|--------|
| 0:00–0:20 | **Problem Framing & Ethical Analysis** | Define what "conviction probability indicator" means operationally. Who sees it? How could it be misused? What are the harm scenarios? | Ethical risk register |
| 0:20–0:40 | **Data Availability Assessment** | Can we even build this? What historical outcome data exists? Design the sub-task to query Gujarat Police. Define minimum data requirements. | Data assessment sub-task specification |
| 0:40–1:00 | **Feasibility & Scope Options** | If data exists: what model? What features? What confidence threshold makes this usable? Explore descoped alternatives. | Feasibility matrix |
| 1:00–1:15 | **Go / No-Go / Descope Decision** | Team decides on one of three paths. | Decision recorded |
| 1:15–1:30 | **ADR Draft + Data Sub-task Creation** | Commit ADR. Create and assign the data availability Jira ticket. | ADR-D08 + Jira ATLAS-SPIKE-D08 |

---

### PROBLEM FRAMING (Amit reads aloud — this is the most ethically sensitive deliberation)

> "The original ATLAS feature list includes a 'Conviction Probability Indicator' — a model-generated score estimating the likelihood that an FIR will result in conviction based on historical patterns. This feature is potentially the most impactful AND the most dangerous component of ATLAS.
>
> **Value case:** If accurate and well-calibrated, this indicator could help SHOs and DySPs prioritise investigation resources toward cases with stronger evidentiary foundations, improving conviction rates and reducing wasted effort.
>
> **Harm case:** If biased, poorly calibrated, or misused, this indicator could:
> - Cause officers to deprioritise cases involving marginalised communities (if historical conviction rates are lower due to systemic discrimination, not case merit)
> - Create a self-fulfilling prophecy — low-probability cases get fewer resources, leading to actual low conviction, reinforcing the model's prediction
> - Be used to pressure complainants to withdraw 'low-probability' FIRs
> - Violate the presumption of innocence if the indicator is visible at the FIR stage
>
> We must decide: do we build this, descope it, or reject it entirely?
>
> **Critical prerequisite:** Before we can make this decision, we need to know whether the **data even exists.** Conviction outcomes require linking FIRs → chargesheets → court dispositions. This data may not be digitally available in linked form."

---

### DECISION OPTIONS

#### Option A: GO — Full Conviction Probability Indicator

Build a model that estimates conviction probability based on FIR features. Display to SHO-level and above. Include confidence intervals. Gate behind bias audit.

**Requirements:** 5+ years of linked FIR-to-outcome data, minimum 50,000 cases with known outcomes, bias audit per ADR-D05 passed.

#### Option B: DESCOPE — Case Strength Indicator (no conviction prediction)

Instead of predicting conviction, build a "Case Completeness Score" that evaluates whether the FIR contains the evidentiary elements typically associated with strong cases (witness details, documentary evidence referenced, forensic evidence, clear identification of accused). This is a document quality metric, not an outcome prediction.

**Requirements:** Annotation of 2,000+ FIRs for evidentiary completeness. No historical outcome data needed. No conviction prediction = no presumption-of-innocence concern.

**This is the "ethical safe harbour" option.** It delivers value (improving FIR quality) without the risks of outcome prediction.

#### Option C: NO-GO — Remove from scope entirely

Conviction/case-strength prediction is too risky for an academic project with a 2-developer team. The bias remediation burden (ADR-D05) would consume disproportionate sprint capacity. Remove from MVP and all future roadmap.

#### Option D: CONDITIONAL GO — Build only if data assessment passes AND ethical review passes

Proceed with the data availability assessment. If data exists and is linkable, build a prototype in Sprint 6. Subject to a separate ethical review by [Amit + BITS faculty advisor] before any deployment. If either gate fails, automatically descope to Option B.

---

### DATA AVAILABILITY ASSESSMENT SUB-TASK (MANDATORY — must be created before session ends)

```markdown
## Jira Ticket: ATLAS-SPIKE-D08 — Data Availability Assessment for Conviction Probability

**Type:** SPIKE (Research)
**Assignee:** Amit (stakeholder query) + Aditya (data analysis)
**Sprint:** Sprint 5
**Story Points:** 5

### Description
Query Gujarat Police to determine whether historical FIR-to-conviction outcome data
exists in a digitally linked format.

### Acceptance Criteria
- [ ] Written query sent to Gujarat Police IT Cell / SCRB asking:
  1. Does eGujCop store court disposition data (conviction/acquittal/discharge) linked to FIR numbers?
  2. If yes, for how many years? How many FIRs have linked outcomes?
  3. Is this data exportable in a format ATLAS can ingest?
  4. Are there any data access restrictions on outcome data?
- [ ] Response received and documented (or "no response within 2 weeks" documented)
- [ ] If data exists: sample of 100 linked records obtained and analysed for:
  - Completeness (% of FIRs with known outcomes)
  - Time span covered
  - Offence type distribution
  - Demographic field availability (for bias audit)
- [ ] Findings documented in SPIKE report at:
  /atlas-project/docs/research/spikes/SPIKE-D08-conviction-data-assessment.md
- [ ] Go/No-Go recommendation based on findings

### Definition of Done
Data availability report completed with one of three conclusions:
(a) DATA SUFFICIENT — proceed to model prototyping
(b) DATA INSUFFICIENT — descope to Case Completeness Score (Option B)
(c) DATA UNAVAILABLE — descope to Option B or Option C per team decision

### Blocker
This SPIKE blocks any conviction probability model development work.
No story points for model development may be committed until this SPIKE is resolved.
```

---

### DECISION CRITERIA

| Criterion | Weight |
|-----------|--------|
| Ethical risk (harm potential if deployed with bias) | 30% |
| Data feasibility (does the data actually exist?) | 25% |
| Sprint capacity impact (how much of Sprint 6–8 does this consume?) | 20% |
| Stakeholder value (does Gujarat Police actually want this?) | 15% |
| Academic contribution (is this novel enough for the capstone?) | 10% |

---

### ADR TEMPLATE

```markdown
# ADR-D08: Conviction Probability Indicator — SPIKE Scoping

**Status:** [Go | Descoped | No-Go | Conditional]
**Date:** [Session date]

## Context
The original ATLAS feature list includes a conviction probability indicator.
This ADR documents the team's go/no-go decision and the rationale.

## Ethical Risk Assessment
| Harm Scenario | Likelihood | Severity | Mitigation |
|--------------|-----------|----------|-----------|
| [From session] | | | |

## Data Availability Assessment
**Status:** [Completed / Pending — ATLAS-SPIKE-D08]
**Findings:** [To be filled after SPIKE completes]

## Decision
We will **[GO / DESCOPE to Case Completeness Score / NO-GO]** because:
[Rationale from weighted criteria.]

## If DESCOPED: Alternative Feature
Case Completeness Score: [Brief specification]

## If CONDITIONAL GO: Gates
1. Data availability gate: ATLAS-SPIKE-D08 must return "DATA SUFFICIENT"
2. Ethical review gate: [Reviewer names] must approve before deployment
3. Bias audit gate: ADR-D05 thresholds must pass on outcome prediction model

## Sign-off
- [ ] Amit — Date: ___
- [ ] Prishiv — Date: ___
- [ ] Aditya — Date: ___
```

---

### DONE WHEN

- [ ] One of Go / Descope / No-Go / Conditional selected and documented
- [ ] **ATLAS-SPIKE-D08 Jira ticket created and assigned** (this is mandatory regardless of decision)
- [ ] If Go or Conditional: Sprint 6 backlog placeholder created, gated on SPIKE outcome
- [ ] If Descoped: Case Completeness Score feature spec drafted (assigned to Aditya)
- [ ] Ethical risk register attached to ADR
- [ ] ADR-D08 committed to wiki

---
---

# D09-PROMPT — Synthetic Data Ethics: Boundaries, Validation, Flagging

**STORE AT:** `/atlas-project/docs/decisions/ADR-D09-synthetic-data-ethics.md`
**Sprint Gate:** Sprint 3 — Must be resolved before any synthetic data is generated for training.

---

### ROLE ASSIGNMENTS

| Role | Person | Responsibility |
|------|--------|---------------|
| Facilitator | Amit | Ethical boundaries; academic integrity implications; Gujarat Police data sensitivity |
| Decision-maker (ML) | Prishiv | Synthetic data generation techniques; model performance impact |
| Decision-maker (Data) | Aditya | Data validation; distinguishing synthetic from real in pipeline; annotation implications |

**Timebox:** 60 minutes

---

### PRE-READ

1. ADR-D04 (Annotation Strategy) — available real data volumes
2. "Synthetic Data for Machine Learning" — survey paper (2023)
3. NITI Aayog data governance principles
4. Gujarat Police data sharing agreement (if any) — what are we permitted to generate synthetically?
5. Differential privacy literature — applicability to FIR text generation

---

### SESSION AGENDA

| Time | Block | Activity | Output |
|------|-------|----------|--------|
| 0:00–0:10 | **Problem Framing** | Why do we need synthetic data? What gap does it fill? | Gap quantification |
| 0:10–0:25 | **Boundary Setting** | What categories of synthetic FIR data are permissible? What is absolutely prohibited? Draw the bright lines. | Boundary table |
| 0:25–0:40 | **Generation & Validation Protocol** | How is synthetic data generated? How is it validated against real data distributions? How is it flagged in the dataset? | Protocol specification |
| 0:40–0:50 | **Downstream Safeguards** | How do we ensure synthetic data doesn't contaminate evaluation metrics? How is it labelled in the data warehouse? | Safeguard checklist |
| 0:50–1:00 | **ADR Draft** | Commit. | ADR-D09 committed |

---

### PROBLEM FRAMING

> "Our NLP models require labelled training data. Real FIR data is limited in quantity (we may only receive a few thousand samples from Gujarat Police) and sensitive in content. Synthetic data — machine-generated FIR-like text — could augment our training set. However, synthetic police data carries unique risks:
>
> 1. **Fabrication risk:** If synthetic FIRs are realistic enough, they could be mistaken for real records if they leak or are improperly labelled.
> 2. **Distribution shift:** If synthetic data doesn't match real FIR patterns, models trained on it will underperform on real data.
> 3. **Ethical boundaries:** Generating synthetic descriptions of sexual offences, child abuse, or communal violence raises ethical concerns even if no real person is referenced.
> 4. **Academic integrity:** Using synthetic data in model evaluation would inflate reported metrics."

---

### BOUNDARY TABLE (fill during session)

| Data Category | Synthetic Generation Permitted? | Conditions |
|--------------|:-----------------------------:|-----------|
| Property crime FIR narratives | ✅ Yes | Must not use real names, addresses, or identifiable details |
| Traffic/negligence FIR narratives | ✅ Yes | Vehicle numbers must be clearly fictitious (GJ-XX-XXXX format) |
| Violent crime (non-sexual) narratives | ⚠️ Conditional | Permitted for classification training only; must be clearly flagged |
| Sexual offence narratives | ❌ No | Ethical prohibition — even synthetic descriptions carry harm potential |
| Child-related offence narratives | ❌ No | Absolute prohibition |
| Communal/caste violence narratives | ❌ No | Risk of reinforcing stereotypes in training data |
| Accused/victim demographic data | ❌ No | Synthetic demographics could embed or amplify bias |
| Legal section citations | ✅ Yes | Must use valid BNS section numbers; useful for section extraction training |
| Geo-location data | ⚠️ Conditional | May use real Gujarat place names with randomised coordinates |
| [Additional categories from session] | | |

---

### DECISION CRITERIA

| Criterion | Weight |
|-----------|--------|
| Ethical safety (no harm from synthetic content creation or leakage) | 35% |
| Model performance impact (does synthetic data actually help?) | 25% |
| Academic integrity (clear separation from evaluation data) | 20% |
| Implementation effort | 10% |
| Gujarat Police stakeholder acceptability | 10% |

---

### ADR TEMPLATE

```markdown
# ADR-D09: Synthetic Data Ethics Protocol

**Status:** [Proposed | Accepted]
**Date:** [Session date]

## Decision
Synthetic data generation is **[Permitted with restrictions / Prohibited entirely]**.

### Permitted Categories
| Category | Generation Method | Volume Cap | Flagging Method |
|----------|------------------|-----------|----------------|
| [From session] | | | |

### Prohibited Categories (Bright Lines)
- [List from session — these are non-negotiable]

### Validation Protocol
1. [Distribution comparison method]
2. [Human review sample rate]
3. [Flagging in data warehouse]

### Contamination Prevention
- Synthetic data column: `is_synthetic = TRUE` in all database records
- Synthetic data NEVER included in test/evaluation sets
- All model performance metrics reported on real data only

## Sign-off
- [ ] Amit — Date: ___
- [ ] Prishiv — Date: ___
- [ ] Aditya — Date: ___
```

---

### DONE WHEN

- [ ] Boundary table completed with clear permit/prohibit designations
- [ ] Validation protocol documented
- [ ] `is_synthetic` flag added to data schema specification (assigned to Prishiv)
- [ ] Synthetic data generation task (if permitted) scoped and added to Sprint 3–4 backlog
- [ ] ADR-D09 committed to wiki

---
---

# D10-PROMPT — Sprint 8 MVP Criteria: Go-Live Gates, P1/P2/P3, Rollback

**STORE AT:** `/atlas-project/docs/decisions/ADR-D10-mvp-criteria.md`
**Sprint Gate:** Sprint 1 — MVP criteria must be defined at project start so every sprint works toward them.

---

### ROLE ASSIGNMENTS

| Role | Person | Responsibility |
|------|--------|---------------|
| Facilitator | Amit | Define "good enough" for Gujarat Police stakeholders; academic submission requirements |
| Decision-maker (Backend/Infra) | Prishiv | Operational readiness criteria — uptime, performance, deployment |
| Decision-maker (Frontend/UX) | Aditya | User-facing completeness — which screens, which workflows must be functional |

**Timebox:** 75 minutes

---

### PRE-READ

1. Gujarat Police stakeholder expectations document (if available)
2. BITS Pilani capstone evaluation rubric — what must be demonstrated
3. All ADRs D01–D09 (architecture, model, integrations — what's been committed)
4. Comparable project MVPs — police analytics systems in other Indian states

---

### SESSION AGENDA

| Time | Block | Activity | Output |
|------|-------|----------|--------|
| 0:00–0:15 | **Problem Framing** | Define MVP audience (Gujarat Police demo? BITS evaluation? Both?). Define "go-live" — pilot deployment vs. demo-only vs. production. | MVP definition statement |
| 0:15–0:40 | **Feature Classification** | List all features. Classify each as P1 (must-have for MVP), P2 (should-have — include if time permits), P3 (nice-to-have — post-MVP). | P1/P2/P3 list |
| 0:40–0:55 | **Go-Live Gates** | Define the binary gates that must pass before MVP is declared ready. | Gate checklist |
| 0:55–1:05 | **Rollback Triggers** | If MVP is deployed as a pilot: what conditions trigger a rollback? Who decides? | Rollback protocol |
| 1:05–1:15 | **ADR Draft** | Commit. | ADR-D10 committed |

---

### FEATURE CLASSIFICATION TEMPLATE (fill during session)

| Feature | Priority | Sprint Target | Acceptance Criteria | Status |
|---------|:--------:|:-------------:|--------------------:|--------|
| FIR data ingestion (eGujCop or CSV) | P1 | Sprint 4 | ≥1,000 FIRs successfully ingested and queryable | — |
| NLP crime-type classification | P1 | Sprint 5 | F1 ≥ 0.75 on real FIR test set | — |
| Role-based dashboard (IO/SHO views) | P1 | Sprint 6 | Login, role-gated views, FIR list, classification display | — |
| Named Entity Recognition (accused/victim/location) | P1 | Sprint 5 | Precision ≥ 0.70 on real FIR test set | — |
| Section number extraction and validation | P2 | Sprint 5 | IPC↔BNS mapping functional | — |
| MO code suggestion | P2 | Sprint 6 | Top-3 suggestion accuracy ≥ 0.60 | — |
| Analytics dashboard (trends, heatmaps) | P2 | Sprint 7 | District-level crime trend display | — |
| Bias audit report (automated) | P1 | Sprint 7 | ADR-D05 thresholds pass | — |
| Conviction probability / Case completeness | P3/Descoped | Sprint 6–7 | Per ADR-D08 decision | — |
| ICJS integration | P3 | Post-MVP | — | — |
| e-Prison integration | P3 | Post-MVP | — | — |
| Multi-language UI (Gujarati interface) | P2 | Sprint 7–8 | Core navigation in Gujarati | — |
| [Additional features from session] | | | | |

---

### GO-LIVE GATE CHECKLIST (fill during session)

| # | Gate | Criteria | Owner | Pass/Fail |
|---|------|----------|-------|-----------|
| G1 | Data ingestion functional | ≥1,000 real or realistic FIRs loaded | Prishiv | — |
| G2 | NLP pipeline operational | Classification + NER running on ingested FIRs | Aditya | — |
| G3 | RBAC enforced | All 6 roles tested; victim identity masking verified | Prishiv | — |
| G4 | Bias audit passed | ADR-D05 thresholds met on test data | Aditya | — |
| G5 | Performance baseline | Dashboard page load < 3 seconds; NLP inference < 5 seconds/FIR | Prishiv | — |
| G6 | Security baseline | No hardcoded credentials; HTTPS enforced; SQL injection tests passed | Prishiv | — |
| G7 | Documentation complete | API docs, user manual draft, deployment guide | Both | — |
| G8 | Stakeholder demo passed | Gujarat Police stakeholder has seen and accepted the demo | Amit | — |

---

### ROLLBACK TRIGGERS (if pilot deployment)

| Trigger | Threshold | Who Decides | Action |
|---------|-----------|-------------|--------|
| System downtime | > 4 hours continuous | Prishiv | Rollback to pre-deployment state |
| Data breach / unauthorized access | Any incident | Amit (immediate) | Immediate shutdown + Gujarat Police notification |
| Bias detection failure in production | ADR-D05 thresholds breached on live data | Amit | Disable NLP classification; revert to manual |
| Gujarat Police requests shutdown | Any request | Amit | Immediate compliance |
| Model accuracy degradation | F1 drops > 0.10 below baseline | Aditya | Disable model; flag for retraining |

---

### ADR TEMPLATE

```markdown
# ADR-D10: Sprint 8 MVP Criteria

**Status:** [Proposed | Accepted]
**Date:** [Session date]

## MVP Definition
ATLAS MVP is a **[pilot deployment / demo-only / production-ready]** system
targeting **[audience]** by Sprint 8 end.

## Feature Classification
### P1 — Must-Have
| Feature | Acceptance Criteria | Sprint |
|---------|--------------------:|:------:|
| [From session] | | |

### P2 — Should-Have
| Feature | Acceptance Criteria | Sprint |
|---------|--------------------:|:------:|
| [From session] | | |

### P3 — Post-MVP
| Feature | Notes |
|---------|-------|
| [From session] | |

## Go-Live Gates
[Gate checklist from session — all must pass]

## Rollback Protocol
[Trigger table from session]

## Sign-off
- [ ] Amit — Date: ___
- [ ] Prishiv — Date: ___
- [ ] Aditya — Date: ___
```

---

### DONE WHEN

- [ ] P1/P2/P3 classification agreed for all features
- [ ] Go-live gate checklist finalised with owners and criteria
- [ ] Rollback triggers documented
- [ ] Sprint 1–8 roadmap updated to reflect P1/P2/P3 allocation
- [ ] ADR-D10 committed to wiki

---
---

# D11-PROMPT — Monthly Report Format: Metrics, Progress Definition, Instalment Protocol

**STORE AT:** `/atlas-project/docs/decisions/ADR-D11-monthly-report-format.md`
**Sprint Gate:** Sprint 1 — First report due at Sprint 2 end.

---

### ROLE ASSIGNMENTS

| Role | Person | Responsibility |
|------|--------|---------------|
| Facilitator | Amit | Define what BITS Pilani and Gujarat Police stakeholders expect to see |
| Decision-maker (Technical Metrics) | Prishiv | Define measurable technical progress indicators |
| Decision-maker (Output Metrics) | Aditya | Define deliverable-based progress indicators; report design |

**Timebox:** 60 minutes

---

### PRE-READ

1. BITS Pilani capstone monthly report template (if prescribed)
2. Gujarat Police project reporting requirements (if any)
3. Agile Sprint Review best practices — what metrics matter
4. ADR-D10 (MVP Criteria) — P1/P2/P3 features as progress milestones

---

### SESSION AGENDA

| Time | Block | Activity | Output |
|------|-------|----------|--------|
| 0:00–0:10 | **Problem Framing** | Who reads the monthly report? What decisions do they make based on it? | Audience × decision matrix |
| 0:10–0:25 | **Metrics Selection** | Select 5–8 metrics that collectively tell the project health story. | Metric definitions |
| 0:25–0:35 | **"Satisfactory Progress" Definition** | Define the threshold for each metric that constitutes "satisfactory." | Threshold table |
| 0:35–0:50 | **Report Template Design** | Design the 2–3 page report template. Assign authorship responsibilities. | Template draft |
| 0:50–0:55 | **Instalment Protocol** | If project funding is tied to progress reports: define what "instalment-eligible" means. | Protocol documented |
| 0:55–1:00 | **ADR Draft** | Commit. | ADR-D11 committed |

---

### METRICS CANDIDATES (select 5–8 during session)

| Metric | Category | Source | Frequency |
|--------|----------|--------|-----------|
| Sprint velocity (story points completed / committed) | Process | Jira | Per sprint |
| P1 feature completion % | Deliverable | ADR-D10 P1 list | Monthly |
| NLP model performance (F1 / Precision / Recall) | Technical | Model evaluation logs | Per training cycle |
| FIR ingestion volume (total records processed) | Technical | System logs | Monthly |
| ADR completion rate (decisions made / decisions pending) | Governance | Wiki | Monthly |
| Defect escape rate (bugs found in demo vs. bugs found in testing) | Quality | Jira | Monthly |
| Test coverage % | Quality | CI/CD pipeline | Per sprint |
| Stakeholder satisfaction (qualitative) | Outcome | Meeting notes | Monthly |

### "SATISFACTORY PROGRESS" DEFINITION

| Metric | Green (On Track) | Amber (At Risk) | Red (Behind) |
|--------|:---:|:---:|:---:|
| Sprint velocity ratio | ≥ 0.80 | 0.60–0.79 | < 0.60 |
| P1 feature completion | On schedule per ADR-D10 | 1 sprint behind | 2+ sprints behind |
| NLP F1 score trajectory | Improving sprint-over-sprint | Flat | Declining |
| ADR completion | All scheduled ADRs signed | 1 pending | 2+ pending |
| [Others from session] | | | |

---

### ADR TEMPLATE

```markdown
# ADR-D11: Monthly Report Format

**Status:** [Proposed | Accepted]
**Date:** [Session date]

## Decision
Monthly reports will follow the template at:
/atlas-project/docs/templates/monthly-report-template.md

## Report Metrics
| # | Metric | Definition | Green/Amber/Red Thresholds |
|---|--------|-----------|---------------------------|
| [From session] | | | |

## Authorship
| Section | Author | Reviewer |
|---------|--------|----------|
| Executive Summary | Amit | — |
| Technical Progress | Prishiv | Aditya |
| NLP/Data Progress | Aditya | Prishiv |
| Risk Register | Amit | Both |

## Submission Schedule
Reports due on the **[Nth] day** of each month, covering the previous month.

## Instalment Protocol
Satisfactory progress (all metrics Green or Amber) = instalment eligible.
Any Red metric requires a remediation plan attached to the report.

## Sign-off
- [ ] Amit — Date: ___
- [ ] Prishiv — Date: ___
- [ ] Aditya — Date: ___
```

---

### DONE WHEN

- [ ] Monthly report template created and stored in `/atlas-project/docs/templates/`
- [ ] 5–8 metrics selected with Green/Amber/Red thresholds
- [ ] Authorship assignments documented
- [ ] First report deadline set
- [ ] ADR-D11 committed to wiki

---
---

# D12-PROMPT — Training Delivery Format: In-Person vs. Hybrid, Language, Assessment

**STORE AT:** `/atlas-project/docs/decisions/ADR-D12-training-delivery.md`
**Sprint Gate:** Sprint 7 — Training materials must be developed in Sprint 7–8.

---

### ROLE ASSIGNMENTS

| Role | Person | Responsibility |
|------|--------|---------------|
| Facilitator | Amit | Gujarat Police training logistics; language requirements; assessment standards |
| Decision-maker (Technical Content) | Prishiv | System administration training; backend operational procedures |
| Decision-maker (User Content) | Aditya | End-user training; dashboard navigation; NLP output interpretation |

**Timebox:** 60 minutes

---

### PRE-READ

1. ADR-D03 (RBAC Matrix) — determines which roles need which training tracks
2. ADR-D10 (MVP Criteria) — what features are in MVP = what must be trained on
3. Gujarat Police IT training infrastructure (computer labs? Projectors? Internet connectivity at training venues?)
4. Gujarat Police language policy for official training (Gujarati mandatory? English acceptable for technical content?)
5. eGujCop training history — how was eGujCop rolled out? What format worked?

---

### SESSION AGENDA

| Time | Block | Activity | Output |
|------|-------|----------|--------|
| 0:00–0:10 | **Problem Framing** | How many users need training? What are their IT literacy levels? What languages do they operate in? | User profile matrix |
| 0:10–0:25 | **Delivery Format** | In-person only vs. hybrid (in-person + video) vs. self-paced digital. Assess venue/infrastructure constraints. | Format decision |
| 0:25–0:40 | **Curriculum Design** | Map training tracks to RBAC roles. Define modules, duration, and learning objectives per track. | Curriculum outline |
| 0:40–0:50 | **Assessment Design** | How do we verify that trainees can actually use the system? Written test? Practical exercise? Certification? | Assessment specification |
| 0:50–0:55 | **Language Decision** | Training materials in Gujarati, English, or bilingual? | Language policy |
| 0:55–1:00 | **ADR Draft** | Commit. | ADR-D12 committed |

---

### DECISION OPTIONS

#### Delivery Format

| Option | Description | Pros | Cons |
|--------|------------|------|------|
| A: In-person only | Team travels to Gujarat Police Academy / district training centres; 1–2 day workshop per batch | Highest engagement; hands-on practice; builds relationship | Travel cost; limited reach; schedule dependency |
| B: Hybrid | 1 in-person session for "train-the-trainers" (5–10 master trainers) + recorded video modules for wider rollout | Scalable; master trainers handle ongoing support | Requires video production; quality depends on master trainers |
| C: Self-paced digital | Screen recordings + interactive tutorials + written guides | Lowest cost; available on-demand; no scheduling | Low completion rates; no hands-on support; assumes internet access |
| D: In-person + digital reference | In-person workshop (Option A) supplemented by digital reference materials (quick-start guides, FAQ, video walkthroughs) | Best of both: engagement + ongoing reference | Highest content production effort |

#### Language Options

| Option | Description | Impact |
|--------|------------|--------|
| English only | All materials in English | Excludes constable-level users with limited English |
| Gujarati only | All materials in Gujarati | Technical terms may lose precision; harder for team to produce |
| Bilingual | Technical content in English; UI navigation and workflow guides in Gujarati; video narration in Gujarati with English subtitles | Best coverage; highest production effort |
| English + Gujarati glossary | English materials with a Gujarati glossary of technical terms | Compromise — moderate effort, moderate coverage |

---

### TRAINING TRACK TEMPLATE (fill during session)

| Track | Target Roles | Modules | Duration | Language | Assessment |
|-------|-------------|---------|----------|----------|-----------|
| Track 1: Case Worker (IO) | IO / Constable | (a) Login & navigation, (b) Viewing FIR classification results, (c) Flagging incorrect classifications | 2 hours | Gujarati with English terms | Practical: complete 3 tasks on test system |
| Track 2: Supervisor (SHO/DySP) | SHO, DySP | (a) All Track 1 content, (b) Analytics dashboard, (c) Override classification, (d) Bias report interpretation | 3 hours | Bilingual | Practical + written quiz |
| Track 3: Administrator | IT Cell staff | (a) System deployment, (b) User management, (c) Model retraining trigger, (d) Troubleshooting | 4 hours | English | Hands-on deployment exercise |
| Track 4: Executive Overview | SP, Senior Officers | (a) System capabilities overview, (b) Data interpretation, (c) Limitation awareness | 1 hour | English / Gujarati (presenter's choice) | None — awareness-level only |

---

### DECISION CRITERIA

| Criterion | Weight |
|-----------|--------|
| User reach (how many officers can we effectively train?) | 25% |
| IT literacy accommodation (does this work for constable-level users?) | 25% |
| Production effort (can a 2-person team produce this by Sprint 8?) | 20% |
| Sustainability (can Gujarat Police continue training after project handover?) | 15% |
| Assessment validity (does the assessment actually verify competence?) | 15% |

---

### ADR TEMPLATE

```markdown
# ADR-D12: Training Delivery Format

**Status:** [Proposed | Accepted]
**Date:** [Session date]

## Decision
**Delivery Format:** [Option A/B/C/D]
**Language Policy:** [English only / Gujarati only / Bilingual / English + Glossary]

## Training Tracks
| Track | Target Roles | Duration | Language | Assessment |
|-------|-------------|----------|----------|-----------|
| [From session] | | | | |

## Production Timeline
| Deliverable | Owner | Sprint | Format |
|------------|-------|--------|--------|
| Track 1 materials | Aditya | Sprint 7 | [Slides/Video/Guide] |
| Track 2 materials | Aditya | Sprint 7 | [Slides/Video/Guide] |
| Track 3 materials | Prishiv | Sprint 8 | [Technical guide] |
| Track 4 presentation | Amit | Sprint 8 | [Executive deck] |

## Train-the-Trainer Plan (if Option B selected)
- Number of master trainers: [N]
- Training-of-trainers session date: [TBD]
- Ongoing support plan: [Specify]

## Sign-off
- [ ] Amit — Date: ___
- [ ] Prishiv — Date: ___
- [ ] Aditya — Date: ___
```

---

### DONE WHEN

- [ ] Delivery format selected
- [ ] Language policy decided
- [ ] Training tracks defined with modules and durations
- [ ] Assessment method specified per track
- [ ] Content production tasks added to Sprint 7–8 backlog with assignments
- [ ] ADR-D12 committed to wiki

---
---

# MASTER DELIBERATION SCHEDULE

| ID | Title | Suggested Sprint | Duration | Dependencies |
|----|-------|:----------------:|:--------:|:-------------|
| D01 | System Architecture | Sprint 1, Day 1–2 | 75 min | None — first decision |
| D10 | MVP Criteria | Sprint 1, Day 2–3 | 75 min | D01 (architecture constrains features) |
| D11 | Monthly Report Format | Sprint 1, Day 3 | 60 min | D10 (metrics tied to MVP criteria) |
| D02 | Model Selection | Sprint 1–2 boundary | 90 min | D01 (architecture constrains model deployment) |
| D03 | RBAC Matrix | Sprint 2, Day 1–2 | 60 min | D01 (auth module design) |
| D06 | Multilingual Pipeline | Sprint 2, Day 3–5 | 75 min | D02 (model choice drives pipeline design) |
| D04 | Annotation Strategy | Sprint 2, Day 5–Sprint 3 Day 1 | 60 min | D02 (model choice drives annotation volume), D06 |
| D05 | Bias Remediation | Sprint 3, Day 1–3 | 75 min | D02, D04 (model + data choices inform bias vectors) |
| D09 | Synthetic Data Ethics | Sprint 3, Day 3–5 | 60 min | D04 (annotation gap determines synthetic need) |
| D07 | Integration Sequencing | Sprint 3, Day 5–Sprint 4 Day 1 | 75 min | D01, D10 (architecture + MVP scope) |
| D08 | Conviction Probability SPIKE | Sprint 5, Day 1–3 | 90 min | D05 (bias protocol must exist first), D07 |
| D12 | Training Delivery | Sprint 7, Day 1–3 | 60 min | D03 (RBAC determines training tracks), D10 |

**Total facilitated deliberation time:** ~14.5 hours across 8 sprints

---

*This document is the session facilitation master reference. Each D-Prompt is self-contained and can be extracted for standalone use. Print or screen-share the relevant prompt at session start. Amit retains facilitation authority for all sessions.*
