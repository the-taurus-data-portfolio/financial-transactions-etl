# Tool/Service Feedback: financial-transactions-etl

<!-- IMPORTANT: Always add the newest feedback/session entry at the TOP of the file (immediately below this comment). Do not append to the bottom. -->

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
