# Tool/Service Feedback: financial-transactions-etl

<!-- IMPORTANT: Always add the newest feedback/session entry at the TOP of the file (immediately below this comment). Do not append to the bottom. -->

## Session: 2026-11-12 — Review run 5, Tiller column structure

### 2. Interface & Usage Issues
- 3/3 files processed and archived; the process exited on its own.
- The Tiller table got 4 new columns in the middle; `schemas/tiller_target.yaml` was updated to the table order and
  the converter filled them empty without code changes. `make test` 35/35.
- `regex_extract` is listed in `docs/how-to-add-bank.md` but not implemented: the doc reads as if it exists.

### 3. Proposed Improvements & Backlog Items
- Backlog (added): fill `Card` / `Payment method` for Swedbank and LHV — draft design
  `docs/design/DESIGN-card-and-payment-method.md`.
- Docs: mark `regex_extract` as "planned" in `how-to-add-bank.md` until the design is implemented.

## Session: 2026-11-07 — Review run 4

### 2. Interface & Usage Issues
- 4/4 files processed, archived, no hang; the documented background run worked as written.
- The PDF-only account again needed hand-built rows; the user wants only its shop payments in Tiller (no cashback, no
  own transfers), which a future parser should support as a filter.

### 3. Proposed Improvements & Backlog Items
- Backlog item for the PDF parser: add the row filter above (keep the composite ids).

## Session: 2026-10-31 — Review run 3

### 2. Interface & Usage Issues
- 4/4 files processed, no hang this run; the documented background run worked as written.
- A new bank account type delivers a PDF statement only and no transaction id. Its rows were built by hand in the
  22-column format with composite ids.

### 3. Proposed Improvements & Backlog Items
- Backlog: parser for this PDF statement format. It must generate the same composite ids
  (`manual:LB<YYYYMMDD><C|D><amount in cents, 6 digits>`), or the dedup will not recognise rows inserted by hand.

## Session: 2026-10-24 — Review run 2 (agent-run pipeline)

### 2. Interface & Usage Issues
- The pipeline finished and exited on its own in 5 s this time (4/4 files); the known hang did not reproduce.
- Card pre-authorisation + refund (online grocery orders) arrive as two rows; correct, but worth a note in the docs.

### 3. Proposed Improvements & Backlog Items
- Added to `docs/backlog.md`: a `Receipt` column in the Tiller output (filled by the agent).

---

## Session: 2026-10-17 — Financial review via `skill-financial-review` (4 banks, 30 rows)

### 2. Interface & Usage Issues
- **Post-archive hang again:** log complete at 15:29:22 (`4/4 files processed`, all files archived), process had to be
  stopped. Third occurrence; the clipboard copy (`Successfully copied … to clipboard`) is the last step before it.
- **Archive overwrites same-name files** (`add_timestamp: false`): confirmed loss of archived CSVs —
  `statement (11)/(12)` (June 2026, a family member's accounts) are missing from `data/archive/`, while their rows are in Tiller.
  Luminor always exports `AccountStatement.csv`, so it has the same risk as Swedbank.
- **Luminor CSV with CR-only line endings** parsed correctly (5 → 5) — no issue, worth a test fixture.

### 3. Proposed Improvements & Backlog Items
- **Backlog (bug):** fix the post-archive hang — make the clipboard copy optional (`--no-clipboard`, default off in
  non-interactive runs) or add a timeout around it.
- **Backlog:** archiver: on a name collision add a timestamp/suffix instead of overwriting (or `add_timestamp: true`);
  then the manual rename step in the skill becomes optional.
- **Backlog (test):** fixture for a Luminor export with `\r` line endings.

---

## Session: 2026-10-10 (2) — Financial review, a family member's Swedbank accounts

Run: 2 files (Swedbank RU), 25 new rows, 2 duplicates, archive OK.

### 1. Implementation Issues
- **Hang after a successful run:** after `Archived: ...` the process never exits (waited >5 min, then killed).
  The last pipeline step before archiving is the clipboard copy (TSV), so the clipboard backend (xclip
  keeps the selection alive) is the likely cause. All outputs were already written.

### 2. Interface & Usage Issues
- The archive-overwrite workaround (rename before the run) was needed again: `statement (14) (1).csv`
  already existed in `data/archive/` with July data.

### 3. Proposed Improvements & Backlog Items
- **Backlog / bug:** make the clipboard copy optional (`--no-clipboard` or config flag, off for agent runs)
  and make it non-blocking (timeout / detached process), so `main.py` exits after archiving.
- Still open from the previous session: local archiver name collisions (suffix instead of overwrite).

## Session: 2026-10-10 — First financial review

Run: 3 files (LHV + 2× Swedbank), 40 new rows, 55 duplicates, archive OK.

### 1. Implementation Issues
- None introduced. Pre-existing behaviour noted below.

### 2. Interface & Usage Issues
- **Archive overwrites:** the local archiver silently overwrites archived files with the same name
  (`add_timestamp: false`). Swedbank exports are always `statement (N).csv`, so archived statements can be lost.
  The workaround (rename before the run) is in `docs/how-to-financial-review.md`.
- **Duplicate `TransactionID` for LHV:** LHV interest and the income tax on it get the same `TransactionID`.
  Same pattern as the Citadele fix. Accepted by the user for now.
- **Docs drift:** `Agents.md` says the production config uses a GDrive source, but `config/config.yaml` has
  `source.type: local` and local archiving.
- **Tiller IDs:** the Tiller spreadsheet ID is committed in `config/config.yaml` / `config_test.yaml`. The private
  IDs for the review are now in the git-ignored `config/local/resources.yaml`.

### 3. Proposed Improvements & Backlog Items
- **Backlog:** local archiver: on a name collision, add a suffix/timestamp instead of overwriting
  (or default `add_timestamp: true`).
- **Backlog (only if the user decides):** de-duplicate `TransactionID` within a batch generically (`-1`/`-2`
  suffix), as already done for Citadele.
- **Backlog:** fix the `Agents.md` "Configuration files" table (production source/archive type).
- **Backlog:** read the dedup `spreadsheet_id` from `config/local/` so that no private IDs are tracked in git.
