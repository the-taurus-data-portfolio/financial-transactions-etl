# Tool/Service Feedback: financial-transactions-etl

<!-- IMPORTANT: Always add the newest feedback/session entry at the TOP of the file (immediately below this comment). Do not append to the bottom. -->

## Session: 2026-07-01 — Code Done, bug fixes, real-file validation

### 1. Implementation Issues

**`tiller_converter._get_accounts_data_for_lookup` called non-existent method (pre-existing bug, now fixed):**
`self.schema_loader.load_config_file()` does not exist on `YamlSchemaLoader` (only `load_schema` and `load_mapping` exist, both prepend fixed dirs). This generated an ERROR log on every Tiller transform call (3× per file). Fixed with direct `yaml.safe_load()` — same pattern already used by `_load_accounts_config` in the same class.

**Archiving erases sample files when `--input-dir data/samples/transactions/` is used:**
Pipeline with archiving enabled will archive all successfully processed files — including sample files. If a developer accidentally runs `--input-dir data/samples/transactions/` with production config, all samples are moved to `data/archive/`. Mitigated this session by disabling archiving in `config_test.yaml`, but no guardrail exists at the code level.

**Duplicate TransactionID for "Value Date" rows:**
Two interest/forex-adjustment rows share the same `Bank Reference` (`60100000873757-20260630`) in the Citadele export, producing identical `TransactionID`. One will be silently dropped by deduplication on the next import. Root cause: Citadele reuses the same Bank Reference for related debit/credit pairs. Needs investigation next session.

**OtherAccountName = NaN for "Value Date" rows:**
These rows have a Narrative like `"Value Date: 01.07.2026"` with no recognisable counterparty — `post_process` finds no tokens to extract. Returns `NaN`. Needs a fallback (e.g., empty string or "Citadele").

### 3. Proposed Improvements & Backlog Items
- **Backlog**: Investigate "Value Date" duplicate Bank Reference — consider appending row index or amount to disambiguate TransactionID.
- **Backlog**: Add NaN fallback in `CitadeleSourceConverter.post_process` for rows where counterparty cannot be extracted — use `""` or `Description` value.
- **Backlog**: Add guard in local source provider or archiver to skip files in `data/samples/` directories, or add a `protect_samples: true` config flag.

---

## Session: 2026-07-01 — Citadele implementation

### 1. Implementation Issues

**`_read_header_from_file_object` inconsistency (pre-existing bug, now fixed):**
`_detect_delimiter_from_file_object` correctly checks `len(header_row) > 1` before accepting a delimiter match. `_read_header_from_file_object` did not — it accepted any non-empty single-column result, which caused the first delimiter tried (`;`) to win even on pipe-delimited files, returning a garbled single-string header. Fixed this session by adding the same `> 1` guard.

**No `Agents.md` in this project:**
The matrix-routing process requires reading `Agents.md` to discover project context (language, type, layer). This project has none. Project type/language had to be inferred from `README.md` and code inspection. `Agents.md` should be created.

**Factory pattern is a plain dict in `etl_pipeline.py`:**
The `_CONVERTER_MAP` is defined as a local variable inside `process_single_file`. As more banks requiring subclasses are added, this will become a maintenance burden. A module-level registry or class-based factory would be cleaner. Not critical for now.

### 3. Proposed Improvements & Backlog Items

- **Backlog**: Create `Agents.md` for `financial-transactions-etl` to enable proper matrix-routing in future SWE sessions.
- **Backlog**: Refactor converter factory (`_CONVERTER_MAP` in `etl_pipeline.py`) to a module-level registry when a second bank-specific converter is added.
- **Backlog**: Update `docs/how-to-add-bank.md` with a "Banks with metadata prefix rows" section documenting `skip_header_rows` + `detection_header_row` workflow for banks like Citadele.

---

## Session: 2026-07-01 — Design review: post_process redesign

### 1. Implementation Issues

No code written (design iteration only). Design-level findings:

**post_process signature correctly designed from the start:**
`post_process(intermediate_df, source_df)` — both DataFrames passed so subclasses can read
any source column (e.g. `Type`) without polluting the intermediate schema. No backlog item needed.

**OtherAccountName for purchases includes location noise:**
Accepted as a known limitation (merchant + city + country + bank ref all go into the field).
Future improvement: implement strip-from-right once the design is proven in production.

### 2. Proposed Improvements & Backlog Items

- ~~`post_process` signature~~ — resolved in design: `post_process(intermediate_df, source_df)` from the start.
- **Backlog**: Purchase `OtherAccountName` cleanup (strip trailing location/country/bank-ref) — defer until post-implementation validation.

---

## Session: 2026-06-30 — Design: Citadele bank support

### 1. Implementation Issues

No code was written this session (design phase only). Issues identified during design analysis:

**Architecture gap — `GenericSourceConverter` is not extensible:**
The current design is purely data-driven; all logic lives in YAML. This works well for standard
CSV formats but breaks down for non-standard cases (Citadele: multi-row header, no per-row IBAN,
embedded-sign amounts). The only option today is to add hacks to the generic converter
(special YAML fields like `header_extractions`, special transformation types like `regex_extract`).

The agreed resolution: add `extract_header`, `extract_footer`, `post_process` hook methods to
the parent class + a `CitadeleSourceConverter` subclass. This is the right architectural direction
but it requires updating the factory/instantiation logic to map bank IDs to converter classes.

**Missing: converter factory / registry:**
There is no factory pattern for converter instantiation. Currently `GenericSourceConverter` is
instantiated directly with the bank type string. Once subclasses exist, this becomes a problem.
A registry (`{"citadele": CitadeleSourceConverter, ...}`) needs to be added before implementation.

**Missing: `Agents.md` or equivalent for this project:**
No `Agents.md` was found in this repository. The SWE role requires reading it at session start.
Either the project never had one, or it was not created. This means the agent cannot load
project-specific context reliably.

### 2. Interface & Usage Issues

No interface issues encountered (design-only session).

### 3. Proposed Improvements & Backlog Items

The following should be added to `docs/Changes_Backlog.md`:

1. **Add converter factory/registry** — map bank ID strings to converter classes so that
   bank-specific subclasses (`CitadeleSourceConverter`) can be instantiated automatically
   without hardcoding in `etl_pipeline.py`.

2. **Create `Agents.md`** — the project has no agent context file. Create one with at minimum:
   project overview, architecture summary, key file paths, and a pointer to
   `docs/how-to-add-bank.md`.

3. **`not_empty` filter operator** — needed for Citadele footer removal; not yet implemented.

4. **`direct_float` transformation type** — needed for Citadele embedded-sign amounts; not yet
   implemented.
