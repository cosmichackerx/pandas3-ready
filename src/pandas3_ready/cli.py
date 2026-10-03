"""Command line interface."""
from __future__ import annotations

import argparse
import sys
import warnings

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
    p.add_argument("--fix", action="store_true", help="rewrite the findings that have a mechanical, oracle-checked replacement (.py files; see the README for exactly which)")
    p.add_argument("--diff", action="store_true", help="show what --fix would change as a unified diff and write nothing (exit 1 if anything would change)")
    p.add_argument("--list-rules", action="store_true")
    p.add_argument("--version", action="version", version=f"pandas3-ready {__version__} (rules checked on pandas {OLD} and {', '.join(NEW)})")
    a = p.parse_args(argv)
    warnings.simplefilter("ignore", SyntaxWarning)   # parsing other people's code: invalid escape sequences in old strings are not our business
    if a.list_rules:
        for r in RULES.values():
            print(f"{r.id:<24} {r.severity:<8} {'oracle' if r.oracle else 'docs':<7} {r.summary}")
        return 0
    for rid in a.disable + a.only:
        if rid not in RULES:
            print(f"unknown rule: {rid} (see --list-rules)", file=sys.stderr)
            return 2
    if a.fix or a.diff:
        if a.base or (a.fix and a.diff):
            print("pandas3-ready: --base cannot be combined with --fix or --diff, and --fix and --diff exclude each other", file=sys.stderr)
            return 2
        from .fix import fix_path
        edits, skips, diffs, changed, notebooks = fix_path(a.path, a.ignore, a.disable, a.only, write=a.fix, min_conf="medium")
        if a.diff:
            sys.stdout.write("".join(diffs))
        for rel, ln, e in edits:
            print(f"{'fixed' if a.fix else 'would fix'} {rel}:{ln}: {e.old!r} -> {e.new!r}  [{e.rule}]", file=sys.stderr)
        for sk in skips:
            print(f"not rewritten {sk.file}:{sk.line}: {sk.why}  [{sk.rule}]", file=sys.stderr)
        left = scan(a.path, a.ignore, a.disable, a.only, a.min_confidence)
        print(f"pandas3-ready: {len(edits)} edit(s) in {changed} file(s){'' if a.fix else ' (nothing written)'}, {len(skips)} not rewritten, {len(left.findings)} finding(s) "
              f"{'remain' if a.fix else 'before the fixes'} that need a human; {notebooks} notebook(s) are never rewritten (run without --fix for the list)", file=sys.stderr)
        return 1 if a.diff and edits else 0
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
