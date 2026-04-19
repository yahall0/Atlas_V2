# ATLAS Platform — Progress Log

**Date:** 2026-04-19
**Branch:** `claude/sleepy-sanderson-ae8ad3`
**Scope:** Delete-FIR / delete-chargesheet capability + FIR-extraction regression fixes

---

## T1: Delete capability for FIRs and charge-sheets

### T1.1 Backend — DELETE endpoints

**Files**

- [`backend/app/api/v1/firs.py`](../backend/app/api/v1/firs.py) — added `DELETE /api/v1/firs/{fir_id}` (`delete_fir_endpoint`)
- [`backend/app/api/v1/chargesheet.py`](../backend/app/api/v1/chargesheet.py) — added `DELETE /api/v1/chargesheet/{cs_id}` (`delete_chargesheet_endpoint`)
- [`backend/app/db/crud_fir.py`](../backend/app/db/crud_fir.py) — added `delete_fir(conn, fir_id, district)` CRUD
- [`backend/app/db/crud_chargesheet.py`](../backend/app/db/crud_chargesheet.py) — added `delete_chargesheet(conn, cs_id, district)` CRUD

**RBAC**

| Role     | DELETE FIR | DELETE chargesheet | Notes                              |
|----------|-----------|--------------------|------------------------------------|
| IO       | no        | no                 | line workers cannot delete         |
| SHO      | yes\*     | yes\*              | \*district-scoped                  |
| DYSP     | yes       | yes                |                                    |
| SP       | yes       | yes                |                                    |
| ADMIN    | yes       | yes                |                                    |
| READONLY | no        | no                 |                                    |

District scoping reuses the existing `_district_for(user)` helper — for SHO, the WHERE clause includes `AND district = %s` so a SHO from one district cannot delete a FIR registered in another.

**Audit chain**

`DELETE /firs/{id}` writes a `delete_fir` row to `audit_log` **before** the cascade fires. The audit row outlives the deleted FIR (resource_id is the soon-to-be-gone UUID, captured for forensic reconstruction). `details` carries `{"fir_number": "<value>"}` so the audit row remains human-readable.

**Cascade behaviour**

The DELETE fires existing PostgreSQL FK cascades end-to-end. No new FK or trigger added — only the append-only-trigger guards needed widening (see T1.2).

```
firs                         (root)
├─ complainants              ON DELETE CASCADE  (since 001)
├─ accused                   ON DELETE CASCADE  (since 001)
├─ property_details          ON DELETE CASCADE  (since 001)
├─ chargesheet_mindmaps      ON DELETE CASCADE  (since 009)
│  └─ mindmap_nodes          ON DELETE CASCADE  (since 009)
│     └─ mindmap_node_status ON DELETE CASCADE  (since 009; trigger-gated, see T1.2)
├─ chargesheets              ON DELETE SET NULL (since 005) ← chargesheets persist
├─ validation_reports        ON DELETE SET NULL (since 006)
└─ evidence_gap_reports      ON DELETE SET NULL (since 007)

chargesheets                 (root)
├─ validation_reports        ON DELETE CASCADE  (since 006)
├─ evidence_gap_reports      ON DELETE CASCADE  (since 007)
├─ audit_log_chargesheet     ON DELETE CASCADE  (since 008)
├─ recommendation_actions    ON DELETE CASCADE  (since 008)
└─ chargesheet_gap_reports   ON DELETE CASCADE  (since 010)
   └─ chargesheet_gap_actions ON DELETE CASCADE (since 010; trigger-gated, see T1.2)
```

The intentional asymmetry — chargesheets become orphaned (`fir_id = NULL`) when their parent FIR is deleted — preserves the prosecution record even after a FIR is purged.

### T1.2 Migrations 014 & 015 — append-only trigger escape hatches

**Problem.** Migrations 009 and 010 installed `BEFORE DELETE` triggers on `mindmap_node_status` and `chargesheet_gap_actions` that raise `EXCEPTION 'is append-only'` for every DELETE. That guard is the right default — both tables are audit ledgers and must never be silently mutated. But it also blocks the cascade path triggered by `DELETE FROM firs` and `DELETE FROM chargesheets`.

**Decision.** Carve a narrow, opt-in escape hatch using a session-scoped GUC rather than disabling the trigger or dropping rows manually in application code. The CRUD layer sets `SET LOCAL atlas.allow_status_delete = 'on'` inside the DELETE transaction; the trigger function checks the GUC and lets the row through only when it is set. Outside that one transaction the append-only invariant continues to hold.

**Migrations**

- [`backend/alembic/versions/014_allow_cascade_delete_status.py`](../backend/alembic/versions/014_allow_cascade_delete_status.py) — rewrites `reject_mindmap_status_mutation()`
- [`backend/alembic/versions/015_allow_cascade_delete_gap_actions.py`](../backend/alembic/versions/015_allow_cascade_delete_gap_actions.py) — rewrites `reject_gap_action_mutation()`

Both trigger functions now read:

```sql
IF TG_OP = 'DELETE'
   AND current_setting('atlas.allow_status_delete', true) = 'on' THEN
  RETURN OLD;
END IF;
RAISE EXCEPTION '<table> is append-only: % operations are prohibited', TG_OP;
```

The CRUD layer pairs the migration:

```python
# backend/app/db/crud_fir.py:delete_fir
with conn:
    with _dict_cursor(conn) as cur:
        cur.execute("SET LOCAL atlas.allow_status_delete = 'on'")
        cur.execute("DELETE FROM firs WHERE id = %s ...", (fir_id, ...))
```

`SET LOCAL` is bound to the active transaction — the GUC reverts automatically on commit/rollback, so the bypass cannot leak to a subsequent query on the same psycopg2 connection.

**Verification (against live atlas_v2 database)**

```
BEGIN; SET LOCAL atlas.allow_status_delete='on';
DELETE FROM firs WHERE id='f8be98eb-...' RETURNING id, fir_number;
ROLLBACK;
→ DELETE 1   (cascade through 361 mindmap_nodes + 14 mindmap_node_status rows; rolled back)

BEGIN;
DELETE FROM firs WHERE id='f8be98eb-...';
→ ERROR: mindmap_node_status is append-only: DELETE operations are prohibited
ROLLBACK;
```

Both invariants hold: cascade succeeds with the GUC, trigger rejects without it.

### T1.3 Frontend — delete buttons and confirmation

**Files**

- [`frontend/src/app/dashboard/fir/[firId]/page.tsx`](../frontend/src/app/dashboard/fir/[firId]/page.tsx) — header **Delete FIR** button + modal
- [`frontend/src/app/dashboard/fir/page.tsx`](../frontend/src/app/dashboard/fir/page.tsx) — inline trash button per row + `window.confirm`
- [`frontend/src/app/dashboard/chargesheet/[id]/page.tsx`](../frontend/src/app/dashboard/chargesheet/[id]/page.tsx) — header **Delete** button + modal
- [`frontend/src/app/dashboard/chargesheet/page.tsx`](../frontend/src/app/dashboard/chargesheet/page.tsx) — inline trash button per row + `window.confirm`

**UX choices**

- **Detail page** uses an in-page modal with full destructive-action copy (lists what gets deleted) and disables the Cancel button while the request is in flight.
- **List page** uses `window.confirm` for the inline action — fewer clicks for the common case, no modal layout to manage when many rows are visible.
- After a successful delete, the detail page redirects to the list view; the list page filters the row out of local state without a re-fetch.

**Common helper.** Both call `apiClient(\`/api/v1/firs/${id}\`, { method: 'DELETE' })`. The existing `apiClient` already returns `res.json()` on 200, so the endpoint deliberately returns `{ deleted: true, fir_id: ... }` rather than 204 No Content.

---

## T2: FIR extraction regression fixes

User report: a freshly-uploaded FIR (`13 FIRST INFORMATION REPORT.pdf`) rendered in the UI with title `FIR ST` and police station `કેરાલા જી.આઈ. Ye 20 FIR [પ4 11192006250 Date 26/01/20`.

### T2.1 Root cause

Both bugs sit in [`backend/app/ingestion/fir_parser.py`](../backend/app/ingestion/fir_parser.py).

| Field             | Symptom                                                                                                                | Root cause                                                                                                                                                        |
|-------------------|------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `fir_number`      | Captured `"ST"` instead of `"11192006250014"`                                                                          | Tesseract read `FIRN` as `FIR [` (the `N` came through as a stray bracket). Primary regex `\bFIRN\s*([\d]+)` missed; fallback `F\.?I\.?R\.?\s*([A-Z0-9/\-]+)` matched the document title `FIRST INFORMATION REPORT` and captured the `ST` after `FIR`. |
| `police_station`  | Captured the entire row-1 header (`કેરાલા જી.આઈ. Ye 20 FIR [પ4 11192006250 Date 26/01/20`)                              | Primary regex's character class `[\u0A80-\u0AFF\s]` excludes the `.` in abbreviations like `કેરાલા જી.આઈ.`, so it failed to match. Fallback-1's `[^\n\(]+` then greedily ate the rest of the row up to the next newline. |

The eGujCop form layout splits the row-1 header cell across two OCR lines:

```
1 Distric અમદાવાદગ્રા Polic કેરાલા જી.આઈ. Ye 20 FIR [પ4 11192006250 Date 26/01/20
t મ્ય      e Sta ડી.સી.       ar 25      ૦. 014 (તારીખ 25
```

True values: District `અમદાવાદગ્રામ્ય`, PS `કેરાલા જી.આઈ.ડી.સી.`, FIR `11192006250014`, Date `26/01/2025`. The district extractor already stitched the head + tail correctly; the police-station extractor did not.

### T2.2 Fix

**`_extract_fir_number`**

1. Added a no-N variant that runs when the FIRN regex misses:

   ```python
   m = re.search(r"\bFIR\b.{0,10}?(\d{10,15})\s+Date\b", text, re.IGNORECASE)
   ```

   The `Date` lookahead anchors the match to the header cell so it cannot pick up `FIRST` from the document title. The `{10,15}` digit constraint rejects short-digit false positives.

2. Tightened the `F.I.R. No.` fallback to require an explicit `No.` / `Number` qualifier — the prior regex made the qualifier optional, which is what allowed `FIRST` → `ST`.

**`_extract_police_station`**

1. Permitted `.` inside the captured Gujarati run so abbreviations such as `જી.આઈ.` survive:

   ```python
   r"Polic\s+([\u0A80-\u0AFF][\u0A80-\u0AFF.\s]*?)\s+(?:Ye|Year)\b"
   ```

2. Added second-line tail stitching modelled on `_extract_district`:

   ```python
   r"e\s+Sta\b[\s\u0A80-\u0AFF.]*?([\u0A80-\u0AFF][\u0A80-\u0AFF.]*)\s+ar\b"
   ```

   When the head ends in a period (abbreviation), the tail is concatenated without a separator (`જી.આઈ.` + `ડી.સી.` → `જી.આઈ.ડી.સી.`); otherwise a single space is inserted.

3. Deleted the over-greedy Fallback-1 (`Distric...Polic\w*\s+([^\n\(]+)`) which was the actual source of the garbage capture. Two narrower fallbacks remain (English `Police Station` label, Gujarati `સ્ટેશન` label).

### T2.3 Verification

Re-ran the new parser against three FIRs already in the database:

| FIR    | Old `fir_number` | New `fir_number` | Old `police_station`                                                       | New `police_station`        |
|--------|------------------|------------------|----------------------------------------------------------------------------|-----------------------------|
| 13     | `ST`             | `11192006250014` | `કેરાલા જી.આઈ. Ye 20 FIR [પ4 11192006250 Date 26/01/20`                    | `કેરાલા જી.આઈ.ડી.સી`        |
| 35     | `11192029250035` | `11192029250035` | `કોઠ`                                                                      | `કોઠ` (unchanged)            |
| 10     | `11192050250010` | `11192050250010` | `સાણંદ`                                                                    | `સાણંદ` (unchanged)          |

The broken FIR 13 row was repaired in-place by re-running `parse_fir_text` against its stored `raw_text` and updating the row.

### T2.4 Known limitations carried forward

- **FIR 35 PS truncated to `કોઠ`** (true name `કોઠારિયા`): the OCR pass simply did not read the rest of the cell, and the second OCR line has no Gujarati text between `e Sta` and `ar` to stitch on. Cannot be fixed in the regex layer.
- **Remediation paths**: install `poppler` + `pdf2image` for 300-DPI rendering inside the backend container (preferred), or trial an alternate Gujarati OCR engine (e.g. PaddleOCR-Gujarati). Both are out of scope for this change.

---

## T3: Container deployment

```
Migration: 013 → 014 → 015          (alembic upgrade head, run by entrypoint.sh)
Backend image: rebuilt 2026-04-19
Frontend image: rebuilt 2026-04-19
Compose project: atlas_v2  (worktree-mounted via -p atlas_v2)
```

Backend `entrypoint.sh` runs `alembic upgrade head` before serving, so a `docker compose up -d backend` is enough — migrations are not a separate step.

---

## File summary

**Created**

- `backend/alembic/versions/014_allow_cascade_delete_status.py`
- `backend/alembic/versions/015_allow_cascade_delete_gap_actions.py`
- `docs/progress_19April2026_delete_and_parser.md` (this file)

**Modified — backend**

- `backend/app/api/v1/firs.py` — DELETE endpoint, audit-log row
- `backend/app/api/v1/chargesheet.py` — DELETE endpoint
- `backend/app/db/crud_fir.py` — `delete_fir` CRUD with GUC bypass
- `backend/app/db/crud_chargesheet.py` — `delete_chargesheet` CRUD with GUC bypass
- `backend/app/ingestion/fir_parser.py` — `_extract_fir_number` and `_extract_police_station` rewrites

**Modified — frontend**

- `frontend/src/app/dashboard/fir/[firId]/page.tsx`
- `frontend/src/app/dashboard/fir/page.tsx`
- `frontend/src/app/dashboard/chargesheet/[id]/page.tsx`
- `frontend/src/app/dashboard/chargesheet/page.tsx`

---

## Follow-up items (not in scope today)

1. **Push branch** `claude/sleepy-sanderson-ae8ad3` to `yahall0/Atlas_V2` (currently blocked on write permissions).
2. **OCR upgrade** to 300-DPI `pdf2image` path so PS names like `કોઠારિયા` survive intact.
3. **Soft-delete option** — current implementation is a hard delete. If the police department's records-retention policy requires keeping deleted FIRs for N years, swap the DELETE for an `UPDATE firs SET deleted_at = now()` and adjust list/get queries to filter `deleted_at IS NULL`.
4. **Bulk delete** — power users may want multi-row selection on the list pages; deferred until a real workflow request surfaces.
