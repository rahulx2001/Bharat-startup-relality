"""Structural contracts for quality UI + catalog honesty."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestQualityContracts(unittest.TestCase):
    def test_index_loads_quality_js(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        sec = html.find('src="security.js"')
        q = html.find('src="quality.js"')
        app = html.find('src="app.js"')
        self.assertGreater(sec, 0)
        self.assertGreater(q, sec)
        self.assertGreater(app, q)
        self.assertIn("qualityFilter", html)
        self.assertIn("methodologyStrip", html)
        self.assertIn("watchlistOnlyBtn", html)
        self.assertIn("loadError", html)

    def test_app_uses_quality_helpers_safely(self):
        app = (ROOT / "app.js").read_text(encoding="utf-8")
        for needle in (
            "matchesQualityFilter",
            "sortStartupsList",
            "toggleWatchlist",
            "showLoadError",
            "Escape",
            "sortTimeline",
        ):
            self.assertIn(needle, app, msg=needle)
        # Research quality badges ("Silver · no sources") must not appear in public UI
        self.assertNotIn("qualityBadgeLabel", app)
        self.assertNotIn("quality-badge", app)

    def test_no_provisional_scare_banner_copy(self):
        app = (ROOT / "app.js").read_text(encoding="utf-8")
        for banned in (
            "Provisional profile",
            "not gold-verified",
            "Treat narrative as incomplete until sources clear",
            "Provisional research",
            "treat narrative as provisional",
        ):
            self.assertNotIn(banned, app, msg=banned)

    def test_existing_modal_sections_and_key_facts(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        for needle in (
            "modalValueProp",
            "modalOpportunity",
            "modalCauseOfDeath",
            "modalTimeline",
            "modalLessons",
            "modalPeople",
            "modalMarketToday",
            "modalRebuildName",
            "modalSources",
            "modalKeyFacts",
            "keyFactsSection",
            "modalReaderTip",
        ):
            self.assertIn(needle, html, msg=needle)
        app = (ROOT / "app.js").read_text(encoding="utf-8")
        for needle in (
            "keyFactsFromStartup",
            "formatYearsActive",
            "formatEmployees",
            "peak_valuation",
            "statusReaderTip",
        ):
            self.assertIn(needle, app, msg=needle)

    def test_catalog_gold_is_rare_and_consistent(self):
        data = json.loads((ROOT / "data" / "graveyard.json").read_text(encoding="utf-8"))
        items = data["startups"]
        self.assertGreaterEqual(len(items), 50)
        gold = [s for s in items if s.get("profile_tier") == "gold"]
        gold_pass = [
            s
            for s in items
            if s.get("profile_tier") == "gold" and s.get("research_status") == "gold_pass"
        ]
        # Honesty: gold labels that pass gate must have sources
        for s in gold_pass:
            src = s.get("sources") or []
            self.assertTrue(src, msg=f"{s.get('startup_name')} gold_pass without sources")
        # Not mass-fake-gold: gold must not exceed sourced rows or 50% of catalog
        with_src = sum(1 for s in items if s.get("sources"))
        self.assertLessEqual(len(gold_pass), with_src)
        self.assertLessEqual(len(gold), max(5, len(items) // 2))
        # every gold_pass must match honest pair
        self.assertEqual(len(gold), len(gold_pass))

    def test_restamp_matches_catalog_tiers(self):
        from pipeline.restamp import restamp_entry
        from pipeline.source_integrity import catalog_brand_tokens

        data = json.loads((ROOT / "data" / "graveyard.json").read_text(encoding="utf-8"))
        items = data["startups"]
        catalog = catalog_brand_tokens(items)
        # Sample a few blocked + gold
        samples = []
        for s in items:
            if s.get("research_status") == "gold_pass":
                samples.append(s)
                break
        for s in items:
            if s.get("research_status") == "blocked":
                samples.append(s)
                break
        self.assertTrue(samples)
        for s in samples:
            clone = json.loads(json.dumps(s))
            restamp_entry(clone, catalog_tokens=catalog)
            self.assertEqual(clone.get("profile_tier"), s.get("profile_tier"))
            self.assertEqual(clone.get("research_status"), s.get("research_status"))


if __name__ == "__main__":
    unittest.main()
