# pandas3-ready

**Find the code that breaks, or worse silently changes, when you move to pandas 3.0.** A zero-dependency static scanner (Python 3.9+) for `.py` files and Jupyter notebooks. pandas 3.0 made
Copy-on-Write the only mode, so `df["a"].fillna(0, inplace=True)` and `df["a"][0] = 1` **no longer change the DataFrame and raise nothing**; it removed `applymap`, `fillna(method=)`,
`groupby(axis=)`, `read_csv(delim_whitespace=)`, `errors="ignore"` and the `H`/`T`/`M`/`Q`/`Y` offset aliases (those raise); and text columns now have the `str` dtype, so `dtype == object` is `False` and
`astype("int64") // 10**9` on a datetime column is off by a factor of 1000. Every rule was run on **real pandas 2.3.3 and pandas 3.0.0 / 3.0.6** (168 cases, see the [validation table](#validation--results));
nothing is mocked. It emits **SARIF** and GitHub annotations and ships as a **GitHub Action** and a **pre-commit** hook. Nothing is imported or executed: it reads the syntax tree.

[![CI](https://github.com/cosmichackerx/pandas3-ready/actions/workflows/ci.yml/badge.svg)](https://github.com/cosmichackerx/pandas3-ready/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/cosmichackerx/pandas3-ready?sort=semver)](https://github.com/cosmichackerx/pandas3-ready/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**The hard part, stated up front:** a static scanner cannot know that `x` is a DataFrame. So every finding carries a **confidence**:

| Confidence | Meaning | Shown by default |
|---|---|---|
| `high` | provably pandas: a module-qualified pandas API (`pd.read_csv(..., delim_whitespace=True)`), or a receiver this file assigned from pandas (`df = pd.read_csv(...)`, `df2 = df.copy()`, `self.df = pd.DataFrame()`, `d: pd.DataFrame`) | yes |
| `medium` | pandas vocabulary on a receiver we cannot type (`x.fillna(0, inplace=True)` where `x` is a parameter, `.applymap`, `.resample("M")`), in a file that imports pandas | yes |
| `low` | only the shape matches (`cfg["a"]["b"] = 1`) | no (`--min-confidence low`) |

Methods whose names other libraries share (`.bool()`, `.view()`, `.ravel()`, `.swapaxes()`, `astype(copy=)`) are only reported on a provably-pandas receiver. Files that do not import pandas are skipped.
The [precision study](#precision-study) reports the numbers per confidence level.

## At a glance

|  | Lite (try it in a minute) | Full (keep it in CI) |
|---|---|---|
| How | `pipx install git+https://github.com/cosmichackerx/pandas3-ready@v0.3.0` then `pandas3-ready .` (read-only, no network) | the [GitHub Action](#github-action) (SARIF, job summary, PR comment), the [pre-commit](#pre-commit) hook and `--base origin/main` [PR mode](#pr-mode) |
| You get | a list of `file:line` findings with severity and confidence; exit code 1 on errors | the same on every pull request, only for lines the PR touches, in the Security tab as SARIF |
| Not included | fixing the code (`--fix` is on the roadmap) | running your tests: pandas 3 changes data-dependent behaviour that no static tool sees |

## Validation / results

Every number below is from this repository's own tests or scripts. "Not proven" is as important as "Result".

| What is claimed | Checked against | Size | Result | Not proven |
|---|---|---|---|---|
| Each rule's claim about pandas 3 (raises / silently changes / warns) is true | **Real pandas 2.3.3** and **real pandas 3.0.0 and 3.0.6**, in separate virtualenvs ([`tests/oracle/`](tests/oracle/)): each case is a small program run on both, and its outputs, exceptions and warnings are compared | 168 cases x 2 | all as expected on 3.0.0 and 3.0.6: the positive cases raise, change output or warn as the rule says; the negative cases behave the same on both versions | pandas 3.1 and later (a weekly job runs the newest 3.x); Python versions other than 3.13 for the oracle; data-dependent behaviour |
| The scanner agrees with pandas on every case | The oracle also runs the scanner on each case's code: the rule must fire at the default confidence on positives and nothing may be reported on negatives | 164 | 164/164 | code the cases do not cover |
| The recommended fix is equivalent | The fixed version of each case that has one is run on both pandas versions: same output on both, no warning on 3.x, and the scanner no longer reports it | 105 fixed cases | all equal | whether the fix is right for your data types |
| Detection on real code | A [precision study](docs/precision-study.md): 5,887 public files in 5,525 repositories found by read-only code search, **248 findings labelled by hand** (sample A, v0.1.0) and 82 more after the fixes (sample B), with Wilson 95% intervals | v0.1.0 sample: **`high` 119 of 120 correct (99%), `medium` 92 of 98 (94%; 6 unclear), `low` 9 of 20 (hidden by default)**. 18 false positives in 7 classes, 7 fixed in v0.3.0; sample B after the first fixes: `high` 43 of 43, `medium` 33 of 35 | Convenience sample (search relevance order, queries chosen to make rules fire), one labeller who wrote the scanner, recall not measured, per-rule intervals wide (at most 8 items per rule and level). Not re-sampled after the last two fixes |
| Mechanical rewrites of `--fix` keep the program's behaviour | The [fix oracle](tests/oracle/run_fix_oracle.py): original code on pandas 2.3.3, fixed code on 2.3.3 and 3.0.x; outputs compared, deprecation warnings, idempotence, refusals | 75 cases (63 fix, 12 refusal) | 0 problems on 2.3.3 vs 3.0.0 and 3.0.6 | Only small programs; real projects' outputs; other pandas versions; Python other than 3.13 |
| Unit tests | `pytest`: positives, negatives (numpy, torch, itertools, str.replace, dict-of-dict), confidence levels, notebooks, suppression, outputs, PR mode, sticky comment | 120+ unit tests | pass on Ubuntu, Windows, macOS with Python 3.9, 3.11, 3.13 | |

## Install and run

```
pipx install git+https://github.com/cosmichackerx/pandas3-ready@v0.3.0      # or: pip install git+https://github.com/cosmichackerx/pandas3-ready@v0.3.0
pandas3-ready .                          # scan the current repository (.py and .ipynb)
pandas3-ready . --base origin/main       # PR mode: only what this branch introduces
pandas3-ready . --diff                   # show the mechanical fixes as a unified diff (writes nothing)
pandas3-ready . --fix                    # apply them in place (.py only)
pandas3-ready . -f sarif -o pandas3.sarif --fail-on never
pandas3-ready . --min-confidence high    # only provably-pandas findings
pandas3-ready --list-rules
```

From a checkout without installing: `PYTHONPATH=src python -m pandas3_ready .`

Exit code: 0 clean, 1 findings at or above `--fail-on` (default `error`), 2 usage error. Output formats: `text`, `markdown`, `json`, `github` (annotations), `sarif` (with `rank` and `properties.confidence`).
Options: `--ignore GLOB`, `--disable RULE`, `--only RULE`, `--min-confidence`. Suppress one finding with a comment on the same or the previous line:
`# pandas3-ready: ignore [chained-assignment]` (no rule list means all rules). Directories such as `.git`, `venv`, `node_modules`, `site-packages` are skipped.

Notebooks: code cells are read in order (variables flow between cells), `%magics` and `!shell` lines are blanked, `%%bash`-style cells are skipped, and the reported line points into the `.ipynb` JSON with the cell number.

## Example output

`pandas3-ready tests/fixtures/legacy/report.py` (a made-up report script; the file is in the repository):

```
report.py
      7:1    error   high   removed-option           mode.use_inf_as_na was removed in pandas 3 (OptionError); replace inf with NaN before
     11:10   error   high   removed-keyword          read_csv(delim_whitespace=...) was removed in pandas 3: use sep=r"\s+"
     12:5    warning high   chained-inplace          `.fillna(..., inplace=True)` on a column/selection operates on a temporary copy in pandas 3: the DataFrame is left unchanged (no error, only a warning)
     13:5    warning high   chained-assignment       chained assignment: the first indexing step returns a copy in pandas 3, so this write never reaches the DataFrame; index once with .loc[rows, col]
     19:51   error   medium removed-offset-alias     frequency alias 'M' was removed in pandas 3 (ValueError); use 'ME'
     20:14   note    medium select-dtypes-object     select_dtypes(include=object) still selects text columns in pandas 3 but warns that it will stop
     21:43   warning medium object-dtype-check       `dtype == object` is False for text columns in pandas 3 (they use the str dtype)
     24:19   warning medium datetime-ns-assumption   datetime cast to int64 and divided by 1e9: pandas 3 may store seconds, ms or us instead of ns, so the result can be off by 1000 or more
     25:14   error   medium removed-keyword          .groupby(axis=...) was removed in pandas 3: transpose first (df.T.groupby(...))
     26:14   error   medium removed-method           .applymap(): renamed to DataFrame.map (Styler.applymap -> Styler.map)
     31:12   error   high   raw-string-reader        read_json() with literal text: pandas 3 treats a str as a path or URL; wrap it in io.StringIO
     31:43   error   high   errors-ignore            to_numeric(errors='ignore') was removed in pandas 3; catch the error or use errors='coerce'

1 Python file(s) scanned, 1 import pandas; behaviour checked on pandas 2.3.3 and 3.0.6. 7 error, 4 warning, 1 note.
```

## Fix the mechanical ones (`--fix`, `--diff`)

`--diff` prints a unified diff of what `--fix` would change and writes nothing (exit 1 if anything would change); `--fix` applies it. Only rewrites that the [fix oracle](tests/oracle/run_fix_oracle.py) proved on real pandas are applied; everything else stays a finding for a human. Each rewrite is a small program run on pandas 2.3.3 (original) and on 2.3.3 and 3.0.x (fixed): the fixed program must print exactly what the original printed on 2.3.3, raise no deprecation warning, and a second `--fix` must change nothing.

| Before | After | Needs |
|---|---|---|
| `fillna(method="ffill")`, `"pad"` | `.ffill()` (keeps `limit`, `axis`, `inplace`) | pandas 2.0 |
| `fillna(method="bfill")`, `"backfill"` | `.bfill()` | pandas 2.0 |
| `df.applymap(f)` | `df.map(f)` | **pandas 2.1** |
| frequency aliases `H`, `BH`, `CBH`, `T`, `L`, `U`, `N`, `S` (also `2H`, `30T`) | `h`, `bh`, `cbh`, `min`, `ms`, `us`, `ns`, `s` | **pandas 2.2** |
| `M`, `Q`, `Y`, `A`, `BM`, `AS` ... where a datetime frequency is certain (`date_range`, `Grouper`, `shift(freq=)`) | `ME`, `QE`, `YE`, `YE`, `BME`, `YS` ... | pandas 2.2 |
| `Timedelta` / `to_timedelta` units `T`, `L`, `U`, `N`, `H` | `min`, `ms`, `us`, `ns`, `h` | pandas 2.2 |
| `read_csv(..., delim_whitespace=True)` | `sep=r"\s+"` | any |
| `infer_datetime_format=True/False` in `read_csv`, `read_table`, `to_datetime` | removed (no effect since pandas 2.0) | pandas 2.0 |
| `copy=True/False` in the calls that lost it, `high` confidence only | removed | see below |

Not rewritten, with the reason on stderr: `resample("M")` / `asfreq("M")` (valid on a `PeriodIndex`, so the right spelling depends on the index); `fillna(value, method=...)`, `downcast=`, `**kwargs` or a method that is not a string literal; `delim_whitespace` together with `sep` or `delimiter`, or not literally `True`; a keyword separated from its neighbours by a comment; overlapping edits; anything whose result would not parse. Only the aliases that mean the same on a `DatetimeIndex` and a `PeriodIndex` are rewritten at `medium` confidence, the others need `high`. `# pandas3-ready: ignore` comments are honoured. **Jupyter notebooks are never rewritten** (counted and reported; edit them in Jupyter).

Know before you run it: `copy=False` no longer shares memory on pandas 3, so removing it is what pandas 3 does anyway; code that relied on a shared buffer was already wrong there. The new spellings (`h`, `min`, `ME`, `.map`) need pandas 2.1/2.2 or later, so run `--fix` after raising your minimum pandas, not before.

On the study corpus (a local **copy** of 5,887 public files; nothing in anyone's repository was written): `--fix` made **846 edits in 313 files**, declined 119 with a reason, and left 935 notebooks alone. All 313 rewritten files still parse. A second `--fix` made 0 edits. This shows the rewrites apply cleanly at scale; it does not show that those projects' own outputs are unchanged (proved only for the oracle programs).

## Rules (19)

The last column is the number of oracle cases per rule (positive cases; 54 more negative cases are shared by all rules).

| Rule | Severity | What pandas 3 does | Instead | Cases |
|---|---|---|---|---|
| `chained-inplace` | warning | df[col].method(..., inplace=True): the method runs on a temporary copy, so pandas 3 silently leaves the DataFrame unchanged | Assign the result: df[col] = df[col].fillna(0), or pass a dict: df.fillna({col: 0}, inplace=True). | 5 |
| `chained-assignment` | warning | df[a][b] = v or df[a].loc[b] = v: the first indexing step is a copy, so pandas 3 silently does not write to the DataFrame | Index once: df.loc[b, a] = v (or df.iloc[i, j] = v). | 7 |
| `readonly-array-write` | error | df[col].values[i] = v / df.to_numpy()[i] = v: the array is read-only in pandas 3 (ValueError), or a copy when dtypes are mixed | Write through pandas: df.loc[...] = v, or copy first: arr = df.to_numpy(copy=True). | 3 |
| `removed-offset-alias` | error | A frequency alias that pandas 3 removed (H, T, L, U, N, S, M, Q, Y, A, BM, BQ, BA, SM, AS, ...): ValueError | Use the new alias: h, min, ms, us, ns, s, ME, QE, YE, BME, BQE, BYE, SME, YS. | 34 |
| `removed-timedelta-unit` | error | A Timedelta unit that pandas 3 removed (T, L, U, N) or deprecated (H) | Use min, ms, us, ns, h. | 6 |
| `removed-method` | error | A method or function that pandas 3 removed (applymap, swapaxes, Series.bool/view/ravel, first/last, pd.value_counts, ...) | Use the replacement named in the message. | 10 |
| `removed-keyword` | error | A keyword argument that pandas 3 removed (fillna(method=), read_csv(delim_whitespace=), groupby(axis=), resample(kind=), ...) | Use the replacement named in the message. | 14 |
| `errors-ignore` | error | errors="ignore" in to_datetime / to_numeric / to_timedelta: removed in pandas 3 | Catch the exception, or use errors="coerce" and check for NaT/NaN. | 4 |
| `raw-string-reader` | error | read_json / read_html / read_xml with a literal JSON, HTML or XML string: pandas 3 reads it as a file path | Wrap it: pd.read_json(io.StringIO(text)). | 3 |
| `removed-option` | error | pd.set_option("mode.use_inf_as_na", ...): the option no longer exists | Replace inf with NaN before: df.replace([np.inf, -np.inf], np.nan). | 1 |
| `cow-option` | note | mode.copy_on_write is set: Copy-on-Write is always on in pandas 3 and the option does nothing (it warns) | Remove the line. | 2 |
| `include-groups` | error | groupby(...).apply(..., include_groups=True): pandas 3 raises ValueError | Drop the argument (the group columns are not passed to the function) and select them explicitly if needed. | 1 |
| `stack-legacy-args` | error | DataFrame.stack(dropna=..., sort=...): pandas 3 raises ValueError (future_stack=False is deprecated) | Remove dropna/sort; call .dropna() or .sort_index() afterwards. | 3 |
| `pct-change-fill` | error | pct_change(fill_method='pad'/..., limit=...): removed in pandas 3 (fill_method must be None) | Fill first (df.ffill()), then call pct_change(). | 2 |
| `object-dtype-check` | warning | dtype == object / is_object_dtype(...): False for text columns in pandas 3, which use the str dtype | Use pd.api.types.is_string_dtype(...) or check both: dtype == object or pd.api.types.is_string_dtype(dtype). | 4 |
| `select-dtypes-object` | note | select_dtypes(include=object): pandas 3 still selects text columns but warns that it will stop | Use include=['object', 'string'] (the same on pandas 2.3.3 and 3.x). | 1 |
| `astype-str-na-literal` | warning | x.astype(str) compared with or replacing the text 'nan'/'None': pandas 3 keeps missing values missing instead of turning them into those strings | Test x.isna() before the cast. | 5 |
| `datetime-ns-assumption` | warning | datetime values cast to int64 and divided by 1e9: pandas 3 may store seconds, ms or us instead of ns, so the result is off by 1000 or more | Divide a Timedelta instead: (ts - pd.Timestamp('1970-01-01')) // pd.Timedelta('1s'). | 4 |
| `copy-keyword` | note | copy=... on astype/reindex/rename/merge/concat: deprecated in pandas 3, it has no effect (Copy-on-Write) | Remove the argument; call .copy() if you need a copy. | 5 |

* `error` = raises on pandas 3. `warning` = runs but gives a different result or silently does nothing. `note` = still works on pandas 3.0 but warns that it will not.
* Offset aliases: pandas 3 removed `H, T, L, U, N, S, M, Q, Y, A, BM, BQ, BA, BY, SM, CBM, AS, BAS` (also with a number or suffix: `2H`, `Q-DEC`, `AS-JAN`); 25 forms in the oracle raise on 3.x and the new spelling gives the same dates.
  `M`, `Q`, `Y` are still valid for **periods** (`period_range`, `to_period`, `Period`), so they are only reported where pandas needs a datetime frequency; `resample("M")` / `asfreq("M")` are medium confidence because they are valid on a `PeriodIndex` (a documented false-positive class, in the oracle as `resample-period-M-fp`).
* One rule fires on code that was already broken before: `df[mask]["b"] = 0` never wrote to `df`, in any pandas version (3.x now warns). The oracle marks such a case `warn3`, not a silent change.

## GitHub Action

```yaml
- uses: actions/checkout@v7
  with:
    fetch-depth: 0          # only needed for pr-mode
- uses: cosmichackerx/pandas3-ready@v0.3.0
  with:
    path: .
    fail-on: error          # error | warning | never
    min-confidence: medium  # high | medium | low
    pr-mode: true           # on pull requests report only what the PR introduces
    comment: true           # one sticky comment, updated in place (needs pull-requests: write; skipped for forks)
    sarif-file: pandas3.sarif
```

Inputs: `path`, `fail-on`, `min-confidence`, `disable`, `ignore`, `summary` (job summary), `pr-mode`, `base`, `comment`, `github-token`, `sarif-file`. Upload the SARIF with
`github/codeql-action/upload-sarif`. The action runs the scanner from its own checkout with the runner's Python; it does not install anything and makes no network calls except the sticky comment.

## pre-commit

```yaml
repos:
  - repo: https://github.com/cosmichackerx/pandas3-ready
    rev: v0.3.0
    hooks:
      - id: pandas3-ready        # report; fails the commit on errors
```

The hook scans the whole repository (`pass_filenames: false`). CI checks it with `pre-commit try-repo`.

## PR mode

`pandas3-ready . --base origin/main` scans the merge base and the working tree and reports only findings that are new (matched by rule, file and the text of the line, so moving a line does not make it new).
In the Action, `pr-mode: true` does this on pull requests. Needs git history (`fetch-depth: 0`).

## Precision study

Full write-up with method, tables and limits: [`docs/precision-study.md`](docs/precision-study.md). Short version, for the findings of v0.1.0 (248 hand-labelled out of 5,482 in 5,887 public files):

| Confidence | Shown by default | Right | Wilson 95% | Unclear |
|---|---|---|---|---|
| `high` | yes | 119 of 120 (99%) | 95% to 100% | 0 |
| `medium` | yes | 92 of 98 (94%) | 87% to 97% | 6 |
| `low` | no (`--min-confidence low`) | 9 of 20 (45%) | 26% to 66% | 4 |

What the false positives were: subscripts of **dicts of DataFrames** (`data['a'].fillna(0, inplace=True)` is fine when `data` is a dict), NumPy arrays that look like pandas, conditions that already handle the string dtype, `scipy.signal.resample(axis=)`, a list of frames indexed by position. Most are fixed in v0.3.0; the ones that need type inference (a dict returned by a function, an attribute holding a dict of frames) are not and stay `medium`. 36% of all findings were inside vendored copies of pandas itself; those directories are now skipped.

Not claimed: this is a convenience sample labelled by one person, **recall was not measured**, and a "true" finding means the pattern behaves as described on pandas 3, not that the project is broken (many hits are old notebooks pinned to old pandas).

## How it is verified

* **Unit tests** (`pytest`, 70+ cases, [`tests/`](tests/)). CI runs them on Ubuntu, Windows and macOS with Python 3.9, 3.11 and 3.13.
* **Oracle** ([`tests/oracle/run_oracle.py`](tests/oracle/run_oracle.py)): `--exec` runs all 168 cases with the pandas installed in the current environment, the comparison step checks both runs and the scanner. Run it yourself:
  `python -m venv old && old/bin/pip install pandas==2.3.3 lxml && python -m venv new && new/bin/pip install pandas==3.0.6 lxml`, then `old/bin/python tests/oracle/run_oracle.py --exec old.json`, the same for `new`, then `python tests/oracle/run_oracle.py old.json new.json`.
  A weekly workflow repeats it against the newest pandas 3.x.
* **Action, packaging, pre-commit** self-tests in CI, plus a check of the Marketplace limits for `action.yml` (name, description of at most 125 characters, branding).
* CI also runs [dependabot-gaps](https://github.com/cosmichackerx/dependabot-gaps), [node24-ready](https://github.com/cosmichackerx/node24-ready) and [claims-check](https://github.com/cosmichackerx/claims-check) (the numbers in this README are checked against the code, and a release gate checks the pins against the tag) on this repository.

## Related tools

Same author, same style (static, zero dependencies, SARIF, oracle-validated):
[kafka4-ready](https://github.com/cosmichackerx/kafka4-ready) (Kafka 3 to 4), [helm4-ready](https://github.com/cosmichackerx/helm4-ready) (Helm 3 to 4), [node24-ready](https://github.com/cosmichackerx/node24-ready) (GitHub Actions on Node 24),
[dependabot-gaps](https://github.com/cosmichackerx/dependabot-gaps), [claims-check](https://github.com/cosmichackerx/claims-check) (keeps README numbers true),
[sha256-ready](https://github.com/cosmichackerx/sha256-ready), [gradle10-ready](https://github.com/cosmichackerx/gradle10-ready), [kotlin24-ready](https://github.com/cosmichackerx/kotlin24-ready).

What else exists for the pandas 3 move (read from documentation and issue threads on 2026-10-03; mostly not run by me):

* **pandas itself.** On 2.3 you can turn on `pd.options.mode.copy_on_write = "warn"` and run your code with `-W error::FutureWarning`; pandas reports `ChainedAssignmentError` / `FutureWarning` for many of the cases below *when the line executes*. It is the most precise
  tool for the lines your tests reach, and the official [migration guide](https://pandas.pydata.org/docs/user_guide/migration.html) recommends upgrading to 2.3 first. pandas3-ready reads files, so it also sees the branches, notebooks and scripts your tests never run; it cannot see data-dependent behaviour (e.g. `astype(str)` on a column that happens to contain NaN).
* **pandas-stubs 3.0 with mypy/pyright** catches removed or changed signatures in typed code; it needs annotations, and stub updates can lag pandas (an Apache Spark lint-image change pinned them for this reason).
* **ruff** has a `PD` rule family (pandas-vet) for style and performance. I did not find a pandas-3 migration rule in it; I did not read all of its rules.
* **[pdperf](https://github.com/goutamadwant/pdperf)** is a performance linter; its chained-indexing rule overlaps with `chained-assignment`, its purpose is different.
* Code review with an LLM is used by some projects (one public issue pastes such a review of a repository). I did not evaluate that.

I found no other static scanner dedicated to pandas 3 removed APIs and silent behaviour changes in my search; that is not proof there is none.

## Limitations (read these)

* **No type inference.** Evidence comes from assignments in the same file (and earlier cells), annotations and module-qualified calls. A DataFrame returned by your own function, a parameter without annotation, or `df = other.method()` stays unknown (medium at best). Recall is therefore limited, and was not measured.
* Aliasing is not followed: `s = df["a"]; s.iloc[0] = 1` (which no longer updates `df`) is not reported, and neither is `astype(str)` assigned to a variable and compared with `"nan"` later. Only the written patterns above are matched.
* Data-dependent changes (`astype(str)` on NaN, `groupby(observed=)` defaults, integer-key `Series[...]`, `apply` passing group columns, `pct_change()` default fill) are not detected unless the code spells the dependency out.
* Rules hold for pandas 2.3.3 vs 3.0.0 and 3.0.6 on CPython 3.13/Linux only. Behaviours that were deprecated but still work on 3.0 are `note`s, and may be errors in pandas 4.
* The [precision study](docs/precision-study.md) is a convenience sample labelled by one person; the final v0.3.0 scanner was not re-sampled after its last two fixes, `cow-option` and `include-groups` had too few findings to say anything, and recall is unmeasured.

## Roadmap

See the [open issues](https://github.com/cosmichackerx/pandas3-ready/issues).

## License

MIT, see [LICENSE](LICENSE).
