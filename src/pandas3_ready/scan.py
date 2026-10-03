"""File discovery, notebook reading, ignore comments, and the Result type."""
from __future__ import annotations

import ast
import fnmatch
import json
import os
import re
from dataclasses import dataclass, field

from .analyze import Analyzer, State
from .rules import CONFIDENCE, RULES

SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", ".venv", "venv", "env", ".tox", ".nox", "__pycache__", "site-packages", "build", "dist", ".eggs",
             ".mypy_cache", ".ruff_cache", ".pytest_cache", ".ipynb_checkpoints"}
MAX_BYTES = 2_000_000
IGNORE_RE = re.compile(r"#\s*pandas3-ready:\s*ignore(?:\s*\[([^\]]*)\])?")


@dataclass
class Finding:
    rule: str
    severity: str
    confidence: str
    file: str
    line: int
    col: int
    message: str
    snippet: str = ""
    cell: int | None = None


@dataclass
class Result:
    findings: list = field(default_factory=list)
    files_scanned: int = 0
    pandas_files: int = 0
    unparsed: int = 0
    hidden_low: int = 0
    pr: dict | None = None


def kind_of(name: str, path: str = ""):
    if name.endswith(".py") or name.endswith(".pyw"):
        return "py"
    if name.endswith(".ipynb"):
        return "ipynb"
    return None


def iter_files(root: str, ignore=()):
    if os.path.isfile(root):
        if kind_of(os.path.basename(root)):
            yield root
        return
    for d, dirs, files in os.walk(root):
        dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS and not x.endswith(".egg-info"))
        for f in sorted(files):
            p = os.path.join(d, f)
            rel = os.path.relpath(p, root).replace(os.sep, "/")
            if kind_of(f) and not any(fnmatch.fnmatch(rel, g) or fnmatch.fnmatch(f, g) for g in ignore):
                yield p


def suppressed(lines, lineno, rule) -> bool:
    for ln in (lineno, lineno - 1):
        if 1 <= ln <= len(lines):
            m = IGNORE_RE.search(lines[ln - 1])
            if m and (ln == lineno or lines[ln - 1].strip().startswith("#")):
                if m.group(1) is None or rule in [x.strip() for x in m.group(1).split(",")]:
                    return True
    return False


def clean_cell(src: str):
    """Make an IPython cell parseable: drop magics and shell escapes, keep line numbers."""
    lines = src.split("\n")
    if lines and lines[0].lstrip().startswith("%%") and not re.match(r"\s*%%(time|timeit|capture|prun|script python)\b", lines[0]):
        return None
    out = []
    for ln in lines:
        s = ln.lstrip()
        ind = ln[:len(ln) - len(s)]
        if s.startswith(("%", "!")) or (s.startswith("?")):
            out.append(ind + "pass")
        elif s.endswith("?") and re.match(r"^[\w.]+\?{1,2}$", s):
            out.append(ind + "pass")
        else:
            out.append(ln)
    return "\n".join(out)


def notebook_sources(text: str):
    """[(cell_number, source, {source_line: file_line})] for code cells."""
    nb = json.loads(text)
    raw = text.split("\n")
    cells = nb.get("cells") if isinstance(nb.get("cells"), list) else [c for ws in nb.get("worksheets", []) for c in ws.get("cells", [])]
    out, ptr, num = [], 0, 0
    for c in cells or []:
        if c.get("cell_type") != "code":
            continue
        num += 1
        src = c.get("source", c.get("input", ""))
        lines = src if isinstance(src, list) else src.split("\n") if isinstance(src, str) else []
        text_src = "".join(lines) if isinstance(src, list) else src
        mapping = {}
        start = ptr
        for i, ln in enumerate(text_src.split("\n"), 1):
            key = json.dumps(ln + ("\n" if i < len(text_src.split("\n")) else ""))
            j = ptr
            while j < len(raw) and key not in raw[j]:
                j += 1
            if j < len(raw):
                mapping[i] = j + 1
                ptr = j + 1
            else:
                mapping[i] = mapping.get(i - 1, start + 1)
        out.append((num, text_src, mapping))
    return out


def scan_file(path: str, rel: str, min_conf: str, res: Result, disabled=(), only=()):
    try:
        if os.path.getsize(path) > MAX_BYTES:
            return
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return
    res.files_scanned += 1
    if "pandas" not in text:
        return
    state = State()
    found = []   # (hit, source_lines, line_map, cell)
    if path.endswith(".ipynb"):
        try:
            cells = notebook_sources(text)
        except (ValueError, AttributeError):
            res.unparsed += 1
            return
        for num, src, mapping in cells:
            cleaned = clean_cell(src)
            if cleaned is None:
                continue
            try:
                tree = ast.parse(cleaned)
            except (SyntaxError, ValueError, RecursionError):
                res.unparsed += 1
                continue
            for h in Analyzer(state).run(tree):
                found.append((h, src.split("\n"), mapping, num))
    else:
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError, RecursionError):
            res.unparsed += 1
            return
        for h in Analyzer(state).run(tree):
            found.append((h, text.split("\n"), None, None))
    if state.pandas_imported:
        res.pandas_files += 1
    floor = CONFIDENCE.index(min_conf)
    for h, lines, mapping, cell in found:
        if h.rule in disabled or (only and h.rule not in only):
            continue
        if suppressed(lines, h.line, h.rule):
            continue
        if CONFIDENCE.index(h.confidence) < floor:
            res.hidden_low += 1
            continue
        snippet = lines[h.line - 1].strip()[:200] if 1 <= h.line <= len(lines) else ""
        line = mapping[h.line] if mapping else h.line
        res.findings.append(Finding(h.rule, h.severity, h.confidence, rel, line, h.col, h.message, snippet, cell))


def scan(path: str, ignore=(), disabled=(), only=(), min_conf: str = "medium") -> Result:
    res = Result()
    base = path if os.path.isdir(path) else os.path.dirname(path) or "."
    for p in iter_files(path, ignore):
        rel = os.path.relpath(p, base).replace(os.sep, "/") if os.path.isdir(path) else os.path.basename(p)
        scan_file(p, rel, min_conf, res, disabled, only)
    res.findings.sort(key=lambda f: (f.file, f.line, f.col, f.rule))
    return res


def scan_text(text: str, min_conf: str = "medium", name: str = "snippet.py") -> Result:
    """Scan source text directly (used by the tests and the oracle)."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, name)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        return scan(p, min_conf=min_conf)
