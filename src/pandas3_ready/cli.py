"""Command line interface."""
from __future__ import annotations

import argparse
import sys

from . import __version__
from .diffmode import GitError, scan_against_base
from .report import RENDERERS, meets_threshold
from .rules import CONFIDENCE, NEW, OLD, RULES
from .scan import scan


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="pandas3-ready", description="Find code that breaks or silently changes on pandas 3.0: chained assignment, removed APIs and keywords, offset aliases, the str dtype. Reads .py files and notebooks; nothing is imported or run.")
    p.add_argument("path", nargs="?", default=".", help="directory (default: .) or one file")
    p.add_argument("-f", "--format", choices=sorted(RENDERERS), default="text")
    p.add_argument("-o", "--output", help="write the report to a file instead of stdout")
    p.add_argument("--fail-on", choices=["error", "warning", "never"], default="error", help="lowest severity that gives exit code 1 (default: error)")
    p.add_argument("--min-confidence", choices=CONFIDENCE, default="medium", help="lowest confidence to report (default: medium; high = provably pandas, low = shape only)")
    p.add_argument("--ignore", action="append", default=[], metavar="GLOB", help="path glob to skip (repeatable)")
    p.add_argument("--disable", action="append", default=[], metavar="RULE", help="turn a rule off (repeatable)")
    p.add_argument("--only", action="append", default=[], metavar="RULE", help="run only this rule (repeatable)")
    p.add_argument("--base", metavar="REF", help="PR mode: report only findings that are new compared to this git revision (merge base with HEAD)")
    p.add_argument("--list-rules", action="store_true")
    p.add_argument("--version", action="version", version=f"pandas3-ready {__version__} (rules checked on pandas {OLD} and {', '.join(NEW)})")
    a = p.parse_args(argv)
    if a.list_rules:
        for r in RULES.values():
            print(f"{r.id:<24} {r.severity:<8} {'oracle' if r.oracle else 'docs':<7} {r.summary}")
        return 0
    for rid in a.disable + a.only:
        if rid not in RULES:
            print(f"unknown rule: {rid} (see --list-rules)", file=sys.stderr)
            return 2
    if a.base:
        try:
            r = scan_against_base(a.path, a.base, a.ignore, a.disable, a.only, a.min_confidence)
        except GitError as e:
            print(f"pandas3-ready: {e}", file=sys.stderr)
            return 2
    else:
        r = scan(a.path, a.ignore, a.disable, a.only, a.min_confidence)
    text = RENDERERS[a.format](r)
    if a.output:
        with open(a.output, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text)
    return 1 if meets_threshold(r, a.fail_on) else 0


if __name__ == "__main__":
    raise SystemExit(main())
