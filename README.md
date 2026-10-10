# Bank to Tiller ETL Pipeline

A flexible ETL system for converting bank transaction CSV exports from multiple Estonian banks
into Tiller Money format for Google Sheets import. Supports automatic bank detection,
deduplication against an existing Tiller sheet, and optional archiving.

## Features

- **Automatic bank detection**: identifies bank type from CSV header row at runtime
- **Multi-bank batching**: process files from different banks in one run
- **Two-step transformation**: Bank → Intermediate → Tiller for maximum flexibility
- **Schema-driven**: YAML-based schemas and mapping rules per bank
- **Deduplication**: checks Transaction IDs against existing Tiller sheet before import
- **Clipboard integration**: TSV output copied to clipboard for direct paste into Google Sheets
- **Atomic archiving**: moves processed files to archive only on 100% batch success
- **Multiple source backends**: local filesystem or Google Drive

## Supported Banks

| Bank | Language variants |
|---|---|
| Swedbank Estonia | Estonian, Russian |
| SEB Estonia | Estonian |
| LHV Estonia | Modern (16-col) and Legacy (19-col) formats |
| Luminor Estonia | Estonian |
| Citadele Estonia | Estonian |

## Quick Start

### 1. Setup

```bash
make setup
```

### 2. Configure Google Sheets (required for deduplication)

1. Create a Google Service Account at [Google Cloud Console](https://console.cloud.google.com/)
2. Enable the Google Sheets API
3. Download the JSON credentials to `config/credentials/test-spreadsheet-credentials.json`
4. Share your Tiller spreadsheet with the service account email (Viewer permission)
5. Update `config/config.yaml`:

```yaml
target_converters:
  tiller:
    deduplication:
      enabled: true
      spreadsheet_id: "your-tiller-spreadsheet-id"
      credentials_file: "config/credentials/test-spreadsheet-credentials.json"
```

### 3. Add your account mapping

Edit `config/tiller/accounts.yaml` — maps your real IBANs to Tiller account names and IDs.
See `config/tiller/accounts_sample.yaml` for the format.

### 4. Run

```bash
# Using make
make run INPUT_DIR=data/transactions

# Or directly
./venv/bin/python src/main.py --input-dir data/transactions
```

## Configuration

Key sections in `config/config.yaml`:

```yaml
source:
  type: "local"         # "local" or "gdrive"
  local:
    input_dir: "data/transactions"
  gdrive:
    input_folder_id: "your-gdrive-folder-id"

archiving:
  enabled: true
  type: "local"         # "local" or "gdrive"
  local:
    archive_dir: "data/archive"

target_converters:
  tiller:
    deduplication:
      enabled: true
      spreadsheet_id: "your-tiller-spreadsheet-id"
      worksheet_title: "Transactions"
      table_name: "Table1"
      credentials_file: "config/credentials/test-spreadsheet-credentials.json"

processing:
  copy_to_clipboard: true
```

Use `config/config_test.yaml` for development — local source, archiving disabled, no Sheets auth.

## CLI Options

```
python src/main.py --help

  --input-dir DIR     Directory containing bank CSV files (required)
  --config FILE       Config file path (default: config/config.yaml)
  --bank TYPE         Override auto-detection for all files in the batch
  --verbose, -v       Enable DEBUG-level logging
  --dry-run           Validate config and schema, skip processing
```

## Examples

```bash
# Auto-detect banks (mixed directory)
./venv/bin/python src/main.py --input-dir data/transactions

# Force a specific bank type
./venv/bin/python src/main.py --input-dir data/transactions --bank swedbank

# Dry run (validate only)
./venv/bin/python src/main.py --input-dir data/transactions --dry-run

# Sample files, no Sheets auth needed
./venv/bin/python src/main.py --input-dir data/samples/transactions --config config/config_test.yaml
```

## Testing

```bash
make test
```

Anonymised sample CSV files for all supported banks are in `data/samples/transactions/`.
These are also used as bank detection signatures at runtime.

## How Bank Detection Works

1. On startup, the pipeline reads the header row from each sample file in `config.yaml`
   and stores it as the detection signature for that bank.
2. For each input CSV, it reads the first header row and compares it against all signatures.
3. An exact match (column names, order, capitalisation) identifies the bank.
4. Falls back to `--bank` override if auto-detection fails.

The Citadele export has a 3-row metadata prefix — the sample file includes this prefix,
so detection compares against row 3 (the actual header), not row 0.

## Data Processing Flow

1. **Detect bank** from CSV header
2. **Load source data** according to bank schema (`schemas/<bank>_source.yaml`)
3. **Filter rows** (e.g. Swedbank balance rows removed by `Reatüüp` filter)
4. **Extract header metadata** if needed (e.g. Citadele IBAN and currency from row 0)
5. **Transform to intermediate format** via mapping rules (`mappings/<bank>_to_intermediate.yaml`)
6. **Post-process** if bank-specific logic is required (e.g. Citadele `OtherAccountName` extraction)
7. **Deduplicate** against existing Transaction IDs in Tiller Google Sheet
8. **Output**: CSV file + clipboard TSV
9. **Archive** source files (only if 100% of the batch succeeded)

## Adding New Banks

See [`docs/how-to-add-bank.md`](docs/how-to-add-bank.md).

## Troubleshooting

**Bank auto-detection failing**
```bash
# Check that your CSV header exactly matches the sample file (case-sensitive, same column order)
head -1 yourfile.csv
head -4 data/samples/transactions/citadele_sample_ee.csv  # row 3 is the header for Citadele

# Force a bank type to bypass detection
./venv/bin/python src/main.py --input-dir data/transactions --bank swedbank
```

**Deduplication not working**
```bash
grep -A 3 "deduplication:" config/config.yaml
grep "Transaction ID" logs/etl_pipeline.log
```

**Google Sheets access errors**
```bash
# Verify credentials
cat config/credentials/test-spreadsheet-credentials.json | python -m json.tool

# Check the spreadsheet is shared with the service account email
```

**Archiving skipped**
Archiving only runs when every file in the batch succeeds. Check the log for failed files:
```bash
grep -i "failed\|error" logs/etl_pipeline.log
```

**Debug mode**
```bash
./venv/bin/python src/main.py --input-dir data/transactions --verbose
```

## Data Privacy

- IBANs are anonymised in output (`EE123...5678` → `EE***5678`)
- All processing is local — no data leaves your machine except to your own Google Sheet
- Google Sheets access is read-only (deduplication only)

## License

Provided as-is for personal use. Ensure compliance with your bank's terms of service
when exporting transaction data.
