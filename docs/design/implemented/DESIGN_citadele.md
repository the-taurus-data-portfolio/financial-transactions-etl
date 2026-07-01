# Design: Citadele Bank Support

**Status: implemented**

## Pre-implementation checklist

One manual step must be completed before starting implementation:

- [ ] **Create Tiller account** — add the Citadele account manually in Tiller Money web app,
  copy the Account ID it assigns, use it in `config/tiller/accounts.yaml`.
  (Encoding is confirmed `us-ascii` / UTF-8 compatible — no action needed.)

---

## Analysis of Statement-Citadele-*.csv

| Property              | Value                                                                 |
|-----------------------|-----------------------------------------------------------------------|
| Delimiter             | `\|` (pipe)                                                           |
| Encoding              | `us-ascii` (UTF-8 compatible)                                         |
| Date format           | `DD.MM.YYYY`                                                          |
| Decimal separator     | `.` (standard — sign is embedded in the value, e.g. `-7.20`)         |
| Skip header rows      | `3` — rows 0–2 are file metadata; actual column headers are at row 3 |
| Footer rows           | Present — several rows at end with empty `Date` column               |
| Account IBAN in export| **Row 0, col 1** — `"EUR EE52XXXXXXXXXXXX"` format (not per-row)     |
| Currency in export    | **Row 0, col 1** — prefix before IBAN, e.g. `"EUR ..."` (always EUR) |
| Per-row counterparty  | Not a dedicated column — extracted from `Narrative` via regex        |

### File structure

```
Row 0  "Account"|"EUR EE52XXXXXXXXXXXX"
Row 1  "From"|"26.06.2026"|"to"|"30.06.2026"
Row 2  |||||"Opening balance:"|"X.XX"
Row 3  "Date"|"Type"|"Narrative"|"Payment No."|"Bank Reference"|"Reference number"|"Amount DR/Amount CR"
Row 4+ transaction data rows
...    |||||"Closing Balance:"|"X.XX"   ← footer (empty Date column, filtered out)
```

### Columns

| # | Column name              | Maps to intermediate   | Notes                                                      |
|---|--------------------------|------------------------|------------------------------------------------------------|
| 0 | `Date`                   | `TransactionDate`      | `direct_copy` (DD.MM.YYYY stays)                           |
| 1 | `Type`                   | —                      | Not mapped; available to `post_process` via the source DataFrame argument              |
| 2 | `Narrative`              | `Description`          | `string_clean`                                             |
| 2 | `Narrative`              | `OtherAccountName`     | `post_process` — extracted and cleaned by `CitadeleSourceConverter` |
| 3 | `Payment No.`            | —                      | Not mapped                                                 |
| 4 | `Bank Reference`         | `TransactionID`        | `prefix_string` with prefix `"CT"`                        |
| 5 | `Reference number`       | —                      | Not mapped                                                 |
| 6 | `Amount DR/Amount CR`    | `Amount`               | `direct_float` — already a signed decimal (e.g. `-7.20`)  |
| — | (file row 0, col 1)      | `BudgetAccountNumber`  | `header_extraction` → `anonymize_iban`                    |
| — | (file row 0, col 1)      | `Currency`             | `header_extraction`, first word → `"EUR"`                 |

### Transaction types and Narrative patterns

All transaction types share the same 7-column structure. No type-based row filtering needed.
`post_process` strips tokens sequentially; purchases are detected structurally, not by payment-comment keywords.

**Transfers** (`INWARD TRANSFER`, `OUTWARD TRANSFER`, `INWARD INSTANT PAYMENT`):

Token sequence:
```
<PHRASE> <NAME> <ISIKUKOOD_11D> <SWIFT_BIC> <COUNTERPARTY_IBAN> [End to end ID: NOTPROVIDED]
```

| Token | Disposition |
|---|---|
| `PHRASE` | keep → `Description` |
| `NAME` (2 words) | → `OtherAccountName` (last 2 tokens of cleaned string after all stripping) |
| `ISIKUKOOD_11D` (11 digits) | PII — strip |
| `SWIFT_BIC` | strip |
| `COUNTERPARTY_IBAN` | strip (future: `OtherAccountIBAN`) |
| `End to end ID: ...` | strip |

`OtherAccountName` = last 2 words of cleaned string (2-word personal name assumed).
`Description` = cleaned string minus those 2 trailing words.

**Card purchases** (`PURCHASE`):

Token sequence:
```
<CARD_DATE> <MASKED_CARD> MCC-<MCC> REF: <REF_NUM> <REMAINDER>
```

| Token | Examples | Disposition |
|---|---|---|
| `CARD_DATE` | `DD/MM/YYYY` (may differ from settlement `TransactionDate`) | → `Description` prefix |
| `MASKED_CARD` | `NNNNNN******NNNN` | reserved for future card-identification field; strip |
| `MCC-<MCC> REF: <REF_NUM>` | `MCC-NNNN REF: NNNN` | strip |
| `REMAINDER` | merchant name + location + country + bank ref | → `OtherAccountName` as-is |

`OtherAccountName` = everything that remains after stripping `CARD_DATE`, `MASKED_CARD`, `MCC-...`, and `REF: ...`.
No further parsing of location/country/bank ref — kept in `OtherAccountName` for now.

`Description` = `"<CARD_DATE>: <REMAINDER>"`.

**Processing in `post_process`**: universal strip passes run on all rows first. Purchase detection is structural (cleaned `Description` starts with card date `DD/MM/YYYY`). No language-keyword branching.

---

## Files to create / modify

### 1. `schemas/citadele_source.yaml` (NEW)

Source schema for Citadele exports. Key `file_details` additions over existing banks:
- `delimiter: "|"`
- `skip_header_rows: 3` — converter passes `skiprows=3` to `pd.read_csv`

No `header_extractions` block needed — IBAN and currency extraction is handled by
`CitadeleSourceConverter.extract_header()` (see code changes below).

Required columns: `Date`, `Amount DR/Amount CR`.
Optional: `Narrative`, `Bank Reference`, `Type`, `Payment No.`, `Reference number`.

### 2. `mappings/citadele_to_intermediate.yaml` (NEW)

Filters:
- `field: "Date"`, `operator: "not_empty"` — removes footer rows with empty Date.

Field mappings:

| Source field          | Target field          | Transformation                                              |
|-----------------------|-----------------------|-------------------------------------------------------------|
| `Date`                | `TransactionDate`     | `direct_copy`                                               |
| `Amount DR/Amount CR` | `Amount`              | `direct_float` — parse signed decimal, `.` as separator    |
| `Narrative`           | `Description`         | `string_clean`                                              |
| `Bank Reference`      | `TransactionID`       | `prefix_string` with prefix `"CT"`                         |
| `AccountIBAN`         | `BudgetAccountNumber` | `anonymize_iban` (same rules as SEB/Luminor)               |
| `Currency`            | `Currency`            | `direct_copy`                                               |

`OtherAccountName` is NOT mapped here — it is populated by `CitadeleSourceConverter.post_process()`
after the standard field mapping runs.

`AccountIBAN` and `Currency` are virtual columns injected into the DataFrame by
`CitadeleSourceConverter.extract_header()` before the main CSV load.

### 3. `data/samples/transactions/citadele_sample_ee.csv` (NEW)

A hand-crafted sample file **without** the 3-row file metadata prefix — starts directly at
the column header row. This is intentional: the bank detector reads the first line of the
sample file, so the sample must start with the actual column headers to produce a stable,
IBAN-independent signature for detection.

Header row must be:
```
"Date"|"Type"|"Narrative"|"Payment No."|"Bank Reference"|"Reference number"|"Amount DR/Amount CR"
```

Include at least 2–3 representative rows (one transfer, one card purchase) with anonymized
`Bank Reference` values.

### 4. `config/tiller/accounts.yaml` (MODIFY)

**Prerequisite — manual step required before implementing this file:**
Add the Citadele account in Tiller Money web app, copy the Account ID.

Add entry. The `account_anonymized_iban` is derived automatically from the file header during
pipeline execution — run the pipeline once on the real file and check the intermediate output's
`BudgetAccountNumber` column for the exact value to use here:

```yaml
- account_name: "Citadele Main"
  account_anonymized_iban: "EE***NNNNN"   # verify after first pipeline run
  bank: "Citadele"
  tiller_account_id: "manual:fe8bf6fc-cde0-4885-ad59-7cb92a5c71ff"
```

### 5. `config/tiller/accounts_sample.yaml` (MODIFY)

Add a fake entry to keep the public sample consistent:
```yaml
- account_name: "Test account (Citadele)"
  account_anonymized_iban: "EE***00006"
  bank: "Citadele"
  tiller_account_id: "manual:00000000-0000-0000-0000-000000000006"
```

### 6. `config/config.yaml` (MODIFY)

Add under `source_converters`:
```yaml
citadele:
  source_schema: citadele_source.yaml
  mapping: citadele_to_intermediate.yaml
  sample_files:
    - "data/samples/transactions/citadele_sample_ee.csv"
```

### 7. `config/config_test.yaml` (MODIFY)

Same `citadele:` block as `config.yaml` — needed to run a test pipeline pass:
```yaml
citadele:
  source_schema: citadele_source.yaml
  mapping: citadele_to_intermediate.yaml
  sample_files:
    - "data/samples/transactions/citadele_sample_ee.csv"
```

---

## Code changes required

Unlike Luminor (purely data-driven, zero code changes), Citadele requires changes across
three layers: the parent interface, the generic converter, and a new Citadele-specific subclass.
All additions are designed so existing banks are unaffected.

### `src/core/interfaces.py`

Add three hook methods to the `SourceConverter` abstract base class (or as concrete no-ops
on the base if the ABC is strict):

**`extract_header(file_content: io.BytesIO) -> dict`**
Default: returns `{}`. Called by `load_source_data` before the main CSV parse. The returned
dict is injected as constant columns into the loaded DataFrame.

**`extract_footer(file_content: io.BytesIO) -> dict`**
Default: returns `{}`. Reserved for future use (e.g. extracting closing balances or totals
from file footer rows). Called by `load_source_data` after the main CSV parse.

**`post_process(intermediate_df: pd.DataFrame, source_df: pd.DataFrame) -> pd.DataFrame`**
Default: returns `intermediate_df` unchanged. Called by `process_content` after `transform_to_intermediate`.
Receives both DataFrames so subclasses can read any source column (e.g. `Type`) without mapping it into the intermediate schema.

### `src/converters/generic_source_converter.py`

**1. `load_source_data` — `skip_header_rows` + hook calls**

- Read `skip_header_rows` from `file_details`; pass as `skiprows` to `pd.read_csv` (default `0`).
- Call `self.extract_header(file_content)` and inject the returned dict as constant columns
  into the DataFrame after the main CSV parse.
- Call `self.extract_footer(file_content)` similarly (inject or store for future use).

**2. `process_content` — call `post_process`**

After `transform_to_intermediate`, call `result_df = self.post_process(result_df, source_df)` before
returning. The default no-op means all existing converters are unaffected.

**3. `_apply_transformation` — add `direct_float` type**

New type: applies `parse_amount` directly to the series. Used when the amount is already a
signed `.`-decimal string (`-7.20`, `100.00`) and no sign manipulation is needed.

**4. `filter_rows` — add `not_empty` operator**

New operator: keeps rows where `str(value).strip() != ""`. Used to remove footer rows with
an empty date column.

### `src/converters/citadele_source_converter.py` (NEW)

New class `CitadeleSourceConverter(GenericSourceConverter)`.

**`extract_header(file_content) -> dict`**

Reads the raw bytes before the main CSV parse. Seeks to start, reads line 0, parses it with
the file's delimiter (`|`), takes column 1 (e.g. `"EUR EE52XXXXXXXXXXXX"`). Splits by space:
- index 0 → `Currency` value (e.g. `"EUR"`)
- index -1 → `AccountIBAN` value (the full IBAN string)

Returns `{"AccountIBAN": <iban>, "Currency": <currency>}`.

**`post_process(df) -> pd.DataFrame`**

Runs after the standard field mappings. At this point `Description` holds the cleaned
Narrative text. This method:

Processes each row based on the `Type` column value (`PURCHASE`, `INWARD INSTANT PAYMENT`, `OUTWARD TRANSFER`, `INWARD TRANSFER`).
Reads `Type` from `source_df` (not mapped in intermediate). No single large regex; each pass strips one known token type.

---

**Transfer rows** — `Type` is `INWARD INSTANT PAYMENT`, `OUTWARD TRANSFER`, or `INWARD TRANSFER`.

Strip tokens sequentially, then extract name from what remains:

| What to strip | How to identify | Disposition |
|---|---|---|
| `End to end ID: ...` suffix | literal prefix `End to end ID:`, rest of string | skip |
| IBAN | country code (2 letters) + 2 check digits + 10+ alphanumeric chars | skip (future: `OtherAccountIBAN`) |
| BIC/SWIFT | 8–11 char token with `EE` at positions 5–6 (avoids false matches on 8-char names) | skip |
| Estonian personal/company code | exactly 11 consecutive digits — isikukood (PII) | skip |

After stripping and collapsing whitespace, the last 2 words of the cleaned string are the counterparty name.

`OtherAccountName` = last 2 words (personal name assumed: 2 words — known limitation for org names).
`Description` = cleaned string minus those 2 trailing words.

---

**Purchase rows** — `Type` is `PURCHASE`.

Strip tokens sequentially, then extract card date and merchant from what remains:

| What to strip | How to identify | Disposition |
|---|---|---|
| `End to end ID: ...` suffix | literal prefix (rare in purchases) | skip |
| `MCC-NNNN` | literal `MCC-` followed by digits | skip |
| `REF: NNNN` | literal `REF:` followed by digits | skip |
| Masked card number | `NNNNNN******NNNN` format | skip |

Card date = first token (`DD/MM/YYYY`); moved to `Description` prefix.
`OtherAccountName` = everything remaining after the 4 strips above (includes location, country, bank ref — acceptable for now).
`Description` = `"<card_date>: <OtherAccountName>"`.

### Factory / converter instantiation

Wherever `GenericSourceConverter` is constructed for a given bank type (likely in
`etl_pipeline.py` or a factory function), add a mapping so that `bank_type == "citadele"`
instantiates `CitadeleSourceConverter` instead of `GenericSourceConverter`. All constructor
arguments remain the same.

### `src/utils/csv_utils.py`

**`_read_header_from_file_object` — add `|` to delimiter candidates**

Append `'|'` to the `[';', ',', '\t']` list so pipe-delimited sample files are correctly
parsed by the bank detector signature loader.

---

## Differences vs existing banks

| Aspect                 | Citadele                          | Luminor (closest match)          |
|------------------------|-----------------------------------|----------------------------------|
| Delimiter              | `\|` (pipe)                       | `;`                              |
| Skip header rows       | `3` (metadata prefix)             | `0` (no metadata prefix)         |
| Date field name        | `Date`                            | `Väärtuspäev`                    |
| Date format            | `DD.MM.YYYY`                      | `DD.MM.YYYY`                     |
| Amount field           | `Amount DR/Amount CR`             | `Summa`                          |
| Amount sign            | Embedded (`-7.20`)                | Separate `Deebet/krediit` column |
| Amount decimal sep.    | `.`                               | `,`                              |
| Currency source        | File header row 0 (`extract_header`)    | Per-row `Valuuta` column         |
| Account IBAN source    | File header row 0 (`extract_header`)    | Per-row `Konto` column           |
| Row filter             | `not_empty` on `Date`                   | None needed                      |
| TransactionID field    | `Bank Reference`                        | `Arhiveerimiskood`               |
| TransactionID prefix   | `CT`                                    | `LN`                             |
| OtherAccountName       | `post_process` from `Description`       | `direct_copy` from dedicated col |
| Converter class        | `CitadeleSourceConverter` (subclass)    | `GenericSourceConverter`         |
| Code changes needed    | Yes (interface + generic + new class)   | None                             |
