# BUG REPORT: Citadele purchase TransactionDate uses settlement date instead of card transaction date

## General Information

**Date**: 2026-07-01
**Priority**: High
**Severity**: NOTE
**Status**: Fixed
**Source**: Real-file pipeline run (Statement-Citadele-01.06.2026-01.07.2026.csv) — observed in intermediate output

---

## 1. Description

For Citadele PURCHASE rows, `TransactionDate` was populated with the batch settlement date (from the `Date` column in the source CSV, e.g. `17.06.2026`), not the actual card transaction date (embedded in the Narrative field, e.g. `13/06/2026`). The settlement date can lag the card swipe by several days, making transaction history inaccurate in Tiller.

Additionally, `Description` was formatted as `DD/MM/YYYY: <merchant>` — embedding the card date as a string prefix — which compounded the confusion: the date in Description did not match the date in the `Date` column.

## 2. Steps to Reproduce

Run the pipeline on any Citadele statement containing PURCHASE rows. Observe `intermediate_transactions.csv`:
- `TransactionDate` column shows the batch date (e.g. `17.06.2026`)
- `Description` column shows `13/06/2026: VITA LOVE TALLINN EE` (card date as prefix)

## 3. Expected

- `TransactionDate` = card swipe date extracted from Narrative (`13.06.2026`)
- `Description` = merchant name only, no date prefix

## 4. Actual

- `TransactionDate` = settlement/batch date from source `Date` column (`17.06.2026`)
- `Description` = `13/06/2026: VITA LOVE TALLINN EE` (date prefix from original design decision)

---

## 5. Root Cause Analysis

`CitadeleSourceConverter._process_purchase()` extracted the card date from the Narrative regex match (`_CARD_DATE_RE`) but only used it to build the `Description` string (`f"{card_date}: {name}"`). It never wrote the card date back to `TransactionDate`.

The design decision to include the date in `Description` was an attempt to preserve the card date, but it created an inconsistency rather than fixing it at the source.

`post_process()` had access to `result.at[idx, 'TransactionDate']` but never updated it for PURCHASE rows.

## 6. Proposed Fix

In `_process_purchase`, return the card date as a third element of the tuple (converted from `DD/MM/YYYY` to `DD.MM.YYYY`). In `post_process`, unpack the third return value and overwrite `result.at[idx, 'TransactionDate']` when it is non-empty. Set `description = name` (no date prefix).

Files: `src/converters/citadele_source_converter.py` — `_process_purchase` and `post_process`.

## 7. Verification Plan

- Reproduction test: assert `TransactionDate == '15.06.2026'` and `'15/06/2026' not in Description` for a PURCHASE narrative starting with `15/06/2026 ...`.
- Regression check: `venv/bin/python -m pytest tests/` must pass after the fix.

---

## 8. Resolution

**Fixed in session**: 2026-07-02
**Fix location**: `src/converters/citadele_source_converter.py` — `_process_purchase` and `post_process`
**Summary**: `_process_purchase` now returns the card date as a 3rd tuple element; `post_process` writes it to `TransactionDate` and sets `Description` to the merchant name only.
