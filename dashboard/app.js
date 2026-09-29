/* Drishti operator dashboard — all views run on the exported model bundle (dashboard/data). */
"use strict";
const $ = (s, r = document) => r.querySelector(s);
const fmt = (v, d = 0) => (v == null || !isFinite(v)) ? "–" : Number(v).toFixed(d);
const pct = v => (v == null || !isFinite(v)) ? "–" : Math.round(v * 100) + "%";
const m2 = v => v >= 10000 ? (v / 10000).toFixed(2) + " ha" : Math.round(v).toLocaleString() + " m²";
const S = { view: "live", mode: "ok", role: "Flood Control Operator", audit: [], charts: {}, sel: null, play: null,
  route: { origin: null, dest: null, picking: null, results: [], closed: new Set() }, approvals: {}, scen: "baseline",
  scenDiff: false, thr: "10", layer: "expected", radarQ: "p50", radarLead: 2, vehicle: "car", sensor: 0 };
let D = {}, G = {}, map, overlay, viewLayer, baseLayer;

// ------------------------------------------------------------------ data
const _dc = new Map();
function dec(s) {
  let a = _dc.get(s); if (a) return a;
  const b = atob(s); a = new Uint8Array(b.length);
  for (let i = 0; i < b.length; i++) a[i] = b.charCodeAt(i);
  _dc.set(s, a); return a;
}
async function load() {
  const j = u => fetch(u).then(r => { if (!r.ok) throw new Error(u); return r.json(); });
  const t = u => fetch(u).then(r => r.text());
  const [grid, net, fc, twin, scen, val, roads, blocks, bnd, bld] = await Promise.all([
    j("data/grid.json"), j("data/network.json"), j("data/forecast.json"), j("data/twin.json"),
    j("data/scenarios.json"), j("data/validation.json"), j("../data/roads.geojson"),
    t("../data/blocks_centroids.csv"), j("../kiet_terrain/campus_osm.geojson"), j("../data/campus_accurate.geojson")]);
  D = { grid, net, fc, twin, scen, val, roads, bnd, bld };
  D.blocks = blocks.trim().split(/\r?\n/).slice(1).map(l => { const c = l.split(","); return { name: c[0], lat: +c[1], lon: +c[2], floors: c[3] }; });
  G = { ny: grid.ny, nx: grid.nx, n: grid.ny * grid.nx, s: grid.bounds[0][0], w: grid.bounds[0][1], nn: grid.bounds[1][0], e: grid.bounds[1][1],
    off: grid.crop_offset || [11, 28] };
  G.dlat = (G.nn - G.s) / G.ny; G.dlon = (G.e - G.w) / G.nx;
  G.dom = dec(grid.domain); G.bld = dec(grid.building); G.road = dec(grid.road); G.low = dec(grid.low_points);
  G.imp = dec(grid.imperv); G.acc = dec(grid.accum_log);
  G.wet = new Uint8Array(G.n); for (let k = 0; k < G.n; k++) G.wet[k] = G.dom[k] && !G.bld[k] ? 1 : 0;
  G.nwet = G.wet.reduce((a, b) => a + b, 0);
  let amax = 0; for (let k = 0; k < G.n; k++) if (G.wet[k]) amax = Math.max(amax, G.acc[k]); G.accMax = amax;
}
const FC = () => D.fc[S.mode];
const F = () => FC().forecast;
const LEADS = () => FC().lead_min;
const cellLL = (i, j) => [G.nn - (i + 0.5) * G.dlat, G.w + (j + 0.5) * G.dlon];
function llCell(ll) {
  const i = Math.floor((G.nn - ll.lat) / G.dlat), j = Math.floor((ll.lng - G.w) / G.dlon);
  return (i < 0 || j < 0 || i >= G.ny || j >= G.nx) ? null : { i, j, k: i * G.nx + j };
}
const cellOfLL = (lat, lon) => llCell({ lat, lng: lon });

// ------------------------------------------------------------------ rendering
const DEPTH_STOPS = [[3, null], [10, [125, 190, 255, 150]], [20, [59, 139, 255, 205]], [30, [224, 165, 38, 225]], [1e9, [239, 68, 82, 240]]];
function depthCol(cm) { if (cm < 3) return null; for (const [t, c] of DEPTH_STOPS) if (cm < t) return c; return null; }
function probCol(p) {
  if (p < 0.05) return null;
  const a = [59, 139, 255], b = [164, 123, 255], c = [239, 68, 82];
  const [x, y, t] = p < 0.5 ? [a, b, p / 0.5] : [b, c, (p - 0.5) / 0.5];
  return [x[0] + (y[0] - x[0]) * t, x[1] + (y[1] - x[1]) * t, x[2] + (y[2] - x[2]) * t, 90 + 160 * p];
}
function diffCol(dcm) {
  if (Math.abs(dcm) < 2) return null;
  const t = Math.min(Math.abs(dcm) / 30, 1);
  return dcm > 0 ? [239, 68, 82, 80 + 170 * t] : [47, 191, 113, 80 + 170 * t];
}
function paint(fn) {
  const c = document.createElement("canvas"); c.width = G.nx; c.height = G.ny;
  const ctx = c.getContext("2d"), img = ctx.createImageData(G.nx, G.ny);
  for (let k = 0; k < G.n; k++) {
    if (!G.wet[k]) continue;
    const col = fn(k); if (!col) continue;
    img.data[4 * k] = col[0]; img.data[4 * k + 1] = col[1]; img.data[4 * k + 2] = col[2]; img.data[4 * k + 3] = col[3];
  }
  ctx.putImageData(img, 0, 0);
  overlay.setUrl(c.toDataURL()); overlay.setOpacity(1);
}
const clearOverlay = () => overlay.setOpacity(0);
function legendDepth(title = "Water depth") {
  $("#legend").innerHTML = `${title}<span class="sw" style="background:rgb(125,190,255)"></span>3–10 cm<span class="sw" style="background:rgb(59,139,255)"></span>10–20<span class="sw" style="background:rgb(224,165,38)"></span>20–30<span class="sw" style="background:rgb(239,68,82)"></span>&gt;30 cm`;
}
function legendProb(t) {
  $("#legend").innerHTML = `P(depth &gt; ${t} cm)<span class="sw" style="background:rgb(59,139,255)"></span>5%<span class="sw" style="background:rgb(164,123,255)"></span>50%<span class="sw" style="background:rgb(239,68,82)"></span>100%`;
}
function chart(id, cfg) {
  if (S.charts[id]) S.charts[id].destroy();
  const el = document.getElementById(id); if (!el) return;
  if (!el.parentElement.classList.contains("cw")) { const w = document.createElement("div"); w.className = "cw"; el.replaceWith(w); w.appendChild(el); }
  cfg.options = Object.assign({ responsive: true, maintainAspectRatio: false, animation: false,
    plugins: { legend: { labels: { boxWidth: 10, font: { size: 10 } } } } }, cfg.options || {});
  S.charts[id] = new Chart(el, cfg);
}
function toast(msg) { const t = $("#toast"); t.textContent = msg; t.classList.remove("hidden"); clearTimeout(t._h); t._h = setTimeout(() => t.classList.add("hidden"), 3200); }
function audit(action, detail = "") { S.audit.unshift({ t: new Date().toLocaleTimeString(), role: S.role, action, detail }); }
const tag = k => `<span class="tag ${{ synthetic: "syn", modelled: "mod", derived: "der", observed: "obs" }[k] || ""}">${k}</span>`;
function setSlider({ min = 0, max, value, label, onChange, show = true }) {
  const bar = $("#timebar"); bar.classList.toggle("hidden", !show); if (!show) return;
  stopPlay();
  const s = $("#slider"); s.min = min; s.max = max; s.value = value;
  const upd = () => { $("#sliderLab").textContent = label(+s.value); onChange(+s.value); };
  s.oninput = upd; upd();
  $("#play").onclick = () => {
    if (S.play) return stopPlay();
    $("#play").textContent = "❚❚";
    S.play = setInterval(() => { s.value = +s.value >= +s.max ? s.min : +s.value + 1; upd(); }, 650);
  };
}
function stopPlay() { if (S.play) clearInterval(S.play); S.play = null; $("#play").textContent = "▶"; }

// ------------------------------------------------------------------ shared analytics
function depthAt(leadIdx, k, which = "expected_cm") {
  if (leadIdx < 0) return dec(FC().depth_now_cm)[k];
  return dec(FC()[which][leadIdx])[k];
}
function domainStats(arr) {
  let fl = 0, mx = 0;
  for (let k = 0; k < G.n; k++) if (G.wet[k]) { if (arr[k] >= 10) fl++; if (arr[k] > mx) mx = arr[k]; }
  return { flooded: fl * 25, max: mx };
}
function nodeNear(lat, lon, r = 60) {
  let best = null, bd = 1e9;
  for (const n of D.net.nodes) { const d = distM(lat, lon, n.lat, n.lon); if (d < bd) { bd = d; best = n; } }
  return bd <= r ? { node: best, d: bd } : null;
}
function distM(a, b, c, d) { const dy = (a - c) * 111320, dx = (b - d) * 111320 * Math.cos(a * Math.PI / 180); return Math.hypot(dx, dy); }
function quant(arr, q) { const s = [...arr].sort((a, b) => a - b); const p = (s.length - 1) * q, lo = Math.floor(p); return s[lo] + (s[Math.ceil(p)] - s[lo]) * (p - lo); }
function hotspotBounds(h) {
  const i0 = h.i0 - G.off[0], i1 = h.i1 - G.off[0], j0 = h.j0 - G.off[1], j1 = h.j1 - G.off[1];
  return [[G.nn - i1 * G.dlat, G.w + j0 * G.dlon], [G.nn - i0 * G.dlat, G.w + j1 * G.dlon]];
}
const K0 = () => D.net.live.t0_index;
function healthCard() {
  const f = F(), q = f.quality, g = q.gauge_counts, tw = D.twin;
  const valid = g.VALID, tot = Object.values(g).reduce((a, b) => a + b, 0);
  const spread = domainSpread();
  const sens = tw.sensors.filter(s => s.status === "VALID").length;
  const conf = D.net.nodes.reduce((a, n) => a + n.confidence, 0) / D.net.nodes.length;
  return {
    status: f.health.status,
    rainfall_freshness: q.radar.status === "VALID" ? "5 min (radar)" : "radar " + q.radar.status + " — gauges",
    radar_coverage: q.radar.status === "VALID" ? "100% of 192×192 km mosaic" : "0% (outage)",
    gauges_valid: `${valid}/${tot}`, drainage_coverage: `${D.net.nodes.length} nodes · mean confidence ${conf.toFixed(2)} (synthetic)`,
    sensor_health: `${sens}/${tw.sensors.length} water-level sensors valid`,
    time_since_assimilation: "5 min", uncertainty: spread > 12 ? "HIGH" : spread > 6 ? "MODERATE" : "LOW",
    uncertainty_inflation: f.health.uncertainty_inflation, reasons: f.health.reasons,
  };
}
function domainSpread() {
  const a = dec(FC().p90_cm[LEADS().length - 1]), b = dec(FC().p10_cm[LEADS().length - 1]);
  let s = 0, n = 0; for (let k = 0; k < G.n; k++) if (G.wet[k] && a[k] > 3) { s += a[k] - b[k]; n++; }
  return n ? s / n : 0;
}
function vehicleThr(v) {
  return { "two-wheeler": [0.07, 0.15], car: [0.10, 0.30], ambulance: [0.15, 0.35], bus: [0.25, 0.45], "fire truck": [0.35, 0.60] }[v];
}
function roadStatus(depthM, v) {
  const [deg, imp] = vehicleThr(v);
  if (depthM >= imp) return "Impassable"; if (depthM >= (deg + imp) / 2) return "High"; if (depthM >= deg) return "Degraded"; return "Passable";
}
const STATUS_COL = { Passable: "#2fbf71", Degraded: "#e0a526", High: "#f07b2f", Impassable: "#ef4452" };
function roadRows() {
  const byId = {}; for (const r of F().flood.roads) byId[r.id] = r; return byId;
}

// ------------------------------------------------------------------ views
const VIEWS = {};

VIEWS.live = () => {
  const live = D.net.live, f = F(), h = healthCard();
  const P = $("#panel");
  P.innerHTML = `
  <div class="card"><h3>Forecast health card ${tag("derived")}</h3>
    <div class="row"><span class="st ${h.status}">${h.status}</span><span class="muted small">cycle every 5 min · last run ${fmt(f.timings_s.total, 1)} s</span></div>
    <table>${[["Rainfall freshness", h.rainfall_freshness], ["Radar coverage", h.radar_coverage], ["Rain gauges valid", h.gauges_valid],
      ["Drainage coverage", h.drainage_coverage], ["Sensor health", h.sensor_health], ["Since last assimilation", h.time_since_assimilation],
      ["Forecast uncertainty", h.uncertainty]].map(r => `<tr><td class="muted">${r[0]}</td><td>${r[1]}</td></tr>`).join("")}</table>
    ${h.reasons.length ? `<div class="small" style="margin-top:6px;color:#ffb1b8">${h.reasons.map(r => "• " + r).join("<br>")}</div>` : ""}
  </div>
  <div class="card"><h3>Situation now ${tag("modelled")}</h3><div class="kpis" id="liveKpi"></div></div>
  <div class="card"><h3>Rainfall · campus mean ${tag("derived")}</h3><canvas id="cRain" class="chart"></canvas></div>
  <div class="card"><h3>Active alerts ${tag("modelled")}</h3><div class="list" id="alerts"></div></div>
  <div class="card"><h3>Observation quality (Module B) ${tag(f.sources.radar === "synthetic_radar" ? "synthetic" : "observed")}</h3>
    <table><tr><th>Source</th><th>Status</th><th>Reason</th></tr>
    <tr><td>Radar mosaic</td><td><span class="st ${f.quality.radar.status}">${f.quality.radar.status}</span></td><td class="small muted">${f.quality.radar.reasons.join("; ") || "range, coverage, freeze, jump checks passed"}</td></tr>
    ${Object.entries(f.quality.gauges).map(([id, g]) => `<tr><td>Gauge ${id}</td><td><span class="st ${g.status}">${g.status}</span></td><td class="small muted">${g.reasons.join("; ") || "ok"}</td></tr>`).join("")}
    </table>
    <div class="small muted" style="margin-top:6px">Radar bias correction ×${fmt(f.rainfall.gauge_mean_field_bias.factor, 2)} (${f.rainfall.gauge_mean_field_bias.pairs} gauge pairs, ${f.rainfall.gauge_mean_field_bias.applied ? "applied" : "not applied"})</div>
  </div>
  <div class="card"><h3>Terrain data tier ${tag("derived")}</h3><div class="small">${D.grid.terrain.data_tier_label}<br><span class="muted">${D.grid.terrain.dem_kind} · ${D.grid.terrain.resolution_m} m grid · ${D.grid.terrain.vertical_datum}</span></div></div>`;
  // alerts from hotspots + roads
  const al = [];
  f.flood.hotspots.forEach((hh, i) => al.push({ lvl: hh.early_warning ? "high" : "medium", t: `Hotspot H${i + 1}: P(>20 cm) ${pct(hh.p_exceed_20cm_max)}`,
    d: hh.early_warning ? `Early warning — 10 cm expected in ~${fmt(hh.time_to_threshold_min)} min` : hh.reasons.join(", "), hh }));
  f.flood.roads.filter(r => r.p_exceed["10cm"] >= 0.3).slice(0, 3).forEach(r => al.push({ lvl: "medium", t: `Road ${r.name || r.id}: P(>10 cm) ${pct(r.p_exceed["10cm"])}`, d: `peak ${fmt(r.expected_peak_m * 100)} cm` }));
  D.twin.anomalies.slice(0, 2).forEach(a => al.push({ lvl: a.severity, t: `${a.asset}: ${a.cause}`, d: a.action }));
  $("#alerts").innerHTML = al.map((a, i) => `<div class="item" data-i="${i}"><span class="st ${a.lvl}">${a.lvl.toUpperCase()}</span> <b>${a.t}</b><div class="small muted">${a.d}</div></div>`).join("") || "<span class='muted'>No alerts</span>";
  $("#alerts").querySelectorAll(".item").forEach(el => el.onclick = () => { const a = al[+el.dataset.i]; if (a.hh) { go("prob"); map.fitBounds(hotspotBounds(a.hh), { maxZoom: 18 }); } });
  // rain chart: history bars + forecast fan
  const k0 = K0(), hist = live.rain_mmh.slice(0, k0 + 1);
  const cum = FC().rain_cum_mm, M = cum.length;
  const rate = q => cum[0].map((_, k) => quant(cum.map(m => (m[k] - (k ? m[k - 1] : 0)) * 12), q));
  const labels = [...live.times_min.slice(0, k0 + 1), ...Array.from({ length: 36 }, (_, k) => D.fc.t0_min + 5 * (k + 1))];
  const pad = Array(k0 + 1).fill(null);
  chart("cRain", { data: { labels, datasets: [
    { type: "bar", label: "observed (radar, corrected)", data: [...hist, ...Array(36).fill(null)], backgroundColor: "#3b8bff" },
    { type: "line", label: "forecast P50", data: [...pad, ...rate(0.5)], borderColor: "#a47bff", pointRadius: 0, borderWidth: 2 },
    { type: "line", label: "P90", data: [...pad, ...rate(0.9)], borderColor: "#ef4452", borderDash: [4, 3], pointRadius: 0, borderWidth: 1 },
    { type: "line", label: "P10", data: [...pad, ...rate(0.1)], borderColor: "#8ea3bf", borderDash: [4, 3], pointRadius: 0, borderWidth: 1 }] },
    options: { scales: { x: { ticks: { maxTicksLimit: 8, callback: (v, i) => "T+" + labels[i] } }, y: { title: { display: true, text: "mm/h" } } } } });
  // map: live physics frames up to now + drainage nodes
  const nodeLayer = L.layerGroup().addTo(viewLayer);
  legendDepth("Twin state");
  setSlider({ max: k0, value: k0, label: v => `T+${live.times_min[v]} min${v === k0 ? " · NOW" : ""}`, onChange: v => {
    const d = dec(live.depth_cm[v]); paint(k => depthCol(d[k]));
    const st = domainStats(d), fill = live.node_fill[v];
    const sur = fill.filter(x => x >= 1).length;
    $("#liveKpi").innerHTML = `<div class="kpi"><small>Flooded ≥10 cm</small><b class="${st.flooded > 2000 ? "warn" : "ok"}">${m2(st.flooded)}</b></div>
      <div class="kpi"><small>Max depth</small><b>${st.max} cm</b></div><div class="kpi"><small>Rain now</small><b>${fmt(live.rain_mmh[v], 1)} mm/h</b></div>
      <div class="kpi"><small>Surcharged nodes</small><b class="${sur ? "danger" : "ok"}">${sur}</b></div>`;
    nodeLayer.clearLayers();
    D.net.nodes.forEach((n, i) => L.circleMarker([n.lat, n.lon], { radius: n.kind === "inlet" ? 3 : 5, weight: 1, color: "#08101c",
      fillColor: fill[i] >= 1 ? "#ef4452" : fill[i] > 0.6 ? "#e0a526" : "#2fbf71", fillOpacity: .95 })
      .bindTooltip(`N-${n.id} ${n.kind}<br>fill ${pct(fill[i])} of depth`).addTo(nodeLayer));
  } });
};

VIEWS.forecast = () => {
  const P = $("#panel"), L_ = LEADS();
  P.innerHTML = `
  <div class="card"><h3>Probabilistic depth forecast ${tag("modelled")}</h3>
    <div class="seg" id="layerSeg">${[["expected", "Expected"], ["p10", "P10"], ["p50", "P50"], ["p90", "P90"], ["peak", "Peak"]].map(([k, l]) => `<button data-k="${k}" class="${S.layer === k ? "on" : ""}">${l}</button>`).join("")}</div>
    <div class="kpis" id="fcKpi" style="margin-top:10px"></div>
    <div class="small muted" style="margin-top:8px">${F().flood.members} ensemble members × 14 lead times · surrogate + physics refinement in ${F().flood.adaptive_refinement.tiles} hotspot tiles. Click the map for a location forecast.</div>
  </div>
  <div class="card" id="cellCard"><h3>Location forecast</h3><div class="muted">Click any street / open cell on the map.</div></div>
  <div class="card"><h3>Domain flooded area ${tag("modelled")}</h3><canvas id="cArea" class="chart"></canvas></div>`;
  P.querySelectorAll("#layerSeg button").forEach(b => b.onclick = () => { S.layer = b.dataset.k; VIEWS.forecast(); });
  const fa = F().flood.domain.flooded_area_m2, ks = Object.keys(fa);
  chart("cArea", { type: "line", data: { labels: ks.map(k => "+" + k), datasets: [
    { label: "P90", data: ks.map(k => fa[k].p90), borderColor: "#ef4452", backgroundColor: "rgba(164,123,255,.18)", fill: "+2", pointRadius: 0 },
    { label: "P50", data: ks.map(k => fa[k].p50), borderColor: "#a47bff", pointRadius: 2 },
    { label: "P10", data: ks.map(k => fa[k].p10), borderColor: "#8ea3bf", pointRadius: 0 }] },
    options: { scales: { y: { title: { display: true, text: "m² ≥ 10 cm" } } } } });
  legendDepth(S.layer === "peak" ? "Peak depth (0–180 min)" : "Depth");
  const key = { expected: "expected_cm", p10: "p10_cm", p50: "p50_cm", p90: "p90_cm" }[S.layer];
  setSlider({ show: S.layer !== "peak", max: L_.length - 1, value: S.leadIdx ?? 5, label: v => `+${L_[v]} min (T+${D.fc.t0_min + L_[v]})`, onChange: v => {
    S.leadIdx = v; const d = dec(FC()[key][v]); paint(k => depthCol(d[k]));
    const st = domainStats(d);
    $("#fcKpi").innerHTML = `<div class="kpi"><small>Flooded ≥10 cm</small><b class="warn">${m2(st.flooded)}</b></div><div class="kpi"><small>Max depth</small><b>${st.max} cm</b></div>`;
    if (S.sel) cellPanel(S.sel);
  } });
  if (S.layer === "peak") { const d = dec(FC().peak_cm); paint(k => depthCol(d[k])); $("#fcKpi").innerHTML = `<div class="kpi"><small>Flooded (peak)</small><b class="warn">${m2(domainStats(d).flooded)}</b></div><div class="kpi"><small>Max peak</small><b>${domainStats(d).max} cm</b></div>`; }
  if (S.sel) cellPanel(S.sel);
};

function cellPanel(c) {
  const k = c.k, fc = FC(), L_ = LEADS(), ll = cellLL(c.i, c.j);
  if (!G.wet[k]) { $("#cellCard").innerHTML = "<h3>Location forecast</h3><div class='muted'>Building / outside the modelled domain.</div>"; return; }
  if (S.selMarker) viewLayer.removeLayer(S.selMarker);
  S.selMarker = L.circleMarker(ll, { radius: 7, color: "#fff", weight: 2, fillOpacity: 0 }).addTo(viewLayer);
  const ttt = dec(fc.ttt_min)[k], pk = dec(fc.peak_cm)[k], pkt = dec(fc.peak_time_min)[k];
  const pr = dec(fc.p_reach)[k] / 100, dur = dec(fc.duration_min)[k];
  const pAny = t => { let m = 0; for (const s of fc.exceed[t]) m = Math.max(m, dec(s)[k]); return m / 100; };
  const idx = S.leadIdx ?? 5;
  const series = w => L_.map((_, l) => dec(fc[w][l])[k]);
  const members = (fc.members_cm || []).map(m => L_.map((_, l) => dec(m[l])[k]));
  $("#cellCard").innerHTML = `<h3>Location ${ll[0].toFixed(5)}, ${ll[1].toFixed(5)} ${tag("modelled")}</h3>
    <div class="kpis"><div class="kpi"><small>Depth now</small><b>${dec(fc.depth_now_cm)[k]} cm</b></div>
      <div class="kpi"><small>At +${L_[idx]} min</small><b>${dec(fc.expected_cm[idx])[k]} cm</b><div class="small muted">P10–P90: ${dec(fc.p10_cm[idx])[k]}–${dec(fc.p90_cm[idx])[k]} cm</div></div>
      <div class="kpi"><small>Peak (P90)</small><b>${pk} cm</b><div class="small muted">(${dec(fc.peak_p90_cm)[k]} cm) at ${pkt === 255 ? "–" : "+" + pkt + " min"}</div></div>
      <div class="kpi"><small>Time to 10 cm</small><b class="${ttt < 255 ? "danger" : "ok"}">${ttt < 255 ? "+" + ttt + " min" : "not expected"}</b><div class="small muted">P(reach) ${pct(pr)} · duration ${dur} min</div></div></div>
    <table style="margin-top:8px"><tr><th>P(depth &gt;)</th><th class="num">10 cm</th><th class="num">20 cm</th><th class="num">30 cm</th></tr>
      <tr><td>any time 0–180 min</td><td class="num">${pct(pAny("10"))}</td><td class="num">${pct(pAny("20"))}</td><td class="num">${pct(pAny("30"))}</td></tr></table>
    <canvas id="cCell" class="chart" style="margin-top:8px"></canvas>
    <div class="why" id="why" style="margin-top:10px"></div>`;
  chart("cCell", { type: "line", data: { labels: L_.map(l => "+" + l), datasets: [
    ...members.map((m, i) => ({ label: i ? undefined : "members", data: m, borderColor: "rgba(142,163,191,.35)", borderWidth: 1, pointRadius: 0 })),
    { label: "P90", data: series("p90_cm"), borderColor: "#ef4452", pointRadius: 0, borderDash: [4, 3] },
    { label: "expected", data: series("expected_cm"), borderColor: "#3b8bff", borderWidth: 2.5, pointRadius: 0 },
    { label: "P10", data: series("p10_cm"), borderColor: "#8ea3bf", pointRadius: 0, borderDash: [4, 3] }] },
    options: { plugins: { legend: { labels: { filter: i => i.text } } }, scales: { y: { title: { display: true, text: "cm" } } } } });
  whyPanel(c, ll);
}

function whyPanel(c, ll) {
  // Module W: contributions of rainfall, runoff, terrain, drainage, anomaly and boundary
  const k = c.k, fc = FC();
  const cum = fc.rain_cum_mm.map(m => m[m.length - 1]), rain = quant(cum, 0.5);
  const imp = G.imp[k] / 100, terr = Math.max(G.low[k] ? 0.85 : 0, G.acc[k] / G.accMax);
  const nn = nodeNear(ll[0], ll[1], 80); const fill = nn ? D.net.live.node_fill[K0()][nn.node.id] : 0;
  const anom = D.twin.anomalies.find(a => { const n = D.net.nodes[a.node]; return n && distM(ll[0], ll[1], n.lat, n.lon) < 90; });
  const f = [
    ["Rainfall", Math.min(rain / 60, 1), `${fmt(rain, 1)} mm expected next 3 h (P50)`],
    ["Runoff", imp, `${pct(imp)} impervious surface`],
    ["Terrain", terr, G.low[k] ? "local depression / low point" : `flow accumulation ${pct(G.acc[k] / G.accMax)} of max`],
    ["Drainage", nn ? Math.min(fill, 1) : 0.9, nn ? `nearest node N-${nn.node.id} (${Math.round(nn.d)} m) ${pct(fill)} full${fill >= 1 ? " — surcharging" : ""}` : "no inlet within 80 m"],
    ["Infrastructure", anom ? anom.likelihood : 0.05, anom ? `${anom.asset}: ${anom.cause}` : "no suspected fault nearby"],
    ["Boundary", F().health.rain_source_mode === "radar" ? 0.1 : 0.1, "outfalls discharging freely"]];
  const top = [...f].sort((a, b) => b[1] - a[1])[0];
  $("#why").innerHTML = `<h3 style="font-size:11px;color:var(--mut);letter-spacing:.09em;margin:0 0 4px">WHY? · hotspot diagnosis ${tag("derived")}</h3>
    ${f.map(([n, v, t]) => `<div class="f"><span>${n}</span><div class="bar"><div style="width:${Math.round(v * 100)}%;background:${v > .7 ? "#ef4452" : v > .4 ? "#e0a526" : "#3b8bff"}"></div></div><span class="small muted">${pct(v)}</span></div><div class="small muted" style="margin:-3px 0 4px 118px">${t}</div>`).join("")}
    <div class="small" style="margin-top:6px">Dominant driver: <b>${top[0]}</b></div>`;
}

VIEWS.prob = () => {
  const P = $("#panel"), f = F(), L_ = LEADS();
  P.innerHTML = `
  <div class="card"><h3>Exceedance probability ${tag("modelled")}</h3>
    <div class="seg" id="thrSeg">${["10", "20", "30"].map(t => `<button data-t="${t}" class="${S.thr === t ? "on" : ""}">&gt; ${t} cm</button>`).join("")}</div>
    <div class="kpis" id="pKpi" style="margin-top:10px"></div></div>
  <div class="card"><h3>Hotspots · adaptive fidelity ${tag("modelled")}</h3><div class="list" id="hsList"></div>
    <div class="small muted">Refined with full coupled physics: ${f.flood.adaptive_refinement.tiles} tiles · members ${JSON.stringify(f.flood.adaptive_refinement.representative_members || [])} · mean correction ${fmt((f.flood.adaptive_refinement.mean_abs_correction_m || 0) * 100, 1)} cm · ${fmt(f.flood.adaptive_refinement.physics_runtime_s, 1)} s</div></div>
  <div class="card"><h3>Radar nowcast ensemble ${tag("modelled")}</h3>
    <div class="row"><div class="seg" id="rq"><button data-q="p50" class="${S.radarQ === "p50" ? "on" : ""}">P50</button><button data-q="p90" class="${S.radarQ === "p90" ? "on" : ""}">P90</button></div>
    <div class="seg" id="rl">${FC().radar.leads.map((l, i) => `<button data-i="${i}" class="${S.radarLead === i ? "on" : ""}">+${l}</button>`).join("")}</div></div>
    <canvas id="radar" width="288" height="288" style="width:100%;border-radius:8px;background:#08101c"></canvas>
    <div class="small muted">96 × 96 km around campus (◎) · motion ${fmt(f.rainfall.nowcast.motion_speed_kmh, 0)} km/h · guidance: ${f.rainfall.nowcast.guidance} · blend weights ${Object.entries(f.rainfall.nowcast.blend_weights).map(([k, v]) => "+" + k + ":" + v).join(" ")}</div></div>
  <div class="card"><h3>Campus rainfall ensemble ${tag("modelled")}</h3><canvas id="cEns" class="chart"></canvas></div>`;
  P.querySelectorAll("#thrSeg button").forEach(b => b.onclick = () => { S.thr = b.dataset.t; VIEWS.prob(); });
  P.querySelectorAll("#rq button").forEach(b => b.onclick = () => { S.radarQ = b.dataset.q; VIEWS.prob(); });
  P.querySelectorAll("#rl button").forEach(b => b.onclick = () => { S.radarLead = +b.dataset.i; VIEWS.prob(); });
  drawRadar();
  // hotspots
  const hl = L.layerGroup().addTo(viewLayer);
  $("#hsList").innerHTML = f.flood.hotspots.map((h, i) => {
    const b = hotspotBounds(h);
    L.rectangle(b, { color: h.early_warning ? "#ef4452" : "#e0a526", weight: 2, fill: false, dashArray: "5 4" }).addTo(hl);
    L.marker([b[1][0], b[0][1]], { icon: L.divIcon({ className: "", html: `<span class="hs-label">H${i + 1}</span>` }) }).addTo(hl);
    return `<div class="item" data-i="${i}"><b>H${i + 1}</b> ${h.early_warning ? '<span class="st high">EARLY WARNING</span>' : ""}
      <div class="small">P(&gt;20 cm) ${pct(h.p_exceed_20cm_max)} · spread ${fmt(h.peak_spread_m * 100)} cm · now ${fmt(h.max_depth_now_m * 100)} cm · 10 cm in ${h.time_to_threshold_min != null ? "+" + h.time_to_threshold_min + " min" : "–"}</div>
      <div class="small muted">${h.reasons.join(" · ")}</div></div>`;
  }).join("") || "<span class='muted'>No hotspots</span>";
  $("#hsList").querySelectorAll(".item").forEach(el => el.onclick = () => map.fitBounds(hotspotBounds(f.flood.hotspots[+el.dataset.i]), { maxZoom: 18 }));
  // ensemble chart
  const cum = FC().rain_cum_mm;
  chart("cEns", { type: "line", data: { labels: cum[0].map((_, k) => "+" + 5 * (k + 1)), datasets: cum.map((m, i) => ({
    label: i ? undefined : "member (cumulative mm)", data: m, borderColor: i === 0 ? "#3b8bff" : "rgba(164,123,255,.35)", borderWidth: i === 0 ? 2 : 1, pointRadius: 0 })) },
    options: { plugins: { legend: { labels: { filter: i => i.text } } }, scales: { x: { ticks: { maxTicksLimit: 7 } }, y: { title: { display: true, text: "mm since T+" + D.fc.t0_min } } } } });
  legendProb(S.thr);
  setSlider({ max: L_.length - 1, value: S.leadIdx ?? 5, label: v => `+${L_[v]} min`, onChange: v => {
    S.leadIdx = v; const d = dec(FC().exceed[S.thr][v]); paint(k => probCol(d[k] / 100));
    let a50 = 0, a80 = 0; for (let k = 0; k < G.n; k++) if (G.wet[k]) { if (d[k] >= 50) a50++; if (d[k] >= 80) a80++; }
    $("#pKpi").innerHTML = `<div class="kpi"><small>Area P ≥ 50%</small><b class="warn">${m2(a50 * 25)}</b></div><div class="kpi"><small>Area P ≥ 80%</small><b class="danger">${m2(a80 * 25)}</b></div>`;
  } });
};

function drawRadar() {
  const r = FC().radar, cv = $("#radar"); if (!cv) return;
  const a = dec(r[S.radarQ][S.radarLead]), n = r.n, ctx = cv.getContext("2d"), px = cv.width / n;
  ctx.fillStyle = "#08101c"; ctx.fillRect(0, 0, cv.width, cv.height);
  for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
    const v = a[i * n + j] / 2; if (v < 0.5) continue;
    const t = Math.min(Math.log10(v + 1) / 2, 1);
    ctx.fillStyle = `hsla(${210 - 210 * t},90%,${45 + 15 * t}%,${0.35 + 0.65 * t})`; ctx.fillRect(j * px, i * px, px + .5, px + .5);
  }
  ctx.strokeStyle = "#fff"; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.arc(cv.width / 2, cv.height / 2, 6, 0, 7); ctx.stroke();
  ctx.fillStyle = "#8ea3bf"; ctx.font = "11px Inter"; ctx.fillText(`${S.radarQ.toUpperCase()} rain rate · +${r.leads[S.radarLead]} min`, 8, 16);
}

VIEWS.drain = () => {
  const tw = D.twin, live = D.net.live, P = $("#panel"), h = healthCard();
  const imp = 100 * (1 - tw.rmse.assimilated_m / tw.rmse.open_loop_m);
  P.innerHTML = `
  <div class="card"><h3>TwinSync data assimilation ${tag("modelled")}</h3>
    <div class="kpis"><div class="kpi"><small>Open-loop error</small><b class="warn">${fmt(tw.rmse.open_loop_m * 100, 1)} cm</b></div>
    <div class="kpi"><small>Assimilated error</small><b class="ok">${fmt(tw.rmse.assimilated_m * 100, 1)} cm</b></div></div>
    <div class="small" style="margin-top:6px">Water-level error at sensors reduced by <b>${fmt(imp)}%</b> · update every 5 min</div>
    <div class="row" style="margin-top:8px"><span class="muted small">Sensor</span><select id="sensSel">${tw.sensors.map((s, i) => `<option value="${i}" ${i === S.sensor ? "selected" : ""}>${s.id} (${s.status})</option>`).join("")}</select></div>
    <canvas id="cTwin" class="chart"></canvas></div>
  <div class="card"><h3>Drainage health intelligence ${tag("derived")}</h3><div class="list" id="anoms"></div></div>
  <div class="card"><h3>Evidence fusion · sensor trust ${tag("derived")}</h3>
    <table><tr><th>Sensor</th><th>Status</th><th class="num">Trust</th><th></th></tr>${tw.sensors.map(s => `<tr><td>${s.id}</td><td><span class="st ${s.status}">${s.status}</span></td><td class="num">${fmt(s.trust, 2)}</td><td style="width:40%"><div class="bar"><div style="width:${s.trust * 100}%;background:${s.trust < .3 ? "#ef4452" : "#2fbf71"}"></div></div></td></tr>`).join("")}</table>
    <div class="small muted" style="margin-top:6px">Rejected sensors are excluded; the twin continues with the remaining observations.</div></div>
  <div class="card"><h3>Digital twin state (Module J)</h3><table id="twinState"></table></div>`;
  $("#sensSel").onchange = e => { S.sensor = +e.target.value; twinChart(); };
  twinChart();
  $("#anoms").innerHTML = tw.anomalies.map((a, i) => `<div class="item"><span class="st ${a.severity}">${a.severity.toUpperCase()}</span> <b>${a.asset}</b> · ${a.cause}
    <div class="row" style="margin:6px 0"><span class="small muted">likelihood</span><div class="bar" style="flex:1"><div style="width:${a.likelihood * 100}%;background:#f07b2f"></div></div><b class="small">${pct(a.likelihood)}</b></div>
    <div class="small muted">${a.evidence}${a.estimated_blockage != null ? ` · estimated blockage ${pct(a.estimated_blockage)}` : ""}</div>
    <div class="row" style="margin:6px 0 0"><span class="small">▶ ${a.action}</span><button class="btn sm" data-wo="${i}" ${S.approvals["wo" + i] ? "disabled" : ""}>${S.approvals["wo" + i] ? "Work order raised" : "Raise work order"}</button></div></div>`).join("");
  $("#anoms").querySelectorAll("[data-wo]").forEach(b => b.onclick = () => { const a = tw.anomalies[+b.dataset.wo]; S.approvals["wo" + b.dataset.wo] = 1; audit("work order raised", `${a.asset} — ${a.action}`); toast(`Work order raised for ${a.asset}`); VIEWS.drain(); });
  const q = F().flood.twin_state;
  const rows = [["Surface state", `${m2(q.flooded_area_now_m2)} flooded · max ${fmt(q.max_depth_now_m * 100)} cm`, "physics + assimilation", "±" + fmt(domainSpread() / 2, 0) + " cm"],
    ["Sewer state", `${live.node_fill[K0()].filter(x => x >= 1).length} surcharged / ${D.net.nodes.length} nodes`, "1D engine + sensors", `±${fmt(tw.rmse.assimilated_m * 100, 1)} cm`],
    ["Storage (sump)", `${pct(live.node_fill[K0()][D.net.nodes.findIndex(n => n.kind === "storage")])} full`, "1D engine", "–"],
    ["Pump P-60", "AUTO · available", "SCADA (simulated)", "–"], ["Boundary", "outfalls free discharge", "config", "–"],
    ["Rainfall", `${fmt(quant(FC().rain_cum_mm.map(m => m[11]), 0.5), 1)} mm next 60 min (P50)`, F().health.rain_source_mode, `P10–P90 ${fmt(quant(FC().rain_cum_mm.map(m => m[11]), .1), 1)}–${fmt(quant(FC().rain_cum_mm.map(m => m[11]), .9), 1)} mm`],
    ["Infrastructure", `${tw.anomalies.filter(a => a.cause.startsWith("pipe")).length} suspected obstructions`, "residual analysis", "likelihood-ranked"]];
  $("#twinState").innerHTML = `<tr><th>State</th><th>Estimate</th><th>Source</th><th>Uncertainty</th></tr>` + rows.map(r => `<tr><td class="muted">${r[0]}</td><td>${r[1]}</td><td class="small muted">${r[2]}</td><td class="small">${r[3]}</td></tr>`).join("");
  // map: pipes + nodes + sensors + anomalies
  clearOverlay();
  $("#legend").innerHTML = `Pipe utilisation<span class="sw" style="background:#2fbf71"></span>&lt;60%<span class="sw" style="background:#e0a526"></span>60–100%<span class="sw" style="background:#ef4452"></span>&gt;100% · ◆ sensor · ◯ anomaly`;
  const net = L.layerGroup().addTo(viewLayer), fixed = L.layerGroup().addTo(viewLayer);
  tw.sensors.forEach(s => L.marker([s.lat, s.lon], { icon: L.divIcon({ className: "", html: `<div style="width:12px;height:12px;transform:rotate(45deg);background:${s.status === "FAULT" ? "#ef4452" : "#3b8bff"};border:2px solid #fff"></div>`, iconSize: [12, 12] }) }).bindTooltip(`${s.id} · trust ${s.trust}`).addTo(fixed));
  tw.anomalies.forEach(a => { const n = D.net.nodes[a.node]; L.circleMarker([n.lat, n.lon], { radius: 14, color: "#f07b2f", weight: 2, fillOpacity: 0 }).bindTooltip(`${a.asset}: ${a.cause}`).addTo(fixed); });
  setSlider({ max: live.times_min.length - 1, value: K0(), label: v => `T+${live.times_min[v]} min${v === K0() ? " · NOW" : v > K0() ? " · forecast" : ""}`, onChange: v => {
    net.clearLayers();
    const u = live.pipe_util[v], fill = live.node_fill[v];
    D.net.edges.forEach((e, i) => { const a = D.net.nodes[e.u], b = D.net.nodes[e.v];
      L.polyline([[a.lat, a.lon], [b.lat, b.lon]], { color: u[i] > 1 ? "#ef4452" : u[i] > .6 ? "#e0a526" : "#2fbf71", weight: 2 + 4 * (e.diameter_m || .3), opacity: .9 })
        .bindTooltip(`${e.kind === "pump" ? "Pump" : "Pipe"} P-${e.id} · Ø${e.diameter_m} m · ${pct(u[i])} of capacity`).addTo(net); });
    D.net.nodes.forEach((n, i) => L.circleMarker([n.lat, n.lon], { radius: n.kind === "inlet" ? 2.5 : 4.5, weight: 1, color: "#08101c", fillColor: fill[i] >= 1 ? "#ef4452" : "#9fc4ff", fillOpacity: 1 }).bindTooltip(`N-${n.id} ${n.kind} · ${pct(fill[i])} full`).addTo(net));
  } });
};
function twinChart() {
  const tw = D.twin, i = S.sensor, t = tw.times_min;
  chart("cTwin", { type: "line", data: { labels: t.map(x => "T+" + x), datasets: [
    { label: "observed", data: tw.observed[i], borderColor: "rgba(0,0,0,0)", backgroundColor: "#e0a526", pointRadius: 2, showLine: false },
    { label: "open loop", data: tw.open_loop[i], borderColor: "#8ea3bf", borderDash: [5, 4], pointRadius: 0 },
    { label: "assimilated", data: tw.assimilated[i], borderColor: "#2fbf71", borderWidth: 2.5, pointRadius: 0 }] },
    options: { scales: { x: { ticks: { maxTicksLimit: 7 } }, y: { title: { display: true, text: "node water depth (m)" } } } } });
}

VIEWS.impact = () => {
  const P = $("#panel"), f = F(), L_ = LEADS();
  const opts = D.blocks.map((b, i) => `<option value="${i}">${b.name} block</option>`).join("");
  P.innerHTML = `
  <div class="card"><h3>Dynamic road impact ${tag("modelled")}</h3>
    <div class="row"><span class="muted small">Vehicle</span><select id="veh">${["two-wheeler", "car", "ambulance", "bus", "fire truck"].map(v => `<option ${v === S.vehicle ? "selected" : ""}>${v}</option>`).join("")}</select>
    <span class="small muted">thresholds ${vehicleThr(S.vehicle).map(x => x * 100 + " cm").join(" / ")}</span></div>
    <div class="kpis" id="roadKpi"></div><table id="roadTbl" style="margin-top:8px"></table></div>
  <div class="card"><h3>Flood-aware time-dependent routing ${tag("modelled")}</h3>
    <div class="row"><button class="btn sm ghost" id="pickO">${S.route.origin ? "✓ Origin set" : "Set origin on map"}</button><button class="btn sm ghost" id="pickD">${S.route.dest ? "✓ Destination set" : "Set destination on map"}</button></div>
    <div class="row"><span class="small muted">or</span><select id="fromB"><option value="">from block…</option>${opts}</select><select id="toB"><option value="">to block…</option>${opts}</select></div>
    <div class="row"><span class="small muted">Depart</span><select id="dep">${[0, 15, 30, 60, 90, 120].map(v => `<option value="${v}" ${v === (S.route.dep || 0) ? "selected" : ""}>${v ? "in " + v + " min" : "now"}</option>`).join("")}</select>
    <span class="small muted">Risk tolerance</span><select id="tol">${["low", "medium", "high"].map(v => `<option ${v === (S.route.tol || "low") ? "selected" : ""}>${v}</option>`).join("")}</select>
    <button class="btn sm" id="goRoute">Find 3 routes</button></div>
    <div id="routeOut"></div></div>
  <div class="card"><h3>Critical infrastructure access ${tag("modelled")}</h3><table id="critTbl"></table></div>`;
  $("#veh").onchange = e => { S.vehicle = e.target.value; VIEWS.impact(); };
  $("#pickO").onclick = () => { S.route.picking = "origin"; toast("Click the map to set the origin"); };
  $("#pickD").onclick = () => { S.route.picking = "dest"; toast("Click the map to set the destination"); };
  $("#fromB").onchange = e => { const b = D.blocks[+e.target.value]; if (b) { S.route.origin = nearestWet(b.lat, b.lon); S.route.results = []; go("impact"); } };
  $("#toB").onchange = e => { const b = D.blocks[+e.target.value]; if (b) { S.route.dest = nearestWet(b.lat, b.lon); S.route.results = []; go("impact"); } };
  $("#dep").onchange = e => S.route.dep = +e.target.value;
  $("#tol").onchange = e => S.route.tol = e.target.value;
  $("#goRoute").onclick = () => runRoutes();
  S.route.layer = L.layerGroup().addTo(viewLayer); drawRouteEnds(); renderRoutes();
  const roadsL = L.layerGroup().addTo(viewLayer), rr = roadRows();
  $("#legend").innerHTML = `Road status (${S.vehicle})` + Object.entries(STATUS_COL).map(([k, c]) => `<span class="sw" style="background:${c}"></span>${k}`).join("");
  clearOverlay();
  setSlider({ max: L_.length - 1, value: S.leadIdx ?? 5, label: v => `+${L_[v]} min`, onChange: v => {
    S.leadIdx = v; roadsL.clearLayers();
    const counts = { Passable: 0, Degraded: 0, High: 0, Impassable: 0 }, rows = [];
    D.roads.features.forEach(ft => {
      const p = ft.properties; if (["footway", "steps", "path"].includes(p.highway)) return;
      const r = rr["R-" + p.osm_id]; const dm = r ? r.expected_by_lead_m[v] : 0; const st = roadStatus(dm, S.vehicle);
      if (r) { counts[st]++; rows.push({ r, st, dm }); }
      const closed = S.route.closed.has("R-" + p.osm_id);
      L.geoJSON(ft, { style: { color: closed ? "#a47bff" : r ? STATUS_COL[st] : "#3a4d69", weight: r ? 5 : 2, opacity: r ? .95 : .5, dashArray: closed ? "6 5" : null } })
        .bindPopup(r ? `<b>${p.name || "Campus road"}</b> (${r.id})<br>${st} for ${S.vehicle} · ${fmt(dm * 100)} cm at +${L_[v]} min<br>P(&gt;10/20/30 cm): ${pct(r.p_exceed["10cm"])} / ${pct(r.p_exceed["20cm"])} / ${pct(r.p_exceed["30cm"])}<br>peak ${fmt(r.expected_peak_m * 100)} cm (P90 ${fmt(r.peak_p90_m * 100)}) · flooded ~${r.duration_expected_min} min<br>travel-time factor ×${{ Passable: 1, Degraded: 1.5, High: 2.5, Impassable: "∞" }[st]}` : `${p.name || p.highway} (outside modelled domain)`).addTo(roadsL);
    });
    $("#roadKpi").innerHTML = Object.entries(counts).map(([k, n]) => `<div class="kpi"><small>${k}</small><b style="color:${STATUS_COL[k]}">${n}</b></div>`).join("");
    rows.sort((a, b) => b.dm - a.dm);
    $("#roadTbl").innerHTML = `<tr><th>Segment</th><th>Status</th><th class="num">Depth</th><th class="num">P&gt;10cm</th><th class="num">10 cm in</th></tr>` +
      rows.slice(0, 7).map(({ r, st, dm }) => `<tr><td>${r.name || r.id}</td><td><span class="st ${st}">${st}</span></td><td class="num">${fmt(dm * 100)} cm</td><td class="num">${pct(r.p_exceed["10cm"])}</td><td class="num">${r.time_to_threshold_min != null ? "+" + r.time_to_threshold_min : "–"}</td></tr>`).join("");
  } });
  // critical infrastructure (Module R)
  const ttt = dec(FC().ttt_min), pr = dec(FC().p_reach);
  const crit = D.blocks.map(b => {
    const c = cellOfLL(b.lat, b.lon); let t = 255, p = 0;
    if (c) for (let di = -6; di <= 6; di++) for (let dj = -6; dj <= 6; dj++) {
      const i = c.i + di, j = c.j + dj; if (i < 0 || j < 0 || i >= G.ny || j >= G.nx) continue; const k = i * G.nx + j;
      if (!G.wet[k] || Math.hypot(di, dj) * 5 > 30) continue; t = Math.min(t, ttt[k]); p = Math.max(p, pr[k] / 100);
    }
    return { b, t, p };
  }).sort((a, b) => a.t - b.t);
  $("#critTbl").innerHTML = `<tr><th>Facility</th><th>Access risk</th><th class="num">P(reach 10 cm)</th></tr>` + crit.map(c => `<tr><td>${c.b.name} block <span class="muted small">${c.b.floors}</span></td><td>${c.t < 255 && c.p >= 0.3 ? `<span class="st High">at risk in ${c.t} min</span>` : '<span class="st OK">accessible</span>'}</td><td class="num">${pct(c.p)}</td></tr>`).join("");
  crit.forEach(c => L.circleMarker([c.b.lat, c.b.lon], { radius: 6, color: "#fff", weight: 1.5, fillColor: c.t < 255 && c.p >= .3 ? "#f07b2f" : "#2fbf71", fillOpacity: 1 }).bindTooltip(`${c.b.name} block`).addTo(viewLayer));
};

function nearestWet(lat, lon) {
  const c = cellOfLL(lat, lon); if (!c) return null; let best = null, bd = 1e9;
  for (let di = -10; di <= 10; di++) for (let dj = -10; dj <= 10; dj++) {
    const i = c.i + di, j = c.j + dj; if (i < 0 || j < 0 || i >= G.ny || j >= G.nx) continue; const k = i * G.nx + j;
    if (!G.wet[k]) continue; const d = Math.hypot(di, dj) - (G.road[k] ? 1.5 : 0); if (d < bd) { bd = d; best = { i, j, k }; }
  }
  return best;
}
function drawRouteEnds() {
  if (!S.route.layer) return; S.route.layer.clearLayers();
  for (const [c, col, lab] of [[S.route.origin, "#2fbf71", "A"], [S.route.dest, "#ef4452", "B"]]) if (c)
    L.marker(cellLL(c.i, c.j), { icon: L.divIcon({ className: "", html: `<span class="hs-label" style="background:${col}">${lab}</span>` }) }).addTo(S.route.layer);
  renderRoutes(true);
}
function closedCells() {
  const set = new Set(); if (!S.route.closed.size) return set;
  D.roads.features.forEach(ft => { if (!S.route.closed.has("R-" + ft.properties.osm_id)) return;
    const lines = ft.geometry.type === "LineString" ? [ft.geometry.coordinates] : ft.geometry.coordinates;
    lines.forEach(ln => { for (let s = 0; s < ln.length - 1; s++) for (let t = 0; t <= 20; t++) {
      const lon = ln[s][0] + (ln[s + 1][0] - ln[s][0]) * t / 20, lat = ln[s][1] + (ln[s + 1][1] - ln[s][1]) * t / 20; const c = cellOfLL(lat, lon); if (c) set.add(c.k); } }); });
  return set;
}
function runRoutes() {
  const o = S.route.origin, d = S.route.dest;
  if (!o || !d) return toast("Set an origin and a destination first");
  const [deg, imp] = vehicleThr(S.vehicle), tolP = { low: 0.1, medium: 0.3, high: 0.6 }[S.route.tol || "low"];
  const dep = S.route.dep || 0, L_ = LEADS(), speed = { "two-wheeler": 4, car: 4, ambulance: 5, bus: 3, "fire truck": 3.5 }[S.vehicle]; // m/s on campus roads
  const closed = closedCells(), thrKey = deg >= .25 ? "30" : deg >= .15 ? "20" : "10";
  const exp = L_.map((_, l) => dec(FC().expected_cm[l])), pex = L_.map((_, l) => dec(FC().exceed[thrKey][l])), now = dec(FC().depth_now_cm);
  const atTime = (arr0, arrs, k, tmin) => { if (tmin < L_[0]) return arr0 ? arr0[k] : arrs[0][k]; let l = 0; while (l < L_.length - 1 && L_[l + 1] <= tmin) l++; if (l >= L_.length - 1) return arrs[l][k]; const w = (tmin - L_[l]) / (L_[l + 1] - L_[l]); return arrs[l][k] * (1 - w) + arrs[l + 1][k] * w; };
  const penalty = new Float32Array(G.n).fill(1), results = [];
  for (let r = 0; r < 3; r++) {
    const dist = new Float64Array(G.n).fill(Infinity), tt = new Float64Array(G.n), prev = new Int32Array(G.n).fill(-1), done = new Uint8Array(G.n);
    const heap = [[0, o.k]]; dist[o.k] = 0;
    const push = x => { heap.push(x); let i = heap.length - 1; while (i) { const p = (i - 1) >> 1; if (heap[p][0] <= heap[i][0]) break; [heap[p], heap[i]] = [heap[i], heap[p]]; i = p; } };
    const pop = () => { const top = heap[0], last = heap.pop(); if (heap.length) { heap[0] = last; let i = 0; for (;;) { const l = 2 * i + 1, rr = l + 1; let m = i; if (l < heap.length && heap[l][0] < heap[m][0]) m = l; if (rr < heap.length && heap[rr][0] < heap[m][0]) m = rr; if (m === i) break; [heap[m], heap[i]] = [heap[i], heap[m]]; i = m; } } return top; };
    while (heap.length) {
      const [c, k] = pop(); if (done[k]) continue; done[k] = 1; if (k === d.k) break;
      const i = (k / G.nx) | 0, j = k % G.nx;
      for (let di = -1; di <= 1; di++) for (let dj = -1; dj <= 1; dj++) {
        if (!di && !dj) continue; const ni = i + di, nj = j + dj; if (ni < 0 || nj < 0 || ni >= G.ny || nj >= G.nx) continue;
        const nk = ni * G.nx + nj; if (!G.wet[nk] || done[nk] || closed.has(nk)) continue;
        const len = 5 * Math.hypot(di, dj), v = G.road[nk] ? speed : speed * 0.35, dt = len / v;
        const tArr = dep + (tt[k] + dt) / 60, dm = atTime(null, exp, nk, tArr) / 100, pe = atTime(null, pex, nk, tArr) / 100;
        if (dm >= imp || (pe > tolP && dm >= deg)) continue;                         // impassable at predicted arrival time
        const cost = dt * (1 + 3 * dm / deg + 4 * pe) * penalty[nk];
        if (c + cost < dist[nk]) { dist[nk] = c + cost; tt[nk] = tt[k] + dt; prev[nk] = k; push([dist[nk], nk]); }
      }
    }
    if (!isFinite(dist[d.k])) break;
    const path = []; for (let k = d.k; k !== -1; k = prev[k]) path.push(k); path.reverse();
    let maxD = 0, maxP = 0, len = 0;
    path.forEach((k, n) => { const tmin = dep + tt[k] / 60; maxD = Math.max(maxD, atTime(null, exp, k, tmin)); maxP = Math.max(maxP, atTime(null, pex, k, tmin) / 100); penalty[k] *= 2.2;
      if (n) { const a = path[n - 1]; len += 5 * Math.hypot(((k / G.nx) | 0) - ((a / G.nx) | 0), k % G.nx - a % G.nx); } });
    if (results.some(x => x.path.length === path.length && x.path.every((v, q) => v === path[q]))) continue;
    results.push({ path, eta: tt[d.k] / 60, len, maxD, maxP, thrKey });
  }
  S.route.results = results;
  audit("route computed", `${S.vehicle}, depart +${dep} min, ${results.length} alternatives`);
  renderRoutes();
}
function renderRoutes(silent) {
  const out = $("#routeOut"); if (!out) return;
  if (!silent && S.route.layer) S.route.layer.eachLayer(l => { if (l instanceof L.Polyline) S.route.layer.removeLayer(l); });
  const cols = ["#3b8bff", "#a47bff", "#e0a526"];
  if (!S.route.results.length) { out.innerHTML = `<div class="small muted">Routes avoid cells predicted impassable for the chosen vehicle at the moment you would reach them.</div>`; return; }
  S.route.results.forEach((r, i) => L.polyline(r.path.map(k => cellLL((k / G.nx) | 0, k % G.nx)), { color: cols[i], weight: 6 - i, opacity: .9 }).addTo(S.route.layer));
  out.innerHTML = `<table><tr><th>Route</th><th class="num">ETA</th><th class="num">Length</th><th class="num">Max depth</th><th class="num">P(&gt;${S.route.results[0].thrKey} cm)</th></tr>` +
    S.route.results.map((r, i) => `<tr><td><span class="sw" style="display:inline-block;width:10px;height:10px;border-radius:3px;background:${cols[i]}"></span> ${["Lowest risk", "Alternative", "Alternative"][i]}</td><td class="num">${fmt(r.eta, 1)} min</td><td class="num">${Math.round(r.len)} m</td><td class="num">${fmt(r.maxD)} cm</td><td class="num">${pct(r.maxP)}</td></tr>`).join("") +
    `</table><div class="row" style="margin-top:6px"><button class="btn sm ghost" id="expRoute">Export GeoJSON</button><span class="small muted">Risk is probabilistic — no route is guaranteed safe.</span></div>`;
  $("#expRoute").onclick = () => { download("routes.geojson", JSON.stringify({ type: "FeatureCollection", features: S.route.results.map((r, i) => ({ type: "Feature", properties: { rank: i + 1, eta_min: +r.eta.toFixed(1), length_m: Math.round(r.len), max_depth_cm: +r.maxD.toFixed(0), p_exceed: +r.maxP.toFixed(2), vehicle: S.vehicle }, geometry: { type: "LineString", coordinates: r.path.map(k => { const ll = cellLL((k / G.nx) | 0, k % G.nx); return [+ll[1].toFixed(6), +ll[0].toFixed(6)]; }) } })) }, null, 1)); audit("export", "routes.geojson"); };
}
function download(name, text, type = "application/json") { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([text], { type })); a.download = name; a.click(); }

const SCEN = [["baseline", "Baseline — forecast storm, nominal network"], ["rain_plus20", "Rainfall +20%"], ["capacity_minus50", "Drain capacity −50% (all pipes)"],
  ["pump_failure", "Pump P-60 fails"], ["downstream_plus20", "River / nala level +2.0 m at outfalls"]];
const ACTIONS = [["state_blocked40", "Do nothing (drains 40% blocked)", 0, 0], ["act_pump_on", "Run pump P-60 continuously", 6000, 5], ["act_clear", "Emergency drain clearance (jetting crews)", 45000, 90], ["act_clear_pump", "Drain clearance + pump", 51000, 90]];
VIEWS.actions = () => {
  const P = $("#panel"), sc = D.scen.scenarios, base = sc.baseline;
  const row = (k, lab) => { const s = sc[k]; const d = s.flooded_m2 - base.flooded_m2;
    return `<div class="item ${S.scen === k ? "on" : ""}" data-k="${k}" style="${S.scen === k ? "border-color:var(--blue)" : ""}"><b>${lab}</b>
      <div class="small">flooded ${m2(s.flooded_m2)} ${k !== "baseline" ? `<b style="color:${d > 0 ? "#ef4452" : "#2fbf71"}">(${d >= 0 ? "+" : ""}${m2(d)})</b>` : ""} · &gt;30 cm ${m2(s.severe_m2)} · peak ${fmt(s.peak_depth_m * 100)} cm · surcharged ${s.surcharged_nodes} · overflow ${fmt(s.overflow_m3)} m³</div></div>`; };
  const bad = sc.state_blocked40;
  const acts = ACTIONS.map(([k, lab, cost, mins]) => { const s = sc[k]; const benefit = bad.flooded_m2 - s.flooded_m2; return { k, lab, cost, mins, s, benefit, sur: s.surcharged_nodes, score: (benefit + 200 * (bad.surcharged_nodes - s.surcharged_nodes)) / (1 + cost / 10000) }; });
  const ranked = [...acts].slice(1).sort((a, b) => b.score - a.score);
  P.innerHTML = `
  <div class="card"><h3>What-if simulation · coupled physics ${tag("modelled")}</h3><div class="list" id="scList">${SCEN.map(([k, l]) => row(k, l)).join("")}</div>
    <label class="toggle small"><input type="checkbox" id="diffT" ${S.scenDiff ? "checked" : ""}/> show change vs baseline</label>
    <div class="row" style="margin-top:8px"><span class="small muted">Close a road for routing:</span><select id="closeR"><option value="">choose segment…</option>${F().flood.roads.map(r => `<option value="${r.id}">${r.name || r.id}${S.route.closed.has(r.id) ? " (closed)" : ""}</option>`).join("")}</select></div></div>
  <div class="card"><h3>Action impact optimizer ${tag("modelled")}</h3>
    <div class="small muted" style="margin-bottom:6px">Current twin state: suspected drain blockage ~40% (Drainage health). Candidate interventions evaluated with full physics:</div>
    <table><tr><th>Action</th><th class="num">Δ flooded</th><th class="num">Surch.</th><th class="num">Cost ₹</th><th class="num">Lead</th></tr>
    ${acts.map(a => `<tr><td>${a.lab}</td><td class="num" style="color:${a.benefit > 0 ? "#2fbf71" : "inherit"}">${a.benefit ? "−" + m2(a.benefit) : "0"}</td><td class="num">${a.sur}</td><td class="num">${a.cost.toLocaleString()}</td><td class="num">${a.mins} min</td></tr>`).join("")}</table>
    <div style="margin-top:8px" class="small">Recommended: <b>${ranked[0].lab}</b> — reduces flooded area by ${m2(ranked[0].benefit)} and surcharged nodes ${bad.surcharged_nodes}→${ranked[0].sur}.</div>
    <div class="row" style="margin-top:8px"><button class="btn sm" id="approve" ${S.approvals.action ? "disabled" : ""}>${S.approvals.action ? "Approved · dispatched" : "Request approval"}</button><span class="small muted">Recommendation only — every action needs human approval.</span></div></div>
  <div class="card"><h3>Sensor placement advisor ${tag("derived")}</h3><table id="sensRec"></table></div>`;
  P.querySelectorAll("#scList .item").forEach(el => el.onclick = () => { S.scen = el.dataset.k; audit("what-if viewed", el.dataset.k); VIEWS.actions(); });
  $("#diffT").onchange = e => { S.scenDiff = e.target.checked; VIEWS.actions(); };
  $("#closeR").onchange = e => { const id = e.target.value; if (!id) return; S.route.closed.has(id) ? S.route.closed.delete(id) : S.route.closed.add(id); audit("road closure toggled", id); toast(`${id} ${S.route.closed.has(id) ? "closed" : "reopened"} — routing will avoid it`); VIEWS.actions(); };
  $("#approve").onclick = () => { if (!confirmRole(["Flood Control Operator", "System Administrator", "Infrastructure Engineer"])) return; S.approvals.action = 1; audit("action approved", ranked[0].lab); toast(`Approved: ${ranked[0].lab}`); VIEWS.actions(); };
  // sensor placement: greedy on forecast uncertainty around candidate nodes
  const spreadMap = (() => { const a = dec(FC().peak_p90_cm), b = dec(FC().peak_cm); return k => Math.max(a[k] - b[k], 0); })();
  const have = D.twin.sensors.map(s => [s.lat, s.lon]);
  const cand = D.net.nodes.filter(n => n.kind !== "outfall" && !D.twin.sensors.some(s => s.node === n.id)).map(n => {
    const c = cellOfLL(n.lat, n.lon); let u = 0; if (c) for (let di = -4; di <= 4; di++) for (let dj = -4; dj <= 4; dj++) { const i = c.i + di, j = c.j + dj; if (i >= 0 && j >= 0 && i < G.ny && j < G.nx && G.wet[i * G.nx + j]) u += spreadMap(i * G.nx + j) + 2 * D.net.live.node_fill[K0()][n.id]; }
    return { n, u };
  });
  const picks = [], tot = cand.reduce((a, c) => a + c.u, 0) || 1;
  for (let r = 0; r < 3; r++) {
    let best = null; for (const c of cand) { if (picks.includes(c)) continue; const near = [...have, ...picks.map(p => [p.n.lat, p.n.lon])].some(([a, b]) => distM(a, b, c.n.lat, c.n.lon) < 60); const g = c.u * (near ? .35 : 1); if (!best || g > best.g) best = { ...c, g, c }; }
    if (best) picks.push(best.c), best.c.gain = best.g;
  }
  $("#sensRec").innerHTML = `<tr><th>Rank</th><th>Location</th><th class="num">Uncertainty reduction</th></tr>` + picks.map((p, i) => `<tr><td>${i + 1}</td><td>N-${p.n.id} ${p.n.kind}</td><td class="num">${fmt(100 * p.gain / tot * 3, 0)}%</td></tr>`).join("");
  picks.forEach((p, i) => L.marker([p.n.lat, p.n.lon], { icon: L.divIcon({ className: "", html: `<span class="hs-label" style="background:#3b8bff">S${i + 1}</span>` }) }).bindTooltip("Recommended new water-level sensor").addTo(viewLayer));
  // map
  const s = sc[S.scen];
  $("#timebar").classList.add("hidden");
  if (S.scenDiff) { const a = dec(s.max_depth_cm), b = dec(base.max_depth_cm); paint(k => diffCol(a[k] - b[k])); $("#legend").innerHTML = `Change in max depth<span class="sw" style="background:#ef4452"></span>deeper<span class="sw" style="background:#2fbf71"></span>shallower`; }
  else { const a = dec(s.max_depth_cm); paint(k => depthCol(a[k])); legendDepth("Max depth (" + S.scen.replace(/_/g, " ") + ")"); }
};
function confirmRole(allowed) { if (allowed.includes(S.role)) return true; toast(`${S.role} cannot approve actions`); audit("approval denied", S.role); return false; }

VIEWS.valid = () => {
  const P = $("#panel"), v = D.val.verification, sm = D.val.surrogate, b = D.scen.baselines, tw = D.twin;
  const fl = Object.fromEntries(v.flood.map(r => [r.lead_min, r]));
  P.innerHTML = `
  <div class="card"><h3>Baseline experiments (SRS §7) ${tag("modelled")}</h3>
    <table><tr><th>Model</th><th class="num">CSI</th><th class="num">Precision</th><th class="num">Recall</th><th class="num">MAE cm</th></tr>
    ${[["B1", "Rainfall threshold"], ["B2", "Rain + DEM"], ["B3", "+ runoff"], ["B4", "+ 1D drainage"], ["B5", "Full coupled 1D/2D"]].map(([k, n]) => `<tr><td><b>${k}</b> ${n}</td><td class="num">${fmt(b[k].csi, 2)}</td><td class="num">${fmt(b[k].precision, 2)}</td><td class="num">${fmt(b[k].recall, 2)}</td><td class="num">${fmt(b[k].depth_mae_m * 100, 1)}</td></tr>`).join("")}
    <tr><td><b>B6</b> + data assimilation</td><td colspan="4" class="small">sensor-level error ${fmt(tw.rmse.open_loop_m * 100, 1)} → ${fmt(tw.rmse.assimilated_m * 100, 1)} cm</td></tr>
    <tr><td><b>B7</b> + adaptive forecasting</td><td colspan="4" class="small">flood CSI(10 cm) ${fmt(fl[60]?.csi_10cm, 2)} at +60 min · ${fmt(fl[180]?.csi_10cm, 2)} at +180 min</td></tr></table>
    <div class="small muted" style="margin-top:6px">B1–B4 scored against B5 on the same storm.</div></div>
  <div class="card"><h3>Surrogate skill vs persistence ${tag("modelled")}</h3><canvas id="cSur" class="chart"></canvas>
    <div class="small muted">${sm.arch} · ${sm.params.toLocaleString()} parameters · ${sm.training.train_windows.toLocaleString()} training windows · held-out test + out-of-distribution scenarios</div></div>
  <div class="card"><h3>Forecast verification · replay T+${v.t0} ${tag("modelled")}</h3>
    <table><tr><th>Lead</th><th class="num">Rain CSI</th><th class="num">Persist.</th><th class="num">Flood CSI</th><th class="num">Brier</th><th class="num">P10–90 cover</th></tr>
    ${v.rain.map(r => { const f = fl[r.lead_min] || {}; return `<tr><td>+${r.lead_min}</td><td class="num">${fmt(r.csi_1mmh, 2)}</td><td class="num">${fmt(r.csi_1mmh_persistence, 2)}</td><td class="num">${fmt(f.csi_10cm, 2)}</td><td class="num">${fmt(f.brier_10cm, 3)}</td><td class="num">${pct(f.p10_p90_coverage)}</td></tr>`; }).join("")}</table>
    <div class="kpis" style="margin-top:8px"><div class="kpi"><small>Hotspot hit rate</small><b class="ok">${pct(v.early_warning.hit_rate)}</b></div><div class="kpi"><small>False alarm ratio</small><b>${pct(v.early_warning.false_alarm_ratio)}</b></div>
    <div class="kpi"><small>Median warning lead</small><b>${fmt(v.early_warning.median_warning_lead_min)} min</b></div><div class="kpi"><small>Cells verified</small><b>${v.early_warning.cells_crossing_after_t0}</b></div></div>
    <div class="small muted" style="margin-top:6px">Replay event: ${v.event.kind} (seed ${v.event.seed}), steering ${v.event.steering_kmh.join(", ")} km/h · scored against the synthetic reference run.</div></div>
  <div class="card"><h3>Provenance (run record)</h3><pre>${JSON.stringify(F().provenance, (k, x) => k === "terrain" ? undefined : x, 1)}</pre>
    <button class="btn sm ghost" id="dlProv">Download run record</button></div>`;
  $("#dlProv").onclick = () => { download(`${F().forecast_id}_provenance.json`, JSON.stringify(F().provenance, null, 1)); audit("export", "provenance"); };
  const t = sm.metrics.test, o = sm.metrics.ood;
  chart("cSur", { type: "line", data: { labels: t.lead_min.map(l => "+" + l), datasets: [
    { label: "CSI test", data: t.csi_10cm, borderColor: "#2fbf71", pointRadius: 0, yAxisID: "y" }, { label: "CSI OOD", data: o.csi_10cm, borderColor: "#3b8bff", pointRadius: 0, yAxisID: "y" },
    { label: "CSI persistence", data: t.csi_10cm_persistence, borderColor: "#8ea3bf", borderDash: [4, 3], pointRadius: 0, yAxisID: "y" }] },
    options: { scales: { y: { min: 0, max: 1, title: { display: true, text: "CSI (10 cm)" } } } } });
  clearOverlay(); $("#timebar").classList.add("hidden"); $("#legend").innerHTML = "Validation";
  const d = dec(FC().p90_cm[LEADS().length - 1]); paint(k => depthCol(d[k])); legendDepth("P90 depth at +180 min");
};

const API = [
  ["GET", "/api/v1/observations/status", () => F().quality], ["GET", "/api/v1/rainfall/forecast", () => F().rainfall],
  ["GET", "/api/v1/twin/state", () => F().flood.twin_state], ["GET", "/api/v1/twin/health", () => healthCard()],
  ["GET", "/api/v1/flood/forecast", () => ({ issued_t_min: F().issued_t_min, lead_min: F().flood.lead_min, domain: F().flood.domain, exceedance_area_m2: F().flood.exceedance_area_m2 })],
  ["GET", "/api/v1/flood/hotspots", () => F().flood.hotspots], ["GET", "/api/v1/roads/impact", () => F().flood.roads.slice(0, 5)],
  ["GET", "/api/v1/drainage/anomalies", () => D.twin.anomalies], ["POST", "/api/v1/routing/time-dependent", () => S.route.results.map(r => ({ eta_min: r.eta, length_m: r.len, max_depth_cm: r.maxD, p_exceed: r.maxP })) ],
  ["POST", "/api/v1/scenarios/simulate", () => Object.fromEntries(Object.entries(D.scen.scenarios).map(([k, s]) => [k, { flooded_m2: s.flooded_m2, peak_depth_m: s.peak_depth_m, surcharged_nodes: s.surcharged_nodes }]))],
  ["GET", "/api/v1/validation/metrics", () => ({ early_warning: D.val.verification.early_warning, rain: D.val.verification.rain })]];
const ROLES = { "System Administrator": "live forecast prob drain impact actions valid system", "Flood Control Operator": "live forecast prob drain impact actions valid system",
  "Emergency Dispatcher": "live forecast prob impact", "Model Engineer": "live forecast prob drain valid system", "Infrastructure Engineer": "live drain actions valid", "Public Viewer": "live forecast impact" };
VIEWS.system = () => {
  const P = $("#panel"), f = F();
  P.innerHTML = `
  <div class="card"><h3>Processing loop · every 5 min</h3>
    <table>${Object.entries(f.timings_s).filter(([k]) => k !== "total").map(([k, v], i, a) => `<tr><td>${i + 1}. ${{ ingest_qc: "Ingest + quality control", mode_bias: "Source selection + gauge bias", nowcast: "Ensemble rainfall nowcast", twin_state: "Twin state update", surrogate: "Surrogate flood ensemble", adaptive_roads: "Hotspot physics + road impact" }[k] || k}</td><td class="num">${fmt(v - (i ? a[i - 1][1] : 0), 1)} s</td></tr>`).join("")}
    <tr><td><b>Total cycle</b></td><td class="num"><b>${fmt(f.timings_s.total, 1)} s</b></td></tr></table></div>
  <div class="card"><h3>API explorer</h3><div class="list" id="apiList">${API.map(([m, p], i) => `<div class="item" data-i="${i}"><span class="st ${m === "GET" ? "VALID" : "SUSPECT"}">${m}</span> <code>${p}</code></div>`).join("")}</div><pre id="apiOut">Select an endpoint to preview its response.</pre></div>
  <div class="card"><h3>Alerts &amp; interoperability</h3><div class="row">
    <button class="btn sm" id="cap">CAP 1.2 alert (XML)</button><button class="btn sm ghost" id="geo">Road impact GeoJSON</button><button class="btn sm ghost" id="sta">SensorThings observations</button></div><pre id="capOut" class="hidden"></pre></div>
  <div class="card"><h3>Access control (RBAC)</h3><table><tr><th>Role</th><th>Views</th></tr>${Object.entries(ROLES).map(([r, v]) => `<tr><td>${r}${r === S.role ? " ●" : ""}</td><td class="small muted">${v.split(" ").map(x => ({ live: "A", forecast: "B", prob: "C", drain: "D", impact: "E", actions: "F", valid: "G", system: "H" })[x]).join(" ")}</td></tr>`).join("")}</table></div>
  <div class="card"><h3>Audit log</h3><table>${S.audit.slice(0, 14).map(a => `<tr><td class="small muted">${a.t}</td><td class="small">${a.role}</td><td class="small">${a.action}<br><span class="muted">${a.detail}</span></td></tr>`).join("") || "<tr><td class='muted'>No events yet</td></tr>"}</table></div>`;
  $("#apiList").querySelectorAll(".item").forEach(el => el.onclick = () => { const [m, p, fn] = API[+el.dataset.i]; $("#apiOut").textContent = `${m} ${p}\n200 OK\n\n` + JSON.stringify(fn(), null, 1); audit("api call", p); });
  $("#cap").onclick = () => { const x = capXml(); $("#capOut").textContent = x; $("#capOut").classList.remove("hidden"); download("drishti_alert.cap.xml", x, "application/xml"); audit("CAP alert exported", f.forecast_id); };
  $("#geo").onclick = () => { const rr = roadRows(); download("road_impact.geojson", JSON.stringify({ type: "FeatureCollection", features: D.roads.features.filter(ft => rr["R-" + ft.properties.osm_id]).map(ft => { const r = rr["R-" + ft.properties.osm_id]; return { type: "Feature", geometry: ft.geometry, properties: { id: r.id, name: r.name, expected_peak_m: r.expected_peak_m, p_exceed: r.p_exceed, time_to_threshold_min: r.time_to_threshold_min, status_car: roadStatus(r.expected_peak_m, "car") } }; }) })); audit("export", "road_impact.geojson"); };
  $("#sta").onclick = () => { const tw = D.twin; $("#capOut").textContent = JSON.stringify({ "@iot.id": "Datastream/water-level", value: tw.sensors.map((s, i) => ({ Thing: s.id, phenomenonTime: `T+${D.fc.t0_min}`, result: tw.observed[i][K0()], resultQuality: s.status, unitOfMeasurement: "m" })) }, null, 1); $("#capOut").classList.remove("hidden"); };
  clearOverlay(); $("#timebar").classList.add("hidden"); $("#legend").innerHTML = "System";
};
function capXml() {
  const f = F(), hs = f.flood.hotspots, now = new Date().toISOString().replace(/\.\d+Z/, "+00:00");
  const area = hs.map((h, i) => { const b = hotspotBounds(h); return `  <area><areaDesc>Hotspot H${i + 1} (P&gt;20cm ${pct(h.p_exceed_20cm_max)})</areaDesc><polygon>${b[0][0].toFixed(5)},${b[0][1].toFixed(5)} ${b[0][0].toFixed(5)},${b[1][1].toFixed(5)} ${b[1][0].toFixed(5)},${b[1][1].toFixed(5)} ${b[1][0].toFixed(5)},${b[0][1].toFixed(5)} ${b[0][0].toFixed(5)},${b[0][1].toFixed(5)}</polygon></area>`; }).join("\n");
  return `<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
 <identifier>drishti-${f.forecast_id}</identifier><sender>drishti@kiet.edu</sender><sent>${now}</sent>
 <status>Exercise</status><msgType>Alert</msgType><scope>Restricted</scope>
 <info><category>Met</category><event>Urban waterlogging</event><urgency>Expected</urgency><severity>Moderate</severity><certainty>Likely</certainty>
  <headline>Street flooding expected on KIET campus within ${Math.min(...hs.map(h => h.time_to_threshold_min ?? 999))} min</headline>
  <description>${hs.length} hotspots. Forecast health ${f.health.status}. Probabilities are ensemble-based.</description>
  <instruction>Avoid flagged roads; use the lowest-risk routes in the Drishti planner.</instruction>
${area}
 </info>
</alert>`;
}

// ------------------------------------------------------------------ shell
function go(view) {
  if (!ROLES[S.role].split(" ").includes(view)) { toast(`${S.role} has no access to this view`); return; }
  S.view = view; stopPlay();
  document.querySelectorAll("#nav button").forEach(b => b.classList.toggle("on", b.dataset.view === view));
  viewLayer.clearLayers(); S.selMarker = null; if (S.route) S.route.layer = null;
  Object.values(S.charts).forEach(c => c.destroy()); S.charts = {};
  $("#timebar").classList.remove("hidden");
  VIEWS[view]();
}
function refreshHeader() {
  const h = F().health;
  const p = $("#healthPill"); p.className = "pill " + (h.status === "OPERATIONAL" ? "ok" : "bad");
  p.textContent = `${h.status} · rain: ${h.rain_source_mode}`;
  const bn = $("#banner"); bn.classList.toggle("hidden", !h.degraded);
  bn.innerHTML = h.degraded ? `⚠ DEGRADED FORECAST — ${h.reasons.join(" · ")} · uncertainty ×${h.uncertainty_inflation}` : "";
  $("#clock").textContent = `T+${D.fc.t0_min} min`;
  document.querySelectorAll("#nav button").forEach(b => b.classList.toggle("locked", !ROLES[S.role].split(" ").includes(b.dataset.view)));
}
async function init() {
  map = L.map("map", { zoomControl: true, preferCanvas: true }).setView([28.7523, 77.4985], 17);
  baseLayer = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", { maxZoom: 20, maxNativeZoom: 19, attribution: "Imagery © Esri" }).addTo(map);
  L.rectangle([[28.70, 77.40], [28.80, 77.60]], { stroke: false, fillColor: "#07101c", fillOpacity: .45, interactive: false }).addTo(map);
  try { await load(); } catch (e) { $("#panel").innerHTML = `<div class="card">Could not load the data bundle (${e.message}). Serve the repository root: <code>python -m http.server</code> and open /dashboard/.</div>`; return; }
  overlay = L.imageOverlay("data:image/gif;base64,R0lGODlhAQABAAAAACw=", [[G.s, G.w], [G.nn, G.e]], { opacity: 0, interactive: false }).addTo(map);
  L.geoJSON({ type: "FeatureCollection", features: D.bnd.features.slice(0, 1) }, { style: { color: "#9fc4ff", weight: 1.5, fill: false, dashArray: "4 4" } }).addTo(map);
  L.geoJSON(D.bld, { filter: ft => ft.geometry.type !== "Point" && String(ft.properties.kind || "building").includes("building"), style: { color: "#44597a", weight: 1, fillColor: "#23344e", fillOpacity: .8 } }).addTo(map);
  viewLayer = L.layerGroup().addTo(map);
  map.fitBounds([[G.s, G.w], [G.nn, G.e]]);
  map.on("click", e => {
    const c = llCell(e.latlng);
    if (S.view === "impact" && S.route.picking) { const w = nearestWet(e.latlng.lat, e.latlng.lng); if (!w) return; S.route[S.route.picking === "origin" ? "origin" : "dest"] = w; S.route.picking = null; go("impact"); return; }
    if (!c) return;
    if (S.view === "forecast") { S.sel = c; cellPanel(c); }
    else if (S.view === "live" || S.view === "prob") { S.sel = c; go("forecast"); cellPanel(c); }
  });
  document.querySelectorAll("#nav button").forEach(b => b.onclick = () => go(b.dataset.view));
  $("#degradeToggle").onchange = e => { S.mode = e.target.checked ? "degraded" : "ok"; audit(e.target.checked ? "radar outage drill started" : "radar outage drill ended"); refreshHeader(); go(S.view); };
  $("#role").onchange = e => { S.role = e.target.value; audit("role switched", S.role); refreshHeader(); if (!ROLES[S.role].split(" ").includes(S.view)) go("live"); else go(S.view); };
  audit("session started", "forecast " + F().forecast_id);
  refreshHeader(); go("live");
}
init();
