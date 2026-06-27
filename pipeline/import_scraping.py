"""Import and merge scraping CSV data into graveyard.json."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .config import GRAVEYARD_JSON, ROOT
from .merge import load_graveyard, merge_entry, save_graveyard, sort_startups
from .normalize import normalize_category, normalize_key, normalize_startup_name

SCRAPING_MASTER = ROOT / "scraping" / "indian_startup_graveyard_MASTER.csv"


def _parse_funding(value) -> int:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0
    text = str(value).replace(",", "").replace("$", "").strip()
    try:
        return int(float(text))
    except ValueError:
        return 0


def import_master_csv() -> dict[str, int]:
    if not SCRAPING_MASTER.exists():
        print(f"[import] Missing {SCRAPING_MASTER}")
        return {"merged": 0, "added": 0}

    df = pd.read_csv(SCRAPING_MASTER)
    data = load_graveyard()
    startups = data.get("startups", [])
    index = {normalize_key(s.get("startup_name", "")): s for s in startups}

    merged = 0
    added = 0
    now = datetime.now(timezone.utc).date().isoformat()

    for _, row in df.iterrows():
        raw_name = str(row.get("startup_name", "")).strip()
        if not raw_name:
            continue

        name = normalize_startup_name(raw_name)
        key = normalize_key(name)
        funding = _parse_funding(row.get("funding"))
        failure_reason = str(row.get("failure_reason", "") or "").strip()
        source = str(row.get("source", "") or "").strip()
        year = row.get("year")

        patch: dict = {
            "startup_name": name,
            "failure_reason": failure_reason or None,
        }
        if funding:
            patch["funding_burned_usd"] = funding
        if source:
            patch["sources"] = [{"title": source, "url": ""}]
        if pd.notna(year):
            try:
                patch["year_died"] = int(year)
            except (TypeError, ValueError):
                pass

        if key in index:
            index[key] = merge_entry(index[key], {k: v for k, v in patch.items() if v})
            index[key]["updated_at"] = now
            merged += 1
        else:
            patch.update(
                {
                    "status": "Shut Down",
                    "short_summary": failure_reason or f"{name} — Indian startup failure case.",
                    "category": "Technology",
                    "added_at": now,
                    "updated_at": now,
                }
            )
            index[key] = {k: v for k, v in patch.items() if v is not None}
            added += 1

    for s in startups:
        key = normalize_key(s.get("startup_name", ""))
        if key in index:
            s.update(index[key])
        s["category"] = normalize_category(s.get("category"))

    for key, item in index.items():
        if not any(normalize_key(s.get("startup_name", "")) == key for s in startups):
            item["category"] = normalize_category(item.get("category"))
            startups.append(item)

    data["startups"] = sort_startups(startups)
    save_graveyard(data)
    print(f"[import] Merged {merged}, added {added} from scraping CSV")
    return {"merged": merged, "added": added}


if __name__ == "__main__":
    import_master_csv()