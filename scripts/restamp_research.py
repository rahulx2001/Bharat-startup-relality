#!/usr/bin/env python3
"""CLI: re-stamp all research metadata from the live gold gate."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.audit_research import audit_startups  # noqa: E402
from pipeline.merge import load_graveyard, save_graveyard, sort_startups  # noqa: E402
from pipeline.restamp import restamp_all  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()

    data = load_graveyard()
    startups = data.get("startups") or []
    before = audit_startups(startups)
    stats = restamp_all(startups)
    after = audit_startups(startups)

    # Consistency: JSON gold labels must equal audit pass count
    labeled_gold = sum(1 for s in startups if s.get("profile_tier") == "gold")
    assert labeled_gold == after["gold_pass"], (
        f"label/audit mismatch: tier=gold count {labeled_gold} vs audit pass {after['gold_pass']}"
    )

    if not args.dry_run:
        data["startups"] = sort_startups(startups)
        save_graveyard(data)

    summary = {
        "stamp_stats": stats,
        "before_audit_pass": before["gold_pass"],
        "after_audit_pass": after["gold_pass"],
        "labeled_gold": labeled_gold,
        "blocked_count": after["blocked_count"],
    }
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
