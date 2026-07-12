"""Optional network helpers for source URL resolution (batch scripts only)."""
from __future__ import annotations

from typing import Callable
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def resolve_url(url: str, timeout: float = 6.0) -> dict:
    """Follow redirects; return final URL, status, and path slug.

    Injectable for tests via patching this function.
    """
    try:
        req = Request(url, method="GET", headers={"User-Agent": "Mozilla/5.0 BSR-SourceCheck/1.0"})
        with urlopen(req, timeout=timeout) as resp:
            final = resp.geturl()
            status = getattr(resp, "status", None) or resp.getcode()
            return {
                "ok": True,
                "input_url": url,
                "final_url": final,
                "status": status,
                "path": urlparse(final).path or "",
            }
    except Exception as exc:
        return {
            "ok": False,
            "input_url": url,
            "final_url": url,
            "status": None,
            "path": "",
            "error": f"{type(exc).__name__}: {exc}",
        }


def redirect_mismatch(subject_tokens: set[str], resolve_result: dict) -> bool:
    """True if final path loses subject brand tokens present in input path."""
    from .source_integrity import tokens_in_url

    if not resolve_result.get("ok"):
        return True
    input_toks = tokens_in_url(resolve_result.get("input_url") or "")
    final_toks = tokens_in_url(resolve_result.get("final_url") or "")
    if not (input_toks & subject_tokens):
        return False
    # subject was in original slug but gone after redirect
    if (input_toks & subject_tokens) and not (final_toks & subject_tokens):
        return True
    return False
