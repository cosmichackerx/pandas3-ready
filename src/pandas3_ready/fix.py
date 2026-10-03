r"""--fix / --diff: rewrite the findings that have a mechanical, oracle-checked replacement. Python files only (notebooks are reported, not rewritten).

What is rewritten (each one is run on real pandas 2.3.3 and 3.x by tests/oracle/run_fix_oracle.py: the original and the fixed program must print the same):
  .fillna(method='ffill'|'pad'|'bfill'|'backfill'[, limit=, axis=, inplace=])  ->  .ffill(...) / .bfill(...)
  .applymap(f)                                   ->  .map(f)                       (pandas >= 2.1)
  frequency aliases 'H' 'T' 'S' 'L' 'U' 'N' ...   ->  'h' 'min' 's' 'ms' 'us' 'ns'   ('M' 'Q' 'Y' 'A' ... -> 'ME' 'QE' 'YE' only where the receiver is
                                                    provably a DatetimeIndex producer such as pd.date_range; pandas >= 2.2)
  Timedelta/to_timedelta unit 'T' 'L' 'U' 'N' 'H' ->  'min' 'ms' 'us' 'ns' 'h'
  read_csv/read_table(delim_whitespace=True)      ->  sep=r"\s+"
  infer_datetime_format=<bool>                   ->  removed
  copy=<True|False> on concat/merge/reindex/rename/astype -> removed (on pandas 2 without Copy-on-Write, copy=False no longer shares memory)
Everything else (errors='ignore', chained assignment, stack(dropna=), pct_change(fill_method=), ...) changes meaning and is left for a human.
"""
from __future__ import annotations

import ast
import difflib
import re

from .analyze import Analyzer, State
from .rules import CONFIDENCE
from .scan import iter_files, suppressed

NEWLINE = re.compile(r"\r\n|\r|\n")


class Edit:
    def __init__(self, start, end, text, line, rule, old, new):
        self.start, self.end, self.text, self.line, self.rule, self.old, self.new = start, end, text, line, rule, old, new


class Skip:
    def __init__(self, file, line, rule, why):
        self.file, self.line, self.rule, self.why = file, line, rule, why


class Offsets:
    """AST (line, utf-8 byte column) -> character offset in the text."""

    def __init__(self, text):
        self.text = text
        self.starts = [0] + [m.end() for m in NEWLINE.finditer(text)]

    def at(self, line, col):
        base = self.starts[line - 1]
        end = self.starts[line] if line < len(self.starts) else len(self.text)
        raw = self.text[base:end].encode("utf-8")
        return base + len(raw[:col].decode("utf-8", errors="strict"))

    def span(self, node):
        return self.at(node.lineno, node.col_offset), self.at(node.end_lineno, node.end_col_offset)


def _elements(call):
    return sorted(list(call.args) + list(call.keywords), key=lambda e: (e.lineno, e.col_offset))


def resolve(op, offs, text):
    """One op -> (start, end, replacement) or raise ValueError(reason)."""
    kind = op[0]
    if kind == "const":
        _, node, new, _c = op
        a, b = offs.span(node)
        lit = text[a:b]
        m = re.fullmatch(r"(['\"])(.*)\1", lit, re.S)
        if not m or "\\" in lit or ast.literal_eval(lit) != node.value:
            raise ValueError("the string is not a plain single literal")
        return a, b, m.group(1) + new + m.group(1)
    if kind == "rename":
        _, call, new, _c = op
        f = call.func
        b = offs.at(f.end_lineno, f.end_col_offset)
        a = b - len(f.attr)
        if text[a:b] != f.attr:
            raise ValueError("cannot locate the method name")
        return a, b, new
    if kind == "kwto":
        _, kw, new, _c = op
        a, b = offs.span(kw)
        return a, b, new
    if kind == "delkw":
        _, call, kw, _c = op
        els = _elements(call)
        i = next(k for k, e in enumerate(els) if e is kw)
        ka, kb = offs.span(kw)
        if i < len(els) - 1:
            na = offs.at(els[i + 1].lineno, els[i + 1].col_offset)
            gap = text[kb:na]
            if not re.fullmatch(r"\s*,\s*", gap):
                raise ValueError("comment or unusual layout after the keyword")
            return ka, na, ""
        if i > 0:
            pb = offs.at(els[i - 1].end_lineno, els[i - 1].end_col_offset)
            gap = text[pb:ka]
            if not re.fullmatch(r"\s*,\s*", gap):
                raise ValueError("comment or unusual layout before the keyword")
            return pb, kb, ""
        tail = re.match(r"\s*,", text[kb:])
        return ka, kb + (tail.end() if tail else 0), ""
    raise ValueError("unknown op")


def plan_file(text, rel, min_conf_idx=0, disabled=(), only=()):
    """-> (edits, skips). Edits do not overlap; the result is checked to parse."""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError):
        return [], []
    hits = Analyzer(State()).run(tree)
    lines = text.split("\n")
    offs = Offsets(text)
    edits, skips = [], []
    taken = []
    for h in sorted(hits, key=lambda h: (h.line, h.col)):
        if h.rule in disabled or (only and h.rule not in only) or suppressed(lines, h.line, h.rule):
            continue
        if CONFIDENCE.index(h.confidence) < min_conf_idx:
            continue
        if not h.ops:
            if h.why:
                skips.append(Skip(rel, h.line, h.rule, h.why))
            continue
        need = max(CONFIDENCE.index(o[-1]) for o in h.ops)
        if CONFIDENCE.index(h.confidence) < need:
            skips.append(Skip(rel, h.line, h.rule, h.why or f"found with {h.confidence} confidence; the rewrite needs {CONFIDENCE[need]} (the receiver may not be pandas)"))
            continue
        if h.why:
            skips.append(Skip(rel, h.line, h.rule, h.why))
            continue
        try:
            parts = [resolve(o, offs, text) for o in h.ops]
        except (ValueError, StopIteration, UnicodeDecodeError) as e:
            skips.append(Skip(rel, h.line, h.rule, str(e) or "layout not understood"))
            continue
        if any(not (b <= a2 or b2 <= a) for a, b, _ in parts for a2, b2 in taken) or any(not (p[1] <= q[0] or q[1] <= p[0]) for i, p in enumerate(parts) for q in parts[i + 1:]):
            skips.append(Skip(rel, h.line, h.rule, "overlaps another rewrite; run --fix again"))
            continue
        for a, b, t in parts:
            taken.append((a, b))
            edits.append(Edit(a, b, t, h.line, h.rule, text[a:b], t))
    return edits, skips


def apply(text, edits):
    out = text
    for e in sorted(edits, key=lambda e: e.start, reverse=True):
        out = out[:e.start] + e.text + out[e.end:]
    return out


def fix_text(text, rel="snippet.py", min_conf="medium", disabled=(), only=()):
    """-> (new_text, edits, skips). If the rewritten file does not parse, edits are dropped one hit at a time."""
    edits, skips = plan_file(text, rel, CONFIDENCE.index(min_conf), disabled, only)
    new = apply(text, edits)
    try:
        ast.parse(new)
    except (SyntaxError, ValueError):
        good = []
        for e in edits:
            try:
                ast.parse(apply(text, good + [e]))
                good.append(e)
            except (SyntaxError, ValueError):
                skips.append(Skip(rel, e.line, e.rule, "the rewritten line would not parse"))
        edits, new = good, apply(text, good)
    return new, edits, skips


def fix_path(path, ignore=(), disabled=(), only=(), write=False, min_conf="medium"):
    import os
    edits_all, skips_all, diffs, changed, notebooks = [], [], [], 0, 0
    base = path if os.path.isdir(path) else os.path.dirname(path) or "."
    for p in iter_files(path, ignore):
        rel = os.path.relpath(p, base).replace(os.sep, "/") if os.path.isdir(path) else os.path.basename(p)
        if p.endswith(".ipynb"):
            notebooks += 1
            continue
        try:
            with open(p, encoding="utf-8", newline="") as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError):
            continue
        if "pandas" not in text:
            continue
        new, edits, skips = fix_text(text, rel, min_conf, disabled, only)
        skips_all += skips
        if not edits:
            continue
        changed += 1
        for e in edits:
            ln = text.count("\n", 0, e.start) + 1
            edits_all.append((rel, ln, e))
        diffs.append("".join(difflib.unified_diff(text.splitlines(True), new.splitlines(True), f"a/{rel}", f"b/{rel}")))
        if write:
            with open(p, "w", encoding="utf-8", newline="") as fh:
                fh.write(new)
    return edits_all, skips_all, diffs, changed, notebooks
