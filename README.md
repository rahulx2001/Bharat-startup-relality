# Bharat Startup Reality

**Best-in-class public static + batch Indian startup intelligence catalog** — failures, struggles, pivots, comebacks, and AI rebuild ideas with **honest research quality labels**.

Live data: [`data/graveyard.json`](data/graveyard.json)

## Path A progress (benchmarked)

| Metric | Baseline | Now | Target |
|--------|----------|-----|--------|
| Profiles with sources | ~2% | **~23%** | ≥70% |
| Gold verified | ~2% | **~23%** | ≥30% |
| Fake gold labels | 0 | **0** | 0 |

Honesty-first: thin company-index URLs rejected; curated article seeds only. Terminal UX: compare, export, URL state, provisional banners, `/` search, Escape close.

## Master upgrade prompt (full 10/10 roadmap)

See **[`docs/MASTER_PROMPT_MAKE_10_OF_10.md`](docs/MASTER_PROMPT_MAKE_10_OF_10.md)** — paste into a new agent session to execute Phases 0–4 (data rescue, terminal UX, events, ops, moat). Includes leftovers, invariants, favicon/brand spec, and anti-fake-gold rules.

## What “10/10” means here

This product is **not** multi-tenant SaaS, a funding data warehouse, or a full Bloomberg terminal.

It aims to be **best-in-class for its product class**:

| Pillar | How we score high |
|--------|-------------------|
| **Honesty** | `profile_tier` / `research_score` / sources restamped via gold gate — badges never invent gold |
| **Browse** | Search, status, category, **research quality**, recency, funding sorts; local **watchlist** |
| **Transparency** | Methodology strip + dataset freshness + gold/source counts |
| **Security** | XSS escape, safe links, CSP headers, SSRF-bounded scrapers, env-only API keys |
| **Ops** | Weekly GHA pipeline path; local restamp/audit without inventing funding |

## Quick start (UI)

Open [`index.html`](index.html) locally (static server recommended) or visit the Vercel deployment.

```bash
# optional local static server
python3 -m http.server 8080
# open http://localhost:8080
```

## Catalog quality (honesty)

```bash
# Re-stamp tiers so labels match the research gate (no LLM required)
python3 -c "import json; from pathlib import Path; from pipeline.restamp import restamp_all; p=Path('data/graveyard.json'); d=json.loads(p.read_text()); print(restamp_all(d['startups'])); p.write_text(json.dumps(d, indent=2, ensure_ascii=False)+chr(10))"

# Audit research gate
python -m pipeline.audit_research --out audit.json
```

- **Gold verified** = gate pass + score bar + source integrity.
- Most profiles may honestly be **silver** until sources/depth clear the bar — that is intentional.

UI badges show **tier · score · source count** from real JSON fields.

## Automation pipeline

```
RSS scrape → NVIDIA NIM research → gold gate + repair → funding CSV → merge → restamp → Vercel
```

### Run pipeline locally

```bash
cp .env.example .env
# set NVIDIA_API_KEY=...

pip install -r requirements.txt
export NVIDIA_API_KEY=nvapi-...
python -m pipeline.run
```

Or: `./scripts/run_pipeline.sh` (supports `--dry-run`).

### GitHub Actions

Secrets: `NVIDIA_API_KEY`, `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`.

Workflow: **every Monday 06:00 UTC** or manual dispatch.

### Research gate env knobs

| Variable | Default | Meaning |
|----------|---------|---------|
| `RESEARCH_REQUIRE_GOLD_FOR_NEW` | `true` | Reject thin new dossiers |
| `RESEARCH_REQUIRE_GOLD_FOR_UPDATE` | `false` | Soft gate on updates |
| `RESEARCH_MAX_REPAIR_PASSES` | `2` | Auto fill-missing LLM repairs |
| `MAX_NEW_STARTUPS_PER_RUN` | `5` | Cost control |

See [`pipeline/prompts.py`](pipeline/prompts.py) and [`pipeline/research_gate.py`](pipeline/research_gate.py).

## Tests

```bash
# Quality + security pure helpers (Node)
node tests/test_quality_js.js
node tests/test_security_js.js

# Python unit + contract suite
python3 -m unittest discover -s tests -v

# JS syntax
node --check security.js && node --check quality.js && node --check app.js
```

## Project structure

```
├── index.html, app.js, styles.css, security.js, quality.js
├── data/graveyard.json, data/funding.csv
├── pipeline/          # scrape, llm, gate, restamp, merge, http_security
├── tests/             # gate, integrity, security, quality contracts
├── scripts/           # enrich / restamp helpers
└── .github/workflows/update-graveyard.yml
```

## Security notes

- Catalog text is escaped before `innerHTML`; links use `safeHttpUrl`.
- Scrapers reject private/loopback/alternate IP encodings.
- API keys only via env / GitHub Secrets — never commit `.env`.

## Non-goals (by design)

Auth multi-user accounts, admin CMS, proprietary paywalled DB, real-time alerts/email, full India-wide entity graph. Those are separate product goals.
