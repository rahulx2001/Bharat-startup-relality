#!/bin/bash
# Import scraping CSV + batch-enrich all startups to BluSmart gold standard.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

source .venv/bin/activate 2>/dev/null || python3 -m venv .venv && source .venv/bin/activate
pip install -q -r requirements.txt

echo "=== Step 1: Import scraping CSV ==="
python -m pipeline.import_scraping

echo "=== Step 2: Batch enrich (BluSmart gold standard) ==="
python -m pipeline.enrich_batch --delay 3

echo "=== Done ==="