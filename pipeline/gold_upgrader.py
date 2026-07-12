"""DEPRECATED: do not fabricate gold dossiers.

Gold depth must come from cloud NIM research (`pipeline.llm.enrich_profile_full`
/ `research_startup`) or remain blocked with an explicit reason when research
cannot run (e.g. missing API key).

This module only classifies failures for honest audit artifacts.
"""
from __future__ import annotations

from typing import Any

from .quality import profile_score
from .research_gate import evaluate_research


def classify_failures(
    startups: list[dict[str, Any]],
    *,
    api_key_present: bool,
    block_reason_if_no_key: str = "missing NVIDIA_API_KEY — cloud NIM research not run",
) -> dict[str, Any]:
    """Return gold-pass names and blocked list (no silent gold)."""
    gold: list[str] = []
    blocked: list[dict[str, Any]] = []
    for s in startups:
        name = s.get("startup_name") or "?"
        score = profile_score(s)
        gate = evaluate_research(s, is_new=False, require_gold=True)
        passed = bool(gate.accepted and score["score"] >= 85)
        if passed:
            gold.append(name)
            continue
        reason = block_reason_if_no_key if not api_key_present else "below gold after research attempts or not yet enriched"
        blocked.append(
            {
                "startup_name": name,
                "status": s.get("status"),
                "score": score["score"],
                "tier": score["tier"],
                "missing": score["missing"],
                "gate_missing": gate.missing,
                "gate_reasons": gate.reasons,
                "blocked_reason": reason,
            }
        )
    return {
        "gold_pass_names": gold,
        "gold_pass": len(gold),
        "blocked": blocked,
        "blocked_count": len(blocked),
        "total": len(startups),
    }


def upgrade_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Not supported — refuse to template-pad to gold."""
    raise RuntimeError(
        "gold_upgrader.upgrade_entry is disabled: use cloud NIM enrich_profile_full "
        "or record a blocked reason. Template gold is forbidden."
    )


def upgrade_all(startups: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Not supported — refuse bulk template gold."""
    raise RuntimeError(
        "gold_upgrader.upgrade_all is disabled: use scripts/enrich_failing_nim.py "
        "with NVIDIA_API_KEY or classify_failures() for blocked lists."
    )
