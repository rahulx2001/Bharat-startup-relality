/**
 * Pure catalog quality + watchlist helpers (no DOM).
 * Unit-testable under Node; attaches BSRQuality on window in browsers.
 */
(function (root) {
  "use strict";

  const WATCHLIST_KEY = "bsr_watchlist_v1";
  const TIER_RANK = { gold: 4, silver: 3, bronze: 2, thin: 1, unset: 0 };

  function sourceCount(startup) {
    const s = startup && startup.sources;
    if (Array.isArray(s)) return s.length;
    if (typeof s === "string" && s.trim()) return 1;
    return 0;
  }

  /** Format USD-ish numbers for funding / peak valuation. Empty → "". */
  function formatUsdCompact(num) {
    if (num == null || num === "") return "";
    const n = Number(num);
    if (!Number.isFinite(n) || n <= 0) return "";
    if (n >= 1e9) return `$${(n / 1e9).toFixed(n >= 1e10 ? 0 : 1)}B`;
    if (n >= 1e6) return `$${(n / 1e6).toFixed(n >= 1e8 ? 0 : 1)}M`;
    if (n >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
    return `$${Math.round(n)}`;
  }

  /** Employees: number or string ranges. Empty → "". */
  function formatEmployees(value) {
    if (value == null || value === "") return "";
    if (typeof value === "string") {
      const t = value.trim();
      if (!t || t === "0") return "";
      // already human ("50-100", "1000+")
      if (/[a-zA-Z+\-]/.test(t) && !/^\d+(\.\d+)?$/.test(t)) return t;
      const n = Number(t.replace(/,/g, ""));
      if (!Number.isFinite(n) || n <= 0) return "";
      return formatEmployeeCount(n);
    }
    const n = Number(value);
    if (!Number.isFinite(n) || n <= 0) return "";
    return formatEmployeeCount(n);
  }

  function formatEmployeeCount(n) {
    if (n >= 1000) {
      const k = n / 1000;
      return `${k >= 10 ? Math.round(k) : k.toFixed(k % 1 ? 1 : 0)}K people`;
    }
    return `${Math.round(n)} people`;
  }

  /**
   * Years active from year_founded / year_died.
   * e.g. "2015–2024 (9 years)" or "2019–present (active)".
   */
  function formatYearsActive(startup, asOfYear) {
    const founded = Number(startup && startup.year_founded);
    if (!Number.isFinite(founded) || founded < 1900 || founded > 2100) return "";
    const diedRaw = startup && startup.year_died;
    const died = diedRaw == null || diedRaw === "" ? null : Number(diedRaw);
    const now = Number.isFinite(asOfYear) ? asOfYear : new Date().getUTCFullYear();
    if (died != null && Number.isFinite(died) && died >= founded) {
      const span = died - founded;
      const years = span <= 0 ? "<1 year" : span === 1 ? "1 year" : `${span} years`;
      return `${founded}–${died} (${years})`;
    }
    const span = Math.max(0, now - founded);
    const years = span <= 0 ? "<1 year" : span === 1 ? "1 year" : `${span} years`;
    return `${founded}–present (${years})`;
  }

  /** Status → short reader guidance (static map, not invented company facts). */
  function statusReaderTip(status) {
    const s = String(status || "").toLowerCase();
    if (s.includes("shut")) {
      return "Closed operations — study capital burn, unit economics, and late-stage governance.";
    }
    if (s.includes("strug") || s.includes("crisis") || s.includes("layoff")) {
      return "Still operating under stress — watch cash runway, layoffs, and pivot signals.";
    }
    if (s.includes("pivot")) {
      return "Changed direction — compare original thesis vs new product and who stayed.";
    }
    if (s.includes("come") || s.includes("recover") || s.includes("ipo")) {
      return "Turnaround path — note what changed in product, costs, and capital.";
    }
    return "Track status over time against funding raised and competitive set.";
  }

  /**
   * At-a-glance facts for readers. Only real catalog fields.
   * Returns [{label, value}] — omit empty values.
   */
  function keyFactsFromStartup(startup, asOfYear) {
    const s = startup || {};
    const facts = [];
    const funding = formatUsdCompact(s.funding_burned_usd);
    if (funding) facts.push({ label: "Funding raised / at risk", value: funding });
    const peak = formatUsdCompact(s.peak_valuation);
    if (peak) facts.push({ label: "Peak valuation", value: peak });
    const emp = formatEmployees(s.employees);
    if (emp) facts.push({ label: "Team size (peak/known)", value: emp });
    const years = formatYearsActive(s, asOfYear);
    if (years) facts.push({ label: "Years active", value: years });
    if (s.headquarters) facts.push({ label: "Headquarters", value: String(s.headquarters) });
    if (s.category) facts.push({ label: "Category", value: String(s.category) });
    if (s.status) facts.push({ label: "Status", value: String(s.status) });
    const founders = Array.isArray(s.founders) ? s.founders.filter(Boolean) : [];
    if (founders.length) {
      facts.push({
        label: "Founders",
        value: founders.slice(0, 4).join(", ") + (founders.length > 4 ? ` +${founders.length - 4}` : ""),
      });
    }
    const inv = Array.isArray(s.investors) ? s.investors.filter(Boolean) : [];
    if (inv.length) {
      facts.push({
        label: "Notable investors",
        value: inv.slice(0, 4).join(", ") + (inv.length > 4 ? ` +${inv.length - 4}` : ""),
      });
    }
    return facts;
  }

  function normalizeTier(startup) {
    const t = String((startup && startup.profile_tier) || "")
      .toLowerCase()
      .trim();
    if (t === "gold" || t === "silver" || t === "bronze" || t === "thin") return t;
    return "unset";
  }

  /** Higher = better research depth (honest fields only). */
  function qualityRank(startup) {
    const tier = normalizeTier(startup);
    let rank = (TIER_RANK[tier] || 0) * 1000;
    const score = Number(startup && startup.research_score);
    if (Number.isFinite(score)) rank += Math.max(0, Math.min(100, score));
    rank += Math.min(50, sourceCount(startup) * 10);
    if (startup && startup.research_status === "gold_pass") rank += 200;
    if (startup && startup.research_rejected) rank -= 100;
    return rank;
  }

  function qualityBadgeLabel(startup) {
    const tier = normalizeTier(startup);
    const score = Number(startup && startup.research_score);
    const scorePart = Number.isFinite(score) ? ` · ${Math.round(score)}` : "";
    const src = sourceCount(startup);
    const srcPart = src > 0 ? ` · ${src} src` : " · no sources";
    if (tier === "gold" && startup && startup.research_status === "gold_pass") {
      return `Gold verified${scorePart}${srcPart}`;
    }
    if (tier === "gold") {
      // Label says gold but gate did not pass — stay honest
      return `Unverified gold label${scorePart}${srcPart}`;
    }
    const pretty = tier === "unset" ? "Unscored" : tier.charAt(0).toUpperCase() + tier.slice(1);
    return `${pretty}${scorePart}${srcPart}`;
  }

  function qualityBadgeClass(startup) {
    const tier = normalizeTier(startup);
    if (tier === "gold" && startup && startup.research_status === "gold_pass") return "tier-gold";
    if (tier === "gold") return "tier-unverified";
    if (tier === "silver") return "tier-silver";
    if (tier === "bronze") return "tier-bronze";
    if (tier === "thin") return "tier-thin";
    return "tier-unset";
  }

  function matchesQualityFilter(startup, filter) {
    const f = String(filter || "all").toLowerCase();
    if (!f || f === "all") return true;
    if (f === "gold") {
      return normalizeTier(startup) === "gold" && startup.research_status === "gold_pass";
    }
    if (f === "has_sources") return sourceCount(startup) > 0;
    if (f === "no_sources") return sourceCount(startup) === 0;
    if (f === "blocked") {
      return Boolean(startup.research_rejected) || startup.research_status === "blocked";
    }
    return normalizeTier(startup) === f;
  }

  function compareByQuality(a, b) {
    const d = qualityRank(b) - qualityRank(a);
    if (d !== 0) return d;
    return String(a.startup_name || "").localeCompare(String(b.startup_name || ""));
  }

  function compareByRecency(a, b) {
    const da = String(a.updated_at || a.added_at || "");
    const db = String(b.updated_at || b.added_at || "");
    const d = db.localeCompare(da);
    if (d !== 0) return d;
    return String(a.startup_name || "").localeCompare(String(b.startup_name || ""));
  }

  function sortStartupsList(items, sortBy) {
    const list = Array.isArray(items) ? items.slice() : [];
    switch (String(sortBy || "default")) {
      case "quality":
        return list.sort(compareByQuality);
      case "recent":
        return list.sort(compareByRecency);
      case "funding":
        return list.sort(
          (a, b) => (Number(b.funding_burned_usd) || 0) - (Number(a.funding_burned_usd) || 0)
        );
      case "year_died":
        return list.sort((a, b) => (Number(b.year_died) || 0) - (Number(a.year_died) || 0));
      case "name":
        return list.sort((a, b) =>
          String(a.startup_name || "").localeCompare(String(b.startup_name || ""))
        );
      default:
        return list;
    }
  }

  function loadWatchlist(storage) {
    const store = storage || (typeof localStorage !== "undefined" ? localStorage : null);
    if (!store) return [];
    try {
      const raw = JSON.parse(store.getItem(WATCHLIST_KEY) || "[]");
      if (!Array.isArray(raw)) return [];
      return raw.map(String).filter(Boolean).slice(0, 200);
    } catch (_) {
      return [];
    }
  }

  function saveWatchlist(names, storage) {
    const store = storage || (typeof localStorage !== "undefined" ? localStorage : null);
    const clean = Array.isArray(names)
      ? names.map(String).filter(Boolean).slice(0, 200)
      : [];
    if (store) {
      try {
        store.setItem(WATCHLIST_KEY, JSON.stringify(clean));
      } catch (_) {
        /* quota */
      }
    }
    return clean;
  }

  function isWatched(name, storage) {
    const n = String(name || "");
    return loadWatchlist(storage).includes(n);
  }

  function toggleWatchlist(name, storage) {
    const n = String(name || "").trim();
    if (!n) return { names: loadWatchlist(storage), watched: false };
    let names = loadWatchlist(storage);
    const idx = names.indexOf(n);
    let watched;
    if (idx >= 0) {
      names = names.filter((x) => x !== n);
      watched = false;
    } else {
      names = names.concat([n]).slice(-200);
      watched = true;
    }
    saveWatchlist(names, storage);
    return { names, watched };
  }

  const MONTHS = {
    jan: 1, january: 1, feb: 2, february: 2, mar: 3, march: 3,
    apr: 4, april: 4, may: 5, jun: 6, june: 6, jul: 7, july: 7,
    aug: 8, august: 8, sep: 9, sept: 9, september: 9,
    oct: 10, october: 10, nov: 11, november: 11, dec: 12, december: 12,
  };

  /**
   * Parse free-form timeline dates to a sortable key (YYYYMMDD number).
   * Supports: "Jul 2014", "January 2025", "2020-05", "2020", "Q3 2020", ISO dates.
   * Unparseable → null (sorted last, stable).
   */
  function timelineDateKey(dateStr) {
    const raw = String(dateStr == null ? "" : dateStr).trim();
    if (!raw) return null;

    // ISO / YYYY-MM-DD / YYYY-MM
    const iso = raw.match(/^(\d{4})(?:-(\d{1,2})(?:-(\d{1,2}))?)?/);
    if (iso && raw.indexOf(iso[0]) === 0 && /^\d{4}/.test(raw)) {
      const y = Number(iso[1]);
      const m = iso[2] ? Number(iso[2]) : 1;
      const d = iso[3] ? Number(iso[3]) : 1;
      if (y >= 1900 && y <= 2100) return y * 10000 + m * 100 + d;
    }

    // Q1 2020 / Q3'20
    const q = raw.match(/Q\s*([1-4])\s*['’]?\s*(\d{2,4})/i);
    if (q) {
      let y = Number(q[2]);
      if (y < 100) y += 2000;
      const m = (Number(q[1]) - 1) * 3 + 1;
      return y * 10000 + m * 100 + 1;
    }

    // Mon YYYY / Month YYYY (e.g. "Jul 2014", "January 2025")
    const monYear = raw.match(
      /\b(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sept?|oct|nov|dec)\b\.?\s*['’]?\s*(\d{4})\b/i
    );
    if (monYear) {
      const token = monYear[1].toLowerCase();
      const month = MONTHS[token] || MONTHS[token.slice(0, 3)] || 1;
      return Number(monYear[2]) * 10000 + month * 100 + 1;
    }

    // Bare year
    const yearOnly = raw.match(/\b(19|20)\d{2}\b/);
    if (yearOnly) return Number(yearOnly[0]) * 10000 + 101;

    return null;
  }

  /** Oldest → newest. Unparseable dates keep relative order at the end. */
  function sortTimeline(events) {
    const list = Array.isArray(events) ? events.slice() : [];
    return list
      .map((ev, idx) => ({
        ev,
        idx,
        key: timelineDateKey(ev && (ev.date != null ? ev.date : ev.year)),
      }))
      .sort((a, b) => {
        if (a.key == null && b.key == null) return a.idx - b.idx;
        if (a.key == null) return 1;
        if (b.key == null) return -1;
        if (a.key !== b.key) return a.key - b.key;
        return a.idx - b.idx;
      })
      .map((x) => x.ev);
  }

  const api = {
    WATCHLIST_KEY,
    sourceCount,
    normalizeTier,
    qualityRank,
    qualityBadgeLabel,
    qualityBadgeClass,
    matchesQualityFilter,
    compareByQuality,
    compareByRecency,
    sortStartupsList,
    loadWatchlist,
    saveWatchlist,
    isWatched,
    toggleWatchlist,
    timelineDateKey,
    sortTimeline,
    formatUsdCompact,
    formatEmployees,
    formatYearsActive,
    statusReaderTip,
    keyFactsFromStartup,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
  root.BSRQuality = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
