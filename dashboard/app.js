(function () {
  const payload = window.IPO_DASHBOARD_DATA || { items: [] };
  const companies = payload.items || [];
  const reports = window.IPO_COMPANY_REPORTS || {};
  const newsIndex = window.IPO_NEWS_INDEX || {};
  const READ_IDS_KEY = "IPO_NEWS_READ_IDS_V1";
  const NEWS_ASSET_VERSION = "20260711-5";
  const els = {
    sourceDate: document.getElementById("sourceDate"),
    companyList: document.getElementById("companyList"),
  };

  const boardOrder = ["科创板", "上交所主板", "深交所主板", "创业板", "北交所"];

  function initials(name) {
    return (name || "待").replace(/[（）()股份有限公司集团科技]/g, "").slice(0, 2) || "待补";
  }

  function stateClass(item) {
    if (item.classification === "重点跟踪") return "state state--hot";
    if (item.classification === "一般观察") return "state";
    return "state state--watch";
  }

  function groupedByBoard() {
    const groups = new Map();
    companies.forEach((item) => {
      const board = item.board || "待补充板块";
      if (!groups.has(board)) groups.set(board, []);
      groups.get(board).push(item);
    });
    return Array.from(groups.entries()).sort((a, b) => {
      const ai = boardOrder.includes(a[0]) ? boardOrder.indexOf(a[0]) : 99;
      const bi = boardOrder.includes(b[0]) ? boardOrder.indexOf(b[0]) : 99;
      if (ai !== bi) return ai - bi;
      return a[0].localeCompare(b[0], "zh-Hans-CN");
    });
  }

  function renderPool() {
    els.companyList.innerHTML = "";
    if (!companies.length) {
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent = "暂无企业";
      els.companyList.appendChild(empty);
      return;
    }

    const fragment = document.createDocumentFragment();
    groupedByBoard().forEach(([board, items]) => {
      const section = document.createElement("section");
      section.className = "board-section";
      section.setAttribute("aria-labelledby", `board-${board}`);

      const head = document.createElement("div");
      head.className = "board-head";
      const title = document.createElement("h2");
      title.id = `board-${board}`;
      title.textContent = board;
      const count = document.createElement("span");
      count.textContent = `${items.length} 家`;
      head.append(title, count);

      const grid = document.createElement("div");
      grid.className = "company-grid";
      items.forEach((item) => grid.appendChild(createCompanyCard(item)));
      section.append(head, grid);
      fragment.appendChild(section);
    });
    els.companyList.appendChild(fragment);
  }

  function createCompanyCard(item) {
    const card = document.createElement("article");
    card.className = "company-card";
    card.setAttribute("aria-label", item.name);

    const top = document.createElement("div");
    top.className = "company-card__top";
    const orb = document.createElement("span");
    orb.className = "company-orb";
    orb.textContent = initials(item.name);
    const status = document.createElement("span");
    status.className = stateClass(item);
    status.textContent = item.status;
    top.append(orb, status);

    const title = document.createElement("h3");
    title.textContent = item.name;

    const industry = document.createElement("p");
    industry.className = "company-industry";
    industry.textContent = item.industry || "行业待补充";

    const facts = document.createElement("dl");
    facts.className = "company-facts";
    appendFact(facts, "预计上市", item.expectedListingTime || "待补充");
    appendFact(facts, "保荐机构", item.sponsor || "待补充");

    const actions = document.createElement("div");
    actions.className = "report-actions";
    const report = reports[item.id] || reports[item.name] || {};
    actions.append(createReportLink("快速看懂", report.overviewUrl, `${item.name} 概览报告`));
    actions.append(createReportLink("完整调研", report.researchUrl, `${item.name} 详细调研报告`));
    actions.append(createNewsLink(item));

    card.append(top, title, industry, facts, actions);
    return card;
  }

  function appendFact(list, label, value) {
    const item = document.createElement("div");
    const term = document.createElement("dt");
    const desc = document.createElement("dd");
    term.textContent = label;
    desc.textContent = value;
    item.append(term, desc);
    list.appendChild(item);
  }

  function createReportLink(label, href, title) {
    if (!href) {
      const disabled = document.createElement("span");
      disabled.className = "report-link is-disabled";
      disabled.textContent = label;
      disabled.setAttribute("aria-disabled", "true");
      disabled.title = "报告待补充";
      return disabled;
    }
    const link = document.createElement("a");
    link.className = "report-link";
    link.href = href;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = label;
    link.title = title;
    return link;
  }

  function readLocalSet(key) {
    try {
      const value = JSON.parse(localStorage.getItem(key) || "[]");
      return new Set(Array.isArray(value) ? value : []);
    } catch (_error) {
      return new Set();
    }
  }

  function hasUnreadNews(entry) {
    if (!entry) return false;
    const readIds = readLocalSet(READ_IDS_KEY);
    return (entry.activeItemIds || []).some((id) => !readIds.has(id));
  }

  function createNewsLink(item) {
    const entry = newsIndex[item.name];
    const link = document.createElement("a");
    link.className = "report-link news-link";
    link.href = `news.html?company=${encodeURIComponent(entry ? entry.slug : item.name)}&v=${NEWS_ASSET_VERSION}`;
    link.textContent = "相关热点新闻";
    link.title = `${item.name} 相关热点新闻`;
    if (hasUnreadNews(entry)) {
      const badge = document.createElement("span");
      badge.className = "news-unread";
      badge.textContent = "有新资讯";
      link.appendChild(badge);
    }
    return link;
  }

  function setMeta() {
    els.sourceDate.textContent = payload.generatedAt || "待补充";
  }

  function init() {
    setMeta();
    renderPool();
  }

  init();
  window.addEventListener("pageshow", renderPool);
})();
