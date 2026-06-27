"""Profile completeness scoring — BluSmart is the gold standard."""
from __future__ import annotations

from typing import Any

REQUIRED_STATUS = {"Shut Down", "Struggling", "Pivoted", "Comeback", "Recovery", "Crisis", "Layoffs"}


def _len_text(value: Any, minimum: int = 80) -> bool:
    return isinstance(value, str) and len(value.strip()) >= minimum


def profile_score(startup: dict[str, Any]) -> dict[str, Any]:
    """Return score 0-100 and missing fields list."""
    checks: list[tuple[str, bool, int]] = [
        ("value_proposition", _len_text(startup.get("value_proposition"), 120), 10),
        ("cause_of_death", _len_text(startup.get("cause_of_death"), 100), 12),
        ("short_summary", _len_text(startup.get("short_summary"), 60), 5),
        ("timeline", len(startup.get("timeline") or []) >= 6, 12),
        ("insights", len(startup.get("insights") or []) >= 5, 10),
        ("lessons", len(startup.get("lessons") or []) >= 3, 5),
        ("market_today", _len_text(startup.get("market_today"), 100), 8),
        ("opportunity_score", bool(startup.get("opportunity_score")), 5),
        ("ai_rebuild", bool((startup.get("ai_rebuild") or {}).get("name")), 15),
        ("ai_rebuild_detail", _ai_rebuild_rich(startup.get("ai_rebuild")), 18),
    ]

    score = 0
    missing = []
    for field, ok, weight in checks:
        if ok:
            score += weight
        else:
            missing.append(field)

    return {
        "score": score,
        "complete": score >= 85,
        "missing": missing,
        "tier": "gold" if score >= 85 else "silver" if score >= 60 else "bronze" if score >= 35 else "thin",
    }


def _ai_rebuild_rich(rebuild: dict | None) -> bool:
    if not rebuild:
        return False
    return (
        _len_text(rebuild.get("description"), 80)
        and len(rebuild.get("tech_stack") or []) >= 4
        and len(rebuild.get("execution_plan") or []) >= 4
        and len(rebuild.get("innovative") or []) >= 4
        and _len_text(rebuild.get("monetization"), 40)
    )


def needs_enrichment(startup: dict[str, Any]) -> bool:
    return not profile_score(startup)["complete"]