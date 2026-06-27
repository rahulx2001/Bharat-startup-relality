#!/usr/bin/env python3
"""Run the full startup graveyard automation pipeline."""
from __future__ import annotations

import argparse
import sys

from .config import MAX_NEW_STARTUPS_PER_RUN, NVIDIA_API_KEY
from .funding import lookup_startup
from .llm import enrich_startup, extract_signals
from .merge import apply_updates, load_graveyard
from .scrape import fetch_articles
from .validate import validate_graveyard


def run_pipeline(dry_run: bool = False, force_scrape: bool = False) -> int:
    print("=== Startup Graveyard Pipeline ===")

    graveyard = load_graveyard()
    startups = graveyard.get("startups", [])
    known_names = [item.get("startup_name", "") for item in startups if item.get("startup_name")]
    known_index = {name.lower(): item for item in startups for name in [item.get("startup_name", "")]}

    articles = fetch_articles(force=force_scrape)
    if not articles:
        print("[pipeline] No new articles found")
        return 0

    if not NVIDIA_API_KEY:
        print("[pipeline] ERROR: Set NVIDIA_API_KEY before running enrichment")
        return 1

    signals = extract_signals(articles, known_names)
    if not signals:
        print("[pipeline] No startup signals extracted")
        return 0

    signals = sorted(signals, key=lambda item: item.get("confidence", 0), reverse=True)

    deduped_signals = []
    seen_names = set()
    for signal in signals:
        norm = signal["startup_name"].strip().lower()
        if norm in seen_names:
            continue
        seen_names.add(norm)
        deduped_signals.append(signal)
    signals = deduped_signals[:MAX_NEW_STARTUPS_PER_RUN]

    enriched_entries = []
    for signal in signals:
        name = signal["startup_name"]
        print(f"[pipeline] Enriching: {name} ({signal['status']})")
        funding = lookup_startup(name)
        existing = known_index.get(name.lower())
        try:
            entry = enrich_startup(signal, funding, existing)
            enriched_entries.append(entry)
        except Exception as exc:
            print(f"[pipeline] Skipped {name}: {exc}")

    if dry_run:
        print(f"[pipeline] Dry run complete — would update {len(enriched_entries)} startups")
        return 0

    stats = apply_updates(enriched_entries)
    errors = validate_graveyard(load_graveyard())
    if errors:
        print("[pipeline] Validation warnings:")
        for error in errors[:20]:
            print(f"  - {error}")
        return 1

    print(
        f"[pipeline] Done — added {stats['added']}, updated {stats['updated']}, "
        f"total {stats['total']} startups"
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Automate startup graveyard data refresh")
    parser.add_argument("--dry-run", action="store_true", help="Scrape + enrich without writing JSON")
    parser.add_argument("--force-scrape", action="store_true", help="Ignore article cache")
    args = parser.parse_args()
    raise SystemExit(run_pipeline(dry_run=args.dry_run, force_scrape=args.force_scrape))


if __name__ == "__main__":
    main()