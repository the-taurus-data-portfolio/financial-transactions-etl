# Code Review — Citadele Bank Support

## Verdict: APPROVED WITH NOTES

---

## Findings

**[NOTE] Architecture — `_find_sample_for_bank` ignores `skip_rows` for Citadele**
File: `src/converters/bank_detector.py`, line 140
Issue: `_find_sample_for_bank` calls `csv_utils.read_csv_header(Path(sample_file), self.logger)` without passing `skip_rows`. For Citadele, the sample file starts with 3 metadata rows. This means the method reads row 0 of the sample (the `"Account"|"EUR ..."` metadata line) and compares it to `header_tuple`, which was matched from row 3. The comparison always fails, so `_find_sample_for_bank` always returns `None` for Citadele. The return value feeds back into `detect_bank_from_header` as `matched_sample`, which is then passed to `get_primary_sample_file` as a fallback in `etl_pipeline.py`. The net effect: bank detection still succeeds (the bank type is found), but the matched sample path is wrong (always falls through to the first sample via `get_primary_sample_file`). For a single-sample bank like Citadele this is harmless in practice, but it is a logical defect.
Expected: `_find_sample_for_bank` should read `detection_header_row` from the config for the given `bank_type` and pass it as `skip_rows` to `csv_utils.read_csv_header`, consistent with how `_load_bank_header_signatures` and `detect_bank_from_header` handle it.

**[NOTE] Config — `config_test.yaml` source type changed from `gdrive` to `local`**
File: `config/config_test.yaml`, lines 64–68
Issue: The diff changes `source.type` from `gdrive` to `local` and sets `input_dir` to `data/samples/transactions`, and sets `archiving.enabled` from `true` to `false`. These are runtime/environment changes unrelated to Citadele bank support. They may reflect the actual test setup but are bundled with the Citadele feature diff with no explanation, making future diffs harder to read and potentially masking config regressions.
Expected: If the `config_test.yaml` defaults were wrong before this PR, the fix should be in a separate commit or noted as intentional in the PR description.

**[NOTE] Repo hygiene — spurious `=7.0.0` file at repo root**
File: `/home/lokobest/services/financial-transactions-etl/=7.0.0`
Issue: An untracked file named `=7.0.0` exists at the repository root. Content is a pip version notice — this is clearly a shell paste accident (`pip install ... >=7.0.0` run with the `=` sign interpreted as a filename redirect). The file has no bearing on functionality but is noise in `git status` and could confuse future readers.
Expected: Delete the file and add `=*` to `.gitignore` as a precaution.

**[NOTE] YAML — missing newline at end of `accounts_sample.yaml`**
File: `config/tiller/accounts_sample.yaml`, line 25
Issue: File ends without a trailing newline after the last `tiller_account_id` value (confirmed with hex dump). The diff shows `\ No newline at end of file` for both the pre-change and post-change version, meaning the defect pre-dates this PR but the change touches the file and could have fixed it.
Expected: Add a trailing newline. Minor, but POSIX tools and some YAML parsers warn on files without final newlines.

**[NOTE] Test coverage — `post_process` organisation/multi-word name gap**
File: `tests/test_citadele_source_converter.py`
Issue: All transfer test cases use 2-word personal names (JANE SMITH, JOHN DOE). The DESIGN document explicitly notes "2-word personal name assumed — known limitation for org names", but there is no test asserting what happens when the counterparty has more than 2 words (e.g. a company name like "ACME CORP LTD"). Without a test, the known limitation is invisible to future editors.
Expected: Add one test case with a 3-word name to document/pin the current behaviour (last 2 words extracted, first word becomes part of Description). A `# known limitation` comment would also suffice if a test is considered out of scope.

---

## Design Fidelity

Implemented: 7 / 7 files from DESIGN.md (`schemas/`, `mappings/`, `data/samples/`, `config/config.yaml`, `config/config_test.yaml`, `config/tiller/accounts_sample.yaml`, `src/converters/citadele_source_converter.py`).

Code changes: all four code modification points from DESIGN.md are implemented — `interfaces.py` (3 new hook methods), `generic_source_converter.py` (`skip_header_rows`, `direct_float`, `not_empty`, `post_process` call), `bank_detector.py` (`detection_header_row`-aware signatures), `csv_utils.py` (`|` delimiter support). The factory wiring in `etl_pipeline.py` is also present and correct.

The `how-to-add-bank.md` guide is new (not in DESIGN.md) and accurately reflects the implementation including the `detection_header_row` config key and sample file format rules. This is an additive improvement.

The `header_extractions` block described in `how-to-add-bank.md` as a schema-driven alternative for IBAN/currency extraction is **not implemented in the generic converter** — only `CitadeleSourceConverter.extract_header()` implements it in code. The guide documents it as a schema option, but there is no corresponding code path in `GenericSourceConverter` that reads a `header_extractions` YAML key. This creates a documentation-to-code gap: a future bank author following the guide's `header_extractions` example will find it silently ignored. This is acceptable given Citadele chose the code-override path, but worth flagging.

---

## Feedback

- The `_signatures_by_skip` refactor in `BankDetector` is clean and backward-compatible. The sorted-iteration order (0 before 3) ensures standard banks are tried before prefix-heavy formats — a good implicit assumption to document as an explicit design comment in the code.
- The `_CONVERTER_MAP` dict placed inside the method body in `etl_pipeline.py` works but rebuilds the dict on every invocation of `process_file`. Moving it to module-level or class-level would be cleaner, especially as more banks accumulate.
- `tiller_converter.py`: The change from `schema_loader.load_config_file()` to direct `open(...) + yaml.safe_load()` bypasses the schema loader's caching and path resolution. The commit message doesn't explain why. If `load_config_file` was broken for this use case, the root cause should be noted in a comment.
- The sample file (`citadele_sample_ee.csv`) correctly includes the 3-row metadata prefix per the updated `how-to-add-bank.md` guidance. This is a change from the original DESIGN.md which specified the sample should omit the prefix. The `how-to-add-bank.md` reflects the final correct decision. No action needed, but the pre-existing DESIGN.md note at §3 is now stale if left as-is.
- All 32 tests pass. Test structure (one class per behaviour) is consistent and readable. Mocking is clean — no filesystem or network calls in unit tests.
