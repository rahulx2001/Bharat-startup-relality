#!/usr/bin/env python3
"""Honest research audit: cloud NIM enrich if key set, else blocked list only.

Never template-pads to gold. Prefer scripts/enrich_failing_nim.py for enrichment.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.audit_research import audit_startups  # noqa: E402
from pipeline.config import nvidia_api_key  # noqa: E402
from pipeline.gold_upgrader import classify_failures  # noqa: E402
from pipeline.merge import load_graveyard  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", type=Path)
    parser.add_argument("--after", type=Path)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--blocked", type=Path)
    parser.add_argument(
        "--enrich",
        action="store_true",
        help="If NVIDIA_API_KEY set, run scripts/enrich_failing_nim.py for failures",
    )
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    startups = load_graveyard().get("startups") or []
    before = audit_startups(startups)
    if args.before:
        args.before.parent.mkdir(parents=True, exist_ok=True)
        args.before.write_text(json.dumps(before, indent=2, ensure_ascii=False), encoding="utf-8")

    key = bool(nvidia_api_key())
    if args.enrich and key:
        from scripts.enrich_failing_nim import main as enrich_main

        # re-parse is awkward; call enrich module programmatically via subprocess
        import subprocess

        cmd = [
            sys.executable,
            str(ROOT / "scripts" / "enrich_failing_nim.py"),
            "--delay",
            "3",
        ]
        if args.limit:
            cmd += ["--limit", str(args.limit)]
        if args.before:
            cmd += ["--before", str(args.before)]
        if args.after:
            cmd += ["--after", str(args.after)]
        if args.blocked:
            cmd += ["--blocked", str(args.blocked)]
        if args.summary:
            cmd += ["--summary", str(args.summary)]
        return subprocess.call(cmd)

    # No enrich: honest blocked list for all non-gold
    classified = classify_failures(startups, api_key_present=key)
    after = before  # data unchanged
    summary = {
        "mode": "audit_only_no_template_gold",
        "api_key_present": key,
        "before_pass": before["gold_pass"],
        "before_fail": before["failing_count"],
        "after_pass": after["gold_pass"],
        "after_fail": after["failing_count"],
        "blocked": classified["blocked"],
        "blocked_count": classified["blocked_count"],
        "note": (
            "No cloud enrichment run. Failing rows listed in blocked with reason. "
            "Run: NVIDIA_API_KEY=... python scripts/enrich_failing_nim.py"
            if not key
            else "Key present but --enrich not passed; blocked = current non-gold rows."
        ),
    }
    if args.after:
        args.after.parent.mkdir(parents=True, exist_ok=True)
        args.after.write_text(json.dumps(after, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.blocked:
        args.blocked.parent.mkdir(parents=True, exist_ok=True)
        args.blocked.write_text(json.dumps(classified["blocked"], indent=2, ensure_ascii=False), encoding="utf-8")
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(
        f"Audit-only: gold={before['gold_pass']}/{before['total']} "
        f"blocked={classified['blocked_count']} api_key={key}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
