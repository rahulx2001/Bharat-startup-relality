"""Profile completeness scoring — BluSmart is the gold standard."""
from __future__ import annotations

from typing import Any

from .prompts import RESEARCH_MINIMUMS

REQUIRED_STATUS = {"Shut Down", "Struggling", "Pivoted", "Comeback", "Recovery", "Crisis", "Layoffs"}


def _len_text(value: Any, minimum: int = 80) -> bool:
    return isinstance(value, str) and len(value.strip()) >= minimum


def profile_score(startup: dict[str, Any]) -> dict[str, Any]:
    """Return score 0-100 and missing fields list.

    Thresholds follow RESEARCH_SYSTEM_RULES / RESEARCH_MINIMUMS so thin
    auto-added startups fail the gold bar until re-researched.
    """
    m = RESEARCH_MINIMUMS
    status = (startup.get("status") or "").strip()
    distress = status in {"Shut Down", "Struggling", "Crisis", "Layoffs"}
    cause_ok = _len_text(startup.get("cause_of_death"), m["cause_of_death_chars"])
    if not distress:
        # Pivoted / Comeback / Recovery may use long failure_reason as narrative
        cause_ok = cause_ok or _len_text(startup.get("failure_reason"), 80)

    checks: list[tuple[str, bool, int]] = [
        ("value_proposition", _len_text(startup.get("value_proposition"), m["value_proposition_chars"]), 10),
        ("cause_of_death", cause_ok, 12),
        ("short_summary", _len_text(startup.get("short_summary"), m["short_summary_chars"]), 5),
        ("timeline", len(startup.get("timeline") or []) >= m["timeline_events"], 12),
        ("insights", len(startup.get("insights") or []) >= m["insights"], 10),
        ("lessons", len(startup.get("lessons") or []) >= m["lessons"], 5),
        ("market_today", _len_text(startup.get("market_today"), m["market_today_chars"]), 8),
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
    m = RESEARCH_MINIMUMS
    return (
        _len_text(rebuild.get("description"), 80)
        and len(rebuild.get("tech_stack") or []) >= m["ai_rebuild_tech_stack"]
        and len(rebuild.get("execution_plan") or []) >= m["ai_rebuild_execution_plan"]
        and len(rebuild.get("innovative") or []) >= m["ai_rebuild_innovative"]
        and _len_text(rebuild.get("monetization"), 40)
    )


def needs_enrichment(startup: dict[str, Any]) -> bool:
    return not profile_score(startup)["complete"]