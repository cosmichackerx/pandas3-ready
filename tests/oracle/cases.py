"""The oracle cases. Each case is a small pandas program that prints its result.

expect: how the program behaves on pandas 3 compared with 2.3.3
  error3  runs on 2.3.3 (maybe with a warning), raises on 3.x
  diff    runs on both, different output (the silent changes)
  warn3   runs on both, same output, 3.x emits a pandas deprecation warning that 2.3.3 does not
  same    same output, no new warning on 3.x (negatives: code the scanner must NOT flag, or flags only as a documented false positive)
fires: the scanner must report `rule` on this code at the default confidence (True), must report nothing (False),
       or may report it although the code is fine ("fp": a documented false-positive class; the case then proves behaviour is identical).
fixed: the replacement the message recommends; it must give the same output on 2.3.3 and 3.x.
"""
PRE = "df = pd.DataFrame({'a': [1.0, None, 3.0], 'b': [1, 2, 3]})\n"
TS = "idx = pd.to_datetime(['2024-01-01 10:00', '2024-01-01 11:30'])\n"
CASES = []


def case(id, rule, code, expect, fixed=None, fires=True, note="", needs=None):
    CASES.append(dict(id=id, rule=rule, code=code, expect=expect, fixed=fixed, fires=fires, note=note, needs=needs))


# ---- chained-inplace
case("ci-fillna", "chained-inplace", PRE + "df['a'].fillna(0, inplace=True)\nprint(df['a'].tolist())", "diff", PRE + "df['a'] = df['a'].fillna(0)\nprint(df['a'].tolist())")
case("ci-replace", "chained-inplace", PRE + "df['b'].replace(1, 9, inplace=True)\nprint(df['b'].tolist())", "diff", PRE + "df['b'] = df['b'].replace(1, 9)\nprint(df['b'].tolist())")
case("ci-attr", "chained-inplace", PRE + "df.a.fillna(0, inplace=True)\nprint(df['a'].tolist())", "diff", PRE + "df['a'] = df['a'].fillna(0)\nprint(df['a'].tolist())")
case("ci-loc", "chained-inplace", PRE + "df.loc[:, 'a'].fillna(0, inplace=True)\nprint(df['a'].tolist())", "diff", PRE + "df.fillna({'a': 0}, inplace=True)\nprint(df['a'].tolist())")
case("ci-dropna-unknown", "chained-inplace", "def f(data):\n    data['a'].fillna(0, inplace=True)\n    return data\nprint(f(pd.DataFrame({'a': [None, 1.0]}))['a'].tolist())", "diff", note="receiver is a parameter: medium confidence")
case("ci-neg-assign", None, PRE + "df['a'] = df['a'].fillna(0)\nprint(df['a'].tolist())", "same", fires=False)
case("ci-neg-dict", None, PRE + "df.fillna({'a': 0}, inplace=True)\nprint(df['a'].tolist())", "same", fires=False)
case("ci-neg-series", None, PRE + "s = df['a'].copy()\ns.fillna(0, inplace=True)\nprint(s.tolist())", "same", fires=False)
case("ci-neg-whole", None, PRE + "df.dropna(inplace=True)\nprint(len(df))", "same", fires=False)

# ---- chained-assignment
case("ca-colrow", "chained-assignment", PRE + "df['b'][0] = 99\nprint(df['b'].tolist())", "diff", PRE + "df.loc[0, 'b'] = 99\nprint(df['b'].tolist())")
case("ca-attr", "chained-assignment", PRE + "df.b[0] = 99\nprint(df['b'].tolist())", "diff", PRE + "df.loc[0, 'b'] = 99\nprint(df['b'].tolist())")
case("ca-col-iloc", "chained-assignment", PRE + "df['b'].iloc[0] = 99\nprint(df['b'].tolist())", "diff", PRE + "df.iloc[0, 1] = 99\nprint(df['b'].tolist())")
case("ca-col-loc", "chained-assignment", PRE + "df['b'].loc[0] = 99\nprint(df['b'].tolist())", "diff", PRE + "df.loc[0, 'b'] = 99\nprint(df['b'].tolist())")
case("ca-mask-col", "chained-assignment", PRE + "df['b'][df['b'] > 1] = 0\nprint(df['b'].tolist())", "diff", PRE + "df.loc[df['b'] > 1, 'b'] = 0\nprint(df['b'].tolist())")
case("ca-aug", "chained-assignment", PRE + "df['b'][0] += 10\nprint(df['b'].tolist())", "diff", PRE + "df.loc[0, 'b'] += 10\nprint(df['b'].tolist())")
case("ca-never-worked", "chained-assignment", PRE + "df[df['b'] > 1]['b'] = 0\nprint(df['b'].tolist())", "warn3", PRE + "df.loc[df['b'] > 1, 'b'] = 0\nprint(df['b'].tolist())",
     note="never wrote to df in either version (3.x now warns): the rule is right to flag it, but it is not a silent 2.3 -> 3.0 change")
case("ca-neg-loc", None, PRE + "df.loc[0, 'b'] = 99\nprint(df['b'].tolist())", "same", fires=False)
case("ca-neg-iloc", None, PRE + "df.iloc[0, 1] = 99\nprint(df['b'].tolist())", "same", fires=False)
case("ca-neg-dict", None, "d = {'a': {}}\nd['a']['b'] = 1\nprint(d)", "same", fires=False, note="nested dict: low confidence, hidden by default")
case("ca-neg-numpy", None, "import numpy as np\nm = np.zeros((2, 2))\nm[0][1] = 5\nprint(m.tolist())", "same", fires=False)

# ---- readonly-array-write
case("ro-col-values", "readonly-array-write", PRE + "df['b'].values[0] = 99\nprint(df['b'].tolist())", "error3", PRE + "df.loc[0, 'b'] = 99\nprint(df['b'].tolist())")
case("ro-to-numpy", "readonly-array-write", "df = pd.DataFrame({'a': [1, 2]})\ndf.to_numpy()[0, 0] = 9\nprint(df['a'].tolist())", "error3", "df = pd.DataFrame({'a': [1, 2]})\ndf.loc[0, 'a'] = 9\nprint(df['a'].tolist())")
case("ro-df-values", "readonly-array-write", "df = pd.DataFrame({'a': [1, 2]})\ndf.values[0, 0] = 9\nprint(df['a'].tolist())", "error3", "df = pd.DataFrame({'a': [1, 2]})\ndf.iloc[0, 0] = 9\nprint(df['a'].tolist())")
case("ro-neg-copy", None, "df = pd.DataFrame({'a': [1, 2]})\narr = df.to_numpy(copy=True)\narr[0, 0] = 9\nprint(arr.tolist())", "same", fires=False)
case("ro-neg-numpy", None, "import numpy as np\na = np.zeros(3)\na[0] = 1\nprint(a.tolist())", "same", fires=False)

# ---- removed-offset-alias: every alias pandas 3 removed, in date_range
ALIASES = [("H", "h"), ("T", "min"), ("L", "ms"), ("U", "us"), ("N", "ns"), ("S", "s"), ("M", "ME"), ("Q", "QE"), ("Y", "YE"), ("A", "YE"), ("BM", "BME"),
           ("BQ", "BQE"), ("BA", "BYE"), ("SM", "SME"), ("CBM", "CBME"), ("AS", "YS"), ("BAS", "BYS"), ("2H", "2h"), ("15T", "15min"), ("Q-DEC", "QE-DEC"),
           ("A-DEC", "YE-DEC"), ("Y-JAN", "YE-JAN"), ("AS-JAN", "YS-JAN"), ("BQ-MAR", "BQE-MAR"), ("BA-DEC", "BYE-DEC")]
DR = "r = pd.date_range('2024-01-01', periods=3, freq='%s')\nprint(r.strftime('%%Y-%%m-%%d %%H:%%M:%%S.%%f').tolist())"
for old, new in ALIASES:
    case(f"alias-{old}", "removed-offset-alias", DR % old, "error3", DR % new)
for ok in ["D", "B", "W", "W-MON", "MS", "ME", "QS", "QE", "QE-DEC", "YS", "YE", "YE-DEC", "h", "min", "s", "ms", "us", "ns", "BME", "SME", "bh"]:
    case(f"alias-ok-{ok}", None, DR % ok, "same", fires=False)
RS = "s = pd.Series([1, 2, 3], index=pd.to_datetime(['2024-01-31', '2024-02-15', '2024-02-29']))\nprint(s.resample('%s').sum().to_string())"
case("resample-M", "removed-offset-alias", RS % "M", "error3", RS % "ME")
case("resample-Q", "removed-offset-alias", RS % "Q", "error3", RS % "QE")
case("resample-ok", None, RS % "ME", "same", fires=False)
case("asfreq-M", "removed-offset-alias", "s = pd.Series([1, 2], index=pd.to_datetime(['2024-01-31', '2024-02-29']))\nprint(s.asfreq('M').to_string())", "error3",
     "s = pd.Series([1, 2], index=pd.to_datetime(['2024-01-31', '2024-02-29']))\nprint(s.asfreq('ME').to_string())")
case("grouper-M", "removed-offset-alias", "d = pd.DataFrame({'t': pd.to_datetime(['2024-01-01', '2024-02-01']), 'v': [1, 2]})\nprint(d.groupby(pd.Grouper(key='t', freq='M')).sum().to_string())", "error3",
     "d = pd.DataFrame({'t': pd.to_datetime(['2024-01-01', '2024-02-01']), 'v': [1, 2]})\nprint(d.groupby(pd.Grouper(key='t', freq='ME')).sum().to_string())")
case("floor-H", "removed-offset-alias", TS + "print(idx.floor('H').tolist())", "error3", TS + "print(idx.floor('h').tolist())")
case("round-T", "removed-offset-alias", TS + "print(idx.round('15T').tolist())", "error3", TS + "print(idx.round('15min').tolist())")
case("period-range-H", "removed-offset-alias", "print(pd.period_range('2024-01-01', periods=2, freq='H').astype(str).tolist())", "error3", "print(pd.period_range('2024-01-01', periods=2, freq='h').astype(str).tolist())")
case("period-range-A", "removed-offset-alias", "print(pd.period_range('2024', periods=2, freq='A').astype(str).tolist())", "error3", "print(pd.period_range('2024', periods=2, freq='Y').astype(str).tolist())")
case("period-range-M-ok", None, "print(pd.period_range('2024-01', periods=2, freq='M').astype(str).tolist())", "same", fires=False, note="'M', 'Q', 'Y' are still valid period frequencies")
case("to_period-M-ok", None, TS + "print(idx.to_period('M').astype(str).tolist())", "same", fires=False)
case("period-M-ok", None, "print(str(pd.Period('2024-01', 'M')))", "same", fires=False)
case("resample-period-M-fp", "removed-offset-alias", "s = pd.Series([1, 2], index=pd.period_range('2024-01', periods=2, freq='M'))\nprint(s.resample('M').sum().to_string())", "same", fires="fp",
     note="documented false positive class: resample('M') on a PeriodIndex is valid; reported at medium confidence only")

# ---- removed-timedelta-unit
for u, new in [("T", "min"), ("L", "ms"), ("U", "us"), ("N", "ns")]:
    case(f"td-unit-{u}", "removed-timedelta-unit", f"print(pd.Timedelta(5, unit='{u}'))", "error3", f"print(pd.Timedelta(5, unit='{new}'))")
case("td-unit-H", "removed-timedelta-unit", "print(pd.Timedelta(5, unit='H'))", "warn3", "print(pd.Timedelta(5, unit='h'))")
case("to_td-unit-T", "removed-timedelta-unit", "print(pd.to_timedelta([5], unit='T').tolist())", "error3", "print(pd.to_timedelta([5], unit='min').tolist())")
case("td-ok", None, "print(pd.Timedelta(5, unit='min'), pd.Timedelta(5, unit='s'))", "same", fires=False)

# ---- removed-method
case("rm-applymap", "removed-method", PRE + "print(df.applymap(lambda x: x * 2).values.tolist())", "error3", PRE + "print(df.map(lambda x: x * 2).values.tolist())")
case("rm-swapaxes", "removed-method", PRE + "print(df.swapaxes(0, 1).shape)", "error3", PRE + "print(df.T.shape)")
case("rm-bool", "removed-method", "s = pd.Series([True])\nprint(s.bool())", "error3", "s = pd.Series([True])\nprint(bool(s.iloc[0]))")
case("rm-view", "removed-method", "s = pd.Series([1, 2])\nprint(s.view('int64').tolist())", "error3", "s = pd.Series([1, 2])\nprint(s.to_numpy().view('int64').tolist())")
case("rm-ravel", "removed-method", "s = pd.Series([1, 2])\nprint(s.ravel().tolist())", "error3", "s = pd.Series([1, 2])\nprint(s.to_numpy().ravel().tolist())")
case("rm-index-format", "removed-method", "i = pd.Index([1, 2])\nprint(i.format())", "error3", "i = pd.Index([1, 2])\nprint(i.astype(str).tolist())")
case("rm-first", "removed-method", "d = pd.DataFrame({'a': [1, 2, 3]}, index=pd.date_range('2024-01-01', periods=3))\nprint(d.first('2D').shape)", "error3",
     "d = pd.DataFrame({'a': [1, 2, 3]}, index=pd.date_range('2024-01-01', periods=3))\nprint(d.loc[:d.index[0] + pd.Timedelta('1D')].shape)")
case("rm-value_counts", "removed-method", "print(pd.value_counts(pd.Series([1, 1, 2])).tolist())", "error3", "print(pd.Series([1, 1, 2]).value_counts().tolist())")
case("rm-is_interval", "removed-method", "print(pd.api.types.is_interval(1))", "error3", "print(isinstance(1, pd.Interval))")
case("rm-sql-execute", "removed-method", "import sqlite3\nc = sqlite3.connect(':memory:')\nprint(pd.io.sql.execute('select 1', c).fetchall())", "error3",
     "import sqlite3\nc = sqlite3.connect(':memory:')\nprint(c.execute('select 1').fetchall())")
case("rm-neg-map", None, PRE + "print(df.map(lambda x: x * 2).values.tolist())", "same", fires=False)
case("rm-neg-first-groupby", None, "d = pd.DataFrame({'g': [1, 1], 'v': [3, 4]})\nprint(d.groupby('g').first().values.tolist())", "same", fires=False)
case("rm-neg-first-n", None, "d = pd.DataFrame({'v': [3, 4]})\nprint(d.head(1).values.tolist())", "same", fires=False)

# ---- removed-keyword
CSV = "import io\ntxt = io.StringIO('a b\\n1 2')\n"
case("rk-fillna-method", "removed-keyword", "print(pd.Series([1, None]).fillna(method='ffill').tolist())", "error3", "print(pd.Series([1, None]).ffill().tolist())")
case("rk-replace-method", "removed-keyword", "print(pd.Series([1, 2, 2]).replace(2, method='ffill').tolist())", "error3", "print(pd.Series([1, 2, 2]).where(pd.Series([1, 2, 2]) != 2).ffill().tolist())")
case("rk-groupby-axis", "removed-keyword", "print(pd.DataFrame({'a': [1, 1]}).groupby(level=0, axis=0).sum().shape)", "error3", "print(pd.DataFrame({'a': [1, 1]}).groupby(level=0).sum().shape)")
case("rk-rolling-axis", "removed-keyword", "print(pd.DataFrame({'a': [1, 2]}).rolling(1, axis=0).sum().shape)", "error3", "print(pd.DataFrame({'a': [1, 2]}).rolling(1).sum().shape)")
case("rk-resample-kind", "removed-keyword", "s = pd.Series([1], index=pd.to_datetime(['2024-01-01']))\nprint(s.resample('D', kind='timestamp').sum().shape)", "error3",
     "s = pd.Series([1], index=pd.to_datetime(['2024-01-01']))\nprint(s.resample('D').sum().shape)")
case("rk-apply-convert", "removed-keyword", "print(pd.Series([1]).apply(lambda x: x, convert_dtype=False).tolist())", "error3", "print(pd.Series([1]).apply(lambda x: x).tolist())")
case("rk-align-method", "removed-keyword", "a, b = pd.Series([1]).align(pd.Series([1]), method='ffill')\nprint(a.tolist())", "error3", "a, b = pd.Series([1]).align(pd.Series([1]))\nprint(a.tolist())")
case("rk-csv-delim_whitespace", "removed-keyword", CSV + "print(pd.read_csv(txt, delim_whitespace=True).shape)", "error3", CSV + "print(pd.read_csv(txt, sep=r'\\s+').shape)")
case("rk-csv-date_parser", "removed-keyword", CSV + "print(pd.read_csv(txt, sep=' ', date_parser=lambda x: x).shape)", "error3", CSV + "print(pd.read_csv(txt, sep=' ').shape)")
case("rk-csv-keep_date_col", "removed-keyword", CSV + "print(pd.read_csv(txt, sep=' ', keep_date_col=True).shape)", "error3", CSV + "print(pd.read_csv(txt, sep=' ').shape)")
case("rk-csv-verbose", "removed-keyword", CSV + "print(pd.read_csv(txt, sep=' ', verbose=False).shape)", "error3", CSV + "print(pd.read_csv(txt, sep=' ').shape)")
case("rk-csv-infer", "removed-keyword", CSV + "print(pd.read_csv(txt, sep=' ', infer_datetime_format=True).shape)", "error3", CSV + "print(pd.read_csv(txt, sep=' ').shape)")
case("rk-table-delim", "removed-keyword", CSV + "print(pd.read_table(txt, delim_whitespace=True).shape)", "error3", CSV + "print(pd.read_table(txt, sep=r'\\s+').shape)")
case("rk-to_datetime-infer", "removed-keyword", "print(pd.to_datetime(['2024-01-01'], infer_datetime_format=True).tolist())", "error3", "print(pd.to_datetime(['2024-01-01']).tolist())")
case("rk-neg-sep", None, CSV + "print(pd.read_csv(txt, sep=r'\\s+').shape)", "same", fires=False)
case("rk-neg-str-replace", None, "print('a-b'.replace('-', '_'))", "same", fires=False)

# ---- errors-ignore
case("ei-to_datetime", "errors-ignore", "print(pd.to_datetime(['x'], errors='ignore').tolist())", "error3", "print(pd.to_datetime(['x'], errors='coerce').isna().tolist())")
case("ei-to_numeric", "errors-ignore", "print(pd.to_numeric(['x'], errors='ignore').tolist())", "error3", "print(pd.to_numeric(['x'], errors='coerce').tolist())")
case("ei-to_timedelta", "errors-ignore", "print(pd.to_timedelta(['x'], errors='ignore').tolist())", "error3", "print(pd.to_timedelta(['x'], errors='coerce').tolist())")
case("ei-apply", "errors-ignore", "d = pd.DataFrame({'a': ['1', 'x']})\nprint(d.apply(pd.to_numeric, errors='ignore')['a'].tolist())", "error3", "d = pd.DataFrame({'a': ['1', 'x']})\nprint(d.apply(pd.to_numeric, errors='coerce')['a'].tolist())")
case("ei-neg-coerce", None, "print(pd.to_numeric(['x'], errors='coerce').tolist())", "same", fires=False)

# ---- raw-string-reader
case("rs-json", "raw-string-reader", "print(pd.read_json('{\"a\": [1]}').shape)", "error3", "import io\nprint(pd.read_json(io.StringIO('{\"a\": [1]}')).shape)")
case("rs-html", "raw-string-reader", "print(len(pd.read_html('<table><tr><th>a</th></tr><tr><td>1</td></tr></table>')))", "error3", "import io\nprint(len(pd.read_html(io.StringIO('<table><tr><th>a</th></tr><tr><td>1</td></tr></table>'))))", needs="lxml")
case("rs-xml", "raw-string-reader", "print(pd.read_xml('<r><x><a>1</a></x></r>').shape)", "error3", "import io\nprint(pd.read_xml(io.StringIO('<r><x><a>1</a></x></r>')).shape)", needs="lxml")
case("rs-neg-stringio", None, "import io\nprint(pd.read_json(io.StringIO('{\"a\": [1]}')).shape)", "same", fires=False)

# ---- options
case("opt-inf-as-na", "removed-option", "pd.set_option('mode.use_inf_as_na', True)\nprint('set')", "error3")
case("opt-cow-set", "cow-option", "pd.set_option('mode.copy_on_write', True)\nprint('set')", "warn3", note="isolated process (global option)")
case("opt-cow-attr", "cow-option", "pd.options.mode.copy_on_write = True\nprint('set')", "warn3", note="isolated process (global option)")

# ---- include-groups / stack / pct_change
G = "d = pd.DataFrame({'g': [1, 1, 2], 'v': [1, 2, 3]})\n"
case("ig-true", "include-groups", G + "print(d.groupby('g').apply(lambda x: x['v'].sum(), include_groups=True).tolist())", "error3", G + "print(d.groupby('g').apply(lambda x: x['v'].sum()).tolist())")
S = "d = pd.DataFrame({'a': [1, None], 'b': [2, 3]})\n"
case("stack-dropna", "stack-legacy-args", S + "print(d.stack(dropna=False).shape)", "error3", S + "print(d.stack(future_stack=True).shape)")
case("stack-sort", "stack-legacy-args", S + "print(d.stack(sort=True).shape)", "error3", S + "print(d.stack(future_stack=True).shape)")
case("stack-fs-false", "stack-legacy-args", S + "print(d.stack(future_stack=False).shape)", "warn3")
case("pct-pad", "pct-change-fill", "print(pd.Series([1, None, 2]).pct_change(fill_method='pad').tolist())", "error3", "print(pd.Series([1, None, 2]).ffill().pct_change(fill_method=None).tolist())")
case("pct-limit", "pct-change-fill", "print(pd.Series([1, 2]).pct_change(limit=1).tolist())", "error3", "print(pd.Series([1, 2]).pct_change(fill_method=None).tolist())")
case("pct-neg-none", None, "print(pd.Series([1, None, 2]).pct_change(fill_method=None).tolist())", "same", fires=False)

# ---- dtype checks
case("od-series", "object-dtype-check", "print(pd.Series(['x']).dtype == object)", "diff", "print(pd.api.types.is_string_dtype(pd.Series(['x'])))")
case("od-dtypes", "object-dtype-check", "print((pd.DataFrame({'a': ['x'], 'b': [1]}).dtypes == object).tolist())", "diff")
case("od-string-O", "object-dtype-check", "print(pd.Series(['x']).dtype == 'O')", "diff")
case("od-is_object_dtype", "object-dtype-check", "print(pd.api.types.is_object_dtype(pd.Series(['x'])))", "diff")
case("od-neg-int", None, "print(pd.Series([1]).dtype == 'int64')", "same", fires=False)
case("sd-object", "select-dtypes-object", "print(pd.DataFrame({'a': ['x'], 'b': [1]}).select_dtypes(include=object).columns.tolist())", "warn3", "print(pd.DataFrame({'a': ['x'], 'b': [1]}).select_dtypes(include=['object', 'string']).columns.tolist())")
case("sd-neg-number", None, "print(pd.DataFrame({'a': ['x'], 'b': [1]}).select_dtypes(include='number').columns.tolist())", "same", fires=False)

# ---- astype(str) + 'nan'
F = "s = pd.Series([1.0, float('nan')])\n"
case("as-eq", "astype-str-na-literal", F + "print((s.astype(str) == 'nan').tolist())", "diff", F + "print(s.isna().tolist())")
case("as-replace", "astype-str-na-literal", F + "print(s.astype(str).replace('nan', '').tolist())", "diff", F + "print(s.astype(str).where(s.notna(), '').tolist())")
case("as-str-replace", "astype-str-na-literal", F + "print(s.astype(str).str.replace('nan', '').tolist())", "diff", F + "print(s.astype(str).where(s.notna(), '').tolist())")
case("as-isin", "astype-str-na-literal", F + "print(s.astype(str).isin(['nan', 'None']).tolist())", "diff", F + "print(s.isna().tolist())")
case("as-none", "astype-str-na-literal", "s = pd.Series(['a', None])\nprint((s.astype(str) == 'None').tolist())", "diff", "s = pd.Series(['a', None])\nprint(s.isna().tolist())")
case("as-neg-plain", None, F + "print(len(s.astype(str)))", "same", fires=False)

# ---- datetime ns assumption
case("dt-index-int", "datetime-ns-assumption", "print((pd.to_datetime(['2024-01-01']).astype('int64') // 10**9).tolist())", "diff", "print(((pd.to_datetime(['2024-01-01']) - pd.Timestamp('1970-01-01')) // pd.Timedelta('1s')).tolist())")
case("dt-asi8", "datetime-ns-assumption", "print((pd.to_datetime(['2024-01-01']).asi8 // 10**9).tolist())", "diff", "print(((pd.to_datetime(['2024-01-01']) - pd.Timestamp('1970-01-01')) // pd.Timedelta('1s')).tolist())")
case("dt-series-div", "datetime-ns-assumption", "s = pd.Series(pd.to_datetime(['2024-01-01']))\nprint((s.astype('int64') / 1e9).tolist())", "diff",
     "s = pd.Series(pd.to_datetime(['2024-01-01']))\nprint(((s - pd.Timestamp('1970-01-01')) / pd.Timedelta('1s')).tolist())")
case("dt-col-dt", "datetime-ns-assumption", "d = pd.DataFrame({'t': pd.to_datetime(['2024-01-01'])})\nprint((d['t'].dt.tz_localize('UTC').astype('int64') // 10**9).tolist())", "diff",
     "d = pd.DataFrame({'t': pd.to_datetime(['2024-01-01'])})\nprint(((d['t'].dt.tz_localize('UTC') - pd.Timestamp('1970-01-01', tz='UTC')) // pd.Timedelta('1s')).tolist())")
case("dt-neg-plain-ints", None, "print((pd.Series([2_000_000_000, 4_000_000_000]).astype('int64') // 10**9).tolist())", "same", fires=False, note="plain integers: low confidence, hidden by default")
case("dt-neg-timestamp", None, "print(pd.Timestamp('2024-01-01').value // 10**9)", "same", fires=False)

# ---- copy keyword
case("cp-astype", "copy-keyword", "print(pd.Series([1]).astype('int64', copy=False).tolist())", "warn3", "print(pd.Series([1]).astype('int64').tolist())")
case("cp-reindex", "copy-keyword", "print(pd.Series([1]).reindex([0], copy=False).tolist())", "warn3", "print(pd.Series([1]).reindex([0]).tolist())")
case("cp-rename", "copy-keyword", "print(pd.Series([1]).rename('a', copy=False).name)", "warn3", "print(pd.Series([1]).rename('a').name)")
case("cp-concat", "copy-keyword", "print(pd.concat([pd.Series([1])], copy=False).tolist())", "warn3", "print(pd.concat([pd.Series([1])]).tolist())")
case("cp-merge", "copy-keyword", "a = pd.DataFrame({'k': [1]})\nprint(pd.merge(a, a, copy=False).shape)", "warn3", "a = pd.DataFrame({'k': [1]})\nprint(pd.merge(a, a).shape)")
case("cp-neg-numpy", None, "import numpy as np\nprint(np.array([1]).astype('int64', copy=False).tolist())", "same", fires=False)

# ---- negatives added after the precision study (v0.2.0): patterns that looked like findings in real code and are not
case("ci-neg-dict-of-frames", None, "d = {'a': pd.DataFrame({'a': [None, 1.0]})}\nd['a'].fillna(0, inplace=True)\nprint(d['a']['a'].tolist())", "same", fires=False,
     note="d['a'] is a dict lookup: the DataFrame itself is modified, on 2.3.3 and 3.x")
case("ca-neg-dict-of-frames", None, "d = {'a': pd.DataFrame({'a': [1, 2]})}\nd['a']['b'] = 5\nprint(d['a']['b'].tolist())", "same", fires=False)
case("cp-neg-asi8", None, "t = pd.to_datetime(pd.Series(['2024-01-01']))\nprint(pd.Index(t).asi8.astype('int64', copy=False).shape)", "same", fires=False)
case("od-neg-string-aware", None, PRE + "x = pd.Series(['a', None])\nprint(x.dtype == 'object' or x.dtype == 'string' or pd.api.types.is_string_dtype(x))", "same", fires=False,
     note="the condition already accepts the string dtype, so it is True on 2.3.3 (object) and 3.x (str)")
