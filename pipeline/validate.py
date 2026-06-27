"""Validate graveyard.json structure."""
from __future__ import annotations

from typing import Any

REQUIRED_FIELDS = ("startup_name", "status", "short_summary")
ALLOWED_STATUS = {"Shut Down", "Struggling", "Pivoted", "Comeback", "Recovery", "Crisis", "Layoffs", "Pre-IPO", "Growing"}


def validate_graveyard(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    startups = data.get("startups")
    if not isinstance(startups, list):
        return ["startups must be a list"]

    names = set()
    for idx, startup in enumerate(startups):
        if not isinstance(startup, dict):
            errors.append(f"startup[{idx}] must be an object")
            continue

        name = startup.get("startup_name")
        if not name:
            errors.append(f"startup[{idx}] missing startup_name")
            continue

        norm = str(name).strip().lower()
        if norm in names:
            errors.append(f"duplicate startup_name: {name}")
        names.add(norm)

        for field in REQUIRED_FIELDS:
            if not startup.get(field):
                errors.append(f"{name}: missing {field}")

        status = startup.get("status")
        if status and status not in ALLOWED_STATUS:
            errors.append(f"{name}: invalid status '{status}'")

    return errors