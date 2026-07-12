"""Tests for hard research gate — no live LLM."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.research_gate import evaluate_research, merge_research  # noqa: E402


def _gold_profile(**overrides):
    base = {
        "startup_name": "TestCo India",
        "status": "Shut Down",
        "year_founded": 2018,
        "year_died": 2024,
        "funding_burned_usd": 12_000_000,
        "category": "FinTech",
        "headquarters": "Bengaluru",
        "short_summary": (
            "TestCo India raised $12M then shut down in 2024 after unit economics "
            "collapsed and a SEBI probe hit its parent."
        ),
        "value_proposition": (
            "TestCo promised UPI-linked SME credit underwriting for Indian merchants, "
            "claiming 40,000 shops across Bengaluru and Mumbai with ₹200 crore GMV. "
            "It positioned against traditional NBFCs with same-day disbursal and "
            "embedded checkout. Peak monthly originations hit $4M in 2022 before "
            "defaults spiked and growth stalled versus better-capitalized rivals."
        ),
        "cause_of_death": (
            "The model required 18%+ take rates to cover 12% cost of capital and 6% "
            "defaults, but competition from banks forced 9% pricing. Parent entity "
            "faced a SEBI-related inquiry in late 2023; vendors went unpaid for three "
            "months. By Q1 2024, runway was under 4 months after a failed $20M round. "
            "Operations suspended in April 2024 with ₹45 crore payables outstanding. "
            "No defensible data moat — bureau scores were commodities."
        ),
        "failure_reason": "Unit economics, funding winter, regulatory stress",
        "founders": ["Asha Verma", "Rohan Iyer"],
        "investors": ["Demo Ventures", "India Seed Fund"],
        "timeline": [{"date": f"202{i}", "event": f"Milestone event number {i} with detail"} for i in range(8)],
        "insights": [f"Insight {i}: markets punish weak unit economics in India SME credit ({i})" for i in range(6)],
        "lessons": [
            "Never price below cost of risk",
            "Hold 18 months runway before aggressive city expansion",
            "Separate parent governance from operating cash",
            "Instrument default cohorts weekly not quarterly",
        ],
        "opportunity_score": {"rebuild_difficulty": 4, "scalability": 3, "market_potential": 4},
        "market_today": (
            "India SME embedded finance remains large but winners are bank-partnered "
            "platforms with cheaper deposits. Pure marketplace lenders without balance "
            "sheet partners struggle post-2023. Open credit and account aggregators "
            "lowered underwriting costs for survivors in 2025–2026."
        ),
        "ai_rebuild": {
            "name": "LedgerGuard SME",
            "description": (
                "AI underwriting co-pilot that only originates via bank balance-sheet "
                "partners, using GST and account-aggregator signals for Indian SMEs."
            ),
            "tech_stack": ["Python", "Postgres", "Feature store", "LLM risk notes", "Kafka"],
            "execution_plan": [
                "Secure NBFC/bank partner",
                "Ingest GST + AA data",
                "Pilot 500 merchants",
                "Calibrate default models",
                "Expand city by city",
            ],
            "innovative": [
                "Bank capital not marketplace capital",
                "Explainable decline reasons",
                "Fraud graph across GSTINs",
                "Dynamic limit management",
                "Collections playbooks",
            ],
            "monetization": "SaaS ₹2–5 per underwriting decision + 40 bps success fee; target ₹8 crore ARR by year 3",
        },
        "sources": [
            {"title": "Inc42 shutdown report", "url": "https://inc42.com/example-testco"},
            {"title": "YourStory", "url": "https://yourstory.com/example-testco"},
        ],
    }
    base.update(overrides)
    return base


class TestResearchGate(unittest.TestCase):
    def test_gold_profile_accepted_as_new(self):
        gate = evaluate_research(_gold_profile(), is_new=True, require_gold=True)
        self.assertTrue(gate.accepted, msg=gate.summary())
        self.assertGreaterEqual(gate.score, 85)
        self.assertEqual(gate.tier, "gold")

    def test_thin_profile_rejected(self):
        thin = {
            "startup_name": "ThinCo",
            "status": "Shut Down",
            "short_summary": "It failed.",
            "sources": [{"title": "x", "url": "https://example.com"}],
        }
        gate = evaluate_research(thin, is_new=True, require_gold=True)
        self.assertFalse(gate.accepted)
        self.assertIn("timeline", gate.missing)

    def test_missing_source_url_rejected(self):
        profile = _gold_profile(sources=[{"title": "no url", "url": ""}])
        gate = evaluate_research(profile, is_new=True, require_gold=True)
        self.assertFalse(gate.accepted)
        self.assertIn("sources_with_url", gate.missing)

    def test_vague_narrative_rejected(self):
        profile = _gold_profile(
            short_summary="A company that tried hard and then stopped operating eventually.",
            value_proposition=(
                "They offered services to customers in several places with a unique approach "
                "that many people liked until things changed for strategic reasons overall."
            ),
            cause_of_death=(
                "Ultimately the business could not continue because of various challenges "
                "across product market and organization that accumulated over a long period "
                "without a clear path to sustainable operations in the region."
            ),
            failure_reason="many issues",
        )
        # Strip digits/currency from core narrative fields already done — ensure no years slipped in timeline only
        gate = evaluate_research(profile, is_new=True, require_gold=True)
        self.assertFalse(gate.accepted)
        self.assertIn("concrete_facts", gate.missing)

    def test_new_requires_founders(self):
        profile = _gold_profile(founders=[])
        gate = evaluate_research(profile, is_new=True, require_gold=True)
        self.assertFalse(gate.accepted)
        self.assertIn("founders", gate.missing)

    def test_merge_research_prefers_richer_text(self):
        base = {"short_summary": "short", "insights": ["a"], "funding_burned_usd": 1}
        patch = {
            "short_summary": "a much longer summary with more detail",
            "insights": ["a", "b"],
            "funding_burned_usd": 5,
        }
        merged = merge_research(base, patch)
        self.assertIn("longer summary", merged["short_summary"])
        self.assertEqual(merged["insights"], ["a", "b"])
        self.assertEqual(merged["funding_burned_usd"], 5)

    def test_require_gold_flag_respected(self):
        thin = {
            "startup_name": "X",
            "status": "Struggling",
            "short_summary": "Still operating with issues.",
        }
        soft = evaluate_research(thin, is_new=False, require_gold=False)
        self.assertTrue(soft.accepted)
        hard = evaluate_research(thin, is_new=True, require_gold=True)
        self.assertFalse(hard.accepted)

    def test_real_blusmart_passes_gate(self):
        import json

        data = json.loads((ROOT / "data" / "graveyard.json").read_text(encoding="utf-8"))
        blusmart = next(s for s in data["startups"] if s.get("startup_name") == "BluSmart")
        # Ensure at least one http source for gate (legacy may lack urls)
        sources = blusmart.get("sources") or []
        if not any(isinstance(s, dict) and str(s.get("url", "")).startswith("http") for s in sources):
            blusmart = dict(blusmart)
            blusmart["sources"] = (sources or []) + [
                {"title": "legacy", "url": "https://example.com/blusmart"}
            ]
        gate = evaluate_research(blusmart, is_new=False, require_gold=True)
        self.assertTrue(gate.accepted, msg=f"{gate.summary()} missing={gate.missing}")


class TestResearchStartupOrchestration(unittest.TestCase):
    def test_research_startup_repairs_then_accepts(self):
        """Drive research_startup with mocked LLM: thin first, gold on repair."""
        from pipeline import llm

        thin = {
            "startup_name": "RepairCo",
            "status": "Shut Down",
            "short_summary": "Closed in 2024 after burning $3M.",
            "sources": [{"title": "News", "url": "https://example.com/r"}],
        }
        gold = _gold_profile(startup_name="RepairCo")

        calls = {"n": 0}

        def fake_chat(system, user, temperature=0.2, retries=5):
            calls["n"] += 1
            # first call enrich, second repair
            if calls["n"] == 1:
                return json_dumps(thin)
            return json_dumps(gold)

        def json_dumps(obj):
            import json as _json

            return _json.dumps(obj)

        signal = {
            "startup_name": "RepairCo",
            "status": "Shut Down",
            "headline": "RepairCo shuts down",
            "source_url": "https://example.com/r",
            "date": "2024-01-01",
            "confidence": 0.9,
        }

        with mock.patch.object(llm, "_chat", side_effect=fake_chat):
            entry, gate = llm.research_startup(signal, {}, None)

        self.assertTrue(gate.accepted, msg=gate.summary())
        self.assertEqual(entry["startup_name"], "RepairCo")
        self.assertGreaterEqual(calls["n"], 2)

    def test_run_pipeline_skips_rejected_new(self):
        from pipeline import run as run_mod

        signal = {
            "startup_name": "RejectMe",
            "status": "Shut Down",
            "headline": "x",
            "source_url": "https://example.com/x",
            "date": "2024",
            "confidence": 0.9,
        }
        thin_entry = {
            "startup_name": "RejectMe",
            "status": "Shut Down",
            "short_summary": "nope",
            "sources": [{"title": "t", "url": "https://example.com/x"}],
        }
        from pipeline.research_gate import evaluate_research

        gate = evaluate_research(thin_entry, is_new=True, require_gold=True)
        self.assertFalse(gate.accepted)

        with mock.patch.object(run_mod, "fetch_articles", return_value=[{"title": "t"}]):
            with mock.patch.object(run_mod, "nvidia_api_key", return_value="test"):
                with mock.patch.object(run_mod, "extract_signals", return_value=[signal]):
                    with mock.patch.object(
                        run_mod,
                        "research_startup",
                        return_value=(thin_entry, gate),
                    ):
                        with mock.patch.object(run_mod, "apply_updates") as apply:
                            code = run_mod.run_pipeline(dry_run=False, force_scrape=True)
        self.assertEqual(code, 0)
        apply.assert_not_called()


if __name__ == "__main__":
    unittest.main()
