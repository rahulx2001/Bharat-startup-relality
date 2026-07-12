"""HTTP security pure-function tests — no network required for core checks."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.http_security import (  # noqa: E402
    clamp_body,
    is_public_http_url,
    redact_secrets,
    validate_feed_url,
)


class TestHttpSecurity(unittest.TestCase):
    def test_allows_public_https(self):
        self.assertTrue(is_public_http_url("https://inc42.com/feed/"))
        self.assertTrue(is_public_http_url("http://example.com/a"))

    def test_blocks_schemes_and_local(self):
        self.assertFalse(is_public_http_url("file:///etc/passwd"))
        self.assertFalse(is_public_http_url("javascript:alert(1)"))
        self.assertFalse(is_public_http_url("https://localhost/admin"))
        self.assertFalse(is_public_http_url("http://127.0.0.1/"))
        self.assertFalse(is_public_http_url("http://192.168.1.1/"))
        self.assertFalse(is_public_http_url("http://10.0.0.5/"))
        self.assertFalse(is_public_http_url("http://169.254.169.254/latest/meta-data/"))
        self.assertFalse(is_public_http_url(""))
        self.assertFalse(is_public_http_url(None))  # type: ignore[arg-type]

    def test_validate_feed_allowlist(self):
        url = validate_feed_url("https://inc42.com/feed/", {"inc42.com", "yourstory.com"})
        self.assertEqual(url, "https://inc42.com/feed/")
        with self.assertRaises(ValueError):
            validate_feed_url("https://evil.example/feed", {"inc42.com"})
        with self.assertRaises(ValueError):
            validate_feed_url("http://127.0.0.1/feed")

    def test_clamp_body(self):
        self.assertEqual(len(clamp_body(b"x" * 100, max_bytes=10)), 10)
        self.assertEqual(clamp_body("hi", max_bytes=100), b"hi")

    def test_redact_secrets(self):
        text = "key=nvapi-ABCDEFGHIJKLMNOPQRSTUVWXYZ123456 and sk-abcdefghijklmnop"
        red = redact_secrets(text)
        self.assertNotIn("ABCDEFGHIJKLMNOPQRSTUVWXYZ123456", red)
        self.assertIn("[REDACTED]", red)

    def test_source_fetch_rejects_ssrf_without_network(self):
        from pipeline.source_fetch import resolve_url

        for bad in (
            "http://127.0.0.1/",
            "http://localhost/admin",
            "file:///etc/passwd",
            "http://169.254.169.254/latest/meta-data/",
            "javascript:alert(1)",
        ):
            result = resolve_url(bad, timeout=0.1)
            self.assertFalse(result["ok"], msg=bad)
            self.assertEqual(result.get("error"), "disallowed_url")

    def test_scrape_module_uses_http_security(self):
        """Structural: scrape wires feed validation + body clamp."""
        src = (ROOT / "pipeline" / "scrape.py").read_text(encoding="utf-8")
        self.assertIn("validate_feed_url", src)
        self.assertIn("clamp_body", src)
        self.assertIn("is_public_http_url", src)
        self.assertIn("timeout", src)


if __name__ == "__main__":
    unittest.main()
