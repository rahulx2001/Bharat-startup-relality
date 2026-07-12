"""Audit all startups against gold research depth (shipped score + gate)."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .merge import load_graveyard
from .quality import profile_score
from .research_gate import evaluate_research


def audit_startups(startups: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if startups is None:
        startups = load_graveyard().get("startups") or []

    rows = []
    tiers: dict[str, int] = {}
    failing = []
    for s in startups:
        name = s.get("startup_name") or "?"
        score = profile_score(s)
        gate = evaluate_research(s, is_new=False, require_gold=True)
        tier = score["tier"]
        tiers[tier] = tiers.get(tier, 0) + 1
        row = {
            "startup_name": name,
            "status": s.get("status"),
            "score": score["score"],
            "tier": tier,
            "complete": score["complete"],
            "gate_accepted": gate.accepted,
            "missing": score["missing"],
            "gate_missing": gate.missing,
            "gate_reasons": gate.reasons,
            "pass": bool(gate.accepted and score["score"] >= 85),
        }
        rows.append(row)
        if not row["pass"]:
            failing.append(row)

    rows.sort(key=lambda r: (r["pass"], r["score"], r["startup_name"]))
    return {
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "total": len(rows),
        "gold_pass": sum(1 for r in rows if r["pass"]),
        "failing_count": len(failing),
        "tiers": tiers,
        "failing": failing,
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
        print(f"Wrote {args.out} — pass {report['gold_pass']}/{report['total']}")
    else:
        print(text)
    raise SystemExit(0 if report["failing_count"] == 0 else 1)


if __name__ == "__main__":
    main()
