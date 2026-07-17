#!/usr/bin/env python3
"""Apply curated source seeds after integrity validation. Never invents gold."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.restamp import restamp_all  # noqa: E402
from pipeline.source_integrity import (  # noqa: E402
    catalog_brand_tokens,
    source_integrity_problems,
)


def main() -> int:
    graveyard = ROOT / "data" / "graveyard.json"
    seeds_path = ROOT / "data" / "source_seeds.json"
    data = json.loads(graveyard.read_text(encoding="utf-8"))
    seeds = json.loads(seeds_path.read_text(encoding="utf-8")).get("seeds") or {}
    items = data["startups"]
    by_name = {s.get("startup_name"): s for s in items}
    catalog = catalog_brand_tokens(items)

    attached = 0
    rejected = 0
    details = []

    for name, srcs in seeds.items():
        if name.startswith("_"):
            continue
        entry = by_name.get(name)
        if not entry:
            details.append({"name": name, "status": "missing_startup"})
            rejected += 1
            continue
        clean = []
        for src in srcs or []:
            if not isinstance(src, dict):
                continue
            url = (src.get("url") or "").strip()
            title = (src.get("title") or "").strip() or "Source"
            if not url.startswith("http"):
                continue
            probe = {**entry, "sources": [{"title": title, "url": url}]}
            probs = source_integrity_problems(probe, catalog)
            if probs:
                rejected += 1
                details.append({"name": name, "url": url, "status": "rejected", "probs": probs})
                continue
            clean.append({"title": title, "url": url})
        if not clean:
            details.append({"name": name, "status": "no_clean_sources"})
            continue
        # merge unique by url
        existing = entry.get("sources") if isinstance(entry.get("sources"), list) else []
        seen = {str(s.get("url")) for s in existing if isinstance(s, dict)}
        merged = list(existing)
        for s in clean:
            if s["url"] not in seen:
                merged.append(s)
                seen.add(s["url"])
                attached += 1
        entry["sources"] = merged
        details.append({"name": name, "status": "attached", "count": len(merged)})

    stats = restamp_all(items)
    with_src = sum(1 for s in items if s.get("sources"))
    gold = sum(
        1
        for s in items
        if s.get("profile_tier") == "gold" and s.get("research_status") == "gold_pass"
    )
    quality_summary = {
        "total": len(items),
        "with_sources": with_src,
        "with_sources_pct": round(with_src / max(1, len(items)), 4),
        "gold_pass": gold,
        "gold_pass_pct": round(gold / max(1, len(items)), 4),
        "blocked": sum(1 for s in items if s.get("research_status") == "blocked"),
        "restamp": stats,
        "seed_attach_events": attached,
        "seed_reject_events": rejected,
    }
    data["startups"] = items
    data["quality_summary"] = quality_summary
    data["generated_at"] = data.get("generated_at") or "2026-07-13"
    graveyard.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"quality_summary": quality_summary, "sample": details[:15]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
