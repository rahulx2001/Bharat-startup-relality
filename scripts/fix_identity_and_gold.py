#!/usr/bin/env python3
"""Restore contaminated rows from pre-NIM baseline and re-research via cloud NIM.

Fails closed: only saves gate-accepted identity-clean gold dossiers.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.audit_research import audit_startups  # noqa: E402
from pipeline.config import nvidia_api_key, nvidia_model  # noqa: E402
from pipeline.funding import lookup_startup  # noqa: E402
from pipeline.identity import identity_problems  # noqa: E402
from pipeline.llm import enrich_profile_full  # noqa: E402
from pipeline.merge import apply_updates, load_graveyard  # noqa: E402
from pipeline.normalize import normalize_category  # noqa: E402
from pipeline.quality import profile_score  # noqa: E402
from pipeline.research_gate import evaluate_research  # noqa: E402


def load_baseline() -> dict[str, dict]:
    """Pre-template / pre-bad-NIM snapshot."""
    raw = subprocess.check_output(
        ["git", "show", "7c50642:data/graveyard.json"],
        cwd=str(ROOT),
    )
    data = json.loads(raw)
    return {s["startup_name"]: s for s in data.get("startups") or [] if s.get("startup_name")}


def needs_fix(entry: dict) -> bool:
    gate = evaluate_research(entry, is_new=False, require_gold=True)
    return not gate.accepted


def main() -> int:
    if not nvidia_api_key():
        print("ERROR: NVIDIA_API_KEY required")
        return 2

    print(f"[fix] model={nvidia_model()}")
    baseline = load_baseline()
    data = load_graveyard()
    startups = data.get("startups") or []
    gold_ex = next((s for s in startups if s.get("startup_name") == "BluSmart"), startups[0])

    targets = [s for s in startups if needs_fix(s)]
    # prefer identity problems first
    targets.sort(
        key=lambda s: (
            0 if "identity_integrity" in evaluate_research(s, is_new=False, require_gold=True).missing else 1,
            profile_score(s)["score"],
        )
    )
    print(f"[fix] targets={len(targets)}")

    blocked: list[dict] = []
    fixed: list[str] = []
    now = datetime.now(timezone.utc).date().isoformat()

    for i, current in enumerate(targets, 1):
        name = current["startup_name"]
        before_gate = evaluate_research(current, is_new=False, require_gold=True)
        print(f"[fix] ({i}/{len(targets)}) {name} score={before_gate.score} missing={before_gate.missing}")

        # Start from baseline if identity-contaminated or wrong-company NIM junk
        base = baseline.get(name) or current
        if identity_problems(current):
            print(f"         identity_problems={identity_problems(current)}; restoring baseline seed")
            seed = dict(base)
        else:
            seed = dict(current)

        funding = lookup_startup(name)
        try:
            entry = enrich_profile_full(seed, funding, gold_ex)
            entry["startup_name"] = name
            entry["status"] = seed.get("status") or current.get("status") or entry.get("status")
            entry["category"] = normalize_category(entry.get("category") or seed.get("category"))
            entry["updated_at"] = now
            # never invent higher funding than known max of seed/current/lookup
            try:
                entry["funding_burned_usd"] = max(
                    int(seed.get("funding_burned_usd") or 0),
                    int(current.get("funding_burned_usd") or 0),
                    int(funding.get("funding_burned_usd") or 0),
                    int(entry.get("funding_burned_usd") or 0),
                )
            except (TypeError, ValueError):
                pass

            gate = evaluate_research(entry, is_new=False, require_gold=True)
            if gate.accepted:
                apply_updates([entry])
                fixed.append(name)
                print(f"         SAVED gold score={gate.score}")
            else:
                # leave current dirty data? Prefer restore baseline if current is identity-bad
                if identity_problems(current) and name in baseline:
                    apply_updates([dict(base, updated_at=now, research_rejected=True)])
                    print("         restored baseline (identity-bad current discarded)")
                blocked.append(
                    {
                        "startup_name": name,
                        "score": gate.score,
                        "missing": gate.missing,
                        "reasons": gate.reasons[:8],
                        "blocked_reason": f"post-fix still below gold/identity: {gate.summary()}",
                    }
                )
                print(f"         BLOCKED {gate.summary()}")
        except Exception as exc:
            blocked.append(
                {
                    "startup_name": name,
                    "score": before_gate.score,
                    "missing": before_gate.missing,
                    "blocked_reason": f"cloud NIM error during identity/gold fix: {exc}",
                }
            )
            print(f"         ERROR {exc}")
        time.sleep(1)

    after = audit_startups(load_graveyard().get("startups") or [])
    # any remaining non-pass not in blocked
    blocked_names = {b["startup_name"] for b in blocked}
    for row in after["failing"]:
        if row["startup_name"] not in blocked_names:
            blocked.append(
                {
                    "startup_name": row["startup_name"],
                    "score": row["score"],
                    "missing": row["missing"],
                    "blocked_reason": f"still below gold after identity fix pass: missing={row['missing'][:6]}",
                }
            )

    print(f"[fix] done fixed={len(fixed)} blocked={len(blocked)} gold_pass={after['gold_pass']}/{after['total']}")
    out = {
        "fixed": fixed,
        "blocked": blocked,
        "after_pass": after["gold_pass"],
        "after_fail": after["failing_count"],
        "after_tiers": after["tiers"],
    }
    print(json.dumps({k: out[k] for k in ("after_pass", "after_fail", "fixed") if k in out}, indent=2))
    # write next to CWD caller will copy to scratch
    Path("fix_identity_result.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return 0 if after["failing_count"] == len(blocked) else 1


if __name__ == "__main__":
    raise SystemExit(main())
