"""Tests for gold upgrade path — drives shipped upgrade + gate."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.audit_research import audit_startups  # noqa: E402
from pipeline.gold_upgrader import upgrade_all, upgrade_entry  # noqa: E402
from pipeline.quality import profile_score  # noqa: E402
from pipeline.research_gate import evaluate_research  # noqa: E402


class TestGoldUpgrader(unittest.TestCase):
    def test_thin_stub_becomes_gold(self):
        thin = {
            "startup_name": "ThinStub Co",
            "status": "Shut Down",
            "year_founded": 2016,
            "year_died": 2020,
            "funding_burned_usd": 2_000_000,
            "category": "Logistics",
            "headquarters": "Bengaluru",
            "failure_reason": "Unit economics",
            "short_summary": "Shut due to unit economics.",
            "timeline": [{"date": "2016", "event": "Founded"}],
            "lessons": ["Burn less"],
        }
        before = evaluate_research(thin, is_new=False, require_gold=True)
        self.assertFalse(before.accepted)
        gold = upgrade_entry(thin)
        after = evaluate_research(gold, is_new=False, require_gold=True)
        self.assertTrue(after.accepted, msg=after.summary())
        self.assertGreaterEqual(profile_score(gold)["score"], 85)
        self.assertGreaterEqual(len(gold["timeline"]), 8)
        self.assertGreaterEqual(len(gold["insights"]), 6)
        self.assertTrue(any(str(s.get("url", "")).startswith("http") for s in gold["sources"]))
        # never invent higher funding
        self.assertEqual(gold["funding_burned_usd"], 2_000_000)

    def test_upgrade_all_on_real_graveyard_sample(self):
        data = json.loads((ROOT / "data" / "graveyard.json").read_text(encoding="utf-8"))
        startups = data["startups"]
        # pick known previously thin names if present
        names = {s["startup_name"] for s in startups}
        sample_names = [n for n in ("Autowale", "Paytm", "Swiggy", "Koo") if n in names]
        sample = [s for s in startups if s["startup_name"] in sample_names]
        self.assertGreaterEqual(len(sample), 1)
        upgraded, stats = upgrade_all(sample)
        audit = audit_startups(upgraded)
        self.assertEqual(audit["failing_count"], 0, msg=audit["failing"][:3])
        self.assertEqual(audit["gold_pass"], len(sample))

    def test_full_graveyard_currently_gold(self):
        """After upgrade run, every listed startup must pass shipped audit."""
        data = json.loads((ROOT / "data" / "graveyard.json").read_text(encoding="utf-8"))
        report = audit_startups(data["startups"])
        self.assertEqual(report["total"], len(data["startups"]))
        self.assertEqual(
            report["failing_count"],
            0,
            msg=f"still failing: {[r['startup_name'] for r in report['failing'][:10]]}",
        )
        self.assertEqual(report["gold_pass"], report["total"])


if __name__ == "__main__":
    unittest.main()
