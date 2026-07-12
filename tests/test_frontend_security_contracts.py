"""Structural contracts for frontend XSS hardening (no browser required)."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestFrontendSecurityContracts(unittest.TestCase):
    def test_index_loads_security_before_app(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        sec = html.find('src="security.js"')
        app = html.find('src="app.js"')
        self.assertGreater(sec, 0)
        self.assertGreater(app, sec)

    def test_app_uses_escape_for_catalog_fields(self):
        app = (ROOT / "app.js").read_text(encoding="utf-8")
        # Card and modal sinks must escape free-text fields
        for needle in (
            "escapeHtml(s.startup_name)",
            "escapeHtml(s.status",
            "escapeHtml(s.short_summary",
            "escapeHtml(t.date)",
            "escapeHtml(t.event)",
            "escapeHtml(p)",
            "escapeHtml(f)",
            "escapeHtml(i)",
            "escapeHtml(t)",
            "safeHttpUrl",
            "noopener noreferrer",
            "getStatusClass",
            # Opportunity score must go through sanitize / opportunityScoreHtml
            "sanitizeOppScore",
            "opportunityScoreHtml",
        ):
            self.assertIn(needle, app, msg=f"missing {needle}")

    def test_opportunity_score_not_raw_in_innerhtml(self):
        """oppScore.* must never appear unescaped inside modalOpportunity template."""
        app = (ROOT / "app.js").read_text(encoding="utf-8")
        # Old vulnerable pattern: ${oppScore.rebuild_difficulty} raw in template
        self.assertNotRegex(
            app,
            r"\$\{oppScore\.(rebuild_difficulty|scalability|market_potential)\}",
            msg="raw oppScore field in template",
        )
        self.assertIn("BSRSecurity.opportunityScoreHtml", app)

    def test_no_raw_catalog_in_innerhtml_templates(self):
        """innerHTML template literals must not interpolate catalog fields raw."""
        app = (ROOT / "app.js").read_text(encoding="utf-8")
        # Extract .innerHTML = `...` blocks (non-greedy, multiline)
        blocks = re.findall(r"\.innerHTML\s*=\s*`([\s\S]*?)`", app)
        self.assertGreater(len(blocks), 0)
        bad = []
        for block in blocks:
            # Allow escapeHtml(...), getStatusClass(...), generateBar(...), safe statics
            for m in re.finditer(r"\$\{([^}]+)\}", block):
                expr = m.group(1).strip()
                if expr.startswith("escapeHtml("):
                    continue
                if expr.startswith("getStatusClass("):
                    continue
                if expr.startswith("generateBar("):
                    continue
                if expr.startswith("getDifficultyLabel(") or expr.startswith("getScaleLabel(") or expr.startswith("getMarketLabel("):
                    continue
                if expr.startswith("formatMoney(") or expr.startswith("formatInrCr("):
                    continue
                # Static ternaries with only escapeHtml branches are already covered;
                # bare s.field is forbidden
                if re.search(r"\bs\.(startup_name|short_summary|failure_reason|status|category|headquarters)\b", expr):
                    if "escapeHtml" not in expr:
                        bad.append(expr[:80])
        self.assertEqual(bad, [], msg=f"raw field interpolations in innerHTML: {bad}")

    def test_feedback_length_limits(self):
        app = (ROOT / "app.js").read_text(encoding="utf-8")
        self.assertIn("slice(0, 4000)", app)
        self.assertIn("formsubmit.co", app)

    def test_vercel_security_headers_present(self):
        import json

        cfg = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
        headers = cfg.get("headers") or []
        flat = []
        for block in headers:
            for h in block.get("headers") or []:
                flat.append(h.get("key", "").lower())
        for required in (
            "x-content-type-options",
            "x-frame-options",
            "content-security-policy",
            "referrer-policy",
        ):
            self.assertIn(required, flat)

    def test_workflow_uses_secrets_not_literals(self):
        yml = (ROOT / ".github" / "workflows" / "update-graveyard.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("${{ secrets.NVIDIA_API_KEY }}", yml)
        self.assertNotRegex(yml, r"nvapi-[A-Za-z0-9_-]{16,}")
        self.assertIn("permissions:", yml)
        self.assertIn("contents: write", yml)


if __name__ == "__main__":
    unittest.main()
