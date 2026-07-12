"""Catalog-aware source integrity (pure — no network I/O).

Flags foreign-brand article URLs/titles, publisher-root-only padding, and
slug/title brand mismatches. Used by the research gate as a hard blocker.
"""
from __future__ import annotations

import re
from typing import Any, Iterable
from urllib.parse import urlparse, unquote

# Tokens too generic to treat as company brands
_STOP_TOKENS = frozenset(
    {
        "india",
        "indian",
        "startup",
        "startups",
        "tech",
        "group",
        "company",
        "com",
        "app",
        "labs",
        "media",
        "news",
        "the",
        "and",
        "for",
        "with",
        "from",
        "into",
        "limited",
        "private",
        "pvt",
        "ltd",
        "inc",
        "llc",
        "www",
        "http",
        "https",
        "html",
        "htm",
        "cms",
        "articleshow",
        "article",
        "story",
        "stories",
        "post",
        "blog",
        "press",
        "coverage",
        "index",
    }
)

_PUBLISHER_ROOTS = frozenset(
    {
        "inc42.com",
        "yourstory.com",
        "entrackr.com",
        "economictimes.indiatimes.com",
        "business-standard.com",
        "livemint.com",
        "moneycontrol.com",
        "crunchbase.com",
        "techcrunch.com",
        "forbes.com",
        "forbesindia.com",
        "reuters.com",
        "medianama.com",
        "the-ken.com",
        "thehindu.com",
        "ndtv.com",
        "timesofindia.indiatimes.com",
    }
)


def brand_tokens_from_name(name: str) -> set[str]:
    """Extract significant brand tokens from a startup name."""
    raw = re.sub(r"[^a-z0-9]+", " ", (name or "").lower()).strip()
    tokens: set[str] = set()
    if not raw:
        return tokens
    parts = [p for p in raw.split() if p and p not in _STOP_TOKENS]
    for p in parts:
        # allow 3-letter brands (Koo, Oyo) and longer
        if len(p) >= 3:
            tokens.add(p)
    # joined form for multi-word brands
    joined = "".join(parts)
    if len(joined) >= 3:
        tokens.add(joined)
    # special aliases
    aliases = {
        "byjus": {"byju", "byjus"},
        "hikemessenger": {"hike"},
        "mobilepremierleague": {"mpl", "mobilepremierleague"},
        "urbanclapurbancompany": {"urbanclap", "urbancompany"},
        "urbancompany": {"urbanclap", "urbancompany"},
        "housingcom": {"housing"},
        "olaelectric": {"olaelectric", "ola"},
        "oyorooms": {"oyo"},
        "taxiforsure": {"taxiforsure"},
        "flipkartping": {"flipkartping", "ping"},
        "zomatoinstant": {"zomatoinstant"},
        "goodglammgroup": {"goodglamm", "glamm"},
        "whitehatjr": {"whitehat"},
        "pepperfry": {"pepperfry"},
        "lybrate": {"lybrate"},
        "practo": {"practo"},
        "koo": {"koo"},
        "swiggy": {"swiggy"},
        "zomato": {"zomato"},
        "paytm": {"paytm"},
        "unacademy": {"unacademy"},
    }
    for t in list(tokens):
        tokens |= aliases.get(t, set())
    return {t for t in tokens if len(t) >= 3 and t not in _STOP_TOKENS}


def catalog_brand_tokens(startups: Iterable[dict[str, Any]]) -> dict[str, set[str]]:
    """Map startup_name -> brand tokens for the full catalog."""
    out: dict[str, set[str]] = {}
    for s in startups or []:
        name = (s.get("startup_name") or "").strip()
        if not name:
            continue
        out[name] = brand_tokens_from_name(name)
    return out


def tokens_in_text(text: str) -> set[str]:
    raw = re.sub(r"[^a-z0-9]+", " ", unquote(text or "").lower())
    return {p for p in raw.split() if len(p) >= 4 and p not in _STOP_TOKENS}


def tokens_in_url(url: str) -> set[str]:
    try:
        parsed = urlparse(url or "")
    except Exception:
        return set()
    path = unquote(parsed.path or "")
    query = unquote(parsed.query or "")
    # include slug pieces; exclude host publisher names as brand evidence of subject
    host_bits = tokens_in_text(parsed.netloc or "")
    body = tokens_in_text(path + " " + query)
    # host tokens like "moneycontrol" are publishers, not startups
    return body - host_bits


def tokens_in_title(title: str) -> set[str]:
    return tokens_in_text(title or "")


def _is_publisher_root(url: str) -> bool:
    """True if URL is essentially a publisher homepage (no article path)."""
    try:
        parsed = urlparse(url or "")
    except Exception:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.netloc or "").lower().removeprefix("www.")
    path = (parsed.path or "").strip("/")
    # bare host or host with empty path
    if not path:
        return True
    # /en /india /search only
    if path.lower() in {"en", "in", "india", "search", "tech", "startups"}:
        return True
    # known publisher root with no article slug depth
    if host in _PUBLISHER_ROOTS and path.count("/") == 0 and len(path) < 12:
        # e.g. inc42.com/ or yourstory.com/ — still root-ish
        if path in {"", "en", "in"}:
            return True
        # single short segment still root padding
        if len(path) <= 8 and path.isalpha():
            return True
    # exact publisher homepage forms
    if host in _PUBLISHER_ROOTS and path == "":
        return True
    return False


def _subject_tokens(entry: dict[str, Any], catalog: dict[str, set[str]]) -> set[str]:
    name = (entry.get("startup_name") or "").strip()
    return set(catalog.get(name) or brand_tokens_from_name(name))


def _other_catalog_tokens(subject: str, catalog: dict[str, set[str]]) -> dict[str, set[str]]:
    return {n: toks for n, toks in catalog.items() if n != subject and toks}


def _dominant_foreign_brand(
    tokens: set[str],
    subject_tokens: set[str],
    others: dict[str, set[str]],
) -> str | None:
    """If tokens clearly match another catalog brand more than the subject, return that brand name."""
    if not tokens:
        return None
    subject_hits = tokens & subject_tokens
    best_other = None
    best_score = 0
    for other_name, otoks in others.items():
        hits = tokens & otoks
        # require a distinctive foreign hit of length >=4 not in subject
        distinctive = {h for h in hits if h not in subject_tokens and len(h) >= 4}
        if not distinctive:
            continue
        score = sum(len(h) for h in distinctive)
        if score > best_score:
            best_score = score
            best_other = other_name
    if best_other and best_score > 0:
        # foreign wins if subject has no token hit in this field, or foreign is longer match
        if not subject_hits:
            return best_other
        # both present — still foreign if foreign slug is primary (e.g. zomato in path, swiggy nowhere)
        foreign_only = best_score >= max(sum(len(h) for h in subject_hits), 4) * 1.5
        if foreign_only and not subject_hits:
            return best_other
        if not subject_hits:
            return best_other
    return None


def source_integrity_problems(
    entry: dict[str, Any],
    catalog_tokens: dict[str, set[str]] | None = None,
) -> list[str]:
    """Return source integrity problems for one startup entry (pure)."""
    name = (entry.get("startup_name") or "").strip()
    if not name:
        return ["missing_startup_name"]

    if catalog_tokens is None:
        catalog_tokens = {name: brand_tokens_from_name(name)}

    subject = _subject_tokens(entry, catalog_tokens)
    others = _other_catalog_tokens(name, catalog_tokens)
    problems: list[str] = []

    sources = [s for s in (entry.get("sources") or []) if isinstance(s, dict)]
    http_sources = []
    for s in sources:
        url = str(s.get("url") or "").strip()
        if url.startswith("http"):
            http_sources.append(s)

    if not http_sources:
        problems.append("no_http_sources")
        return problems

    on_topic = 0
    for s in http_sources:
        url = str(s.get("url") or "").strip()
        title = str(s.get("title") or "").strip()
        url_toks = tokens_in_url(url)
        title_toks = tokens_in_title(title)

        if _is_publisher_root(url):
            problems.append(f"publisher_root_only:{url}")
            continue

        foreign_url = _dominant_foreign_brand(url_toks, subject, others)
        foreign_title = _dominant_foreign_brand(title_toks, subject, others)

        # URL path about another catalog company
        if foreign_url and foreign_url != name:
            problems.append(f"foreign_brand_url:{foreign_url}:{url[:120]}")
            continue

        # Title about another catalog company while URL/title lacks subject
        if foreign_title and foreign_title != name:
            if not (title_toks & subject) and not (url_toks & subject):
                problems.append(f"foreign_brand_title:{foreign_title}:{title[:80]}")
                continue

        # Slug claims subject brand but title is about another brand
        if (url_toks & subject) and foreign_title and foreign_title != name:
            if not (title_toks & subject):
                problems.append(f"slug_title_brand_mismatch:{foreign_title}")
                continue

        # On-topic if subject token appears in URL path or title
        if (url_toks & subject) or (title_toks & subject):
            on_topic += 1
            continue

        # No subject signal and not already flagged — weak/off-topic article
        problems.append(f"offtopic_or_unbranded_source:{url[:120]}")

    if on_topic == 0:
        problems.append("no_on_topic_sources")

    # If every http source is publisher root only
    if http_sources and all(_is_publisher_root(str(s.get("url") or "")) for s in http_sources):
        if "no_on_topic_sources" not in problems:
            problems.append("all_sources_publisher_roots")

    # dedupe
    seen: set[str] = set()
    out: list[str] = []
    for p in problems:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def source_integrity_ok(entry: dict[str, Any], catalog_tokens: dict[str, set[str]] | None = None) -> bool:
    return not source_integrity_problems(entry, catalog_tokens)


def filter_valid_sources(
    entry: dict[str, Any],
    catalog_tokens: dict[str, set[str]] | None = None,
) -> list[dict[str, str]]:
    """Return only sources that would not individually fail foreign/root checks.

    Used by remediation to strip bad sources before re-audit.
    """
    name = (entry.get("startup_name") or "").strip()
    if catalog_tokens is None:
        catalog_tokens = {name: brand_tokens_from_name(name)}
    subject = _subject_tokens(entry, catalog_tokens)
    others = _other_catalog_tokens(name, catalog_tokens)
    kept: list[dict[str, str]] = []
    for s in entry.get("sources") or []:
        if not isinstance(s, dict):
            continue
        url = str(s.get("url") or "").strip()
        title = str(s.get("title") or "").strip()
        if not url.startswith("http"):
            continue
        if _is_publisher_root(url):
            continue
        url_toks = tokens_in_url(url)
        title_toks = tokens_in_title(title)
        if _dominant_foreign_brand(url_toks, subject, others):
            continue
        if _dominant_foreign_brand(title_toks, subject, others) and not (title_toks & subject) and not (url_toks & subject):
            continue
        if not ((url_toks & subject) or (title_toks & subject)):
            continue
        kept.append({"title": title or "Source", "url": url})
    return kept
