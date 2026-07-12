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

testBadgeHonesty();
testQualityFilterAndSort();
testWatchlistPure();
console.log("OK tests/test_quality_js.js");
