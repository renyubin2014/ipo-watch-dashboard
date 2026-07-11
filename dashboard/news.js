(function () {
  const READ_IDS_KEY = "IPO_NEWS_READ_IDS_V1";
  const params = new URLSearchParams(window.location.search);
  const slug = params.get("company") || "";
  let payload = null;
  let historyMode = false;

  const els = {
    companyName: document.getElementById("companyName"),
    companyIndustry: document.getElementById("companyIndustry"),
    updatedAt: document.getElementById("updatedAt"),
    explainer: document.getElementById("explainer"),
    newsHeading: document.getElementById("newsHeading"),
    historyToggle: document.getElementById("historyToggle"),
    queueNote: document.getElementById("queueNote"),
    newsList: document.getElementById("newsList"),
  };

  const explainerSections = [
    ["basics", "基础解释"],
    ["profitMechanism", "行业如何赚钱"],
    ["industryNow", "当前行业发生了什么"],
    ["companyImpact", "为什么影响这家公司"],
    ["watchMetrics", "后续只看哪些指标"],
    ["misconceptions", "常见误区"],
    ["sourcesAndCutoff", "来源和截止日期"],
  ];

  function readSet(key) {
    try {
      const parsed = JSON.parse(localStorage.getItem(key) || "[]");
      return new Set(Array.isArray(parsed) ? parsed : []);
    } catch (_error) {
      return new Set();
    }
  }

  function writeSet(key, values) {
    localStorage.setItem(key, JSON.stringify(Array.from(values)));
  }

  function markItemRead(id) {
    const values = readSet(READ_IDS_KEY);
    values.add(id);
    writeSet(READ_IDS_KEY, values);
  }

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function appendTextBlock(parent, title, value) {
    const block = element("section", "explainer-block");
    block.appendChild(element("h3", "", title));
    if (Array.isArray(value)) {
      const list = document.createElement("ul");
      value.forEach((item) => list.appendChild(element("li", "", item)));
      block.appendChild(list);
    } else {
      block.appendChild(element("p", "", value || "暂无内容"));
    }
    parent.appendChild(block);
  }

  function renderExplainer() {
    const explainer = payload.explainer;
    els.explainer.replaceChildren();
    if (!explainer) {
      els.explainer.hidden = true;
      return;
    }
    els.explainer.hidden = false;
    els.explainer.appendChild(element("div", "explainer-label", "科普"));
    const details = document.createElement("details");
    details.appendChild(element("summary", "", explainer.title));
    explainerSections.forEach(([key, title]) => appendTextBlock(details, title, explainer.sections[key]));
    els.explainer.appendChild(details);
  }

  function openItem(item) {
    markItemRead(item.id);
    renderNews();
    window.open(item.sourceUrl, "_blank", "noopener,noreferrer");
  }

  function renderCard(item) {
    const card = element("article", "news-card");
    card.tabIndex = 0;
    card.setAttribute("role", "link");
    const meta = element("div", "news-meta");
    meta.appendChild(element("span", `news-type ${item.type}`, item.type === "company" ? "公司动态" : "行业动态"));
    meta.appendChild(element("span", "", `${item.sourceName} · ${item.publishedAt.slice(0, 10)}`));
    card.appendChild(meta);
    card.appendChild(element("h3", "", item.title));
    card.appendChild(element("p", "", item.summary));
    const important = element("p");
    important.appendChild(element("strong", "", "为什么值得关注："));
    important.append(item.whyImportant);
    card.appendChild(important);
    const relevance = element("p");
    relevance.appendChild(element("strong", "", "与公司的关系："));
    relevance.append(item.companyRelevance);
    card.appendChild(relevance);
    const watch = element("p");
    watch.appendChild(element("strong", "", "下一步观察："));
    watch.append(item.watchNext);
    card.appendChild(watch);
    const link = element("a", "source-link", "查看原文 ↗");
    link.href = item.sourceUrl;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      openItem(item);
    });
    card.appendChild(link);
    card.addEventListener("click", () => openItem(item));
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openItem(item);
      }
    });
    return card;
  }

  function latestPerType(items) {
    const selected = [];
    ["company", "industry"].forEach((type) => {
      const match = items.find((item) => item.type === type);
      if (match) selected.push(match);
    });
    return selected;
  }

  function renderNews() {
    const readIds = readSet(READ_IDS_KEY);
    const allItems = payload.items || [];
    const source = historyMode
      ? allItems.filter((item) => readIds.has(item.id))
      : allItems.filter((item) => !readIds.has(item.id));
    const visible = historyMode ? source : latestPerType(source);
    els.newsList.replaceChildren();
    els.newsHeading.textContent = historyMode ? "历史新闻" : "最新精选";
    els.historyToggle.textContent = historyMode ? "返回最新" : "历史新闻";
    if (!historyMode && source.length > visible.length) {
      els.queueNote.hidden = false;
      els.queueNote.textContent = `还有 ${source.length - visible.length} 条未读，读完当前内容后依次显示。`;
    } else {
      els.queueNote.hidden = true;
    }
    if (!visible.length) {
      els.newsList.appendChild(element("p", "empty-state", historyMode ? "还没有读过的历史新闻。" : "暂无新的精选资讯，可进入历史新闻查看此前内容。"));
      return;
    }
    visible.forEach((item) => els.newsList.appendChild(renderCard(item)));
  }

  function render() {
    document.title = `${payload.company} · 相关热点新闻`;
    els.companyName.textContent = payload.company;
    els.companyIndustry.textContent = payload.industry;
    els.updatedAt.textContent = `更新于 ${payload.updatedAt.replace("T", " ").slice(0, 16)}（北京时间）`;
    renderExplainer();
    renderNews();
  }

  els.historyToggle.addEventListener("click", () => {
    historyMode = !historyMode;
    renderNews();
  });

  if (!/^[a-z0-9-]+$/.test(slug)) {
    els.newsList.appendChild(element("p", "empty-state", "公司参数无效，请返回企业池重新进入。"));
    return;
  }

  fetch(`news-data/${slug}.json`, { cache: "no-store" })
    .then((response) => {
      if (!response.ok) throw new Error("news payload unavailable");
      return response.json();
    })
    .then((data) => {
      payload = data;
      render();
    })
    .catch(() => {
      els.newsList.appendChild(element("p", "empty-state", "暂时无法加载该公司的精选资讯，请稍后再试。"));
    });
})();
