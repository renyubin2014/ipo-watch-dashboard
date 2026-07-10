export const readItems = (payload) => Array.isArray(payload) ? payload : payload.items || [];

export function joinCompaniesAndAnalysis(companiesPayload, analysisPayload) {
  const analysisById = new Map(readItems(analysisPayload).map((item) => [item.companyId, item]));
  return readItems(companiesPayload).map((company) => ({
    ...company,
    analysis: analysisById.get(company.id),
  }));
}

export function filterCompanies(companies, {
  query = "",
  status = "",
  board = "",
  completeness = "",
  freshness = "",
} = {}) {
  const normalizedQuery = query.trim().toLowerCase();
  return companies.filter((company) => {
    const searchable = [
      company.name,
      company.industry,
      company.board,
      company.status,
      company.analysis?.oneLineThesis,
    ].filter(Boolean).join(" ").toLowerCase();
    return (!normalizedQuery || searchable.includes(normalizedQuery))
      && (!status || company.status === status)
      && (!board || company.board === board)
      && (!completeness || company.scoreCompleteness === completeness)
      && (!freshness || company.sourceDate === freshness);
  });
}

export function reportHref(companyId, reportName) {
  return `./reports-v2/${encodeURIComponent(companyId)}/${reportName}.html`;
}

const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
}[character]));

function addOptions(select, values) {
  [...new Set(values.filter(Boolean))].sort().forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.append(option);
  });
}

function renderCard(company) {
  const advantage = company.analysis?.maximumAdvantage?.summary || "待补充";
  const risk = company.analysis?.maximumRisk?.summary || "待补充";
  const thesis = company.analysis?.oneLineThesis || company.latestProgress || "待补充";
  return `
    <article class="company-card">
      <div class="card-top">
        <span class="tag">${escapeHtml(company.status)}</span>
        <span class="date">资料日期：${escapeHtml(company.sourceDate || "待验证")}</span>
      </div>
      <h3>${escapeHtml(company.name)}</h3>
      <p class="industry">${escapeHtml(company.board)} · ${escapeHtml(company.industry)}</p>
      <p class="thesis">${escapeHtml(thesis)}</p>
      <div class="verdicts">
        <p class="verdict"><strong>最大优势：</strong>${escapeHtml(advantage)}</p>
        <p class="verdict risk"><strong>最大风险：</strong>${escapeHtml(risk)}</p>
      </div>
      <div class="card-meta"><span class="tag">完整度：${escapeHtml(company.scoreCompleteness || "待验证")}</span></div>
      <div class="card-actions">
        <a href="${reportHref(company.id, "overview")}">概览报告</a>
        <a href="${reportHref(company.id, "research")}">详尽调研</a>
      </div>
    </article>`;
}

function initializeDashboard() {
  const controls = {
    search: document.querySelector("#search"),
    status: document.querySelector("#status-filter"),
    board: document.querySelector("#board-filter"),
    completeness: document.querySelector("#completeness-filter"),
    freshness: document.querySelector("#freshness-filter"),
  };
  const cards = document.querySelector("#company-cards");
  const count = document.querySelector("#result-count");
  const snapshot = document.querySelector("#snapshot");

  Promise.all([
    fetch("./data/companies.json").then((response) => response.json()),
    fetch("./data/analysis.json").then((response) => response.json()),
  ]).then(([companiesPayload, analysisPayload]) => {
    const companies = joinCompaniesAndAnalysis(companiesPayload, analysisPayload);
    addOptions(controls.status, companies.map((item) => item.status));
    addOptions(controls.board, companies.map((item) => item.board));
    addOptions(controls.completeness, companies.map((item) => item.scoreCompleteness));
    addOptions(controls.freshness, companies.map((item) => item.sourceDate));
    snapshot.textContent = `研究池共 ${companies.length} 家 · 数据生成于 ${companiesPayload.meta?.generatedAt || "待验证"}`;

    function render() {
      const visible = filterCompanies(companies, {
        query: controls.search.value,
        status: controls.status.value,
        board: controls.board.value,
        completeness: controls.completeness.value,
        freshness: controls.freshness.value,
      });
      count.textContent = `显示 ${visible.length} / ${companies.length} 家`;
      cards.innerHTML = visible.length
        ? visible.map(renderCard).join("")
        : '<p class="empty-state">没有符合当前条件的企业，请调整筛选条件。</p>';
    }

    Object.values(controls).forEach((control) => control.addEventListener("input", render));
    render();
  }).catch(() => {
    snapshot.textContent = "数据载入失败，请确认静态文件完整发布。";
    cards.innerHTML = '<p class="empty-state">暂时无法载入研究数据。</p>';
  });
}

if (typeof document !== "undefined") {
  initializeDashboard();
}
