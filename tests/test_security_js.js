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

testEscapeHtml();
testSafeHttpUrl();
testStatusClassToken();
testClampScore();
console.log("OK tests/test_security_js.js");
