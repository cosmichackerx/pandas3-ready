"""Draw the stratified random sample (rule x confidence, fixed seed, at most --per-repo findings per repo and stratum) that gets labelled by hand,
and print each finding with its surrounding lines.

    python study/sample.py SCAN.json FILES_DIR OUT.md [--seed 20261004] [--cap 10] [--per-repo 3]
"""
import json
import os
import random
import sys
from collections import defaultdict

scan, files, out = sys.argv[1:4]


def opt(name, default):
    return int(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default


seed, cap, per_repo = opt("--seed", 20261004), opt("--cap", 10), opt("--per-repo", 3)
data = json.load(open(scan))
rng = random.Random(seed)
strata = defaultdict(list)
for f in data["findings"]:
    strata[(f["rule"], f["confidence"])].append(f)
chosen = []
for key in sorted(strata):
    pool = sorted(strata[key], key=lambda f: (f["repo"], f["file"], f["line"]))
    rng.shuffle(pool)
    seen = defaultdict(int)
    n = 0
    for f in pool:
        if n >= cap:
            break
        if seen[f["repo"]] >= per_repo:
            continue
        seen[f["repo"]] += 1
        n += 1
        chosen.append({**f, "id": len(chosen), "stratum_size": len(pool)})
out_lines = []
for f in chosen:
    path = os.path.join(files, f["repo"].replace("/", "__"), f["file"])
    try:
        src = open(path, encoding="utf-8", errors="replace").read().splitlines()
    except OSError:
        src = []
    ln = f["line"]
    if f["file"].endswith(".ipynb"):
        ln = f["line"]
    a, b = max(0, ln - 3), min(len(src), ln + 2)
    out_lines.append(f"### {f['id']}  {f['rule']} ({f['severity']}, {f['confidence']})  {f['repo']}  {f['file']}:{f['line']}")
    out_lines.append("```")
    for i in range(a, b):
        out_lines.append(("=> " if i + 1 == ln else "   ") + f"{i + 1}: {src[i][:140]}")
    out_lines.append("```")
    out_lines.append(f"msg: {f['message'][:160]}\n")
open(out, "w").write("\n".join(out_lines))
json.dump(chosen, open(out.replace(".md", ".json"), "w"), indent=1)
print(len(chosen), "sampled from", sum(len(v) for v in strata.values()), "findings in", len(strata), "strata")
