"""Identity integrity checks — reject wrong-company LLM dossiers."""
from __future__ import annotations

import re
from typing import Any

# Brands that repeatedly appeared as LLM confabulations in this project
PHANTOM_BRANDS = (
    "zolve",
    "zetwerk",
    "zetabox",
    "zostel",
)


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def own_name_keys(startup_name: str) -> set[str]:
    name = (startup_name or "").strip()
    keys: set[str] = set()
    if not name:
        return keys
    keys.add(_norm(name))
    parts = [p for p in re.sub(r"[^a-z0-9]+", " ", name.lower()).split() if len(p) >= 4]
    if parts:
        keys.add(parts[0])
    # common aliases
    aliases = {
        "byjus": {"byju", "byjus"},
        "hikemessenger": {"hike"},
        "mobilepremierleague": {"mpl"},
        "urbanclapurbancompany": {"urbanclap", "urbancompany"},
        "urbancompany": {"urbanclap", "urbancompany"},
        "housingcom": {"housing"},
        "olaelectric": {"olaelectric"},
        "oyorooms": {"oyo"},
        "taxiforsure": {"taxiforsure"},
        "goodglammgroup": {"goodglamm", "glamm"},
        "whitehatjr": {"whitehat"},
    }
    nk = _norm(name)
    keys |= aliases.get(nk, set())
    return {k for k in keys if len(k) >= 3}


def text_mentions_own(startup_name: str, text: str) -> bool:
    blob = _norm(text)
    if not blob:
        return False
    return any(k in blob for k in own_name_keys(startup_name))


def identity_problems(entry: dict[str, Any]) -> list[str]:
    """Return list of identity integrity problems (empty if OK)."""
    name = (entry.get("startup_name") or "").strip()
    summary = str(entry.get("short_summary") or "")
    cause = str(entry.get("cause_of_death") or "")
    vp = str(entry.get("value_proposition") or "")
    problems: list[str] = []

    if not name:
        return ["missing_startup_name"]

    core = f"{summary}\n{vp}"
    if not text_mentions_own(name, core):
        problems.append("own_name_missing_from_summary_or_value_prop")

    # Opening brand is a phantom / wrong company
    m = re.match(r"^([A-Za-z][A-Za-z0-9.&']+)", summary.strip())
    if m:
        first = m.group(1).lower()
        if first in PHANTOM_BRANDS and first not in name.lower():
            problems.append(f"summary_opens_with_phantom:{first}")

    # Phantom brand dominates opening of summary
    sl = summary.lower().lstrip()
    for p in PHANTOM_BRANDS:
        if sl.startswith(p) and p not in name.lower():
            problems.append(f"summary_about:{p}")
        # cause about phantom without own name
        cl = cause.lower()
        if p in cl[:120] and p not in name.lower() and not text_mentions_own(name, cause):
            problems.append(f"cause_about:{p}")

    # Source titles/URLs about phantom confabulations only.
    # Competitor names (Zomato/Flipkart) in a real acquisition headline can be valid.
    own = own_name_keys(name)
    for item in entry.get("sources") or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").lower()
        url = str(item.get("url") or "").lower()
        for p in PHANTOM_BRANDS:
            if (p in title or p in url) and p not in name.lower():
                if not any(k in _norm(title + url) for k in own):
                    problems.append(f"source_about:{p}")
                    break

    # Special cases called out by audit
    if name == "Swiggy" and "zomato" in summary.lower()[:90] and "swiggy" not in summary.lower()[:90]:
        problems.append("swiggy_summary_about_zomato")
    if name == "Housing.com" and "food delivery" in summary.lower() and "housing" not in summary.lower():
        problems.append("housing_summary_about_food")
    if name == "Grofers" and "zostel" in (summary + cause + vp).lower():
        problems.append("grofers_about_zostel")
    if name == "Taxiforsure" and "electric bus" in summary.lower():
        problems.append("taxiforsure_wrong_product")

    # dedupe preserve order
    seen: set[str] = set()
    out: list[str] = []
    for p in problems:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def identity_ok(entry: dict[str, Any]) -> bool:
    return not identity_problems(entry)
