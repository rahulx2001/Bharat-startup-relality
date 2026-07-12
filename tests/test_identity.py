"""Identity integrity tests — real gate path."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.identity import identity_ok, identity_problems  # noqa: E402
from pipeline.research_gate import evaluate_research  # noqa: E402


class TestIdentity(unittest.TestCase):
    def test_wrong_company_summary_rejected(self):
        entry = {
            "startup_name": "Unacademy",
            "status": "Struggling",
            "short_summary": "Fintech unicorn Zolve, valued at $1B, struggles despite $150M funding in 2023.",
            "value_proposition": "Zolve offers US banking for Indians with cards and accounts across cities.",
            "cause_of_death": "Zolve unit economics failed after high CAC and thin margins in fintech.",
            "timeline": [{"date": str(2018 + i), "event": f"event {i} with funding $1M"} for i in range(8)],
            "insights": [f"insight {i} with number {i}" for i in range(6)],
            "lessons": [f"lesson {i}" for i in range(4)],
            "market_today": "India edtech market remains large after 2023 corrections with hybrid models winning share.",
            "opportunity_score": {"rebuild_difficulty": 3, "scalability": 3, "market_potential": 4},
            "ai_rebuild": {
                "name": "X",
                "description": "A long enough description for the rebuild concept about learning platforms in India.",
                "tech_stack": ["a", "b", "c", "d", "e"],
                "execution_plan": ["1", "2", "3", "4", "5"],
                "innovative": ["1", "2", "3", "4", "5"],
                "monetization": "Subscription with ₹ targets for courses and cohorts.",
            },
            "sources": [
                {
                    "title": "Zolve raises $100M",
                    "url": "https://entrackr.com/2023/02/zolve-raises-100m-series-a/",
                }
            ],
            "founders": ["Gaurav Munjal"],
        }
        probs = identity_problems(entry)
        self.assertTrue(probs)
        self.assertFalse(identity_ok(entry))
        gate = evaluate_research(entry, is_new=False, require_gold=True)
        self.assertFalse(gate.accepted)
        self.assertIn("identity_integrity", gate.missing)

    def test_correct_identity_can_pass_identity_check(self):
        entry = {
            "startup_name": "Unacademy",
            "status": "Struggling",
            "short_summary": (
                "Unacademy scaled online UPSC/JEE coaching to tens of millions of learners then cut "
                "costs after 2022 edtech winter with layoffs and unit-economics pressure."
            ),
            "value_proposition": (
                "Unacademy offered live and recorded exam prep for Indian competitive exams with "
                "top educators, subscriptions, and hybrid centres across major cities."
            ),
            "cause_of_death": (
                "Unacademy faced post-COVID demand normalization, high content CAC, and capital "
                "markets demanding profitability; restructuring and layoffs followed 2022–2024."
            ),
            "sources": [
                {
                    "title": "Unacademy coverage",
                    "url": "https://inc42.com/buzz/unacademy-edtech-restructuring/",
                }
            ],
        }
        self.assertEqual(identity_problems(entry), [])
        self.assertTrue(identity_ok(entry))

    def test_sources_required_for_existing_gold(self):
        entry = {
            "startup_name": "BluSmart",
            "status": "Shut Down",
            "short_summary": (
                "BluSmart collapsed after SEBI action over fund diversion and unpaid staff in 2024–2025 "
                "with about $70M burned on EV fleet ops."
            ),
            "value_proposition": (
                "BluSmart promised all-electric rides across Delhi NCR with standardized pricing and "
                "a large EV fleet competing with Uber and Rapido on airport corridors."
            ),
            "cause_of_death": (
                "BluSmart's parent stress and alleged fund diversion destroyed financing; asset-heavy "
                "EV utilization never covered costs versus larger ride-hailing networks in India."
            ),
            "timeline": [{"date": f"202{i}", "event": f"BluSmart milestone {i} raised $1M context"} for i in range(8)],
            "insights": [f"BluSmart insight {i} with 10% metric" for i in range(6)],
            "lessons": [f"lesson {i}" for i in range(4)],
            "market_today": "EV ride-hail in India still hard without utilization and clean governance in 2025–2026.",
            "opportunity_score": {"rebuild_difficulty": 4, "scalability": 3, "market_potential": 3},
            "ai_rebuild": {
                "name": "EV corridor",
                "description": "Rebuild corridor EV rides with partner fleets and utilization dashboards for India.",
                "tech_stack": ["a", "b", "c", "d", "e"],
                "execution_plan": ["1", "2", "3", "4", "5"],
                "innovative": ["1", "2", "3", "4", "5"],
                "monetization": "Subscription fleet + per-ride take rate with ₹ targets.",
            },
            "sources": [{"title": "Inc42", "url": ""}],  # no http
            "founders": ["Anmol Singh Jaggi"],
            "funding_burned_usd": 70_000_000,
        }
        gate = evaluate_research(entry, is_new=False, require_gold=True)
        self.assertFalse(gate.accepted)
        self.assertTrue(
            "sources_with_url" in gate.missing or "source_integrity" in gate.missing,
            msg=gate.missing,
        )


if __name__ == "__main__":
    unittest.main()
