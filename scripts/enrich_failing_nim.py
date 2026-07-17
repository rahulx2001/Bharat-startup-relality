#!/usr/bin/env python3
"""Cloud-NIM enrich every below-gold startup; block with reasons on failure.

Requires NVIDIA_API_KEY. Does not template-pad. Writes progress after each save.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.audit_research import audit_startups  # noqa: E402
from pipeline.config import nvidia_api_key, nvidia_model, research_max_repair_passes  # noqa: E402
from pipeline.funding import lookup_startup  # noqa: E402
from pipeline.llm import enrich_profile_full  # noqa: E402
from pipeline.merge import apply_updates, load_graveyard  # noqa: E402
from pipeline.normalize import normalize_category  # noqa: E402
from pipeline.quality import profile_score  # noqa: E402
from pipeline.research_gate import evaluate_research  # noqa: E402


def _gold_example(startups: list) -> dict:
    for s in startups:
        if s.get("startup_name") == "BluSmart":
            return s
    # prefer highest score as example
    best = max(startups, key=lambda x: profile_score(x)["score"])
    return best


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Max failing startups to process (0=all)")
    parser.add_argument("--delay", type=float, default=3.0)
    parser.add_argument("--before", type=Path)
    parser.add_argument("--after", type=Path)
    parser.add_argument("--blocked", type=Path)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()

    if not nvidia_api_key():
        print("ERROR: NVIDIA_API_KEY not set — cannot cloud-enrich; use audit+blocked path")
        return 2

    print(f"[enrich] model={nvidia_model()} repair_passes={research_max_repair_passes()}")
    data = load_graveyard()
    startups = data.get("startups") or []
    before = audit_startups(startups)
    if args.before:
        args.before.parent.mkdir(parents=True, exist_ok=True)
        args.before.write_text(json.dumps(before, indent=2, ensure_ascii=False), encoding="utf-8")

    failing_names = [r["startup_name"] for r in before["failing"]]
    targets = [s for s in startups if s.get("startup_name") in set(failing_names)]
    # thinnest first
    targets.sort(key=lambda s: profile_score(s)["score"])
    if args.limit > 0:
        targets = targets[: args.limit]

    gold = _gold_example(startups)
    now = datetime.now(timezone.utc).date().isoformat()
    blocked: list[dict] = []
    enriched_ok: list[str] = []

    print(f"[enrich] targets={len(targets)} (of {before['failing_count']} failing)")

    for i, existing in enumerate(targets, 1):
        name = existing["startup_name"]
        before_sc = profile_score(existing)
        print(f"[enrich] ({i}/{len(targets)}) {name} score={before_sc['score']} tier={before_sc['tier']}")
        funding = lookup_startup(name)
        try:
            entry = enrich_profile_full(existing, funding, gold)
            entry["category"] = normalize_category(entry.get("category") or existing.get("category"))
            entry["updated_at"] = now
            entry.setdefault("added_at", existing.get("added_at") or now)
            # only save if gold gate passes
            gate = evaluate_research(entry, is_new=False, require_gold=True)
            sc = profile_score(entry)
            if gate.accepted and sc["score"] >= 85:
                # require at least one real http source that is not a bare site search if possible
                apply_updates([entry])
                enriched_ok.append(name)
                print(f"         SAVED gold score={sc['score']}")
            else:
                blocked.append(
                    {
                        "startup_name": name,
                        "score": sc["score"],
                        "tier": sc["tier"],
                        "missing": sc["missing"],
                        "gate_missing": gate.missing,
                        "blocked_reason": f"cloud NIM enrich+repair still below gold: {gate.summary()}",
                    }
                )
                print(f"         BLOCKED {gate.summary()}")
        except Exception as exc:
            blocked.append(
                {
                    "startup_name": name,
                    "score": before_sc["score"],
                    "tier": before_sc["tier"],
                    "missing": before_sc["missing"],
                    "blocked_reason": f"cloud NIM error: {exc}",
                }
            )
            print(f"         ERROR {exc}")

        if i < len(targets):
            time.sleep(args.delay)

    # re-audit full file
    after = audit_startups(load_graveyard().get("startups") or [])
    # any still failing not already in blocked → blocked as not processed / still thin
    blocked_names = {b["startup_name"] for b in blocked}
    for row in after["failing"]:
        if row["startup_name"] not in blocked_names and row["startup_name"] not in enriched_ok:
            blocked.append(
                {
                    "startup_name": row["startup_name"],
                    "score": row["score"],
                    "tier": row["tier"],
                    "missing": row["missing"],
                    "blocked_reason": "still below gold after run (not successfully enriched)",
                }
            )

    summary = {
        "model": nvidia_model(),
        "before_pass": before["gold_pass"],
        "before_fail": before["failing_count"],
        "after_pass": after["gold_pass"],
        "after_fail": after["failing_count"],
        "enriched_ok": enriched_ok,
        "enriched_count": len(enriched_ok),
        "blocked": blocked,
        "blocked_count": len(blocked),
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }

    if args.after:
        args.after.parent.mkdir(parents=True, exist_ok=True)
        args.after.write_text(json.dumps(after, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.blocked:
        args.blocked.parent.mkdir(parents=True, exist_ok=True)
        args.blocked.write_text(json.dumps(blocked, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(
        f"[enrich] done pass {before['gold_pass']}->{after['gold_pass']} "
        f"enriched={len(enriched_ok)} blocked={len(blocked)}"
    )
    # success if every non-gold is on blocked list (honest)
    failing_names_after = {r["startup_name"] for r in after["failing"]}
    blocked_cover = failing_names_after <= {b["startup_name"] for b in blocked}
    return 0 if blocked_cover else 1


if __name__ == "__main__":
    raise SystemExit(main())
