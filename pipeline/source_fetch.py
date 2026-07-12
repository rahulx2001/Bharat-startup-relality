"""Optional network helpers for source URL resolution (batch scripts only)."""
from __future__ import annotations

from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .http_security import is_public_http_url

_MAX_RESOLVE_READ = 64_000  # only need redirects/status, not full body


def resolve_url(url: str, timeout: float = 6.0) -> dict:
    """Follow redirects; return final URL, status, and path slug.

    Rejects non-public schemes/hosts before connect (SSRF guard).
    Injectable for tests via patching this function.
    """
    if not is_public_http_url(url):
        return {
            "ok": False,
            "input_url": url,
            "final_url": url,
            "status": None,
            "path": "",
            "error": "disallowed_url",
        }
    try:
        req = Request(url, method="GET", headers={"User-Agent": "Mozilla/5.0 BSR-SourceCheck/1.0"})
        with urlopen(req, timeout=timeout) as resp:  # noqa: S310 — guarded by is_public_http_url
            final = resp.geturl()
            if not is_public_http_url(final):
                return {
                    "ok": False,
                    "input_url": url,
                    "final_url": final,
                    "status": None,
                    "path": "",
                    "error": "redirect_to_disallowed_url",
                }
            # Drain a bounded amount so we do not pull multi-MB bodies
            try:
                resp.read(_MAX_RESOLVE_READ)
            except Exception:
                pass
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
