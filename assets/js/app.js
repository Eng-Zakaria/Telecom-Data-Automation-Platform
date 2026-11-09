/* ============================================================
   TeleComPilot — UI controller
   Charts, navigation, theme, live dashboard behavior
   ============================================================ */

(function () {
  "use strict";

  const $ = (sel, ctx) => (ctx || document).querySelector(sel);
  const $$ = (sel, ctx) => Array.from((ctx || document).querySelectorAll(sel));

  /* ---------- Chart.js globals ---------- */
  const CSS = getComputedStyle(document.documentElement);
  const isDark = () => document.documentElement.dataset.theme === "dark";
  const theme = () => ({
    grid: isDark() ? "rgba(148,163,184,0.08)" : "rgba(100,116,139,0.12)",
    tick: isDark() ? "#8ea2c0" : "#64748b",
    border: isDark() ? "#1c2a42" : "#dfe7f1",
    text: isDark() ? "#e6edf7" : "#0f1c30",
  });

  const baseOpts = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { labels: { color: theme().tick, usePointStyle: true, boxWidth: 7, font: { size: 11 } } },
      tooltip: {
        backgroundColor: isDark() ? "#131f33" : "#ffffff",
        titleColor: theme().text,
        bodyColor: theme().text,
        borderColor: theme().border,
        borderWidth: 1,
        padding: 10,
        cornerRadius: 8,
      },
    },
    scales: {
      x: {
        grid: { color: theme().grid },
        ticks: { color: theme().tick, font: { size: 11 } },
        border: { color: theme().border },
      },
      y: {
        grid: { color: theme().grid },
        ticks: { color: theme().tick, font: { size: 11 } },
        border: { display: false },
      },
    },
  };

  const charts = {};

  function makeChart(id, cfg) {
    const el = document.getElementById(id);
    if (!el) return;
    charts[id] = new Chart(el, { ...cfg, options: deepMerge(structuredClone(baseOpts), cfg.options || {}) });
  }

  function deepMerge(a, b) {
    for (const k of Object.keys(b)) {
      if (b[k] && typeof b[k] === "object" && !Array.isArray(b[k]) && a[k] && typeof a[k] === "object") {
        deepMerge(a[k], b[k]);
      } else {
        a[k] = b[k];
      }
    }
    return a;
  }

  function refreshThemeScales() {
    Object.values(charts).forEach((c) => {
      const o = c.options;
      if (o.scales) {
        Object.values(o.scales).forEach((s) => {
          if (s.grid) s.grid.color = theme().grid;
          if (s.ticks) s.ticks.color = theme().tick;
          if (s.border) s.border.color = theme().border;
        });
      }
      if (o.plugins && o.plugins.legend) o.plugins.legend.labels.color = theme().tick;
      c.update();
    });
  }

  /* ---------- Mock live data ---------- */
  const dayLabels = () => {
    const out = [];
    const now = new Date();
    for (let i = 13; i >= 0; i--) {
      const d = new Date(now);
      d.setDate(d.getDate() - i);
      out.push(`${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}`);
    }
    return out;
  };

  function series(len, lo, hi, seed) {
    const out = [];
    let v = seed != null ? seed : (lo + hi) / 2;
    for (let i = 0; i < len; i++) {
      v += (Math.random() - 0.48) * (hi - lo) * 0.22;
      v = Math.min(hi, Math.max(lo, v));
      out.push(+v.toFixed(2));
    }
    return out;
  }

  /* ---------- Sparklines ---------- */
  function drawSparkline(canvas, color, data) {
    const w = canvas.width || 70;
    const h = canvas.height || 26;
    const ctx = canvas.getContext("2d");
    const px = w / (data.length - 1);
    const max = Math.max(...data), min = Math.min(...data);
    const scale = max - min || 1;
    const grad = ctx.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, color + "33");
    grad.addColorStop(1, color + "00");
    ctx.clearRect(0, 0, w, h);
    ctx.beginPath();
    data.forEach((v, i) => (i === 0 ? ctx.moveTo(i * px, h - ((v - min) / scale) * h) : ctx.lineTo(i * px, h - ((v - min) / scale) * h)));
    ctx.lineTo(w, h); ctx.lineTo(0, h); ctx.closePath();
    ctx.fillStyle = grad; ctx.fill();
    ctx.beginPath();
    ctx.strokeStyle = color; ctx.lineWidth = 1.6; ctx.lineJoin = "round";
    data.forEach((v, i) => (i === 0 ? ctx.moveTo(i * px, h - ((v - min) / scale) * h) : ctx.lineTo(i * px, h - ((v - min) / scale) * h)));
    ctx.stroke();
  }

  function initSparklines() {
    $$(".sparkline").forEach((el) => {
      const key = el.dataset.spark;
      const defs = {
        records: { c: "#14b8a6", n: 18, lo: 180, hi: 248 },
        pipelines: { c: "#3b82f6", n: 18, lo: 96, hi: 99.4 },
        quality: { c: "#f59e0b", n: 18, lo: 95, hi: 98 },
        latency: { c: "#ef4444", n: 18, lo: 165, hi: 205 },
        models: { c: "#8b5cf6", n: 18, lo: 10, hi: 14 },
        streams: { c: "#10b981", n: 18, lo: 38, hi: 44 },
      };
      const cfg = defs[key];
      const canvas = document.createElement("canvas");
      canvas.width = 70; canvas.height = 26;
      el.appendChild(canvas);
      drawSparkline(canvas, cfg.c, series(cfg.n, cfg.lo, cfg.hi));
    });
  }

  /* ---------- KPI count-up ---------- */
  function initCountUp() {
    const els = $$(".kpi-value [data-target]");
    els.forEach((el) => {
      const target = parseFloat(el.dataset.target);
      const decimals = target % 1 !== 0 ? 1 : 0;
      const dur = 1100;
      const start = performance.now();
      function frame(t) {
        const p = Math.min(1, (t - start) / dur);
        const eased = 1 - Math.pow(1 - p, 3);
        el.textContent = (target * eased).toFixed(decimals);
        if (p < 1) requestAnimationFrame(frame);
      }
      requestAnimationFrame(frame);
    });
  }

  /* ---------- Navigation ---------- */
  const viewMeta = {
    overview: ["Platform Overview", "Unified control plane for telecom data operations"],
    architecture: ["System Architecture", "Medallion architecture across Azure + Microsoft Fabric"],
    pipelines: ["Data Pipelines", "Bronze, silver and gold pipelines — batch and streaming"],
    models: ["ML Models", "Model registry, performance and promotion lifecycle"],
    domains: ["Business Domains", "Analytics across 8 operational domains"],
    infrastructure: ["Infrastructure", "Azure resources and local development stack"],
    cicd: ["CI / CD", "Automated delivery with quality gates"],
    monitoring: ["Monitoring", "Golden signals, alerts and live metrics"],
    docs: ["Documentation & ADRs", "Architecture decision records and operational docs"],
  };

  function switchView(name) {
    if (!viewMeta[name]) return;
    $$(".nav-item").forEach((b) => b.classList.toggle("is-active", b.dataset.view === name));
    $$(".view").forEach((v) => v.classList.remove("is-active"));
    const panel = document.getElementById(`view-${name}`);
    if (panel) panel.classList.add("is-active");
    $("#pageTitle").textContent = viewMeta[name][0];
    $("#pageSubtitle").textContent = viewMeta[name][1];
    $("#sidebar").classList.remove("open");
    window.scrollTo({ top: 0, behavior: "smooth" });
    requestAnimationFrame(() => {
      Object.values(charts).forEach((c) => c.resize());
    });
  }

  $$(".nav-item").forEach((b) => b.addEventListener("click", () => switchView(b.dataset.view)));
  $$("[data-go]").forEach((a) =>
    a.addEventListener("click", (e) => {
      e.preventDefault();
      switchView(a.dataset.go);
    })
  );

  $$(".chip").forEach((chip) =>
    chip.addEventListener("click", () => {
      chip.parentElement.querySelectorAll(".chip").forEach((c) => c.classList.remove("is-active"));
      chip.classList.add("is-active");
      toast(`Viewing ${chip.dataset.range || "range"} data`);
    })
  );

  /* ---------- Theme ---------- */
  const themeToggle = $("#themeToggle");
  themeToggle.addEventListener("click", () => {
    const root = document.documentElement;
    root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
    localStorage.setItem("tc-theme", root.dataset.theme);
    refreshThemeScales();
    toast(root.dataset.theme === "dark" ? "Dark mode enabled" : "Light mode enabled");
  });

  const saved = localStorage.getItem("tc-theme");
  if (saved) document.documentElement.dataset.theme = saved;

  /* ---------- Mobile menu ---------- */
  $("#menuToggle").addEventListener("click", () => $("#sidebar").classList.toggle("open"));

  /* ---------- Search (jump navigation) ---------- */
  const search = $("#globalSearch");
  const map = {
    architecture: ["architecture", "medallion", "lake", "system", "stack"],
    pipelines: ["pipeline", "bronze", "silver", "gold", "streaming", "batch", "run"],
    models: ["model", "ml", "churn", "fraud", "registry"],
    domains: ["domain", "retention", "finance", "marketing", "care", "roaming", "product", "assurance"],
    infrastructure: ["infrastructure", "azure", "docker", "terraform", "cloud", "cost"],
    cicd: ["ci", "cd", "deploy", "workflow", "actions", "gate"],
    monitoring: ["monitor", "alert", "latency", "load"],
    docs: ["doc", "adr", "readme", "runbook"],
  };
  search.addEventListener("input", () => {
    const q = search.value.trim().toLowerCase();
    if (q.length < 2) return;
    for (const [view, keys] of Object.entries(map)) {
      if (keys.some((k) => q.includes(k) || k.includes(q))) {
        switchView(view);
        if (q.length >= 3) toast(`Jumped to ${viewMeta[view][0].toLowerCase()}`);
        break;
      }
    }
  });

  function toast(msg) {
    const t = $("#toast");
    t.textContent = msg;
    t.classList.add("show");
    clearTimeout(t._t);
    t._t = setTimeout(() => t.classList.remove("show"), 2400);
  }

  /* ---------- Live ticker (throughput KPI) ---------- */
  setInterval(() => {
    const el = $('[data-kpi="streams"] [data-target]');
    if (el) {
      const base = 42.6;
      const jitter = +(base + (Math.random() - 0.5) * 4).toFixed(1);
      el.textContent = jitter;
      const dot = $(".status-indicator .dot");
      if (dot && Math.random() > 0.97) dot.style.background = "#f59e0b";
      else if (dot) dot.style.background = "";
    }
  }, 2500);

  /* ---------- Progress bar on load ---------- */
  const bar = document.createElement("div");
  bar.id = "progressBar";
  document.body.appendChild(bar);
  requestAnimationFrame(() => bar.classList.add("active"));
  bar.style.width = "30%";
  window.addEventListener("load", () => {
    bar.style.width = "100%";
    setTimeout(() => { bar.classList.remove("active"); bar.style.width = "0%"; }, 400);
  });

  /* ---------- Charts ---------- */
  const labels14 = dayLabels();

  /* Throughput */
  makeChart("chart-throughput", {
    type: "line",
    data: {
      labels: labels14,
      datasets: [
        {
          label: "Ingestion (k events/s)",
          data: series(14, 38, 48),
          borderColor: "#3b82f6",
          backgroundColor: "rgba(59,130,246,0.10)",
          fill: true,
          tension: 0.4,
          borderWidth: 2,
          pointRadius: 0,
        },
        {
          label: "Processed (M rows)",
          data: series(14, 130, 165),
          borderColor: "#10b981",
          backgroundColor: "rgba(16,185,129,0.08)",
          fill: true,
          tension: 0.4,
          borderWidth: 2,
          pointRadius: 0,
          yAxisID: "y1",
        },
      ],
    },
    options: {
      scales: {
        ...baseOpts.scales,
        y: { ...baseOpts.scales.y, title: { display: true, text: "k events/s", color: theme().tick, font: { size: 10 } } },
        y1: {
          position: "right",
          grid: { drawOnChartArea: false },
          ticks: { color: theme().tick, font: { size: 11 } },
          title: { display: true, text: "M rows", color: theme().tick, font: { size: 10 } },
        },
      },
    },
  });

  /* Sources doughnut */
  makeChart("chart-sources", {
    type: "doughnut",
    data: {
      labels: ["CDR", "Billing", "Network KPI", "Complaints", "Roaming"],
      datasets: [{
        data: [42, 28, 18, 7, 5],
        backgroundColor: ["#3b82f6", "#10b981", "#8b5cf6", "#f59e0b", "#06b6d4"],
        borderWidth: 0,
        hoverOffset: 6,
      }],
    },
    options: {
      cutout: "68%",
      plugins: {
        legend: { position: "bottom", align: "start", labels: { ...baseOpts.plugins.legend.labels, boxWidth: 9 } },
      },
    },
  });

  /* Domains usage */
  makeChart("chart-domains", {
    type: "bar",
    data: {
      labels: ["Retention", "RA", "NetOps", "Marketing", "Care", "Finance", "Roaming", "Product"],
      datasets: [{
        label: "Queries (k)",
        data: [86, 41, 64, 52, 38, 47, 22, 31],
        backgroundColor: ["#10b981", "#8b5cf6", "#3b82f6", "#f59e0b", "#ef4444", "#14b8a6", "#06b6d4", "#ec4899"],
        borderRadius: 6,
        barThickness: 18,
      }],
    },
    options: {
      plugins: { legend: { display: false } },
      scales: { ...baseOpts.scales, x: { ...baseOpts.scales.x, grid: { display: false } } },
    },
  });

  /* Pipeline duration */
  makeChart("chart-pipeline-duration", {
    type: "bar",
    data: {
      labels: ["00:00", "02:00", "04:00", "06:00", "08:00", "10:00", "12:00", "14:00", "16:00", "18:00", "20:00", "22:00"],
      datasets: [
        {
          label: "Bronze",
          data: series(12, 2, 6),
          backgroundColor: "rgba(217,119,6,0.55)",
          borderRadius: 5,
          barThickness: 14,
        },
        {
          label: "Silver",
          data: series(12, 4, 9),
          backgroundColor: "rgba(148,163,184,0.55)",
          borderRadius: 5,
          barThickness: 14,
        },
        {
          label: "Gold",
          data: series(12, 5, 12),
          backgroundColor: "rgba(234,179,8,0.55)",
          borderRadius: 5,
          barThickness: 14,
        },
      ],
    },
    options: {
      plugins: { legend: { ...baseOpts.plugins.legend, position: "top" } },
      scales: { ...baseOpts.scales, x: { ...baseOpts.scales.x, grid: { display: false } } },
    },
  });

  /* Quarantine recovered */
  makeChart("chart-quarantine", {
    type: "line",
    data: {
      labels: labels14,
      datasets: [
        {
          label: "Quarantined rows",
          data: series(14, 150, 480),
          borderColor: "#ef4444",
          backgroundColor: "rgba(239,68,68,0.08)",
          fill: true,
          tension: 0.4,
          pointRadius: 0,
        },
        {
          label: "Auto-recovered",
          data: series(14, 120, 430),
          borderColor: "#10b981",
          backgroundColor: "rgba(16,185,129,0.08)",
          fill: true,
          tension: 0.4,
          pointRadius: 0,
        },
      ],
    },
    options: { plugins: { legend: { position: "bottom" } } },
  });

  /* Model performance */
  makeChart("chart-model-perf", {
    type: "line",
    data: {
      labels: labels14,
      datasets: [
        { label: "Churn", data: series(14, 0.88, 0.94), borderColor: "#10b981", tension: 0.4, pointRadius: 0, borderWidth: 2 },
        { label: "Fraud", data: series(14, 0.89, 0.93), borderColor: "#ef4444", tension: 0.4, pointRadius: 0, borderWidth: 2 },
        { label: "News (KPI)", data: series(14, 0.87, 0.92), borderColor: "#3b82f6", tension: 0.4, pointRadius: 0, borderWidth: 2 },
        { label: "Propensity", data: series(14, 0.87, 0.91), borderColor: "#8b5cf6", tension: 0.4, pointRadius: 0, borderWidth: 2 },
      ],
    },
    options: {
      plugins: { legend: { position: "top" } },
      scales: {
        ...baseOpts.scales,
        y: { ...baseOpts.scales.y, min: 0.85, max: 0.95, ticks: { ...baseOpts.scales.y.ticks, callback: (v) => v.toFixed(2) } },
      },
    },
  });

  /* Executive dashboard */
  makeChart("chart-exec", {
    type: "line",
    data: {
      labels: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
      datasets: [
        { label: "Revenue (SAR M)", data: series(12, 380, 460), borderColor: "#10b981", fill: true, backgroundColor: "rgba(16,185,129,0.08)", tension: 0.4, pointRadius: 2 },
        { label: "ARPU (SAR)", data: series(12, 54, 64), borderColor: "#3b82f6", tension: 0.4, pointRadius: 2, yAxisID: "y1" },
        { label: "Subscribers (k)", data: series(12, 2400, 2680), borderColor: "#8b5cf6", tension: 0.4, pointRadius: 2, yAxisID: "y2" },
      ],
    },
    options: {
      plugins: { legend: { position: "top" } },
      scales: {
        x: baseOpts.scales.x,
        y: { ...baseOpts.scales.y, position: "left" },
        y1: { position: "right", grid: { drawOnChartArea: false }, ticks: { color: theme().tick, font: { size: 11 } } },
        y2: { position: "right", grid: { drawOnChartArea: false }, ticks: { color: theme().tick, font: { size: 11 } } },
      },
    },
  });

  /* Cost by environment */
  makeChart("chart-cost", {
    type: "doughnut",
    data: {
      labels: ["Production", "Staging", "Development", "Ephemeral"],
      datasets: [{
        data: [8200, 1800, 950, 320],
        backgroundColor: ["#10b981", "#f59e0b", "#3b82f6", "#8b5cf6"],
        borderWidth: 0,
        hoverOffset: 6,
      }],
    },
    options: {
      cutout: "66%",
      plugins: {
        legend: { position: "bottom", labels: { ...baseOpts.plugins.legend.labels, boxWidth: 9 } },
        tooltip: { ...baseOpts.plugins.tooltip, callbacks: { label: (c) => ` ${c.label}: SAR ${c.parsed.toLocaleString()}/mo` } },
      },
    },
  });

  /* Deploy frequency */
  makeChart("chart-deploys", {
    type: "bar",
    data: {
      labels: labels14,
      datasets: [
        { label: "Deployments", data: series(14, 2, 10), backgroundColor: "rgba(16,185,129,0.7)", borderRadius: 5, barThickness: 16 },
        { label: "PRs merged", data: series(14, 1, 6), backgroundColor: "rgba(59,130,246,0.6)", borderRadius: 5, barThickness: 16 },
      ],
    },
    options: {
      plugins: { legend: { position: "top" } },
      scales: { ...baseOpts.scales, x: { ...baseOpts.scales.x, grid: { display: false } } },
    },
  });

  /* Monitor live */
  function liveChartData() {
    const labels = [];
    for (let i = 59; i >= 0; i--) {
      const d = new Date(Date.now() - i * 1000);
      labels.push(d.toTimeString().slice(0, 8));
    }
    return labels;
  }
  const monitorLabels = liveChartData();
  let cpuSeries = series(60, 22, 58);
  let memSeries = series(60, 38, 66);
  let latSeries = series(60, 90, 190);

  const monitorChart = new Chart($("#chart-monitor-live"), {
    type: "line",
    data: {
      labels: monitorLabels,
      datasets: [
        { label: "CPU %", data: cpuSeries, borderColor: "#3b82f6", tension: 0.35, pointRadius: 0, borderWidth: 1.6 },
        { label: "Memory %", data: memSeries, borderColor: "#8b5cf6", tension: 0.35, pointRadius: 0, borderWidth: 1.6 },
        { label: "Latency ms", data: latSeries, borderColor: "#f59e0b", tension: 0.35, pointRadius: 0, borderWidth: 1.6 },
      ],
    },
    options: deepMerge(structuredClone(baseOpts), {
      animation: false,
      scales: { y: { ...baseOpts.scales.y, min: 0, max: 200 } },
    }),
  });
  charts["chart-monitor-live"] = monitorChart;

  setInterval(() => {
    cpuSeries = [...cpuSeries.slice(1), +(cpuSeries[cpuSeries.length - 1] + (Math.random() - 0.5) * 7).toFixed(1)];
    memSeries = [...memSeries.slice(1), +(memSeries[memSeries.length - 1] + (Math.random() - 0.5) * 4).toFixed(1)];
    latSeries = [...latSeries.slice(1), +(latSeries[latSeries.length - 1] + (Math.random() - 0.5) * 12).toFixed(0)];
    monitorChart.data.datasets[0].data = cpuSeries;
    monitorChart.data.datasets[1].data = memSeries;
    monitorChart.data.datasets[2].data = latSeries;
    monitorChart.update("none");
  }, 1500);

  /* Alerts volume */
  makeChart("chart-alerts", {
    type: "line",
    data: {
      labels: labels14,
      datasets: [
        { label: "Critical", data: series(14, 0, 4), borderColor: "#ef4444", tension: 0.4, pointRadius: 0, fill: true, backgroundColor: "rgba(239,68,68,0.07)" },
        { label: "Warning", data: series(14, 4, 14), borderColor: "#f59e0b", tension: 0.4, pointRadius: 0, fill: true, backgroundColor: "rgba(245,158,11,0.07)" },
        { label: "Info", data: series(14, 10, 26), borderColor: "#3b82f6", tension: 0.4, pointRadius: 0, fill: true, backgroundColor: "rgba(59,130,246,0.07)" },
      ],
    },
    options: { plugins: { legend: { position: "top" } } },
  });

  /* ---------- Domain mini charts ---------- */
  const miniSeeds = {
    retention: ["#10b981", 18, 20], fraud: ["#8b5cf6", 4, 18], network: ["#3b82f6", 6, 22],
    marketing: ["#f59e0b", 10, 28], care: ["#ef4444", 12, 30], finance: ["#14b8a6", 14, 26],
    roaming: ["#06b6d4", 8, 20], product: ["#ec4899", 16, 32],
    rev: ["#10b981", 30, 50], churn: ["#ef4444", 8, 20], nps: ["#3b82f6", 30, 48], lat: ["#f59e0b", 60, 90],
  };
  function initMiniCharts() {
    $$("canvas[data-mini]").forEach((canvas) => {
      const key = canvas.dataset.mini;
      const [color, lo, hi] = miniSeeds[key] || ["#10b981", 10, 20];
      const w = 110, h = 34;
      canvas.width = w; canvas.height = h;
      const d = series(16, lo, hi);
      const ctx = canvas.getContext("2d");
      const max = Math.max(...d), min = Math.min(...d);
      const grad = ctx.createLinearGradient(0, 0, 0, h);
      grad.addColorStop(0, color + "22");
      grad.addColorStop(1, color + "00");
      ctx.beginPath();
      d.forEach((v, i) => (i === 0 ? ctx.moveTo((i / (d.length - 1)) * w, h - ((v - min) / (max - min || 1)) * h) : ctx.lineTo((i / (d.length - 1)) * w, h - ((v - min) / (max - min || 1)) * h)));
      ctx.strokeStyle = color; ctx.lineWidth = 1.6; ctx.stroke();
      ctx.beginPath();
      d.forEach((v, i) => (i === 0 ? ctx.moveTo((i / (d.length - 1)) * w, h - ((v - min) / (max - min || 1)) * h) : ctx.lineTo((i / (d.length - 1)) * w, h - ((v - min) / (max - min || 1)) * h)));
      ctx.lineTo(w, h); ctx.lineTo(0, h); ctx.closePath(); ctx.fillStyle = grad; ctx.fill();
    });
  }

  /* ---------- Medallion bar animation ---------- */
  setTimeout(() => {
    $$(".med-bar span").forEach((b) => (b.style.width = b.getAttribute("style") ? b.style.width.split(":")[1] : "0%"));
  }, 150);

  /* ---------- Initialization ---------- */
  function init() {
    initSparklines();
    initCountUp();
    initMiniCharts();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();