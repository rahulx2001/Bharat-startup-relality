#!/usr/bin/env python3
"""Strip invalid sources, optional redirect check, block rows without on-topic sources.

Does not homepage-pad to fake gold. Optional NIM re-research only when API key set.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.audit_research import audit_startups  # noqa: E402
from pipeline.config import nvidia_api_key  # noqa: E402
from pipeline.merge import load_graveyard, save_graveyard, sort_startups  # noqa: E402
from pipeline.restamp import restamp_all  # noqa: E402
from pipeline.source_fetch import redirect_mismatch, resolve_url  # noqa: E402
from pipeline.source_integrity import (  # noqa: E402
    brand_tokens_from_name,
    catalog_brand_tokens,
    filter_valid_sources,
    source_integrity_problems,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-redirects", action="store_true", help="Network resolve remaining URLs")
    parser.add_argument("--enrich", action="store_true", help="NIM re-research rows left without sources")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--before", type=Path)
    parser.add_argument("--after", type=Path)
    parser.add_argument("--blocked", type=Path)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()

    data = load_graveyard()
    startups = data.get("startups") or []
    catalog = catalog_brand_tokens(startups)
    before = audit_startups(startups)
    if args.before:
        args.before.parent.mkdir(parents=True, exist_ok=True)
        args.before.write_text(json.dumps(before, indent=2, ensure_ascii=False), encoding="utf-8")

    stripped_counts = {}
    for s in startups:
        name = s.get("startup_name") or "?"
        before_n = len(s.get("sources") or [])
        kept = filter_valid_sources(s, catalog)
        # optional redirect validation
        if args.check_redirects and kept:
            subject = catalog.get(name) or brand_tokens_from_name(name)
            final_kept = []
            for item in kept:
                res = resolve_url(item["url"])
                if redirect_mismatch(subject, res):
                    continue
                if res.get("ok") and res.get("final_url"):
                    item = {**item, "url": res["final_url"]}
                final_kept.append(item)
            kept = final_kept
        s["sources"] = kept
        stripped_counts[name] = {"before": before_n, "after": len(kept)}

    # Always re-stamp tiers so JSON never claims gold when gate fails
    stamp_stats = restamp_all(startups)

    # Re-audit after strip + restamp
    mid = audit_startups(startups)
    need_enrich = [s for s in startups if not next(r for r in mid["all"] if r["startup_name"] == s["startup_name"])["pass"]]

    blocked = list(mid["blocked"])
    enriched_ok = []

    if args.enrich and nvidia_api_key() and need_enrich:
        from pipeline.funding import lookup_startup
        from pipeline.llm import enrich_profile_full
        from pipeline.normalize import normalize_category
        from pipeline.research_gate import evaluate_research

        gold = next((x for x in startups if x.get("startup_name") == "BluSmart"), startups[0])
        targets = need_enrich
        if args.limit > 0:
            targets = targets[: args.limit]
        now = datetime.now(timezone.utc).date().isoformat()
        for s in targets:
            name = s["startup_name"]
            print(f"[remediate] NIM enrich {name}")
            try:
                entry = enrich_profile_full(s, lookup_startup(name), gold)
                entry["startup_name"] = name
                entry["status"] = s.get("status") or entry.get("status")
                entry["category"] = normalize_category(entry.get("category") or s.get("category"))
                entry["updated_at"] = now
                # keep only integrity-valid sources from model output
                entry["sources"] = filter_valid_sources(entry, catalog_brand_tokens(startups + [entry]))
                gate = evaluate_research(entry, is_new=False, require_gold=True, catalog_tokens=catalog_brand_tokens(startups + [entry]))
                probs = source_integrity_problems(entry, catalog_brand_tokens(startups + [entry]))
                if gate.accepted and not probs:
                    # write into list
                    for i, row in enumerate(startups):
                        if row.get("startup_name") == name:
                            startups[i] = entry
                            break
                    enriched_ok.append(name)
                    print(f"  SAVED {name}")
                else:
                    print(f"  still bad gate={gate.accepted} src={probs[:3]}")
            except Exception as exc:
                print(f"  ERROR {exc}")

    # Final restamp after any enrich
    stamp_stats = restamp_all(startups)
    data["startups"] = sort_startups(startups)
    save_graveyard(data)

    after = audit_startups(data["startups"])
    blocked = after["blocked"]

    if args.after:
        args.after.parent.mkdir(parents=True, exist_ok=True)
        args.after.write_text(json.dumps(after, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.blocked:
        args.blocked.parent.mkdir(parents=True, exist_ok=True)
        args.blocked.write_text(json.dumps(blocked, indent=2, ensure_ascii=False), encoding="utf-8")
    summary = {
        "stripped": stripped_counts,
        "enriched_ok": enriched_ok,
        "stamp_stats": stamp_stats,
        "before_pass": before["gold_pass"],
        "after_pass": after["gold_pass"],
        "after_fail": after["failing_count"],
        "blocked_count": after["blocked_count"],
        "blocked": blocked,
    }
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(
        f"remediate: gold {before['gold_pass']}->{after['gold_pass']} "
        f"blocked={after['blocked_count']} enriched={len(enriched_ok)} "
        f"demoted_labels={stamp_stats.get('demoted_from_gold_label')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
