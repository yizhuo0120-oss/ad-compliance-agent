"use strict";
const $ = (selector) => document.querySelector(selector);
let lastReport = null;
let busy = false;
const riskNames = { violation: "发现违规风险", suspicious: "疑似风险 · 待复核", compliant: "未发现风险" };

function node(tag, className, text) {
  const item = document.createElement(tag);
  if (className) item.className = className;
  if (text !== undefined) item.textContent = text;
  return item;
}
function errorMessage(message) {
  $("#error").textContent = message;
  $("#error").hidden = false;
}
function progress(message) {
  $("#progress-text").textContent = message;
}
function setBusy(value, message = "正在处理…") {
  busy = value;
  document.querySelectorAll("form button[type=submit], .tab").forEach((button) => { button.disabled = value; });
  $("#progress").hidden = !value;
  progress(message);
}
function resetResult(title) {
  $("#result-title").textContent = title;
  $("#error").hidden = true;
  $("#download-report").hidden = true;
  lastReport = null;
  $("#result").replaceChildren();
}
async function api(path, data) {
  const response = await fetch(path, {
    method: "POST", headers: { "Content-Type": "application/json", "X-Demo-Token": $("#access-token").value },
    body: JSON.stringify(data), signal: AbortSignal.timeout(290000),
  });
  let result;
  try { result = await response.json(); } catch (_) { throw new Error("服务暂时不可用，请稍后重试。"); }
  if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "提交内容不符合要求，请检查后重试。");
  return result;
}
function failure(error) {
  errorMessage(error.name === "TimeoutError" ? "处理超时，请稍后重试。" : (error.message || "网络连接失败，请稍后重试。"));
}
function reportView(report, mode = "full") {
  const section = node("div");
  const summary = node("div", `report-summary ${report.risk_level}`);
  summary.append(node("span", "risk-badge", mode === "keyword" ? "关键词初筛 · 需进一步审核" : (riskNames[report.risk_level] || "待复核")));
  summary.append(node("p", "", report.summary));
  summary.append(node("small", "", `${report.findings.length} 项风险信号 · ${(report.meta.latency_ms / 1000).toFixed(1)} 秒`));
  section.append(summary);
  for (const finding of report.findings) {
    const item = node("article", "finding");
    item.append(node("h4", "", finding.type), node("blockquote", "", finding.fragment), node("p", "", finding.reason));
    const law = finding.law || {};
    const details = node("details");
    details.append(node("summary", "", [law.name, law.article].filter(Boolean).join(" · ") || "法条依据待核验"));
    details.append(node("p", "", law.quote || "该引用未匹配到知识库原文，请人工核验。"));
    item.append(details);
    if (finding.suggestion) item.append(node("p", "rewrite", `改写方向：${finding.suggestion}`));
    section.append(item);
  }
  if (report.transcript?.texts) {
    const details = node("details", "transcript");
    details.append(node("summary", "", "查看海报转写文字"), node("p", "", report.transcript.texts.join("\n")));
    section.append(details);
  }
  return section;
}
function storeReport(value) { lastReport = value; $("#download-report").hidden = false; }

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    if (busy) return;
    document.querySelectorAll(".tab").forEach((item) => {
      const active = item === tab;
      item.classList.toggle("active", active); item.setAttribute("aria-selected", String(active)); item.tabIndex = active ? 0 : -1;
      $(`#panel-${item.dataset.tab}`).hidden = !active;
    });
  });
  tab.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const tabs = [...document.querySelectorAll(".tab")];
    const index = tabs.indexOf(tab);
    const next = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
    tabs[next].click(); tabs[next].focus();
  });
});
function textCount() { $("#text-count").textContent = `${$("#ad-text").value.length} / 8000`; }
$("#ad-text").addEventListener("input", textCount);
$("#load-sample").addEventListener("click", () => { $("#ad-text").value = "全网最低价！行业第一品牌，百分百有效，赶紧抢购！"; textCount(); });
$("#text-form").addEventListener("submit", async (event) => {
  event.preventDefault(); if (busy) return;
  resetResult("审核结果"); setBusy(true, "正在检查文案并检索相关法条…");
  try {
    const mode = $("#audit-mode").value;
    const report = await api("/api/audit/text", { text: $("#ad-text").value, mode });
    $("#result").append(reportView(report, mode)); storeReport(report);
  } catch (error) { failure(error); } finally { setBusy(false); }
});
function readFile(file) {
  return new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = () => reject(new Error("无法读取图片。")); reader.readAsDataURL(file); });
}
$("#poster-file").addEventListener("change", async () => {
  $("#error").hidden = true; $("#poster-preview").hidden = true;
  const file = $("#poster-file").files[0]; if (!file) return;
  if (file.size > 3 * 1024 * 1024) { errorMessage("请选择小于 3 MB 的图片。"); $("#poster-file").value = ""; return; }
  if (!["image/png", "image/jpeg", "image/webp"].includes(file.type)) { errorMessage("仅支持 PNG、JPEG 或 WebP 图片。"); $("#poster-file").value = ""; return; }
  try { $("#poster-preview").src = await readFile(file); $("#poster-preview").hidden = false; $("#upload-title").textContent = file.name; } catch (error) { failure(error); }
});
$("#image-form").addEventListener("submit", async (event) => {
  event.preventDefault(); if (busy) return;
  const file = $("#poster-file").files[0]; if (!file) return;
  resetResult("海报审核结果"); setBusy(true, "正在转写海报文字并检查画面风险…");
  try {
    const report = await api("/api/audit/image", { image: await readFile(file) });
    $("#result").append(reportView(report)); storeReport(report);
  } catch (error) { failure(error); } finally { setBusy(false); }
});
function materialView(result) {
  const pack = result.pack, material = pack.platforms[0];
  const item = node("article", "material");
  const header = node("div", "material-head");
  header.append(node("h4", "", material.platform));
  const summary = node("span", "risk-badge", riskNames[pack.audit.risk_level]);
  if (pack.audit.risk_level !== "compliant") summary.style.color = "var(--gold)";
  header.append(summary); item.append(header, node("pre", "", material.copy));
  if (material.tags.length) item.append(node("div", "tags", material.tags.map((tag) => `#${tag.replace(/^#/, "")}`).join(" ")));
  item.append(node("p", "material-note", `审核 ${result.rounds} 轮 · 改写 ${pack.audit.revisions} 次${pack.audit.risk_level !== "compliant" ? " · 请人工复核后再发布" : ""}`));
  if (result.report.findings.length) {
    const details = node("details", "transcript");
    details.append(node("summary", "", "查看最终审核依据"), reportView(result.report)); item.append(details);
  }
  const copyButton = node("button", "text-button", "复制文案 ↗"); copyButton.type = "button";
  copyButton.addEventListener("click", async () => { try { await navigator.clipboard.writeText(material.copy); copyButton.textContent = "已复制 ✓"; } catch (_) { errorMessage("无法自动复制，请选中文案复制。"); } });
  item.append(copyButton);
  if (pack.audit.risk_level === "compliant") {
    const imageButton = node("button", "primary", "生成宣传场景图 ↗"); imageButton.type = "button";
    imageButton.addEventListener("click", async () => {
      if (busy) return;
      $("#error").hidden = true; imageButton.disabled = true; setBusy(true, "正在生成宣传场景图并添加 AI 标识…");
      try {
        const promo = await api("/api/promo", { product: pack.product, copy: material.copy });
        const image = node("img", "promo-image"); image.src = promo.image; image.alt = `${pack.product.name}的 AI 宣传场景图`;
        const download = node("a", "promo-link", "下载宣传图 ↓"); download.href = promo.image; download.download = "ai-promo.jpg";
        item.append(image, node("p", "material-note", promo.ai_disclosure), download);
        imageButton.hidden = true; result.promo = promo;
      } catch (error) { failure(error); } finally { setBusy(false); imageButton.disabled = false; }
    });
    item.append(imageButton);
  }
  return item;
}
$("#generate-form").addEventListener("submit", async (event) => {
  event.preventDefault(); if (busy) return;
  const platforms = [...document.querySelectorAll('input[name="platform"]:checked')].map((input) => input.value);
  if (!platforms.length) { errorMessage("请至少选择一个投放平台。"); return; }
  resetResult("生成物料"); setBusy(true, "正在提炼商品卖点与投放策略…");
  const outputs = [];
  try {
    const product = await api("/api/plan", { name: $("#product-name").value, info: $("#product-info").value });
    for (let i = 0; i < platforms.length; i++) {
      progress(`正在生成并审核 ${platforms[i]} 文案（${i + 1}/${platforms.length}）…`);
      const result = await api("/api/generate", { product, platform: platforms[i] });
      outputs.push(result); $("#result").append(materialView(result)); storeReport(outputs);
    }
  } catch (error) { failure(error); } finally { setBusy(false); }
});
$("#download-report").addEventListener("click", () => {
  if (!lastReport) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(lastReport, null, 2)], { type: "application/json" }));
  const link = node("a"); link.href = url; link.download = "ad-compliance-report.json"; document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
});
(async () => {
  try {
    const response = await fetch("/api/health"); if (!response.ok) throw new Error();
    const health = await response.json();
    $("#service-status").replaceChildren(node("i"), document.createTextNode(health.configured ? "审核服务已就绪" : "可体验关键词初筛"));
    $("#service-status").classList.toggle("unconfigured", !health.configured);
    $("#access-panel").hidden = !health.access_required;
    if (!health.configured) $("#audit-mode").value = "keyword";
  } catch (_) { $("#service-status").replaceChildren(node("i"), document.createTextNode("服务暂时不可用")); }
})();
