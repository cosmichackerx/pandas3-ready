"""Renderers: text, markdown, json, github annotations, sarif."""
from __future__ import annotations

import json

from . import __version__
from .rules import NEW, OLD, RULES
from .scan import Result

ORDER = {"error": 0, "warning": 1, "note": 2}
RANK = {"high": 90.0, "medium": 60.0, "low": 30.0}
URL = "https://github.com/cosmichackerx/pandas3-ready"


def counts(r: Result) -> dict:
    c = {"error": 0, "warning": 0, "note": 0}
    for f in r.findings:
        c[f.severity] += 1
    return c


def summary_line(r: Result) -> str:
    c = counts(r)
    base = (f"{r.files_scanned} Python file(s) scanned, {r.pandas_files} import pandas; behaviour checked on pandas {OLD} and {NEW[-1]}. "
            f"{c['error']} error, {c['warning']} warning, {c['note']} note")
    if r.pr:
        base += f" introduced since {r.pr['base']}. Not shown: {r.pr['existing']} that were already there; {r.pr['resolved']} resolved"
    base += "."
    if r.hidden_low:
        base += f" {r.hidden_low} low-confidence match(es) hidden (--min-confidence low shows them)."
    if r.unparsed:
        base += f" {r.unparsed} file(s)/cell(s) could not be parsed and were skipped."
    return base


def where(f) -> str:
    return f"{f.file}:{f.line}" + (f" (cell {f.cell})" if f.cell else "")


def render_text(r: Result) -> str:
    out: list = []
    if not r.findings:
        out.append("No new pandas 3 findings." if r.pr else "No pandas 3 findings.")
    last = None
    for f in r.findings:
        if f.file != last:
            out.append(f"\n{f.file}")
            last = f.file
        out.append(f"  {f.line:>5}:{f.col:<4} {f.severity:<7} {f.confidence:<6} {f.rule:<24} {f.message}" + (f" (cell {f.cell})" if f.cell else ""))
    out += ["", summary_line(r)]
    return "\n".join(out).lstrip("\n") + "\n"


def render_markdown(r: Result) -> str:
    out = ["## pandas3-ready", "", summary_line(r), ""]
    if r.findings:
        out += ["| Severity | Confidence | Rule | Where | Message |", "|---|---|---|---|---|"]
        for f in sorted(r.findings, key=lambda f: (ORDER[f.severity], f.file, f.line)):
            out.append(f"| {f.severity} | {f.confidence} | `{f.rule}` | `{where(f)}` | {f.message.replace('|', chr(92) + '|')} |")
    else:
        out.append("No new findings." if r.pr else "No findings.")
    return "\n".join(out) + "\n"


def render_json(r: Result) -> str:
    return json.dumps({
        "tool": "pandas3-ready", "version": __version__, "testedAgainst": {"baseline": OLD, "pandas3": NEW},
        "filesScanned": r.files_scanned, "pandasFiles": r.pandas_files, "hiddenLowConfidence": r.hidden_low, "summary": counts(r),
        **({"pullRequest": r.pr} if r.pr else {}),
        "findings": [{"rule": f.rule, "severity": f.severity, "confidence": f.confidence, "file": f.file, "line": f.line, "column": f.col,
                      **({"cell": f.cell} if f.cell else {}), "message": f.message, "snippet": f.snippet} for f in r.findings],
    }, indent=2) + "\n"


def render_github(r: Result) -> str:
    def esc(s: str) -> str:
        return s.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    lvl = {"error": "error", "warning": "warning", "note": "notice"}
    return "".join(f"::{lvl[f.severity]} file={f.file},line={f.line},col={f.col},title={f.rule} ({f.confidence})::{esc(f.message)}\n" for f in r.findings)


def render_sarif(r: Result) -> str:
    level = {"error": "error", "warning": "warning", "note": "note"}
    ids = list(RULES)
    rules = [{"id": i, "name": i, "shortDescription": {"text": RULES[i].summary}, "helpUri": RULES[i].url,
              "help": {"text": RULES[i].fix}, "defaultConfiguration": {"level": level[RULES[i].severity]}} for i in ids]
    results = [{"ruleId": f.rule, "ruleIndex": ids.index(f.rule), "level": level[f.severity], "rank": RANK[f.confidence],
                "message": {"text": f.message}, "properties": {"confidence": f.confidence},
                "locations": [{"physicalLocation": {"artifactLocation": {"uri": f.file, "uriBaseId": "%SRCROOT%"},
                                                    "region": {"startLine": max(1, f.line), "startColumn": max(1, f.col)}}}]} for f in r.findings]
    return json.dumps({"$schema": "https://json.schemastore.org/sarif-2.1.0.json", "version": "2.1.0",
                       "runs": [{"tool": {"driver": {"name": "pandas3-ready", "version": __version__, "informationUri": URL, "rules": rules}},
                                 "results": results}]}, indent=2) + "\n"


RENDERERS = {"text": render_text, "markdown": render_markdown, "json": render_json, "github": render_github, "sarif": render_sarif}


def meets_threshold(r: Result, fail_on: str) -> bool:
    if fail_on == "never":
        return False
    return any(f.severity == "error" or (fail_on == "warning" and f.severity == "warning") for f in r.findings)
