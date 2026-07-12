#!/usr/bin/env python3
"""Run the full startup graveyard automation pipeline."""
from __future__ import annotations

import argparse

from .config import (
    MAX_NEW_STARTUPS_PER_RUN,
    nvidia_api_key,
    nvidia_model,
    research_require_gold_for_new,
    research_require_gold_for_update,
)
from .funding import lookup_startup
from .llm import extract_signals, research_startup
from .merge import apply_updates, load_graveyard
from .scrape import fetch_articles
from .validate import validate_graveyard


def run_pipeline(dry_run: bool = False, force_scrape: bool = False) -> int:
    print("=== Startup Graveyard Pipeline ===")
    print(f"[pipeline] Model: {nvidia_model()}")
    print(
        f"[pipeline] Research gate: new_require_gold={research_require_gold_for_new()} "
        f"update_require_gold={research_require_gold_for_update()}"
    )

    graveyard = load_graveyard()
    startups = graveyard.get("startups", [])
    known_names = [item.get("startup_name", "") for item in startups if item.get("startup_name")]
    known_index = {
        (item.get("startup_name") or "").lower(): item
        for item in startups
        if item.get("startup_name")
    }

    articles = fetch_articles(force=force_scrape)
    if not articles:
        print("[pipeline] No new articles found")
        return 0

    if not nvidia_api_key():
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

    accepted_entries = []
    rejected = []
    for signal in signals:
        name = signal["startup_name"]
        existing = known_index.get(name.lower())
        is_new = existing is None
        kind = "NEW" if is_new else "UPDATE"
        print(f"[pipeline] Researching ({kind}): {name} ({signal['status']})")
        funding = lookup_startup(name)
        try:
            entry, gate = research_startup(signal, funding, existing)
        except Exception as exc:
            print(f"[pipeline] Skipped {name}: {exc}")
            rejected.append((name, f"error: {exc}"))
            continue

        if not gate.accepted:
            print(f"[pipeline] REJECTED {name}: {gate.summary()}")
            rejected.append((name, gate.summary()))
            # Never write thin NEW startups when gold is required
            if is_new and research_require_gold_for_new():
                continue
            # Updates: only write if gold required is off
            if not is_new and research_require_gold_for_update():
                continue
            if is_new:
                continue
            # Non-strict update path: still skip if score is extremely thin
            if gate.score < 35:
                print(f"[pipeline] Skipping very thin update for {name} (score={gate.score})")
                continue

        accepted_entries.append(entry)
        print(f"[pipeline] ACCEPTED {name}: {gate.summary()}")

    if dry_run:
        print(
            f"[pipeline] Dry run — would write {len(accepted_entries)} startups, "
            f"rejected {len(rejected)}"
        )
        for name, reason in rejected[:20]:
            print(f"  reject {name}: {reason}")
        return 0

    if not accepted_entries:
        print(f"[pipeline] No accepted research dossiers (rejected={len(rejected)})")
        return 0

    stats = apply_updates(accepted_entries)
    errors = validate_graveyard(load_graveyard())
    if errors:
        print("[pipeline] Validation errors:")
        for error in errors[:20]:
            print(f"  - {error}")
        return 1

    print(
        f"[pipeline] Done — added {stats['added']}, updated {stats['updated']}, "
        f"total {stats['total']} startups, rejected {len(rejected)}"
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
