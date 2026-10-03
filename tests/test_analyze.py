"""Scanner behaviour on small snippets: what is reported, with which confidence, and (as important) what is not."""
import pytest

from pandas3_ready.scan import scan_text

HEAD = "import pandas as pd\nimport numpy as np\n"


def found(src, conf="low"):
    return [(f.rule, f.confidence) for f in scan_text(HEAD + src, min_conf=conf).findings]


def rules(src, conf="medium"):
    return {r for r, _ in found(src, conf)}


# ---- only pandas files are analysed
def test_file_without_pandas_import_is_skipped():
    assert scan_text("df = {}\ndf['a'].fillna(0, inplace=True)\nx.applymap(f)\n", "low").findings == []


def test_from_import_and_alias_are_resolved():
    src = "from pandas import read_csv as rc, date_range\nrc('x', delim_whitespace=True)\ndate_range('2024', periods=2, freq='H')\n"
    assert {f.rule for f in scan_text(src, "low").findings} == {"removed-keyword", "removed-offset-alias"}


def test_import_pandas_without_alias():
    src = "import pandas\npandas.read_csv('x', verbose=True)\n"
    assert [f.rule for f in scan_text(src).findings] == ["removed-keyword"]


# ---- confidence: provably pandas is high, vocabulary only is medium
def test_known_receiver_is_high():
    assert found("df = pd.read_csv('a')\ndf['a'].fillna(0, inplace=True)\n") == [("chained-inplace", "high")]


def test_function_parameter_is_medium():
    assert found("def f(d):\n    d['a'].fillna(0, inplace=True)\n") == [("chained-inplace", "medium")]


def test_annotated_parameter_is_known():
    assert found("def f(d: pd.DataFrame):\n    d['a'].fillna(0, inplace=True)\n") == [("chained-inplace", "high")]


def test_name_assigned_twice_with_a_non_pandas_value_is_not_known():
    r = found("x = pd.read_csv('a')\nx = {}\nx['a']['b'] = 1\n")
    assert r == [("chained-assignment", "low")]


def test_self_attribute_is_followed():
    src = "class A:\n    def __init__(self):\n        self.df = pd.DataFrame()\n    def f(self):\n        self.df['a'][0] = 1\n"
    assert found(src) == [("chained-assignment", "high")]


def test_copy_of_known_is_known():
    assert found("a = pd.read_csv('a')\nb = a.copy()\nb['x'][0] = 1\n") == [("chained-assignment", "high")]


def test_shape_only_is_low_and_hidden_by_default():
    assert found("cfg = load()\ncfg['a']['b'] = 1\n") == [("chained-assignment", "low")]
    assert found("cfg = load()\ncfg['a']['b'] = 1\n", conf="medium") == []


def test_loc_in_the_chain_is_medium():
    assert found("def f(x):\n    x['a'].loc[0] = 1\n") == [("chained-assignment", "medium")]


def test_notebook_variables_flow_between_cells(tmp_path):
    import json
    from pandas3_ready.scan import scan
    cells = [["import pandas as pd\n", "df = pd.read_csv('a')\n"], ["df['a'][0] = 1\n"]]
    nb = {"cells": [{"cell_type": "code", "metadata": {}, "outputs": [], "execution_count": None, "source": c} for c in cells], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}
    (tmp_path / "n.ipynb").write_text(json.dumps(nb, indent=1))
    f = scan(str(tmp_path)).findings
    assert [(x.rule, x.confidence, x.cell) for x in f] == [("chained-assignment", "high", 2)]


# ---- things that must NOT be reported (other libraries, correct pandas)
@pytest.mark.parametrize("src", [
    "t = torch.zeros(3)\nm = t.bool()\n",                       # torch Tensor.bool
    "a = np.zeros(3)\nb = a.view('int64')\nc = a.ravel()\nd = a.swapaxes(0, 1)\n",  # numpy
    "x = a.astype('int64', copy=False)\n",                       # numpy astype(copy=)
    "s = 'a-b'.replace('-', '_')\nt = s.replace('a', 'b', 1)\n",
    "from itertools import groupby\nfor k, g in groupby(items):\n    pass\n",
    "r = df2.groupby('g').first()\n",                              # groupby().first() without offset
    "d = {}\nd['a'] = {}\nd['a']['b'] = 1\n",
    "x = np.zeros((2, 2))\nx[0][1] = 3\nx.values = 1\n",
    "df = pd.DataFrame()\ndf.loc[0, 'a'] = 1\ndf.iloc[0, 0] = 2\ndf['b'] = 3\n",
    "df = pd.DataFrame()\ndf = df.fillna(0)\ndf.fillna(0, inplace=True)\ndf.dropna(inplace=True)\n",
    "s = pd.Series([1]).copy()\ns.fillna(0, inplace=True)\n",
    "idx = pd.period_range('2024-01', periods=2, freq='M')\nx = pd.Period('2024', 'Y')\ny = idx.to_period('M')\n",
    "pd.date_range('2024', periods=2, freq='h')\npd.date_range('2024', periods=2, freq='ME')\npd.date_range('2024', freq='D', periods=2)\n",
    "pd.Timedelta(1, unit='min')\npd.Timedelta(1, unit='s')\n",
    "import io\npd.read_json(io.StringIO('{}'))\npd.read_json('data.json')\npd.read_json(text)\n",
    "pd.to_numeric(x, errors='coerce')\npd.to_datetime(x, errors='raise')\n",
    "pd.read_csv('a', sep=r'\\s+')\n",
    "x = df.dtype\nok = np.dtype('int64') == np.dtype('float64')\n",
    "a = size // 10**9\nb = nbytes / 1e9\n",                          # plain arithmetic
    "ts = pd.Timestamp('2024').value // 10**9\n",
    "np.concatenate([a, b], copy=False)\n",
    "obj.merge(other, copy=False)\nnp.empty(3).astype(float, copy=False)\n" if False else "np.empty(3).astype(float, copy=False)\n",
])
def test_not_reported(src):
    assert found(src, conf="medium") == [], src


def test_dict_view_is_not_array_write():
    assert found("d = {}\nd.values()[0] = 1\n") == []


def test_values_write_needs_pandas_evidence():
    assert found("m = Model()\nm.values[0] = 1\n") == []
    assert found("df = pd.DataFrame()\ndf.values[0, 0] = 1\n") == [("readonly-array-write", "high")]


# ---- rules, one assertion each (the oracle covers behaviour; this covers detection details)
def test_offset_aliases_with_suffix_and_multiple():
    assert rules("pd.date_range('2024', periods=2, freq='2H')\npd.date_range('2024', periods=2, freq='Q-DEC')\npd.date_range('2024', periods=2, freq='AS-JAN')\n") == {"removed-offset-alias"}
    assert len(found("pd.date_range('2024', periods=2, freq='Q-DEC')\n")) == 1


def test_alias_message_names_the_replacement():
    f = scan_text(HEAD + "pd.date_range('2024', periods=2, freq='Q-DEC')\n").findings[0]
    assert "'QE-DEC'" in f.message


def test_resample_M_is_medium_even_on_a_known_receiver():
    assert found("s = pd.Series([1])\ns.resample('M')\n") == [("removed-offset-alias", "medium")]


def test_period_context_keeps_M():
    assert found("pd.period_range('2024-01', periods=2, freq='M')\n") == []
    assert found("pd.period_range('2024-01-01', periods=2, freq='H')\n") == [("removed-offset-alias", "high")]


def test_timedelta_H_is_a_note():
    f = scan_text(HEAD + "pd.Timedelta(1, unit='H')\n").findings[0]
    assert f.severity == "note" and f.rule == "removed-timedelta-unit"


def test_astype_str_needs_the_nan_text():
    assert rules("s = pd.Series([1])\nx = s.astype(str)\n") == set()
    assert rules("s = pd.Series([1])\nx = s.astype(str) == 'nan'\n") == {"astype-str-na-literal"}
    assert rules("s = pd.Series([1])\nx = s.astype(str).str.strip() == 'None'\n") == {"astype-str-na-literal"}
    assert rules("s = pd.Series([1])\nx = s.astype(str).replace('nan', '')\n") == {"astype-str-na-literal"}
    assert rules("s = pd.Series([1])\nx = s.astype(str).replace('abc', '')\n") == set()


def test_object_dtype_variants():
    assert rules("s = pd.Series([1])\ns.dtype == object\ns.dtype == 'O'\ns.dtype is object\n") == {"object-dtype-check"}
    assert rules("a = np.zeros(2)\na.dtype == object\n", "medium") == set()   # unknown receiver: low


def test_select_dtypes_object_only_when_text_not_covered():
    assert rules("df = pd.DataFrame()\ndf.select_dtypes(include=object)\n") == {"select-dtypes-object"}
    assert rules("df = pd.DataFrame()\ndf.select_dtypes(include=['object', 'string'])\n") == set()
    assert rules("df = pd.DataFrame()\ndf.select_dtypes(exclude=object)\n") == set()


def test_datetime_ns_needs_evidence_for_medium():
    assert found("df = pd.DataFrame()\nx = df['created_at'].astype('int64') // 10**9\n") == [("datetime-ns-assumption", "medium")]
    assert found("df = pd.DataFrame()\nx = df['size'].astype('int64') // 10**9\n") == [("datetime-ns-assumption", "low")]
    assert found("df = pd.DataFrame()\nx = df.index.asi8 // 10**9\n") == [("datetime-ns-assumption", "high")]


def test_inplace_on_attribute_column():
    assert found("df = pd.DataFrame()\ndf.a.fillna(0, inplace=True)\n") == [("chained-inplace", "high")]
    assert found("df = pd.DataFrame()\ndf.fillna(0, inplace=True)\n") == []


def test_stack_pct_include_groups():
    assert rules("df = pd.DataFrame()\ndf.stack(dropna=False)\ndf.pct_change(fill_method='pad')\ndf.groupby('a').apply(f, include_groups=True)\n") == {"stack-legacy-args", "pct-change-fill", "include-groups"}
    assert rules("df = pd.DataFrame()\ndf.pct_change(fill_method=None)\ndf.groupby('a').apply(f, include_groups=False)\n") == set()


def test_options_and_cow():
    assert rules("pd.set_option('mode.use_inf_as_na', True)\npd.options.mode.copy_on_write = True\npd.set_option('mode.copy_on_write', True)\n") == {"removed-option", "cow-option"}
    assert rules("pd.set_option('display.max_rows', 5)\npd.options.mode.chained_assignment = None\n") == set()


def test_copy_keyword():
    assert rules("a = pd.concat([x], copy=False)\nb = pd.merge(x, y, copy=True)\nc = df.rename(columns={}, copy=False)\n") == {"copy-keyword"}
    assert rules("d = pd.DataFrame()\ne = d.astype('int64', copy=False)\n") == {"copy-keyword"}


# ---- suppression
def test_ignore_comment_same_line_and_previous_line():
    src = "df = pd.DataFrame()\ndf['a'].fillna(0, inplace=True)  # pandas3-ready: ignore\n# pandas3-ready: ignore [chained-assignment]\ndf['a'][0] = 1\ndf['b'][0] = 1\n"
    r = scan_text(HEAD + src).findings
    assert [(f.rule, f.line) for f in r] == [("chained-assignment", 7)]


def test_ignore_comment_with_other_rule_does_not_hide():
    src = "df = pd.DataFrame()\ndf['a'].fillna(0, inplace=True)  # pandas3-ready: ignore [removed-method]\n"
    assert [f.rule for f in scan_text(HEAD + src).findings] == ["chained-inplace"]


def test_syntax_error_is_counted_not_fatal():
    r = scan_text("import pandas as pd\ndef (:\n")
    assert r.findings == [] and r.unparsed == 1
