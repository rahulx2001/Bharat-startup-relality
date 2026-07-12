"""NVIDIA NIM API helpers for article parsing and startup enrichment."""
from __future__ import annotations

import json
import re
from typing import Any

from .config import NVIDIA_API_KEY, NVIDIA_BASE_URL, NVIDIA_MODEL
from .prompts import SIGNAL_SYSTEM_PROMPT, enrich_system_prompt
from .quality import profile_score


def _client():
    if not NVIDIA_API_KEY:
        raise RuntimeError("NVIDIA_API_KEY is not set")
    from openai import OpenAI  # cloud NIM only; lazy so pure helpers import without the SDK

    return OpenAI(base_url=NVIDIA_BASE_URL, api_key=NVIDIA_API_KEY)


def _extract_json(text: str) -> Any:
    text = (text or "").strip()
    if not text:
        raise ValueError("Empty LLM response")

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def _chat(system: str, user: str, temperature: float = 0.2, retries: int = 5) -> str:
    import time

    last_error = None
    for attempt in range(retries):
        try:
            response = _client().chat.completions.create(
                model=NVIDIA_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                max_tokens=8192,
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            last_error = exc
            message = str(exc).lower()
            if "429" in message or "rate" in message or "too many" in message:
                wait = min(120, 20 * (attempt + 1))
                print(f"[llm] Rate limited — waiting {wait}s (attempt {attempt + 1}/{retries})")
                time.sleep(wait)
                continue
            raise
    raise last_error  # type: ignore[misc]


def extract_signals(articles: list[dict[str, Any]], known_names: list[str]) -> list[dict[str, Any]]:
    """Turn news articles into startup signals."""
    if not articles:
        return []

    known = ", ".join(known_names[:120])
    payload = json.dumps(articles, ensure_ascii=False, indent=2)
    system = SIGNAL_SYSTEM_PROMPT
    user = (
        f"Known startups already in database: {known}\n\n"
        f"Articles:\n{payload}\n\n"
        "Prefer updates for known startups when news mentions them. "
        "Only add new startups when the article clearly names one Indian company."
    )

    raw = _chat(system, user)
    parsed = _extract_json(raw)
    signals = parsed.get("signals", parsed if isinstance(parsed, list) else [])
    cleaned = []
    for item in signals:
        name = (item.get("startup_name") or "").strip()
        status = (item.get("status") or "").strip()
        if not name or status not in {"Shut Down", "Struggling", "Pivoted", "Comeback", "Recovery"}:
            continue
        cleaned.append(
            {
                "startup_name": name,
                "status": status,
                "headline": item.get("headline") or "",
                "source_url": item.get("source_url") or "",
                "date": item.get("date") or "",
                "confidence": float(item.get("confidence") or 0.5),
            }
        )
    print(f"[llm] Extracted {len(cleaned)} startup signals")
    return cleaned


def _detailed_schema_hint() -> dict[str, Any]:
    """Schema with explicit depth requirements for research outputs."""
    return {
        "startup_name": "string",
        "status": "Shut Down | Struggling | Pivoted | Comeback | Recovery",
        "year_founded": "number or null",
        "year_died": "number or null",
        "funding_burned_usd": "number — use funding_lookup/existing; never invent",
        "peak_valuation": "number or null",
        "employees": "number or null",
        "category": "string — one clear sector label",
        "headquarters": "string — city/region in India when known",
        "short_summary": "string — 1-2 dense sentences with numbers/dates (min ~80 chars)",
        "value_proposition": "string — 3-5 sentences: product, customer, scale, positioning (min ~180 chars)",
        "cause_of_death": "string or null — detailed research paragraph with ₹/$ , unit economics, governance",
        "failure_reason": "string — comma-separated key reasons",
        "founders": ["string — full names"],
        "investors": ["string — firm names"],
        "timeline": [{"date": "Mon YYYY or YYYY", "event": "specific event"}],
        "insights": ["string — ≥6 concrete market/strategy insights"],
        "lessons": ["string — ≥4 founder lessons"],
        "opportunity_score": {
            "rebuild_difficulty": "1-5",
            "scalability": "1-5",
            "market_potential": "1-5",
        },
        "market_today": "string — 3-5 sentences on India market after this company",
        "ai_rebuild": {
            "name": "string",
            "description": "string — 2-3 sentences",
            "tech_stack": ["string — ≥5 items"],
            "execution_plan": ["string — ≥5 steps"],
            "innovative": ["string — ≥5 moat points"],
            "monetization": "string — specific ₹ revenue model",
        },
        "sources": [{"title": "string", "url": "string"}],
        "profile_tier": "gold when checklist met",
    }


def _log_research_depth(entry: dict[str, Any], label: str) -> None:
    """Print quality score so thin research is visible in pipeline logs."""
    score = profile_score(entry)
    name = entry.get("startup_name") or "?"
    print(
        f"[llm] Research depth for {name} ({label}): "
        f"tier={score['tier']} score={score['score']} "
        f"complete={score['complete']} missing={score['missing']}"
    )
    if not score["complete"]:
        print(
            f"[llm] WARNING: {name} is below gold research depth. "
            "System prompt requires detailed research — review sources or re-enrich."
        )


def enrich_startup(signal: dict[str, Any], funding: dict[str, Any], existing: dict[str, Any] | None) -> dict[str, Any]:
    """Generate or refresh a full graveyard.json startup entry (detailed research required)."""
    schema_hint = _detailed_schema_hint()
    mode = "refresh" if existing else "new"

    context = {
        "research_mode": mode,
        "instruction": (
            "Apply RESEARCH_SYSTEM_RULES. "
            + (
                "This is a NEW startup being added — produce a full detailed dossier."
                if mode == "new"
                else "This is a REFRESH — deepen gaps, never shrink a detailed profile."
            )
        ),
        "signal": signal,
        "funding_lookup": funding,
        "existing_entry": existing,
        "schema": schema_hint,
        "depth_targets": {
            "timeline_min": 8,
            "insights_min": 6,
            "lessons_min": 4,
            "ai_rebuild_lists_min": 5,
        },
    }
    system = enrich_system_prompt(mode=mode)
    user = json.dumps(context, ensure_ascii=False, indent=2)
    raw = _chat(system, user, temperature=0.3)
    entry = _extract_json(raw)
    if not isinstance(entry, dict):
        raise ValueError("enrich_startup expected a JSON object from the model")

    csv_funding = funding.get("funding_burned_usd") or 0
    existing_funding = (existing or {}).get("funding_burned_usd") or 0
    if csv_funding and csv_funding >= existing_funding:
        entry["funding_burned_usd"] = csv_funding
    elif existing_funding:
        entry["funding_burned_usd"] = existing_funding
    if funding.get("category") and not entry.get("category"):
        entry["category"] = funding["category"]
    if funding.get("headquarters") and not entry.get("headquarters"):
        entry["headquarters"] = funding["headquarters"]
    if funding.get("investors") and not entry.get("investors"):
        entry["investors"] = funding["investors"]

    if signal.get("source_url"):
        sources = entry.get("sources") or []
        sources.append({"title": signal.get("headline") or "News update", "url": signal["source_url"]})
        entry["sources"] = sources[:8]

    entry["startup_name"] = entry.get("startup_name") or signal["startup_name"]
    entry["status"] = signal.get("status") or entry.get("status")
    entry["sources"] = _normalize_sources(entry.get("sources"))

    depth = profile_score(entry)
    if depth["complete"]:
        entry["profile_tier"] = "gold"
    elif not entry.get("profile_tier"):
        entry["profile_tier"] = depth["tier"]

    _log_research_depth(entry, mode)
    return entry


def _normalize_sources(sources: Any) -> list[dict[str, str]]:
    cleaned: list[dict[str, str]] = []
    for item in sources or []:
        if isinstance(item, dict):
            title = str(item.get("title", "")).strip()
            url = str(item.get("url", "")).strip()
            if title or url:
                cleaned.append({"title": title or "Source", "url": url})
        elif isinstance(item, str) and item.strip():
            text = item.strip()
            if text.startswith("{") and "title" in text:
                try:
                    import ast

                    parsed = ast.literal_eval(text)
                    if isinstance(parsed, dict):
                        cleaned.append(
                            {
                                "title": str(parsed.get("title", "Source")),
                                "url": str(parsed.get("url", "")),
                            }
                        )
                        continue
                except (SyntaxError, ValueError):
                    pass
            cleaned.append({"title": text[:120], "url": ""})
    return cleaned[:6]


def enrich_profile_full(existing: dict[str, Any], funding: dict[str, Any], gold_example: dict[str, Any]) -> dict[str, Any]:
    """BluSmart-level deep enrichment for an existing startup profile."""
    schema_hint = _detailed_schema_hint()
    schema_hint["profile_tier"] = "gold"

    system = enrich_system_prompt(mode="gold")
    user = json.dumps(
        {
            "research_mode": "gold",
            "instruction": (
                "Apply RESEARCH_SYSTEM_RULES at maximum depth. "
                "Match or exceed the gold_standard_example structure and richness."
            ),
            "gold_standard_example": {
                "startup_name": gold_example.get("startup_name"),
                "short_summary": gold_example.get("short_summary"),
                "value_proposition": gold_example.get("value_proposition"),
                "cause_of_death": gold_example.get("cause_of_death"),
                "timeline_count": len(gold_example.get("timeline") or []),
                "insights_count": len(gold_example.get("insights") or []),
                "ai_rebuild": gold_example.get("ai_rebuild"),
            },
            "existing_entry": existing,
            "funding_lookup": funding,
            "schema": schema_hint,
            "depth_targets": {
                "timeline_min": 8,
                "insights_min": 6,
                "lessons_min": 4,
                "ai_rebuild_lists_min": 5,
            },
        },
        ensure_ascii=False,
        indent=2,
    )

    raw = _chat(system, user, temperature=0.25)
    entry = _extract_json(raw)
    if not isinstance(entry, dict):
        raise ValueError("enrich_profile_full expected a JSON object from the model")

    entry["startup_name"] = existing.get("startup_name") or entry.get("startup_name")
    entry["status"] = existing.get("status") or entry.get("status")
    entry["profile_tier"] = "gold"

    csv_funding = funding.get("funding_burned_usd") or 0
    existing_funding = existing.get("funding_burned_usd") or 0
    entry["funding_burned_usd"] = max(existing_funding, csv_funding, entry.get("funding_burned_usd") or 0)

    entry["sources"] = _normalize_sources(entry.get("sources") or existing.get("sources"))
    _log_research_depth(entry, "gold")
    return entry