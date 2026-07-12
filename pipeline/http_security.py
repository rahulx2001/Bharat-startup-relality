"""HTTP safety helpers for scrapers and source fetchers (no network I/O here)."""
from __future__ import annotations

import ipaddress
import re
import socket
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

# Host looks like an IP-ish literal (decimal, hex, dotted, IPv6) — not a DNS name
_IPISH_RE = re.compile(
    r"^(?:"
    r"\d+"  # pure decimal e.g. 2130706433
    r"|0x[0-9a-f]+"  # hex e.g. 0x7f000001
    r"|(?:\d+|0x[0-9a-f]+)(?:\.(?:\d+|0x[0-9a-f]+)){1,3}"  # dotted / short / mixed
    r"|\[?[0-9a-f:]+\]?"  # IPv6-ish
    r")$",
    re.IGNORECASE,
)


def _is_non_public_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def parse_ip_literal(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """Parse host as an IP including alternate encodings attackers use for SSRF.

    Handles: standard dotted/IPv6, decimal (2130706433), hex (0x7f000001),
    short forms (127.1), and mixed dotted that inet_aton accepts.
    Returns None if host is not an IP literal (may be a DNS name).
    """
    if not host or not isinstance(host, str):
        return None
    h = host.strip().lower()
    if h.startswith("[") and h.endswith("]"):
        h = h[1:-1]
    if not h:
        return None

    # Standard forms first
    try:
        return ipaddress.ip_address(h)
    except ValueError:
        pass

    # Pure decimal IPv4 (e.g. http://2130706433/ → 127.0.0.1)
    if h.isdigit():
        try:
            n = int(h)
            if 0 <= n <= 0xFFFFFFFF:
                return ipaddress.IPv4Address(n)
        except (ValueError, OverflowError):
            return None

    # Pure hex IPv4 (e.g. 0x7f000001)
    if h.startswith("0x"):
        try:
            n = int(h, 16)
            if 0 <= n <= 0xFFFFFFFF:
                return ipaddress.IPv4Address(n)
        except (ValueError, OverflowError):
            return None

    # Dotted / short / octal-ish forms via inet_aton (platform accepts many encodings)
    if re.fullmatch(r"[0-9a-fx.]+", h, flags=re.IGNORECASE):
        try:
            packed = socket.inet_aton(h)
            return ipaddress.IPv4Address(packed)
        except OSError:
            pass
        # Manual short-form expansion: a, a.b, a.b.c → 32-bit layout
        parts = h.split(".")
        if 1 <= len(parts) <= 4:
            try:
                nums = [int(p, 0) for p in parts]  # base 0: 0x.. and 0.. octal
            except ValueError:
                return None
            if any(n < 0 for n in nums):
                return None
            try:
                if len(nums) == 1:
                    val = nums[0]
                elif len(nums) == 2:
                    if nums[0] > 0xFF or nums[1] > 0xFFFFFF:
                        return None
                    val = (nums[0] << 24) | nums[1]
                elif len(nums) == 3:
                    if nums[0] > 0xFF or nums[1] > 0xFF or nums[2] > 0xFFFF:
                        return None
                    val = (nums[0] << 24) | (nums[1] << 16) | nums[2]
                else:
                    if any(n > 0xFF for n in nums):
                        return None
                    val = (nums[0] << 24) | (nums[1] << 16) | (nums[2] << 8) | nums[3]
                if 0 <= val <= 0xFFFFFFFF:
                    return ipaddress.IPv4Address(val)
            except (ValueError, OverflowError):
                return None

    # Looks like an IP but failed to parse → treat as unusable (not a hostname)
    if _IPISH_RE.match(h):
        return None  # signal ambiguous: caller should reject via is_ipish check
    return None


def is_ip_literal_host(host: str) -> bool:
    """True if host is an IP literal or IP-encoding form (not a DNS name)."""
    if not host:
        return False
    h = host.strip().lower()
    if h.startswith("[") and h.endswith("]"):
        h = h[1:-1]
    if parse_ip_literal(host) is not None:
        return True
    return bool(_IPISH_RE.match(h))


def is_public_http_url(url: str) -> bool:
    """True only for http(s) URLs that are not clearly private/local.

    Does not perform DNS (avoids network in pure checks). Hostnames that look
    like IPs are validated including decimal/hex/short encodings; bare DNS
    names are allowed only if not blocked. Callers that connect should also use
    `resolve_and_validate_host` before the request.
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

    ip = parse_ip_literal(host)
    if ip is not None:
        return not _is_non_public_ip(ip)

    # IP-ish but unparseable (weird encodings) — reject rather than treat as DNS
    if is_ip_literal_host(host):
        return False

    # DNS hostname — allowed at pure-check layer
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
    """Resolve hostname and ensure no private IPs (SSRF guard). May use DNS.

    IP literals (including alternate encodings) are validated without treating
    them as hostnames first.
    """
    host = (hostname or "").strip().lower()
    if not host or host in _BLOCKED_HOSTS:
        raise ValueError("blocked host")

    lit = parse_ip_literal(host)
    if lit is not None:
        if _is_non_public_ip(lit):
            raise ValueError(f"non-public IP literal {lit} for {host}")
        return
    if is_ip_literal_host(host):
        raise ValueError(f"unparseable IP-like host {host}")

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
        if _is_non_public_ip(ip):
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
