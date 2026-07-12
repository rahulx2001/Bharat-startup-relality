#!/usr/bin/env python3
"""Upgrade every graveyard startup to gold research depth and write audits."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.audit_research import audit_startups  # noqa: E402
from pipeline.gold_upgrader import upgrade_all  # noqa: E402
from pipeline.merge import load_graveyard, save_graveyard, sort_startups  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--before", type=Path, default=None)
    parser.add_argument("--after", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=None)
    args = parser.parse_args()

    data = load_graveyard()
    startups = data.get("startups") or []
    before = audit_startups(startups)
    if args.before:
        args.before.parent.mkdir(parents=True, exist_ok=True)
        args.before.write_text(json.dumps(before, indent=2, ensure_ascii=False), encoding="utf-8")

    upgraded, stats = upgrade_all(startups)
    after = audit_startups(upgraded)

    if not args.dry_run:
        data["startups"] = sort_startups(upgraded)
        data["generated_at"] = datetime.now(timezone.utc).date().isoformat()
        data["research_upgrade_at"] = datetime.now(timezone.utc).isoformat()
        save_graveyard(data)

    if args.after:
        args.after.parent.mkdir(parents=True, exist_ok=True)
        args.after.write_text(json.dumps(after, indent=2, ensure_ascii=False), encoding="utf-8")

    summary = {
        "before_pass": before["gold_pass"],
        "before_fail": before["failing_count"],
        "after_pass": after["gold_pass"],
        "after_fail": after["failing_count"],
        "upgrade_stats": stats,
        "blocked": after["failing"],
    }
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(
        f"Research upgrade: {before['gold_pass']}/{before['total']} -> "
        f"{after['gold_pass']}/{after['total']} gold-pass "
        f"(blocked={after['failing_count']})"
    )
    for row in after["failing"][:30]:
        print(" BLOCKED", row["startup_name"], row["score"], row["gate_missing"][:5])
    return 0 if after["failing_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
