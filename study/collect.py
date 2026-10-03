"""Collect candidate files for the precision study with the GitHub code search API (read only; opens nothing on those repositories).

    python study/collect.py OUT.json

Every query returns at most 1000 results in GitHub's relevance order, not random: the sample is a convenience sample.
Two kinds of queries: TARGETED (text typical for a rule, to give each rule a chance to fire) and BROAD (any file that imports pandas, in file-size
buckets, so that the share of false positives on ordinary pandas code can be seen).
"""
import json
import subprocess
import sys
import time

TARGETED = [
    "inplace=True fillna language:Python", "inplace=True replace extension:ipynb", "applymap language:Python", "applymap extension:ipynb",
    "delim_whitespace=True language:Python", "fillna(method= language:Python", "fillna(method= extension:ipynb", "errors='ignore' to_numeric language:Python",
    "errors=\"ignore\" to_datetime language:Python", "use_inf_as_na language:Python", "freq='H' date_range language:Python", "resample('M') language:Python",
    "resample(\"M\") language:Python", "freq='T' language:Python", "groupby axis=1 language:Python", "infer_datetime_format=True language:Python",
    "select_dtypes(include=object) language:Python", "select_dtypes(include='object') language:Python", "dtype == object language:Python pandas",
    "astype(str) 'nan' language:Python pandas", ".values[ pandas language:Python", "to_numpy() pandas language:Python chained", "astype('int64') 10**9 pandas language:Python",
    "asi8 pandas language:Python", "copy=False pandas astype language:Python", "pd.value_counts language:Python", "swapaxes pandas language:Python",
    "pct_change(fill_method language:Python", "stack(dropna=False) language:Python", "include_groups language:Python pandas", "pd.read_json( '{ language:Python",
    "SettingWithCopyWarning language:Python", "chained_assignment language:Python pandas", "timedelta unit='T' pandas language:Python", "df['a'][0] = pandas language:Python",
]
BROAD = ["import pandas as pd language:Python size:%d..%d" % (a, b) for a, b in
         [(500, 800), (800, 1200), (1200, 1800), (1800, 2600), (2600, 3600), (3600, 5000), (5000, 7500), (7500, 12000), (12000, 20000), (20000, 40000)]]
BROAD += ["import pandas as pd extension:ipynb size:%d..%d" % (a, b) for a, b in [(3000, 6000), (6000, 12000), (12000, 25000), (25000, 60000)]]
PAGES = 3


def api(path):
    for attempt in range(6):
        p = subprocess.run(["gh", "api", path], capture_output=True, text=True)
        if p.returncode == 0:
            return json.loads(p.stdout)
        if "rate limit" in (p.stderr + p.stdout).lower() or "403" in p.stderr:
            time.sleep(30 * (attempt + 1))
            continue
        if "422" in p.stderr:
            return None
        time.sleep(5)
    return None


def main(out):
    seen = {}
    for kind, queries in (("targeted", TARGETED), ("broad", BROAD)):
        for q in queries:
            for page in range(1, PAGES + 1):
                d = api("search/code?per_page=100&page=%d&q=%s" % (page, q.replace(" ", "+")))
                time.sleep(7)
                if not d or not d.get("items"):
                    break
                for it in d["items"]:
                    repo = it["repository"]["full_name"]
                    if repo.startswith("cosmichackerx/"):
                        continue
                    seen.setdefault(repo + "|" + it["path"], {"repo": repo, "path": it["path"], "html_url": it["html_url"], "fork": it["repository"].get("fork", False), "query": q, "kind": kind})
                print(kind, q, page, len(seen), flush=True)
                if len(d["items"]) < 100:
                    break
            json.dump(list(seen.values()), open(out, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1])
