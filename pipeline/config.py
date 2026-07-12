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


def _load_dotenv(path: Path | None = None) -> None:
    """Load KEY=VALUE from .env without overriding existing env (no extra deps)."""
    env_path = path or (ROOT / ".env")
    if not env_path.is_file():
        return
    try:
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if not key or key in os.environ:
                continue
            os.environ[key] = value.strip().strip("'").strip('"')
    except OSError:
        return


_load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def nvidia_api_key() -> str:
    return os.getenv("NVIDIA_API_KEY", "").strip()


def nvidia_base_url() -> str:
    return os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1").strip()


def nvidia_model() -> str:
    return os.getenv("NVIDIA_MODEL", "z-ai/glm-5.2").strip()


def nvidia_max_tokens() -> int:
    try:
        return max(256, int(os.getenv("NVIDIA_MAX_TOKENS", "8192")))
    except ValueError:
        return 8192


def research_max_repair_passes() -> int:
    """How many fill-missing LLM passes after the first research attempt."""
    try:
        return max(0, min(3, int(os.getenv("RESEARCH_MAX_REPAIR_PASSES", "2"))))
    except ValueError:
        return 2


def research_require_gold_for_new() -> bool:
    """Reject new startups that fail the gold research gate (default: on)."""
    return _env_bool("RESEARCH_REQUIRE_GOLD_FOR_NEW", True)


def research_require_gold_for_update() -> bool:
    """Reject updates that fail gold (default: off — still attempt repair)."""
    return _env_bool("RESEARCH_REQUIRE_GOLD_FOR_UPDATE", False)


# Back-compat constants (prefer getters for secrets/model)
NVIDIA_API_KEY = nvidia_api_key()
NVIDIA_BASE_URL = nvidia_base_url()
NVIDIA_MODEL = nvidia_model()

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
    "Crisis": 6,
    "Layoffs": 7,
    "Pre-IPO": 8,
    "Growing": 9,
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
