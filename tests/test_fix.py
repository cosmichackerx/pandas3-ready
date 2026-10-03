import json

import pytest

from pandas3_ready.cli import main
from pandas3_ready.fix import fix_text

H = "import pandas as pd\n"


def fx(src, **kw):
    new, edits, skips = fix_text(H + src, **kw)
    return new[len(H):], edits, skips


@pytest.mark.parametrize("src,want", [
    ("df.fillna(method='ffill')\n", "df.ffill()\n"),
    ("df.fillna(method=\"pad\", limit=2)\n", "df.ffill(limit=2)\n"),
    ("df.fillna(limit=2, method='bfill')\n", "df.bfill(limit=2)\n"),
    ("df.fillna(method='backfill', axis=1, inplace=True)\n", "df.bfill(axis=1, inplace=True)\n"),
    ("df.fillna(\n    method='ffill',\n    limit=1,\n)\n", "df.ffill(\n    limit=1,\n)\n"),
    ("df.fillna(method='ffill',)\n", "df.ffill()\n"),
    ("df.applymap(str)\n", "df.map(str)\n"),
    ("pd.date_range('2024', periods=2, freq='H')\n", "pd.date_range('2024', periods=2, freq='h')\n"),
    ("pd.date_range('2024', periods=2, freq=\"30T\")\n", "pd.date_range('2024', periods=2, freq=\"30min\")\n"),
    ("pd.date_range('2024', periods=2, freq='M')\n", "pd.date_range('2024', periods=2, freq='ME')\n"),
    ("pd.date_range('2024', periods=2, freq='Q-DEC')\n", "pd.date_range('2024', periods=2, freq='QE-DEC')\n"),
    ("pd.date_range('2024', periods=2, freq='A-JAN')\n", "pd.date_range('2024', periods=2, freq='YE-JAN')\n"),
    ("x.resample('H').sum()\n", "x.resample('h').sum()\n"),
    ("pd.to_timedelta(3, unit='T')\n", "pd.to_timedelta(3, unit='min')\n"),
    ("pd.Timedelta(3, unit='H')\n", "pd.Timedelta(3, unit='h')\n"),
    ("pd.read_csv('a', delim_whitespace=True)\n", "pd.read_csv('a', sep=r\"\\s+\")\n"),
    ("pd.read_csv('a', infer_datetime_format=True, header=0)\n", "pd.read_csv('a', header=0)\n"),
    ("pd.concat([a, b], copy=False)\n", "pd.concat([a, b])\n"),
    ("pd.concat([a, b], copy=True, axis=1)\n", "pd.concat([a, b], axis=1)\n"),
])
def test_rewrites(src, want):
    new, edits, skips = fx(src)
    assert new == want and edits


@pytest.mark.parametrize("src", [
    "df.fillna(0, method='ffill')\n",                 # a value as well
    "df.fillna(method='ffill', downcast='infer')\n",  # no one-line equivalent
    "m = 'ffill'\ndf.fillna(method=m)\n",             # not a literal
    "df.fillna(\n    method='ffill',  # carry\n    limit=1)\n",   # comment would be lost
    "x.resample('M').sum()\n",                        # valid on a PeriodIndex
    "x.resample('A').sum()\n",
    "pd.date_range('2024', periods=2, freq=f)\n",     # not a literal
    "pd.read_csv('a', sep=' ', delim_whitespace=True)\n",
    "pd.read_csv('a', delim_whitespace=w)\n",
    "pd.concat([a, b], copy=flag)\n",
    "pd.to_numeric(s, errors='ignore')\n",            # a human decision
    "df['a'][0] = 1\n",
    "df['a'].fillna(0, inplace=True)\n",
    "s.pct_change(fill_method='ffill')\n",
    "df.stack(dropna=False)\n",
])
def test_refused_and_unfixable_are_left_alone(src):
    new, edits, _ = fx(src)
    assert new == src and not edits


def test_idempotent():
    src = "df.fillna(method='ffill', limit=1).applymap(str)\npd.date_range('2024', periods=2, freq='H')\npd.concat([a, b], copy=False)\n"
    once, e1, _ = fx(src)
    twice, e2, _ = fx(once)
    assert once == twice and e1 and not e2


def test_ignore_comment_is_respected():
    new, edits, _ = fx("df.applymap(str)  # pandas3-ready: ignore removed-method\n")
    assert not edits and new.endswith("ignore removed-method\n")


def test_non_ascii_before_the_edit_and_crlf():
    src = "x = 'héllo €'; df.fillna(method='ffill')\r\ny = 'ü'; z.applymap(f)\r\n"
    new, edits, _ = fx(src)
    assert new == "x = 'héllo €'; df.ffill()\r\ny = 'ü'; z.map(f)\r\n" and len(edits) == 3


def test_two_removed_keywords_on_one_call():
    new, edits, _ = fx("pd.read_csv('a', delim_whitespace=True, infer_datetime_format=True)\n")
    assert new == "pd.read_csv('a', sep=r\"\\s+\")\n" and len(edits) == 2


def test_untyped_receiver_still_gets_alias_fix_but_not_period_family():
    assert fx("x.resample('30T').mean()\n")[0] == "x.resample('30min').mean()\n"
    assert fx("x.resample('M').mean()\n")[2], "the refusal is reported with a reason"


def test_file_without_pandas_and_syntax_errors_untouched(tmp_path):
    (tmp_path / "a.py").write_text("df.fillna(method='ffill')\n")
    (tmp_path / "b.py").write_text("import pandas as pd\ndef (:\n")
    assert main([str(tmp_path), "--fix"]) == 0
    assert (tmp_path / "a.py").read_text() == "df.fillna(method='ffill')\n"
    assert (tmp_path / "b.py").read_text() == "import pandas as pd\ndef (:\n"


def test_cli_diff_writes_nothing_and_exits_1(tmp_path, capsys):
    p = tmp_path / "a.py"
    p.write_text("import pandas as pd\ndf = pd.DataFrame()\ndf = df.fillna(method='ffill')\n")
    assert main([str(tmp_path), "--diff"]) == 1
    out = capsys.readouterr().out
    assert "-df = df.fillna(method='ffill')" in out and "+df = df.ffill()" in out
    assert "fillna(method" in p.read_text()


def test_cli_fix_writes_and_second_run_is_clean(tmp_path):
    p = tmp_path / "a.py"
    p.write_text("import pandas as pd\ndf = pd.DataFrame()\ndf = df.fillna(method='ffill')\n")
    assert main([str(tmp_path), "--fix"]) == 0
    assert p.read_text() == "import pandas as pd\ndf = pd.DataFrame()\ndf = df.ffill()\n"
    assert main([str(tmp_path), "--diff"]) == 0


def test_notebooks_are_never_rewritten(tmp_path, capsys):
    nb = {"cells": [{"cell_type": "code", "source": ["import pandas as pd\n", "df.fillna(method='ffill')\n"], "metadata": {}, "outputs": [], "execution_count": None}], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}
    p = tmp_path / "n.ipynb"
    text = json.dumps(nb)
    p.write_text(text)
    assert main([str(tmp_path), "--fix"]) == 0
    assert p.read_text() == text
    assert "1 notebook(s)" in capsys.readouterr().err


def test_fix_and_diff_exclude_each_other_and_base(tmp_path):
    assert main([str(tmp_path), "--fix", "--diff"]) == 2
    assert main([str(tmp_path), "--fix", "--base", "HEAD"]) == 2
