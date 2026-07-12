"""NVIDIA NIM API helpers for article parsing and startup enrichment.

Cloud-only OpenAI-compatible client. Research depth is enforced by
`research_gate` + repair passes — not prompts alone.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any

from .config import (
    nvidia_api_key,
    nvidia_base_url,
    nvidia_max_tokens,
    nvidia_model,
    research_max_repair_passes,
)
from .identity import identity_problems
from .prompts import SIGNAL_SYSTEM_PROMPT, enrich_system_prompt
from .quality import profile_score
from .research_gate import GateResult, evaluate_research, merge_research


def _client():
    api_key = nvidia_api_key()
    if not api_key:
        raise RuntimeError("NVIDIA_API_KEY is not set")
    from openai import OpenAI

    return OpenAI(base_url=nvidia_base_url(), api_key=api_key)


def _extract_json(text: str) -> Any:
    text = (text or "").strip()
    if not text:
        raise ValueError("Empty LLM response")

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    for open_c, close_c in (("{", "}"), ("[", "]")):
        start = text.find(open_c)
        end = text.rfind(close_c)
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError(f"Could not parse JSON from LLM response: {text[:200]!r}")


def _is_retryable(exc: BaseException) -> bool:
    message = str(exc).lower()
    return any(
        m in message
        for m in ("429", "rate", "too many", "timeout", "temporar", "503", "502")
    )


def _is_json_mode_unsupported(exc: BaseException) -> bool:
    message = str(exc).lower()
    return any(
        m in message
        for m in (
            "response_format",
            "json_object",
            "json mode",
            "unsupported",
            "unknown parameter",
            "extra inputs are not permitted",
        )
    )


def _chat(system: str, user: str, temperature: float = 0.2, retries: int = 5) -> str:
    last_error: BaseException | None = None
    use_json_mode = True
    model = nvidia_model()
    max_tokens = nvidia_max_tokens()

    for attempt in range(retries):
        try:
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if use_json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            response = _client().chat.completions.create(**kwargs)
            return response.choices[0].message.content or ""
        except Exception as exc:
            last_error = exc
            if use_json_mode and _is_json_mode_unsupported(exc):
                print(f"[llm] JSON mode unsupported for {model}; falling back")
                use_json_mode = False
                continue
            if _is_retryable(exc):
                wait = min(120, 20 * (attempt + 1))
                print(f"[llm] Transient error — waiting {wait}s ({attempt + 1}/{retries})")
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
    user = (
        f"Known startups already in database: {known}\n\n"
        f"Articles:\n{payload}\n\n"
        "Prefer updates for known startups when news mentions them. "
        "Only add new startups when the article clearly names one Indian company."
    )

    raw = _chat(SIGNAL_SYSTEM_PROMPT, user)
    parsed = _extract_json(raw)
    if isinstance(parsed, list):
        signals = parsed
    else:
        signals = parsed.get("signals", [])
    cleaned = []
    for item in signals:
        if not isinstance(item, dict):
            continue
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


def _apply_funding_and_sources(
    entry: dict[str, Any],
    signal: dict[str, Any] | None,
    funding: dict[str, Any],
    existing: dict[str, Any] | None,
) -> dict[str, Any]:
    csv_funding = funding.get("funding_burned_usd") or 0
    existing_funding = (existing or {}).get("funding_burned_usd") or 0
    entry_funding = entry.get("funding_burned_usd") or 0
    try:
        entry["funding_burned_usd"] = max(int(csv_funding or 0), int(existing_funding or 0), int(entry_funding or 0))
    except (TypeError, ValueError):
        pass

    if funding.get("category") and not entry.get("category"):
        entry["category"] = funding["category"]
    if funding.get("headquarters") and not entry.get("headquarters"):
        entry["headquarters"] = funding["headquarters"]
    if funding.get("investors") and not entry.get("investors"):
        entry["investors"] = funding["investors"]

    if signal and signal.get("source_url"):
        sources = entry.get("sources") or []
        sources.append({"title": signal.get("headline") or "News update", "url": signal["source_url"]})
        entry["sources"] = sources

    if signal:
        entry["startup_name"] = entry.get("startup_name") or signal.get("startup_name")
        entry["status"] = signal.get("status") or entry.get("status")

    if existing:
        entry["startup_name"] = existing.get("startup_name") or entry.get("startup_name")
        if not entry.get("status"):
            entry["status"] = existing.get("status")

    entry["sources"] = _normalize_sources(entry.get("sources") or (existing or {}).get("sources"))
    return entry


def _stamp_tier(entry: dict[str, Any], gate: GateResult) -> dict[str, Any]:
    if gate.accepted and gate.score >= 85:
        entry["profile_tier"] = "gold"
    else:
        entry["profile_tier"] = gate.tier
    entry["research_score"] = gate.score
    entry["research_missing"] = gate.missing
    return entry


def _log_gate(gate: GateResult, label: str, name: str) -> None:
    print(f"[research] {name} ({label}): {gate.summary()}")
    for reason in gate.reasons[:6]:
        print(f"[research]   • {reason}")


def enrich_startup(signal: dict[str, Any], funding: dict[str, Any], existing: dict[str, Any] | None) -> dict[str, Any]:
    """Single-pass research (prefer research_startup for gated production use)."""
    mode = "refresh" if existing else "new"
    schema_hint = _detailed_schema_hint()
    context = {
        "research_mode": mode,
        "instruction": (
            "Apply RESEARCH_SYSTEM_RULES. "
            + (
                "NEW startup — full detailed dossier; system will REJECT thin output."
                if mode == "new"
                else "REFRESH — deepen gaps, never shrink a detailed profile."
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
    raw = _chat(enrich_system_prompt(mode=mode), json.dumps(context, ensure_ascii=False, indent=2), temperature=0.3)
    entry = _extract_json(raw)
    if not isinstance(entry, dict):
        raise ValueError("enrich_startup expected a JSON object from the model")
    entry = _apply_funding_and_sources(entry, signal, funding, existing)
    gate = evaluate_research(entry, is_new=existing is None)
    entry = _stamp_tier(entry, gate)
    _log_gate(gate, mode, entry.get("startup_name") or "?")
    return entry


def repair_research(
    draft: dict[str, Any],
    *,
    signal: dict[str, Any] | None,
    funding: dict[str, Any],
    existing: dict[str, Any] | None,
    missing: list[str],
    reasons: list[str],
) -> dict[str, Any]:
    """Second-pass LLM call to fill gaps that failed the research gate."""
    context = {
        "research_mode": "repair",
        "missing_fields": missing,
        "gate_reasons": reasons,
        "partial_draft": draft,
        "signal": signal,
        "funding_lookup": funding,
        "existing_entry": existing,
        "schema": _detailed_schema_hint(),
        "instruction": (
            "Return a COMPLETE gold-depth JSON profile that fixes every missing field. "
            "Keep all strong facts from partial_draft."
        ),
    }
    raw = _chat(
        enrich_system_prompt(mode="repair"),
        json.dumps(context, ensure_ascii=False, indent=2),
        temperature=0.25,
    )
    patch = _extract_json(raw)
    if not isinstance(patch, dict):
        raise ValueError("repair_research expected a JSON object")
    merged = merge_research(draft, patch)
    return _apply_funding_and_sources(merged, signal, funding, existing)


def research_startup(
    signal: dict[str, Any],
    funding: dict[str, Any],
    existing: dict[str, Any] | None,
) -> tuple[dict[str, Any], GateResult]:
    """Research with automatic repair passes and hard gate evaluation.

    Returns (entry, gate). Caller must not persist if gate.accepted is False
    for new startups (when require-gold is enabled).
    """
    is_new = existing is None
    entry = enrich_startup(signal, funding, existing)
    gate = evaluate_research(entry, is_new=is_new)
    entry = _stamp_tier(entry, gate)

    passes = research_max_repair_passes()
    attempt = 0
    while not gate.accepted and attempt < passes:
        attempt += 1
        name = entry.get("startup_name") or signal.get("startup_name")
        print(f"[research] Repair pass {attempt}/{passes} for {name} — missing {gate.missing}")
        try:
            entry = repair_research(
                entry,
                signal=signal,
                funding=funding,
                existing=existing,
                missing=gate.missing,
                reasons=gate.reasons,
            )
        except Exception as exc:
            print(f"[research] Repair pass failed: {exc}")
            break
        gate = evaluate_research(entry, is_new=is_new)
        entry = _stamp_tier(entry, gate)
        _log_gate(gate, f"repair-{attempt}", name or "?")

    return entry, gate


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
    return cleaned[:8]


def enrich_profile_full(existing: dict[str, Any], funding: dict[str, Any], gold_example: dict[str, Any]) -> dict[str, Any]:
    """BluSmart-level deep enrichment with repair until gold (or max passes)."""
    schema_hint = _detailed_schema_hint()
    schema_hint["profile_tier"] = "gold"
    target_name = existing.get("startup_name") or ""
    system = enrich_system_prompt(mode="gold")
    user = json.dumps(
        {
            "research_mode": "gold",
            "target_company": target_name,
            "instruction": (
                f"Apply RESEARCH_SYSTEM_RULES at maximum depth for ONLY '{target_name}'. "
                f"short_summary MUST start with '{target_name}'. "
                "Match structure/depth of gold_standard_example but NEVER copy another company's story. "
                "System rejects thin output and wrong-identity dossiers."
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

    entry = _apply_funding_and_sources(entry, None, funding, existing)
    entry["startup_name"] = existing.get("startup_name") or entry.get("startup_name")
    entry["status"] = existing.get("status") or entry.get("status")

    gate = evaluate_research(entry, is_new=False, require_gold=True)
    entry = _stamp_tier(entry, gate)
    _log_gate(gate, "gold", entry.get("startup_name") or "?")

    passes = research_max_repair_passes()
    attempt = 0
    while not gate.accepted and attempt < passes:
        attempt += 1
        print(f"[research] Gold repair {attempt}/{passes} for {entry.get('startup_name')}")
        try:
            # Identity failures get a dedicated fix prompt
            mode = "identity_fix" if "identity_integrity" in gate.missing else "repair"
            if mode == "identity_fix":
                ctx = {
                    "research_mode": "identity_fix",
                    "target_company": existing.get("startup_name"),
                    "identity_problems": identity_problems(entry),
                    "partial_draft": entry,
                    "existing_entry": existing,
                    "funding_lookup": funding,
                    "schema": _detailed_schema_hint(),
                }
                raw = _chat(
                    enrich_system_prompt(mode="identity_fix"),
                    json.dumps(ctx, ensure_ascii=False, indent=2),
                    temperature=0.2,
                )
                patch = _extract_json(raw)
                if not isinstance(patch, dict):
                    raise ValueError("identity_fix expected JSON object")
                entry = merge_research(entry, patch)
                entry = _apply_funding_and_sources(entry, None, funding, existing)
            else:
                entry = repair_research(
                    entry,
                    signal=None,
                    funding=funding,
                    existing=existing,
                    missing=gate.missing,
                    reasons=gate.reasons,
                )
            entry["startup_name"] = existing.get("startup_name") or entry.get("startup_name")
            entry["status"] = existing.get("status") or entry.get("status")
        except Exception as exc:
            print(f"[research] Gold repair failed: {exc}")
            break
        gate = evaluate_research(entry, is_new=False, require_gold=True)
        entry = _stamp_tier(entry, gate)
        _log_gate(gate, f"gold-repair-{attempt}", entry.get("startup_name") or "?")

    if not gate.accepted:
        # Still return best effort for batch, but mark clearly
        entry["profile_tier"] = gate.tier
        entry["research_rejected"] = True
    return entry
