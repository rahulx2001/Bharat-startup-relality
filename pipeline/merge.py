"""Merge enriched startups into graveyard.json."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from .config import FAMOUS_SHUTDOWNS, GRAVEYARD_JSON, STATUS_PRIORITY


def _normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def load_graveyard() -> dict[str, Any]:
    if not GRAVEYARD_JSON.exists():
        return {"generated_at": "", "startups": []}
    return json.loads(GRAVEYARD_JSON.read_text(encoding="utf-8"))


def save_graveyard(data: dict[str, Any]) -> None:
    data["generated_at"] = datetime.now(timezone.utc).date().isoformat()
    GRAVEYARD_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _merge_timeline(existing: list[dict], incoming: list[dict]) -> list[dict]:
    seen = {(item.get("date"), item.get("event")) for item in existing}
    merged = list(existing)
    for item in incoming or []:
        key = (item.get("date"), item.get("event"))
        if key not in seen and item.get("event"):
            merged.append(item)
            seen.add(key)
    return merged[-12:]


def _merge_lists(existing: list, incoming: list, limit: int = 12) -> list:
    merged = []
    for value in (existing or []) + (incoming or []):
        text = str(value).strip()
        if text and text not in merged:
            merged.append(text)
    return merged[:limit]


def merge_entry(existing: dict[str, Any] | None, incoming: dict[str, Any]) -> dict[str, Any]:
    if not existing:
        return incoming

    merged = dict(existing)
    for key, value in incoming.items():
        if value in (None, "", [], {}):
            continue
        if key == "timeline":
            merged[key] = _merge_timeline(existing.get("timeline", []), value)
        elif key in {"insights", "lessons", "founders", "investors"}:
            merged[key] = _merge_lists(existing.get(key, []), value)
        elif key == "sources":
            merged[key] = _merge_lists(existing.get(key, []), value, limit=8)
        elif key == "funding_burned_usd":
            current = existing.get("funding_burned_usd") or 0
            incoming_val = value or 0
            merged[key] = max(current, incoming_val)
        else:
            merged[key] = value
    return merged


def sort_startups(startups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def sort_key(startup: dict[str, Any]):
        status = startup.get("status", "Unknown")
        name = startup.get("startup_name", "")
        status_order = STATUS_PRIORITY.get(status, 99)
        if status == "Shut Down":
            famous_order = FAMOUS_SHUTDOWNS.index(name) if name in FAMOUS_SHUTDOWNS else 999
            funding = startup.get("funding_burned_usd") or 0
            return (status_order, famous_order, -funding)
        funding = startup.get("funding_burned_usd") or 0
        return (status_order, 0, -funding)

    return sorted(startups, key=sort_key)


def apply_updates(entries: list[dict[str, Any]]) -> dict[str, int]:
    data = load_graveyard()
    startups = data.get("startups", [])
    index = {_normalize_name(item.get("startup_name", "")): item for item in startups}

    added = 0
    updated = 0
    for entry in entries:
        norm = _normalize_name(entry.get("startup_name", ""))
        if not norm:
            continue
        if norm in index:
            index[norm] = merge_entry(index[norm], entry)
            updated += 1
        else:
            index[norm] = entry
            added += 1

    deduped: list[dict[str, Any]] = []
    seen = set()
    for item in startups:
        norm = _normalize_name(item.get("startup_name", ""))
        if norm in seen:
            continue
        seen.add(norm)
        deduped.append(index.get(norm, item))

    for norm, item in index.items():
        if norm not in seen:
            deduped.append(item)
            seen.add(norm)

    data["startups"] = sort_startups(deduped)
    save_graveyard(data)
    return {"added": added, "updated": updated, "total": len(data["startups"])}