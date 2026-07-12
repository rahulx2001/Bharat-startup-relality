"""Unit tests for catalog-aware source integrity — pure, no HTTP."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.research_gate import evaluate_research  # noqa: E402
from pipeline.source_fetch import redirect_mismatch  # noqa: E402
from pipeline.source_integrity import (  # noqa: E402
    brand_tokens_from_name,
    catalog_brand_tokens,
    filter_valid_sources,
    source_integrity_problems,
    tokens_in_url,
)


def _catalog():
    names = [
        "Swiggy",
        "Zomato",
        "Flipkart Ping",
        "Koo",
        "Lybrate",
        "Practo",
        "Unacademy",
        "Paytm",
        "BluSmart",
    ]
    return catalog_brand_tokens([{"startup_name": n} for n in names])


class TestSourceIntegrityPure(unittest.TestCase):
    def test_swiggy_sole_zomato_fundraising_url_fails(self):
        entry = {
            "startup_name": "Swiggy",
            "sources": [
                {
                    "title": "ET",
                    "url": "https://economictimes.indiatimes.com/tech/startups/zomato-raises-62-million-from-kora-and-naspers/articleshow/84813177.cms",
                }
            ],
        }
        probs = source_integrity_problems(entry, _catalog())
        self.assertTrue(probs, msg=probs)
        self.assertTrue(
            any("foreign_brand" in p or "no_on_topic" in p for p in probs),
            msg=probs,
        )
        gate = evaluate_research(
            {
                **entry,
                "status": "Struggling",
                "short_summary": "Swiggy remains unprofitable after IPO with ₹5,630Cr revenue signals in 2025.",
                "value_proposition": "Swiggy does food delivery and Instamart grocery across India cities with large fleet density.",
                "cause_of_death": "Swiggy unit economics lag Zomato profitability targets after years of subsidies and high burn.",
                "timeline": [{"date": f"202{i}", "event": f"Swiggy event {i} raised $1M context"} for i in range(8)],
                "insights": [f"Swiggy insight {i} with 10%" for i in range(6)],
                "lessons": [f"lesson {i}" for i in range(4)],
                "market_today": "India food delivery consolidates around Swiggy and Zomato with stricter capital discipline in 2025–2026.",
                "opportunity_score": {"rebuild_difficulty": 3, "scalability": 4, "market_potential": 4},
                "ai_rebuild": {
                    "name": "x",
                    "description": "Rebuild Swiggy dark stores with AI routing and contribution dashboards for India.",
                    "tech_stack": ["a", "b", "c", "d", "e"],
                    "execution_plan": ["1", "2", "3", "4", "5"],
                    "innovative": ["1", "2", "3", "4", "5"],
                    "monetization": "Take rate plus membership with ₹ targets for cohorts.",
                },
                "founders": ["Sriharsha Majety"],
                "funding_burned_usd": 3_600_000_000,
            },
            is_new=False,
            require_gold=True,
            catalog_tokens=_catalog(),
        )
        self.assertFalse(gate.accepted)
        self.assertIn("source_integrity", gate.missing)

    def test_flipkart_ping_koo_moneycontrol_fails(self):
        entry = {
            "startup_name": "Flipkart Ping",
            "sources": [
                {
                    "title": "Koo shuts down operations",
                    "url": "https://www.moneycontrol.com/news/business/startup/koo-shuts-down-operations-12789001.html",
                }
            ],
        }
        probs = source_integrity_problems(entry, _catalog())
        self.assertTrue(any("foreign_brand" in p or "no_on_topic" in p for p in probs), msg=probs)

    def test_lybrate_practo_press_fails(self):
        entry = {
            "startup_name": "Lybrate",
            "sources": [
                {
                    "title": "Practo raises funding",
                    "url": "https://www.moneycontrol.com/news/business/practo-raises-series-c-funding-123.html",
                }
            ],
        }
        probs = source_integrity_problems(entry, _catalog())
        self.assertTrue(any("foreign_brand" in p or "no_on_topic" in p for p in probs), msg=probs)

    def test_publisher_root_only_fails(self):
        entry = {
            "startup_name": "Paytm",
            "sources": [
                {"title": "Paytm — Inc42", "url": "https://inc42.com/"},
                {"title": "Paytm — YourStory", "url": "https://yourstory.com/"},
            ],
        }
        probs = source_integrity_problems(entry, _catalog())
        self.assertTrue(any("publisher_root" in p or "no_on_topic" in p or "all_sources" in p for p in probs), msg=probs)

    def test_on_topic_article_path_passes(self):
        entry = {
            "startup_name": "Unacademy",
            "sources": [
                {
                    "title": "Unacademy lays off staff after edtech winter",
                    "url": "https://entrackr.com/2022/02/unacademy-lays-off-thousands/",
                }
            ],
        }
        probs = source_integrity_problems(entry, _catalog())
        self.assertEqual(probs, [], msg=probs)

    def test_filter_valid_sources_strips_foreign(self):
        entry = {
            "startup_name": "Swiggy",
            "sources": [
                {
                    "title": "Zomato raises",
                    "url": "https://economictimes.indiatimes.com/tech/startups/zomato-raises-62-million/articleshow/1.cms",
                },
                {
                    "title": "Swiggy IPO delayed",
                    "url": "https://www.livemint.com/companies/news/swiggy-ipo-launch-expected-to-be-postponed-11668011111128.html",
                },
            ],
        }
        kept = filter_valid_sources(entry, _catalog())
        self.assertEqual(len(kept), 1)
        self.assertIn("swiggy", kept[0]["url"].lower())

    def test_unacademy_forbes_redirect_mismatch(self):
        """Mock resolve: unacademy slug redirects to unrelated anmol-singh path."""
        subject = brand_tokens_from_name("Unacademy")
        resolve_result = {
            "ok": True,
            "input_url": "https://www.forbesindia.com/article/unacademy/edtech-platform-unacademy-raises-150m/62149/1",
            "final_url": "https://www.forbesindia.com/article/anmol-singh-forex-trading-story/62149/1",
            "status": 200,
            "path": "/article/anmol-singh-forex-trading-story/62149/1",
        }
        self.assertTrue(redirect_mismatch(subject, resolve_result))

    def test_tokens_in_url_extracts_slug_brands(self):
        toks = tokens_in_url(
            "https://economictimes.indiatimes.com/tech/startups/zomato-raises-62-million-from-kora/articleshow/1.cms"
        )
        self.assertIn("zomato", toks)


if __name__ == "__main__":
    unittest.main()
