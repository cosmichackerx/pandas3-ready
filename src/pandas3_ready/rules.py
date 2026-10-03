"""Rule registry. Every rule is tied to behaviour that tests/oracle/run_oracle.py observed on real pandas.

OLD and NEW are the pandas versions the oracle ran on; a rule is only claimed for those. `oracle` is False for a rule whose
behaviour is taken from the pandas documentation and not (yet) run.
"""
from __future__ import annotations

from dataclasses import dataclass

REPO = "https://github.com/cosmichackerx/pandas3-ready"
OLD = "2.3.3"
NEW = ["3.0.0", "3.0.6"]
GUIDE = "https://pandas.pydata.org/docs/user_guide/migration.html"


@dataclass(frozen=True)
class Rule:
    id: str
    severity: str
    summary: str
    fix: str
    oracle: bool = True
    url: str = REPO + "#rules"


RULES = {r.id: r for r in [
    Rule("chained-inplace", "warning", "df[col].method(..., inplace=True): the method runs on a temporary copy, so pandas 3 silently leaves the DataFrame unchanged", "Assign the result: df[col] = df[col].fillna(0), or pass a dict: df.fillna({col: 0}, inplace=True)."),
    Rule("chained-assignment", "warning", "df[a][b] = v or df[a].loc[b] = v: the first indexing step is a copy, so pandas 3 silently does not write to the DataFrame", "Index once: df.loc[b, a] = v (or df.iloc[i, j] = v)."),
    Rule("readonly-array-write", "error", "df[col].values[i] = v / df.to_numpy()[i] = v: the array is read-only in pandas 3 (ValueError), or a copy when dtypes are mixed", "Write through pandas: df.loc[...] = v, or copy first: arr = df.to_numpy(copy=True)."),
    Rule("removed-offset-alias", "error", "A frequency alias that pandas 3 removed (H, T, L, U, N, S, M, Q, Y, A, BM, BQ, BA, SM, AS, ...): ValueError", "Use the new alias: h, min, ms, us, ns, s, ME, QE, YE, BME, BQE, BYE, SME, YS."),
    Rule("removed-timedelta-unit", "error", "A Timedelta unit that pandas 3 removed (T, L, U, N) or deprecated (H)", "Use min, ms, us, ns, h."),
    Rule("removed-method", "error", "A method or function that pandas 3 removed (applymap, swapaxes, Series.bool/view/ravel, first/last, pd.value_counts, ...)", "Use the replacement named in the message."),
    Rule("removed-keyword", "error", "A keyword argument that pandas 3 removed (fillna(method=), read_csv(delim_whitespace=), groupby(axis=), resample(kind=), ...)", "Use the replacement named in the message."),
    Rule("errors-ignore", "error", "errors=\"ignore\" in to_datetime / to_numeric / to_timedelta: removed in pandas 3", "Catch the exception, or use errors=\"coerce\" and check for NaT/NaN."),
    Rule("raw-string-reader", "error", "read_json / read_html / read_xml with a literal JSON, HTML or XML string: pandas 3 reads it as a file path", "Wrap it: pd.read_json(io.StringIO(text))."),
    Rule("removed-option", "error", "pd.set_option(\"mode.use_inf_as_na\", ...): the option no longer exists", "Replace inf with NaN before: df.replace([np.inf, -np.inf], np.nan)."),
    Rule("cow-option", "note", "mode.copy_on_write is set: Copy-on-Write is always on in pandas 3 and the option does nothing (it warns)", "Remove the line."),
    Rule("include-groups", "error", "groupby(...).apply(..., include_groups=True): pandas 3 raises ValueError", "Drop the argument (the group columns are not passed to the function) and select them explicitly if needed."),
    Rule("stack-legacy-args", "error", "DataFrame.stack(dropna=..., sort=...): pandas 3 raises ValueError (future_stack=False is deprecated)", "Remove dropna/sort; call .dropna() or .sort_index() afterwards."),
    Rule("pct-change-fill", "error", "pct_change(fill_method='pad'/..., limit=...): removed in pandas 3 (fill_method must be None)", "Fill first (df.ffill()), then call pct_change()."),
    Rule("object-dtype-check", "warning", "dtype == object / is_object_dtype(...): False for text columns in pandas 3, which use the str dtype", "Use pd.api.types.is_string_dtype(...) or check both: dtype == object or pd.api.types.is_string_dtype(dtype)."),
    Rule("select-dtypes-object", "note", "select_dtypes(include=object): pandas 3 still selects text columns but warns that it will stop", "Use include=['object', 'string'] (the same on pandas 2.3.3 and 3.x)."),
    Rule("astype-str-na-literal", "warning", "x.astype(str) compared with or replacing the text 'nan'/'None': pandas 3 keeps missing values missing instead of turning them into those strings", "Test x.isna() before the cast."),
    Rule("datetime-ns-assumption", "warning", "datetime values cast to int64 and divided by 1e9: pandas 3 may store seconds, ms or us instead of ns, so the result is off by 1000 or more", "Divide a Timedelta instead: (ts - pd.Timestamp('1970-01-01')) // pd.Timedelta('1s')."),
    Rule("copy-keyword", "note", "copy=... on astype/reindex/rename/merge/concat: deprecated in pandas 3, it has no effect (Copy-on-Write)", "Remove the argument; call .copy() if you need a copy."),
]}

CONFIDENCE = ["low", "medium", "high"]
