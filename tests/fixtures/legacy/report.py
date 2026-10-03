"""Monthly sales report written for pandas 1.x/2.x."""
import io

import numpy as np
import pandas as pd

pd.set_option("mode.use_inf_as_na", True)


def load(path):
    df = pd.read_csv(path, delim_whitespace=True, parse_dates=["created_at"])
    df["amount"].fillna(0, inplace=True)
    df["region"][df["region"].isna()] = "unknown"
    df.loc[df["amount"] < 0, "amount"] = np.nan
    return df


def summarize(df):
    monthly = df.set_index("created_at").resample("M")["amount"].sum()
    labels = df.select_dtypes(include=object).columns
    text_cols = [c for c in df.columns if df[c].dtype == object]
    df["code"] = df["code"].astype(str)
    df.loc[df["code"] == "nan", "code"] = ""
    df["epoch"] = df["created_at"].astype("int64") // 10**9
    totals = df.groupby("region", axis=0).sum()
    pretty = df.applymap(lambda x: x)
    return monthly, labels, text_cols, totals, pretty


def parse(raw):
    return pd.read_json('{"a": [1, 2]}'), pd.to_numeric(raw, errors="ignore")
