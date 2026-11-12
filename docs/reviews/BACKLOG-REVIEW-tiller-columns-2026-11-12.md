# Open items review — Tiller `Transactions` columns (2026-11-12)

Scope (user request): only the items about adding or removing columns of the Tiller `Transactions` table (Data Table
`Table1`), and the changes the service needs for them. Not a full review of the service.

Sources: `docs/backlog.md`, `docs/feedback/personal-finance-assistant-role.md`, `docs/specification.md`; finance
domain: `roles/personal-finance-assistant/docs/backlog.md`, `docs/feedback/personal-finance-assistant.md`,
`skills/financial-review/SKILL.md`, `skills/expense-clarification/SKILL.md`, `skills/transaction-split/SKILL.md`,
`skills/education-tax-monitor/scripts/monitor.py`; `tools/google-spreadsheets` (`Agents.md`, `docs/backlog.md`,
`service/sheets_service.py`). Previous review: none for this scope.
✔ = checked against the code on 2026-11-12. Effort includes tests and docs. Criticality: High / Medium / Low.

## How a column reaches the sheet today

1. `schemas/tiller_target.yaml` lists the 22 output fields. Their order is the output column order: the converter
   adds missing fields as empty and reorders to the schema (✔ `src/converters/tiller_converter.py:383-395`).
2. `mappings/intermediate_to_tiller.yaml` fills 13 of them; the rest stay empty.
3. The agent builds `rows.json` from `output/tiller_transactions.csv` and calls `google-spreadsheets insert`.
   The tool maps cells **by position** to the table columns (✔ `service/sheets_service.py:729-734`).
4. Dedup reads the sheet with `get_all_records()` and looks the `Transaction ID` column up **by header name**
   (✔ `src/utils/google_sheets_reader.py:89-109`): added or removed columns do not affect it, as long as header
   names stay unique.
5. The tool cannot add or delete a table column (✔ `tools/google-spreadsheets/Agents.md`, no column task): the
   user changes the columns in the Sheets UI.

Column fill rate on 2026-11-12 (3,324 rows): `Check Number`, `Category Hint`, `Tags`, `Merchant Name`, `Source` are
empty in every row; `Full Description` is filled in about 13 % of the rows.

## 1. Open bugs / risks

| # | Problem | How it works now | Proposed change | Effort | Criticality | Source / notes |
|---|---|---|---|---|---|---|
| B1 | A column added in the **middle** of the sheet shifts every cell after it, silently | `_coerce_row` pads a short row with empty cells **at the end** (✔ `sheets_service.py:731-733`). A 22-cell row written into a 23-column table puts each value after the new column one column to the left of where it belongs. No error is raised. A row that is **wider** than the table fails (✔ line 731) | (a) Skill Step 3: assert that the CSV header equals the metadata column names before the insert (the agent did this ad hoc on 2026-11-12). (b) Tool: an opt-in strict width check (`len(row) != col_count` → error), or insert by header name | (a) 0.5 h; (b) 2–3 h +google-spreadsheets | High | New finding of this review. Must be done **before** any column is added |

## 2. Open designs

None.

## 3. Open backlog items

| # | Item | How it works now | Changes needed | Effort | Criticality | Source / notes |
|---|---|---|---|---|---|---|
| K1 | `Clarified` checkbox (do not ask the family again about rows that are already explained) | No such field; each review re-derives open items from scratch | **Sheet:** a checkbox column. **Service:** add the field to `tiller_target.yaml` (empty). **Tool:** writing a checkbox value with `update --entity-type cell` is not verified (Needs reproduction: write `true` to a BOOLEAN column of a test table). **Skills:** financial-review Steps 4–5 and expense-clarification skip checked rows and set the box when an answer is applied | 2–3 h +design (where the flag lives) | Medium | Role backlog, 2026-11-12 |
| K2 | `Receipt` column: hyperlink to the receipt on Drive | Not in the schema ✔ `tiller_target.yaml`; the skill text already describes how to fill it (✔ `financial-review/SKILL.md:273`). The tool writes `{text, link}` cells (backlog statement, not reproduced) | **Sheet:** add the column (last position is safest). **Service:** add the field to `tiller_target.yaml` at the same position; no mapping (empty). **Skill:** Step 5 fills it for every matched row; split parts copy it (transaction-split copies the full row ✔ `transaction-split/SKILL.md:39`). Optional backfill for older rows | 1–2 h (+ backfill 1–2 h) | Medium | Service backlog, requested 2026-10-24 |
| K3 | "Add anonymised card number" | Backlog has one line, no purpose. The masked card number is already inside `Description`: Swedbank `XXXXXX******NNNN`, LHV `(..NNNN)`, Luminor `Kaart:XXXXXX******NNNN` | **Intermediate:** a new `CardNumber` field (last 4 digits only). **Bank mappings:** `regex_extract` from the description (the transformation exists ✔ `docs/how-to-add-bank.md:151`) for Swedbank, LHV, Luminor, Citadele (Citadele post_process already strips the masked card ✔ `Agents.md`, Citadele special handling). **Target:** `tiller_target.yaml` + mapping. Tests per bank | 3–4 h | Low | Service backlog. **Stale text:** purpose missing (who paid? which family member?). Ask the user |

| K4 | Remove the column that holds a link as plain `http://…` text instead of a hyperlink (user, 2026-11-12, not recorded yet) | **Not located:** the `Transactions` tab has 22 columns (= `Table1`), and no column holds URL text (✔ tab read 2026-11-12: one `Description` cell contains a URL as part of the bank text). Either the column is on another tab, or its values are hyperlink cells that `read` returns as text only | **Pre-condition:** tool backlog "`read` returns hyperlink cells as text only, the URI is lost" (✔ `tools/google-spreadsheets/docs/backlog.md:59`). Then: the user removes the column in the Sheets UI; if it is in `Table1`, remove the field from `tiller_target.yaml` in the same change | 0.5 h (service) + 3–4 h (tool, read with links) | Low | User request in this review. Ask which column |

## 4. Feedback not in the backlog

| # | Item | Changes needed | Effort | Criticality | Source / notes |
|---|---|---|---|---|---|
| F1 | `Payment method` column (card / transfer) | **Today:** for every report row the agent opens the archived statement to get the type (✔ `expense-clarification/SKILL.md:43-44`: "Tiller has no such column"). Swedbank `Tehingu tüüp` is already read by the source schema (✔ `schemas/swedbank_source.yaml:59`) but not mapped to the intermediate format (✔ `schemas/intermediate.yaml`, no such field). **Service:** intermediate `PaymentType`; Swedbank mapping `K` → card, `MK` → transfer; LHV / Luminor / Citadele / SEB from the description format or a type column; `tiller_target.yaml` + mapping. **Skill:** read the column instead of the archive | 3–5 h | Medium | Repeated workaround in every clarification report (2026-10-31, 2026-11-07, 2026-11-12) |

## 5. Removing columns

No backlog item asks for a removal. If the user wants to remove the 5 empty columns:
- **Service:** remove the fields from `tiller_target.yaml` in the same change, before the next import. If the
  schema stays wider than the sheet, the insert fails loudly (✔ `sheets_service.py:731`): this is safe, but it blocks
  the review.
- **Tiller:** `Category Hint`, `Categorized By` and `Categorized Date` are written by Tiller AutoCat (`Categorized
  By` / `Categorized Date` are filled in about 70 % of the rows): keep them. Whether Tiller needs `Tags`, `Merchant
  Name`, `Source`, `Check Number` to exist is not verified (Needs reproduction: Tiller documentation or a test copy of
  the sheet).
- Scripts that read by header name (`monitor.py` ✔ `:98`, dedup reader) are not affected.

## 6. Questions for the user

1. K3 card number: what is it for (who paid, which card of the family)? Is the last 4 digits enough?
2. K1 `Clarified`: a Tiller column, or the report's own store? A Tiller column is visible and filterable in the
   sheet, but it adds one more column to keep in sync.
3. Remove the 5 empty columns? Only after B1 (a) is in place and Tiller's requirements are checked.

4. K4: which column holds the plain `http://` links, and on which tab?

**Scope decision (user, 2026-11-12):** change the table structure first; filling the new columns with data
(F1 payment type, K3 card number, K2 backfill) comes later if the effort is large. Structure-only effort: one
`tiller_target.yaml` change (+ docs) for all new / removed columns, about 1 h, after B1 (a).

## Applied (2026-11-12)

- ✅ **B1 (a)**: `skills/financial-review/scripts/build_rows.py` (finance domain) builds `rows.json` and refuses a
  CSV whose header differs from the table columns; skill Step 3 uses it. B1 (b) (tool strict width) stays open.
- ✅ **Structure**: the user added `Clarified?` (checkbox), `Receipt`, `Payment method`, `Card` inside `Table1` at
  chosen positions (26 columns); `schemas/tiller_target.yaml` follows the table 1:1. Test row: all values under the
  right headers, checkbox `true` written and read as `TRUE`, `Receipt` hyperlink confirmed by the user; row deleted;
  full-table diff against the backup clean.
- ✅ **K4 closed**: the plain-URL column is not in the Tiller spreadsheet (the user mixed it up with another
  spreadsheet). The link-reading tool bug does not block this work.
- **K3 + F1** → service backlog with the draft [design](../design/DESIGN-card-and-payment-method.md)
  (`Payment method`: `Card` / `Transfer` first).
- **K1 / K2 filling** (Clarified?, Receipt) stays in the finance-domain role backlog / skill.

## 7. Suggested order

1. **B1 (a)**: header check in skill-financial-review Step 3 (0.5 h). Without it, any new column in the middle of
   the sheet silently corrupts the next insert. Then add new columns **at the end** of the table only.
2. **K2 + F1 + K1 in one service change**: one schema change, one sheet change by the user, one re-check of the
   insert. Each new field in `tiller_target.yaml` appended at the end, in the same order as in the sheet. F1 also
   removes a repeated manual step from every clarification report.
3. **B1 (b)** in the tool (strict width check), so the safety check does not depend on the skill text.
4. **K3** after its purpose is clarified; it touches every bank mapping.
5. Removal of empty columns last, after the Tiller check.
