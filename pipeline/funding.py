"""Lookup startup funding data from the government funding CSV."""
from __future__ import annotations

import re
from functools import lru_cache

import pandas as pd

from .config import FUNDING_CSV


def _normalize_name(name: str) -> str:
    cleaned = re.sub(r"https?://", "", name.lower())
    cleaned = re.sub(r"www\.", "", cleaned)
    cleaned = re.sub(r"[^a-z0-9]+", "", cleaned)
    return cleaned.strip()


@lru_cache(maxsize=1)
def _load_funding_frame() -> pd.DataFrame:
    if not FUNDING_CSV.exists():
        return pd.DataFrame()

    df = pd.read_csv(FUNDING_CSV)
    df["startup_norm"] = df["startup"].astype(str).map(_normalize_name)
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    return df


def lookup_startup(name: str) -> dict:
    """Return aggregated funding metadata for a startup name."""
    df = _load_funding_frame()
    if df.empty:
        return {}

    norm = _normalize_name(name)
    matches = df[df["startup_norm"] == norm]
    if matches.empty:
        matches = df[df["startup_norm"].str.contains(norm[:6], na=False)] if len(norm) >= 6 else matches
    if matches.empty:
        return {}

    grouped = matches.groupby("startup", as_index=False).agg(
        funding_total_usd=("amount", "sum"),
        category=("vertical", "last"),
        headquarters=("city", "last"),
        investors=("investor", lambda s: sorted({str(v).strip() for v in s if str(v).strip()})),
        rounds=("round", lambda s: sorted({str(v).strip() for v in s if str(v).strip()})),
    )
    row = grouped.iloc[0]
    return {
        "funding_burned_usd": int(row["funding_total_usd"]),
        "category": str(row["category"]),
        "headquarters": str(row["headquarters"]),
        "investors": row["investors"][:12],
        "rounds": row["rounds"][:8],
    }