"""Hard research-quality gate for startup profiles.

Prompt rules alone are not enough. This module decides whether a researched
profile is deep enough to enter (or update) the database.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .prompts import RESEARCH_MINIMUMS
from .quality import profile_score


DISTRESS_STATUSES = {"Shut Down", "Struggling", "Crisis", "Layoffs"}


@dataclass
class GateResult:
    """Outcome of research quality evaluation."""

    accepted: bool
    score: int
    tier: str
    complete: bool
    missing: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    is_new: bool = False

    def summary(self) -> str:
        status = "ACCEPT" if self.accepted else "REJECT"
        miss = ", ".join(self.missing) if self.missing else "—"
        return (
            f"{status} tier={self.tier} score={self.score} "
            f"complete={self.complete} missing=[{miss}]"
        )


def _len_text(value: Any, minimum: int) -> bool:
    return isinstance(value, str) and len(value.strip()) >= minimum


def _source_urls(entry: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    for item in entry.get("sources") or []:
        if isinstance(item, dict):
            url = str(item.get("url") or "").strip()
            if url.startswith("http"):
                urls.append(url)
    return urls


def _has_concrete_signal(text: str) -> bool:
    """Heuristic: research text should include numbers, currency, or years."""
    if not text:
        return False
    import re

    return bool(
        re.search(r"\d", text)
        or "₹" in text
        or "$" in text
        or re.search(r"20\d{2}", text)
    )


def evaluate_research(
    entry: dict[str, Any],
    *,
    is_new: bool = False,
    require_gold: bool | None = None,
) -> GateResult:
    """Evaluate whether a profile meets research standards.

    require_gold:
      - True  → must be gold/complete to accept
      - False → accept any structurally valid entry (not used for new adds)
      - None  → default: require gold for new startups, gold for updates too
                when RESEARCH_REQUIRE_GOLD is enabled (caller passes explicit)
    """
    from .config import research_require_gold_for_new, research_require_gold_for_update

    if require_gold is None:
        require_gold = research_require_gold_for_new() if is_new else research_require_gold_for_update()

    depth = profile_score(entry)
    missing = list(depth["missing"])
    reasons: list[str] = []
    m = RESEARCH_MINIMUMS

    name = (entry.get("startup_name") or "").strip()
    if not name:
        missing.append("startup_name")
        reasons.append("missing startup_name")

    status = (entry.get("status") or "").strip()
    if not status:
        missing.append("status")
        reasons.append("missing status")

    # Evidence: at least one http(s) source URL
    urls = _source_urls(entry)
    min_sources = 1 if is_new else 1
    if len(urls) < min_sources:
        missing.append("sources_with_url")
        reasons.append("need ≥1 source with http(s) URL")

    # Founders expected on new detailed dossiers
    founders = [f for f in (entry.get("founders") or []) if str(f).strip()]
    if is_new and len(founders) < 1:
        missing.append("founders")
        reasons.append("new startup research must include founder names when public")

    # Distress narratives
    if status in DISTRESS_STATUSES:
        if not _len_text(entry.get("cause_of_death"), m["cause_of_death_chars"]):
            if "cause_of_death" not in missing:
                missing.append("cause_of_death")
            reasons.append("distress status requires detailed cause_of_death")

    # Concrete numbers somewhere in core narrative
    narrative = " ".join(
        str(entry.get(k) or "")
        for k in ("short_summary", "value_proposition", "cause_of_death", "failure_reason")
    )
    if not _has_concrete_signal(narrative):
        missing.append("concrete_facts")
        reasons.append("core narrative lacks numbers/dates/currency (too vague)")

    # Timeline event quality: events should not be empty strings
    timeline = entry.get("timeline") or []
    if isinstance(timeline, list):
        weak = sum(1 for t in timeline if not (isinstance(t, dict) and t.get("event")))
        if weak:
            reasons.append(f"{weak} timeline rows missing event text")

    # Deduplicate missing while preserving order
    seen: set[str] = set()
    missing_unique: list[str] = []
    for item in missing:
        if item not in seen:
            seen.add(item)
            missing_unique.append(item)

    # Hard blockers for gold acceptance.
    # New startups must have real source URLs; legacy catalog rows can pass on
    # score completeness without http sources (many predate URL-normalized sources).
    hard_blockers = {"concrete_facts", "startup_name", "status"}
    if is_new:
        hard_blockers.add("founders")
        hard_blockers.add("sources_with_url")
    if status in DISTRESS_STATUSES:
        # only hard-block cause when depth score also lacks it (profile_score missing)
        if "cause_of_death" in missing:
            hard_blockers.add("cause_of_death")


    blocked = [m for m in missing_unique if m in hard_blockers]
    score_ok = depth["score"] >= 85
    # profile_score "complete" means gold bar on weighted fields
    complete = bool(depth["complete"] and not blocked)

    if require_gold:
        # Accept gold-tier dossiers: high score + no hard blockers.
        # Soft gaps (e.g. insights 5/6 on an 85+ profile) do not reject if score_ok.
        accepted = score_ok and not blocked and bool(name and status)
        if is_new and depth["score"] < 85:
            accepted = False
        # Brand-new rows still need core structure, not a bare 85 from weird weights
        if is_new and any(
            m in missing_unique
            for m in ("value_proposition", "timeline", "ai_rebuild", "ai_rebuild_detail", "short_summary")
        ):
            accepted = False
    else:
        accepted = bool(name and status and entry.get("short_summary"))

    if blocked:
        for b in blocked:
            if b not in {r.split()[0] for r in reasons}:
                reasons.append(f"hard blocker: {b}")

    return GateResult(
        accepted=accepted,
        score=depth["score"],
        tier=depth["tier"],
        complete=complete,
        missing=missing_unique,
        reasons=reasons,
        is_new=is_new,
    )


def merge_research(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Merge repair pass into base, preferring longer/richer values."""
    if not base:
        return dict(patch or {})
    if not patch:
        return dict(base)

    out = dict(base)
    for key, value in patch.items():
        if value in (None, "", [], {}):
            continue
        current = out.get(key)
        if key in {"timeline", "insights", "lessons", "founders", "investors"}:
            merged: list = []
            seen: set[str] = set()
            for item in (current or []) + (value or []):
                token = repr(item)
                if token not in seen:
                    seen.add(token)
                    merged.append(item)
            # caps
            limit = 16 if key == "timeline" else 12
            out[key] = merged[:limit]
        elif key == "sources":
            merged_s: list = []
            seen_s: set[str] = set()
            for item in (current or []) + (value or []):
                if isinstance(item, dict):
                    token = f"{item.get('title')}|{item.get('url')}"
                else:
                    token = str(item)
                if token not in seen_s:
                    seen_s.add(token)
                    merged_s.append(item)
            out[key] = merged_s[:10]
        elif key == "ai_rebuild" and isinstance(value, dict):
            cur = dict(current) if isinstance(current, dict) else {}
            for rk, rv in value.items():
                if rv in (None, "", [], {}):
                    continue
                if rk in {"tech_stack", "execution_plan", "innovative"} and isinstance(rv, list):
                    base_list = list(cur.get(rk) or [])
                    for item in rv:
                        if item not in base_list:
                            base_list.append(item)
                    cur[rk] = base_list
                elif isinstance(rv, str) and isinstance(cur.get(rk), str):
                    cur[rk] = rv if len(rv) >= len(cur.get(rk) or "") else cur[rk]
                else:
                    cur[rk] = rv
            out[key] = cur
        elif key == "funding_burned_usd":
            try:
                out[key] = max(int(current or 0), int(value or 0))
            except (TypeError, ValueError):
                out[key] = value
        elif isinstance(value, str) and isinstance(current, str):
            out[key] = value if len(value.strip()) >= len(current.strip()) else current
        else:
            out[key] = value
    return out
