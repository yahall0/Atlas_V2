# ADR-D15: Sub-clause precision in legal section recommendations

**Status:** Accepted
**Date:** 2026-04-19
**Deciders:** Platform Engineering Lead, ML Engineering Lead, Programme Director
**Supersedes:** none
**Superseded by:** none

---

## Context

ATLAS is used by Investigating Officers to prepare First Information Reports and chargesheets that are filed in court. The platform's section-recommendation surface, when invoked, returns the statutory provisions that the IO is advised to consider for endorsement.

In Indian criminal practice, statutory sections frequently aggregate multiple distinct fact-patterns under a single section number — the section number is an *umbrella*, not a charge. For example:

* **BNS 305** ("Theft in a dwelling house, or means of transportation or place of worship, etc.") enumerates five disjoint alternatives in clauses (a) through (e). Theft from a residence is **305(a)**; theft of a vehicle is **305(b)**; theft of an idol from a place of worship is **305(d)**. A chargesheet citing only "BNS 305" is procedurally loose and invites a court note for amendment.
* **BNS 331** carries eight numbered sub-sections, each prescribing a different punishment regime. **331(2)** applies to housebreaking *after sunset and before sunrise*; **331(3)** applies to housebreaking *in order to commit any offence punishable with imprisonment* (with a proviso extending the term to seven years if the intended offence is theft).
* **BNS 332** has lettered clauses (a)–(c) and a proviso. The proviso is itself an addressable unit that materially changes the punishment for the theft-intent case.
* **IPC 376** has nested sub-clauses going several levels deep — **376(2)(a)(i)** is meaningfully distinct from **376(2)(b)** and from **376(3)**.

The system's initial recommendation contract emitted only the umbrella section identifier (`BNS_305`). A defect identified during user evaluation in April 2026 showed that the system recommended "BNS 305" for a residential-theft case where the only chargeable form is "BNS 305(a)". The recommended endorsement, if filed verbatim, would require court correction.

In a domain where human liberty is the object of the proceedings, this is not an acceptable level of precision.

## Decision

The platform SHALL emit, render, persist and export recommendations at the **smallest applicable addressable unit** of the statute. Where a section contains addressable sub-clauses, the recommendation SHALL identify the matching sub-clause(s) and SHALL NOT default to the umbrella section.

This is implemented as the following binding contract.

### 1. Data layer
The verbatim section corpus (`backend/app/legal_sections/data/{ipc,bns}_sections.jsonl`) SHALL include, for every section, a `sub_clauses` array decomposing the section into addressable sub-units. The shape of each entry is defined in [Data Dictionary §18.3](../solution_design/02_data_dictionary.md#183-sub-clause-records-legal_sectionssub_clauses-json-shape).

The decomposition SHALL recognise the following marker shapes:

| Shape | Examples | Scheme |
|---|---|---|
| Numbered | `(1)`, `(2)`, … `(99)` | `num` |
| Lettered (lower) | `(a)`, `(b)`, … `(z)` | `alpha_lower` |
| Lettered (upper) | `(A)`, `(B)`, … | `alpha_upper` |
| Roman (lower) | `(i)`, `(ii)`, `(iii)`, … | `roman_lower` |
| Roman (upper) | `(I)`, `(II)`, … | `roman_upper` |
| Ordinal | `First.`, `Secondly.`, `Thirdly.` … | `ordinal` |
| Proviso | `Provided that`, `Provided further that`, `Provided also` | `proviso` |

Single-character ambiguous tokens (`i`, `v`, `x`, `l`, `c`, `d`, `m` and uppercase) SHALL be classified using context: if the immediately preceding marker at the same nesting level is the alphabetical predecessor (e.g. `(h)` then `(i)`), the token is the letter; otherwise it is a Roman numeral.

Provisos SHALL be first-class addressable units, citable as `<section> Proviso` (or with the full opening phrase, e.g. `BNS 332 Provided that`).

### 2. Retrieval layer
The chunker SHALL emit one chunk per sub-clause when sub-clauses exist. Each chunk's metadata SHALL carry the parent `section_id`, the `canonical_citation`, and the `addressable_id`, so that retrieval and aggregation operate at sub-clause granularity without re-parsing.

### 3. Recommendation contract
The `SectionRecommendation` schema (defined in `backend/app/legal_sections/schemas.py` and reflected in [API Reference §12](../solution_design/03_api_reference.md#12-section-recommendation-sprint-6)) SHALL include the fields `sub_clause_label`, `canonical_citation` and `addressable_id`.

The following rules are binding:

| Rule | Statement |
|---|---|
| RC-01 | If the matched section contains zero addressable sub-clauses, `sub_clause_label` SHALL be `null` and `canonical_citation` SHALL be the section header form (e.g. `BNS 379`). |
| RC-02 | If the matched section contains addressable sub-clauses, the recommender SHALL identify the smallest matching unit. Returning the umbrella section is a defect. |
| RC-03 | When more than one sibling sub-clause matches, each SHALL be emitted as a separate recommendation entry. The parent `section_id` is shared; `canonical_citation` differs. |
| RC-04 | `rationale_quote` SHALL be the verbatim text of the cited sub-clause, including the marker. It SHALL NOT be the umbrella section header. |
| RC-05 | Provisos are first-class addressable units. They SHALL be emitted with `canonical_citation = "<section> Proviso"` (or the full proviso opening phrase). |
| RC-06 | The IO interface SHALL render `canonical_citation` verbatim in the chargeable list and in any document export. |

### 4. Quality gate
The verifier `python scripts/verify_legal_sections.py` SHALL exit with status `0` and the `all_sub_clause_checks_pass` field SHALL be `true` before any release that affects the corpus, the parser, the chunker, or the recommender. The verifier asserts the presence of each canonical citation in the parsed `sub_clauses` for the sections enumerated in `SUBCLAUSE_CHECKS`.

The unit-test suite at `backend/tests/legal_sections/test_subclause_parser.py` is the regression gate at the parser level. All 22 cases SHALL pass on every release branch.

### 5. Audit
Every recommendation acceptance, modification or dismissal SHALL be recorded in the audit chain with the `canonical_citation` exactly as emitted. This preserves traceability of the chargeable form across investigation, prosecution and appeal.

## Consequences

### Positive
* Chargeable lists produced by the platform are filing-ready without manual sub-clause inference.
* Court audits can trace any recommendation back to a specific sub-clause and the verbatim source text.
* The recommender's accuracy can be measured at sub-clause precision, not section-only precision — a more honest and stricter benchmark.
* Statutory amendments that change a single sub-clause can be ingested without a corpus rebuild — the parser identifies the affected `addressable_id` and the chunker rebuilds only that chunk.

### Negative
* Increased corpus volume (≈487 IPC + ≈839 BNS sub-clauses are now addressable units in addition to the 943 base sections).
* Recommender output volume grows proportionally; the IO interface must group sibling sub-clauses under their parent for readability.
* Parser maintenance burden: new statutory drafting conventions (e.g. the `(AA)` enumeration in some special acts, sub-paragraphs marked `(I)(a)`) must be added to the parser as encountered. This is mitigated by the verifier and unit-test gate.

### Operational
* Backwards-incompatible change to `SectionRecommendation` schema. Frontend update is required to render the new fields. The transition is internal to ATLAS — no external API consumers exist at the date of this ADR.

## Implementation references

| Concern | Path |
|---|---|
| Parser | `backend/app/legal_sections/subclause_parser.py` |
| Schemas | `backend/app/legal_sections/schemas.py` |
| Extraction | `scripts/extract_legal_sections.py` |
| Verifier | `scripts/verify_legal_sections.py` |
| Unit tests | `backend/tests/legal_sections/test_subclause_parser.py` |
| Module README | `backend/app/legal_sections/README.md` |
| Data Dictionary | `docs/solution_design/02_data_dictionary.md` §18.3 |
| API Reference | `docs/solution_design/03_api_reference.md` §12 |

## Validation status at acceptance

* `python scripts/verify_legal_sections.py` → `OVERALL: PASS`
* `pytest backend/tests/legal_sections/test_subclause_parser.py` → 22 passed, 0 failed
* Corpus: 511 IPC base + 74 letter variants = 585 sections; 358 BNS sections; 487 IPC sub-clauses across 98 sections; 839 BNS sub-clauses across 151 sections.
