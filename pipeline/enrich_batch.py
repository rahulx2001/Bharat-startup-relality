#!/usr/bin/env python3
"""Batch-enrich all startups to BluSmart gold-standard depth."""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone

from .config import CACHE_DIR, nvidia_api_key, nvidia_model
from .funding import lookup_startup
from .llm import enrich_profile_full
from .merge import apply_updates, load_graveyard
from .normalize import normalize_category
from .quality import needs_enrichment, profile_score
from .research_gate import evaluate_research

PROGRESS_FILE = CACHE_DIR / "enrich_progress.json"


def _load_progress() -> set[str]:
    if not PROGRESS_FILE.exists():
        return set()
    try:
        data = json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
        return set(data.get("done", []))
    except (json.JSONDecodeError, OSError):
        return set()


def _save_progress(done: set[str]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    PROGRESS_FILE.write_text(
        json.dumps({"done": sorted(done), "updated_at": datetime.now(timezone.utc).isoformat()}, indent=2),
        encoding="utf-8",
    )


def _gold_example() -> dict:
    data = load_graveyard()
    startups = data.get("startups") or []
    if not startups:
        raise RuntimeError("graveyard.json has no startups for gold example")
    for s in startups:
        if s.get("startup_name") == "BluSmart":
            return s
    return startups[0]


def run_batch(limit: int = 0, force: bool = False, delay: float = 30.0) -> int:
    if not nvidia_api_key():
        print("[batch] ERROR: Set NVIDIA_API_KEY")
        return 1

    print(f"[batch] Model: {nvidia_model()}")
    data = load_graveyard()
    startups = data.get("startups", [])
    gold = _gold_example()
    done = set() if force else _load_progress()
    now = datetime.now(timezone.utc).date().isoformat()

    targets = []
    for s in startups:
        name = s.get("startup_name", "")
        if not name:
            continue
        if name in done and not force:
            continue
        if force or needs_enrichment(s):
            targets.append(s)

    if limit > 0:
        targets = targets[:limit]

    print(f"[batch] Enriching {len(targets)} startups to BluSmart gold standard")

    saved = 0
    skipped = 0
    for i, existing in enumerate(targets, 1):
        name = existing["startup_name"]
        before = profile_score(existing)
        print(f"[batch] ({i}/{len(targets)}) {name} — tier {before['tier']} score {before['score']}")

        funding = lookup_startup(name)
        try:
            entry = enrich_profile_full(existing, funding, gold)
            entry["category"] = normalize_category(entry.get("category") or existing.get("category"))
            entry["updated_at"] = now
            if not existing.get("added_at"):
                entry["added_at"] = existing.get("added_at") or now

            gate = evaluate_research(entry, is_new=False, require_gold=True)
            if not gate.accepted:
                print(f"         ✗ gate failed: {gate.summary()} — not saving")
                skipped += 1
            else:
                apply_updates([entry])
                done.add(name)
                _save_progress(done)
                saved += 1
                after = profile_score(entry)
                print(f"         → tier {after['tier']} score {after['score']} (saved)")
        except Exception as exc:
            print(f"         ✗ failed: {exc}")
            skipped += 1

        if i < len(targets):
            time.sleep(delay)

    print(f"[batch] Complete — saved {saved}, skipped {skipped}, progress {len(done)}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch enrich graveyard profiles")
    parser.add_argument("--limit", type=int, default=0, help="Max startups to process (0 = all)")
    parser.add_argument("--force", action="store_true", help="Re-enrich even if marked done")
    parser.add_argument("--delay", type=float, default=2.0, help="Seconds between API calls")
    args = parser.parse_args()
    raise SystemExit(run_batch(limit=args.limit, force=args.force, delay=args.delay))


if __name__ == "__main__":
    main()
