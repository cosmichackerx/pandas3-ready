"""Precision tables from a scan json, the sample json and labels.json.

Precision = true / (true + false); 'unclear' items are left out of it and shown on their own (worst case: unclear counted as false).
Wilson 95% intervals. Also shown: the same excluding findings in vendored copies of pandas' own sources/tests.

    python study/tabulate.py SCAN.json SAMPLE.json A|B
"""
import json
import math
import os
import re
import sys
from collections import defaultdict

scan, sample, which = sys.argv[1:4]
L = json.load(open(os.path.join(os.path.dirname(__file__), "labels.json")))
fp = {int(k) for k in L[which]["fp"]}
unc = {int(k) for k in L[which]["unclear"]}
VENDORED = re.compile(r"(?:^|/)pandas(?:-[\w.]+)?/(?:tests|core|io|_libs|util)/|test_chaining_and_caching|/koalas/")
data, items = json.load(open(scan)), json.load(open(sample))


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0, c - h), min(1, c + h))


def stats(ids):
    bad = sum(1 for i in ids if i in fp)
    u = sum(1 for i in ids if i in unc)
    good = len(ids) - bad - u
    return good, bad, u


def prec(good, bad, u):
    n = good + bad
    if not n:
        return "no sample"
    lo, hi = wilson(good, n)
    worst = good / (n + u)
    return f"{good / n:.0%} ({lo:.0%} to {hi:.0%}); worst case {worst:.0%}"


tot = defaultdict(int)
for f in data["findings"]:
    tot[(f["rule"], f["confidence"])] += 1
vend_all = sum(1 for f in data["findings"] if VENDORED.search(f["repo"] + "/" + f["file"]))
print(f"Findings in vendored copies of pandas' own files: {vend_all} of {len(data['findings'])}\n")
print("### Per confidence level\n\n| Confidence | Findings | Repos | Hand-checked | True | False | Unclear | Precision (95% Wilson) | Without vendored pandas files |\n|---|---:|---:|---:|---:|---:|---:|---|---|")
for conf in ("high", "medium", "low"):
    fs = [f for f in data["findings"] if f["confidence"] == conf]
    ids = [i for i, f in enumerate(items) if f["confidence"] == conf]
    nv = [i for i in ids if not VENDORED.search(items[i]["repo"] + "/" + items[i]["file"])]
    g, b, u = stats(ids)
    g2, b2, u2 = stats(nv)
    print(f"| {conf} | {len(fs)} | {len({f['repo'] for f in fs})} | {len(ids)} | {g} | {b} | {u} | {prec(g, b, u)} | {prec(g2, b2, u2)} (n={len(nv)}) |")
ids = list(range(len(items)))
g, b, u = stats(ids)
print(f"| all | {len(data['findings'])} | {len({f['repo'] for f in data['findings']})} | {len(ids)} | {g} | {b} | {u} | {prec(g, b, u)} | |")
print("\n### Per rule (confidence levels pooled in the sample; low-confidence findings are hidden by default)\n\n| Rule | Findings | Repos | Hand-checked | True | False | Unclear | Precision, high and medium only |\n|---|---:|---:|---:|---:|---:|---:|---|")
for r in sorted({f["rule"] for f in data["findings"]}):
    fs = [f for f in data["findings"] if f["rule"] == r]
    ids = [i for i, f in enumerate(items) if f["rule"] == r]
    hm = [i for i in ids if items[i]["confidence"] != "low"]
    g, b, u = stats(ids)
    print(f"| `{r}` | {len(fs)} | {len({f['repo'] for f in fs})} | {len(ids)} | {g} | {b} | {u} | {prec(*stats(hm))} (n={len(hm)}) |")
print("\n### Per rule and confidence\n\n| Rule | Confidence | Findings | Hand-checked | False | Unclear | Precision |\n|---|---|---:|---:|---:|---:|---|")
for (r, c) in sorted(tot):
    ids = [i for i, f in enumerate(items) if (f["rule"], f["confidence"]) == (r, c)]
    g, b, u = stats(ids)
    print(f"| `{r}` | {c} | {tot[(r, c)]} | {len(ids)} | {b} | {u} | {prec(g, b, u)} |")
