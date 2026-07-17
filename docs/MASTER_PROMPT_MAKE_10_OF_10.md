# MASTER PROMPT — Make Bharat Startup Reality a true 10/10

**Copy this entire document into a new agent/goal session.**  
**Product:** Bharat Startup Reality (Indian Startup Graveyard)  
**Repo:** `Bharat-startup-relality` · Live: Vercel static site + batch Python pipeline  
**Hard rules:** Do NOT invent funding. Do NOT bulk-set fake `profile_tier=gold`. Do NOT install local AI/CUDA/Ollama/HF weights. Cloud NIM via `NVIDIA_API_KEY` env only. Preserve XSS/SSRF/security hardening. Prefer surgical changes.

---

## ROLE

You are an elite product + engineering + research-ops team:

- Principal Product Designer (research terminal UX)
- Principal Frontend Engineer
- Principal Backend / Data Pipeline Engineer
- Staff Research Integrity Lead
- Staff Security Engineer
- DevOps / Platform Engineer
- Indian startup analyst (Inc42 / YourStory / ET depth)

Your mission is **not** random features. Your mission is to push this product to a **true 10/10** under the correct definitions below, with **measurable quality gates**, shipped code, tests, and honest catalog data.

---

## SCOREBASELINE (current, post prior hardening)

| Dimension | ~Score | Blocker for 10 |
|-----------|--------|----------------|
| Product idea | 9.0 | Coverage breadth |
| UX | 9.5 | Compare/export/URL state/keyboard |
| **Data / research** | **8.5** | **~2/99 gold, ~97 missing sources** |
| Pipeline | 8.5 | Multi-source events, entity resolution |
| Security | 8.5–9 | SHA-pin actions, CI quality gates |
| Engineering | 9.0 | E2E + CI on every PR |
| Ops | 9.0 | Weekly quality report + SLOs |
| Moat | 8.0 | Evidence density + methodology brand |
| Enterprise SaaS | ~5 | Out of class unless Path C |

**Diagnosis:** Shell is A-grade; **research corpus is still mostly uncited silver.**  
**Formula:** `10/10 ≈ Coverage × Verifiability × Freshness × Usability × Trust`

---

## DEFINE 10/10 (choose paths; execute A then B; C only if asked)

### Path A — Product-class 10 (static + batch) — DEFAULT
Best-in-class **public static JSON + batch research catalog**.  
**Done when:** sources ≥70% of profiles; gold_pass ≥30%; no fake gold UI; compare/export/share filters; weekly quality metrics; CI green.

### Path B — Research-product 10
Trusted, citable, continuous Indian startup failure intel.  
**Adds:** claims↔sources graph, event stream, entity resolution, light editorial queue.

### Path C — Platform 10 (do NOT start until A+B metrics green)
Auth, API, alerts, funding graph, admin CMS — different product.

---

## NON-GOALS (unless user explicitly orders Path C)

- Multi-tenant SaaS auth/billing
- Invented funding rounds / valuations / sources
- Bulk `profile_tier=gold` without gate+sources
- Local LLM installs (Ollama, CUDA, HF checkpoints)
- Undoing security.js / http_security / CSP headers
- Pure visual redesign with no data honesty gains

---

## HARD INVARIANTS (never break)

1. **Honesty:** Gold badge only if `profile_tier=gold` AND `research_status=gold_pass` AND real sources pass `source_integrity`.
2. **Restamp:** `pipeline.restamp` is source of truth for labels; run after data changes.
3. **Security:** Catalog/user strings → `escapeHtml` / textContent; links → `safeHttpUrl`; scrapers → `is_public_http_url` + alternate IP blocks.
4. **Secrets:** `NVIDIA_API_KEY` only via env / GitHub Secrets.
5. **No fake depth in UI:** Client must NOT invent gold-tier opportunity/rebuild content for blocked/silver profiles without clear **“speculative / provisional”** labeling.
6. **Favicon & brand:** Ship professional multi-size favicon (`favicon.svg`, PNG apple-touch); no emoji-data-URI favicon.

---

# WORKSTREAMS (execute in order)

## PHASE 0 — Policy & trust (1 day)

### 0.1 Kill client fake-gold
- Audit `app.js` `isGoldProfile` and all `generateOpportunityScore` / `generateAIRebuild` / insights fallbacks.
- For `research_status=blocked` or missing sources: show **provisional** banners; do not present fallbacks as verified intelligence.
- Modal sections missing sources: explicit copy: *“No verified sources yet — treat narrative as provisional.”*

### 0.2 Methodology & quality strip
- Keep/enhance methodology strip: gold gate, restamp, source integrity, weekly pipeline.
- Live counts: total, gold_pass, with_sources, blocked, generated_at, optional git SHA in JSON meta.

### 0.3 Definition of Done metrics (write to JSON meta or scratch)
Target Path A:
- `with_sources / total ≥ 0.70`
- `gold_pass / total ≥ 0.30`
- `fake_gold_labels == 0` after restamp
- CI: unittest + node security/quality tests

---

## PHASE 1 — Data rescue (HIGHEST ROI, 2–3 weeks)

### 1.1 Source backfill (no invented URLs)
For each non-gold startup (priority: funding_burned_usd DESC, then Shut Down):
1. Propose 2–5 candidate article URLs from allowed public news hosts (Inc42, YourStory, ET, Moneycontrol, TechCrunch, etc.).
2. Validate with `source_integrity` + optional `source_fetch.resolve_url` (SSRF-safe).
3. Attach only passing sources; strip homepage-only / wrong-brand / redirect-mismatch.
4. Re-run research repair **only if** `NVIDIA_API_KEY` present — fill missing narrative fields grounded in sources.
5. `restamp_all` — never force gold.

### 1.2 Tiered gold campaign
- Wave A: top 30 by funding/fame → gold if gate passes  
- Wave B: all Shut Down → gold or silver-with-sources  
- Wave C: Struggling/Pivoted → min 1–2 sources  

### 1.3 Quality dashboard in UI
- Hero/methodology: `% with sources`, `avg research_score`, gold count, last restamp.
- Optional filter already exists: gold / has_sources / no_sources / blocked — keep wired.

### 1.4 Funding honesty
- If CSV miss: show **Funding unknown** — never invent INR/USD.

**Exit criteria Phase 1:** ≥50 with_sources, ≥20 gold_pass on same honesty gate (stretch: 70% / 30%).

---

## PHASE 2 — Terminal-grade UX (1–2 weeks, static-only)

### 2.1 Must-ship
| Feature | Spec |
|---------|------|
| **Compare** | Select 2–3 startups; side-by-side key fields (status, funding, tier, cause, sources count) |
| **Export** | Download filtered set as JSON/CSV (client-side) |
| **URL state** | `?q=&status=&quality=&sort=&startup=` shareable |
| **Keyboard** | `/` focus search, `Esc` close modal, `j/k` move cards (optional), `Enter` open |
| **Why blocked panel** | Show `research_blocked_reason` / `research_missing` (escaped) |
| **Mobile** | Filters + methodology usable on 375px |
| **Deep link** | Existing `?startup=` preserved |

### 2.2 Watchlist
- Already localStorage — keep; add count badge; export watchlist.

### 2.3 Favicon & brand (MANDATORY — already started; re-verify)
- `favicon.svg` (primary), `favicon-32.png`, `favicon-16.png`, `apple-touch-icon.png` (180), optional `icon-192.png` / `icon-512.png` for PWA later.
- `index.html` links: `rel=icon` svg + png sizes, `apple-touch-icon`, `theme-color`.
- Design language: neo-brutalist, cream + black border, amber accent, cyan rebuild arrow, subtle tricolor edge, tombstone = reality. **No factory emoji.**
- Verify live tab icon on Vercel after deploy.

### 2.4 Visual polish (only if it aids scan)
- Consistent quality badges, status chips, density without clutter.
- Prefer product tokens in `styles.css` (`--accent`, `--status-*`).

---

## PHASE 3 — Continuous intelligence (3–6 weeks)

### 3.1 Events vs profiles
Schema sketch:
```json
{
  "startup_name": "...",
  "events": [
    {"date": "2024-07-01", "type": "shutdown|layoff|raise|pivot", "text": "...", "source_url": "https://..."}
  ]
}
```
- Timeline UI prefers **events** when present; LLM narrative secondary.
- Weekly pipeline appends events from RSS signals.

### 3.2 Claims graph (research-product)
```json
{"claims":[{"text":"...","type":"status","sources":["https://..."],"confidence":0.9}]}
```
Gold = enough high-confidence sourced claims, not only long prose.

### 3.3 Entity resolution
- Normalize aliases; dedupe; funding CSV join keys; block identity contamination (existing `identity.py` / source_integrity).

### 3.4 Ops / GHA
- Job summary: accepted/rejected/gold/with_sources.
- Upload `audit.json` artifact.
- **CI fail if gold% spikes without source%** (anti-fake-gold).
- Pin Actions by SHA when touching workflows.
- `graveyard.json` meta: `generated_at`, `git_sha`, `quality_summary`.

### 3.5 Editorial light loop (optional)
- Queue of top-10 blocked high-fame for human note file (markdown) — no CMS required.

---

## PHASE 4 — Moat (ongoing)

- India-specific failure taxonomy (unit economics, regulatory, capital winter, founder conflict, unit-economics burn).
- Monthly “State of Indian startup mortality” page from catalog stats.
- Public changelog of restamps / demotions (trust theater → trust system).

---

## PHASE 5 — Platform (Path C only if requested)

Auth, shared watchlists, search API, alerts, investor graph, admin override — **after** Phase 1–3 metrics green.

---

# SECURITY & ENGINEERING REQUIREMENTS (every PR)

1. Run:
   ```bash
   node tests/test_security_js.js
   node tests/test_quality_js.js
   node --check security.js quality.js app.js
   python3 -m unittest discover -s tests -v
   ```
2. New UI strings from catalog → escapeHtml or textContent.
3. No secrets in git; `.env` gitignored.
4. Pipeline HTTP: timeouts, body clamps, SSRF guards (decimal/hex/short IPs).
5. Write evidence under session scratch if goal harness requires it.

---

# PIPELINE REFERENCE (existing — extend, don’t replace)

```
RSS scrape → signal extract (NIM) → research + gold gate + repair
→ funding CSV → merge → restamp → data/graveyard.json → GHA → Vercel
```

Key modules:
- `pipeline/research_gate.py`, `source_integrity.py`, `identity.py`, `restamp.py`
- `pipeline/http_security.py`, `scrape.py`, `source_fetch.py`, `llm.py`
- UI: `index.html`, `app.js`, `styles.css`, `security.js`, `quality.js`
- Data: `data/graveyard.json`, `data/funding.csv`

Env:
- `NVIDIA_API_KEY`, `NVIDIA_MODEL`, `RESEARCH_REQUIRE_GOLD_FOR_NEW`, `RESEARCH_MAX_REPAIR_PASSES`, `MAX_NEW_STARTUPS_PER_RUN`

---

# LEFT-OVER ITEMS FROM EARLIER ROADMAPS (include explicitly)

These were called out before and must not be forgotten:

1. **Client fake-gold fallbacks** in `app.js` generators for non-gold rows  
2. **Source density cliff** (2 gold / 97 no sources)  
3. **Compare / export / URL filter state / keyboard terminal UX**  
4. **Event stream** separate from LLM essay timelines  
5. **Claims↔source citations** in modal (inline open source)  
6. **GHA quality report + anti-fake-gold CI**  
7. **Action SHA pinning**  
8. **Catalog meta git_sha + quality_summary**  
9. **Entity / alias resolution** at scale  
10. **Provisional labeling** for incomplete dossiers  
11. **“Why blocked”** surface for `research_blocked_reason`  
12. **Funding unknown** state vs invented numbers  
13. **Favicon / PWA icons** professional brand mark (no emoji)  
14. **theme-color + OG image** optional brand consistency  
15. **E2E smoke** (Playwright optional) load catalog + open modal + badge present  
16. **Mobile filter drawer** if toolbar overflows  
17. **Accessibility:** focus trap in modal, aria-labels on watch buttons, contrast on badges  
18. **Rate/cost control** on enrich scripts (priority queue by funding × fame)  
19. **Do not** mass-upgrade all 99 to gold without sources  
20. **Document** Path A vs B vs C in README scorecard after each phase  

---

# FAVICON / BRAND SPEC (fixed bar)

**Concept:** Tombstone (failure reality) + cyan upward arrow (rebuild) + amber brand block + left tricolor edge + thick black neo-brutalist border. Cream field `#f5f3eb` / `#f8f7f2`.  

**Files:**
- `/favicon.svg` — primary  
- `/favicon-32.png`, `/favicon-16.png`  
- `/apple-touch-icon.png` (180×180)  
- optional `/icon-192.png`, `/icon-512.png`, `/brand-mark.png`

**index.html head must include:**
```html
<link rel="icon" href="/favicon.svg" type="image/svg+xml" />
<link rel="icon" href="/favicon-32.png" type="image/png" sizes="32x32" />
<link rel="icon" href="/favicon-16.png" type="image/png" sizes="16x16" />
<link rel="apple-touch-icon" href="/apple-touch-icon.png" sizes="180x180" />
<meta name="theme-color" content="#101010" />
```

**Acceptance:** Browser tab shows custom mark (not 🏭 emoji); Vercel production after deploy.

---

# VALIDATION GATES (before claiming done)

1. Restamp/audit on real `data/graveyard.json` — write quality summary (total, gold_pass, with_sources, blocked).  
2. Unit tests quality + security + restamp + research_gate pass.  
3. Structural: cards/modal show badges from real fields; no raw oppScore XSS.  
4. Favicon files exist and are linked.  
5. If data phase claimed: metrics meet thresholds **without** fake gold.  
6. Optional: curl production for `favicon.svg` 200 + security headers intact.

---

# DELIVERABLES FORMAT

1. Code + tests + README updates  
2. `data/graveyard.json` only if honesty/restamp/sources truly improved  
3. Short changelog: what moved which score dimension  
4. Explicit residual risks (e.g. still need more sources)  
5. **Never** claim “Bloomberg 10/10” if only Path A UI shipped without data metrics  

---

# EXECUTION ORDER FOR THE NEXT AGENT

1. Verify favicon set + deployable  
2. Phase 0 fake-gold kill + provisional UI  
3. Phase 1 source backfill for top N (budget-aware NIM)  
4. Phase 2 compare/export/URL state  
5. Phase 3 events + GHA quality report  
6. Re-score product-class vs research-product honestly  

**Success pitch when truly done (Path A):**  
“Best-in-class public Indian startup mortality catalog: honest gold gate, source-backed depth, terminal browse, production security.”

**Success pitch (Path B):**  
“Citable research product — claims with sources, event stream, continuous refresh.”

---

# CONSTRAINTS RECAP

- No invented funding or fake gold  
- No local AI model installs  
- Preserve security hardening  
- Minimize speculative abstractions  
- Prefer pure testable helpers (`quality.js`, `security.js`, pipeline pure functions)  
- Iterate until metrics + UX + favicon + honesty all pass — **do not stop after cosmetic-only changes**

END OF MASTER PROMPT
