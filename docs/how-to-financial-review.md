# How-to: Financial Review

Recurring process: import new bank statements into the Tiller spreadsheet and resolve
transactions that Tiller AutoCat could not categorise.

The agent follows the steps below in order and stops at every **[USER]** checkpoint.
Nothing is written to the spreadsheet without explicit user confirmation.

---

## Resources

| Resource | Value |
|---|---|
| Statements source | `~/Downloads` (bank CSV exports downloaded by the user) |
| Service input dir | `data/transactions/` (`source.type: local` in `config/config.yaml`) |
| Archive | `data/archive/` (filled automatically by the service on 100% batch success) |
| Tiller spreadsheet | `tiller.*` in `config/local/resources.yaml`: tab `Transactions`, Data Table `Table1` |
| Receipts folder (GDrive) | `receipts.folder_id` in `config/local/resources.yaml` (category sub-folders inside) |
| Credentials | `config/credentials/test-spreadsheet-credentials.json` (service SA): Editor on the spreadsheet, Viewer on the receipts folder |
| Spreadsheet tool config | `config/google-spreadsheets.yaml` |

`config/local/` is git-ignored and holds the private Google resource IDs. If the file is missing,
ask the user for the IDs and recreate it. Never copy the IDs into tracked files.
| Tools | `~/ai-agents/tools/google-spreadsheets`, `~/ai-agents/tools/gdrive` |

**Credentials rule:** use only the service credentials in `config/credentials/`. Never use keys or
configs of other domains (e.g. `ai-agents/agents/domains/private/finance/`), not even for reads.
On 403 or an empty listing, ask the user to share the resource with the service SA
(`client_email` in the credentials file).

### Tool invocation

The `.venv/bin/google-spreadsheets` console script is broken (`ImportError: cannot import name 'app'`)
and the `gdrive` / `google-spreadsheets` aliases are not available in the agent shell. Call the
modules directly from the service root and always close stdin (`</dev/null`), otherwise `ls` hangs:

```bash
GS="$HOME/ai-agents/tools/google-spreadsheets/.venv/bin/python -m google_spreadsheets.cli.run \
  --config config/google-spreadsheets.yaml -c config/credentials/test-spreadsheet-credentials.json"
GD="$HOME/ai-agents/tools/gdrive/.venv/bin/python -m gdrive.cli.run \
  -c config/credentials/test-spreadsheet-credentials.json"
res() { ./venv/bin/python -c "import yaml,sys; d=yaml.safe_load(open('config/local/resources.yaml'))
for k in sys.argv[1].split('.'): d=d[k]
print(d)" "$1"; }
TBL="--entity-type table --id $(res tiller.table_id) --parent-id $(res tiller.spreadsheet_id)"
```

---

## Step 1 — Collect statements

1. List CSVs in `~/Downloads` modified since the last review (usually: today). Identify the bank
   from the header row (see the format table in `Agents.md`).
2. Compare names against `data/archive/`. Swedbank exports are named `statement (N).csv`, and the
   names repeat across downloads. The local archiver **overwrites** same-name files
   (`add_timestamp: false`).
3. Move (not copy) the files into `data/transactions/`. Rename Swedbank files to a unique name:
   `Swedbank_<IBAN>_<DD-MM-YYYY>_<DD-MM-YYYY>.csv` (period taken from the `Kuupäev` column).
   LHV / Citadele names already contain IBAN + period, so keep them as they are.

## Step 2 — Run the service

```bash
./venv/bin/python src/main.py --input-dir data/transactions
```

Check in the output / `logs/etl_pipeline.log`:
- `N/N files processed successfully` and the files moved to `data/archive/`
- the per-file `Deduplication completed: X duplicates removed, Y remaining` lines
- the resulting rows in `output/tiller_transactions.csv`

Report to the user: rows per account, duplicates skipped, anomalies noticed.
Known accepted anomalies (report, do **not** fix or add to the backlog):
- **Duplicate `Transaction ID`:** LHV interest and the income tax on it share the same
  `Transaction ID`. Inserted as-is.
- **Truncated `From / To`:** Swedbank card payments sometimes have a truncated `From / To`
  (only the address tail). The bank already sends it truncated in `Saaja/Maksja`. This is a bank
  data issue and not a service bug.

## Step 3 — Insert into Tiller

1. Read the table metadata. The column order must match the 22 columns of
   `output/tiller_transactions.csv`:
   ```bash
   $GS $TBL --task metadata --format json </dev/null
   ```
2. Build `rows.json` in the scratchpad from `output/tiller_transactions.csv`:
   - keep the service row order (account block, then date ascending)
   - `DATE` columns (`Date`, `Month`, `Week`, `Date Added`) → `YYYY-MM-DD`
     (source formats: `M/D/YYYY` for `Date`, `M/D/YY` for the others)
   - `Amount` → number; empty strings → `null`
   - **append one all-`null` row**: there must be one empty row after the inserted block
3. **[USER]** Show a summary (rows per account and period, amount sum, target position) and wait for confirmation.
4. Insert at the **top** of the table:
   ```bash
   $GS $TBL --task insert --at-row top --data-file <scratchpad>/rows.json --format json </dev/null
   ```
   A successful insert prints `[{}]`. Verify by reading the table: the first data rows are the new
   batch, then one empty row, then the previous top row.
   ```bash
   $GS $TBL --task read --format tsv </dev/null > <scratchpad>/table.tsv
   ```

## Step 4 — Resolve unclear categories

Tiller AutoCat categorises the new rows within minutes of the insert. Re-read the table first.

1. In the new batch (`Date Added` = today) select rows with category
   `Needs Clarification (Expense)` / `Needs Clarification (Income)`, plus rows with an empty category.
   Also include clarification rows left over from the previous batch.
2. List the receipts folder and its sub-folders:
   ```bash
   $GD --task ls --id "$(res receipts.folder_id)" -F json </dev/null
   ```
   - root: unprocessed scans (`Scanned_YYYYMMDD-HHMM.jpg`, invoice PDFs). The scan date is the
     scan date, not the purchase date.
   - sub-folders: processed receipts `YYYY_MM_DD_<Store>_<id>.<ext>` + a `.md` sidecar
     (items, total). Read the `.md` instead of the image when it exists.
3. Download candidates into a scratchpad sub-folder (`--task download --id <id> -o <dir>`) and
   match them by amount + date + store. The legal entity in the bank statement can differ from
   the store name on the receipt, so match by amount and date first.
4. Propose categories **only from the existing Tiller categories** (see column `Category`). Use:
   - the receipt contents (item level)
   - the payment description (transfers often state the purpose)
   - the history of the same merchant: `grep` the table TSV and count `Category`
   Mark proposals without evidence as guesses.
5. **[USER]** Present a table: date, amount, merchant, evidence, proposed category. The user updates the
   categories in the spreadsheet; do not write categories unless asked.

Also report receipts that have no matching transaction yet (they belong to the next statement)
and new rows without a category (e.g. LHV interest / fees).

---

## Session end

Update `docs/progress.md` (what was imported, open items for the next review) and the feedback files
per `agents/docs/session-hygiene.md`.
