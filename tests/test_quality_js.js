/**
 * Node unit tests for quality.js — run: node tests/test_quality_js.js
 */
const assert = require("assert");
const path = require("path");
const api = require(path.join(__dirname, "..", "quality.js"));

function sample(overrides) {
  return Object.assign(
    {
      startup_name: "Acme",
      profile_tier: "silver",
      research_score: 90,
      research_status: "blocked",
      research_rejected: true,
      sources: [],
      funding_burned_usd: 1e6,
      updated_at: "2024-01-01",
    },
    overrides || {}
  );
}

function testBadgeHonesty() {
  const gold = sample({
    profile_tier: "gold",
    research_status: "gold_pass",
    research_rejected: false,
    sources: [{ title: "A", url: "https://example.com/a" }],
    research_score: 100,
  });
  assert.ok(api.qualityBadgeLabel(gold).toLowerCase().includes("gold verified"));
  assert.strictEqual(api.qualityBadgeClass(gold), "tier-gold");

  const fakeGold = sample({
    profile_tier: "gold",
    research_status: "blocked",
    research_rejected: true,
    sources: [],
  });
  const label = api.qualityBadgeLabel(fakeGold).toLowerCase();
  assert.ok(label.includes("unverified") || !label.startsWith("gold verified"));
  assert.notStrictEqual(api.qualityBadgeClass(fakeGold), "tier-gold");

  const silver = sample({ profile_tier: "silver" });
  assert.ok(api.qualityBadgeLabel(silver).toLowerCase().includes("silver"));
  assert.strictEqual(api.qualityBadgeClass(silver), "tier-silver");
}

function testQualityFilterAndSort() {
  const a = sample({
    startup_name: "Zed",
    profile_tier: "thin",
    research_score: 10,
    sources: [],
  });
  const b = sample({
    startup_name: "Alpha",
    profile_tier: "gold",
    research_status: "gold_pass",
    research_rejected: false,
    research_score: 100,
    sources: [{ url: "https://x.com/1" }],
  });
  const c = sample({
    startup_name: "Mid",
    profile_tier: "silver",
    research_score: 88,
    sources: [],
  });

  assert.strictEqual(api.matchesQualityFilter(b, "gold"), true);
  assert.strictEqual(api.matchesQualityFilter(c, "gold"), false);
  assert.strictEqual(api.matchesQualityFilter(c, "silver"), true);
  assert.strictEqual(api.matchesQualityFilter(a, "no_sources"), true);
  assert.strictEqual(api.matchesQualityFilter(b, "has_sources"), true);
  assert.strictEqual(api.matchesQualityFilter(c, "blocked"), true);

  const sorted = api.sortStartupsList([a, b, c], "quality");
  assert.strictEqual(sorted[0].startup_name, "Alpha");
  assert.ok(api.qualityRank(b) > api.qualityRank(c));
  assert.ok(api.qualityRank(c) > api.qualityRank(a));

  const byName = api.sortStartupsList([b, a, c], "name");
  assert.strictEqual(byName[0].startup_name, "Alpha");
}

function testWatchlistPure() {
  const mem = {
    _d: {},
    getItem(k) {
      return this._d[k] || null;
    },
    setItem(k, v) {
      this._d[k] = String(v);
    },
  };
  assert.deepStrictEqual(api.loadWatchlist(mem), []);
  let r = api.toggleWatchlist("Foo", mem);
  assert.strictEqual(r.watched, true);
  assert.ok(api.isWatched("Foo", mem));
  r = api.toggleWatchlist("Foo", mem);
  assert.strictEqual(r.watched, false);
  assert.strictEqual(api.isWatched("Foo", mem), false);
}

function testKeyFactFormatters() {
  assert.strictEqual(api.formatUsdCompact(null), "");
  assert.strictEqual(api.formatUsdCompact(0), "");
  assert.strictEqual(api.formatUsdCompact(5500000000), "$5.5B");
  assert.strictEqual(api.formatUsdCompact(775000000), "$775M");
  assert.ok(api.formatUsdCompact(300000000).includes("M"));

  assert.strictEqual(api.formatEmployees(null), "");
  assert.strictEqual(api.formatEmployees(0), "");
  assert.strictEqual(api.formatEmployees(2000), "2K people");
  assert.strictEqual(api.formatEmployees(50), "50 people");
  assert.strictEqual(api.formatEmployees("1000+"), "1000+");

  assert.strictEqual(api.formatYearsActive({}), "");
  assert.strictEqual(
    api.formatYearsActive({ year_founded: 2015, year_died: 2024 }),
    "2015–2024 (9 years)"
  );
  assert.ok(api.formatYearsActive({ year_founded: 2019 }, 2026).includes("present"));

  const facts = api.keyFactsFromStartup({
    funding_burned_usd: 1e9,
    peak_valuation: 2e9,
    employees: 500,
    year_founded: 2018,
    year_died: 2023,
    headquarters: "Bengaluru",
    category: "EdTech",
    status: "Shut Down",
    founders: ["A", "B"],
    investors: ["Seq"],
    sources: [{ url: "https://inc42.com/a/b" }],
  });
  const labels = facts.map((f) => f.label);
  assert.ok(labels.includes("Peak valuation"));
  assert.ok(labels.includes("Team size (peak/known)"));
  assert.ok(labels.includes("Years active"));
  assert.ok(labels.includes("Funding raised / at risk"));
  assert.ok(api.statusReaderTip("Shut Down").toLowerCase().includes("closed"));
  // missing fields → no empty values
  assert.strictEqual(api.keyFactsFromStartup({}).length, 0);
}

function testTimelineSortChronological() {
  const mixed = [
    { date: "Jan 2025", event: "App offline" },
    { date: "Jul 2014", event: "Founded" },
    { date: "May 2020", event: "Pandemic boom" },
  ];
  const sorted = api.sortTimeline(mixed);
  assert.strictEqual(sorted[0].date, "Jul 2014");
  assert.strictEqual(sorted[1].date, "May 2020");
  assert.strictEqual(sorted[2].date, "Jan 2025");
  assert.strictEqual(sorted[0].event, "Founded");

  // keys
  assert.ok(api.timelineDateKey("Jul 2014") < api.timelineDateKey("May 2020"));
  assert.ok(api.timelineDateKey("May 2020") < api.timelineDateKey("Jan 2025"));
  assert.ok(api.timelineDateKey("Q1 2019") < api.timelineDateKey("2021-06-15"));

  // stable with unparseable at end
  const withBad = [
    { date: "TBD", event: "unknown" },
    { date: "2015", event: "year only" },
    { date: "Mar 2018", event: "mid" },
  ];
  const s2 = api.sortTimeline(withBad);
  assert.strictEqual(s2[0].date, "2015");
  assert.strictEqual(s2[1].date, "Mar 2018");
  assert.strictEqual(s2[2].date, "TBD");
}

testBadgeHonesty();
testQualityFilterAndSort();
testWatchlistPure();
testKeyFactFormatters();
testTimelineSortChronological();
console.log("OK tests/test_quality_js.js");
