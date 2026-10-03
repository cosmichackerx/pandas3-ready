"""Cases for the --fix oracle. Each case is a program that prints its result.

For a `fix` case the oracle checks: running --fix on `code` gives a program that (1) prints on pandas 2.3.3 exactly what `code` printed on 2.3.3, (2) prints the
same on pandas 3.x, (3) raises no pandas deprecation warning on either, (4) is not changed by a second --fix run, (5) no longer triggers the rule.
For a `refuse` case --fix must leave the program byte-for-byte unchanged (the rewrite would change meaning, or the receiver is not provably safe).
"""
import re
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))
from pandas3_ready.analyze import NEW_ALIAS  # noqa: E402

PRE = "df = pd.DataFrame({'a': [1.0, None, None, 4.0], 'b': [None, 2.0, None, None]})\n"
FIX_CASES = []


def fix(id, rule, code):
    FIX_CASES.append(dict(id=id, rule=rule, code=code, kind="fix"))


def refuse(id, rule, code):
    FIX_CASES.append(dict(id=id, rule=rule, code=code, kind="refuse"))


# ---- fillna(method=) -> ffill / bfill
for m, new in (("ffill", "ffill"), ("pad", "ffill"), ("bfill", "bfill"), ("backfill", "bfill")):
    fix(f"fm-{m}", "removed-keyword", PRE + f"print(df.fillna(method='{m}').to_string())")
fix("fm-limit", "removed-keyword", PRE + "print(df.fillna(method='ffill', limit=1).to_string())")
fix("fm-limit-first", "removed-keyword", PRE + "print(df.fillna(limit=1, method='bfill').to_string())")
fix("fm-axis", "removed-keyword", PRE + "print(df.fillna(method='ffill', axis=1).to_string())")
fix("fm-series", "removed-keyword", PRE + "print(df['a'].fillna(method='ffill').tolist())")
fix("fm-inplace", "removed-keyword", PRE + "df.fillna(method='ffill', inplace=True)\nprint(df.to_string())")
fix("fm-multiline", "removed-keyword", PRE + "print(df.fillna(\n    method='ffill',\n    limit=1,\n).to_string())")
fix("fm-trailing-comma", "removed-keyword", PRE + "print(df.fillna(method='ffill',).to_string())")
fix("fm-double-quotes-chain", "removed-keyword", PRE + 'print(df.fillna(method="ffill").fillna(method="bfill").to_string())')
refuse("fm-value", "removed-keyword", PRE + "print(df.fillna(0, method='ffill').to_string())")
refuse("fm-downcast", "removed-keyword", PRE + "print(df.fillna(method='ffill', downcast='infer').to_string())")
refuse("fm-variable", "removed-keyword", PRE + "m = 'ffill'\nprint(df.fillna(method=m).to_string())")
refuse("fm-comment", "removed-keyword", PRE + "print(df.fillna(\n    method='ffill',  # carry forward\n    limit=1,\n).to_string())")

# ---- applymap -> map
fix("am-basic", "removed-method", PRE + "print(df.applymap(lambda x: x * 2).to_string())")
fix("am-na-action", "removed-method", PRE + "print(df.applymap(lambda x: x * 2, na_action='ignore').to_string())")
fix("am-chain", "removed-method", PRE + "print(df.fillna(0).applymap(str).to_string())")

# ---- frequency aliases (every alias the scanner knows, on pd.date_range and on resample)
TSDF = "ts = pd.Series(range(100), index=pd.date_range('2024-01-01', periods=100, freq='min'))\n"
for old in sorted(NEW_ALIAS):
    suffix = {"Q": "-DEC", "A": "-JAN", "Y": "-JAN", "BQ": "-DEC", "BA": "-JAN", "BY": "-JAN", "AS": "-JAN", "BAS": "-JAN"}.get(old, "")
    fix(f"al-range-{old}", "removed-offset-alias", f"print(pd.date_range('2024-01-31', periods=4, freq='{old}{suffix}').strftime('%Y-%m-%d %H:%M:%S.%f').tolist())")
fix("al-multiple-2H", "removed-offset-alias", "print(pd.date_range('2024-01-01', periods=3, freq='2H').tolist())")
fix("al-30T", "removed-offset-alias", "print(pd.date_range('2024-01-01', periods=3, freq='30T').tolist())")
fix("al-resample-H", "removed-offset-alias", TSDF + "print(ts.resample('H').sum().tolist())")
fix("al-resample-T", "removed-offset-alias", TSDF + "print(ts.resample('15T').sum().tolist())")
fix("al-resample-S", "removed-offset-alias", TSDF + "print(ts.resample('30S').sum().head(4).tolist())")
fix("al-asfreq-H", "removed-offset-alias", TSDF + "print(ts.asfreq('30T').head(3).tolist())")
fix("al-grouper", "removed-offset-alias", TSDF + "print(ts.groupby(pd.Grouper(freq='H')).sum().tolist())")
fix("al-floor", "removed-offset-alias", "print(pd.Timestamp('2024-01-01 10:47').floor('H'))")
fix("al-kw-rule", "removed-offset-alias", TSDF + "print(ts.resample(rule='H').sum().tolist())")
fix("al-period-range", "removed-offset-alias", "print(list(pd.period_range('2024-01-01', periods=3, freq='H').astype(str)))")
refuse("al-resample-M", "removed-offset-alias", TSDF + "print(ts.resample('M').sum().tolist())")
refuse("al-resample-A", "removed-offset-alias", TSDF + "print(ts.resample('A').sum().tolist())")
refuse("al-variable", "removed-offset-alias", "f = 'H'\nprint(pd.date_range('2024-01-01', periods=3, freq=f).tolist())")

# ---- timedelta units
for u in ("T", "L", "U", "N", "H"):
    fix(f"td-unit-{u}", "removed-timedelta-unit", f"print(pd.to_timedelta(5, unit='{u}'))\nprint(pd.Timedelta(3, unit='{u}'))")
refuse("td-unit-variable", "removed-timedelta-unit", "u = 'T'\nprint(pd.Timedelta(3, unit=u))")

# ---- read_csv / to_datetime keywords
CSV = "import io\ntxt = 'a b\\n1 2\\n3 4\\n'\n"
fix("rc-delim", "removed-keyword", CSV + "print(pd.read_csv(io.StringIO(txt), delim_whitespace=True).to_string())")
fix("rc-delim-more", "removed-keyword", CSV + "print(pd.read_csv(io.StringIO(txt), delim_whitespace=True, header=0, index_col=0).to_string())")
fix("rt-delim", "removed-keyword", CSV + "print(pd.read_table(io.StringIO(txt), delim_whitespace=True).to_string())")
fix("rc-idf", "removed-keyword", "import io\nprint(pd.read_csv(io.StringIO('d,v\\n2024-01-05,1\\n2024-02-06,2\\n'), parse_dates=['d'], infer_datetime_format=True)['d'].dt.strftime('%Y-%m-%d').tolist())")
fix("td-idf", "removed-keyword", "print(pd.to_datetime(pd.Series(['2024-01-05', '2024-02-06']), infer_datetime_format=True).tolist())")
fix("rc-delim-and-idf", "removed-keyword", CSV + "print(pd.read_csv(io.StringIO(txt), delim_whitespace=True, infer_datetime_format=True).to_string())")
refuse("rc-delim-with-sep", "removed-keyword", CSV + "print(pd.read_csv(io.StringIO(txt), sep=' ', delim_whitespace=True).to_string())")
refuse("rc-delim-variable", "removed-keyword", CSV + "w = True\nprint(pd.read_csv(io.StringIO(txt), delim_whitespace=w).to_string())")

# ---- copy=
S = "a = pd.DataFrame({'k': [1, 2], 'x': [3, 4]})\nb = pd.DataFrame({'k': [1, 2], 'y': [5, 6]})\n"
fix("cp-concat-false", "copy-keyword", S + "print(pd.concat([a, b], axis=1, copy=False).to_string())")
fix("cp-concat-true", "copy-keyword", S + "print(pd.concat([a, b], copy=True).to_string())")
fix("cp-concat-first", "copy-keyword", S + "print(pd.concat([a, b], copy=False, axis=1).to_string())")
fix("cp-merge", "copy-keyword", S + "print(pd.merge(a, b, on='k', copy=False).to_string())")
fix("cp-reindex", "copy-keyword", S + "print(a.reindex([1, 0], copy=False).to_string())")
fix("cp-rename", "copy-keyword", S + "print(a.rename(columns={'x': 'z'}, copy=False).to_string())")
fix("cp-astype", "copy-keyword", S + "print(a.astype('float64', copy=False).to_string())")
refuse("cp-variable", "copy-keyword", S + "c = False\nprint(pd.concat([a, b], copy=c).to_string())")
refuse("cp-numpy-astype", "copy-keyword", "import numpy as np\nprint(np.array([1]).astype('int64', copy=False).tolist())")
