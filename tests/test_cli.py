import json
import os

from pandas3_ready import __version__
from pandas3_ready.cli import main
from pandas3_ready.rules import RULES

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def run(capsys, *a):
    rc = main(list(a))
    return rc, capsys.readouterr().out


def test_legacy_fixture_fails_and_clean_one_passes(capsys):
    rc, out = run(capsys, os.path.join(FIX, "legacy"))
    assert rc == 1 and "removed-keyword" in out and "chained-inplace" in out
    rc, out = run(capsys, os.path.join(FIX, "clean"), "--fail-on", "warning")
    assert rc == 0, out


def test_fail_on_levels(capsys):
    p = os.path.join(FIX, "legacy", "analysis.ipynb")   # warnings only
    assert run(capsys, p)[0] == 0
    assert run(capsys, p, "--fail-on", "warning")[0] == 1
    assert run(capsys, p, "--fail-on", "never")[0] == 0


def test_notebook_lines_point_into_the_json(capsys):
    _, out = run(capsys, os.path.join(FIX, "legacy", "analysis.ipynb"), "-f", "json")
    d = json.loads(out)
    lines = open(os.path.join(FIX, "legacy", "analysis.ipynb")).read().split("\n")
    for f in d["findings"]:
        assert "fillna" in lines[f["line"] - 1] or "region" in lines[f["line"] - 1]
        assert f["cell"] in (2, 3)


def test_json_and_sarif_shape(capsys):
    _, out = run(capsys, os.path.join(FIX, "legacy"), "-f", "json")
    d = json.loads(out)
    assert d["tool"] == "pandas3-ready" and d["version"] == __version__ and d["findings"][0]["confidence"] in ("high", "medium")
    _, out = run(capsys, os.path.join(FIX, "legacy"), "-f", "sarif")
    s = json.loads(out)
    run0 = s["runs"][0]
    assert s["version"] == "2.1.0" and run0["tool"]["driver"]["name"] == "pandas3-ready"
    ids = [r["id"] for r in run0["tool"]["driver"]["rules"]]
    assert ids == list(RULES)
    for res in run0["results"]:
        assert ids[res["ruleIndex"]] == res["ruleId"] and res["properties"]["confidence"] and 0 <= res["rank"] <= 100
        assert res["locations"][0]["physicalLocation"]["region"]["startLine"] >= 1


def test_github_and_markdown_formats(capsys):
    _, out = run(capsys, os.path.join(FIX, "legacy"), "-f", "github")
    assert out.startswith("::") and "title=" in out
    _, out = run(capsys, os.path.join(FIX, "legacy"), "-f", "markdown")
    assert "| Severity | Confidence |" in out


def test_min_confidence_low_shows_more(capsys):
    src = "import pandas as pd\ncfg = load()\ncfg['a']['b'] = 1\n"
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        open(os.path.join(d, "a.py"), "w").write(src)
        _, out = run(capsys, d)
        assert "No pandas 3 findings" in out and "1 low-confidence" in out
        _, out = run(capsys, d, "--min-confidence", "low")
        assert "chained-assignment" in out


def test_only_disable_and_unknown_rule(capsys):
    p = os.path.join(FIX, "legacy")
    _, out = run(capsys, p, "--only", "removed-keyword", "-f", "json")
    assert {f["rule"] for f in json.loads(out)["findings"]} == {"removed-keyword"}
    _, out = run(capsys, p, "--disable", "removed-keyword", "-f", "json")
    assert "removed-keyword" not in {f["rule"] for f in json.loads(out)["findings"]}
    assert main([p, "--only", "nope"]) == 2


def test_ignore_glob(capsys):
    _, out = run(capsys, os.path.join(FIX, "legacy"), "--ignore", "*.py", "--ignore", "*.ipynb")
    assert "No pandas 3 findings" in out


def test_list_rules_and_version(capsys):
    rc, out = run(capsys, "--list-rules")
    assert rc == 0 and len(out.strip().splitlines()) == len(RULES)
    try:
        main(["--version"])
    except SystemExit:
        pass
    assert "2.3.3" in capsys.readouterr().out


def test_every_rule_has_text():
    for r in RULES.values():
        assert r.summary and r.fix and r.severity in ("error", "warning", "note")
