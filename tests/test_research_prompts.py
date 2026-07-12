"""Tests for research system prompts — no live LLM calls."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.prompts import (  # noqa: E402
    RESEARCH_MINIMUMS,
    RESEARCH_SYSTEM_RULES,
    SIGNAL_SYSTEM_PROMPT,
    enrich_system_prompt,
)
from pipeline.quality import profile_score  # noqa: E402


class TestResearchSystemPrompt(unittest.TestCase):
    def test_rules_require_detail_for_new_startups(self):
        text = RESEARCH_SYSTEM_RULES.lower()
        self.assertIn("detail is mandatory", text)
        self.assertIn("never invent", text)
        self.assertIn("timeline", text)
        self.assertIn("ai_rebuild", text)

    def test_new_mode_is_explicit(self):
        prompt = enrich_system_prompt(mode="new")
        self.assertIn("NEW STARTUP RESEARCH", prompt)
        self.assertIn("DETAIL IS MANDATORY", prompt)
        self.assertIn("full research dossier", prompt.lower())
        self.assertIn(RESEARCH_SYSTEM_RULES[:80], prompt)

    def test_refresh_and_gold_modes(self):
        refresh = enrich_system_prompt(mode="refresh")
        gold = enrich_system_prompt(mode="gold")
        self.assertIn("REFRESH", refresh)
        self.assertIn("GOLD-STANDARD", gold)
        self.assertIn("never thin", refresh.lower())

    def test_signal_prompt_is_json_oriented(self):
        self.assertIn("signals", SIGNAL_SYSTEM_PROMPT)
        self.assertIn("Shut Down", SIGNAL_SYSTEM_PROMPT)

    def test_minimums_align_with_quality_bar(self):
        self.assertGreaterEqual(RESEARCH_MINIMUMS["timeline_events"], 8)
        self.assertGreaterEqual(RESEARCH_MINIMUMS["insights"], 6)
        self.assertGreaterEqual(RESEARCH_MINIMUMS["lessons"], 4)

        thin = {
            "startup_name": "ThinCo",
            "short_summary": "short",
            "value_proposition": "x" * 50,
            "timeline": [{"date": "2020", "event": "founded"}],
            "insights": ["a"],
            "lessons": ["b"],
        }
        score = profile_score(thin)
        self.assertFalse(score["complete"])
        self.assertIn("timeline", score["missing"])


if __name__ == "__main__":
    unittest.main()
