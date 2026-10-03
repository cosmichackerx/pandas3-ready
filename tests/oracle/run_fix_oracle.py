"""Oracle for --fix: every rewrite is run on real pandas.

  python run_fix_oracle.py --exec out.json     run each case's original and --fix-ed program with the pandas installed here, and the offline checks
  python run_fix_oracle.py --count             number of cases
  python run_fix_oracle.py OLD.json NEW.json   compare a pandas 2.3.3 run with a pandas 3.x run (needs no pandas)

Exit code 1 when a fixed program prints something different from the original on 2.3.3, differs on 3.x, warns, is changed by a second --fix, or still triggers its rule,
or when a `refuse` case was rewritten.
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "src"))
from fix_cases import FIX_CASES  # noqa: E402
from run_oracle import DEPRECATION, run_inline  # noqa: E402

HEAD = "import pandas as pd\nimport numpy as np\n"


def fixed_program(code: str):
    from pandas3_ready.fix import fix_text
    new, edits, skips = fix_text(HEAD + code, "case.py")
    return new[len(HEAD):], edits, skips


def offline(c) -> dict:
    from pandas3_ready.scan import scan_text
    new, edits, skips = fixed_program(c["code"])
    again, edits2, _ = fixed_program(new)
    left = [f.rule for f in scan_text(HEAD + new, min_conf="medium").findings]
    return {"fixed": new, "edits": len(edits), "idempotent": again == new and not edits2, "rule_left": c["rule"] in left, "skips": [s.why for s in skips]}


def do_exec(out_path: str) -> int:
    import pandas as pd
    res = {"pandas": pd.__version__, "cases": {}}
    for c in FIX_CASES:
        o = offline(c)
        entry = {"kind": c["kind"], "rule": c["rule"], "offline": o, "orig": run_inline(c["code"]), "fixed": run_inline(o["fixed"]) if o["fixed"] != c["code"] else None}
        res["cases"][c["id"]] = entry
    with open(out_path, "w") as fh:
        json.dump(res, fh, indent=1)
    print(f"pandas {pd.__version__}: ran {len(FIX_CASES)} fix cases -> {out_path}")
    return 0


def compare(old_path: str, new_path: str) -> int:
    old, new = json.load(open(old_path)), json.load(open(new_path))
    bad, n_fix, n_refuse = [], 0, 0
    for c in FIX_CASES:
        o, n = old["cases"][c["id"]], new["cases"][c["id"]]
        off = o["offline"]
        if c["kind"] == "refuse":
            n_refuse += 1
            if off["edits"]:
                bad.append(f"{c['id']}: --fix rewrote a case it must refuse")
            continue
        n_fix += 1
        if not off["edits"]:
            bad.append(f"{c['id']}: --fix made no edit")
            continue
        if o["orig"]["status"] != "ok":
            bad.append(f"{c['id']}: the original does not run on {old['pandas']}: {o['orig']['exc']}")
            continue
        if not off["idempotent"]:
            bad.append(f"{c['id']}: a second --fix changes the program again")
        if off["rule_left"]:
            bad.append(f"{c['id']}: the fixed program still triggers {c['rule']}")
        for label, r in (("old", o["fixed"]), ("new", n["fixed"])):
            if r["status"] != "ok":
                bad.append(f"{c['id']}: fixed program fails on the {label} pandas: {r['exc']}")
            elif r["out"] != o["orig"]["out"]:
                bad.append(f"{c['id']}: fixed program prints something different on the {label} pandas")
            if set(r["warn"]) & DEPRECATION:
                bad.append(f"{c['id']}: fixed program warns on the {label} pandas: {r['warn']}")
    print(f"pandas {old['pandas']} -> {new['pandas']}: {n_fix} fix cases, {n_refuse} refusal cases, {len(bad)} problem(s)")
    for b in bad:
        print("  " + b)
    return 1 if bad else 0


def main() -> int:
    a = sys.argv[1:]
    if a[:1] == ["--count"]:
        print(f"{len(FIX_CASES)} cases, {sum(1 for c in FIX_CASES if c['kind'] == 'fix')} fix cases, {sum(1 for c in FIX_CASES if c['kind'] == 'refuse')} refusal cases")
        return 0
    if a[:1] == ["--exec"]:
        return do_exec(a[1])
    if len(a) == 2:
        return compare(*a)
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
