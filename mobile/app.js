(function () {
  const payload = window.IPO_DASHBOARD_DATA || { items: [] };
  const companies = payload.items || [];
  const reports = window.IPO_COMPANY_REPORTS || {};
  const boardOrder = ["科创板", "上交所主板", "深交所主板", "创业板", "北交所"];

  const els = {
    totalCount: document.getElementById("totalCount"),
    boardCount: document.getElementById("boardCount"),
    sourceDate: document.getElementById("sourceDate"),
    boardNav: document.getElementById("boardNav"),
    companyList: document.getElementById("companyList"),
  };

  function initials(name) {
    return (name || "待").replace(/[（）()股份有限公司集团科技]/g, "").slice(0, 2) || "待补";
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

  function splitExpected(value) {
    const text = value || "待补充";
    const match = text.match(/^(.+?)（(.+)）$/);
    if (!match) return { main: text, note: "" };
    return { main: match[1], note: match[2] };
  }

  function setMeta(groups) {
    els.totalCount.textContent = companies.length;
    els.boardCount.textContent = groups.length;
    els.sourceDate.textContent = payload.generatedAt || "待补充";
  }

  function renderBoardNav(groups) {
    const fragment = document.createDocumentFragment();
    groups.forEach(([board, items], index) => {
      const link = document.createElement("a");
      link.href = `#board-${index}`;
      link.textContent = `${board} ${items.length}`;
      fragment.appendChild(link);
    });
    els.boardNav.replaceChildren(fragment);
  }

  function renderCompanies(groups) {
    const fragment = document.createDocumentFragment();
    groups.forEach(([board, items], index) => {
      const section = document.createElement("section");
      section.className = "board-section";
      section.id = `board-${index}`;

      const head = document.createElement("div");
      head.className = "board-head";
      const title = document.createElement("h2");
      title.textContent = board;
      const count = document.createElement("span");
      count.textContent = `${items.length} 家`;
      head.append(title, count);
      section.appendChild(head);

      items.forEach((item) => section.appendChild(createCompanyCard(item)));
      fragment.appendChild(section);
    });
    els.companyList.replaceChildren(fragment);
  }

  function createCompanyCard(item) {
    const report = reports[item.id] || reports[item.name] || {};
    const expected = splitExpected(item.expectedListingTime);

    const card = document.createElement("article");
    card.className = "company-card";

    const top = document.createElement("div");
    top.className = "company-top";
    const orb = document.createElement("span");
    orb.className = "company-orb";
    orb.textContent = initials(item.name);
    const state = document.createElement("span");
    state.className = "state";
    state.textContent = item.status || "待补充";
    top.append(orb, state);

    const title = document.createElement("h3");
    title.textContent = item.name;

    const industry = document.createElement("p");
    industry.className = "industry";
    industry.textContent = item.industry || "行业待补充";

    const facts = document.createElement("div");
    facts.className = "facts";
    facts.appendChild(createFact("预计上市", expected.main, expected.note));
    facts.appendChild(createFact("保荐机构", item.sponsor || "待补充", ""));

    const actions = document.createElement("div");
    actions.className = "actions";
    actions.appendChild(createReportLink("快速看懂", report.overviewUrl, true));
    actions.appendChild(createReportLink("完整调研", report.researchUrl, false));

    card.append(top, title, industry, facts, actions);
    return card;
  }

  function createFact(label, value, note) {
    const item = document.createElement("div");
    const labelEl = document.createElement("span");
    labelEl.textContent = label;
    const valueEl = document.createElement("strong");
    valueEl.textContent = value;
    item.append(labelEl, valueEl);
    if (note) {
      const noteEl = document.createElement("small");
      noteEl.textContent = note;
      item.appendChild(noteEl);
    }
    return item;
  }

  function createReportLink(label, href, isPrimary) {
    const link = document.createElement(href ? "a" : "span");
    link.className = isPrimary ? "button button--primary" : "button";
    link.textContent = label;
    if (!href) {
      link.setAttribute("aria-disabled", "true");
      return link;
    }
    link.href = href;
    link.target = "_blank";
    link.rel = "noreferrer";
    return link;
  }

  function init() {
    const groups = groupedByBoard();
    setMeta(groups);
    renderBoardNav(groups);
    renderCompanies(groups);
  }

  init();
})();
