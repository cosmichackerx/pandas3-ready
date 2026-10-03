# Changelog

## 0.3.0 - 2026-10-04

* **`--fix` and `--diff`**: auto-apply only rewrites proven on real pandas by the new fix oracle (75 cases: 63 fix, 12 refusal; 0 problems on 2.3.3 vs 3.0.0 and 3.0.6): `fillna(method=)` to `.ffill()`/`.bfill()`, `applymap` to `map`, `H/T/L/U/N/S` and `M/Q/Y/A` aliases where the datetime context is certain, Timedelta units, `delim_whitespace=True` to `sep=r"\s+"`, `infer_datetime_format` and `copy=` removal. Ambiguous cases (`resample("M")` on a possible PeriodIndex, `fillna(value, method=)`, comments between arguments) are refused with a reason. Idempotent. Notebooks are never rewritten.
* Dry run on a local copy of the study corpus: 846 edits in 313 files, all still parse.
* `--fix` and `--diff` cannot be combined with each other or with `--base`.
* SyntaxWarnings from parsing other people's code are silenced.

## 0.2.0 - 2026-10-03

* **Precision study** on 5,887 public files (5,525 repositories), 248 findings hand-labelled (`docs/precision-study.md`, `study/`): `high` 119/120 correct, `medium` 92/98, `low` 9/20. Findings of v0.1.0 were wrong in 18 cases; 7 classes found.
* False positives fixed: subscripts of dicts of DataFrames (`data['a'].fillna(0, inplace=True)`), `.asi8` (NumPy array) with `astype(copy=False)`, `dtype == 'object'` in a condition that already accepts the string dtype, `dfs[0].rename(inplace=True)` (positional index on a list), functions of other libraries called through an imported module (`scipy.signal.resample(axis=)`).
* Vendored copies of pandas (a `pandas/` directory with `core/`, `_libs/` or `tests/`) are skipped: 36% of all findings in the corpus were in such copies.
* Oracle: 4 new negative cases (168 in total, 0 disagreements on pandas 2.3.3 vs 3.0.0 and 3.0.6). 84 unit tests.

## 0.1.0 - 2026-10-03

First release. Nineteen rules for the move to pandas 3.0, each run on real pandas 2.3.3 and on pandas 3.0.0 and 3.0.6 (`tests/oracle/`, 164 cases).

* Scans `.py` files and Jupyter notebooks (code cells in order, magics blanked) with the standard-library `ast`; nothing is imported or run. Files that do not import pandas are skipped.
* Every finding has a confidence: `high` (provably pandas), `medium` (pandas vocabulary on an untyped receiver), `low` (shape only, hidden unless `--min-confidence low`).
* Silent changes: `chained-inplace`, `chained-assignment`, `object-dtype-check`, `astype-str-na-literal`, `datetime-ns-assumption`. Errors: `readonly-array-write`, `removed-offset-alias`, `removed-timedelta-unit`, `removed-method`, `removed-keyword`, `errors-ignore`, `raw-string-reader`, `removed-option`, `include-groups`, `stack-legacy-args`, `pct-change-fill`. Notes: `cow-option`, `select-dtypes-object`, `copy-keyword`.
* Text, markdown, JSON, GitHub annotation and SARIF 2.1.0 output; PR mode (`--base`) with a sticky comment; GitHub Action and pre-commit hook; `# pandas3-ready: ignore [rule]` comments.
* CI: tests on Ubuntu/Windows/macOS with Python 3.9/3.11/3.13, the oracle on two pandas 3 versions, Action/pre-commit/package self-tests, claims-check (README numbers and, on release, the pins), a weekly run of the oracle against the newest pandas 3.x.
