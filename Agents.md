# financial-transactions-etl — Agents.md

## Project Context
- **Type**: Service
- **Layer**: Backend
- **Language**: Python
- **Frameworks**: pandas, PyYAML

## Description
ETL pipeline that converts bank transaction CSV exports from multiple Estonian banks into
Tiller Money format for Google Sheets import. Supports automatic bank detection, deduplication
against an existing Tiller sheet, and optional archiving.

## Communication
Follow [`philosophy.md`](~/ai-agents/agents/docs/philosophy.md) (Communication & Language Standards).
- **Mirror the user's language in chat**: reply in the language the user writes in (Russian → Russian,
  English → English). Technical terms and entities stay in English.
- Documentation artefacts (docs, feedback, progress) are always in English.

---

## Entry Points

### CLI
```bash
# Production (real bank files from data/transactions/)
./venv/bin/python src/main.py --input-dir data/transactions

# Development (sample files, no Sheets auth needed)
./venv/bin/python src/main.py --input-dir data/samples/transactions --config config/config_test.yaml

# Tests
make test
```

| Flag | Default | Description |
|---|---|---|
| `--input-dir DIR` | — | Directory containing bank CSVs (required) |
| `--config FILE` | `config/config.yaml` | Config file path |
| `--bank TYPE` | auto-detected | Override bank detection for all files in the batch |
| `--verbose / -v` | off | Enable DEBUG-level logging |
| `--dry-run` | off | Validate config and schema, skip processing |

### VS Code (`.vscode/launch.json`)
| Config name | What it runs |
|---|---|
| `Run (financial transactions)` | `src/main.py --config config/config.yaml` — set `--input-dir` in args before running |
| `Run tests (financial transactions)` | `src/main.py --config config/config_test.yaml` — set `--input-dir` in args before running |

---

## Make Commands

| Target | Command | Notes |
|---|---|---|
| `make setup` | Create venv + `pip install -r requirements.txt` | One-time project setup |
| `make install` | `pip install -r requirements.txt` into existing venv | Re-sync deps after pulling |
| `make run INPUT_DIR=<path>` | `python src/main.py --input-dir <path>` | Requires `INPUT_DIR`; uses production config |
| `make test` | `pytest tests/ -v` | conftest.py adds `src/` to sys.path |
| `make clean` | Remove venv + `__pycache__` / `.pyc` files | Full env teardown |
| `make logs-clean` | `rm -rf logs/* output/*` | Clear generated output |

> VS Code does **not** use the Makefile — it invokes `src/main.py` directly via `launch.json`.

---

## Architecture

### Source layout
```
src/
  core/        — pipeline orchestrator, ABCs, config, schema loading, source providers, archivers
  converters/  — bank source converters (generic + subclasses), target converter, bank detector
  utils/       — CSV, date, string, file, Google Sheets, logging utilities
schemas/       — YAML source/target schemas per bank
mappings/      — YAML field mapping rules per bank
config/        — YAML config (production + test), Tiller account mappings
tests/         — pytest test suite
data/
  samples/transactions/  — anonymised CSVs (one per bank variant); also the detection signatures
  transactions/          — real bank exports (not committed)
  archive/               — destination after successful local archiving
```

### Data flow
```
Source CSV(s)
  → SourceProvider          (local / GDrive)
    → BankDetector          (exact header match vs sample file signatures)
      → SourceConverter     (GenericSourceConverter or subclass)
          extract_header()      → virtual columns (e.g. IBAN, currency for Citadele)
          load_source_data()    → source DataFrame
          filter_rows()
          transform_to_intermediate()
          post_process()        → intermediate DataFrame
        → TillerConverter
            deduplication       (load existing TransactionIDs from Google Sheets)
            transform_to_target()
          → save_output()       (CSV file + clipboard TSV)
  → Archiver                (local / GDrive — only on 100% batch success)
```

### Configuration files
| File | Purpose |
|---|---|
| `config/config.yaml` | Production: GDrive source, archiving enabled, live Sheets dedup |
| `config/config_test.yaml` | Development: local source `data/samples/transactions`, archiving off |
| `config/tiller/accounts.yaml` | Real IBAN → Tiller account name/ID mapping |
| `config/tiller/accounts_sample.yaml` | Anonymised mapping for sample/test runs |

---

## Supported Banks

### YAML artefacts per bank
| Bank key | Source schema | Mapping | Sample file(s) |
|---|---|---|---|
| `swedbank` | `schemas/swedbank_source.yaml` | `mappings/swedbank_to_intermediate.yaml` | `swedbank_sample_ee.csv`, `swedbank_sample_ru.csv` |
| `seb` | `schemas/seb_source.yaml` | `mappings/seb_to_intermediate.yaml` | `seb_sample_ee.csv` |
| `lhv` | `schemas/lhv_source.yaml` | `mappings/lhv_to_intermediate.yaml` | `lhv_sample_ee.csv` |
| `lhv_legacy` | `schemas/lhv_legacy_source.yaml` | `mappings/lhv_legacy_to_intermediate.yaml` | `lhv_sample_legacy_ee.csv` |
| `luminor` | `schemas/luminor_source.yaml` | `mappings/luminor_to_intermediate.yaml` | `luminor_sample_ee.csv` |
| `citadele` | `schemas/citadele_source.yaml` | `mappings/citadele_to_intermediate.yaml` | `citadele_sample_ee.csv` |

Sample files live in `data/samples/transactions/`.

### Bank format comparison
| Property | Swedbank | SEB | LHV (modern) | LHV (legacy) | Luminor | Citadele |
|---|---|---|---|---|---|---|
| **Delimiter** | `;` | `;` | `,` | `,` | `;` | `\|` (pipe) |
| **Decimal separator** | `,` | `,` | `.` | `.` | `,` | `.` |
| **Date format** | `DD.MM.YYYY` | `DD.MM.YYYY` | `YYYY-MM-DD` | `YYYY-MM-DD` | `DD.MM.YYYY` | `DD.MM.YYYY` |
| **Encoding** | UTF-8 | UTF-8 | UTF-8 | UTF-8 | UTF-8 | UTF-8 |
| **Skip header rows** | 0 | 0 | 0 | 0 | 0 | 3 |
| **Footer rows** | No | No | No | No | No | Yes (empty `Date` filtered) |
| **Amount sign** | D/K indicator | D/C indicator | D/C indicator | D/C indicator | D/C indicator | Embedded signed float |
| **IBAN source** | Per-row column | Per-row column | Per-row column | Per-row column | Per-row column | File header row 0 |
| **Currency source** | Per-row column | Per-row column | Per-row column | Per-row column | Per-row column | File header row 0 |
| **Row filter** | `Reatüüp == "20"` | None | None | None | None | Empty `Date` column |
| **TransactionID source** | `Arhiveerimistunnus` | `Arhiveerimistunnus` | `Kande viide` | `Kande viide` | `Arhiveerimiskood` | `Bank Reference` |
| **TransactionID prefix** | `SW` | `SE` | `LH` | `LH` | `LN` | `CT` |
| **Custom converter** | No | No | No | No | No | `CitadeleSourceConverter` |
| **Language variants** | EE + RU | — | — | — | — | — |
| **Columns (total)** | 11 | 15 | 16 | 19 | 12 | 7 |

### Swedbank special handling
- **Row filter** (`Reatüüp` column): exports include a balance row (`Reatüüp == "10"`) and transaction rows (`Reatüüp == "20"`). Only `"20"` rows are processed; `"10"` rows are filtered out by the mapping.
- **D/K indicator**: uses `K` for credit (Estonian: "Kreedit"), not `C` as all other banks do.
- **Language variants**: two sample files registered under the same `swedbank` config key — Estonian and Russian column headers are both valid detection signatures.

### Citadele special handling
- `extract_header()`: reads `"EUR EE52XXXXXXXXXXXX"` from row 0 → injects `Currency` + `AccountIBAN` virtual columns
- `post_process()`:
  - **PURCHASE rows**: strips card date / masked card / MCC / REF tokens; overwrites `TransactionDate` with card swipe date (from `DD/MM/YYYY` prefix in Narrative)
  - **Transfer rows**: strips IBAN, BIC, personal code, End-to-end ID; last 2 words → `OtherAccountName`
  - **Duplicate TransactionID**: same `Bank Reference` on multiple rows (e.g. CREDIT INTEREST + WITHHOLDING TAX) → suffixed `-1`, `-2` to ensure uniqueness

---

## Key Invariants
- **Archiving is atomic**: files are archived only when 100% of the batch succeeds.
- **`_CONVERTER_MAP` in `ETLPipeline`**: only banks with a custom subclass are listed; all others use `GenericSourceConverter`.
- **Sample files are the detection signatures**: header row of each sample file must exactly match real bank exports (column names, order, capitalisation). Citadele sample includes the 3-row metadata prefix.
- **`config_test.yaml` disables archiving**: always use it when running on `data/samples/transactions/` to protect sample files.
- **`header_extractions` YAML key** is defined in `citadele_source.yaml` but is not implemented in `GenericSourceConverter`. It is handled exclusively via `CitadeleSourceConverter.extract_header()`. Any future generic bank requiring header extraction must subclass.

---

## Dependency Management

**Current state**: `requirements.txt` + manual venv via `make setup`. No lockfile, no deterministic installs.

**Gap**: `requirements.txt` pins major versions loosely (or not at all). Transitive dependencies are unversioned — a `pip install` on a different machine or date can produce a different environment. There is no `requirements-dev.txt` separation for test-only packages (e.g. `pytest`).

**Migration target**: [Poetry](https://python-poetry.org/)
- `pyproject.toml` replaces `requirements.txt` (declarative deps with version constraints)
- `poetry.lock` guarantees reproducible installs
- `poetry install --without dev` for production; `poetry install` for development
- Makefile targets update to `poetry run python src/main.py ...`

Backlog item: migrate from `requirements.txt` + venv to Poetry.

---

## Documentation Index
- [`docs/how-to-add-bank.md`](docs/how-to-add-bank.md) — step-by-step guide for adding a new bank
- Financial review (statements → service → Tiller insert → receipt-based categorisation) — finance-domain skill
  `skill-financial-review` (`~/ai-agents/agents/domains/private/finance/skills/financial-review/SKILL.md`)
- [`docs/design/`](docs/design/) — bank design documents (`implemented/` and in-progress)
- [`docs/feedback/`](docs/feedback/) — SWE and other role session feedback (append-top)
- [`docs/backlog.md`](docs/backlog.md) — outstanding work items
