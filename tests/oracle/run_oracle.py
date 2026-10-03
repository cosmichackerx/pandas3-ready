"""Differential oracle: run every case on pandas 2.3.3 and on pandas 3.x and check that the scanner agrees with what pandas did.

  python run_oracle.py --exec out.json     run all cases (and their fixed versions) with the pandas installed here
  python run_oracle.py --count             print the number of cases and rules they cover
  python run_oracle.py OLD.json NEW.json   compare two runs and check the scanner on every case (needs no pandas)

Exit code 1 when pandas behaved differently from the case's `expect`, a fix is not equivalent, or the scanner disagrees.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import warnings

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "src"))
from cases import CASES  # noqa: E402

DEPRECATION = {"Pandas4Warning", "FutureWarning", "DeprecationWarning", "ChainedAssignmentError", "SettingWithCopyWarning"}


def isolated(code: str) -> bool:
    return "mode.copy_on_write" in code or "use_inf_as_na" in code


def run_inline(code: str) -> dict:
    import numpy as np
    import pandas as pd
    buf = io.StringIO()
    g = {"pd": pd, "np": np}
    status, exc = "ok", None
    with warnings.catch_warnings(record=True) as w, contextlib.redirect_stdout(buf):
        warnings.simplefilter("always")
        try:
            exec(code, g)
        except BaseException as e:  # noqa: BLE001
            status, exc = "error", type(e).__name__
    return {"status": status, "out": buf.getvalue().strip(), "exc": exc, "warn": sorted({x.category.__name__ for x in w})}


def run_isolated(code: str) -> dict:
    r = subprocess.run([sys.executable, __file__, "--one"], input=code, capture_output=True, text=True, timeout=120)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return {"status": "error", "out": "", "exc": "Crash", "warn": []}


def run(code: str) -> dict:
    return run_isolated(code) if isolated(code) else run_inline(code)


def do_exec(out_path: str) -> int:
    import pandas as pd
    res = {"pandas": pd.__version__, "cases": {}}
    for c in CASES:
        if c["needs"]:
            try:
                __import__(c["needs"])
            except ImportError:
                res["cases"][c["id"]] = {"skipped": f"needs {c['needs']}"}
                continue
        res["cases"][c["id"]] = {"orig": run(c["code"]), **({"fixed": run(c["fixed"])} if c["fixed"] else {})}
    with open(out_path, "w") as fh:
        json.dump(res, fh, indent=1)
    print(f"pandas {pd.__version__}: ran {len(CASES)} cases -> {out_path}")
    return 0


def judge(expect, o, n):
    """Return an error string or None."""
    if expect == "error3":
        return None if (o["status"] == "ok" and n["status"] == "error") else f"expected ok -> error, got {o['status']} -> {n['status']} ({n['exc']})"
    if o["status"] != "ok" or n["status"] != "ok":
        return f"expected both to run, got {o['status']}({o['exc']}) -> {n['status']}({n['exc']})"
    if expect == "diff":
        return None if o["out"] != n["out"] else f"expected different output, both printed {o['out']!r}"
    if o["out"] != n["out"]:
        return f"expected same output, got {o['out']!r} vs {n['out']!r}"
    new_warn = set(n["warn"]) - set(o["warn"])
    if expect == "warn3":
        return None if new_warn & DEPRECATION else f"expected a new deprecation warning on 3.x, got {n['warn']} (old {o['warn']})"
    if expect == "same":
        return None if not (new_warn & DEPRECATION) else f"expected no new warning, got {sorted(new_warn)}"
    return f"unknown expect {expect}"


def compare(old_path: str, new_path: str) -> int:
    from pandas3_ready.scan import scan_text
    old, new = json.load(open(old_path)), json.load(open(new_path))
    bad, ran, skipped, scanner_ok = [], 0, 0, 0
    for c in CASES:
        o, n = old["cases"][c["id"]], new["cases"][c["id"]]
        if "skipped" in o or "skipped" in n:
            skipped += 1
            continue
        ran += 1
        err = judge(c["expect"], o["orig"], n["orig"])
        if err:
            bad.append(f"{c['id']}: {err}")
        if c["fixed"]:
            fo, fn = o["fixed"], n["fixed"]
            if fo["status"] != "ok" or fn["status"] != "ok" or fo["out"] != fn["out"]:
                bad.append(f"{c['id']}: fixed code differs between versions: {fo['status']}:{fo['out']!r} vs {fn['status']}:{fn['out']!r} ({fo['exc']}, {fn['exc']})")
            elif set(fn["warn"]) & DEPRECATION:
                bad.append(f"{c['id']}: fixed code warns on {new['pandas']}: {fn['warn']}")
        found = {f.rule for f in scan_text("import pandas as pd\n" + c["code"]).findings}
        if c["fires"] is True and c["rule"] not in found:
            bad.append(f"{c['id']}: scanner did not report {c['rule']} (reported {sorted(found)})")
        elif c["fires"] is False and found:
            bad.append(f"{c['id']}: scanner reported {sorted(found)} on code that should be clean")
        elif c["fires"] == "fp" and c["rule"] not in found:
            bad.append(f"{c['id']}: documented false positive no longer reported (update the docs)")
        else:
            scanner_ok += 1
        if c["fixed"] and c["rule"]:
            again = {f.rule for f in scan_text("import pandas as pd\n" + c["fixed"]).findings}
            if c["rule"] in again:
                bad.append(f"{c['id']}: the recommended fix is itself reported as {c['rule']}")
    print(f"pandas {old['pandas']} -> {new['pandas']}: {ran} cases run, {skipped} skipped, {len(bad)} disagreement(s), scanner agrees on {scanner_ok}")
    for b in bad:
        print("  DISAGREE", b)
    return 1 if bad else 0


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--one":
        print(json.dumps(run_inline(sys.stdin.read())))
        sys.exit(0)
    if len(sys.argv) == 2 and sys.argv[1] == "--count":
        print(f"{len(CASES)} cases, {len({c['rule'] for c in CASES if c['rule']})} rules, {sum(1 for c in CASES if c['fixed'])} fixed cases")
        sys.exit(0)
    if len(sys.argv) == 3 and sys.argv[1] == "--exec":
        sys.exit(do_exec(sys.argv[2]))
    if len(sys.argv) == 3:
        sys.exit(compare(sys.argv[1], sys.argv[2]))
    print(__doc__)
    sys.exit(2)
