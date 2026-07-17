"""Tests: no template gold; classify_failures honest blocked list."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.audit_research import audit_startups  # noqa: E402
from pipeline.gold_upgrader import classify_failures, upgrade_all, upgrade_entry  # noqa: E402
from pipeline.research_gate import evaluate_research  # noqa: E402


class TestNoTemplateGold(unittest.TestCase):
    def test_upgrade_entry_disabled(self):
        with self.assertRaises(RuntimeError):
            upgrade_entry({"startup_name": "X", "status": "Shut Down"})

    def test_upgrade_all_disabled(self):
        with self.assertRaises(RuntimeError):
            upgrade_all([{"startup_name": "X", "status": "Shut Down"}])

    def test_classify_failures_blocks_without_key(self):
        thin = {
            "startup_name": "ThinStub",
            "status": "Shut Down",
            "short_summary": "gone",
        }
        report = classify_failures([thin], api_key_present=False)
        self.assertEqual(report["gold_pass"], 0)
        self.assertEqual(report["blocked_count"], 1)
        self.assertIn("NVIDIA_API_KEY", report["blocked"][0]["blocked_reason"])

    def test_audit_matches_gate_on_real_file(self):
        data = json.loads((ROOT / "data" / "graveyard.json").read_text(encoding="utf-8"))
        report = audit_startups(data["startups"])
        self.assertEqual(report["total"], len(data["startups"]))
        # every failing row must fail evaluate_research or score
        for row in report["failing"]:
            s = next(x for x in data["startups"] if x["startup_name"] == row["startup_name"])
            gate = evaluate_research(s, is_new=False, require_gold=True)
            self.assertFalse(gate.accepted and row["score"] >= 85 and row["pass"])


if __name__ == "__main__":
    unittest.main()
