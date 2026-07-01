# How to Add a New Bank

This guide walks through adding support for a new bank's CSV export to the ETL pipeline.
It is based on the Luminor (standard case) and Citadele (non-standard case) implementations.

---

## Step 0: Decide your bank ID

Pick a short, lowercase, no-spaces identifier. Examples: `luminor`, `citadele`, `seb`.
This ID is used as the key in `config.yaml`, as the filename prefix for schemas/mappings,
and as the two-letter `TransactionID` prefix (uppercased).

---

## Step 1: Analyse the CSV export

Download a real bank statement and inspect it. Answer these questions:

| Question | Why it matters |
|---|---|
| What delimiter is used? | `file_details.delimiter` in the source schema |
| What encoding? Run `file -i file.csv` | `file_details.encoding` in the source schema |
| How many metadata rows precede the actual column header? | `file_details.skip_header_rows` |
| What are the exact column names in the header row? | Schema field definitions |
| What is the date format? (`DD.MM.YYYY`, `YYYY-MM-DD`, …) | Date transformation or `direct_copy` |
| What is the decimal separator in amounts? (`,` or `.`) | Whether to use `replace_decimal_separator` |
| Is the amount sign embedded in the value, or in a separate D/C column? | Amount transformation strategy |
| Is the account IBAN present in every transaction row? | Whether `anonymize_iban` (per-row) or `header_extraction` + `anonymize_iban` (from file header) |
| Is the currency present in every transaction row? | Whether `direct_copy` (per-row) or `header_extraction` (from file header) |
| Are there footer rows or non-transaction rows that must be filtered? | Whether to define `filters` in the mapping |
| Is there a unique transaction ID column? | Used for deduplication |

Build a column mapping table:

| # | Column name | Maps to intermediate | Transformation | Notes |
|---|-------------|----------------------|----------------|-------|
| … | …           | …                    | …              | …     |

---

## Step 2: Create the source schema

Create `schemas/<bank_id>_source.yaml`.

### Minimal standard template

```yaml
schema_name: "<BankName> Estonia Source CSV Schema"
description: "Schema for <BankName> CSV export files"
file_details:
  delimiter: ";"       # use the actual delimiter
  decimal_separator: ","
  date_format: "DD.MM.YYYY"
  encoding: "utf-8"

fields:
  - name: "ExactColumnNameFromCSV"
    alias: "FriendlyAlias"
    type: "string"
    description: "What this column contains"
    required: true     # set true only if absence should block processing
```

### Non-standard: multi-row file header

If the CSV has metadata rows before the actual column header (like Citadele's 3-row prefix),
add `skip_header_rows` to `file_details`:

```yaml
file_details:
  delimiter: "|"
  skip_header_rows: 3   # skip rows 0–2; actual column headers are at row 3
  encoding: "utf-8"
```

The converter passes this value as `skiprows` to `pd.read_csv`. All existing banks default
to `0` when this key is absent.

### Non-standard: account IBAN or currency only in file header

If a field (IBAN, currency) is not present in each transaction row but appears in a metadata
row at the top of the file, use `header_extractions` in `file_details`:

```yaml
file_details:
  delimiter: "|"
  skip_header_rows: 3
  header_extractions:
    - virtual_column: "AccountIBAN"   # name injected as a DataFrame column
      row: 0                           # which metadata row to read (0-based)
      col: 1                           # which column in that row (0-based)
      transform:
        type: "extract_word_by_index"
        index: -1                      # -1 = last word; 0 = first word
        notes: "'EUR EE521...' → 'EE521...'"
    - virtual_column: "Currency"
      row: 0
      col: 1
      transform:
        type: "extract_word_by_index"
        index: 0                       # 'EUR EE521...' → 'EUR'
```

The extracted values are injected as constant columns into the DataFrame before field mapping
runs. Then reference them as regular `source_field` values in the mapping YAML.

> **Note**: `header_extractions` is not yet implemented in `GenericSourceConverter`.
> To extract header metadata today, override `extract_header()` in a bank-specific subclass
> (see `CitadeleSourceConverter.extract_header()` for the reference implementation).

---

## Step 3: Create the mapping

Create `mappings/<bank_id>_to_intermediate.yaml`.

### Structure

```yaml
mapping_name: "<BankName> Bank Source to Intermediate Mapping"
description: "…"
source_schema: "<bank_id>_source.yaml"
target_schema: "intermediate.yaml"

# optional — only if non-transaction rows must be removed
filters:
  - field: "ColumnName"
    operator: "not_in"          # equals | not_equals | not_in | not_empty
    value: ["BadValue1", "BadValue2"]
    description: "Why these rows are excluded"

field_mappings:
  - source_field: "SourceColumn"
    target_field: "TransactionDate"
    transformation:
      type: "direct_copy"
```

### Transformation reference

| Type | When to use | Required sub-fields |
|---|---|---|
| `direct_copy` | Column value copied as-is | — |
| `string_clean` | Strip whitespace; remove leading apostrophe | `rules: [{action: remove_leading_apostrophe}]` |
| `anonymize_iban` | Per-row full IBAN → anonymized form | `rules` with `keep_country_prefix`, `keep_last_n_digits`, `replace_middle_with` |
| `calculated_float` with `replace_decimal_separator` + `apply_sign_based_on_field` | Amount in separate column, D/C sign in another column | `rules` list with both actions |
| `calculated_float` with `replace_decimal_separator` only | Amount with `,` decimal sep, sign already embedded | `rules: [{action: replace_decimal_separator, from: ",", to: "."}]` |
| `direct_float` | Amount already a signed `.`-decimal string | — |
| `prefix_string` | Prepend a bank prefix to the transaction ID | `prefix: "XX"` |
| `regex_extract` | Extract a sub-string from a column via regex | `patterns: [{pattern: "…", group: 1}, …]` — first match wins |
| `date_format_conversion` | Source date format differs from DD.MM.YYYY | `source_format`, `target_format` |

### Common intermediate target fields

| Target field | Description |
|---|---|
| `TransactionDate` | Date string in DD.MM.YYYY |
| `Amount` | Signed float (negative = expense, positive = income) |
| `Currency` | ISO currency code, e.g. `EUR` |
| `Description` | Free-text payment description |
| `BudgetAccountNumber` | Anonymized IBAN of the user's own account |
| `OtherAccountName` | Counterparty name (payee or payer) |
| `TransactionID` | Unique transaction identifier (bank-prefixed) |

### Filter operators

| Operator | Keeps rows where … |
|---|---|
| `equals` | field value == value |
| `not_equals` | field value != value |
| `not_in` | field value not in list |
| `not_empty` | field value is a non-empty string |

---

## Step 4: Create the sample file

Create `data/samples/transactions/<bank_id>_sample_ee.csv`.

**Rules:**
- Anonymize all personal data: replace real IBANs with `XX***NNNNN`, mask card numbers, replace names.
- Include at least 2–3 rows covering the main transaction types (transfer + card purchase).
- The sample file must **mirror the real export format** — if the real file has metadata prefix rows
  (like Citadele's 3-row header), include them in the sample too (anonymized).
- Set `detection_header_row: N` in the bank's config block to tell the detector how many rows
  to skip to find the column headers. Banks without a prefix omit this key (defaults to 0).

Example for Citadele (3-row metadata prefix, `detection_header_row: 3`):
```
"Account"|"EUR EE000000000000000000"
"From"|"01.06.2026"|"to"|"30.06.2026"
|||||"Opening balance:"|"0.00"
"Date"|"Type"|"Narrative"|"Payment No."|"Bank Reference"|"Reference number"|"Amount DR/Amount CR"
"26.06.2026"|"INWARD TRANSFER"|"INWARD TRANSFER JOHN DOE 38000000001 HABAEE2X EE000000000000000001"||"1000000001"||"100.00"
"28.06.2026"|"PURCHASE"|"28/06/2026 123456******7890 MCC-5812 REF: 12345 MERCHANT TALLINN EE HABAEE2X"||"1000000002"||"-7.20"
```

---

## Step 5: Update configs

### `config/config.yaml`

Under `source_converters`, add:

```yaml
<bank_id>:
  source_schema: <bank_id>_source.yaml
  mapping: <bank_id>_to_intermediate.yaml
  sample_files:
    - "data/samples/transactions/<bank_id>_sample_ee.csv"
```

### `config/config_test.yaml`

Add the same block. Test with:
```bash
python src/main.py --config config/config_test.yaml --input-dir data/samples/transactions/ --bank <bank_id>
```

### `config/tiller/accounts.yaml`

Add an entry for each real account at this bank:

```yaml
- account_name: "Friendly Name"
  account_anonymized_iban: "EE***NNNNN"   # must match what the converter produces
  bank: "<BankName>"
  tiller_account_id: "manual:<uuid-from-tiller>"
```

If the bank does NOT have per-row IBAN (e.g. Citadele), the IBAN is extracted dynamically
from the file header. Run the pipeline once on the real file and read the `BudgetAccountNumber`
value from the intermediate output — that is the value to enter here.

### `config/tiller/accounts_sample.yaml`

Add a fake entry with a placeholder IBAN and UUID:

```yaml
- account_name: "Test account (<BankName>)"
  account_anonymized_iban: "EE***0000N"
  bank: "<BankName>"
  tiller_account_id: "manual:00000000-0000-0000-0000-00000000000N"
```

---

## Step 6: Verify — does it need code changes?

Run the test pipeline command from Step 5. If everything works: done.

If the bank has a non-standard format, you may need one or more of the following code changes
in `src/converters/generic_source_converter.py` and `src/utils/csv_utils.py`:

| Feature | When needed | Where to add |
|---|---|---|
| `skip_header_rows` in schema | Multi-row file header (Citadele) | `load_source_data` reads the value and passes `skiprows=N` to `pd.read_csv` |
| `header_extractions` in schema | IBAN or currency only in file header rows | **Not yet implemented** — use `extract_header()` override in a bank subclass instead |
| `direct_float` transformation | Amount already a signed `.`-decimal string | New branch in `_apply_transformation` |
| `regex_extract` transformation | Extract counterparty name from a free-text column | New branch in `_apply_transformation`; `patterns` list, first match wins |
| `not_empty` filter operator | Footer rows with empty date/type column | New branch in `filter_rows` |
| `\|` delimiter in header reader | Pipe-delimited sample file for bank detection | Add `'|'` to the delimiter list in `csv_utils._read_header_from_file_object` |

Each of these is a small, self-contained addition that does not affect existing banks.

---

## Step 7: End-to-end test

Run with the real export file (not the sample):

```bash
python src/main.py --config config/config.yaml --input-dir data/transactions/ --bank <bank_id>
```

Verify:
- Correct number of rows (no footer rows, no header rows in output).
- `Amount` signs correct (expenses negative, income positive).
- `BudgetAccountNumber` matches the value in `accounts.yaml`.
- `TransactionID` has the correct prefix and is unique per row.
- `TransactionDate` is in `DD.MM.YYYY` format in the intermediate CSV.
- Tiller output has correct `Account`, `Account ID`, `Institution` from the lookup.

---

## Decision tree: which transformations to use?

```
Amount column
├── Sign in a separate D/C column?
│   └── YES → calculated_float + replace_decimal_separator + apply_sign_based_on_field
└── NO (sign embedded in value)
    ├── Decimal separator is comma?
    │   └── YES → calculated_float + replace_decimal_separator (","→".")
    └── NO (decimal is dot)
        └── → direct_float

Account IBAN column
├── Present in every row?
│   └── YES → anonymize_iban
└── NO (only in file header)
    └── → header_extraction (extract_word_by_index) → anonymize_iban

Currency column
├── Present in every row?
│   └── YES → direct_copy
└── NO (only in file header)
    └── → header_extraction (extract_word_by_index) → direct_copy

Counterparty name
├── Dedicated column?
│   └── YES → direct_copy (or string_clean)
└── NO (embedded in free-text Narrative)
    └── → regex_extract with ordered pattern list

Footer rows
├── File has footer rows?
│   └── YES → filter: not_empty on date column (or not_in on type column)
└── NO → no filter needed
```

---

## Reference: implemented banks

| Bank | Schema | Mapping | Delimiter | Skip rows | Amount sign | IBAN per row | Notes |
|---|---|---|---|---|---|---|---|
| Swedbank | `swedbank_source.yaml` | `swedbank_to_intermediate.yaml` | `;` | 0 | D/C column | Yes | Two language variants |
| SEB | `seb_source.yaml` | `seb_to_intermediate.yaml` | `;` | 0 | D/C column | Yes | Type-column row filter |
| LHV | `lhv_source.yaml` | `lhv_to_intermediate.yaml` | `;` | 0 | D/C column | Yes | Modern format |
| LHV Legacy | `lhv_legacy_source.yaml` | `lhv_legacy_to_intermediate.yaml` | `;` | 0 | D/C column | Yes | Pre-2024 format |
| Luminor | `luminor_source.yaml` | `luminor_to_intermediate.yaml` | `;` | 0 | D/C column | Yes | No code changes needed |
| Citadele | `citadele_source.yaml` | `citadele_to_intermediate.yaml` | `\|` | 3 | Embedded | No | Needs code additions |
