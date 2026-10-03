# Changelog

## 0.1.0 - 2026-10-03

First release. Nineteen rules for the move to pandas 3.0, each run on real pandas 2.3.3 and on pandas 3.0.0 and 3.0.6 (`tests/oracle/`, 164 cases).

* Scans `.py` files and Jupyter notebooks (code cells in order, magics blanked) with the standard-library `ast`; nothing is imported or run. Files that do not import pandas are skipped.
* Every finding has a confidence: `high` (provably pandas), `medium` (pandas vocabulary on an untyped receiver), `low` (shape only, hidden unless `--min-confidence low`).
* Silent changes: `chained-inplace`, `chained-assignment`, `object-dtype-check`, `astype-str-na-literal`, `datetime-ns-assumption`. Errors: `readonly-array-write`, `removed-offset-alias`, `removed-timedelta-unit`, `removed-method`, `removed-keyword`, `errors-ignore`, `raw-string-reader`, `removed-option`, `include-groups`, `stack-legacy-args`, `pct-change-fill`. Notes: `cow-option`, `select-dtypes-object`, `copy-keyword`.
* Text, markdown, JSON, GitHub annotation and SARIF 2.1.0 output; PR mode (`--base`) with a sticky comment; GitHub Action and pre-commit hook; `# pandas3-ready: ignore [rule]` comments.
* CI: tests on Ubuntu/Windows/macOS with Python 3.9/3.11/3.13, the oracle on two pandas 3 versions, Action/pre-commit/package self-tests, claims-check (README numbers and, on release, the pins), a weekly run of the oracle against the newest pandas 3.x.
