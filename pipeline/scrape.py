"""Scrape Indian startup news from RSS feeds."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import feedparser
import requests

from .config import (
    ARTICLES_CACHE,
    CACHE_DIR,
    FAILURE_KEYWORDS,
    MAX_ARTICLES_PER_RUN,
    RSS_FEEDS,
    SEEN_CACHE,
)

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": "StartupGraveyardBot/1.0 (+https://github.com/startup-graveyard)",
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    }
)


def _load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _save_json(path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")


def _matches_keywords(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in FAILURE_KEYWORDS)


def _parse_date(entry: dict[str, Any]) -> str:
    for key in ("published_parsed", "updated_parsed"):
        parsed = entry.get(key)
        if parsed:
            return datetime(*parsed[:6], tzinfo=timezone.utc).date().isoformat()
    return datetime.now(timezone.utc).date().isoformat()


def fetch_articles(force: bool = False) -> list[dict[str, Any]]:
    """Fetch and cache relevant startup news articles."""
    if not force and ARTICLES_CACHE.exists():
        cached = _load_json(ARTICLES_CACHE, [])
        if cached:
            return cached[:MAX_ARTICLES_PER_RUN]

    seen_urls = set(_load_json(SEEN_CACHE, []))
    articles: list[dict[str, Any]] = []

    for source, feed_url in RSS_FEEDS:
        try:
            response = SESSION.get(feed_url, timeout=20)
            response.raise_for_status()
            feed = feedparser.parse(response.content)
        except requests.RequestException as exc:
            print(f"[scrape] Skipping {source}: {exc}")
            continue

        for entry in feed.entries:
            title = (entry.get("title") or "").strip()
            link = (entry.get("link") or "").strip()
            summary = re.sub(r"<[^>]+>", " ", entry.get("summary", "") or "")
            summary = re.sub(r"\s+", " ", summary).strip()

            if not title or not link:
                continue

            blob = f"{title} {summary}"
            if not _matches_keywords(blob):
                continue

            normalized = _normalize_url(link)
            if normalized in seen_urls:
                continue

            articles.append(
                {
                    "source": source,
                    "title": title,
                    "summary": summary[:500],
                    "url": link,
                    "date": _parse_date(entry),
                }
            )
            seen_urls.add(normalized)

            if len(articles) >= MAX_ARTICLES_PER_RUN:
                break

        if len(articles) >= MAX_ARTICLES_PER_RUN:
            break

    articles.sort(key=lambda item: item["date"], reverse=True)
    _save_json(ARTICLES_CACHE, articles)
    _save_json(SEEN_CACHE, sorted(seen_urls))
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[scrape] Found {len(articles)} relevant articles")
    return articles