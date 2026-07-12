"""HTTP safety helpers for scrapers and source fetchers (no network I/O here)."""
from __future__ import annotations

import ipaddress
import socket
from typing import Any
from urllib.parse import urlparse

# Default max body we will retain from a remote response (bytes)
DEFAULT_MAX_BODY_BYTES = 2_000_000  # 2 MiB

_BLOCKED_HOSTS = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "metadata.google.internal",
        "metadata",
        "0.0.0.0",
        "::1",
        "[::1]",
    }
)


def is_public_http_url(url: str) -> bool:
    """True only for http(s) URLs that are not clearly private/local.

    Does not perform DNS (avoids network in pure checks). Hostnames that look
    like IPs are validated; bare hostnames are allowed only if not blocked
    names. Callers that need full SSRF protection should also use
    `resolve_and_validate_host` before connecting.
    """
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").strip().lower()
    if not host:
        return False
    if host in _BLOCKED_HOSTS or host.endswith(".localhost") or host.endswith(".local"):
        return False
    # Block link-local / metadata style hosts
    if host.startswith("169.254.") or host == "metadata.google.internal":
        return False
    try:
        ip = ipaddress.ip_address(host)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return False
    except ValueError:
        # hostname — allowed if not blocked above
        pass
    return True


def validate_feed_url(url: str, allowed_hosts: set[str] | None = None) -> str:
    """Return normalized feed URL or raise ValueError."""
    if not is_public_http_url(url):
        raise ValueError(f"disallowed feed URL: {url!r}")
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower()
    if allowed_hosts is not None and host not in allowed_hosts:
        raise ValueError(f"feed host not in allowlist: {host}")
    return url.strip()


def resolve_and_validate_host(hostname: str) -> None:
    """Resolve hostname and ensure no private IPs (SSRF guard). May use DNS."""
    host = (hostname or "").strip().lower()
    if not host or host in _BLOCKED_HOSTS:
        raise ValueError("blocked host")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise ValueError(f"DNS resolution failed for {host}") from exc
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise ValueError(f"resolved to non-public IP {addr} for {host}")


def clamp_body(data: bytes | str, max_bytes: int = DEFAULT_MAX_BODY_BYTES) -> bytes:
    if isinstance(data, str):
        raw = data.encode("utf-8", errors="replace")
    else:
        raw = data
    if len(raw) > max_bytes:
        return raw[:max_bytes]
    return raw


def redact_secrets(text: str, secrets: list[str] | None = None) -> str:
    """Best-effort redaction for logs."""
    out = text or ""
    for secret in secrets or []:
        if secret and secret in out:
            out = out.replace(secret, "[REDACTED]")
    # common key prefixes
    import re

    out = re.sub(r"nvapi-[A-Za-z0-9_-]{8,}", "nvapi-[REDACTED]", out)
    out = re.sub(r"sk-[A-Za-z0-9]{8,}", "sk-[REDACTED]", out)
    return out
