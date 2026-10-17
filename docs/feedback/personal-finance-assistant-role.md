# Tool/Service Feedback: financial-transactions-etl

<!-- IMPORTANT: Always add the newest feedback/session entry at the TOP of the file (immediately below this comment). Do not append to the bottom. -->

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
