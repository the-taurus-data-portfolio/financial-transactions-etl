# Tool/Service Feedback: financial-transactions-etl

<!-- IMPORTANT: Always add the newest feedback/session entry at the TOP of the file (immediately below this comment). Do not append to the bottom. -->

## Session: 2026-07-01 — Code Review: Citadele Bank Support

### 2. Interface & Usage Issues

1. **`_find_sample_for_bank` does not accept `skip_rows`**: The method at `bank_detector.py:140` calls `csv_utils.read_csv_header` without the `skip_rows` argument, so for any bank with `detection_header_row > 0` the sample file match will always fail. The returned `matched_sample` will always be `None`. The ETL pipeline falls back to `get_primary_sample_file` which returns the first sample, so the outcome is currently correct — but the mechanism is silently broken.

2. **`header_extractions` documented but not implemented generically**: `docs/how-to-add-bank.md` describes a `file_details.header_extractions` schema block as a declarative way to inject IBAN/currency from file header rows (with `extract_word_by_index` transform). No code path in `GenericSourceConverter` reads this key. A future bank author following the guide will find it silently ignored. The only implementation of header extraction is the `extract_header()` override in `CitadeleSourceConverter`.

3. **`config_test.yaml` contains environment-specific overrides without documentation**: `source.type` is set to `local` and `archiving.enabled` is `false`. These are functional changes that affect how CI or shared developers run tests, but neither the DESIGN doc nor any commit message explains the change.

4. **`tiller_converter.py` bypasses `schema_loader.load_config_file`**: The change at line 307–308 swaps the schema_loader call for a direct `open() + yaml.safe_load()`. No comment explains why the abstraction was bypassed.

### 3. Proposed Improvements & Backlog Items

- **BACKLOG**: Fix `_find_sample_for_bank` to pass `detection_header_row` as `skip_rows` — read it from `config.get('source_converters', {}).get(bank_type, {}).get('detection_header_row', 0)` before calling `csv_utils.read_csv_header`.
- **BACKLOG**: Either implement `header_extractions` in `GenericSourceConverter.load_source_data` (data-driven path for future banks), or remove the `header_extractions` section from `docs/how-to-add-bank.md` to avoid misleading future implementors.
- **BACKLOG**: Add a trailing newline to `config/tiller/accounts_sample.yaml`.
- **BACKLOG**: Delete `=7.0.0` from repo root; add `=*` to `.gitignore`.
- **BACKLOG**: Add a test for `_process_transfer` with a 3-word counterparty name to document the known 2-word name limitation.
