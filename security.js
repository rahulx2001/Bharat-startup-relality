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

  /** Clamp numeric score to integer 1..max for safe class generation. */
  function clampScore(value, max) {
    const n = Number(value);
    if (!Number.isFinite(n)) return 0;
    return Math.max(0, Math.min(max, Math.floor(n)));
  }

  const api = { escapeHtml, safeHttpUrl, statusClassToken, clampScore };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
  root.BSRSecurity = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
