/**
 * Node unit tests for security.js — run: node tests/test_security_js.js
 */
const assert = require("assert");
const path = require("path");
const api = require(path.join(__dirname, "..", "security.js"));

function testEscapeHtml() {
  assert.strictEqual(api.escapeHtml('<script>alert("x")</script>'),
    "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;");
  assert.strictEqual(api.escapeHtml("a & b"), "a &amp; b");
  assert.strictEqual(api.escapeHtml(null), "");
  assert.strictEqual(api.escapeHtml("O'Reilly"), "O&#39;Reilly");
}

function testSafeHttpUrl() {
  assert.strictEqual(api.safeHttpUrl("https://inc42.com/a"), "https://inc42.com/a");
  assert.strictEqual(api.safeHttpUrl("javascript:alert(1)"), "");
  assert.strictEqual(api.safeHttpUrl("data:text/html,hi"), "");
  assert.strictEqual(api.safeHttpUrl("ftp://x"), "");
  assert.strictEqual(api.safeHttpUrl(""), "");
  assert.strictEqual(api.safeHttpUrl("not a url"), "");
}

function testStatusClassToken() {
  assert.strictEqual(api.statusClassToken("Shut Down"), "dead");
  assert.strictEqual(api.statusClassToken("<script>"), "struggling");
  assert.strictEqual(api.statusClassToken("Pivoted"), "pivoted");
  assert.strictEqual(api.statusClassToken("Comeback"), "comeback");
  assert.ok(!api.statusClassToken("Pivoted").includes("<"));
  assert.ok(["dead", "struggling", "pivoted", "comeback"].includes(api.statusClassToken("x\" onload=alert(1)")));
}

function testClampScore() {
  assert.strictEqual(api.clampScore(3, 5), 3);
  assert.strictEqual(api.clampScore(99, 5), 5);
  assert.strictEqual(api.clampScore(-1, 5), 0);
  assert.strictEqual(api.clampScore("nope", 5), 0);
  assert.strictEqual(api.clampScore(null, 5), 0);
}

function testOpportunityScoreXssPoison() {
  // Real attack payload from skeptic: poison opportunity_score fields
  const poison = {
    rebuild_difficulty: '<img src=x onerror=alert(1)>',
    scalability: '"><script>alert(1)</script>',
    market_potential: "3 onload=alert(1)",
  };
  const safe = api.sanitizeOppScore(poison);
  assert.strictEqual(safe.rebuild_difficulty, 0);
  assert.strictEqual(safe.scalability, 0);
  assert.strictEqual(safe.market_potential, 0);

  const html = api.opportunityScoreHtml(poison, {
    difficulty: "Moderate",
    scale: "Moderate",
    market: "Medium",
  });
  assert.ok(!html.includes("<img"), "must not contain raw img tag from poison");
  assert.ok(!html.includes("<script"), "must not contain raw script from poison");
  assert.ok(!html.includes("onerror="), "must not contain onerror handler");
  assert.ok(!html.includes("onload="), "must not contain onload handler");
  // Numeric values only after sanitize
  assert.ok(html.includes(">0/5"), "clamped zero scores rendered");
  // Legitimate scores still work
  const good = api.opportunityScoreHtml(
    { rebuild_difficulty: 4, scalability: 5, market_potential: 3 },
    { difficulty: "Hard", scale: "Very High", market: "Medium" }
  );
  assert.ok(good.includes(">4/5"));
  assert.ok(good.includes("Hard"));
}

testEscapeHtml();
testSafeHttpUrl();
testStatusClassToken();
testClampScore();
testOpportunityScoreXssPoison();
console.log("OK tests/test_security_js.js");
