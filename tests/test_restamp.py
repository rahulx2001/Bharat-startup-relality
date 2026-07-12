"""Tests: profile_tier never says gold when gate fails."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.audit_research import audit_startups  # noqa: E402
from pipeline.restamp import restamp_all, restamp_entry  # noqa: E402


class TestRestamp(unittest.TestCase):
    def test_swiggy_empty_sources_not_labeled_gold(self):
        entry = {
            "startup_name": "Swiggy",
            "status": "Struggling",
            "profile_tier": "gold",
            "research_score": 100,
            "research_mode": "gold",
            "short_summary": "Swiggy remains large but unprofitable with ₹5630Cr revenue signals.",
            "value_proposition": "Swiggy does food delivery and Instamart across India with dense fleets.",
            "cause_of_death": "Swiggy still burns cash versus contribution margin targets after IPO timing pressure.",
            "timeline": [{"date": f"202{i}", "event": f"Swiggy milestone {i}"} for i in range(8)],
            "insights": [f"Swiggy insight {i} with 10%" for i in range(6)],
            "lessons": [f"lesson {i}" for i in range(4)],
            "market_today": "India food delivery remains a Swiggy vs Zomato duopoly with capital discipline rising.",
            "opportunity_score": {"rebuild_difficulty": 3, "scalability": 4, "market_potential": 4},
            "ai_rebuild": {
                "name": "x",
                "description": "Rebuild Swiggy dark stores with AI routing for India cities and unit economics.",
                "tech_stack": ["a", "b", "c", "d", "e"],
                "execution_plan": ["1", "2", "3", "4", "5"],
                "innovative": ["1", "2", "3", "4", "5"],
                "monetization": "Take rate plus membership with ₹ targets for cohorts.",
            },
            "sources": [],
            "founders": ["Sriharsha Majety"],
            "funding_burned_usd": 3_600_000_000,
        }
        restamp_entry(entry)
        self.assertNotEqual(entry.get("profile_tier"), "gold")
        self.assertEqual(entry.get("research_status"), "blocked")
        self.assertTrue(entry.get("research_rejected"))
        self.assertNotEqual(entry.get("research_mode"), "gold")
        self.assertIn("source", (entry.get("research_blocked_reason") or "").lower())

    def test_unacademy_empty_sources_demoted(self):
        entry = {
            "startup_name": "Unacademy",
            "status": "Struggling",
            "profile_tier": "gold",
            "research_score": 88,
            "short_summary": "Unacademy scaled online exam prep then restructured after edtech winter.",
            "value_proposition": "Unacademy offered live classes for UPSC and JEE across India with subscriptions.",
            "cause_of_death": "Unacademy faced demand normalization and high content costs after 2022 capital markets tightened.",
            "timeline": [{"date": f"202{i}", "event": f"Unacademy event {i}"} for i in range(8)],
            "insights": [f"Unacademy insight {i} 20%" for i in range(6)],
            "lessons": [f"lesson {i}" for i in range(4)],
            "market_today": "India edtech remains large with hybrid models and tighter unit economics after 2023.",
            "opportunity_score": {"rebuild_difficulty": 3, "scalability": 3, "market_potential": 4},
            "ai_rebuild": {
                "name": "x",
                "description": "Rebuild Unacademy tutoring with AI teaching assistants and lower CAC funnels.",
                "tech_stack": ["a", "b", "c", "d", "e"],
                "execution_plan": ["1", "2", "3", "4", "5"],
                "innovative": ["1", "2", "3", "4", "5"],
                "monetization": "Subscription courses with ₹ monthly ARPU targets.",
            },
            "sources": [],
        }
        restamp_entry(entry)
        self.assertNotEqual(entry["profile_tier"], "gold")
        self.assertEqual(entry["research_status"], "blocked")

    def test_restamp_all_matches_audit_on_real_file(self):
        data = json.loads((ROOT / "data" / "graveyard.json").read_text(encoding="utf-8"))
        startups = data["startups"]
        # work on copies
        import copy

        rows = [copy.deepcopy(s) for s in startups]
        stats = restamp_all(rows)
        audit = audit_startups(rows)
        labeled = sum(1 for s in rows if s.get("profile_tier") == "gold")
        self.assertEqual(labeled, audit["gold_pass"], msg=f"stats={stats} audit={audit['gold_pass']}")
        # no false gold
        pass_names = {r["startup_name"] for r in audit["all"] if r["pass"]}
        for s in rows:
            if s.get("profile_tier") == "gold":
                self.assertIn(s["startup_name"], pass_names)


if __name__ == "__main__":
    unittest.main()
