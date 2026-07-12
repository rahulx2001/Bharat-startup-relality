"""Re-stamp research metadata so JSON labels match the real gold gate.

Never leave profile_tier=gold / research_mode=gold when evaluate_research fails.
"""
from __future__ import annotations

from typing import Any

from .quality import profile_score
from .research_gate import evaluate_research
from .source_integrity import catalog_brand_tokens, source_integrity_problems


def restamp_entry(
    entry: dict[str, Any],
    *,
    catalog_tokens: dict[str, set[str]] | None = None,
) -> dict[str, Any]:
    """Mutate and return entry with honest research metadata."""
    score = profile_score(entry)
    gate = evaluate_research(
        entry,
        is_new=False,
        require_gold=True,
        catalog_tokens=catalog_tokens,
    )
    src_probs = source_integrity_problems(entry, catalog_tokens)
    passed = bool(gate.accepted and score["score"] >= 85 and not src_probs)

    entry["research_score"] = score["score"]
    entry["research_missing"] = list(gate.missing)
    entry["research_gate_reasons"] = list(gate.reasons[:12])

    if passed:
        entry["profile_tier"] = "gold"
        entry["research_status"] = "gold_pass"
        entry.pop("research_rejected", None)
        entry.pop("research_blocked_reason", None)
        # research_mode may remain as provenance of last enrich, but never imply pass
        if entry.get("research_mode") in {None, ""}:
            entry["research_mode"] = "verified"
    else:
        # Never present as gold when gate/source integrity fails
        entry["profile_tier"] = score["tier"] if score["tier"] != "gold" else (
            "silver" if score["score"] >= 60 else "bronze" if score["score"] >= 35 else "thin"
        )
        # Explicit demotion if score math said gold but evidence failed
        if score["tier"] == "gold" and not passed:
            entry["profile_tier"] = "silver" if score["score"] >= 85 else score["tier"]
        entry["research_status"] = "blocked"
        entry["research_rejected"] = True
        bits = []
        if src_probs:
            bits.append("source_integrity:" + ",".join(src_probs[:3]))
        if gate.missing:
            bits.append("gate:" + ",".join(gate.missing[:5]))
        entry["research_blocked_reason"] = "; ".join(bits) or "below gold research bar"
        # Clear misleading research_mode=gold stamp
        if entry.get("research_mode") == "gold":
            entry["research_mode"] = "unverified"
        if entry.get("research_upgraded") and not passed:
            entry["research_upgraded"] = False

    return entry


def restamp_all(startups: list[dict[str, Any]]) -> dict[str, Any]:
    """Re-stamp every startup; return stats."""
    catalog = catalog_brand_tokens(startups)
    gold = 0
    blocked = 0
    demoted = 0
    for s in startups:
        before_tier = s.get("profile_tier")
        restamp_entry(s, catalog_tokens=catalog)
        if s.get("research_status") == "gold_pass":
            gold += 1
        else:
            blocked += 1
        if before_tier == "gold" and s.get("profile_tier") != "gold":
            demoted += 1
    return {
        "total": len(startups),
        "gold_pass": gold,
        "blocked": blocked,
        "demoted_from_gold_label": demoted,
    }
