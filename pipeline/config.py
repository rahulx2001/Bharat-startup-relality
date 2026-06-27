"""Pipeline configuration."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CACHE_DIR = ROOT / "pipeline" / "cache"

GRAVEYARD_JSON = DATA_DIR / "graveyard.json"
FUNDING_CSV = DATA_DIR / "funding.csv"
ARTICLES_CACHE = CACHE_DIR / "articles.json"
SEEN_CACHE = CACHE_DIR / "seen_urls.json"

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "meta/llama-3.1-70b-instruct")

MAX_NEW_STARTUPS_PER_RUN = int(os.getenv("MAX_NEW_STARTUPS_PER_RUN", "5"))
MAX_ARTICLES_PER_RUN = int(os.getenv("MAX_ARTICLES_PER_RUN", "40"))

RSS_FEEDS = [
    ("Inc42", "https://inc42.com/feed/"),
    ("YourStory", "https://yourstory.com/feed"),
    (
        "Google News — Indian startup failures",
        "https://news.google.com/rss/search?q=indian+startup+(shutdown+OR+layoffs+OR+insolvency+OR+pivot+OR+failed)&hl=en-IN&gl=IN&ceid=IN:en",
    ),
    (
        "Google News — Indian startup struggling",
        "https://news.google.com/rss/search?q=indian+startup+(struggling+OR+crisis+OR+burn+rate)&hl=en-IN&gl=IN&ceid=IN:en",
    ),
]

FAILURE_KEYWORDS = (
    "shutdown",
    "shut down",
    "layoff",
    "layoffs",
    "insolvency",
    "bankrupt",
    "pivot",
    "failed",
    "closes",
    "crisis",
    "struggling",
    "winding up",
    "nclt",
    "down round",
)

STATUS_PRIORITY = {
    "Shut Down": 1,
    "Struggling": 2,
    "Pivoted": 3,
    "Comeback": 4,
    "Recovery": 5,
    "Pre-IPO": 6,
    "Growing": 7,
}

FAMOUS_SHUTDOWNS = [
    "Byju's",
    "BluSmart",
    "Dunzo",
    "Koo App",
    "Hike",
    "Zilingo",
    "TaxiForSure",
    "Staples India",
    "Peppertap",
    "AskMe",
]