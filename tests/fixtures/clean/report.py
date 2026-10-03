"""The same report after the pandas 3 migration."""
import io

import numpy as np
import pandas as pd


def load(path):
    df = pd.read_csv(path, sep=r"\s+", parse_dates=["created_at"])
    df["amount"] = df["amount"].fillna(0)
    df.loc[df["region"].isna(), "region"] = "unknown"
    df.loc[df["amount"] < 0, "amount"] = np.nan
    return df


def summarize(df):
    monthly = df.set_index("created_at").resample("ME")["amount"].sum()
    labels = df.select_dtypes(include=["object", "string"]).columns
    text_cols = [c for c in df.columns if pd.api.types.is_string_dtype(df[c])]
    df["code"] = df["code"].astype(str).where(df["code"].notna(), "")
    df["epoch"] = (df["created_at"] - pd.Timestamp("1970-01-01")) // pd.Timedelta("1s")
    totals = df.groupby("region").sum()
    pretty = df.map(lambda x: x)
    return monthly, labels, text_cols, totals, pretty


def parse(raw):
    return pd.read_json(io.StringIO('{"a": [1, 2]}')), pd.to_numeric(raw, errors="coerce")
