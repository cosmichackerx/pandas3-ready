"""AST analysis of one Python module (or the cells of one notebook, in order).

Design: a finding needs *evidence that the code is pandas*, and says how strong it is:
  high    the code is provably pandas: a module-qualified pandas API (pd.read_csv(...)), or a receiver this module assigned from pandas
  medium  pandas vocabulary on a receiver we cannot type (x.fillna(0, inplace=True), df-like names), in a file that imports pandas
  low     only the shape matches (a[b][c] = v); hidden unless --min-confidence low
Only files that import pandas are analysed. Nothing is imported or executed.
"""
from __future__ import annotations

import ast
import re

from .names import PANDAS_ATTRS

# functions in pandas that return DataFrame / Series / Index objects
FACTORIES = {"pandas." + n for n in (
    "DataFrame Series Index MultiIndex DatetimeIndex PeriodIndex TimedeltaIndex RangeIndex Categorical read_csv read_table read_excel read_json "
    "read_parquet read_sql read_sql_query read_sql_table read_pickle read_feather read_fwf read_clipboard read_orc read_stata read_sas read_spss read_xml "
    "concat merge merge_asof merge_ordered pivot pivot_table melt crosstab get_dummies to_datetime to_numeric to_timedelta cut qcut date_range bdate_range "
    "period_range timedelta_range json_normalize wide_to_long factorize".split())}
NONPD_ATTRS = {"values", "to_numpy", "array", "tolist", "to_list", "to_dict", "to_records", "shape", "size", "ndim", "dtype", "item", "iterrows", "itertuples",
               "items", "to_csv", "to_json", "to_string", "to_html", "to_latex", "to_parquet", "to_excel", "to_sql", "to_pickle", "to_markdown",
               "to_clipboard", "to_feather", "to_hdf", "to_xml", "to_gbq", "to_stata", "empty", "memory_usage", "info", "describe_option", "asi8", "codes"}
INDEXERS = {"loc", "iloc", "at", "iat"}
DF_NAME = re.compile(r"^(df|dfs|frame)\d*$|^df_|_df\d*$|_df_|^data_?frame", re.I)
NAN_TEXT = {"nan", "NaN", "None", "<NA>", "NAN"}

# ---- frequency aliases pandas 3 removed (checked on real pandas in tests/oracle/cases.py)
NEW_ALIAS = {"H": "h", "BH": "bh", "CBH": "cbh", "T": "min", "L": "ms", "U": "us", "N": "ns", "S": "s", "M": "ME", "Q": "QE", "Y": "YE", "A": "YE",
             "BM": "BME", "BQ": "BQE", "BA": "BYE", "BY": "BYE", "SM": "SME", "CBM": "CBME", "AS": "YS", "BAS": "BYS"}
ALIAS_RE = re.compile(r"^(\d*)(" + "|".join(sorted(NEW_ALIAS, key=len, reverse=True)) + r")(-[A-Z]{3})?$")
PERIOD_BAD = {"H", "T", "L", "U", "N", "S", "A", "BA"}  # for Period/period_range 'M', 'Q', 'Y' are still valid
PERIOD_FAMILY = {"M", "Q", "Y", "A"}  # on resample/asfreq these are also valid when the index is a PeriodIndex


def bad_alias(s: str, period: bool = False):
    m = ALIAS_RE.match(s)
    if not m:
        return None
    n, a, suffix = m.groups()
    if period and a not in PERIOD_BAD:
        return None
    new = NEW_ALIAS[a]
    if suffix and a in ("Q", "A", "Y", "BQ", "BA", "BY"):
        new = new + suffix
    elif suffix and a in ("AS", "BAS"):
        new = new + suffix
    return s, n + new, a


REMOVED_KW = {  # qualified pandas function -> {keyword: advice}
    "pandas.read_csv": {"delim_whitespace": "use sep=r\"\\s+\"", "date_parser": "use date_format", "keep_date_col": "removed, no replacement",
                        "verbose": "removed, no replacement", "infer_datetime_format": "removed, strict parsing is the default"},
    "pandas.read_table": {"delim_whitespace": "use sep=r\"\\s+\"", "date_parser": "use date_format", "keep_date_col": "removed, no replacement",
                          "verbose": "removed, no replacement", "infer_datetime_format": "removed, strict parsing is the default"},
    "pandas.to_datetime": {"infer_datetime_format": "removed, strict parsing is the default"},
}
REMOVED_KW_METHOD = {  # method name -> {keyword: advice}
    "fillna": {"method": "use .ffill() / .bfill()"},
    "replace": {"method": "removed, use ffill()/bfill() on the result", "limit": "removed together with method"},
    "groupby": {"axis": "transpose first (df.T.groupby(...))"},
    "rolling": {"axis": "transpose first (df.T.rolling(...))"},
    "expanding": {"axis": "transpose first"},
    "ewm": {"axis": "transpose first"},
    "resample": {"axis": "transpose first", "kind": "removed, convert the index with to_period()/to_timestamp()"},
    "apply": {"convert_dtype": "removed; call .infer_objects() on the result"},
    "align": {"method": "removed, fill after aligning", "limit": "removed", "fill_axis": "removed", "broadcast_axis": "removed"},
}
REMOVED_METHOD_ANY = {  # name -> advice (names that are pandas-only enough to flag on an untyped receiver)
    "applymap": "renamed to DataFrame.map (Styler.applymap -> Styler.map)",
}
REMOVED_METHOD_KNOWN = {  # only flagged when the receiver is provably pandas (numpy/torch/str have methods with these names)
    "bool": "removed; use bool(obj.iloc[0]) after checking len(obj) == 1",
    "swapaxes": "removed; use .transpose() or .T",
    "view": "Series.view removed; use .astype(...) (or numpy view on .to_numpy())",
    "ravel": "Series.ravel removed; use .to_numpy().ravel()",
    "format": "Index.format removed; use .astype(str) or .map(formatter)",
}
REMOVED_FUNC = {
    "pandas.value_counts": "pd.value_counts removed; use Series.value_counts()",
    "pandas.io.sql.execute": "removed; use the DBAPI/SQLAlchemy connection directly",
    "pandas.api.types.is_interval": "removed; use isinstance(obj, pd.Interval)",
    "pandas.api.types.is_period": "removed; use isinstance(obj, pd.Period)",
}
COPY_FUNCS = {"pandas.concat", "pandas.merge"}
COPY_METHODS = {"merge", "reindex", "rename"}  # astype only on a provably pandas receiver (numpy.astype also has copy=)
INPLACE_METHODS = {"fillna", "replace", "dropna", "drop", "rename", "sort_values", "sort_index", "ffill", "bfill", "interpolate", "clip", "where", "mask",
                   "drop_duplicates", "reset_index", "set_index", "rename_axis", "pad", "backfill"}
INT64 = {"int64", "i8", "<i8", "int", "np.int64", "numpy.int64"}


def is_const(n, types=(str,)):
    return isinstance(n, ast.Constant) and isinstance(n.value, types)


def call_kw(call: ast.Call, name: str):
    for k in call.keywords:
        if k.arg == name:
            return k.value
    return None


def const_num(n):
    """1e9 -> 1e9, 10**9 -> 1e9, 1_000_000_000 -> 1e9; None if not a plain number."""
    if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
        return float(n.value)
    if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Pow) and isinstance(n.left, ast.Constant) and isinstance(n.right, ast.Constant):
        try:
            return float(n.left.value) ** float(n.right.value)
        except Exception:
            return None
    return None


class Hit:
    __slots__ = ("rule", "severity", "confidence", "line", "col", "message")

    def __init__(self, rule, severity, confidence, line, col, message):
        self.rule, self.severity, self.confidence, self.line, self.col, self.message = rule, severity, confidence, line, col, message


class State:
    """Import aliases and inferred pandas variables; shared across the cells of a notebook."""

    def __init__(self):
        self.alias: dict = {}
        self.pandas_imported = False
        self.foreign: set = set()   # names bound by `import x` / `import x as y` of a non-pandas module
        self.known: dict = {}      # scope id -> {key: bool}
        self.parent: dict = {}     # scope id -> parent scope id
        self.assigns: dict = {}    # scope id -> {key: [assigned value nodes]}, accumulated over notebook cells
        self.counter = 0
        self.module_scope = None


def _target_key(t):
    if isinstance(t, ast.Name):
        return t.id
    if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id in ("self", "cls"):
        return "self." + t.attr
    return None


class Analyzer:
    def __init__(self, state: State):
        self.s = state
        self.hits: list = []
        self.scope = 0
        self._seen: set = set()
        self._guard: set = set()

    # ---------------------------------------------------------------- imports / names
    def collect_imports(self, tree):
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for a in n.names:
                    top = a.name.split(".")[0]
                    if top not in ("pandas", "numpy"):
                        self.s.foreign.add(a.asname or top)
                    if top in ("pandas", "numpy"):
                        if a.asname:
                            self.s.alias[a.asname] = a.name
                        else:
                            self.s.alias[top] = top
                        if top == "pandas":
                            self.s.pandas_imported = True
            elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
                top = n.module.split(".")[0]
                if top in ("pandas", "numpy"):
                    if top == "pandas":
                        self.s.pandas_imported = True
                    for a in n.names:
                        if a.name != "*":
                            self.s.alias[a.asname or a.name] = n.module + "." + a.name

    def resolve(self, n):
        """Canonical dotted name of a Name/Attribute chain whose root is an imported pandas/numpy alias, else None."""
        if isinstance(n, ast.Name):
            return self.s.alias.get(n.id)
        if isinstance(n, ast.Attribute):
            base = self.resolve(n.value)
            return base + "." + n.attr if base else None
        return None

    # ---------------------------------------------------------------- pandas-variable inference
    def build_scopes(self, tree):
        """Assign every function/module a scope id and find which names are only ever assigned pandas objects."""
        assigns = self.s.assigns
        if self.s.module_scope is None:
            self.s.module_scope = self.new_scope(None)
        scopes = {id(tree): self.s.module_scope}
        self._scope_of = {id(tree): self.s.module_scope}

        def walk(node, sc):
            for ch in ast.iter_child_nodes(node):
                if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                    ns = self.new_scope(sc)
                    self._scope_of[id(ch)] = ns
                    args = ch.args
                    for a in args.posonlyargs + args.args + args.kwonlyargs + ([args.vararg] if args.vararg else []) + ([args.kwarg] if args.kwarg else []):
                        ann = getattr(a, "annotation", None)
                        ok = ann is not None and self.annot_is_pandas(ann)
                        assigns.setdefault(ns, {}).setdefault(a.arg, []).append(("annot", True) if ok else None)
                    walk(ch, ns)
                    continue
                if isinstance(ch, ast.ClassDef):
                    ns = self.new_scope(sc)
                    self._scope_of[id(ch)] = ns
                    walk(ch, ns)
                    continue
                if isinstance(ch, ast.Assign):
                    for t in ch.targets:
                        k = _target_key(t)
                        if k:
                            assigns.setdefault(sc, {}).setdefault(k, []).append(ch.value)
                        else:
                            self.mark_unknown_targets(t, assigns, sc)
                elif isinstance(ch, ast.AnnAssign) and ch.target is not None:
                    k = _target_key(ch.target)
                    if k:
                        ok = self.annot_is_pandas(ch.annotation)
                        assigns.setdefault(sc, {}).setdefault(k, []).append(ch.value if ch.value is not None and not ok else (("annot", True) if ok else None))
                elif isinstance(ch, (ast.For, ast.AsyncFor)):
                    self.mark_unknown_targets(ch.target, assigns, sc)
                elif isinstance(ch, (ast.With, ast.AsyncWith)):
                    for it in ch.items:
                        if it.optional_vars is not None:
                            self.mark_unknown_targets(it.optional_vars, assigns, sc)
                elif isinstance(ch, ast.ExceptHandler) and ch.name:
                    assigns.setdefault(sc, {}).setdefault(ch.name, []).append(None)
                elif isinstance(ch, ast.NamedExpr):
                    assigns.setdefault(sc, {}).setdefault(ch.target.id, []).append(None)
                elif isinstance(ch, ast.AugAssign):
                    k = _target_key(ch.target)
                    if k:
                        assigns.setdefault(sc, {}).setdefault(k, []).append(ast.BinOp(left=ch.target, op=ch.op, right=ch.value))
                walk(ch, sc)

        walk(tree, scopes[id(tree)])
        for _ in range(4):
            for sc, d in assigns.items():
                kn = self.s.known.setdefault(sc, {})
                for k, vals in d.items():
                    kn[k] = all(self.value_is_pd(v, sc) for v in vals)

    def new_scope(self, parent):
        self.s.counter += 1
        sid = self.s.counter
        self.s.parent[sid] = parent
        self.s.known.setdefault(sid, {})
        return sid

    def mark_unknown_targets(self, t, assigns, sc):
        for n in ast.walk(t):
            k = _target_key(n) if isinstance(n, (ast.Name, ast.Attribute)) else None
            if k and isinstance(getattr(n, "ctx", None), ast.Store):
                assigns.setdefault(sc, {}).setdefault(k, []).append(None)

    def annot_is_pandas(self, ann):
        if isinstance(ann, ast.Constant) and isinstance(ann.value, str):
            return bool(re.search(r"\b(pd|pandas)\.(DataFrame|Series|Index)\b", ann.value))
        q = self.resolve(ann)
        if q in ("pandas.DataFrame", "pandas.Series", "pandas.Index"):
            return True
        return isinstance(ann, ast.Subscript) and self.annot_is_pandas(ann.value)

    def value_is_pd(self, v, sc):
        if v is None:
            return False
        if isinstance(v, tuple):
            return True
        return self.is_pd(v, sc)

    def lookup(self, key, sc):
        if key.startswith("self."):
            vals = [d[key] for d in self.s.known.values() if key in d]
            return bool(vals) and all(vals)
        while sc is not None:
            kn = self.s.known.get(sc, {})
            if key in kn:
                return kn[key]
            sc = self.s.parent.get(sc)
        return False

    def is_pd(self, n, sc=None) -> bool:
        sc = self.scope if sc is None else sc
        if isinstance(n, ast.Name):
            return self.lookup(n.id, sc)
        if isinstance(n, ast.Attribute):
            k = _target_key(n)
            if k and k.startswith("self.") and self.lookup(k, sc):
                return True
            if n.attr in NONPD_ATTRS:
                return False
            return self.is_pd(n.value, sc)
        if isinstance(n, ast.Subscript):
            return self.is_pd(n.value, sc)
        if isinstance(n, ast.Call):
            q = self.resolve(n.func)
            if q is not None:
                return q in FACTORIES
            if isinstance(n.func, ast.Attribute):
                if n.func.attr in NONPD_ATTRS:
                    return False
                return self.is_pd(n.func.value, sc)
            return False
        if isinstance(n, ast.BinOp):
            return self.is_pd(n.left, sc) or self.is_pd(n.right, sc)
        if isinstance(n, ast.UnaryOp):
            return self.is_pd(n.operand, sc)
        if isinstance(n, ast.Compare):
            return self.is_pd(n.left, sc) or any(self.is_pd(c, sc) for c in n.comparators)
        if isinstance(n, ast.IfExp):
            return self.is_pd(n.body, sc) and self.is_pd(n.orelse, sc)
        return False

    def is_foreign_module_call(self, recv) -> bool:
        r = self.root(recv) if recv is not None else None
        return isinstance(r, ast.Name) and r.id in self.s.foreign and not self.lookup(r.id, self.scope)

    def is_dictlike(self, n) -> bool:
        """A name only ever assigned a dict (literal, comprehension, dict(), defaultdict()): d['k'] is a dict lookup, not a column selection."""
        if not isinstance(n, ast.Name):
            return False
        sc = self.scope
        while sc is not None:
            vals = self.s.assigns.get(sc, {}).get(n.id)
            if vals:
                return all(isinstance(v, (ast.Dict, ast.DictComp)) or (isinstance(v, ast.Call) and isinstance(v.func, (ast.Name, ast.Attribute))
                                                                        and (v.func.id if isinstance(v.func, ast.Name) else v.func.attr) in ("dict", "defaultdict", "OrderedDict"))
                           for v in vals)
            sc = self.s.parent.get(sc)
        return False

    def root(self, n):
        while True:
            if isinstance(n, (ast.Attribute, ast.Subscript)):
                n = n.value
            elif isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
                n = n.func.value
            else:
                return n

    def evidence(self, n) -> str:
        """known | hint | unknown"""
        if self.is_pd(n):
            return "known"
        r = self.root(n)
        k = _target_key(r) if isinstance(r, (ast.Name, ast.Attribute)) else None
        if k and DF_NAME.search(k.split(".")[-1]):
            return "hint"
        return "unknown"

    # ---------------------------------------------------------------- reporting
    def add(self, rule, node, message, confidence, severity=None):
        from .rules import RULES
        key = (rule, node.lineno, node.col_offset)
        if key in self._seen:
            return
        self._seen.add(key)
        self.hits.append(Hit(rule, severity or RULES[rule].severity, confidence, node.lineno, node.col_offset + 1, message))

    # ---------------------------------------------------------------- driver
    def run(self, tree):
        self.collect_imports(tree)
        if not self.s.pandas_imported:
            return []
        self._seen = set()
        self.build_scopes(tree)
        for n in ast.walk(tree):
            for c in ast.iter_child_nodes(n):
                c._parent = n  # type: ignore[attr-defined]
        self.visit(tree, self._scope_of[id(tree)])
        return self.hits

    def visit(self, node, sc):
        if id(node) in self._scope_of:
            sc = self._scope_of[id(node)]
        self.scope = sc
        m = getattr(self, "v_" + type(node).__name__, None)
        if m:
            m(node)
        for ch in ast.iter_child_nodes(node):
            self.visit(ch, sc)

    # ---------------------------------------------------------------- rules: statements
    def v_Assign(self, n):
        for t in n.targets:
            self.check_target(t, n)
        self.check_option_assign(n)

    def v_AugAssign(self, n):
        self.check_target(n.target, n)

    def v_AnnAssign(self, n):
        if n.value is not None:
            self.check_target(n.target, n)

    def check_option_assign(self, n):
        for t in n.targets:
            q = self.resolve(t)
            if q == "pandas.options.mode.use_inf_as_na":
                self.add("removed-option", n, "pd.options.mode.use_inf_as_na no longer exists in pandas 3 (AttributeError/OptionError); replace inf with NaN before", "high")
            if q == "pandas.options.mode.copy_on_write":
                self.add("cow-option", n, "pd.options.mode.copy_on_write: Copy-on-Write is always on in pandas 3; the option has no effect and warns", "high")

    def check_target(self, t, stmt):
        if not isinstance(t, ast.Subscript):
            if isinstance(t, ast.Attribute):
                self.chained_attr_target(t, stmt)
            return
        # readonly-array-write: df[col].values[i] = v / df.to_numpy()[i] = v
        v = t.value
        if isinstance(v, ast.Attribute) and v.attr == "values" or (isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute) and v.func.attr == "to_numpy"):
            recv = v.value if isinstance(v, ast.Attribute) else v.func.value
            if isinstance(v, ast.Call) and (call_kw(v, "copy") is not None):
                return
            ev = self.evidence(recv)
            if ev == "known":
                self.add("readonly-array-write", stmt, ".values / .to_numpy() is read-only in pandas 3: this raises ValueError (or writes to a copy when dtypes are mixed)", "high")
            elif ev == "hint":
                self.add("readonly-array-write", stmt, ".values / .to_numpy() is read-only in pandas 3: this raises ValueError (or writes to a copy when dtypes are mixed)", "medium")
            return
        # chained-assignment: two indexing steps on the left
        steps, node, indexer = 0, t, False
        while True:
            if isinstance(node, ast.Subscript):
                steps += 1
                node = node.value
            elif isinstance(node, ast.Attribute) and node.attr in INDEXERS:
                indexer = True
                node = node.value
            else:
                break
        col_attr = False
        if isinstance(node, ast.Attribute) and node.attr not in PANDAS_ATTRS and self.is_pd(node.value):
            steps += 1
            col_attr = True
            node = node.value
        if self.is_dictlike(node):
            steps -= 1   # d['k'] on a dict of DataFrames is a dict lookup, the DataFrame is not copied
        if steps < 2:
            return
        ev = self.evidence(t.value if not col_attr else node)
        msg = "chained assignment: the first indexing step returns a copy in pandas 3, so this write never reaches the DataFrame; index once with .loc[rows, col]"
        if ev == "known":
            self.add("chained-assignment", stmt, msg, "high")
        elif indexer or ev == "hint":
            self.add("chained-assignment", stmt, msg, "medium")
        else:
            self.add("chained-assignment", stmt, msg, "low")

    def chained_attr_target(self, t, stmt):
        # df[mask].col = v  /  df.loc[...].col = v  (attribute write on an indexing result)
        v = t.value
        if isinstance(v, ast.Subscript) and t.attr not in PANDAS_ATTRS and self.is_pd(v):
            ev = self.evidence(v)
            if ev == "known":
                self.add("chained-assignment", stmt, "chained assignment: df[...].col = v writes to a copy in pandas 3; use df.loc[rows, col] = v", "high")

    # ---------------------------------------------------------------- rules: comparisons / arithmetic
    def v_BoolOp(self, n):
        def string_aware(x):
            for y in ast.walk(x):
                if isinstance(y, ast.Constant) and y.value in ("string", "str"):
                    return True
                if isinstance(y, (ast.Name, ast.Attribute)) and (getattr(y, "id", None) or getattr(y, "attr", None)) in ("is_string_dtype", "StringDtype"):
                    return True
            return False
        if any(string_aware(v) for v in n.values):
            for v in n.values:
                for y in ast.walk(v):
                    if isinstance(y, ast.Compare):
                        self._guard.add(id(y))

    def v_Compare(self, n):
        left, ops, comps = n.left, n.ops, n.comparators
        for op, right in zip(ops, comps):
            for a, b in ((left, right), (right, left)):
                self.cmp_object_dtype(n, a, b, op)
                self.cmp_nan_text(n, a, b)
            left = right

    def is_object_marker(self, b):
        if isinstance(b, ast.Name) and b.id == "object":
            return True
        if is_const(b) and b.value in ("O", "object"):
            return True
        return self.resolve(b) in ("numpy.object_", "numpy.object")

    def cmp_object_dtype(self, n, a, b, op):
        if not isinstance(op, (ast.Eq, ast.NotEq, ast.Is, ast.IsNot, ast.In)):
            return
        if not (isinstance(a, ast.Attribute) and a.attr in ("dtype", "dtypes")):
            return
        if isinstance(op, ast.In):
            if not (isinstance(b, (ast.Tuple, ast.List, ast.Set)) and any(self.is_object_marker(e) for e in b.elts)):
                return
        elif not self.is_object_marker(b):
            return
        if id(n) in self._guard:
            return   # the same condition already looks for the string dtype
        ev = self.evidence(a.value)
        conf = "high" if ev == "known" else "medium" if ev == "hint" else "low"
        self.add("object-dtype-check", n, f"`{a.attr} == object` is False for text columns in pandas 3 (they use the str dtype)", conf)

    def cmp_nan_text(self, n, a, b):
        if is_const(b) and b.value in NAN_TEXT and self.is_astype_str(a):
            self.astype_str_hit(n, a)

    def is_astype_str(self, n):
        # <expr>.astype(str) possibly followed by .str.strip()/.str.lower()/... chain handled by caller
        while isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in ("strip", "lower", "upper") and self.through_str(n.func.value):
            n = n.func.value.value  # x.str.strip() -> x
        return isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "astype" and bool(n.args) and (
            (isinstance(n.args[0], ast.Name) and n.args[0].id == "str") or (is_const(n.args[0]) and n.args[0].value == "str"))

    def through_str(self, n):
        return isinstance(n, ast.Attribute) and n.attr == "str"

    def astype_str_hit(self, node, call):
        c = call
        while isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.func.attr != "astype":
            c = c.func.value.value
        recv = c.func.value if isinstance(c, ast.Call) else call
        ev = self.evidence(recv)
        self.add("astype-str-na-literal", node, "astype(str) turns missing values into 'nan'/'None' in pandas 2 and keeps them missing in pandas 3, so this comparison/replacement never matches there",
                 "high" if ev == "known" else "medium")

    def v_BinOp(self, n):
        if not isinstance(n.op, (ast.Div, ast.FloorDiv)):
            return
        d = const_num(n.right)
        if d not in (1e9, 1e6):
            return
        L = n.left
        if isinstance(L, ast.Attribute) and L.attr == "asi8":
            ev = self.evidence(L.value)
            self.add("datetime-ns-assumption", n, "`.asi8` counts the index's own unit (ns in pandas 2, possibly us or s in pandas 3), so dividing by 1e9 is wrong in pandas 3", "high" if ev == "known" else "medium")
            return
        if isinstance(L, ast.Call) and isinstance(L.func, ast.Attribute) and L.func.attr in ("astype", "view") and L.args:
            a = L.args[0]
            name = a.value if is_const(a) else (a.id if isinstance(a, ast.Name) else self.resolve(a) or "")
            if str(name) in INT64:
                ev = self.evidence(L.func.value)
                dt = self.has_datetime_evidence(L.func.value)
                conf = "high" if (ev == "known" and dt == 2) else "medium" if dt else "low"
                self.add("datetime-ns-assumption", n, "datetime cast to int64 and divided by 1e9: pandas 3 may store seconds, ms or us instead of ns, so the result can be off by 1000 or more", conf)

    def assigned_values(self, name):
        sc = self.scope
        while sc is not None:
            vals = self.s.assigns.get(sc, {}).get(name)
            if vals:
                return [v for v in vals if isinstance(v, ast.AST)]
            sc = self.s.parent.get(sc)
        return []

    def has_datetime_evidence(self, n, depth=0) -> int:
        """2 = the expression visibly involves datetimes, 1 = only a column name like created_at / timestamp, 0 = nothing."""
        best = 0
        if depth < 2:
            for x in ast.walk(n):
                if isinstance(x, ast.Name):
                    for v in self.assigned_values(x.id):
                        best = max(best, self.has_datetime_evidence(v, depth + 1))
        for x in ast.walk(n):
            if isinstance(x, ast.Attribute) and x.attr in ("dt", "index"):
                best = 2
            elif isinstance(x, ast.Call) and self.resolve(x.func) in ("pandas.to_datetime", "pandas.date_range", "pandas.DatetimeIndex"):
                best = 2
            elif isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute) and x.func.attr == "astype" and x.args and is_const(x.args[0]) and "datetime64" in str(x.args[0].value):
                best = 2
            elif isinstance(x, ast.Subscript) and is_const(x.slice) and re.search(r"time|date|stamp|^ts$|_at$|_dt$", str(x.slice.value), re.I):
                best = max(best, 1)
        return best

    # ---------------------------------------------------------------- rules: calls
    def v_Call(self, n):
        f = n.func
        q = self.resolve(f)
        name = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else None
        recv = f.value if isinstance(f, ast.Attribute) else None
        if name is None:
            return
        method = recv is not None and q is None
        ev = self.evidence(recv) if method else "known"
        hi = "high" if ev == "known" else "medium"
        self.chained_inplace(n, name, recv, method)
        self.freq_aliases(n, q, name, recv, ev)
        self.timedelta_units(n, q)
        self.removed_things(n, q, name, recv, method, ev, hi)
        self.errors_ignore(n, q, name)
        self.raw_reader(n, q)
        self.options(n, q)
        self.include_groups(n, name)
        self.stack_args(n, name, method, ev)
        self.pct_change(n, name, method, ev)
        self.select_dtypes(n, name, method, ev)
        self.is_object_dtype_call(n, q)
        self.astype_str_call(n, name, recv)
        self.copy_kw(n, q, name, method, ev)

    def chained_inplace(self, n, name, recv, method):
        if not method or name not in INPLACE_METHODS:
            return
        ip = call_kw(n, "inplace")
        if not (isinstance(ip, ast.Constant) and ip.value is True):
            return
        sel = recv
        if isinstance(sel, ast.Subscript):
            if self.is_dictlike(sel.value):
                return   # d['k'].fillna(..., inplace=True) on a dict of DataFrames changes the DataFrame itself
            ev = self.evidence(sel)
            if ev != "known" and isinstance(sel.slice, ast.Constant) and isinstance(sel.slice.value, int) and not isinstance(sel.slice.value, bool):
                return   # dfs[0].rename(..., inplace=True): positional index on a list of frames, not a column of a frame
        elif isinstance(sel, ast.Attribute) and sel.attr not in PANDAS_ATTRS and self.is_pd(sel.value) and sel.attr not in INDEXERS:
            ev = "known"   # df.col.fillna(0, inplace=True)
        else:
            return
        self.add("chained-inplace", n, f"`.{name}(..., inplace=True)` on a column/selection operates on a temporary copy in pandas 3: the DataFrame is left unchanged (no error, only a warning)",
                 "high" if ev == "known" else "medium")

    def freq_aliases(self, n, q, name, recv, ev):
        specs = []   # (node, period_context)
        if q in ("pandas.date_range", "pandas.bdate_range", "pandas.timedelta_range"):
            node = call_kw(n, "freq") or (n.args[3] if len(n.args) > 3 else None)
            specs.append((node, False, "high"))
        elif q in ("pandas.DatetimeIndex", "pandas.Grouper", "pandas.TimedeltaIndex"):
            specs.append((call_kw(n, "freq"), False, "high"))
        elif q in ("pandas.period_range", "pandas.PeriodIndex", "pandas.Period"):
            node = call_kw(n, "freq") or (n.args[2] if q == "pandas.period_range" and len(n.args) > 2 else n.args[1] if q == "pandas.Period" and len(n.args) > 1 else None)
            specs.append((node, True, "high"))
        elif q is None and recv is not None:
            hi = "high" if ev == "known" else "medium"
            if name in ("resample", "asfreq"):
                specs.append((call_kw(n, "rule") or call_kw(n, "freq") or (n.args[0] if n.args else None), False, hi))
            elif name == "shift":
                specs.append((call_kw(n, "freq"), False, hi))
            elif name in ("floor", "ceil", "round"):
                specs.append((call_kw(n, "freq") or (n.args[0] if n.args else None), False, hi))
            elif name == "to_period":
                specs.append((call_kw(n, "freq") or (n.args[0] if n.args else None), True, hi))
        for node, period, conf in specs:
            if node is not None and is_const(node):
                r = bad_alias(node.value, period)
                if r:
                    s, new, a = r
                    if a in PERIOD_FAMILY and name in ("resample", "asfreq") and q is None:
                        conf = "medium"   # valid when the index is a PeriodIndex
                    self.add("removed-offset-alias", node, f"frequency alias '{s}' was removed in pandas 3 (ValueError); use '{new}'", conf)

    def timedelta_units(self, n, q):
        if q not in ("pandas.Timedelta", "pandas.to_timedelta"):
            return
        node = call_kw(n, "unit") or (n.args[1] if len(n.args) > 1 else None)
        if node is not None and is_const(node):
            if node.value in ("T", "L", "U", "N"):
                self.add("removed-timedelta-unit", node, f"Timedelta unit '{node.value}' was removed in pandas 3 (ValueError); use '{ {'T': 'min', 'L': 'ms', 'U': 'us', 'N': 'ns'}[node.value] }'", "high")
            elif node.value == "H":
                self.add("removed-timedelta-unit", node, "Timedelta unit 'H' is deprecated in pandas 3 (still works, warns); use 'h'", "high", severity="note")

    def removed_things(self, n, q, name, recv, method, ev, hi):
        if q in REMOVED_FUNC:
            self.add("removed-method", n, REMOVED_FUNC[q], "high")
        if q in REMOVED_KW:
            for k, adv in REMOVED_KW[q].items():
                if call_kw(n, k) is not None:
                    self.add("removed-keyword", n, f"{q.split('.')[-1]}({k}=...) was removed in pandas 3: {adv}", "high")
        if method and self.is_foreign_module_call(recv):
            return   # scipy.signal.resample(x, n, axis=-1), sklearn.utils.resample(...): a function of another library
        if method:
            if name in REMOVED_METHOD_ANY:
                self.add("removed-method", n, f".{name}(): {REMOVED_METHOD_ANY[name]}", hi)
            if name in REMOVED_METHOD_KNOWN and ev == "known" and not n.keywords:
                self.add("removed-method", n, f".{name}(): {REMOVED_METHOD_KNOWN[name]}", "high")
            if name in ("first", "last") and n.args and is_const(n.args[0]) and re.match(r"^\d+[A-Za-z]+$", n.args[0].value):
                self.add("removed-method", n, f".{name}('{n.args[0].value}') was removed in pandas 3; slice by label or position instead", hi)
            if name in REMOVED_KW_METHOD:
                for k, adv in REMOVED_KW_METHOD[name].items():
                    if call_kw(n, k) is not None:
                        conf = hi
                        if name in ("groupby", "rolling", "expanding", "ewm", "resample", "align", "apply") and ev == "unknown" and k in ("axis",):
                            conf = "medium"
                        self.add("removed-keyword", n, f".{name}({k}=...) was removed in pandas 3: {adv}", conf)

    def errors_ignore(self, n, q, name):
        targets = {"pandas.to_datetime", "pandas.to_numeric", "pandas.to_timedelta"}
        e = call_kw(n, "errors")
        if e is None or not (is_const(e) and e.value == "ignore"):
            return
        if q in targets:
            self.add("errors-ignore", n, f"{q.split('.')[-1]}(errors='ignore') was removed in pandas 3; catch the error or use errors='coerce'", "high")
        elif name == "apply" and n.args and self.resolve(n.args[0]) in targets:
            self.add("errors-ignore", n, f"apply({self.resolve(n.args[0]).split('.')[-1]}, errors='ignore') was removed in pandas 3; use errors='coerce'", "high")

    def raw_reader(self, n, q):
        if q in ("pandas.read_json", "pandas.read_html", "pandas.read_xml") and n.args and is_const(n.args[0]):
            s = n.args[0].value.lstrip()
            if s[:1] in ("{", "[", "<"):
                self.add("raw-string-reader", n, f"{q.split('.')[-1]}() with literal text: pandas 3 treats a str as a path or URL; wrap it in io.StringIO", "high")

    def options(self, n, q):
        if q in ("pandas.set_option", "pandas.option_context", "pandas.get_option", "pandas.reset_option") and n.args and is_const(n.args[0]):
            o = n.args[0].value
            if o == "mode.use_inf_as_na":
                self.add("removed-option", n, "mode.use_inf_as_na was removed in pandas 3 (OptionError); replace inf with NaN before", "high")
            if o == "mode.copy_on_write":
                self.add("cow-option", n, "mode.copy_on_write: Copy-on-Write is always on in pandas 3; the option has no effect and warns", "high")

    def include_groups(self, n, name):
        v = call_kw(n, "include_groups")
        if name == "apply" and isinstance(v, ast.Constant) and v.value is True:
            self.add("include-groups", n, "apply(include_groups=True) raises ValueError in pandas 3", "high")

    def stack_args(self, n, name, method, ev):
        if not method or name != "stack":
            return
        for k in ("dropna", "sort"):
            if call_kw(n, k) is not None:
                self.add("stack-legacy-args", n, f"stack({k}=...) raises ValueError in pandas 3 (new implementation)", "high" if ev == "known" else "medium")
        fs = call_kw(n, "future_stack")
        if isinstance(fs, ast.Constant) and fs.value is False:
            self.add("stack-legacy-args", n, "stack(future_stack=False) is deprecated in pandas 3", "high" if ev == "known" else "medium", severity="note")

    def pct_change(self, n, name, method, ev):
        if not method or name != "pct_change":
            return
        fm, lim = call_kw(n, "fill_method"), call_kw(n, "limit")
        bad = (fm is not None and not (isinstance(fm, ast.Constant) and fm.value is None)) or lim is not None
        if bad:
            self.add("pct-change-fill", n, "pct_change(fill_method=..., limit=...) raises in pandas 3: fill_method must be None; call ffill() first", "high" if ev == "known" else "medium")

    def select_dtypes(self, n, name, method, ev):
        if not method or name != "select_dtypes":
            return
        inc = call_kw(n, "include") or (n.args[0] if n.args else None)
        if inc is None:
            return
        elts = inc.elts if isinstance(inc, (ast.List, ast.Tuple, ast.Set)) else [inc]
        covers_text = any((is_const(e) and e.value in ("string", "str")) or self.resolve(e) in ("pandas.StringDtype",) for e in elts)
        if any(self.is_object_marker(e) for e in elts) and not covers_text:
            self.add("select-dtypes-object", n, "select_dtypes(include=object) still selects text columns in pandas 3 but warns that it will stop", "high" if ev == "known" else "medium")

    def is_object_dtype_call(self, n, q):
        if q == "pandas.api.types.is_object_dtype":
            self.add("object-dtype-check", n, "is_object_dtype() is False for text (str dtype) in pandas 3", "high")

    def astype_str_call(self, n, name, recv):
        # <astype(str) chain>.replace('nan', ...), .str.replace('nan', ...), .isin([... 'nan' ...]), .eq('nan'), .ne('nan'), .mask(...)
        if name not in ("replace", "isin", "eq", "ne", "mask", "where", "contains", "startswith", "endswith") or recv is None:
            return
        base = recv
        if isinstance(base, ast.Attribute) and base.attr == "str":
            base = base.value
        if not self.is_astype_str(base):
            return
        lits = [a for a in ast.walk(ast.Tuple(elts=n.args, ctx=ast.Load())) if is_const(a) and a.value in NAN_TEXT]
        if lits:
            self.astype_str_hit(n, base)

    def copy_kw(self, n, q, name, method, ev):
        if call_kw(n, "copy") is None:
            return
        if q in COPY_FUNCS:
            self.add("copy-keyword", n, f"{q.split('.')[-1]}(copy=...) is deprecated in pandas 3 and has no effect", "high")
        elif method and name in COPY_METHODS:
            self.add("copy-keyword", n, f".{name}(copy=...) is deprecated in pandas 3 and has no effect", "high" if ev == "known" else "medium")
        elif method and name == "astype" and ev == "known":
            self.add("copy-keyword", n, ".astype(copy=...) is deprecated in pandas 3 and has no effect", "high")
