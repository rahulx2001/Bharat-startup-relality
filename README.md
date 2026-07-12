# Startup Graveyard UI

**Bharat Startup Reality** — a static site that maps Indian startup failures, struggles, and pivots.

Live data: [`data/graveyard.json`](data/graveyard.json)

## Quick start (UI only)

Open [`index.html`](index.html) in a browser, or visit the Vercel deployment.

## Automation pipeline

The site is static JSON + vanilla JS. This repo now includes an automated pipeline:

```
RSS news scrape → NVIDIA LLM analysis → funding CSV lookup → merge graveyard.json → Vercel deploy
```

### What it does

1. **Scrape** — pulls Indian startup news from Inc42, YourStory, and Google News RSS
2. **Detect** — NVIDIA API extracts startup names + status (Shut Down, Struggling, etc.)
3. **Enrich** — generates timeline, cause of death, lessons, AI rebuild ideas
4. **Funding lookup** — fills funding/investors from [`data/funding.csv`](data/funding.csv)
5. **Merge** — updates [`data/graveyard.json`](data/graveyard.json) without duplicates
6. **Deploy** — GitHub Actions commits changes and deploys to Vercel weekly

### Run locally

```bash
cp .env.example .env
# Add your NVIDIA API key to .env

chmod +x scripts/run_pipeline.sh
./scripts/run_pipeline.sh

# Preview without writing JSON
./scripts/run_pipeline.sh --dry-run
```

Or directly:

```bash
pip install -r requirements.txt
export NVIDIA_API_KEY=nvapi-...
python -m pipeline.run
```

### GitHub Actions setup

Push this repo to GitHub, then add these **repository secrets**:

| Secret | Value |
|--------|-------|
| `NVIDIA_API_KEY` | Your NVIDIA NIM API key |
| `VERCEL_TOKEN` | Vercel account token |
| `VERCEL_ORG_ID` | `team_ZfvCldMtHgjKIrOwnC6VCprr` |
| `VERCEL_PROJECT_ID` | `prj_amZcoXnhx6BLQKwwVYWgRlKs8dLu` |

The workflow runs **every Monday at 6:00 UTC**, or manually via **Actions → Update Startup Graveyard → Run workflow**.

### Project structure

```
startup-graveyard-ui/
├── index.html, app.js, styles.css   # Static UI
├── data/
│   ├── graveyard.json                 # Main dataset (93 startups)
│   └── funding.csv                    # Indian startup funding reference
├── pipeline/
│   ├── scrape.py                      # RSS news scraper
│   ├── llm.py                         # NVIDIA API enrichment
│   ├── funding.py                     # Funding CSV lookup
│   ├── merge.py                       # JSON merge + sort
│   └── run.py                         # Pipeline entry point
└── scripts/
    ├── reorganize.py                  # Manual JSON sort/dedup
    └── run_pipeline.sh                # Local runner
```

### Notes

- The UI still has category-based fallbacks in `app.js` for entries missing `ai_rebuild` fields
- Set `MAX_NEW_STARTUPS_PER_RUN` to control API cost per run (default: 5)
- Pipeline cache lives in `pipeline/cache/` (gitignored except what Actions commits)
- **Research system prompt:** [`pipeline/prompts.py`](pipeline/prompts.py) — detailed research constitution (timeline ≥8, insights ≥6, lessons ≥4, rich narrative / `ai_rebuild`, no invented funding).
- **Hard research gate:** [`pipeline/research_gate.py`](pipeline/research_gate.py) — new startups are **rejected** unless gold depth is met (sources with URLs, concrete facts, founders, full dossier). Failed drafts get up to `RESEARCH_MAX_REPAIR_PASSES` automatic fill-missing LLM repairs (`research_startup` in `pipeline/llm.py`).
- Env knobs: `RESEARCH_REQUIRE_GOLD_FOR_NEW=true` (default), `RESEARCH_REQUIRE_GOLD_FOR_UPDATE=false`, `RESEARCH_MAX_REPAIR_PASSES=2`.

### Research quality audit & cloud enrichment

```bash
# Audit gold gate (shipped score + evaluate_research)
python -m pipeline.audit_research --out audit.json

# Enrich below-gold rows via cloud NIM (requires NVIDIA_API_KEY)
export NVIDIA_API_KEY=...
export NVIDIA_MODEL=meta/llama-3.1-8b-instruct
python scripts/enrich_failing_nim.py
```

Template gold padding is **disabled**. Failures without successful NIM research must appear on a blocked list with reasons.

### Source integrity

Gold profiles require **on-topic article sources** (not publisher homepages, not other companies' URLs).

```bash
python -m pipeline.audit_research --out audit.json
python scripts/remediate_sources.py --check-redirects
```
