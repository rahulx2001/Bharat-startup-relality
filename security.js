/**
 * Pure browser security helpers for catalog/user text.
 * No dependencies. Safe to unit-test under Node.
 */
(function (root) {
  "use strict";

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  /**
   * Allow only http(s) absolute URLs for href. Reject javascript:, data:, etc.
   */
  function safeHttpUrl(value) {
    if (value == null) return "";
    const raw = String(value).trim();
    if (!raw) return "";
    try {
      // Support absolute URLs only for external links
      const u = new URL(raw);
      if (u.protocol !== "http:" && u.protocol !== "https:") return "";
      return u.toString();
    } catch (_) {
      return "";
    }
  }

  /**
   * Map status to a known CSS class token (allowlist — never inject from free text).
   * Must match styles.css: .card-status.dead | .struggling | .pivoted | .comeback
   */
  function statusClassToken(status) {
    const s = String(status || "").toLowerCase();
    if (s.includes("shut")) return "dead";
    if (s.includes("strug") || s.includes("crisis") || s.includes("layoff")) return "struggling";
    if (s.includes("pivot")) return "pivoted";
    if (s.includes("come") || s.includes("recover") || s.includes("grow") || s.includes("ipo")) {
      return "comeback";
    }
    return "struggling";
  }

  /** Clamp numeric score to integer 0..max for safe class generation. */
  function clampScore(value, max) {
    const n = Number(value);
    if (!Number.isFinite(n)) return 0;
    return Math.max(0, Math.min(max, Math.floor(n)));
  }

  /**
   * Sanitize opportunity_score from catalog JSON.
   * Poisoned strings/objects become 0 — never free-text in HTML sinks.
   */
  function sanitizeOppScore(score) {
    const s = score && typeof score === "object" ? score : {};
    return {
      rebuild_difficulty: clampScore(s.rebuild_difficulty, 5),
      scalability: clampScore(s.scalability, 5),
      market_potential: clampScore(s.market_potential, 5),
    };
  }

  /**
   * Safe innerHTML fragment for opportunity cards (all values numeric/allowlisted).
   */
  function opportunityScoreHtml(score, labels) {
    const o = sanitizeOppScore(score);
    const lab = labels || {};
    const diff = escapeHtml(String(lab.difficulty || ""));
    const scale = escapeHtml(String(lab.scale || ""));
    const market = escapeHtml(String(lab.market || ""));
    // bars: only numeric clamped spans
    function bar(v, color) {
      const safeColor = color === "green" || color === "orange" ? color : "";
      let html = "";
      for (let i = 1; i <= 5; i++) {
        const filled = i <= v ? `filled ${safeColor}`.trim() : "";
        html += `<span class="${filled}"></span>`;
      }
      return html;
    }
    return (
      `<div class="opportunity-card">` +
      `<div class="opp-label">🔧 Rebuild Difficulty</div>` +
      `<div class="opp-bar">${bar(o.rebuild_difficulty, "")}</div>` +
      `<div class="opp-value">${escapeHtml(String(o.rebuild_difficulty))}/5 (${diff})</div>` +
      `</div>` +
      `<div class="opportunity-card">` +
      `<div class="opp-label">📈 Scalability Potential</div>` +
      `<div class="opp-bar">${bar(o.scalability, "green")}</div>` +
      `<div class="opp-value">${escapeHtml(String(o.scalability))}/5 (${scale})</div>` +
      `</div>` +
      `<div class="opportunity-card">` +
      `<div class="opp-label">🎯 Market Potential Today</div>` +
      `<div class="opp-bar">${bar(o.market_potential, "orange")}</div>` +
      `<div class="opp-value">${market}</div>` +
      `</div>`
    );
  }

  const api = {
    escapeHtml,
    safeHttpUrl,
    statusClassToken,
    clampScore,
    sanitizeOppScore,
    opportunityScoreHtml,
  };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
  root.BSRSecurity = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
