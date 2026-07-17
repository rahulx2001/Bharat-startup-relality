"""Normalize categories and startup names."""
from __future__ import annotations

import re

CATEGORY_MAP = {
    "edtech": "EdTech",
    "e-tech": "EdTech",
    "fintech": "FinTech",
    "food delivery": "Food Delivery",
    "quick commerce / delivery": "Quick Commerce",
    "quick commerce": "Quick Commerce",
    "grocery delivery": "Grocery Delivery",
    "ride-hailing": "Ride-hailing",
    "electric mobility / ride-hailing": "Electric Mobility",
    "fashion e-commerce": "Fashion E-commerce",
    "e-commerce": "E-Commerce",
    "proptech / real estate": "PropTech",
    "real estate": "PropTech",
    "used cars marketplace": "Auto Marketplace",
    "home services": "Home Services",
    "healthcare": "Healthcare",
    "food tech": "Food Tech",
    "ai / generative ai": "AI",
    "social media": "Social Media",
    "logistics": "Logistics",
    "d2c": "D2C",
    "saas": "SaaS",
}


def normalize_category(category: str | None) -> str:
    if not category:
        return "Technology"
    key = category.strip().lower()
    return CATEGORY_MAP.get(key, category.strip())


def normalize_startup_name(name: str) -> str:
    """Strip parenthetical status suffixes from CSV names."""
    cleaned = re.sub(r"\s*\([^)]*\)\s*$", "", name or "").strip()
    return cleaned or name


def normalize_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", normalize_startup_name(name).lower())