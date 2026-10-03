"""Run pandas3-ready (at --min-confidence low, so every confidence level is in the data) on every downloaded repository directory.

    python study/run_scan.py DEST OUT.json
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from pandas3_ready.scan import scan  # noqa: E402

dest, out = sys.argv[1], sys.argv[2]
repos, findings = [], []
for d in sorted(os.listdir(dest)):
    p = os.path.join(dest, d)
    if not os.path.isdir(p):
        continue
    r = scan(p, min_conf="low")
    repos.append({"repo": d.replace("__", "/", 1), "files": r.files_scanned, "pandas_files": r.pandas_files, "findings": len(r.findings)})
    for f in r.findings:
        findings.append({"repo": d.replace("__", "/", 1), "rule": f.rule, "severity": f.severity, "confidence": f.confidence, "file": f.file, "line": f.line, "cell": f.cell,
                         "message": f.message, "snippet": f.snippet})
json.dump({"repos": repos, "findings": findings}, open(out, "w"), indent=1)
print(len(repos), "repositories,", sum(r["pandas_files"] for r in repos), "files import pandas,", len(findings), "findings")
