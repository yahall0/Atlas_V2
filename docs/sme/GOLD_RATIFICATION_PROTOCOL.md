# Gold-Standard Ratification Protocol — for the SME Panel

| Document Attribute | Value |
|---|---|
| Document ID | ATLAS-SME-001 |
| Version | 1.0 |
| Status | Issued for Use |
| Classification | Restricted |
| Issue Date | 2026-04-19 |
| Audience | Legal SME panel ratifying the ATLAS gold standard |
| Companion to | [ADR-D15](../decisions/ADR-D15-subclause-precision.md), [ADR-D16](../decisions/ADR-D16-recommender-pipeline.md), [ADR-D18](../decisions/ADR-D18-gold-ratification.md) |

---

## 1. Why your work matters

The ATLAS section recommender is *measured* against the gold-standard set you are about to review. Every quality lever the engineering team can pull — reranker fine-tuning, embedder selection, structured-fact extraction, feedback-driven re-ranking — is judged by a single number: did it improve recall and precision against this gold set.

If the gold set is wrong, every metric is misleading and every engineering decision risks being wrong-headed. Your ratification is the load-bearing pillar of system quality. *That* is the importance of this exercise.

The technical team has done the homework — every entry has been pre-reviewed by an AI curator with deep statutory knowledge, and the proposed labels are sub-clause-precise (per ADR-D15). Your job is to confirm, correct or reject — not to start from scratch.

## 2. What you are reviewing

Each entry contains:
- **fir_id** — internal identifier (e.g. `GS_0001`)
- **narrative** — the FIR statement of facts (anonymised where applicable)
- **occurrence_date_iso** — drives BNS-vs-IPC act selection (cutoff 2024-07-01)
- **accused_count** — used by required-companion rules (BNS 3(5) etc.)
- **expected_citations** — the AI-curator's proposed sub-clause-precise list
- **ai_curator_notes** — what the curator changed and why

You will *not* see internal model scores. Your judgment is the standard, not the system's confidence.

## 3. What "correct" means

Treat each FIR as if you were the public prosecutor reviewing the IO's draft. The gold-standard label set should reflect:

1. **The substantive offences disclosed by the FIR facts as written**, and only those. If the facts are silent on grievous hurt, do not include grievous-hurt sections (mark as deferred).
2. **Sub-clause precision.** Cite `BNS 305(a)`, not `BNS 305`. Cite `BNS 331(3)`, not `BNS 331`. The recommender is held to this standard; the gold set must be held to it too.
3. **All required companions**, including BNS 3(5) (or IPC 34) when two or more accused acted in concert.
4. **No over-charging.** If a section's gating ingredient is absent from the FIR, exclude it. Better to have a clean five-section set that holds, than a defensible-but-questionable nine-section set that the prosecutor has to amend.
5. **Cross-act coverage.** Where the primary chargeable surface is a special act (POCSO, NDPS, SC/ST Atrocities, IT Act, MV Act, Dowry Prohibition Act), the AI-curator notes flag it. ATLAS today only stocks IPC and BNS — surface the cross-act recommendation as a panel comment so the engineering team prioritises ingestion.

## 4. The four actions

| Key | Action | When to use |
|---|---|---|
| **A** | **Accept** — entry transitions to `sme_ratified` | The AI-curator's labels are correct as proposed, sub-clause-precise, and complete. |
| **M** | **Modify** — you supply the corrected complete label list, entry transitions to `sme_revised` | One or more labels are wrong, missing, or over-charged. You will be prompted to re-enter the COMPLETE list (not a diff). |
| **R** | **Reject** — entry transitions to `withdrawn` with required reason | The narrative itself is unsuitable as a gold-standard FIR (e.g. ambiguous facts, internal contradiction, insufficient detail). The reason you give is recorded. |
| **D** | **Defer** — entry stays `ai_curated_pending_sme`, you move on | You want to discuss this entry with another panel member or seek a precedent before committing. |
| **Q** | **Quit** — save progress and exit | End the session. Resume by re-running the CLI; you start from the next pending entry. |

## 5. Calibration cases (do these first)

Before working through the full set, please ratify these five entries first. They establish your calibration with the rest of the panel and with the AI curator's interpretation of the sub-clause precision rule.

| FIR | What it tests |
|---|---|
| `GS_0001` (Bhikhabhai theft) | Sub-clause precision (`305(a)` not `305`); proviso-as-citable-unit (`BNS 332 Provided that`); receipt-of-stolen-property (`317(2)`) at FIR stage with named suspect |
| `GS_0011` (affray) | Common intention does NOT attach in mutual-fight situations |
| `GS_0024` (child kidnapping) | Over-charging removal — `BNS 139` (kidnap to murder) was wrongly added by the model and removed by the curator |
| `GS_0038` (mob assault, 8 accused) | Unlawful-assembly chain (`189 + 190 + 191`) and the redundancy of `3(5)` once `190` is present |
| `GS_0049` (attempt to murder by fire) | Sub-clause precision on `BNS 109 → 109(1)`; companion section `BNS 85` for cruelty in a domestic context |

After these five, please mark a *calibration close* at the top of the panel discussion thread — any disagreement among reviewers should be resolved before moving on.

## 6. Throughput target

A trained legal reviewer should complete one entry in 4–6 minutes. The full 60-entry set is an 8-hour engagement spread over two sittings. Resume support is built in — there is no expectation of a single sitting.

## 7. Audit trail

Every action you take writes:
- a line to the **ratification ledger** (`backend/app/legal_sections/data/ratification_ledger.jsonl`) with diff hashes of the labels before and after, and
- an entry to the **platform audit chain** with the action code (`GOLD_RATIFIED_ACCEPT` / `_MODIFY` / `_REJECT`).

Your reviewer identity (name + bar id / employee id) is captured on every entry. The chain is immutable. This is the same compliance posture the platform uses for live IO actions on chargesheets.

## 8. Re-running and overrides

If a panel member later identifies a defect in an `sme_ratified` entry, the entry can be transitioned to `sme_revised` with a fresh reason. The full lineage is reconstructible from the ledger. Do not edit the JSONL by hand — go through the CLI.

## 9. What we will measure after ratification

After every batch of ratifications (target: every 10 entries), the engineering team re-runs the eval harness:

```
python scripts/eval_recommender.py --status sme_ratified
```

This produces:
- top-1 / top-3 / top-5 / top-10 accuracy
- sub-clause recall and precision
- over-charging and missed-charging rates

The ratified-only metrics are the trustworthy ones. They will move materially as ratification progresses, and they govern every future engineering decision (reranker fine-tune, embedder swap, special-act ingestion priority).

## 10. Contact and escalation

| Concern | Who |
|---|---|
| Statutory ambiguity on a specific section | Senior counsel on the panel |
| FIR factual ambiguity (the narrative itself is unclear) | Programme management — flag for re-write or removal |
| Tooling failure (CLI crash, save error) | Platform engineering on-call |
| Disagreement between two SME reviewers | Panel chair, then ARB if unresolved |

---

## Appendix A — Quick legal reference

| Concept | Section | Note |
|---|---|---|
| Common intention | BNS 3(5) | Charge with substantive sections when ≥ 2 accused acted in concert; **redundant with BNS 190** in unlawful-assembly cases |
| Unlawful assembly chain | BNS 189 + 190 + 191 | Required when ≥ 5 accused acted with common object |
| Theft in dwelling | BNS 305(a) | Sub-clause matters — (b) vehicle, (c) goods from vehicle, (d) idol/place of worship, (e) Govt./local authority |
| House-trespass / housebreaking | BNS 329, 330, 331(1)–(8) | Sub-section by gravity: (1) base, (2) by night, (3) with intent to commit offence, (4) night + intent, (5) preparation for hurt, (6) night + preparation, (7) causing hurt, (8) night + causing hurt |
| Hurt | BNS 114 → 115 → 117 → 118 | Definition → simple → grievous → grievous by dangerous weapon |
| Attempt to murder | BNS 109(1) | Specifically cite the sub-clause (1) — the operative limb |
| Receipt of stolen property | BNS 317(2)–(5) | Conditional charge — operative on recovery from suspect |

## Appendix B — Sub-clause precision examples

| Wrong | Right |
|---|---|
| BNS 305 | BNS 305(a) |
| BNS 331 | BNS 331(3) (or 331(4) by night) |
| BNS 109 | BNS 109(1) |
| BNS 332 | BNS 332 Provided that *(when intended offence is theft)* |
| BNS 324 | BNS 324(2) / (4) / (5) by damage value |
| BNS 351 | BNS 351(2) / (3) / (4) by threat type |

---

*End of Protocol.*
