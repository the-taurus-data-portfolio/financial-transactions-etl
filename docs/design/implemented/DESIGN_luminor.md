# Design: Luminor Bank Support

## Pre-implementation checklist

Two manual steps must be completed before starting implementation:

- [ ] **Verify encoding** — download a fresh statement from Luminor without opening/editing it,
  then run `file -i AccountStatement.csv`. Update `encoding` in `schemas/luminor_source.yaml`.
  Likely `utf-8` or `windows-1252`. (Note: `chardet` is not installed in this project.)
- [ ] **Create Tiller account** — add the Luminor account manually in Tiller Money web app,
  copy the Account ID it assigns, use it in `config/tiller/accounts.yaml`.

---

## Analysis of AccountStatement.csv

| Property           | Value                                                                   |
|--------------------|-------------------------------------------------------------------------|
| Delimiter          | `;`                                                                     |
| Encoding           | **TBD** — verify on fresh download (likely `utf-8` or `windows-1252`)  |
| Date format        | `DD.MM.YYYY`                                                            |
| Decimal separator  | `,` (e.g. `2,50`); amounts quoted in raw file, pandas strips automatically |
| D/C indicator      | `D` = debit (expense), `C` = credit (income)                           |
| IBAN in export     | Full IBAN — anonymized by pipeline via `anonymize_iban`                 |
| Trailing semicolon | Creates phantom `Unnamed: 12` column — harmless |

### Columns

| # | Column name               | Maps to intermediate     | Notes                         |
|---|---------------------------|--------------------------|-------------------------------|
| 0 | `Konto`                   | `BudgetAccountNumber`    | Full IBAN in real export — use `anonymize_iban` (same rules as SEB) |
| 1 | `Dokumendi number`        | —                        | Empty for service fees, not needed |
| 2 | `Väärtuspäev`             | `TransactionDate`        | `direct_copy` (DD.MM.YYYY stays) |
| 3 | `Saaja/maksja konto`      | —                        | Counterparty IBAN, not mapped |
| 4 | `Saaja/maksja nimi`       | `OtherAccountName`       | `direct_copy`                 |
| 5 | `Deebet/krediit`          | (sign source only)       | Used by Amount transformation |
| 6 | `Summa`                   | `Amount`                 | Replace `,`→`.`, apply sign from `Deebet/krediit` |
| 7 | `Viitenumber`             | —                        | Not mapped                    |
| 8 | `Arhiveerimiskood`        | `TransactionID`          | Prefix with `"LN"`            |
| 9 | `Makse andmed`            | `Description`            | `string_clean`                |
| 10| `Valuuta`                 | `Currency`               | `direct_copy`                 |
| 11| `Registrikood/isikukood`  | —                        | Not mapped                    |
| 12| `Unnamed: 12`             | —                        | Phantom from trailing `;`, ignored |

---

## Files to create / modify

### 1. `schemas/luminor_source.yaml` (NEW)

Source schema with all 12 real columns. Required fields:
`Konto`, `Väärtuspäev`, `Deebet/krediit`, `Summa`, `Valuuta`.
The `Arhiveerimiskood` and `Makse andmed` marked `required: false`
(service-fee rows may have empty `Arhiveerimiskood` — sample shows it populated, but it is safer).

### 2. `mappings/luminor_to_intermediate.yaml` (NEW)

No row filters needed — all rows are real transactions (no header/footer type column).

Field mappings:

| Source field       | Target field        | Transformation                                           |
|--------------------|---------------------|----------------------------------------------------------|
| `Väärtuspäev`      | `TransactionDate`   | `direct_copy`                                            |
| `Summa`            | `Amount`            | `calculated_float`: `,`→`.` + sign from `Deebet/krediit` (`D`/`C`) |
| `Valuuta`          | `Currency`          | `direct_copy`                                            |
| `Makse andmed`     | `Description`       | `string_clean`                                           |
| `Konto`            | `BudgetAccountNumber` | `anonymize_iban` (country prefix 2 + `***` + last 5 digits) |
| `Saaja/maksja nimi`| `OtherAccountName`  | `direct_copy`                                            |
| `Arhiveerimiskood` | `TransactionID`     | `prefix_string` with prefix `"LN"`                      |

### 3. `data/samples/transactions/luminor_sample_ee.csv` (NEW)

Copy of `AccountStatement (1).csv` from Downloads — contains both card and transfer transactions,
header row already manually anonymized. Used by `BankDetector` for header signature matching.

**Encoding — action required before implementing:** The sample was edited in Sublime Text which
may have re-saved it as UTF-8. To confirm the real Luminor export encoding, download a fresh
statement without editing and run:
```bash
file -i AccountStatement.csv
python3 -c "import chardet; print(chardet.detect(open('AccountStatement.csv','rb').read()))"
```
Likely candidates: `utf-8` or `windows-1252`. The schema `encoding` field must reflect
the original export, not the edited copy.

### 4. `config/tiller/accounts.yaml` (MODIFY)

**Prerequisite — manual step required before implementing this file:**
Add the Luminor account manually in the Tiller Money web app, then copy the Account ID it assigns.

After that, add the entry:

```yaml
- account_name: "Luminor"               # or any friendly display name
  account_anonymized_iban: "EE***84899"  # confirmed anonymized IBAN for this account
  bank: "Luminor"
  tiller_account_id: "manual:<id-from-tiller>"  # paste ID from Tiller after adding the account
```

This entry is required for the Tiller `Account`, `Account ID`, and `Institution` field lookups.

### 5. `config/tiller/accounts_sample.yaml` (MODIFY)

Add a fake entry to keep the public sample consistent with the real `accounts.yaml`:

```yaml
- account_name: "Test account (Luminor)"
  account_anonymized_iban: "EE***00005"
  bank: "Luminor"
  tiller_account_id: "manual:00000000-0000-0000-0000-000000000005"
```

### 6. `config/config_test.yaml` (MODIFY)

Same `luminor:` block as `config.yaml` — needed to run a test pipeline pass:

```yaml
luminor:
  source_schema: luminor_source.yaml
  mapping: luminor_to_intermediate.yaml
  sample_files:
    - "data/samples/transactions/luminor_sample_ee.csv"
```

To run a test with Luminor sample files locally:
```bash
python src/main.py --config config/config_test.yaml --input-dir data/samples/transactions/ --bank luminor
```

### 7. `config/config.yaml` (MODIFY)

Add under `source_converters`:

```yaml
luminor:
  source_schema: luminor_source.yaml
  mapping: luminor_to_intermediate.yaml
  sample_files:
    - "data/samples/transactions/luminor_sample_ee.csv"
```

---

## Card vs. transfer transactions

Both transaction types share the same 13-column structure. Differences are data-only — no structural impact on the pipeline:

| Field                | Bank transfer            | Card payment                                                    |
|----------------------|--------------------------|-----------------------------------------------------------------|
| `Dokumendi number`   | Populated                | Empty                                                           |
| `Saaja/maksja konto` | Counterparty IBAN        | Empty                                                           |
| `Saaja/maksja nimi`  | Counterparty name        | Merchant name                                                   |
| `Arhiveerimiskood`   | Populated ✓              | Populated ✓ (reliable TransactionID source for deduplication)  |
| `Makse andmed`       | Free-text description    | `Kaart:408885******4251. Omanik: ... Ost - [merchant] - kuupäev [date]` |

No row filtering is needed — all rows in Luminor exports are settled transactions.

---

## Code changes

**None required.** The `GenericSourceConverter` and `BankDetector` are fully data-driven.
All logic is in the YAML files above.

---

## Differences vs existing banks

| Aspect               | Luminor                        | SEB (closest match)           |
|----------------------|--------------------------------|-------------------------------|
| Delimiter            | `;`                            | `;`                           |
| Date field name      | `Väärtuspäev`                  | `Kuupäev`                     |
| Date format          | `DD.MM.YYYY`                   | `DD.MM.YYYY`                  |
| Amount field         | `Summa`                        | `Summa`                       |
| D/C field name       | `Deebet/krediit`               | `Deebet/Kreedit (D/C)`        |
| D/C values           | `D` / `C`                      | `D` / `C`                     |
| Description field    | `Makse andmed`                 | `Selgitus`                    |
| Transaction ID field | `Arhiveerimiskood`             | `Arhiveerimistunnus`          |
| IBAN in export       | Full IBAN (needs `anonymize_iban`) | Full IBAN (needs `anonymize_iban`) |
| Row filter needed    | No                             | Yes (exclude type H, K2, etc)|
| TransactionID prefix | `LN`                           | `SE`                          |
