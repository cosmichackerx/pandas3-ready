# Precision study (v0.1.0 findings, v0.2.0 and v0.4.0 fixes)

Question: **when pandas3-ready reports something in real, untyped Python code, is the report right?** This is the number the README leads with, because without type inference the scanner cannot prove that a variable is a DataFrame; it can only assign a confidence level. Recall (what it misses) was **not** measured.

## What was done

1. **Collect** (`study/collect.py`): GitHub code search, read-only (no clone, no issue, no comment, no star, nothing opened on those repositories). 49 queries x up to 3 pages: 35 *targeted* queries (text typical of a rule, so that every rule has a chance to fire) and 14 *broad* queries (`import pandas as pd`, `.ipynb`, in file-size buckets, so that ordinary pandas code is in the sample). 12,107 distinct files in 10,424 repositories.
2. **Download** (`study/download.py`): a fixed-seed random subset of 3,000 targeted and 3,000 broad files, at most 3 per repository, from raw.githubusercontent.com at the commit the search returned: 5,525 repositories, 5,887 files downloaded. The list is in `study/corpus.tsv` (the files themselves are not committed). 4,184 of the files import pandas.
3. **Scan** (`study/run_scan.py`) with v0.1.0 at `--min-confidence low`, so every confidence level is in the data: **5,482 findings in 1,206 repositories**.
4. **Sample** (`study/sample.py`): stratified by rule x confidence, fixed seed 20261004, at most 8 per stratum and 2 per repository: 248 findings (sample A, `study/sample-A.json`).
5. **Label by hand** (one person, me): read each finding with a few lines of context and, when needed, more of the file. *True* = the code really does what the rule says (the receiver is a pandas object and the pandas 3 behaviour in the message applies). *False* = wrong for the file as written. *Unclear* = the file does not show enough (for example whether a column holds datetimes). Labels and reasons: `study/labels.json`.
6. **Fix** the false-positive classes found, re-scan the same files, and draw a second sample B (high and medium only, seed 777, at most 3 per stratum and 1 per repository, 82 findings, many of them also in A) to see whether the fixes held and whether new classes show up.

"True" means *the pattern is there and pandas 3 treats it as described*. It does not mean the project is broken: many hits are in old notebooks or in projects that pin pandas 1.x or 2.x.

## Result, sample A (v0.1.0)

### Per confidence level

| Confidence | Findings | Repos | Hand-checked | True | False | Unclear | Precision (95% Wilson) | Without vendored pandas files |
|---|---:|---:|---:|---:|---:|---:|---|---|
| high | 2146 | 627 | 120 | 119 | 1 | 0 | 99% (95% to 100%); worst case 99% | 99% (94% to 100%); worst case 99% (n=89) |
| medium | 2078 | 525 | 104 | 92 | 6 | 6 | 94% (87% to 97%); worst case 88% | 90% (80% to 95%); worst case 82% (n=68) |
| low | 1258 | 278 | 24 | 9 | 11 | 4 | 45% (26% to 66%); worst case 38% | 44% (25% to 66%); worst case 36% (n=22) |
| all | 5482 | 1206 | 248 | 220 | 18 | 10 | 92% (88% to 95%); worst case 89% | |

### Per rule (confidence levels pooled in the sample; low-confidence findings are hidden by default)

| Rule | Findings | Repos | Hand-checked | True | False | Unclear | Precision, high and medium only |
|---|---:|---:|---:|---:|---:|---:|---|
| `astype-str-na-literal` | 15 | 11 | 10 | 10 | 0 | 0 | 100% (72% to 100%); worst case 100% (n=10) |
| `chained-assignment` | 1496 | 259 | 24 | 14 | 10 | 0 | 88% (64% to 97%); worst case 88% (n=16) |
| `chained-inplace` | 354 | 105 | 16 | 14 | 2 | 0 | 88% (64% to 97%); worst case 88% (n=16) |
| `copy-keyword` | 59 | 18 | 16 | 15 | 1 | 0 | 94% (72% to 99%); worst case 94% (n=16) |
| `cow-option` | 3 | 2 | 3 | 3 | 0 | 0 | 100% (44% to 100%); worst case 100% (n=3) |
| `datetime-ns-assumption` | 107 | 78 | 24 | 15 | 1 | 8 | 91% (62% to 98%); worst case 62% (n=16) |
| `errors-ignore` | 56 | 37 | 8 | 8 | 0 | 0 | 100% (68% to 100%); worst case 100% (n=8) |
| `include-groups` | 1 | 1 | 1 | 1 | 0 | 0 | 100% (21% to 100%); worst case 100% (n=1) |
| `object-dtype-check` | 146 | 98 | 24 | 18 | 4 | 2 | 93% (70% to 99%); worst case 88% (n=16) |
| `pct-change-fill` | 48 | 14 | 16 | 16 | 0 | 0 | 100% (81% to 100%); worst case 100% (n=16) |
| `readonly-array-write` | 18 | 9 | 10 | 10 | 0 | 0 | 100% (72% to 100%); worst case 100% (n=10) |
| `removed-keyword` | 902 | 293 | 16 | 16 | 0 | 0 | 100% (81% to 100%); worst case 100% (n=16) |
| `removed-method` | 351 | 189 | 16 | 16 | 0 | 0 | 100% (81% to 100%); worst case 100% (n=16) |
| `removed-offset-alias` | 1535 | 157 | 16 | 16 | 0 | 0 | 100% (81% to 100%); worst case 100% (n=16) |
| `removed-option` | 16 | 13 | 8 | 8 | 0 | 0 | 100% (68% to 100%); worst case 100% (n=8) |
| `removed-timedelta-unit` | 40 | 31 | 8 | 8 | 0 | 0 | 100% (68% to 100%); worst case 100% (n=8) |
| `select-dtypes-object` | 254 | 184 | 16 | 16 | 0 | 0 | 100% (81% to 100%); worst case 100% (n=16) |
| `stack-legacy-args` | 81 | 40 | 16 | 16 | 0 | 0 | 100% (81% to 100%); worst case 100% (n=16) |

Precision is *true / (true + false)*; "worst case" counts every unclear item as false. The sample is stratified (at most 8 per rule and confidence level), so the "all" row is a sample rate, not an estimate for the whole population; the per-confidence rows are the headline. The per-rule-and-confidence table is in the appendix.

**Reading:** at the default (high and medium) the sample was right in 211 of 218 decided findings (97%); `high` was right in 119 of 120 and `medium` in 92 of 98 (6 more were unclear). `low` (shape only, hidden by default) was right in 9 of 20 decided: that is why it is hidden, and why `--min-confidence low` is not recommended for CI.

## False-positive classes found (18 false, 10 unclear)

| Class | Items | Status in v0.2.0 |
|---|---|---|
| Subscript of a **dict of DataFrames** (`data['a'].fillna(0, inplace=True)`, `d['a']['x'] = 1`): a dict lookup returns the DataFrame itself, nothing is copied | 20, 22, 46 | fixed when the name is only ever assigned a dict literal, `dict()` or `defaultdict()`. **Not fixed** when the dict comes from a function call or an attribute (`c.pnl[n].loc[...] = v`, `systemData = load()`): items 26, 29, 44 remain, all `medium` |
| Nested dict/list subscripts (`self.M_k[i][1] = v`, `data['a']['b'] = v`) at `low` | 18, 19, 21, 23, 24, 25 | not fixed: `low` stays hidden by default (0 of 8 true) |
| `pd.Index(t).asi8.astype(np.int64, copy=False)`: `asi8` is a NumPy array | 53 | fixed |
| `dtype == 'object'` inside a condition that already accepts the string dtype (`... or dtype == 'string'`, `is_string_dtype`) | 110, 122 | fixed |
| `.dtype == object` on a NumPy array (low) | 116, 117 | not fixed (117 disappeared because it was in a vendored pandas copy) |
| `astype('int64') // 10**9` on a column that already holds integer nanoseconds (`StartTimeUnixNano`) | 87 | not fixable without data |
| Findings inside **vendored copies of pandas itself** (`pandas/tests/...`, `pandas/core/...`; their own tests use the old APIs on purpose) | not false, but **1,984 of 5,482 findings (36%)** | fixed: a directory called `pandas` with `core/`, `_libs/` or `tests/` in it is skipped |

Of the 18 false items, 7 are no longer reported by the v0.2.0 scanner and 11 are (checked by re-scanning the same files).

*Unclear* (10): `astype('int64') // 10**9` on columns whose dtype the file does not show (8) and two `dtype == 'object'` checks on unknown receivers. That is the honest limit of the `datetime-ns-assumption` rule at `medium`: the idiom `x.astype('int64') // 10**9` is nearly always "datetime to epoch seconds", but the file has to show that the column is a datetime.

## Result, sample B (after the first fixes; high and medium only)

### Per confidence level

| Confidence | Findings | Repos | Hand-checked | True | False | Unclear | Precision (95% Wilson) | Without vendored pandas files |
|---|---:|---:|---:|---:|---:|---:|---|---|
| high | 1274 | 583 | 46 | 43 | 0 | 3 | 100% (92% to 100%); worst case 93% | 100% (92% to 100%); worst case 93% (n=45) |
| medium | 1016 | 477 | 36 | 33 | 2 | 1 | 94% (81% to 98%); worst case 92% | 94% (80% to 98%); worst case 91% (n=33) |
| low | 0 | 0 | 0 | 0 | 0 | 0 | no sample | no sample (n=0) |
| all | 2290 | 975 | 82 | 76 | 2 | 4 | 97% (91% to 99%); worst case 93% | |

Sample B found **two more false-positive classes**, both fixed afterwards (so B does not measure the final scanner either):

* `dfs[0].rename(..., inplace=True)`: a positional index on a list of frames, `medium` (now skipped when the subscript is an integer and the receiver is not known to be pandas).
* `scipy.signal.resample(x, n, axis=-1)` matched `.resample(axis=)`: a function of another library imported with `import scipy.signal` (now skipped when the receiver is the name of an imported non-pandas module).

The final scanner (v0.2.0) was re-run on the full corpus: 3,259 findings (1,274 high, 1,001 medium, 984 low) in 4,068 pandas files (the vendored copies are gone). It was **not** re-sampled after these last two fixes until sample C (below); their effect was checked on the two labelled items, by unit tests, and by four new negative oracle cases (168 cases in total, 0 disagreements between pandas 2.3.3 and 3.0.0/3.0.6).

## Sample C and the data-flow change (v0.4.0)

v0.4.0 adds one small piece of data flow: a name or `self.attr` that is only ever assigned a dict (literal, comprehension, `dict()`, a `.copy()` / `deepcopy` / alias of such a dict, or the result of a function of the same file whose every `return` is one) is a dict, so `data['a']...` on it is a dict lookup, not a column selection.

**What it removed.** The whole corpus was re-scanned (`study/run_scan.py`): 145 findings that v0.2.0/v0.3.0 reported are gone, none are new. Two were `medium` (`systemData['Agg_Players'].reset_index(inplace=True)` and a `.loc[...] =` on it, where `systemData` is returned by `data_import()` and is a dict of frames: the labelled false positive 44 of sample A); 143 were `low` `chained-assignment` (hidden by default), mostly `self.something[k][j] = ...` on attributes initialised as `{}`. I read the code behind both `medium` ones and 14 randomly chosen `low` ones: all 16 were dicts, so the removal was right. The other 129 were **not** read one by one.
What it did not remove: items 26 and 29 of sample A (`c.pnl[n].loc[...] =`, `network.buses_t[n]...`): attributes of library objects (PyPSA) that hold dicts of frames; the file does not say so.

**Sample C.** A fresh sample of `high` and `medium` findings of the v0.4.0 scanner (`study/sample.py`, seed 20261003, at most 3 per rule and level, 1 per repository, 63 items), drawn only from the 5,287 repositories that are in neither sample A nor B (238 repositories excluded). Labels in `study/labels.json`, items in `study/sample-C.json`.

| Confidence | Findings | Hand-checked | True | False | Unclear | Precision (95% Wilson) |
|---|---:|---:|---:|---:|---:|---|
| high | 852 | 35 | 35 | 0 | 0 | 100% (90% to 100%) |
| medium | 698 | 28 | 27 | 0 | 1 | 100% (88% to 100%); worst case 96% |
| all | 1,550 | 63 | 62 | 0 | 1 | 100% (94% to 100%); worst case 98% |

The one unclear item: `data['time'].astype('int64') // 10**9` where the dtype of `time` is not visible (a comment calls it a time column).

How to read this, honestly:
* **Zero false positives in 63 does not mean zero in the corpus.** The upper bound is what the interval says: for `medium`, the true rate of false positives could be around 12% and still produce this sample. Sample B had 2 in 36.
* Same labeller, who wrote the scanner, and who knew which classes had been fixed. The sample has at most 3 per rule and level, so rare rules are over-represented compared with their share of findings, and the common `medium` classes (`chained-inplace`, `removed-offset-alias` on `resample('M')`) are covered by 3 items each.
* The sample cannot show the dict change helped: it removed 2 `medium` findings out of about 1,000 (0.2%). Its effect on the headline number is therefore tiny. What the change does is remove one class of false positives that the study had found (a dict returned by a function) and a larger group of `low` ones.
* The medium precision trend over the samples (A: 92 of 98, B: 33 of 35, C: 27 of 28) is real but the three samples are different draws with different fixes in between, not a controlled before/after.

## What the numbers do not say

* **Convenience sample.** GitHub code search returns at most 1,000 results per query in its own relevance order. The targeted queries were chosen to make the rules fire, so the number of findings says nothing about how common the problems are. Only the precision of what was reported is estimated.
* **One labeller**, me, who wrote the scanner. Labels were made before the fixes and are in `study/labels.json` so anyone can disagree item by item.
* **Recall is not measured.** The study does not look for what the scanner misses (a variable that is a DataFrame the scanner could not prove, code the search did not return).
* **Precision per rule rests on at most 8 items per confidence level**; the 95% Wilson intervals are wide (8 of 8 correct has a lower bound of 68%). The per-confidence rows (98 to 120 decided items) are the ones to quote.
* `cow-option` (3 findings in the corpus) and `include-groups` (1) have too few findings for a precision statement.
* In the **broad** (ordinary pandas file) half of the corpus, only 45 of 2,684 pandas files (1.7%) had any finding at the default confidence. This is a side observation, not a precision number: those 45 were not separately labelled.
* "True" findings in old code are true about pandas 3 only: the scanner does not know which pandas version a project pins.

## Reproduce

```
python study/collect.py files.json            # needs `gh` logged in; about 45 minutes with the built-in pauses
python study/download.py files.json files --max-per-repo 3
python study/run_scan.py files scan.json
python study/sample.py scan.json files sample.md --seed 20261004 --cap 8 --per-repo 2
python study/tabulate.py scan.json study/sample-A.json A
# sample C: scan with v0.4.0, keep high+medium findings of repositories not in A or B, then
python study/sample.py scanC.json files sampleC.md --seed 20261003 --cap 3 --per-repo 1
python study/tabulate.py scanC.json study/sample-C.json C
```

`study/corpus.tsv` lists the 6,000 sampled files with the commit each was fetched at.

## Appendix: per rule and confidence (sample A)

### Per rule and confidence

| Rule | Confidence | Findings | Hand-checked | False | Unclear | Precision |
|---|---|---:|---:|---:|---:|---|
| `astype-str-na-literal` | high | 2 | 2 | 0 | 0 | 100% (34% to 100%); worst case 100% |
| `astype-str-na-literal` | medium | 13 | 8 | 0 | 0 | 100% (68% to 100%); worst case 100% |
| `chained-assignment` | high | 182 | 8 | 0 | 0 | 100% (68% to 100%); worst case 100% |
| `chained-assignment` | low | 1174 | 8 | 8 | 0 | 0% (0% to 32%); worst case 0% |
| `chained-assignment` | medium | 140 | 8 | 2 | 0 | 75% (41% to 93%); worst case 75% |
| `chained-inplace` | high | 197 | 8 | 0 | 0 | 100% (68% to 100%); worst case 100% |
| `chained-inplace` | medium | 157 | 8 | 2 | 0 | 75% (41% to 93%); worst case 75% |
| `copy-keyword` | high | 15 | 8 | 1 | 0 | 88% (53% to 98%); worst case 88% |
| `copy-keyword` | medium | 44 | 8 | 0 | 0 | 100% (68% to 100%); worst case 100% |
| `cow-option` | high | 3 | 3 | 0 | 0 | 100% (44% to 100%); worst case 100% |
| `datetime-ns-assumption` | high | 47 | 8 | 0 | 0 | 100% (68% to 100%); worst case 100% |
| `datetime-ns-assumption` | low | 24 | 8 | 0 | 3 | 100% (57% to 100%); worst case 62% |
| `datetime-ns-assumption` | medium | 36 | 8 | 1 | 5 | 67% (21% to 94%); worst case 25% |
| `errors-ignore` | high | 56 | 8 | 0 | 0 | 100% (68% to 100%); worst case 100% |
| `include-groups` | high | 1 | 1 | 0 | 0 | 100% (21% to 100%); worst case 100% |
| `object-dtype-check` | high | 37 | 8 | 0 | 0 | 100% (68% to 100%); worst case 100% |
| `object-dtype-check` | low | 60 | 8 | 3 | 1 | 57% (25% to 84%); worst case 50% |
| `object-dtype-check` | medium | 49 | 8 | 1 | 1 | 86% (49% to 97%); worst case 75% |
| `pct-change-fill` | high | 21 | 8 | 0 | 0 | 100% (68% to 100%); worst case 100% |
| `pct-change-fill` | medium | 27 | 8 | 0 | 0 | 100% (68% to 100%); worst case 100% |
| `readonly-array-write` | high | 2 | 2 | 0 | 0 | 100% (34% to 100%); worst case 100% |
| `readonly-array-write` | medium | 16 | 8 | 0 | 0 | 100% (68% to 100%); worst case 100% |
| `removed-keyword` | high | 487 | 8 | 0 | 0 | 100% (68% to 100%); worst case 100% |
| `removed-keyword` | medium | 415 | 8 | 0 | 0 | 100% (68% to 100%); worst case 100% |
| `removed-method` | high | 214 | 8 | 0 | 0 | 100% (68% to 100%); worst case 100% |
| `removed-method` | medium | 137 | 8 | 0 | 0 | 100% (68% to 100%); worst case 100% |
| `removed-offset-alias` | high | 715 | 8 | 0 | 0 | 100% (68% to 100%); worst case 100% |
| `removed-offset-alias` | medium | 820 | 8 | 0 | 0 | 100% (68% to 100%); worst case 100% |
| `removed-option` | high | 16 | 8 | 0 | 0 | 100% (68% to 100%); worst case 100% |
| `removed-timedelta-unit` | high | 40 | 8 | 0 | 0 | 100% (68% to 100%); worst case 100% |
| `select-dtypes-object` | high | 89 | 8 | 0 | 0 | 100% (68% to 100%); worst case 100% |
| `select-dtypes-object` | medium | 165 | 8 | 0 | 0 | 100% (68% to 100%); worst case 100% |
| `stack-legacy-args` | high | 22 | 8 | 0 | 0 | 100% (68% to 100%); worst case 100% |
| `stack-legacy-args` | medium | 59 | 8 | 0 | 0 | 100% (68% to 100%); worst case 100% |
