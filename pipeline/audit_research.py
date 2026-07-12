"""Audit all startups against gold research depth (shipped score + gate + source integrity)."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .merge import load_graveyard
from .quality import profile_score
from .research_gate import evaluate_research
from .source_integrity import catalog_brand_tokens, source_integrity_problems


def audit_startups(startups: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if startups is None:
        startups = load_graveyard().get("startups") or []

    catalog = catalog_brand_tokens(startups)
    rows = []
    tiers: dict[str, int] = {}
    failing = []
    blocked = []
    for s in startups:
        name = s.get("startup_name") or "?"
        score = profile_score(s)
        src_probs = source_integrity_problems(s, catalog)
        gate = evaluate_research(s, is_new=False, require_gold=True, catalog_tokens=catalog)
        tier = score["tier"]
        tiers[tier] = tiers.get(tier, 0) + 1
        source_integrity_pass = not src_probs
        # Gold pass requires gate acceptance (which includes source_integrity hard blocker)
        passed = bool(gate.accepted and score["score"] >= 85 and source_integrity_pass)
        row = {
            "startup_name": name,
            "status": s.get("status"),
            "score": score["score"],
            "tier": tier,
            "complete": score["complete"],
            "gate_accepted": gate.accepted,
            "source_integrity_pass": source_integrity_pass,
            "source_integrity_problems": src_probs,
            "missing": score["missing"],
            "gate_missing": gate.missing,
            "gate_reasons": gate.reasons,
            "pass": passed,
        }
        rows.append(row)
        if not passed:
            failing.append(row)
            reason_bits = []
            if not source_integrity_pass:
                reason_bits.append("source_integrity:" + ",".join(src_probs[:3]))
            if not gate.accepted:
                reason_bits.append("gate:" + ",".join(gate.missing[:4]))
            if score["score"] < 85:
                reason_bits.append(f"score:{score['score']}")
            blocked.append(
                {
                    "startup_name": name,
                    "score": score["score"],
                    "tier": tier,
                    "source_integrity_problems": src_probs,
                    "gate_missing": gate.missing,
                    "blocked_reason": "; ".join(reason_bits) or "below gold",
                }
            )

    rows.sort(key=lambda r: (r["pass"], r["score"], r["startup_name"]))
    return {
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "total": len(rows),
        "gold_pass": sum(1 for r in rows if r["pass"]),
        "failing_count": len(failing),
        "blocked_count": len(blocked),
        "tiers": tiers,
        "failing": failing,
        "blocked": blocked,
        "all": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit graveyard research depth")
    parser.add_argument("--out", type=Path, help="Write JSON audit to this path")
    args = parser.parse_args()
    report = audit_startups()
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"Wrote {args.out} — pass {report['gold_pass']}/{report['total']} blocked={report['blocked_count']}")
    else:
        print(text)
    raise SystemExit(0 if report["failing_count"] == 0 else 1)


if __name__ == "__main__":
    main()
