# DESIGN — `Card` and `Payment method` columns from the bank statement

**Status:** Draft (2026-11-12). **Scope:** Swedbank and LHV first; other banks leave the columns empty.
**Origin:** [Tiller columns review](../reviews/BACKLOG-REVIEW-tiller-columns-2026-11-12.md), items K3 and F1.

## 1. Goal

Fill two Tiller columns during conversion:

| Tiller column | Values | Use |
|---|---|---|
| `Payment method` | `Card` / `Transfer` (first version) | The clarification report needs the payment method of every row; today the agent opens the archived statement for each row |
| `Card` | Masked card number, last 4 digits only: `****1234` | Shows which card (and so which family member) paid; card replacements stay visible |

The columns already exist in the Tiller table and in `schemas/tiller_target.yaml` (added 2026-11-12, left empty).
This design only fills them.

## 2. Source data (checked on the archive, 2026-11-12)

### Swedbank

- Transaction type column `Tehingu tüüp` (RU export: `Тип сделки`), already in `schemas/swedbank_source.yaml`.
- Card payments (`K`) carry the masked card number at the start of `Selgitus`: `XXXXXX******NNNN DD.MM.YY <merchant>`
  (171 of 171 `K` rows in the archive).

| `Tehingu tüüp` | Rows in archive | Meaning | `Payment method` |
|---|---|---|---|
| `K` | 171 | card payment | `Card` |
| `MV` | 3 | card refund | `Card` |
| `MK` | 204 | transfer (in and out, incl. Trustly) | `Transfer` |
| `M` | 3 | bank fee | `Transfer` |
| other / empty | — | — | empty (log a warning with the type, not the row) |

### LHV

- No transaction type column.
- Card payments and card refunds start `Selgitus` with `(..NNNN)`: `(..NNNN) YYYY-MM-DD HH:MM <merchant>`
  (260 rows: 253 debit, 7 credit). All other rows (transfers, monthly fees; 116) have no prefix.

| `Selgitus` | `Payment method` | `Card` |
|---|---|---|
| starts with `(..NNNN)` | `Card` | `****NNNN` |
| anything else | `Transfer` | empty |

## 3. Design

### 3.1 New transformations (`src/converters/generic_source_converter.py`)

Two branches in `_apply_transformation`, generic and usable by every bank:

```yaml
# regex_extract: first matching pattern wins; `output` is a template with {1}, {2} … for the groups,
# or a constant. No match → `default` (empty string when omitted).
transformation:
  type: "regex_extract"
  patterns:
    - pattern: "^'?\\d{6}\\*{6}(\\d{4})\\s"
      output: "****{1}"
  default: ""

# value_map: exact match of the source value; no match → `default`.
transformation:
  type: "value_map"
  map: {K: "Card", MV: "Card", MK: "Transfer", M: "Transfer"}
  default: ""
```

`regex_extract` is already listed as a planned extension in `docs/how-to-add-bank.md` (extension table); this
design adds the `output` template and `default`. Masking is part of the pattern output: only the last 4 digits ever
leave the converter.

### 3.2 Intermediate format (`schemas/intermediate.yaml`)

Two new fields: `CardNumber` (masked) and `PaymentMethod`, both marked `optional: true`.

`TillerConverter.validate_intermediate_schema` (`src/converters/tiller_converter.py:167-192`) fails on any missing
intermediate column. Change it to skip fields with `optional: true`; the Tiller converter already fills a missing
target field with an empty value (`tiller_converter.py:383-387`). So banks without the mapping need no change.

### 3.3 Mappings

| File | Change |
|---|---|
| `mappings/swedbank_to_intermediate.yaml` | `Tehingu tüüp` → `PaymentMethod` (`value_map`); `Selgitus` → `CardNumber` (`regex_extract`, pattern above) |
| `mappings/lhv_to_intermediate.yaml` | `Selgitus` → `PaymentMethod` (`regex_extract`: `^\(\.\.\d{4}\)` → `Card`, default `Transfer`); `Selgitus` → `CardNumber` (`^\(\.\.(\d{4})\)` → `****{1}`) |
| `mappings/intermediate_to_tiller.yaml` | `PaymentMethod` → `Payment method`, `CardNumber` → `Card` (`direct_copy`) |

The Swedbank RU export uses the same schema key (language variants); check that `Тип сделки` maps to the same
source field as `Tehingu tüüp` before relying on it.

### 3.4 Tests

- Unit tests for `regex_extract` (template, constant output, default, first match wins) and `value_map`
  (hit, miss → default).
- Validation: an optional intermediate field may be missing; a required one still fails.
- Swedbank (ET and RU samples) and LHV samples: `K` / `MK` rows and LHV card / transfer rows produce the expected
  `Payment method` and `Card`; no full card number appears anywhere in the output CSV.
- Samples in `data/samples/transactions/` are anonymised; add masked card rows if they are missing.

### 3.5 Docs

`Agents.md` bank format table (new rows: payment method source, card source), `docs/how-to-add-bank.md`
(`regex_extract` and `value_map` move from "planned" to the transformation table), `docs/specification.md`.

## 4. Out of scope (later)

- Other banks (SEB, Luminor, Citadele): Luminor `Kaart:XXXXXX******NNNN` and Citadele purchase rows look easy; the
  columns stay empty until then.
- More `Payment method` values (`Bank fee`, `Card refund`): the `value_map` makes this a mapping-only change.
- Backfill of the rows already in Tiller (from `data/archive/` by `Transaction ID`).
- The `Receipt` and `Clarified?` columns: not statement data, filled by the financial review.

## 5. Effort

About 4–5 h with tests and docs (transformations 2 h, validation 0.5 h, mappings 0.5 h, tests and docs 1–2 h).
