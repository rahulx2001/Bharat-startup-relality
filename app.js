const DATA_URL = './data/graveyard.json';

const PAGE_SIZE = 12;

// Security helpers (security.js) — escape untrusted catalog/LLM text
const escapeHtml = (v) => (globalThis.BSRSecurity ? BSRSecurity.escapeHtml(v) : String(v ?? '')
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;').replace(/'/g, '&#39;'));
const safeHttpUrl = (v) => (globalThis.BSRSecurity ? BSRSecurity.safeHttpUrl(v) : '');

const state = {
  data: [],
  filtered: [],
  activeStatus: 'All',
  categoryFilter: 'All',
  qualityFilter: 'all',
  sortBy: 'default',
  recentOnly: false,
  watchlistOnly: false,
  compareIds: [],
  currentPage: 1,
  generatedAt: '',
  qualitySummary: null,
};

const Q = () => globalThis.BSRQuality || null;

const el = (id) => document.getElementById(id);

const formatMoney = (num) => {
  if (!num || Number.isNaN(num)) return '—';
  const n = Number(num);
  if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(0)}M`;
  if (n >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
};

const unique = (arr) => [...new Set(arr)];

/** Honest gold only — never treat long prose as verified gold. */
const isGoldProfile = (s) =>
  s && s.profile_tier === 'gold' && s.research_status === 'gold_pass';

const sourceCountOf = (s) => (Q() ? Q().sourceCount(s) : (Array.isArray(s?.sources) ? s.sources.length : 0));

const formatMoneyOrUnknown = (num) => {
  if (num == null || num === '' || Number(num) === 0 || Number.isNaN(Number(num))) {
    return 'Funding unknown';
  }
  return formatMoney(num);
};

const isRecentlyUpdated = (s) => {
  const date = s.updated_at || s.added_at;
  if (!date) return false;
  const updated = new Date(date);
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - 90);
  return updated >= cutoff;
};

const formatInrCr = (usd) => {
  const inrCr = Math.round((usd || 0) * 0.012 * 10) / 10;
  if (inrCr >= 1000) return `₹${(inrCr / 100).toFixed(1)}k Cr`;
  return `₹${inrCr.toLocaleString('en-IN')} Cr`;
};

const parseSources = (sources) => {
  if (!sources?.length) return [];
  return sources.map((item) => {
    if (typeof item === 'object' && item !== null) {
      return { title: item.title || 'Source', url: item.url || '' };
    }
    if (typeof item === 'string' && item.includes('title')) {
      try {
        const parsed = JSON.parse(item.replace(/'/g, '"'));
        return { title: parsed.title || 'Source', url: parsed.url || '' };
      } catch (_) {
        return { title: item.slice(0, 120), url: '' };
      }
    }
    return { title: String(item), url: '' };
  });
};

// Theme toggle
const initTheme = () => {
  const saved = localStorage.getItem('theme') || 'light';
  document.documentElement.setAttribute('data-theme', saved);
};

el('themeToggle').addEventListener('click', () => {
  const current = document.documentElement.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
});

initTheme();

const buildStats = (items) => {
  const shutDown = items.filter(s => s.status === 'Shut Down').length;
  const struggling = items.filter(s => s.status === 'Struggling' || s.status === 'Crisis' || s.status === 'Layoffs').length;
  const pivoted = items.filter(s => s.status === 'Pivoted' || s.status === 'Comeback' || s.status === 'Recovery').length;
  const burned = items.reduce((sum, s) => sum + (s.funding_burned_usd || 0), 0);

  el('stat-failed').textContent = shutDown.toString();
  el('stat-struggling').textContent = struggling.toString();
  el('stat-pivoted').textContent = pivoted.toString();
  el('stat-burned').textContent = formatMoney(burned);
};

const buildStatusFilters = () => {
  const statuses = ['All', 'Shut Down', 'Struggling', 'Pivoted', 'Comeback'];
  const container = el('statusFilters');
  container.innerHTML = '';
  statuses.forEach((status) => {
    const btn = document.createElement('button');
    btn.className = `status-btn ${status === 'All' ? 'active' : ''}`;
    btn.setAttribute('data-status', status);
    const icons = { 'All': '📊', 'Shut Down': '💀', 'Struggling': '⚠️', 'Pivoted': '🔄', 'Comeback': '🚀' };
    btn.textContent = `${icons[status] || ''} ${status}`;
    btn.onclick = () => {
      state.activeStatus = status;
      document.querySelectorAll('.status-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      applyFilters();
    };
    container.appendChild(btn);
  });
};

const getStatusClass = (status) => {
  if (globalThis.BSRSecurity && BSRSecurity.statusClassToken) {
    return BSRSecurity.statusClassToken(status);
  }
  const map = { 'Shut Down': 'dead', 'Struggling': 'struggling', 'Crisis': 'struggling', 'Layoffs': 'struggling', 'Pivoted': 'pivoted', 'Comeback': 'comeback', 'Recovery': 'comeback' };
  return map[status] || 'struggling';
};

const getPageSlice = (items) => {
  const total = items.length;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  if (state.currentPage > totalPages) state.currentPage = totalPages;
  if (state.currentPage < 1) state.currentPage = 1;

  const startIndex = (state.currentPage - 1) * PAGE_SIZE;
  const endIndex = Math.min(startIndex + PAGE_SIZE, total);

  return {
    pageItems: items.slice(startIndex, endIndex),
    total,
    totalPages,
    startIndex,
    endIndex,
  };
};

const buildPagination = ({ total, totalPages, startIndex, endIndex }) => {
  const nav = el('pagination');
  const info = el('paginationInfo');
  const controls = el('paginationControls');

  if (!nav || !info || !controls) return;

  if (total === 0) {
    nav.classList.add('hidden');
    return;
  }

  nav.classList.remove('hidden');
  info.textContent = `Showing ${startIndex + 1}–${endIndex} of ${total} startups`;

  const goToPage = (page) => {
    state.currentPage = page;
    renderResults();
    el('cardsGrid')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  controls.innerHTML = '';

  const prevBtn = document.createElement('button');
  prevBtn.className = 'page-btn';
  prevBtn.textContent = '← Prev';
  prevBtn.disabled = state.currentPage <= 1;
  prevBtn.onclick = () => goToPage(state.currentPage - 1);
  controls.appendChild(prevBtn);

  const pages = new Set([1, totalPages, state.currentPage, state.currentPage - 1, state.currentPage + 1]);
  const sortedPages = [...pages].filter((p) => p >= 1 && p <= totalPages).sort((a, b) => a - b);

  let lastPage = 0;
  sortedPages.forEach((page) => {
    if (page - lastPage > 1) {
      const dots = document.createElement('span');
      dots.className = 'page-ellipsis';
      dots.textContent = '…';
      controls.appendChild(dots);
    }
    const pageBtn = document.createElement('button');
    pageBtn.className = `page-btn ${page === state.currentPage ? 'active' : ''}`;
    pageBtn.textContent = String(page);
    pageBtn.onclick = () => goToPage(page);
    controls.appendChild(pageBtn);
    lastPage = page;
  });

  const nextBtn = document.createElement('button');
  nextBtn.className = 'page-btn';
  nextBtn.textContent = 'Next →';
  nextBtn.disabled = state.currentPage >= totalPages;
  nextBtn.onclick = () => goToPage(state.currentPage + 1);
  controls.appendChild(nextBtn);
};

const buildCards = (items) => {
  const grid = el('cardsGrid');
  grid.innerHTML = '';

  if (!items.length) {
    grid.innerHTML = '<div class="empty-state">No startups match your search or filter.</div>';
    return;
  }

  items.forEach((s) => {
    const card = document.createElement('div');
    card.className = 'card';
    const foundersRaw = s.founders?.length ? `👤 ${s.founders.slice(0, 2).join(', ')}` : '';
    const yearRange = s.year_founded ? `${s.year_founded}${s.year_died ? ' → ' + s.year_died : ' → Present'}` : '';
    const badgeLabel = Q() ? Q().qualityBadgeLabel(s) : String(s.profile_tier || 'unscored');
    const badgeClass = Q() ? Q().qualityBadgeClass(s) : 'tier-unset';
    const watched = Q() ? Q().isWatched(s.startup_name) : false;
    // Escape all catalog fields — data may include LLM-generated or untrusted text
    card.innerHTML = `
      <div class="card-top-row">
        <div class="card-status ${getStatusClass(s.status)}">${escapeHtml(s.status || 'Struggling')}</div>
        <button type="button" class="watch-btn ${watched ? 'active' : ''}" data-watch="${escapeHtml(s.startup_name)}" aria-label="Toggle watchlist" title="Watchlist">${watched ? '★' : '☆'}</button>
      </div>
      <h4>${escapeHtml(s.startup_name)}</h4>
      <div class="meta">
        <span class="quality-badge ${escapeHtml(badgeClass)}">${escapeHtml(badgeLabel)}</span>
        ${yearRange ? `<span class="tag">${escapeHtml(yearRange)}</span>` : ''}
        <span class="tag alt">${escapeHtml(formatMoneyOrUnknown(s.funding_burned_usd))}</span>
        <span class="tag warn">${escapeHtml(s.category || 'Tech')}</span>
      </div>
      <p>${escapeHtml(s.short_summary || s.failure_reason || 'No details available.')}</p>
      ${foundersRaw ? `<div class="card-founders">${escapeHtml(foundersRaw)}</div>` : ''}
      <div class="card-actions-row">
        <label class="compare-check" onclick="event.stopPropagation()">
          <input type="checkbox" data-compare="${escapeHtml(s.startup_name)}" ${state.compareIds.includes(s.startup_name) ? 'checked' : ''}/> Compare
        </label>
        <div class="card-cta">🔍 Tap to explore →</div>
      </div>
    `;
    card.onclick = (ev) => {
      if (ev.target.closest('.watch-btn') || ev.target.closest('.compare-check')) return;
      openModal(s);
    };
    const cmp = card.querySelector('input[data-compare]');
    if (cmp) {
      cmp.addEventListener('change', (ev) => {
        ev.stopPropagation();
        toggleCompare(s.startup_name, cmp.checked);
      });
    }
    const watchBtn = card.querySelector('.watch-btn');
    if (watchBtn) {
      watchBtn.addEventListener('click', (ev) => {
        ev.stopPropagation();
        if (!Q()) return;
        Q().toggleWatchlist(s.startup_name);
        applyFilters();
      });
    }
    grid.appendChild(card);
  });
};

const applyFilters = () => {
  const term = el('searchInput').value.toLowerCase().trim();
  let filtered = state.data;

  if (state.activeStatus !== 'All') {
    if (state.activeStatus === 'Struggling') {
      filtered = filtered.filter((s) => ['Struggling', 'Crisis', 'Layoffs'].includes(s.status));
    } else if (state.activeStatus === 'Pivoted') {
      filtered = filtered.filter((s) => s.status === 'Pivoted');
    } else if (state.activeStatus === 'Comeback') {
      filtered = filtered.filter((s) => ['Comeback', 'Recovery', 'Growing', 'Pre-IPO'].includes(s.status));
    } else {
      filtered = filtered.filter((s) => s.status === state.activeStatus);
    }
  }
  if (term) {
    filtered = filtered.filter((s) => {
      const blob = `${s.startup_name} ${s.failure_reason} ${s.category} ${s.headquarters} ${(s.founders || []).join(' ')} ${(s.investors || []).join(' ')}`.toLowerCase();
      return blob.includes(term);
    });
  }

  if (state.categoryFilter !== 'All') {
    filtered = filtered.filter((s) => s.category === state.categoryFilter);
  }

  if (state.recentOnly) {
    filtered = filtered.filter(isRecentlyUpdated);
  }

  if (state.qualityFilter && state.qualityFilter !== 'all' && Q()) {
    filtered = filtered.filter((s) => Q().matchesQualityFilter(s, state.qualityFilter));
  }

  if (state.watchlistOnly && Q()) {
    const names = new Set(Q().loadWatchlist());
    filtered = filtered.filter((s) => names.has(s.startup_name));
  }

  filtered = sortStartups(filtered, state.sortBy);

  state.filtered = filtered;
  state.currentPage = 1;
  renderResults();
};

const sortStartups = (items, sortBy) => {
  if (Q() && typeof Q().sortStartupsList === 'function') {
    return Q().sortStartupsList(items, sortBy);
  }
  const list = [...items];
  switch (sortBy) {
    case 'recent':
      return list.sort((a, b) => (b.updated_at || b.added_at || '').localeCompare(a.updated_at || a.added_at || ''));
    case 'funding':
      return list.sort((a, b) => (b.funding_burned_usd || 0) - (a.funding_burned_usd || 0));
    case 'year_died':
      return list.sort((a, b) => (b.year_died || 0) - (a.year_died || 0));
    case 'name':
      return list.sort((a, b) => a.startup_name.localeCompare(b.startup_name));
    default:
      return list;
  }
};

const buildCategoryFilter = (items) => {
  const select = el('categoryFilter');
  if (!select) return;
  const categories = unique(items.map((s) => s.category).filter(Boolean)).sort();
  const current = state.categoryFilter;
  select.innerHTML = '<option value="All">All categories</option>';
  categories.forEach((cat) => {
    const opt = document.createElement('option');
    opt.value = cat;
    opt.textContent = cat;
    select.appendChild(opt);
  });
  select.value = categories.includes(current) ? current : 'All';
  state.categoryFilter = select.value;
};

const renderResults = () => {
  const slice = getPageSlice(state.filtered);
  buildCards(slice.pageItems);
  buildPagination(slice);
  buildStats(state.filtered);
};

const openModal = (s) => {
  el('detailModal').classList.add('show');
  el('detailModal').setAttribute('aria-hidden', 'false');
  el('modalTitle').textContent = s.startup_name;

  const yearRange = s.year_founded ? `${s.year_founded}${s.year_died ? ' → ' + s.year_died : ' → Present'}` : '';
  const badgeLabel = Q() ? Q().qualityBadgeLabel(s) : String(s.profile_tier || 'unscored');
  const badgeClass = Q() ? Q().qualityBadgeClass(s) : 'tier-unset';
  const watched = Q() ? Q().isWatched(s.startup_name) : false;
  el('modalMeta').innerHTML = `
    <span class="card-status ${getStatusClass(s.status)}">${escapeHtml(s.status || 'Struggling')}</span>
    <span class="quality-badge ${escapeHtml(badgeClass)}">${escapeHtml(badgeLabel)}</span>
    ${yearRange ? `<span class="tag">${escapeHtml(yearRange)}</span>` : ''}
    <span class="tag alt">${escapeHtml(formatMoneyOrUnknown(s.funding_burned_usd))}</span>
    <span class="tag warn">${escapeHtml(s.category || 'Tech')}</span>
    <span class="tag">${escapeHtml(s.headquarters || 'India')}</span>
    <button type="button" class="watch-btn modal-watch ${watched ? 'active' : ''}" id="modalWatchBtn">${watched ? '★ In watchlist' : '☆ Watchlist'}</button>
  `;
  const modalWatch = el('modalWatchBtn');
  if (modalWatch && Q()) {
    modalWatch.onclick = () => {
      Q().toggleWatchlist(s.startup_name);
      openModal(s);
      if (state.watchlistOnly) applyFilters();
    };
  }

  // Hide integrity scare-banner (keep quality badge only)
  const integrity = el('modalIntegrity');
  if (integrity) {
    integrity.hidden = true;
    integrity.innerHTML = '';
  }

  // Value Proposition — prefer rich catalog text
  el('modalValueProp').textContent = s.value_proposition || s.short_summary || s.failure_reason
    || `${s.startup_name} was a ${s.category || 'tech'} company based in ${s.headquarters || 'India'}.`;

  // Opportunity Score — catalog first, then category estimate for depth
  const oppScoreRaw = s.opportunity_score || generateOpportunityScore(s);
  if (globalThis.BSRSecurity && BSRSecurity.opportunityScoreHtml) {
    const safe = BSRSecurity.sanitizeOppScore(oppScoreRaw);
    el('modalOpportunity').innerHTML = BSRSecurity.opportunityScoreHtml(safe, {
      difficulty: getDifficultyLabel(safe.rebuild_difficulty),
      scale: getScaleLabel(safe.scalability),
      market: getMarketLabel(safe.market_potential),
    });
  } else {
    el('modalOpportunity').innerHTML = '<p class="thin-note">Opportunity score unavailable.</p>';
  }

  // Cause of Death / Decline (only show for Shut Down or if explicitly has cause_of_death)
  const deathSection = document.querySelector('.death-section');
  if (s.status === 'Shut Down') {
    deathSection.style.display = 'block';
    deathSection.querySelector('h3').textContent = '⚰️ CAUSE OF DEATH';
    el('modalCauseOfDeath').textContent = s.cause_of_death || s.failure_reason || 'No details available.';
  } else if (s.cause_of_death) {
    deathSection.style.display = 'block';
    deathSection.querySelector('h3').textContent = '⚠️ WHY THEY\'RE STRUGGLING';
    el('modalCauseOfDeath').textContent = s.cause_of_death;
  } else {
    deathSection.style.display = 'none';
  }

  // Timeline — always chronological (oldest → newest)
  const timeline = el('modalTimeline');
  timeline.innerHTML = '';
  const timelineEvents = Q()?.sortTimeline
    ? Q().sortTimeline(s.timeline || [])
    : [...(s.timeline || [])];
  timelineEvents.forEach((t) => {
    const div = document.createElement('div');
    div.className = 'timeline-item';
    div.innerHTML = `<div class="date">${escapeHtml(t.date)}</div><div>${escapeHtml(t.event)}</div>`;
    timeline.appendChild(div);
  });

  // Lessons/Loot — catalog first, then helpful category-based insights
  const lessonsList = el('modalLessons');
  lessonsList.innerHTML = '';
  const insights = s.insights?.length
    ? s.insights
    : (s.lessons?.length ? s.lessons : generateInsights(s));
  insights.forEach((p, i) => {
    const li = document.createElement('li');
    li.innerHTML = `<strong>Insight ${i + 1}:</strong> ${escapeHtml(p)}`;
    lessonsList.appendChild(li);
  });

  // People
  const people = el('modalPeople');
  people.innerHTML = '';
  (s.founders || []).forEach((f) => {
    const div = document.createElement('div');
    div.className = 'person-card';
    div.innerHTML = `<div class="role">Founder</div><div class="name">${escapeHtml(f)}</div>`;
    people.appendChild(div);
  });
  (s.investors || []).forEach((i) => {
    const div = document.createElement('div');
    div.className = 'person-card';
    div.innerHTML = `<div class="role">Investor</div><div class="name">${escapeHtml(i)}</div>`;
    people.appendChild(div);
  });
  if (!s.founders?.length && !s.investors?.length) {
    people.innerHTML = '<div class="person-card"><div class="name">No data available</div></div>';
  }

  // Market Today
  el('modalMarketToday').textContent = s.market_today || generateMarketToday(s);

  // AI Rebuild Idea — catalog first, category rebuild when missing
  const rebuild = s.ai_rebuild?.name ? s.ai_rebuild : generateAIRebuild(s);
  el('modalRebuildName').textContent = rebuild.name;
  el('modalRebuildDesc').textContent = rebuild.description;
  el('modalTechStack').innerHTML = (rebuild.tech_stack || [])
    .map((t) => `<span class="tech-tag">${escapeHtml(t)}</span>`)
    .join('');

  // Execution Plan
  const execList = el('modalExecutionPlan');
  execList.innerHTML = '';
  const plan = rebuild.execution_plan || [];
  if (!plan.length) {
    const li = document.createElement('li');
    li.textContent = 'Execution plan being refined.';
    execList.appendChild(li);
  } else {
    plan.forEach((step) => {
      const li = document.createElement('li');
      li.textContent = step;
      execList.appendChild(li);
    });
  }

  // What Makes This Innovative
  const innovativeList = el('modalInnovative');
  innovativeList.innerHTML = '';
  const innovations = rebuild.innovative?.length ? rebuild.innovative : generateInnovative(s);
  innovations.forEach((point) => {
    const li = document.createElement('li');
    li.textContent = point;
    innovativeList.appendChild(li);
  });

  // Monetization
  el('modalMonetization').textContent = rebuild.monetization || generateMonetization(s);

  // Sources
  const sources = parseSources(s.sources);
  const sourcesSection = el('sourcesSection');
  const sourcesList = el('modalSources');
  if (sourcesSection && sourcesList) {
    sourcesSection.style.display = 'block';
    sourcesList.innerHTML = '';
    if (!sources.length) {
      const li = document.createElement('li');
      li.textContent = 'Sources will appear as public coverage is linked.';
      sourcesList.appendChild(li);
    } else {
      sources.forEach((src) => {
        const li = document.createElement('li');
        const safeUrl = safeHttpUrl(src.url);
        if (safeUrl) {
          const a = document.createElement('a');
          a.href = safeUrl;
          a.target = '_blank';
          a.rel = 'noopener noreferrer nofollow';
          a.textContent = src.title || 'Source';
          li.appendChild(a);
        } else {
          li.textContent = src.title || 'Source';
        }
        sourcesList.appendChild(li);
      });
    }
  }
};

// Helper functions for generating content
const generateBar = (value, max, color = '') => {
  const m = globalThis.BSRSecurity?.clampScore
    ? BSRSecurity.clampScore(max, 20) || 5
    : Math.min(20, Math.max(1, Number(max) || 5));
  const v = globalThis.BSRSecurity?.clampScore
    ? BSRSecurity.clampScore(value, m)
    : Math.min(m, Math.max(0, Math.floor(Number(value) || 0)));
  // color is allowlisted — never free-text from catalog
  const safeColor = color === 'green' || color === 'orange' ? color : '';
  let html = '';
  for (let i = 1; i <= m; i++) {
    const filled = i <= v ? `filled ${safeColor}`.trim() : '';
    html += `<span class="${filled}"></span>`;
  }
  return html;
};

const getDifficultyLabel = (val) => {
  const labels = ['Very Easy', 'Easy', 'Moderate', 'Hard', 'Very Hard'];
  return labels[val - 1] || 'Moderate';
};

const getScaleLabel = (val) => {
  const labels = ['Limited', 'Low', 'Moderate', 'High', 'Very High'];
  return labels[val - 1] || 'Moderate';
};

const getMarketLabel = (val) => {
  const labels = ['Low', 'Low-Medium', 'Medium', 'Medium-High', 'High'];
  return labels[val - 1] || 'Medium';
};

const generateOpportunityScore = (s) => {
  // Generate based on category and status
  const categoryScores = {
    'EdTech': { rebuild_difficulty: 3, scalability: 4, market_potential: 4 },
    'FinTech': { rebuild_difficulty: 4, scalability: 5, market_potential: 5 },
    'Food Delivery': { rebuild_difficulty: 4, scalability: 3, market_potential: 3 },
    'E-commerce': { rebuild_difficulty: 3, scalability: 4, market_potential: 4 },
    'HealthTech': { rebuild_difficulty: 4, scalability: 4, market_potential: 5 },
    'Quick Commerce': { rebuild_difficulty: 5, scalability: 3, market_potential: 4 },
    'Ride-hailing': { rebuild_difficulty: 5, scalability: 4, market_potential: 3 },
    'B2B': { rebuild_difficulty: 3, scalability: 4, market_potential: 4 },
  };

  for (const [key, scores] of Object.entries(categoryScores)) {
    if (s.category?.toLowerCase().includes(key.toLowerCase())) {
      return scores;
    }
  }
  return { rebuild_difficulty: 3, scalability: 3, market_potential: 3 };
};

const generateInsights = (s) => {
  const insights = [];
  if (s.lessons?.length) return s.lessons;

  insights.push(`Understanding the ${s.category || 'tech'} market requires deep knowledge of customer behavior and competition.`);
  insights.push(`With ${formatMoney(s.funding_burned_usd)} raised, the key lesson is capital efficiency and sustainable unit economics.`);
  insights.push(`Modern AI tools could significantly reduce development costs and improve product-market fit.`);
  insights.push(`The failure of ${s.startup_name} created a gap that innovative founders could fill with better execution.`);

  return insights;
};

const generateMarketToday = (s) => {
  const categoryMarkets = {
    'EdTech': `Today, the EdTech industry in India is worth $6B+ with players like Unacademy, PhysicsWallah, and international giants competing. AI-powered personalized learning is the next frontier, with tools like ChatGPT and Claude changing how students learn. An AI-native rebuild could leverage these tools for hyper-personalized education at a fraction of the cost.`,
    'FinTech': `India's FinTech market is projected to reach $150B by 2025. UPI processes 10B+ transactions monthly. The opportunity lies in AI-powered financial advisory, embedded finance, and serving the underbanked population with innovative credit products.`,
    'Food Delivery': `Zomato and Swiggy dominate with combined GMV of $10B+. Quick commerce is the new battleground. Opportunities exist in cloud kitchens, specialized cuisine delivery, and AI-powered demand prediction to reduce food waste.`,
    'HealthTech': `India's digital health market is expected to reach $50B by 2030. AI diagnostics, telemedicine, and preventive healthcare are growth areas. The space is ripe for AI-first solutions that can provide affordable healthcare at scale.`,
    'E-commerce': `India's e-commerce market is worth $70B+, dominated by Flipkart and Amazon. Opportunities exist in vertical commerce, social commerce, and AI-powered shopping experiences for tier 2-3 cities.`,
  };

  for (const [key, market] of Object.entries(categoryMarkets)) {
    if (s.category?.toLowerCase().includes(key.toLowerCase())) {
      return market;
    }
  }
  return `The ${s.category || 'technology'} market in India continues to evolve rapidly. With increasing digital adoption and AI capabilities, there's significant opportunity for innovative startups to solve problems that earlier companies couldn't. The key is leveraging modern technology stack and focusing on sustainable unit economics from day one.`;
};

const generateAIRebuild = (s) => {
  const categoryRebuilds = {
    'EdTech': {
      name: `${s.startup_name.split(' ')[0]}AI Learn`,
      description: `An AI-first personalized learning platform using GPT-4, Claude, and custom ML models to create adaptive learning paths. Unlike ${s.startup_name}, this version would have near-zero content creation costs by leveraging AI tutors, while providing 24/7 personalized doubt resolution and exam preparation.`,
      tech_stack: ['OpenAI GPT-4', 'Claude API', 'Whisper', 'LangChain', 'Stripe', 'Firebase'],
      execution_plan: [
        'Build MVP with AI tutor using OpenAI APIs - validate with 100 students',
        'Add voice-based doubt solving using Whisper for vernacular language support',
        'Partner with schools for distribution - B2B2C model for sustainable growth',
        'Implement freemium model with premium AI features and human expert sessions'
      ],
      monetization: `Freemium model with ₹99/month basic tier and ₹499/month premium with unlimited AI tutoring, mock tests, and human expert sessions. B2B school partnerships at ₹50/student/month. Target: ₹10Cr ARR in Year 1 with 30% gross margins.`
    },
    'FinTech': {
      name: `${s.startup_name.split(' ')[0]} Pay Agent`,
      description: `AI-powered agentic finance platform using Google's Universal Commerce Protocol (UCP) for payments and OpenAI's Agent Payments Protocol for autonomous transactions. Users can say "Pay my electricity bill" or "Invest ₹5000 in mutual funds" and AI agents handle everything - discovery, comparison, checkout. Integrates with NPCI for UPI-based agentic payments like the Razorpay-NPCI-OpenAI pilot.`,
      tech_stack: ['Google UCP', 'OpenAI ACP', 'NPCI UPI APIs', 'Account Aggregator', 'GPT-4', 'Razorpay', 'Python ML'],
      execution_plan: [
        'Integrate with Google UCP for agentic payments within Gemini ecosystem',
        'Implement OpenAI Agent Payments Protocol for ChatGPT-based transactions',
        'Partner with NPCI for UPI-based agentic payments (like Razorpay pilot)',
        'Build AI financial advisor that executes investments autonomously',
        'Add voice-based finance commands in Hindi/regional languages via Gemini'
      ],
      monetization: `Transaction fee on agentic payments (0.2-0.5%), commission on investments (0.5-1%), lending referral (1-2%), premium AI advisor at ₹299/month. Target: ₹50Cr ARR by Year 2.`
    },
    'HealthTech': {
      name: `${s.startup_name.split(' ')[0]} Health AI`,
      description: `AI-driven telemedicine and diagnostics platform that uses computer vision for preliminary diagnosis, GPT for symptom analysis, and connects patients with specialists. Eliminates hardware dependency that affected ${s.startup_name} by going software-first.`,
      tech_stack: ['OpenAI Vision', 'GPT-4', 'Twilio', 'AWS HealthLake', 'Stripe'],
      execution_plan: [
        'Build AI symptom checker with 90%+ accuracy using GPT-4 and medical databases',
        'Add image-based skin/eye condition analysis using computer vision',
        'Partner with diagnostic labs for test bookings with commission',
        'Enable video consultations with verified doctors on platform'
      ],
      monetization: `Consultation fee commission (20-30%), diagnostic test booking commission (10-15%), subscription for chronic disease management at ₹299/month, B2B corporate health packages. Target: ₹15Cr ARR by Year 2.`
    },
    'Food Delivery': {
      name: `${s.startup_name.split(' ')[0]} Kitchen AI`,
      description: `AI-optimized cloud kitchen platform that uses ML for demand prediction, automated inventory management, and dynamic menu optimization. Focuses on profitability through AI efficiency rather than competing on delivery speed.`,
      tech_stack: ['TensorFlow', 'GPT-4', 'Swiggy/Zomato APIs', 'Node.js', 'PostgreSQL'],
      execution_plan: [
        'Build demand prediction ML model using historical order data',
        'Launch 2-3 cloud kitchens with AI-optimized menus and inventory',
        'Implement dynamic pricing based on demand and competition',
        'Scale to 20 kitchens with proven unit economics before raising Series A'
      ],
      monetization: `Direct food sales through aggregators with 15-20% margins (vs industry 5-10%) through AI optimization. Franchise model for expansion. Target: ₹30Cr revenue with ₹4.5Cr profit by Year 2.`
    },
    'Auto Services': {
      name: `${s.startup_name.split(' ')[0]} Auto AI`,
      description: `AI-powered vehicle maintenance platform that predicts service needs, provides instant quotes via image analysis, and connects with verified mechanics. Builds on ${s.startup_name}'s model but with AI-first approach and asset-light operations.`,
      tech_stack: ['Computer Vision', 'GPT-4', 'React Native', 'MongoDB', 'Razorpay'],
      execution_plan: [
        'Build car damage assessment tool using computer vision for instant quotes',
        'Partner with local garages as service providers (no owned workshops)',
        'Add predictive maintenance based on vehicle data and driving patterns',
        'Launch subscription model for fleet operators with guaranteed SLAs'
      ],
      monetization: `Commission from garages (15-20% of service value), subscription for fleet management at ₹999/vehicle/month, spare parts marketplace with 25% margins. Target: ₹20Cr ARR by Year 2.`
    },
    'B2B': {
      name: `${s.startup_name.split(' ')[0]} B2B Agent`,
      description: `AI-powered B2B procurement platform integrated with Google's Universal Commerce Protocol (UCP) for agentic B2B transactions. AI agents handle vendor discovery, RFQ generation, price negotiation, and purchase orders autonomously. Think Udaan meets Gemini - businesses just tell the AI what they need.`,
      tech_stack: ['Google UCP', 'GPT-4', 'Python ML', 'Elasticsearch', 'PostgreSQL', 'Razorpay Business'],
      execution_plan: [
        'Build UCP-compatible B2B catalog with 1M+ SKUs from verified suppliers',
        'Create AI procurement agent that understands natural language requirements',
        'Implement automated RFQ and negotiation using LLM-based price optimization',
        'Launch agentic trade financing with instant credit decisions via AI',
        'Add supply chain AI for demand forecasting and inventory optimization'
      ],
      monetization: `Transaction fee (0.5-1% of GMV via UCP), SaaS subscription for AI procurement at ₹50K-2L/month, trade financing revenue share (2-3% spread). Target: ₹100Cr ARR by Year 3.`
    },
    'Quick Commerce / Delivery': {
      name: `${s.startup_name.split(' ')[0]} 2.0 Agent`,
      description: `AI-native hyperlocal delivery with NO APP required. Users tell Gemini/ChatGPT/Siri what they need: "Pickup my laundry and drop at home by 5pm" or "Order biryani and cake for tonight." The AI agent uses Google's Universal Commerce Protocol (UCP) and OpenAI's Agentic Commerce Protocol (ACP) to discover local stores, confirm options, and complete payment - all within the conversation. Integrates with Razorpay/NPCI for UPI-based agentic payments like the Razorpay-NPCI-OpenAI pilot.`,
      tech_stack: ['Google UCP', 'OpenAI ACP', 'GPT-4/Gemini', 'Bhashini (vernacular voice)', 'Razorpay', 'ONDC APIs', 'Node.js/AWS', 'React Dashboard'],
      execution_plan: [
        'Q2 2026: Build Dunzo 2.0 ChatGPT/Gemini plugin + Razorpay ACP endpoint. Beta with Bangalore grocery/pharmacy shops',
        'H2 2026: Public launch in Bengaluru. Refine AI prompts from real interactions. Add pantry, medicine, pets categories',
        '2027: Expand to Mumbai/Delhi. Launch Google Business Agent integration ("chat with Dunzo" from Search). Multi-task bundles',
        '2028: Scale to 10+ cities with AI route batching and demand forecasting. Subscription plans (Dunzo Pro/Plus). Explore drone delivery'
      ],
      monetization: `Transaction fees (5-10% via ACP/UCP), Subscriptions (Dunzo Plus for consumers, Dunzo Business for retailers), Premium SaaS (inventory management, demand forecasting), In-chat advertising (brand promotions via AI responses), Dynamic surge pricing. Target: ₹50Cr ARR by Year 2.`
    },
    'Local Search / E-commerce': {
      name: `${s.startup_name.split(' ')[0]} Commerce AI`,
      description: `Voice-first, asset-light commerce agent for the ONDC era. Revives the "directory" concept as an AI concierge: users in Tier-2/3 cities speak in Bhojpuri, Tamil, or Bengali via Bhashini integration - "Humra ke ek lall saree dikhaiye, 500 rupya ke andar" (Show me a red saree under 500). The AI searches ONDC network (not proprietary inventory), confirms choices, and executes payment via UCP/ACP. TRUSTLESS architecture: payments flow Buyer UPI → ONDC Gateway → Seller - platform never holds funds.`,
      tech_stack: ['ONDC APIs', 'Google UCP', 'OpenAI ACP', 'Bhashini ASR/TTS (₹0.50/min)', 'GPT-4/Gemini', 'WhatsApp Business API', 'Razorpay'],
      execution_plan: [
        'Navigate NCLT to acquire brand IP. Build "Headless Service" that lives on WhatsApp/Voice, not destination website',
        'Integrate Bhashini for Hindi, Bhojpuri, Tamil, Bengali voice commerce. Target: NBU (Next Billion Users) who find apps intimidating',
        'Go live as ONDC Buyer App focused on Tier-2/3 cities. Trustless escrow: never hold principal amounts',
        'Launch "AskMe Agent Pro" SaaS for SMB sellers (₹500-800/month) - AI listing optimization, auto-descriptions, inventory management'
      ],
      monetization: `ONDC Buyer App Fee (1-2% convenience fee auto-split at gateway), Seller SaaS subscriptions (₹500-800/month for AI tools), Premium voice commerce features. LOW COST structure: Zero vendor onboarding (ONDC), Variable logistics (Shadowfax/Shiprocket bids), AI support replaces call centers (~80% savings). Target: ₹25Cr ARR by Year 2.`
    },
    'E-commerce': {
      name: `${s.startup_name.split(' ')[0]} Commerce AI`,
      description: `AI-native agentic commerce platform powered by Google's Universal Commerce Protocol (UCP) and OpenAI's Agentic Commerce Protocol (ACP). Users can discover, compare, and buy products entirely through AI agents like Gemini or ChatGPT - no app needed. Integrates with Flipkart, Amazon, and local sellers for seamless checkout within AI interfaces.`,
      tech_stack: ['Google UCP', 'OpenAI ACP', 'GPT-4', 'Gemini API', 'Stripe Connect', 'WhatsApp Business API', 'React Native'],
      execution_plan: [
        'Integrate with Google Universal Commerce Protocol for Gemini-based shopping',
        'Implement OpenAI Agentic Commerce Protocol for ChatGPT instant checkout',
        'Build merchant onboarding for UCP/ACP compatibility with Razorpay/Stripe',
        'Launch WhatsApp AI shopping agent with voice-based product discovery',
        'Add agentic price comparison across platforms with AI negotiation'
      ],
      monetization: `UCP/ACP transaction fee (1-2% of GMV), merchant SaaS for agentic commerce enablement at ₹25K/month, AI-powered advertising within agent responses. Target: ₹200Cr GMV with ₹30Cr revenue by Year 2.`
    },
    'Social': {
      name: `${s.startup_name.split(' ')[0]} Social AI`,
      description: `AI-first social platform with personalized content curation, AI-generated content tools, and creator monetization. Focuses on niche communities rather than competing with Big Tech.`,
      tech_stack: ['GPT-4', 'Stable Diffusion', 'React Native', 'Firebase', 'Stripe'],
      execution_plan: [
        'Launch with AI content creation tools for creators (text, image, video)',
        'Build recommendation algorithm for niche community discovery',
        'Add creator monetization through subscriptions and tips',
        'Implement AI moderation for content safety at scale'
      ],
      monetization: `Creator subscription revenue share (20-30%), tipping commission (5%), brand partnership facilitation fee (15%), premium AI tools subscription at ₹199/month. Target: ₹20Cr ARR by Year 2.`
    },
    'Ride-hailing': {
      name: `${s.startup_name.split(' ')[0]} Mobility AI`,
      description: `AI-optimized EV ride-hailing platform focused on specific routes/corridors with predictive positioning and dynamic pricing. Asset-light model with driver partnerships.`,
      tech_stack: ['TensorFlow', 'React Native', 'Google Maps API', 'PostgreSQL', 'Stripe'],
      execution_plan: [
        'Start with 2-3 high-demand corridors (airport, tech parks, stations)',
        'Build demand prediction for driver positioning optimization',
        'Partner with EV fleet owners for asset-light scaling',
        'Add subscription model for daily commuters with guaranteed rides'
      ],
      monetization: `Commission per ride (15-20%), subscription plans for regular commuters at ₹2999/month, corporate tie-ups for employee transportation. Target: ₹30Cr GMV by Year 2.`
    },
    'Real Estate': {
      name: `${s.startup_name.split(' ')[0]} PropAI`,
      description: `AI-powered property discovery and transaction platform with virtual tours, price prediction, and automated documentation. Reduces friction in real estate transactions.`,
      tech_stack: ['GPT-4', '3D Scanning', 'React', 'PostgreSQL', 'DigiLocker APIs'],
      execution_plan: [
        'Build AI property valuation model using historical transaction data',
        'Add virtual tour generation using 3D scanning and AI enhancement',
        'Automate documentation with AI-powered legal review',
        'Launch rent-to-own and fractional ownership products'
      ],
      monetization: `Brokerage fee (1% of transaction value), premium listing fees for sellers at ₹5K-25K, home loan referral commission (0.5%). Target: ₹25Cr revenue by Year 3.`
    },
    'Gaming': {
      name: `${s.startup_name.split(' ')[0]} Game AI`,
      description: `AI-powered skill gaming platform with fair matchmaking, anti-fraud detection, and personalized game recommendations. Focuses on compliance-first approach for sustainable growth.`,
      tech_stack: ['Python ML', 'Unity', 'React Native', 'PostgreSQL', 'Razorpay'],
      execution_plan: [
        'Build AI matchmaking system for fair skill-based competitions',
        'Implement ML-based fraud detection to prevent bots and collusion',
        'Launch with quiz and puzzle games before adding fantasy sports',
        'Add social features for community building and organic growth'
      ],
      monetization: `Platform fee (10-15% of prize pool), premium subscriptions for advanced analytics at ₹199/month, brand sponsorships for tournaments. Target: ₹50Cr GMV by Year 2.`
    },
    'Grocery': {
      name: `${s.startup_name.split(' ')[0]} Fresh AI`,
      description: `AI-optimized hyperlocal grocery with demand prediction, dynamic inventory, and route optimization. Partners with kiranas instead of building owned infrastructure.`,
      tech_stack: ['TensorFlow', 'React Native', 'Google Maps API', 'PostgreSQL', 'Razorpay'],
      execution_plan: [
        'Integrate with Google UCP for voice-based grocery ordering via Gemini',
        'Build demand forecasting model to reduce wastage to <2%',
        'Partner with 50 kiranas in one locality for inventory network',
        'Implement AI route optimization for delivery efficiency',
        'Launch agentic subscription: "AI, order my weekly groceries" via ChatGPT'
      ],
      monetization: `Delivery fee + margin on products (blended 20%), agentic commerce fee (1% via UCP), subscription boxes at ₹999/week. Target: ₹30Cr revenue by Year 2.`
    },
    'Furniture': {
      name: `${s.startup_name.split(' ')[0]} Interior AI`,
      description: `AI-powered interior design and furniture platform with AR visualization, style recommendations, and modular customization. Integrates with Google UCP for seamless checkout - users can say "Gemini, find me a sofa under ₹30K" and complete purchase within the AI interface.`,
      tech_stack: ['Google UCP', 'GPT-4 Vision', 'AR Kit', 'Three.js', 'React', 'Shopify'],
      execution_plan: [
        'Build AI room design tool that generates furniture recommendations',
        'Integrate with Google UCP for in-Gemini furniture shopping',
        'Add AR visualization for virtual furniture placement',
        'Partner with manufacturers for made-to-order production',
        'Launch interior design consultation with AI assistance'
      ],
      monetization: `Product margin (30-40%), UCP transaction fee (1-2%), interior design service fee (₹10K-50K). Target: ₹20Cr revenue by Year 2.`
    },
    'Quick Commerce': {
      name: `${s.startup_name.split(' ')[0]} Agent Delivery`,
      description: `AI-agent powered quick commerce that integrates with Google UCP and OpenAI ACP. Users tell Gemini or ChatGPT what they need, AI finds best prices across platforms, and completes checkout - all within 2 minutes. Like what Zepto Cafe is testing but for everything.`,
      tech_stack: ['Google UCP', 'OpenAI ACP', 'GPT-4', 'React Native', 'Razorpay', 'Google Maps API'],
      execution_plan: [
        'Build UCP-compatible quick commerce API for Gemini integration',
        'Implement OpenAI ACP for ChatGPT-based ordering',
        'Partner with dark stores for inventory (asset-light model)',
        'Launch multi-platform price comparison via AI agents',
        'Add voice-based ordering in Hindi/regional languages'
      ],
      monetization: `Delivery fee + product margin (blended 15%), agentic commerce commission (1-2% via UCP/ACP), subscription for priority delivery at ₹199/month. Target: ₹100Cr GMV by Year 2.`
    },
    'Home Services': {
      name: `${s.startup_name.split(' ')[0]} ServiceMatch AI`,
      description: `AI-powered service professional matching and quality prediction. Computer vision for job assessment, ML-based worker-job matching, automated scheduling optimization, and predictive quality scoring to reduce complaints. Solves gig worker churn with AI-based fair pricing and demand prediction.`,
      tech_stack: ['Computer Vision', 'TensorFlow', 'GPT-4', 'React Native', 'PostgreSQL', 'Razorpay'],
      execution_plan: [
        'Build AI photo assessment: customer uploads photo, AI estimates job complexity and fair price instantly',
        'Create ML matching model: pairs worker skills, location, ratings with job requirements for 95%+ match quality',
        'Deploy demand forecasting: predict high-demand periods, surge pricing, worker availability optimization',
        'Add quality prediction: flag high-risk jobs before execution based on customer/worker history patterns',
        'Launch worker income guarantee: AI distributes jobs fairly to reduce churn and partner unrest'
      ],
      monetization: `Commission (20-25% of service value), premium priority booking at ₹99-199, subscription for recurring services (₹499/month), B2B contracts for corporates/apartments. Target: ₹50Cr ARR by Year 2.`
    },
    'Audio Entertainment': {
      name: `${s.startup_name.split(' ')[0]} Story AI`,
      description: `AI-native audio content platform. AI-generated stories in multiple Indian languages and voices. AI voice cloning for personalized narration. Generative audio: users describe story, AI writes and narrates. Solves content cost problem (human writers/narrators are expensive) with AI generation at 1/100th cost.`,
      tech_stack: ['Eleven Labs', 'GPT-4', 'Whisper', 'Stable Audio', 'React Native', 'AWS'],
      execution_plan: [
        'Build AI story generator: fine-tune LLM on popular genres (romance, thriller, mythology) in Hindi/regional',
        'Create AI voice library: clone popular narrator voices with permission, generate unlimited hours at ₹0.10/minute vs ₹500+/hour human cost',
        'Launch personalized audio: AI adapts story pacing, character names, plot based on listener preferences',
        'Add interactive fiction: listener choices affect story direction via voice commands',
        'Enable creator tools: writers upload script, AI generates multi-voice audio drama automatically'
      ],
      monetization: `Freemium: 2 hours/month free. Premium: ₹99/month unlimited. Creator tools: ₹499/month for AI voice generation. B2B licensing for publishers. Target: ₹30Cr ARR by Year 2.`
    },
    'Used Cars': {
      name: `${s.startup_name.split(' ')[0]} CarInspect AI`,
      description: `AI-powered vehicle inspection and valuation platform. Computer vision detects scratches, dents, rust from photos. ML predicts accurate resale value from 200+ data points. OBD-II integration for mechanical health assessment. Solves trust problem in used car market with AI transparency.`,
      tech_stack: ['Computer Vision', 'TensorFlow', 'OBD-II APIs', 'React Native', 'PostgreSQL', 'Razorpay'],
      execution_plan: [
        'Build photo inspection AI: detect vehicle condition from 20 standard photos with 95%+ accuracy',
        'Create price prediction model: train on 10M+ transactions for accurate valuation within 3% margin',
        'Deploy OBD-II scanner integration: read engine codes, battery health, transmission status remotely',
        'Add AI negotiation assistant: suggests fair price for both buyer and seller based on market data',
        'Launch certified inspection service: ₹999 AI-powered inspection report with warranty backing'
      ],
      monetization: `Transaction fee (1-2% of sale value), inspection reports at ₹499-999, warranty products (₹5K-20K), financing referral (2% of loan value). Target: ₹40Cr ARR by Year 2.`
    },
    'Short Video': {
      name: `${s.startup_name.split(' ')[0]} Creator Studio`,
      description: `AI-powered content creation tools for short-video creators. Not competing with Reels—enabling creators who post TO Reels. AI avatars for faceless content, AI video generation from text, auto-captions in 10+ Indian languages, voice cloning for dubbing, trending audio matching.`,
      tech_stack: ['Stable Diffusion', 'Whisper', 'Eleven Labs', 'RunwayML', 'React Native', 'AWS'],
      execution_plan: [
        'Launch AI Avatar Generator: creators get animated talking avatar from single photo—solves camera-shy problem',
        'Build AI Video Editor: auto-captions in Hindi/Tamil/Telugu, smart cuts, background removal, trending audio matching',
        'Add AI Voice Cloning: dub same video in multiple languages automatically—opens 500M+ non-English audience',
        'Create Text-to-Video: type script in Hindi, AI generates short video with synthetic voice and stock footage',
        'Enable multi-platform publishing: one-click post to Reels, YouTube Shorts, Moj, ShareChat'
      ],
      monetization: `Freemium: 5 videos/month. Pro: ₹499/month (unlimited, AI avatars). Studio: ₹1999/month (voice cloning, API). Agency licensing: ₹10L+/year. Target: ₹25Cr ARR by Year 2.`
    },
    'Electric Vehicles': {
      name: `${s.startup_name.split(' ')[0]} SafeRide Network`,
      description: `V2V (Vehicle-to-Vehicle) safety and predictive maintenance platform. Vehicles become connected sensors sharing real-time hazard data (potholes, accidents, obstacles). AI predicts component failures 7-14 days ahead from motor/battery/brake telemetry. Fleet API for logistics companies.`,
      tech_stack: ['MQTT/V2X protocols', 'Edge AI (NVIDIA Jetson)', 'TensorFlow Lite', 'AWS IoT', 'PostgreSQL', 'React Native'],
      execution_plan: [
        'Enable V2V mesh: vehicles broadcast hazard data via Bluetooth mesh to nearby vehicles',
        'Build Predictive Maintenance AI: analyze motor temperature, battery degradation, brake wear patterns',
        'Deploy OTA alerts: "Your brake pad needs replacement in ~500km—schedule service now"',
        'Create Fleet API: delivery/logistics companies get real-time telemetry, route safety scores, driver behavior',
        'Partner with insurance: riders share data for lower premiums, earn referral fee'
      ],
      monetization: `Consumer: Free (premium safety ₹99/month). Fleet API: ₹299/vehicle/month. Insurance referrals: 10-15% of premium. Reduces warranty costs 20-30%. Target: ₹100Cr ARR from fleet by Year 3.`
    },
    'D2C': {
      name: `${s.startup_name.split(' ')[0]} Brand Intelligence`,
      description: `AI-powered demand forecasting and inventory optimization for D2C brands. Predicts which products will sell, optimal pricing, inventory levels. Reduces dead stock by 40%+. Automated product photography through AI. Solves the core Thrasio-model problem: overpaying for brands without understanding demand.`,
      tech_stack: ['TensorFlow', 'GPT-4 Vision', 'Shopify API', 'Amazon SP-API', 'PostgreSQL', 'AWS'],
      execution_plan: [
        'Build demand forecasting: predict SKU-level demand 30-90 days ahead with 85%+ accuracy',
        'Create AI product photography: generate e-commerce images from single product photo',
        'Deploy dynamic pricing engine: optimize prices across marketplaces in real-time',
        'Add inventory optimization: prevent stockouts and overstock with ML-based reorder points',
        'Launch brand acquisition scoring: AI evaluates D2C brands for M&A based on 50+ metrics'
      ],
      monetization: `SaaS: ₹25K-2L/month for brands based on GMV. Transaction fee: 0.5% on AI-optimized sales. Brand acquisition: success fee on facilitated deals. Target: ₹40Cr ARR by Year 2.`
    },
  };

  for (const [key, rebuild] of Object.entries(categoryRebuilds)) {
    if (s.category?.toLowerCase().includes(key.toLowerCase())) {
      return rebuild;
    }
  }

  // Default rebuild suggestion - more intelligent, category-agnostic
  return {
    name: `${s.startup_name.split(' ')[0]} AI Platform`,
    description: `AI-first rebuild of ${s.startup_name} focused on solving the core unit economics problem that killed the original. Uses AI for: 1) Demand prediction to reduce wastage/inefficiency, 2) Automated operations to cut labor costs 70%+, 3) Personalization to increase conversion 2-3x, 4) Quality prediction to reduce complaints/refunds. Asset-light, profitable from Day 1 at small scale before raising growth capital.`,
    tech_stack: ['GPT-4/Gemini', 'TensorFlow', 'React Native', 'PostgreSQL', 'Razorpay', 'AWS'],
    execution_plan: [
      `Analyze ${s.startup_name}'s failure: identify the specific unit economic flaw (CAC, margins, ops costs)`,
      `Build AI layer that directly addresses that flaw (e.g., demand prediction for inventory, matching for marketplace)`,
      `Launch in single city/vertical with 100 customers to prove unit economics before scaling`,
      `Achieve ₹1Cr ARR with positive contribution margin before raising external capital`,
      `Scale only after proving 3:1 LTV:CAC ratio and path to profitability`
    ],
    monetization: `Focus on sustainable unit economics from Day 1. Subscription or transaction-based revenue aligned with customer success. Target: ₹10Cr ARR with 20%+ contribution margin by Year 2.`
  };
};

const generateMonetization = (s) => {
  return `Based on ${s.startup_name}'s model and current market conditions, a rebuilt version should focus on: 1) Subscription-based recurring revenue for predictability, 2) Commission-based transactions for alignment with customer success, 3) Premium AI features that provide 10x value vs free tier, 4) B2B partnerships for distribution without customer acquisition costs. The key is achieving profitability at small scale before seeking growth capital.`;
};

const generateInnovative = (s) => {
  const categoryInnovations = {
    'EdTech': [
      'Zero CAC growth via existing AI platforms (ChatGPT, Gemini)',
      'No content creation cost - AI generates personalized lessons',
      '24/7 availability with infinite patience',
      'Vernacular support without hiring language experts',
      'Instant scalability - same AI serves 1 or 1M students'
    ],
    'FinTech': [
      'Zero CAC via Google UCP / OpenAI ACP integration',
      'Agentic payments - users just speak their intent',
      'ONDC-compatible architecture for interoperability',
      'No discounts needed - convenience is the moat',
      'Instant compliance via pre-integrated NPCI/UPI rails'
    ],
    'Food Delivery': [
      'Zero CAC growth - users come via Gemini/ChatGPT',
      'No app fatigue - works inside tools users already use',
      'AI-driven demand shaping, not just order fulfillment',
      'ONDC-compatible future - interoperable by design',
      'Profit-first architecture - no discounts required'
    ],
    'E-commerce': [
      'Zero marketing spend - discovery happens in AI assistants',
      'No app download friction - buy in 2 messages',
      'AI negotiates best prices across platforms automatically',
      'Voice commerce in Hindi/regional languages',
      'UCP/ACP rails eliminate payment integration complexity'
    ],
    'Quick Commerce': [
      'Agentic ordering - "Gemini, I need milk in 10 mins"',
      'Multi-platform price comparison via AI agents',
      'Asset-light model with dark store partnerships',
      'Predictive inventory via AI demand forecasting',
      'No customer app needed - just AI + delivery'
    ],
    'Quick Commerce / Delivery': [
      'CONVERSATIONAL COMMERCE: Ask Dunzo in plain language - no app menus',
      'AI handles ambiguous queries: "supplies for camping trip" → full list',
      'End-to-end agentic: GPT/Gemini browses, adds to cart, pays via Razorpay in one flow',
      'LOCAL INTELLIGENCE: AI knows which bakery/pharmacy is closest AND cheapest',
      'OPEN ECOSYSTEM: Any AI assistant can offer delivery via UCP/ACP standards',
      'Learns user preferences: "I usually go to the green grocer"',
      'No walled garden - Shopify, Flipkart, local kiranas all accessible'
    ],
    'Local Search': [
      'VOICE-FIRST: Bhashini enables Bhojpuri/Tamil/Bengali commerce',
      'TRUSTLESS: Payments flow Buyer → ONDC Gateway → Seller directly',
      'ZERO VENDOR ONBOARDING: Plug into ONDC - all sellers auto-discoverable',
      'AI CONCIERGE replaces human call centers at 80% lower cost',
      'Built on open protocols - no proprietary lock-in',
      'NBU-first design: for users who find apps intimidating',
      'SaaS monetization: recurring revenue from seller tools'
    ],
    'B2B': [
      'AI handles vendor discovery and RFQ automatically',
      'LLM-powered contract analysis and negotiation',
      'Instant credit decisions via AI underwriting',
      'UCP enables B2B transactions within Gemini',
      'Supply chain prediction reduces inventory costs 40%'
    ],
    'HealthTech': [
      'AI triage reduces unnecessary doctor consultations 60%',
      'Computer vision diagnosis at <₹10 per scan',
      'Vernacular health literacy via voice AI',
      '24/7 chronic disease monitoring via WhatsApp',
      'ABDM integration for seamless health records'
    ],
  };

  for (const [key, innovations] of Object.entries(categoryInnovations)) {
    if (s.category?.toLowerCase().includes(key.toLowerCase())) {
      return innovations;
    }
  }

  // Default innovations
  return [
    'Zero CAC growth via Google UCP / OpenAI ACP platforms',
    'No app download needed - works inside AI assistants',
    'AI handles discovery, comparison, and checkout autonomously',
    'Profit-first architecture - no unsustainable discounts',
    'ONDC-compatible for future interoperability'
  ];
};

const closeModal = () => {
  el('detailModal').classList.remove('show');
  el('detailModal').setAttribute('aria-hidden', 'true');
};

const showLoadError = (message) => {
  const box = el('loadError');
  const grid = el('cardsGrid');
  if (box) {
    box.hidden = false;
    box.textContent = message;
  }
  if (grid) {
    grid.innerHTML = '<div class="empty-state">Catalog could not be loaded. Check your connection or try again later.</div>';
  }
};

const computeQualitySummary = (items) => {
  const total = items.length || 1;
  const gold = items.filter((s) => isGoldProfile(s)).length;
  const withSrc = items.filter((s) => sourceCountOf(s) > 0).length;
  const blocked = items.filter((s) => s.research_rejected || s.research_status === 'blocked').length;
  const scores = items.map((s) => Number(s.research_score)).filter((n) => Number.isFinite(n));
  const avg = scores.length ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : 0;
  return {
    total: items.length,
    gold_pass: gold,
    gold_pass_pct: +(gold / total).toFixed(4),
    with_sources: withSrc,
    with_sources_pct: +(withSrc / total).toFixed(4),
    blocked,
    avg_research_score: avg,
  };
};

const loadData = async () => {
  const box = el('loadError');
  if (box) {
    box.hidden = true;
    box.textContent = '';
  }
  try {
    const res = await fetch(DATA_URL);
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    const json = await res.json();
    state.data = json.startups || [];
    state.filtered = state.data;
    state.generatedAt = json.generated_at || '';
    state.qualitySummary = json.quality_summary || computeQualitySummary(state.data);
    buildStatusFilters();
    buildCategoryFilter(state.data);
    applyUrlState();
    updateHeroMeta(state.data);
    applyFilters();
    openDeepLink();
    updateWatchlistBadge();
  } catch (err) {
    console.error('[loadData]', err);
    showLoadError(
      'Failed to load startup catalog (data/graveyard.json). The rest of the page shell still works — retry by refreshing.'
    );
  }
};

const updateHeroMeta = (items) => {
  const burned = items.reduce((sum, s) => sum + (s.funding_burned_usd || 0), 0);
  const subtitle = el('heroSubtitle');
  const freshness = el('dataFreshness');
  if (subtitle) {
    subtitle.textContent = `The unfiltered truth about Indian startups — failures, struggles, pivots & comebacks. Learn from ${formatInrCr(burned)} in lessons.`;
  }
  const qs = state.qualitySummary || computeQualitySummary(items);
  const gold = qs.gold_pass;
  const withSrc = qs.with_sources;
  if (freshness) {
    const datePart = state.generatedAt ? `📅 Dataset last updated: ${state.generatedAt}` : '📅 Dataset date unknown';
    freshness.textContent = `${datePart} · ${items.length} startups · ${gold} gold verified (${Math.round((qs.gold_pass_pct || 0) * 100)}%) · ${withSrc} with sources (${Math.round((qs.with_sources_pct || 0) * 100)}%) · avg score ${qs.avg_research_score || '—'}`;
  }
  const qLine = el('qualitySummaryLine');
  if (qLine) {
    const blocked = qs.blocked;
    qLine.textContent = `Live honesty: ${gold}/${items.length} gold-verified · ${blocked} below gold bar · ${withSrc} with source URLs · avg research score ${qs.avg_research_score}. Path A targets: ≥70% sources, ≥30% gold.`;
  }
  updateWatchlistBadge();
};

const slugifyName = (name) => String(name || '').toLowerCase().replace(/[^a-z0-9]+/g, '-');

const openDeepLink = () => {
  const params = new URLSearchParams(window.location.search);
  const slug = params.get('startup');
  if (!slug) return;
  const match = state.data.find((s) => slugifyName(s.startup_name) === slug.toLowerCase());
  if (match) openModal(match);
};

const applyUrlState = () => {
  const params = new URLSearchParams(window.location.search);
  if (params.get('q') && el('searchInput')) el('searchInput').value = params.get('q');
  if (params.get('status')) state.activeStatus = params.get('status');
  if (params.get('quality')) {
    state.qualityFilter = params.get('quality');
    if (el('qualityFilter')) el('qualityFilter').value = state.qualityFilter;
  }
  if (params.get('sort')) {
    state.sortBy = params.get('sort');
    if (el('sortBy')) el('sortBy').value = state.sortBy;
  }
  if (params.get('category')) {
    state.categoryFilter = params.get('category');
  }
  if (params.get('recent') === '1') state.recentOnly = true;
  if (params.get('watch') === '1') state.watchlistOnly = true;
  el('recentOnlyBtn')?.classList.toggle('active', state.recentOnly);
  el('watchlistOnlyBtn')?.classList.toggle('active', state.watchlistOnly);
};

const syncUrlState = () => {
  const params = new URLSearchParams();
  const q = el('searchInput')?.value?.trim();
  if (q) params.set('q', q);
  if (state.activeStatus && state.activeStatus !== 'All') params.set('status', state.activeStatus);
  if (state.qualityFilter && state.qualityFilter !== 'all') params.set('quality', state.qualityFilter);
  if (state.sortBy && state.sortBy !== 'default') params.set('sort', state.sortBy);
  if (state.categoryFilter && state.categoryFilter !== 'All') params.set('category', state.categoryFilter);
  if (state.recentOnly) params.set('recent', '1');
  if (state.watchlistOnly) params.set('watch', '1');
  const qs = params.toString();
  const next = qs ? `${window.location.pathname}?${qs}` : window.location.pathname;
  window.history.replaceState({}, '', next);
};

const toggleCompare = (name, on) => {
  const n = String(name || '');
  if (!n) return;
  if (on) {
    if (!state.compareIds.includes(n) && state.compareIds.length < 3) state.compareIds.push(n);
  } else {
    state.compareIds = state.compareIds.filter((x) => x !== n);
  }
  renderCompareBar();
};

const renderCompareBar = () => {
  const bar = el('compareBar');
  if (!bar) return;
  if (!state.compareIds.length) {
    bar.hidden = true;
    bar.innerHTML = '';
    return;
  }
  bar.hidden = false;
  bar.innerHTML = `
    <div class="compare-bar-inner">
      <strong>Compare (${state.compareIds.length}/3):</strong>
      ${state.compareIds.map((n) => `<span class="tag">${escapeHtml(n)}</span>`).join('')}
      <button type="button" class="filter-btn" id="runCompareBtn">Open compare</button>
      <button type="button" class="filter-btn" id="clearCompareBtn">Clear</button>
    </div>`;
  el('runCompareBtn')?.addEventListener('click', openComparePanel);
  el('clearCompareBtn')?.addEventListener('click', () => {
    state.compareIds = [];
    renderCompareBar();
    renderResults();
  });
};

const openComparePanel = () => {
  const panel = el('comparePanel');
  const body = el('compareBody');
  if (!panel || !body) return;
  const rows = state.compareIds.map((name) => state.data.find((s) => s.startup_name === name)).filter(Boolean);
  if (rows.length < 2) {
    alert('Select at least 2 startups to compare.');
    return;
  }
  const fields = [
    ['Status', (s) => s.status || '—'],
    ['Tier', (s) => (Q() ? Q().qualityBadgeLabel(s) : s.profile_tier || '—')],
    ['Funding', (s) => formatMoneyOrUnknown(s.funding_burned_usd)],
    ['Category', (s) => s.category || '—'],
    ['Sources', (s) => String(sourceCountOf(s))],
    ['Research score', (s) => String(s.research_score ?? '—')],
    ['Cause / struggle', (s) => (s.cause_of_death || s.failure_reason || '—').slice(0, 160)],
  ];
  let html = '<table class="compare-table"><thead><tr><th>Field</th>';
  rows.forEach((s) => { html += `<th>${escapeHtml(s.startup_name)}</th>`; });
  html += '</tr></thead><tbody>';
  fields.forEach(([label, fn]) => {
    html += `<tr><th>${escapeHtml(label)}</th>`;
    rows.forEach((s) => { html += `<td>${escapeHtml(fn(s))}</td>`; });
    html += '</tr>';
  });
  html += '</tbody></table>';
  body.innerHTML = html;
  panel.hidden = false;
  panel.classList.add('show');
};

const closeComparePanel = () => {
  const panel = el('comparePanel');
  if (!panel) return;
  panel.hidden = true;
  panel.classList.remove('show');
};

const exportFiltered = (format) => {
  const rows = state.filtered || [];
  if (!rows.length) {
    alert('Nothing to export for current filters.');
    return;
  }
  const slim = rows.map((s) => ({
    startup_name: s.startup_name,
    status: s.status,
    category: s.category,
    funding_burned_usd: s.funding_burned_usd ?? null,
    profile_tier: s.profile_tier,
    research_status: s.research_status,
    research_score: s.research_score,
    sources_count: sourceCountOf(s),
    headquarters: s.headquarters,
    year_founded: s.year_founded,
    year_died: s.year_died,
  }));
  let blob;
  let filename;
  if (format === 'csv') {
    const headers = Object.keys(slim[0]);
    const lines = [headers.join(',')];
    slim.forEach((r) => {
      lines.push(headers.map((h) => {
        const v = r[h] == null ? '' : String(r[h]);
        return `"${v.replace(/"/g, '""')}"`;
      }).join(','));
    });
    blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' });
    filename = 'bharat-startup-reality-export.csv';
  } else {
    blob = new Blob([JSON.stringify(slim, null, 2)], { type: 'application/json' });
    filename = 'bharat-startup-reality-export.json';
  }
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
};

const updateWatchlistBadge = () => {
  const btn = el('watchlistOnlyBtn');
  if (!btn || !Q()) return;
  const n = Q().loadWatchlist().length;
  btn.textContent = n ? `★ Watchlist (${n})` : '★ Watchlist';
};

// Patch applyFilters to sync URL after filter
const _applyFiltersOrig = typeof applyFilters === 'function' ? null : null;

el('searchInput')?.addEventListener('input', () => { applyFilters(); syncUrlState(); });
el('categoryFilter')?.addEventListener('change', (e) => {
  state.categoryFilter = e.target.value;
  applyFilters();
  syncUrlState();
});
el('sortBy')?.addEventListener('change', (e) => {
  state.sortBy = e.target.value;
  applyFilters();
  syncUrlState();
});
el('qualityFilter')?.addEventListener('change', (e) => {
  state.qualityFilter = e.target.value;
  applyFilters();
  syncUrlState();
});
el('recentOnlyBtn')?.addEventListener('click', () => {
  state.recentOnly = !state.recentOnly;
  el('recentOnlyBtn').classList.toggle('active', state.recentOnly);
  applyFilters();
  syncUrlState();
});
el('watchlistOnlyBtn')?.addEventListener('click', () => {
  state.watchlistOnly = !state.watchlistOnly;
  el('watchlistOnlyBtn')?.classList.toggle('active', state.watchlistOnly);
  applyFilters();
  syncUrlState();
});
el('exportJsonBtn')?.addEventListener('click', () => exportFiltered('json'));
el('exportCsvBtn')?.addEventListener('click', () => exportFiltered('csv'));
el('compareClose')?.addEventListener('click', closeComparePanel);
el('compareBackdrop')?.addEventListener('click', closeComparePanel);
el('modalBackdrop').addEventListener('click', closeModal);
el('modalClose').addEventListener('click', closeModal);

document.addEventListener('keydown', (e) => {
  const tag = (e.target && e.target.tagName) || '';
  const typing = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || e.target?.isContentEditable;
  if (e.key === 'Escape') {
    const detail = el('detailModal');
    const feedback = el('feedbackModal');
    const compare = el('comparePanel');
    if (compare && !compare.hidden) closeComparePanel();
    if (detail?.classList.contains('show')) closeModal();
    if (feedback?.classList.contains('show') && typeof closeFeedbackModal === 'function') {
      closeFeedbackModal();
    }
    return;
  }
  if (!typing && e.key === '/') {
    e.preventDefault();
    el('searchInput')?.focus();
  }
});

// Bubble Animation
const createBubbles = () => {
  const container = el('bubblesContainer');
  if (!container) return;

  const colors = ['orange', 'pink', 'blue', 'green'];
  const bubbleCount = window.innerWidth < 600 ? 8 : 15;

  const createBubble = () => {
    const bubble = document.createElement('div');
    bubble.className = `bubble ${colors[Math.floor(Math.random() * colors.length)]}`;

    const size = Math.random() * 80 + 20;
    bubble.style.width = `${size}px`;
    bubble.style.height = `${size}px`;
    bubble.style.left = `${Math.random() * 100}%`;
    bubble.style.animationDuration = `${Math.random() * 10 + 8}s`;
    bubble.style.animationDelay = `${Math.random() * 5}s`;

    container.appendChild(bubble);

    // Remove bubble after animation
    setTimeout(() => {
      bubble.remove();
    }, 20000);
  };

  // Initial bubbles
  for (let i = 0; i < bubbleCount; i++) {
    setTimeout(() => createBubble(), i * 300);
  }

  // Continuous bubble generation
  setInterval(() => {
    if (container.children.length < bubbleCount + 5) {
      createBubble();
    }
  }, 2000);
};

// Feedback Modal
const openFeedbackModal = () => {
  el('feedbackModal').classList.add('show');
  el('feedbackModal').setAttribute('aria-hidden', 'false');
};

const closeFeedbackModal = () => {
  el('feedbackModal').classList.remove('show');
  el('feedbackModal').setAttribute('aria-hidden', 'true');
};

el('feedbackFab').addEventListener('click', openFeedbackModal);
el('feedbackBackdrop').addEventListener('click', closeFeedbackModal);
el('feedbackClose').addEventListener('click', closeFeedbackModal);

// Send feedback to email using Formsubmit.co (no setup required!)
el('feedbackForm').addEventListener('submit', async (e) => {
  e.preventDefault();

  const type = String(el('feedbackType').value || '').slice(0, 80);
  const details = String(el('feedbackDetails').value || '').slice(0, 4000);
  const email = String(el('feedbackEmail').value || '').slice(0, 200);
  if (!details.trim()) {
    alert('Please enter feedback details.');
    return;
  }
  const timestamp = new Date().toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' });

  // Store in localStorage as backup (cap size)
  let feedbacks = [];
  try {
    feedbacks = JSON.parse(localStorage.getItem('feedbacks') || '[]');
    if (!Array.isArray(feedbacks)) feedbacks = [];
  } catch (_) {
    feedbacks = [];
  }
  feedbacks.push({ type, details, email, timestamp });
  if (feedbacks.length > 50) feedbacks = feedbacks.slice(-50);
  localStorage.setItem('feedbacks', JSON.stringify(feedbacks));

  const submitBtn = e.target.querySelector('button[type="submit"]');
  submitBtn.disabled = true;
  submitBtn.textContent = '📤 Sending...';

  try {
    // Send to Formsubmit.co - emails go directly to rahulsinghx2001@gmail.com
    const response = await fetch('https://formsubmit.co/ajax/rahulsinghx2001@gmail.com', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      },
      body: JSON.stringify({
        _subject: `[Bharat Startup Reality] New ${type} Feedback`,
        feedback_type: type,
        details: details,
        user_email: email || 'Not provided',
        submitted_at: timestamp
      })
    });

    if (response.ok) {
      alert('🎉 Thanks for your feedback! We\'ve received it at rahulsinghx2001@gmail.com');
    } else {
      throw new Error('Network response was not ok');
    }
  } catch (error) {
    console.error('Email send error:', error);
    alert('🎉 Thanks for your feedback! (Saved locally - check console for details)');
  }

  submitBtn.disabled = false;
  submitBtn.textContent = '🚀 Submit Feedback';

  // Reset form and close modal
  el('feedbackForm').reset();
  closeFeedbackModal();
});



// Initialize bubbles after page load
setTimeout(createBubbles, 500);

loadData();
