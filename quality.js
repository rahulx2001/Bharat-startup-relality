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
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
  root.BSRQuality = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
