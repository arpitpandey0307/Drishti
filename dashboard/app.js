/* Drishti operations dashboard — every view runs on the exported model bundle (dashboard/data). */
"use strict";
const $ = (s, r = document) => r.querySelector(s);
const fmt = (v, d = 0) => (v == null || !isFinite(v)) ? "–" : Number(v).toFixed(d);
const pct = v => (v == null || !isFinite(v)) ? "–" : Math.round(v * 100) + "%";
const m2 = v => v >= 10000 ? (v / 10000).toFixed(2) + " ha" : Math.round(v).toLocaleString() + " m²";
const COL = { teal: "#2ec4d6", deep: "#1e6fd9", orange: "#ff7a1a", amber: "#f2b84b", red: "#e5484d", green: "#3fb68b", paper: "#e9e4d8", mut: "#8a949c", rule: "#23313c", ink: "#0b1117" };
const S = { view: "live", mode: "ok", role: "Flood Control Operator", audit: [], charts: {}, sel: null, play: null, w3d: true, sat: true,
  route: { origin: null, dest: null, picking: null, results: [], closed: new Set() }, approvals: {}, scen: "baseline",
  scenDiff: false, thr: "10", layer: "expected", radarQ: "p50", radarLead: 2, vehicle: "car", sensor: 0, emergency: false };
let D = {}, G = {}, map;
const VIEW_META = { live: ["A", "Situation", "twin state up to now"], forecast: ["B", "Forecast", "0–180 min depth ensemble"], prob: ["C", "Hotspots", "exceedance probability"],
  drain: ["D", "Drainage", "network health + assimilation"], impact: ["E", "Roads & routes", "impact + time-dependent routing"], actions: ["F", "Action lab", "what-if physics + interventions"],
  valid: ["G", "Validation", "skill against the reference run"], system: ["H", "System", "loop · API · alerts · access"] };

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
  const [grid, net, idx, twin, scen, val, roads, blocks, bnd, bld] = await Promise.all([
    j("data/grid.json"), j("data/network.json"), j("data/forecast_index.json"), j("data/twin.json"),
    j("data/scenarios.json"), j("data/validation.json"), j("../data/roads.geojson"),
    t("../data/blocks_centroids.csv"), j("../kiet_terrain/campus_osm.geojson"), j("../data/campus_accurate.geojson")]);
  D = { grid, net, idx, twin, scen, val, roads, bnd, bld, cycles: {} };
  await loadCycle(idx.default);
  D.blocks = blocks.trim().split(/\r?\n/).slice(1).map(l => { const c = l.split(","); return { name: c[0], lat: +c[1], lon: +c[2], floors: c[3] }; });
  G = { ny: grid.ny, nx: grid.nx, n: grid.ny * grid.nx, s: grid.bounds[0][0], w: grid.bounds[0][1], nn: grid.bounds[1][0], e: grid.bounds[1][1], off: grid.crop_offset || [11, 28] };
  G.dlat = (G.nn - G.s) / G.ny; G.dlon = (G.e - G.w) / G.nx;
  G.dom = dec(grid.domain); G.bld = dec(grid.building); G.road = dec(grid.road); G.low = dec(grid.low_points);
  G.imp = dec(grid.imperv); G.acc = dec(grid.accum_log);
  G.wet = new Uint8Array(G.n); for (let k = 0; k < G.n; k++) G.wet[k] = G.dom[k] && !G.bld[k] ? 1 : 0;
  let amax = 0; for (let k = 0; k < G.n; k++) if (G.wet[k]) amax = Math.max(amax, G.acc[k]); G.accMax = amax;
}
async function loadCycle(t0) {
  if (!D.cycles[t0]) D.cycles[t0] = await fetch(`data/forecast_${t0}.json`).then(r => r.json());
  D.fc = D.cycles[t0];
}
const FC = () => D.fc[S.mode];
const F = () => FC().forecast;
const LEADS = () => FC().lead_min;
const K0 = () => Math.round(D.fc.t0_min / 5) - 1;
const cellLL = (i, j) => [G.nn - (i + 0.5) * G.dlat, G.w + (j + 0.5) * G.dlon];
function llCell(ll) {
  const i = Math.floor((G.nn - ll.lat) / G.dlat), j = Math.floor((ll.lng - G.w) / G.dlon);
  return (i < 0 || j < 0 || i >= G.ny || j >= G.nx) ? null : { i, j, k: i * G.nx + j };
}
const cellOfLL = (lat, lon) => llCell({ lat, lng: lon });

// ------------------------------------------------------------------ colour ramps
const DEPTH_RAMP = [[3, [189, 235, 242]], [10, [46, 196, 214]], [20, [30, 111, 217]], [30, [242, 184, 75]], [60, [229, 72, 77]]];
function depthRGB(cm) {
  if (cm < 3) return null;
  for (let i = 1; i < DEPTH_RAMP.length; i++) if (cm < DEPTH_RAMP[i][0]) {
    const [a, ca] = DEPTH_RAMP[i - 1], [b, cb] = DEPTH_RAMP[i], t = (cm - a) / (b - a);
    return ca.map((v, q) => Math.round(v + (cb[q] - v) * t));
  }
  return DEPTH_RAMP[DEPTH_RAMP.length - 1][1];
}
const depthCol = cm => { const c = depthRGB(cm); return c ? [...c, 150 + Math.min(cm, 60) * 1.6] : null; };
function probRGB(p) {
  const a = [46, 196, 214], b = [242, 184, 75], c = [229, 72, 77];
  const [x, y, t] = p < 0.5 ? [a, b, p / 0.5] : [b, c, (p - 0.5) / 0.5];
  return x.map((v, q) => Math.round(v + (y[q] - v) * t));
}
const probCol = p => p < 0.05 ? null : [...probRGB(p), 70 + 170 * p];
function diffCol(dcm) {
  if (Math.abs(dcm) < 2) return null;
  const t = Math.min(Math.abs(dcm) / 30, 1);
  return dcm > 0 ? [229, 72, 77, 80 + 170 * t] : [63, 182, 139, 80 + 170 * t];
}
const rgb = c => `rgb(${c[0]},${c[1]},${c[2]})`;

// ------------------------------------------------------------------ map layer kit (MapLibre)
const MK = { srcs: [], lyrs: [], mks: [], hov: [], clk: [], uid: 0 };
const tipPop = () => MK.tip || (MK.tip = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 12, maxWidth: "280px" }));
function mkClear() {
  for (const l of MK.lyrs) if (map.getLayer(l)) map.removeLayer(l);
  for (const s of MK.srcs) if (map.getSource(s)) map.removeSource(s);
  MK.mks.forEach(m => m.remove()); MK.lyrs = []; MK.srcs = []; MK.mks = []; MK.hov = []; MK.clk = [];
  if (MK.tip) MK.tip.remove();
}
function mkGeo(fc, layers, opt = {}) {
  const id = "v" + (MK.uid++);
  map.addSource(id, { type: "geojson", data: fc }); MK.srcs.push(id);
  layers.forEach((L, i) => {
    const lid = id + "_" + i;
    map.addLayer({ id: lid, source: id, ...L }, map.getLayer("blds") ? "blds" : undefined); MK.lyrs.push(lid);
    if (opt.tip && i === 0) MK.hov.push({ layer: lid, tip: opt.tip });
    if (opt.click && i === 0) MK.clk.push({ layer: lid, fn: opt.click });
  });
  return id;
}
const mkSet = (id, fc) => map.getSource(id) && map.getSource(id).setData(fc);
function mkMarker(ll, html, tip, onClick) {
  // MapLibre positions markers with a CSS transform on the element, so animated/rotated content
  // must live inside a plain wrapper
  const el = document.createElement("div"); el.innerHTML = html; el.style.lineHeight = "0";
  if (tip) el.title = tip;
  if (onClick) el.addEventListener("click", e => { e.stopPropagation(); onClick(); });
  const m = new maplibregl.Marker({ element: el }).setLngLat([ll[1], ll[0]]).addTo(map); MK.mks.push(m); return m;
}
const FCOL = feats => ({ type: "FeatureCollection", features: feats });
const pt = (lat, lon, p = {}) => ({ type: "Feature", properties: p, geometry: { type: "Point", coordinates: [lon, lat] } });
const line = (lls, p = {}) => ({ type: "Feature", properties: p, geometry: { type: "LineString", coordinates: lls.map(x => [x[1], x[0]]) } });
function boxPoly(s, w, n, e, p = {}) { return { type: "Feature", properties: p, geometry: { type: "Polygon", coordinates: [[[w, s], [e, s], [e, n], [w, n], [w, s]]] } }; }

// raster overlay + 3D water columns (persistent layers)
function paint(fn, water) {
  const c = document.createElement("canvas"); c.width = G.nx; c.height = G.ny;
  const ctx = c.getContext("2d"), img = ctx.createImageData(G.nx, G.ny);
  for (let k = 0; k < G.n; k++) {
    if (!G.wet[k]) continue;
    const col = fn(k); if (!col) continue;
    img.data[4 * k] = col[0]; img.data[4 * k + 1] = col[1]; img.data[4 * k + 2] = col[2]; img.data[4 * k + 3] = col[3];
  }
  ctx.putImageData(img, 0, 0);
  map.getSource("flood").updateImage({ url: c.toDataURL(), coordinates: [[G.w, G.nn], [G.e, G.nn], [G.e, G.s], [G.w, G.s]] });
  map.setPaintProperty("flood", "raster-opacity", 0.9);
  setWater(water);
}
function setWater(water) {
  const feats = [];
  if (water && S.w3d) for (let k = 0; k < G.n; k++) {
    if (!G.wet[k]) continue;
    const r = water(k); if (!r) continue;
    const i = (k / G.nx) | 0, j = k % G.nx, n = G.nn - i * G.dlat, w = G.w + j * G.dlon;
    feats.push(boxPoly(n - G.dlat, w, n, w + G.dlon, { h: r.h, c: r.c }));
  }
  map.getSource("water").setData(FCOL(feats));
}
const WATER_EXAG = 12;                          // vertical exaggeration of water columns
const depthWater = arr => k => arr[k] >= 3 ? { h: arr[k] / 100 * WATER_EXAG, c: rgb(depthRGB(arr[k])) } : null;
function clearOverlay() { if (map.getLayer("flood")) map.setPaintProperty("flood", "raster-opacity", 0); setWater(null); }

function legendRamp(title, stops, labels) {
  $("#legend").innerHTML = `<div>${title}</div><div class="ramp" style="background:linear-gradient(90deg,${stops.join(",")})"></div><div class="lab">${labels.map(l => `<span>${l}</span>`).join("")}</div>`;
}
const legendDepth = (t = "Water depth") => legendRamp(t + (S.w3d ? ` · columns ×${WATER_EXAG} vertical` : ""), ["rgb(189,235,242)", "rgb(46,196,214)", "rgb(30,111,217)", "rgb(242,184,75)", "rgb(229,72,77)"], ["3", "10", "20", "30", "60 cm"]);
const legendProb = t => legendRamp(`P(depth > ${t} cm)`, ["rgb(46,196,214)", "rgb(242,184,75)", "rgb(229,72,77)"], ["5%", "50%", "100%"]);
function legendKeys(title, items) { $("#legend").innerHTML = `<div>${title}</div><div style="margin-top:5px">${items.map(([c, l]) => `<span class="sw" style="background:${c};margin-left:0"></span>${l}&nbsp;&nbsp;`).join("")}</div>`; }

function chart(id, cfg) {
  if (S.charts[id]) S.charts[id].destroy();
  const el = document.getElementById(id); if (!el) return;
  if (!el.parentElement.classList.contains("cw")) { const w = document.createElement("div"); w.className = "cw"; el.replaceWith(w); w.appendChild(el); }
  cfg.options = Object.assign({ responsive: true, maintainAspectRatio: false, animation: false,
    plugins: { legend: { labels: { boxWidth: 8, boxHeight: 8, font: { size: 10 } } } } }, cfg.options || {});
  S.charts[id] = new Chart(el, cfg);
}
function toast(msg) { const t = $("#toast"); t.textContent = msg; t.classList.remove("hidden"); clearTimeout(t._h); t._h = setTimeout(() => t.classList.add("hidden"), 3200); }
function audit(action, detail = "") { S.audit.unshift({ t: new Date().toLocaleTimeString(), role: S.role, action, detail }); }
const tag = k => `<span class="tag ${{ synthetic: "syn", modelled: "mod", derived: "der", observed: "obs" }[k] || ""}">${k}</span>`;
function setSlider({ min = 0, max, value, label, onChange, show = true }) {
  const bar = $("#timebar"); bar.classList.toggle("hidden", !show); if (!show) return;
  stopPlay();
  const s = $("#slider"); s.min = min; s.max = max; s.value = value;
  $("#ticks").style.background = `repeating-linear-gradient(90deg,#2d3e4b 0 1px,transparent 1px ${100 / Math.max(max - min, 1)}%)`;
  const upd = () => { $("#sliderLab").textContent = label(+s.value); onChange(+s.value); };
  s.oninput = upd; upd();
  $("#play").onclick = () => {
    if (S.play) return stopPlay();
    $("#play").textContent = "❚❚";
    S.play = setInterval(() => { s.value = +s.value >= +s.max ? s.min : +s.value + 1; upd(); }, 700);
  };
}
function stopPlay() { if (S.play) clearInterval(S.play); S.play = null; $("#play").textContent = "▶"; }

// ------------------------------------------------------------------ shared analytics
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
const fitLL = (b, z = 18.2) => map.fitBounds([[b[0][1], b[0][0]], [b[1][1], b[1][0]]], { padding: 140, maxZoom: z, pitch: S.w3d ? 55 : 0, duration: 900 });
function domainSpread() {
  const a = dec(FC().p90_cm[LEADS().length - 1]), b = dec(FC().p10_cm[LEADS().length - 1]);
  let s = 0, n = 0; for (let k = 0; k < G.n; k++) if (G.wet[k] && a[k] > 3) { s += a[k] - b[k]; n++; }
  return n ? s / n : 0;
}
function healthCard() {
  const f = F(), q = f.quality, g = q.gauge_counts, tw = D.twin;
  const tot = Object.values(g).reduce((a, b) => a + b, 0);
  const spread = domainSpread();
  const sens = tw.sensors.filter(s => s.status === "VALID").length;
  const conf = D.net.nodes.reduce((a, n) => a + n.confidence, 0) / D.net.nodes.length;
  return {
    status: f.health.status,
    rainfall_freshness: q.radar.status === "VALID" ? "5 min (radar)" : "radar " + q.radar.status + " — gauges",
    radar_coverage: q.radar.status === "VALID" ? "100% of 192×192 km mosaic" : "0% (outage)",
    gauges_valid: `${g.VALID}/${tot}`, drainage_coverage: `${D.net.nodes.length} nodes · confidence ${conf.toFixed(2)} (synthetic)`,
    sensor_health: `${sens}/${tw.sensors.length} water-level sensors valid`,
    time_since_assimilation: "5 min", uncertainty: spread > 12 ? "HIGH" : spread > 6 ? "MODERATE" : "LOW",
    uncertainty_inflation: f.health.uncertainty_inflation, reasons: f.health.reasons,
  };
}
function vehicleThr(v) {
  const base = { "two-wheeler": [0.07, 0.15], car: [0.10, 0.30], ambulance: [0.15, 0.35], bus: [0.25, 0.45], "fire truck": [0.35, 0.60] }[v];
  if (!S.emergency) return base;
  // emergency policy: emergency vehicles may use deeper water, public traffic is restricted earlier
  return ["ambulance", "fire truck"].includes(v) ? [base[0] + 0.05, base[1] + 0.10] : [base[0] - 0.03, base[1] - 0.10];
}
function roadStatus(depthM, v) {
  const [deg, imp] = vehicleThr(v);
  if (depthM >= imp) return "Impassable"; if (depthM >= (deg + imp) / 2) return "High"; if (depthM >= deg) return "Degraded"; return "Passable";
}
const STATUS_COL = { Passable: COL.green, Degraded: COL.amber, High: COL.orange, Impassable: COL.red };
function roadRows() { const byId = {}; for (const r of F().flood.roads) byId[r.id] = r; return byId; }
function nodeFC(fill, rad = n => n.kind === "inlet" ? 3 : 5.5) {
  return FCOL(D.net.nodes.map((n, i) => pt(n.lat, n.lon, { id: n.id, kind: n.kind, fill: fill[i], r: rad(n),
    c: fill[i] >= 1 ? COL.red : fill[i] > 0.6 ? COL.amber : COL.green })));
}
const circleLayer = (extra = {}) => ({ type: "circle", paint: Object.assign({ "circle-radius": ["get", "r"], "circle-color": ["get", "c"], "circle-stroke-color": COL.ink, "circle-stroke-width": 1.2 }, extra) });

// ------------------------------------------------------------------ views
const VIEWS = {};

VIEWS.live = () => {
  const live = D.net.live, f = F(), h = healthCard();
  const P = $("#panel");
  P.innerHTML = `
  <div class="card"><h3>Forecast health ${tag("derived")}</h3>
    <div class="row"><span class="st ${h.status}">${h.status}</span><span class="muted small">cycle every 5 min · this run ${fmt(f.timings_s.total, 1)} s</span></div>
    <table>${[["Rainfall freshness", h.rainfall_freshness], ["Radar coverage", h.radar_coverage], ["Rain gauges valid", h.gauges_valid],
      ["Drainage coverage", h.drainage_coverage], ["Sensor health", h.sensor_health], ["Since last assimilation", h.time_since_assimilation],
      ["Forecast uncertainty", h.uncertainty]].map(r => `<tr><td class="muted">${r[0]}</td><td>${r[1]}</td></tr>`).join("")}</table>
    ${h.reasons.length ? `<div class="small" style="margin-top:8px;color:#ffb1b4">${h.reasons.map(r => "— " + r).join("<br>")}</div>` : ""}
  </div>
  <div class="card"><h3>Now on campus ${tag("modelled")}</h3><div class="kpis" id="liveKpi"></div></div>
  <div class="card"><h3>Rainfall, campus mean ${tag("derived")}</h3><canvas id="cRain"></canvas></div>
  <div class="card"><h3>Alerts ${tag("modelled")}</h3><div class="list" id="alerts"></div></div>
  <div class="card"><h3>Observation quality ${tag(f.sources.radar === "synthetic_radar" ? "synthetic" : "observed")}</h3>
    <table><tr><th>Source</th><th>Status</th><th>Reason</th></tr>
    <tr><td>Radar mosaic</td><td><span class="st ${f.quality.radar.status}">${f.quality.radar.status}</span></td><td class="small muted">${f.quality.radar.reasons.join("; ") || "range, coverage, freeze and jump checks passed"}</td></tr>
    ${Object.entries(f.quality.gauges).map(([id, g]) => `<tr><td>Gauge ${id}</td><td><span class="st ${g.status}">${g.status}</span></td><td class="small muted">${g.reasons.join("; ") || "ok"}</td></tr>`).join("")}
    </table>
    <div class="small muted" style="margin-top:8px">Radar bias correction ×${fmt(f.rainfall.gauge_mean_field_bias.factor, 2)} from ${f.rainfall.gauge_mean_field_bias.pairs} gauge pairs (${f.rainfall.gauge_mean_field_bias.applied ? "applied" : "not applied — too little paired rain"})</div>
  </div>
  <div class="card"><h3>Terrain data tier ${tag("derived")}</h3><div class="small">${D.grid.terrain.data_tier_label}<br><span class="muted">${D.grid.terrain.dem_kind} · ${D.grid.terrain.resolution_m} m grid · ${D.grid.terrain.vertical_datum}</span></div></div>`;
  const al = [];
  f.flood.hotspots.forEach((hh, i) => al.push({ lvl: hh.early_warning ? "high" : "medium", t: `Hotspot H${i + 1} — P(>20 cm) ${pct(hh.p_exceed_20cm_max)}`,
    d: hh.early_warning ? `dry now, 10 cm expected in ~${fmt(hh.time_to_threshold_min)} min` : hh.reasons.join(", "), hh }));
  f.flood.roads.filter(r => r.p_exceed["10cm"] >= 0.3).slice(0, 3).forEach(r => al.push({ lvl: "medium", t: `Road ${r.name || r.id} — P(>10 cm) ${pct(r.p_exceed["10cm"])}`, d: `expected peak ${fmt(r.expected_peak_m * 100)} cm` }));
  D.twin.anomalies.slice(0, 2).forEach(a => al.push({ lvl: a.severity, t: `${a.asset} — ${a.cause}`, d: a.action }));
  $("#alerts").innerHTML = al.map((a, i) => `<div class="item" data-i="${i}"><span class="st ${a.lvl}">${a.lvl}</span><div><b>${a.t}</b></div><div class="small muted">${a.d}</div></div>`).join("") || "<span class='muted'>No alerts</span>";
  $("#alerts").querySelectorAll(".item").forEach(el => el.onclick = () => { const a = al[+el.dataset.i]; if (a.hh) { go("prob"); fitLL(hotspotBounds(a.hh)); } });
  const k0 = K0(), hist = live.rain_mmh.slice(0, k0 + 1);
  const cum = FC().rain_cum_mm;
  const rate = q => cum[0].map((_, k) => quant(cum.map(m => (m[k] - (k ? m[k - 1] : 0)) * 12), q));
  const labels = [...live.times_min.slice(0, k0 + 1), ...Array.from({ length: 36 }, (_, k) => D.fc.t0_min + 5 * (k + 1))];
  const pad = Array(k0 + 1).fill(null);
  chart("cRain", { data: { labels, datasets: [
    { type: "bar", label: "observed", data: [...hist, ...Array(36).fill(null)], backgroundColor: COL.teal },
    { type: "line", label: "forecast P50", data: [...pad, ...rate(0.5)], borderColor: COL.paper, pointRadius: 0, borderWidth: 1.8 },
    { type: "line", label: "P90", data: [...pad, ...rate(0.9)], borderColor: COL.orange, borderDash: [4, 3], pointRadius: 0, borderWidth: 1 },
    { type: "line", label: "P10", data: [...pad, ...rate(0.1)], borderColor: COL.mut, borderDash: [4, 3], pointRadius: 0, borderWidth: 1 }] },
    options: { scales: { x: { ticks: { maxTicksLimit: 7, callback: (v, i) => "T+" + labels[i] } }, y: { title: { display: true, text: "mm/h" } } } } });
  const nodes = mkGeo(nodeFC(live.node_fill[k0]), [circleLayer()], { tip: p => `<b>N-${p.id}</b> ${p.kind}<br>${pct(p.fill)} of pipe depth` });
  legendDepth("Twin state");
  setSlider({ max: k0, value: k0, label: v => `T+${live.times_min[v]} min${v === k0 ? " · now" : ""}`, onChange: v => {
    const d = dec(live.depth_cm[v]); paint(k => depthCol(d[k]), depthWater(d));
    const st = domainStats(d), fill = live.node_fill[v], sur = fill.filter(x => x >= 1).length;
    $("#liveKpi").innerHTML = `<div class="kpi"><small>Flooded ≥ 10 cm</small><b class="${st.flooded > 2000 ? "warn" : "ok"}">${m2(st.flooded)}</b></div>
      <div class="kpi"><small>Deepest cell</small><b>${st.max} cm</b></div><div class="kpi"><small>Rain now</small><b>${fmt(live.rain_mmh[v], 1)}<span class="small muted"> mm/h</span></b></div>
      <div class="kpi"><small>Surcharged nodes</small><b class="${sur ? "danger" : "ok"}">${sur}</b></div>`;
    mkSet(nodes, nodeFC(fill));
  } });
};

VIEWS.forecast = () => {
  const P = $("#panel"), L_ = LEADS();
  P.innerHTML = `
  <div class="card"><h3>Depth forecast ${tag("modelled")}</h3>
    <div class="seg" id="layerSeg">${[["expected", "Expected"], ["p10", "P10"], ["p50", "P50"], ["p90", "P90"], ["peak", "Peak"]].map(([k, l]) => `<button data-k="${k}" class="${S.layer === k ? "on" : ""}">${l}</button>`).join("")}</div>
    <div class="kpis" id="fcKpi" style="margin-top:12px"></div>
    <div class="small muted" style="margin-top:10px">${F().flood.members} ensemble members × 14 lead times. Surrogate everywhere, full physics inside ${F().flood.adaptive_refinement.tiles} hotspot tiles. Click the map for a location forecast.</div>
  </div>
  <div class="card" id="cellCard"><h3>Location forecast</h3><div class="muted small">Click any street or open ground on the map.</div></div>
  <div class="card"><h3>Flooded area over time ${tag("modelled")}</h3><canvas id="cArea"></canvas></div>`;
  P.querySelectorAll("#layerSeg button").forEach(b => b.onclick = () => { S.layer = b.dataset.k; go("forecast"); });
  const fa = F().flood.domain.flooded_area_m2, ks = Object.keys(fa);
  chart("cArea", { type: "line", data: { labels: ks.map(k => "+" + k), datasets: [
    { label: "P90", data: ks.map(k => fa[k].p90), borderColor: COL.orange, backgroundColor: "rgba(46,196,214,.14)", fill: "+2", pointRadius: 0, borderWidth: 1 },
    { label: "P50", data: ks.map(k => fa[k].p50), borderColor: COL.paper, pointRadius: 0, borderWidth: 2 },
    { label: "P10", data: ks.map(k => fa[k].p10), borderColor: COL.mut, pointRadius: 0, borderWidth: 1 }] },
    options: { scales: { y: { title: { display: true, text: "m² ≥ 10 cm" } } } } });
  legendDepth(S.layer === "peak" ? "Peak depth 0–180 min" : "Depth");
  const key = { expected: "expected_cm", p10: "p10_cm", p50: "p50_cm", p90: "p90_cm" }[S.layer];
  setSlider({ show: S.layer !== "peak", max: L_.length - 1, value: S.leadIdx ?? 5, label: v => `+${L_[v]} min · T+${D.fc.t0_min + L_[v]}`, onChange: v => {
    S.leadIdx = v; const d = dec(FC()[key][v]); paint(k => depthCol(d[k]), depthWater(d));
    const st = domainStats(d);
    $("#fcKpi").innerHTML = `<div class="kpi"><small>Flooded ≥ 10 cm</small><b class="warn">${m2(st.flooded)}</b></div><div class="kpi"><small>Deepest cell</small><b>${st.max} cm</b></div>`;
    if (S.sel) cellPanel(S.sel);
  } });
  if (S.layer === "peak") { const d = dec(FC().peak_cm); paint(k => depthCol(d[k]), depthWater(d)); const st = domainStats(d); $("#fcKpi").innerHTML = `<div class="kpi"><small>Flooded at peak</small><b class="warn">${m2(st.flooded)}</b></div><div class="kpi"><small>Deepest peak</small><b>${st.max} cm</b></div>`; }
  if (S.sel) cellPanel(S.sel);
};

function cellPanel(c) {
  const k = c.k, fc = FC(), L_ = LEADS(), ll = cellLL(c.i, c.j);
  if (!G.wet[k]) { $("#cellCard").innerHTML = "<h3>Location forecast</h3><div class='muted small'>That is a building or outside the modelled campus.</div>"; return; }
  if (S.selMarker) S.selMarker.remove();
  S.selMarker = mkMarker(ll, `<div class="ring"></div>`);
  const ttt = dec(fc.ttt_min)[k], pk = dec(fc.peak_cm)[k], pkt = dec(fc.peak_time_min)[k];
  const pr = dec(fc.p_reach)[k] / 100, dur = dec(fc.duration_min)[k];
  const pAny = t => { let m = 0; for (const s of fc.exceed[t]) m = Math.max(m, dec(s)[k]); return m / 100; };
  const idx = S.leadIdx ?? 5;
  const series = w => L_.map((_, l) => dec(fc[w][l])[k]);
  const members = (fc.members_cm || []).map(m => L_.map((_, l) => dec(m[l])[k]));
  $("#cellCard").innerHTML = `<h3>${ll[0].toFixed(5)}°N ${ll[1].toFixed(5)}°E ${tag("modelled")}</h3>
    <div class="kpis"><div class="kpi"><small>Depth now</small><b>${dec(fc.depth_now_cm)[k]} cm</b></div>
      <div class="kpi"><small>At +${L_[idx]} min</small><b>${dec(fc.expected_cm[idx])[k]} cm</b><div class="small muted">P10–P90 ${dec(fc.p10_cm[idx])[k]}–${dec(fc.p90_cm[idx])[k]} cm</div></div>
      <div class="kpi"><small>Expected peak</small><b>${pk} cm</b><div class="small muted">P90 ${dec(fc.peak_p90_cm)[k]} cm · ${pkt === 255 ? "–" : "at +" + pkt + " min"}</div></div>
      <div class="kpi"><small>Reaches 10 cm</small><b class="${ttt < 255 ? "danger" : "ok"}">${ttt < 255 ? "+" + ttt + " min" : "no"}</b><div class="small muted">P ${pct(pr)} · wet ${dur} min</div></div></div>
    <table style="margin-top:10px"><tr><th>P(depth &gt;)</th><th class="num">10 cm</th><th class="num">20 cm</th><th class="num">30 cm</th></tr>
      <tr><td class="muted">within 3 h</td><td class="num">${pct(pAny("10"))}</td><td class="num">${pct(pAny("20"))}</td><td class="num">${pct(pAny("30"))}</td></tr></table>
    <canvas id="cCell"></canvas>
    <div class="why" id="why" style="margin-top:14px"></div>`;
  chart("cCell", { type: "line", data: { labels: L_.map(l => "+" + l), datasets: [
    ...members.map((m, i) => ({ label: i ? undefined : "members", data: m, borderColor: "rgba(138,148,156,.4)", borderWidth: 1, pointRadius: 0 })),
    { label: "P90", data: series("p90_cm"), borderColor: COL.orange, pointRadius: 0, borderDash: [4, 3], borderWidth: 1 },
    { label: "expected", data: series("expected_cm"), borderColor: COL.teal, borderWidth: 2.5, pointRadius: 0 },
    { label: "P10", data: series("p10_cm"), borderColor: COL.mut, pointRadius: 0, borderDash: [4, 3], borderWidth: 1 }] },
    options: { plugins: { legend: { labels: { filter: i => i.text } } }, scales: { y: { title: { display: true, text: "cm" } } } } });
  whyPanel(c, ll);
}

function whyPanel(c, ll) {
  const k = c.k, fc = FC();
  const rain = quant(fc.rain_cum_mm.map(m => m[m.length - 1]), 0.5);
  const imp = G.imp[k] / 100, terr = Math.max(G.low[k] ? 0.85 : 0, G.acc[k] / G.accMax);
  const nn = nodeNear(ll[0], ll[1], 80); const fill = nn ? D.net.live.node_fill[K0()][nn.node.id] : 0;
  const anom = D.twin.anomalies.find(a => { const n = D.net.nodes[a.node]; return n && distM(ll[0], ll[1], n.lat, n.lon) < 90; });
  const f = [
    ["Rainfall", Math.min(rain / 60, 1), `${fmt(rain, 1)} mm expected in the next 3 h (P50)`],
    ["Runoff", imp, `${pct(imp)} of the surface is impervious`],
    ["Terrain", terr, G.low[k] ? "sits in a local depression" : `flow accumulation ${pct(G.acc[k] / G.accMax)} of campus max`],
    ["Drainage", nn ? Math.min(fill, 1) : 0.9, nn ? `inlet N-${nn.node.id}, ${Math.round(nn.d)} m away, ${pct(fill)} full${fill >= 1 ? " and surcharging" : ""}` : "no inlet within 80 m"],
    ["Assets", anom ? anom.likelihood : 0.05, anom ? `${anom.asset}: ${anom.cause}` : "no suspected fault nearby"],
    ["Boundary", 0.1, "outfalls discharging freely"]];
  const top = [...f].sort((a, b) => b[1] - a[1])[0];
  $("#why").innerHTML = `<div class="small" style="margin-bottom:4px"><span style="font:400 17px var(--serif)">Why here?</span> ${tag("derived")}</div>
    ${f.map(([n, v, t]) => `<div class="f"><span>${n}</span><div class="bar"><div style="width:${Math.round(v * 100)}%;background:${v > .7 ? COL.red : v > .4 ? COL.amber : COL.teal}"></div></div><span>${pct(v)}</span></div><div class="small muted" style="margin:2px 0 0 106px">${t}</div>`).join("")}
    <div class="small" style="margin-top:10px">Main driver: <b style="color:var(--orange)">${top[0].toLowerCase()}</b></div>`;
}

VIEWS.prob = () => {
  const P = $("#panel"), f = F(), L_ = LEADS(), ad = f.flood.adaptive_refinement;
  P.innerHTML = `
  <div class="card"><h3>Chance of flooding ${tag("modelled")}</h3>
    <div class="seg" id="thrSeg">${["10", "20", "30"].map(t => `<button data-t="${t}" class="${S.thr === t ? "on" : ""}">&gt; ${t} cm</button>`).join("")}</div>
    <div class="kpis" id="pKpi" style="margin-top:12px"></div></div>
  <div class="card"><h3>Hotspots ${tag("modelled")}</h3><div class="list" id="hsList"></div>
    <div class="small muted" style="margin-top:8px">Re-run with the full coupled physics: ${ad.tiles} tiles, members ${(ad.representative_members || []).join(", ") || "–"}, mean correction ${fmt((ad.mean_abs_correction_m || 0) * 100, 1)} cm, ${fmt(ad.physics_runtime_s, 1)} s.</div></div>
  <div class="card"><h3>Radar nowcast ${tag("modelled")}</h3>
    <div class="row"><div class="seg" id="rq"><button data-q="p50" class="${S.radarQ === "p50" ? "on" : ""}">P50</button><button data-q="p90" class="${S.radarQ === "p90" ? "on" : ""}">P90</button></div>
    <div class="seg" id="rl">${FC().radar.leads.map((l, i) => `<button data-i="${i}" class="${S.radarLead === i ? "on" : ""}">+${l}</button>`).join("")}</div></div>
    <canvas id="radar" width="360" height="360" style="width:100%;display:block;background:#081016"></canvas>
    <div class="small muted" style="margin-top:6px">96 × 96 km around campus · storm moving ${fmt(f.rainfall.nowcast.motion_speed_kmh, 0)} km/h · long-lead guidance: ${f.rainfall.nowcast.guidance} · nowcast weight ${Object.entries(f.rainfall.nowcast.blend_weights).map(([k, v]) => "+" + k + " " + v).join(", ")}</div></div>
  <div class="card"><h3>Rain ensemble, campus ${tag("modelled")}</h3><canvas id="cEns"></canvas></div>`;
  P.querySelectorAll("#thrSeg button").forEach(b => b.onclick = () => { S.thr = b.dataset.t; go("prob"); });
  P.querySelectorAll("#rq button").forEach(b => b.onclick = () => { S.radarQ = b.dataset.q; drawRadar(); P.querySelectorAll("#rq button").forEach(x => x.classList.toggle("on", x === b)); });
  P.querySelectorAll("#rl button").forEach(b => b.onclick = () => { S.radarLead = +b.dataset.i; drawRadar(); P.querySelectorAll("#rl button").forEach(x => x.classList.toggle("on", x === b)); });
  drawRadar();
  const hs = f.flood.hotspots;
  mkGeo(FCOL(hs.map((h, i) => { const b = hotspotBounds(h); return boxPoly(b[0][0], b[0][1], b[1][0], b[1][1], { n: i + 1, c: h.early_warning ? COL.red : COL.amber }); })),
    [{ type: "line", paint: { "line-color": ["get", "c"], "line-width": 2, "line-dasharray": [2, 1.5] } },
     { type: "fill-extrusion", paint: { "fill-extrusion-color": ["get", "c"], "fill-extrusion-opacity": 0.12, "fill-extrusion-height": 14 } }]);
  hs.forEach((h, i) => { const b = hotspotBounds(h); mkMarker([b[1][0], b[0][1]], `<span class="pin hot">H${i + 1}</span>`, h.reasons.join(", "), () => fitLL(b)); });
  $("#hsList").innerHTML = hs.map((h, i) => `<div class="item" data-i="${i}"><b>H${i + 1}</b> ${h.early_warning ? '<span class="st high" style="margin-left:6px">early warning</span>' : ""}
      <div class="small">P(&gt;20 cm) <b>${pct(h.p_exceed_20cm_max)}</b> · spread ${fmt(h.peak_spread_m * 100)} cm · now ${fmt(h.max_depth_now_m * 100)} cm · 10 cm ${h.time_to_threshold_min != null ? "in " + h.time_to_threshold_min + " min" : "–"}</div>
      <div class="small muted">${h.reasons.join(" · ")}</div></div>`).join("") || "<span class='muted'>No hotspots this cycle</span>";
  $("#hsList").querySelectorAll(".item").forEach(el => el.onclick = () => fitLL(hotspotBounds(hs[+el.dataset.i])));
  const cum = FC().rain_cum_mm;
  chart("cEns", { type: "line", data: { labels: cum[0].map((_, k) => "+" + 5 * (k + 1)), datasets: cum.map((m, i) => ({
    label: i ? undefined : "members, cumulative", data: m, borderColor: i === 0 ? COL.paper : "rgba(46,196,214,.35)", borderWidth: i === 0 ? 2 : 1, pointRadius: 0 })) },
    options: { plugins: { legend: { labels: { filter: i => i.text } } }, scales: { x: { ticks: { maxTicksLimit: 7 } }, y: { title: { display: true, text: "mm after T+" + D.fc.t0_min } } } } });
  legendProb(S.thr);
  setSlider({ max: L_.length - 1, value: S.leadIdx ?? 5, label: v => `+${L_[v]} min · T+${D.fc.t0_min + L_[v]}`, onChange: v => {
    S.leadIdx = v; const d = dec(FC().exceed[S.thr][v]);
    paint(k => probCol(d[k] / 100), k => d[k] >= 5 ? { h: d[k] / 100 * 8, c: rgb(probRGB(d[k] / 100)) } : null);
    let a50 = 0, a80 = 0; for (let k = 0; k < G.n; k++) if (G.wet[k]) { if (d[k] >= 50) a50++; if (d[k] >= 80) a80++; }
    $("#pKpi").innerHTML = `<div class="kpi"><small>Area with P ≥ 50%</small><b class="warn">${m2(a50 * 25)}</b></div><div class="kpi"><small>Area with P ≥ 80%</small><b class="danger">${m2(a80 * 25)}</b></div>`;
  } });
};

function drawRadar() {
  const r = FC().radar, cv = $("#radar"); if (!cv) return;
  const a = dec(r[S.radarQ][S.radarLead]), n = r.n, ctx = cv.getContext("2d"), px = cv.width / n;
  ctx.fillStyle = "#081016"; ctx.fillRect(0, 0, cv.width, cv.height);
  ctx.strokeStyle = "#1b2831"; ctx.lineWidth = 1;
  for (let q = 1; q < 4; q++) { ctx.beginPath(); ctx.arc(cv.width / 2, cv.height / 2, q * cv.width / 8, 0, 7); ctx.stroke(); }
  ctx.beginPath(); ctx.moveTo(cv.width / 2, 0); ctx.lineTo(cv.width / 2, cv.height); ctx.moveTo(0, cv.height / 2); ctx.lineTo(cv.width, cv.height / 2); ctx.stroke();
  for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
    const v = a[i * n + j] / 2; if (v < 0.5) continue;
    const t = Math.min(Math.log10(v + 1) / 2, 1), c = t < .5 ? [46, 196, 214] : t < .8 ? [242, 184, 75] : [229, 72, 77];
    ctx.fillStyle = `rgba(${c},${0.3 + 0.7 * t})`; ctx.fillRect(j * px, i * px, px + .5, px + .5);
  }
  ctx.strokeStyle = COL.paper; ctx.lineWidth = 1.5; ctx.strokeRect(cv.width / 2 - 4, cv.height / 2 - 4, 8, 8);
  ctx.fillStyle = COL.mut; ctx.font = "500 11px 'IBM Plex Mono'"; ctx.fillText(`${S.radarQ.toUpperCase()} rain rate · +${r.leads[S.radarLead]} min`, 10, 18);
  ctx.fillText("24 km", cv.width / 2 + cv.width / 4 + 4, cv.height / 2 - 4);
}

VIEWS.drain = () => {
  const tw = D.twin, live = D.net.live, P = $("#panel");
  const imp = 100 * (1 - tw.rmse.assimilated_m / tw.rmse.open_loop_m);
  P.innerHTML = `
  <div class="card"><h3>Assimilation ${tag("modelled")}</h3>
    <div class="kpis"><div class="kpi"><small>Model alone</small><b class="warn">${fmt(tw.rmse.open_loop_m * 100, 1)} cm</b></div>
    <div class="kpi"><small>With sensors</small><b class="ok">${fmt(tw.rmse.assimilated_m * 100, 1)} cm</b></div></div>
    <div class="small" style="margin-top:8px">Water-level error at the sensors drops by <b>${fmt(imp)}%</b> once readings are folded in every 5 minutes.</div>
    <div class="row" style="margin-top:12px"><span class="muted small">Sensor</span><select id="sensSel">${tw.sensors.map((s, i) => `<option value="${i}" ${i === S.sensor ? "selected" : ""}>${s.id} · ${s.status}</option>`).join("")}</select></div>
    <canvas id="cTwin"></canvas></div>
  <div class="card"><h3>Suspected faults ${tag("derived")}</h3><div class="list" id="anoms"></div></div>
  <div class="card"><h3>Sensor trust ${tag("derived")}</h3>
    <table><tr><th>Sensor</th><th>Status</th><th class="num">Trust</th><th></th></tr>${tw.sensors.map(s => `<tr><td>${s.id}</td><td><span class="st ${s.status}">${s.status}</span></td><td class="num">${fmt(s.trust, 2)}</td><td style="width:38%;vertical-align:middle"><div class="bar"><div style="width:${s.trust * 100}%;background:${s.trust < .3 ? COL.red : COL.green}"></div></div></td></tr>`).join("")}</table>
    <div class="small muted" style="margin-top:8px">Rejected sensors drop out; the twin carries on with the rest.</div></div>
  <div class="card"><h3>Twin state</h3><table id="twinState"></table></div>`;
  $("#sensSel").onchange = e => { S.sensor = +e.target.value; twinChart(); const s = tw.sensors[S.sensor]; map.flyTo({ center: [s.lon, s.lat], zoom: 18.3, duration: 800 }); };
  twinChart();
  $("#anoms").innerHTML = tw.anomalies.map((a, i) => `<div class="item" data-i="${i}"><span class="st ${a.severity}">${a.severity}</span> <b>${a.asset}</b> — ${a.cause}
    <div class="row" style="margin:8px 0 4px"><span class="small muted">likelihood</span><div class="bar" style="flex:1"><div style="width:${a.likelihood * 100}%;background:${COL.orange}"></div></div><b class="small">${pct(a.likelihood)}</b></div>
    <div class="small muted">${a.evidence}${a.estimated_blockage != null ? ` · estimated blockage ${pct(a.estimated_blockage)}` : ""}</div>
    <div class="row" style="margin:8px 0 0;justify-content:space-between"><span class="small">→ ${a.action}</span><button class="btn sm" data-wo="${i}" ${S.approvals["wo" + i] ? "disabled" : ""}>${S.approvals["wo" + i] ? "Order raised" : "Raise work order"}</button></div></div>`).join("");
  $("#anoms").querySelectorAll("[data-wo]").forEach(b => b.onclick = e => { e.stopPropagation(); const a = tw.anomalies[+b.dataset.wo]; S.approvals["wo" + b.dataset.wo] = 1; audit("work order raised", `${a.asset} — ${a.action}`); toast(`Work order raised for ${a.asset}`); go("drain"); });
  $("#anoms").querySelectorAll(".item").forEach(el => el.onclick = () => { const n = D.net.nodes[tw.anomalies[+el.dataset.i].node]; map.flyTo({ center: [n.lon, n.lat], zoom: 18.5, duration: 800 }); });
  const q = F().flood.twin_state, fillNow = live.node_fill[K0()];
  const rows = [["Surface", `${m2(q.flooded_area_now_m2)} flooded · deepest ${fmt(q.max_depth_now_m * 100)} cm`, "physics + assimilation", "±" + fmt(domainSpread() / 2, 0) + " cm"],
    ["Sewers", `${fillNow.filter(x => x >= 1).length} of ${D.net.nodes.length} nodes surcharged`, "1D engine + sensors", `±${fmt(tw.rmse.assimilated_m * 100, 1)} cm`],
    ["Sump", `${pct(fillNow[D.net.nodes.findIndex(n => n.kind === "storage")])} full`, "1D engine", "–"],
    ["Pump P-60", "auto · available", "SCADA (simulated)", "–"], ["Outfalls", "free discharge", "boundary config", "–"],
    ["Rain, next hour", `${fmt(quant(FC().rain_cum_mm.map(m => m[11]), 0.5), 1)} mm (P50)`, F().health.rain_source_mode, `${fmt(quant(FC().rain_cum_mm.map(m => m[11]), .1), 1)}–${fmt(quant(FC().rain_cum_mm.map(m => m[11]), .9), 1)} mm`],
    ["Infrastructure", `${tw.anomalies.filter(a => a.cause.startsWith("pipe")).length} suspected obstructions`, "residual analysis", "ranked"]];
  $("#twinState").innerHTML = `<tr><th>State</th><th>Estimate</th><th>Source</th><th>±</th></tr>` + rows.map(r => `<tr><td class="muted">${r[0]}</td><td>${r[1]}</td><td class="small muted">${r[2]}</td><td class="small">${r[3]}</td></tr>`).join("");
  clearOverlay();
  legendKeys("Pipe load · ◆ sensor · ○ fault", [[COL.green, "< 60%"], [COL.amber, "60–100%"], [COL.red, "> 100%"]]);
  const pipeFC = u => FCOL(D.net.edges.map((e, i) => { const a = D.net.nodes[e.u], b = D.net.nodes[e.v];
    return line([[a.lat, a.lon], [b.lat, b.lon]], { id: e.id, kind: e.kind, d: e.diameter_m || .3, u: u[i], w: 2 + 5 * (e.diameter_m || .3), c: u[i] > 1 ? COL.red : u[i] > .6 ? COL.amber : COL.green }); }));
  const pipes = mkGeo(pipeFC(live.pipe_util[K0()]), [
    { type: "line", paint: { "line-color": ["get", "c"], "line-width": ["get", "w"], "line-opacity": .95 }, layout: { "line-cap": "round" } },
    { type: "line", paint: { "line-color": ["get", "c"], "line-width": ["*", 3, ["get", "w"]], "line-opacity": .18, "line-blur": 4 } }],
    { tip: p => `<b>${p.kind === "pump" ? "Pump" : "Pipe"} P-${p.id}</b><br>Ø ${p.d} m · ${pct(p.u)} of capacity` });
  const nodes = mkGeo(nodeFC(live.node_fill[K0()], n => n.kind === "inlet" ? 2.5 : 4.5), [circleLayer()], { tip: p => `<b>N-${p.id}</b> ${p.kind}<br>${pct(p.fill)} full` });
  tw.sensors.forEach(s => mkMarker([s.lat, s.lon], `<div class="dia ${s.status === "FAULT" ? "bad" : ""}"></div>`, `${s.id} · trust ${s.trust}`));
  tw.anomalies.forEach(a => { const n = D.net.nodes[a.node]; mkMarker([n.lat, n.lon], `<div class="ring" title="${a.asset}: ${a.cause}"></div>`); });
  setSlider({ max: live.times_min.length - 1, value: K0(), label: v => `T+${live.times_min[v]} min${v === K0() ? " · now" : v > K0() ? " · ahead" : ""}`, onChange: v => {
    mkSet(pipes, pipeFC(live.pipe_util[v])); mkSet(nodes, nodeFC(live.node_fill[v], n => n.kind === "inlet" ? 2.5 : 4.5));
  } });
};
function twinChart() {
  const tw = D.twin, i = S.sensor, t = tw.times_min;
  chart("cTwin", { type: "line", data: { labels: t.map(x => "T+" + x), datasets: [
    { label: "observed", data: tw.observed[i], borderColor: "rgba(0,0,0,0)", backgroundColor: COL.amber, pointRadius: 2, showLine: false },
    { label: "model alone", data: tw.open_loop[i], borderColor: COL.mut, borderDash: [5, 4], pointRadius: 0, borderWidth: 1.2 },
    { label: "assimilated", data: tw.assimilated[i], borderColor: COL.teal, borderWidth: 2.5, pointRadius: 0 }] },
    options: { scales: { x: { ticks: { maxTicksLimit: 7 } }, y: { title: { display: true, text: "node depth (m)" } } } } });
}

VIEWS.impact = () => {
  const P = $("#panel"), L_ = LEADS();
  const opts = D.blocks.map((b, i) => `<option value="${i}">${b.name} block</option>`).join("");
  P.innerHTML = `
  <div class="card"><h3>Road impact ${tag("modelled")}</h3>
    <div class="row"><label class="field"><span>Vehicle</span><select id="veh">${["two-wheeler", "car", "ambulance", "bus", "fire truck"].map(v => `<option ${v === S.vehicle ? "selected" : ""}>${v}</option>`).join("")}</select></label>
    <span class="small muted">slows at ${Math.round(vehicleThr(S.vehicle)[0] * 100)} cm · stops at ${Math.round(vehicleThr(S.vehicle)[1] * 100)} cm</span></div>
    <label class="switch" style="margin-bottom:12px"><input type="checkbox" id="emerg" ${S.emergency ? "checked" : ""}/><i></i><span>Emergency operations policy</span></label>
    <div class="kpis" id="roadKpi"></div><table id="roadTbl" style="margin-top:10px"></table></div>
  <div class="card"><h3>Route planner ${tag("modelled")}</h3>
    <div class="row"><button class="btn sm ghost" id="pickO">${S.route.origin ? "A set ✓" : "Pick A on map"}</button><button class="btn sm ghost" id="pickD">${S.route.dest ? "B set ✓" : "Pick B on map"}</button></div>
    <div class="row"><label class="field"><span>From</span><select id="fromB"><option value="">block…</option>${opts}</select></label><label class="field"><span>To</span><select id="toB"><option value="">block…</option>${opts}</select></label>
    <label class="field"><span>Leave</span><select id="dep">${[0, 15, 30, 60, 90, 120].map(v => `<option value="${v}" ${v === (S.route.dep || 0) ? "selected" : ""}>${v ? "in " + v + " min" : "now"}</option>`).join("")}</select></label>
    <label class="field"><span>Risk tolerance</span><select id="tol">${["low", "medium", "high"].map(v => `<option ${v === (S.route.tol || "low") ? "selected" : ""}>${v}</option>`).join("")}</select></label></div>
    <button class="btn" id="goRoute">Find three routes</button>
    <div id="routeOut" style="margin-top:12px"></div></div>
  <div class="card"><h3>Building access ${tag("modelled")}</h3><table id="critTbl"></table></div>`;
  $("#veh").onchange = e => { S.vehicle = e.target.value; go("impact"); };
  $("#emerg").onchange = e => { S.emergency = e.target.checked; audit("emergency policy " + (S.emergency ? "activated" : "deactivated")); go("impact"); };
  $("#pickO").onclick = () => { S.route.picking = "origin"; toast("Click the map to place A"); };
  $("#pickD").onclick = () => { S.route.picking = "dest"; toast("Click the map to place B"); };
  $("#fromB").onchange = e => { const b = D.blocks[+e.target.value]; if (b) { S.route.origin = nearestWet(b.lat, b.lon); S.route.results = []; go("impact"); } };
  $("#toB").onchange = e => { const b = D.blocks[+e.target.value]; if (b) { S.route.dest = nearestWet(b.lat, b.lon); S.route.results = []; go("impact"); } };
  $("#dep").onchange = e => S.route.dep = +e.target.value;
  $("#tol").onchange = e => S.route.tol = e.target.value;
  $("#goRoute").onclick = () => runRoutes();
  clearOverlay();
  const rr = roadRows();
  const roadFeats = v => FCOL(D.roads.features.filter(ft => !["footway", "steps", "path"].includes(ft.properties.highway)).map(ft => {
    const p = ft.properties, r = rr["R-" + p.osm_id], dm = r ? r.expected_by_lead_m[v] : 0, st = roadStatus(dm, S.vehicle), closed = S.route.closed.has("R-" + p.osm_id);
    return { type: "Feature", geometry: ft.geometry, properties: { id: r ? r.id : "", name: p.name || p.highway || "road", m: r ? 1 : 0, st, dm, closed: closed ? 1 : 0,
      c: closed ? "#b58cff" : r ? STATUS_COL[st] : "#3b4a55", w: r ? 6 : 2 } };
  }));
  const roads = mkGeo(roadFeats(S.leadIdx ?? 5), [
    { type: "line", paint: { "line-color": ["get", "c"], "line-width": ["get", "w"], "line-opacity": .95 }, layout: { "line-cap": "round", "line-join": "round" } },
    { type: "line", filter: ["==", ["get", "m"], 1], paint: { "line-color": ["get", "c"], "line-width": 16, "line-opacity": .15, "line-blur": 6 } }],
    { tip: p => p.m ? `<b>${p.name}</b> · ${p.id}<br><span style="color:${p.c}">${p.st === "High" ? "High risk" : p.st}</span> for ${S.vehicle} · ${fmt(p.dm * 100)} cm${p.closed ? "<br>closed" : ""}` : `${p.name} · outside modelled campus`,
      click: p => { const r = rr[p.id]; if (!r) return null; return `<b>${r.name || "Campus road"}</b> <span class="muted">${r.id}</span><br>P(&gt;10/20/30 cm): ${pct(r.p_exceed["10cm"])} / ${pct(r.p_exceed["20cm"])} / ${pct(r.p_exceed["30cm"])}<br>expected peak ${fmt(r.expected_peak_m * 100)} cm (P90 ${fmt(r.peak_p90_m * 100)})<br>under water ~${r.duration_expected_min} min · 10 cm ${r.time_to_threshold_min != null ? "at +" + r.time_to_threshold_min : "not expected"}`; } });
  legendKeys(`Road status · ${S.vehicle}${S.emergency ? " · emergency policy" : ""}`, Object.entries(STATUS_COL).map(([k, c]) => [c, k === "High" ? "High risk" : k]));
  S.route.layerId = mkGeo(FCOL([]), [
    { type: "line", paint: { "line-color": ["get", "c"], "line-width": 12, "line-opacity": .25, "line-blur": 3 } },
    { type: "line", paint: { "line-color": ["get", "c"], "line-width": ["get", "w"] }, layout: { "line-cap": "round", "line-join": "round" } }]);
  drawRouteEnds(); renderRoutes();
  setSlider({ max: L_.length - 1, value: S.leadIdx ?? 5, label: v => `+${L_[v]} min · T+${D.fc.t0_min + L_[v]}`, onChange: v => {
    S.leadIdx = v; mkSet(roads, roadFeats(v));
    const counts = { Passable: 0, Degraded: 0, High: 0, Impassable: 0 }, rows = [];
    Object.values(rr).forEach(r => { const dm = r.expected_by_lead_m[v], st = roadStatus(dm, S.vehicle); counts[st]++; rows.push({ r, st, dm }); });
    $("#roadKpi").innerHTML = Object.entries(counts).map(([k, n]) => `<div class="kpi"><small>${k === "High" ? "High risk" : k}</small><b style="color:${STATUS_COL[k]}">${n}</b></div>`).join("");
    rows.sort((a, b) => b.dm - a.dm);
    $("#roadTbl").innerHTML = `<tr><th>Segment</th><th>Status</th><th class="num">Depth</th><th class="num">P&gt;10</th><th class="num">10 cm</th></tr>` +
      rows.slice(0, 7).map(({ r, st, dm }) => `<tr><td>${r.name || r.id}</td><td><span class="st ${st}">${st === "High" ? "high risk" : st}</span></td><td class="num">${fmt(dm * 100)} cm</td><td class="num">${pct(r.p_exceed["10cm"])}</td><td class="num">${r.time_to_threshold_min != null ? "+" + r.time_to_threshold_min : "–"}</td></tr>`).join("");
  } });
  // building access (Module R)
  const ttt = dec(FC().ttt_min), pr = dec(FC().p_reach);
  const crit = D.blocks.map(b => {
    const c = cellOfLL(b.lat, b.lon); let t = 255, p = 0, tMax = 0, dry = false;
    if (c) for (let di = -6; di <= 6; di++) for (let dj = -6; dj <= 6; dj++) {
      const i = c.i + di, j = c.j + dj; if (i < 0 || j < 0 || i >= G.ny || j >= G.nx) continue; const k = i * G.nx + j;
      if (!G.wet[k] || Math.hypot(di, dj) * 5 > 30) continue; t = Math.min(t, ttt[k]); p = Math.max(p, pr[k] / 100);
      if (ttt[k] === 255 || pr[k] < 30) dry = true; else tMax = Math.max(tMax, ttt[k]);
    }
    return { b, t, p, risk: t < 255 && p >= 0.3, alt: dry ? "stays open 3 h" : `until +${tMax} min` };
  }).sort((a, b) => a.t - b.t);
  $("#critTbl").innerHTML = `<tr><th>Building</th><th>First access cut</th><th>Other access</th><th class="num">P</th></tr>` + crit.map(c => `<tr><td>${c.b.name} block <span class="muted small">${c.b.floors}</span></td><td>${c.risk ? `<span class="st High">in ${c.t} min</span>` : '<span class="st OK">clear</span>'}</td><td class="small">${c.risk ? c.alt : "–"}</td><td class="num">${pct(c.p)}</td></tr>`).join("");
  mkGeo(FCOL(crit.map(c => pt(c.b.lat, c.b.lon, { n: c.b.name, c: c.risk ? COL.orange : COL.green, r: 7 }))), [circleLayer({ "circle-stroke-color": COL.paper, "circle-stroke-width": 2 })],
    { tip: p => `<b>${p.n} block</b>` });
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
  for (const [c, cls, lab] of [[S.route.origin, "a", "A"], [S.route.dest, "b", "B"]]) if (c) mkMarker(cellLL(c.i, c.j), `<span class="pin ${cls}">${lab}</span>`);
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
  if (!o || !d) return toast("Pick A and B first");
  const [deg, imp] = vehicleThr(S.vehicle), tolP = { low: 0.1, medium: 0.3, high: 0.6 }[S.route.tol || "low"];
  const dep = S.route.dep || 0, L_ = LEADS(), speed = { "two-wheeler": 4, car: 4, ambulance: 5, bus: 3, "fire truck": 3.5 }[S.vehicle];
  const closed = closedCells(), thrKey = deg >= .25 ? "30" : deg >= .15 ? "20" : "10";
  const exp = L_.map((_, l) => dec(FC().expected_cm[l])), pex = L_.map((_, l) => dec(FC().exceed[thrKey][l]));
  const atTime = (arrs, k, tmin) => { if (tmin < L_[0]) return arrs[0][k]; let l = 0; while (l < L_.length - 1 && L_[l + 1] <= tmin) l++; if (l >= L_.length - 1) return arrs[l][k]; const w = (tmin - L_[l]) / (L_[l + 1] - L_[l]); return arrs[l][k] * (1 - w) + arrs[l + 1][k] * w; };
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
        const tArr = dep + (tt[k] + dt) / 60, dm = atTime(exp, nk, tArr) / 100, pe = atTime(pex, nk, tArr) / 100;
        if (dm >= imp || (pe > tolP && dm >= deg)) continue;                  // impassable when we would get there
        const cost = dt * (1 + 3 * dm / deg + 4 * pe) * penalty[nk];
        if (c + cost < dist[nk]) { dist[nk] = c + cost; tt[nk] = tt[k] + dt; prev[nk] = k; push([dist[nk], nk]); }
      }
    }
    if (!isFinite(dist[d.k])) break;
    const path = []; for (let k = d.k; k !== -1; k = prev[k]) path.push(k); path.reverse();
    let maxD = 0, maxP = 0, len = 0;
    path.forEach((k, n) => { const tmin = dep + tt[k] / 60; maxD = Math.max(maxD, atTime(exp, k, tmin)); maxP = Math.max(maxP, atTime(pex, k, tmin) / 100); penalty[k] *= 2.2;
      if (n) { const a = path[n - 1]; len += 5 * Math.hypot(((k / G.nx) | 0) - ((a / G.nx) | 0), k % G.nx - a % G.nx); } });
    if (results.some(x => x.path.length === path.length && x.path.every((v, q) => v === path[q]))) continue;
    results.push({ path, eta: tt[d.k] / 60, len, maxD, maxP, thrKey });
  }
  S.route.results = results;
  audit("route computed", `${S.vehicle}, leave +${dep} min, ${results.length} alternatives`);
  if (!results.length) toast("No passable route for this vehicle at that time");
  renderRoutes();
}
const ROUTE_COL = [COL.teal, COL.paper, COL.amber];
function renderRoutes() {
  const out = $("#routeOut"); if (!out) return;
  mkSet(S.route.layerId, FCOL(S.route.results.map((r, i) => line(r.path.map(k => cellLL((k / G.nx) | 0, k % G.nx)), { c: ROUTE_COL[i], w: 5 - i })).reverse()));
  if (!S.route.results.length) { out.innerHTML = `<div class="small muted">Routes skip any cell predicted impassable for this vehicle at the moment it would get there.</div>`; return; }
  out.innerHTML = `<table><tr><th>Route</th><th class="num">ETA</th><th class="num">Length</th><th class="num">Deepest</th><th class="num">P&gt;${S.route.results[0].thrKey}</th></tr>` +
    S.route.results.map((r, i) => `<tr><td><span style="display:inline-block;width:14px;height:3px;background:${ROUTE_COL[i]};vertical-align:middle;margin-right:6px"></span>${["Lowest risk", "Second", "Third"][i]}</td><td class="num">${fmt(r.eta, 1)} min</td><td class="num">${Math.round(r.len)} m</td><td class="num">${fmt(r.maxD)} cm</td><td class="num">${pct(r.maxP)}</td></tr>`).join("") +
    `</table><div class="row" style="margin-top:10px;justify-content:space-between"><button class="btn sm ghost" id="expRoute">Export GeoJSON</button><span class="small muted">No route is guaranteed dry.</span></div>`;
  $("#expRoute").onclick = () => { download("routes.geojson", JSON.stringify({ type: "FeatureCollection", features: S.route.results.map((r, i) => ({ type: "Feature", properties: { rank: i + 1, eta_min: +r.eta.toFixed(1), length_m: Math.round(r.len), max_depth_cm: +r.maxD.toFixed(0), p_exceed: +r.maxP.toFixed(2), vehicle: S.vehicle }, geometry: { type: "LineString", coordinates: r.path.map(k => { const ll = cellLL((k / G.nx) | 0, k % G.nx); return [+ll[1].toFixed(6), +ll[0].toFixed(6)]; }) } })) }, null, 1)); audit("export", "routes.geojson"); };
}
function download(name, text, type = "application/json") { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([text], { type })); a.download = name; a.click(); }

const SCEN = [["baseline", "Baseline", "forecast storm, network as designed"], ["rain_plus20", "Rain +20%", "same storm, 20% heavier"], ["capacity_minus50", "Drains at half capacity", "every pipe 50% blocked"],
  ["pump_failure", "Pump P-60 fails", "sump fills, no lift to outfall"], ["downstream_plus20", "Nala +2.0 m", "outfalls back up from the receiving drain"]];
const ACTIONS = [["state_blocked40", "Do nothing (drains ~40% blocked)", 0, 0], ["act_pump_on", "Run pump P-60 continuously", 6000, 5], ["act_clear", "Emergency drain jetting", 45000, 90], ["act_clear_pump", "Jetting + pump", 51000, 90]];
VIEWS.actions = () => {
  const P = $("#panel"), sc = D.scen.scenarios, base = sc.baseline;
  const row = ([k, lab, sub]) => { const s = sc[k]; const d = s.flooded_m2 - base.flooded_m2;
    return `<div class="item ${S.scen === k ? "on" : ""}" data-k="${k}"><b>${lab}</b> <span class="small muted">— ${sub}</span>
      <div class="small" style="margin-top:3px">flooded <b>${m2(s.flooded_m2)}</b> ${k !== "baseline" ? `<b style="color:${d > 0 ? COL.red : COL.green}">${d >= 0 ? "+" : ""}${m2(d)}</b>` : ""} · &gt;30 cm ${m2(s.severe_m2)} · peak ${fmt(s.peak_depth_m * 100)} cm · surcharged ${s.surcharged_nodes} · overflow ${fmt(s.overflow_m3)} m³</div></div>`; };
  const bad = sc.state_blocked40;
  const acts = ACTIONS.map(([k, lab, cost, mins]) => { const s = sc[k]; const benefit = bad.flooded_m2 - s.flooded_m2; return { k, lab, cost, mins, s, benefit, sur: s.surcharged_nodes, score: (benefit + 200 * (bad.surcharged_nodes - s.surcharged_nodes)) / (1 + cost / 10000) }; });
  const ranked = acts.slice(1).sort((a, b) => b.score - a.score);
  P.innerHTML = `
  <div class="card"><h3>What if… ${tag("modelled")}</h3><div class="small muted" style="margin-bottom:6px">Each scenario is a full coupled 1D/2D run of the same storm.</div><div class="list" id="scList">${SCEN.map(row).join("")}</div>
    <label class="switch" style="margin-top:12px"><input type="checkbox" id="diffT" ${S.scenDiff ? "checked" : ""}/><i></i><span>Show change against baseline</span></label>
    <div class="row" style="margin-top:12px"><label class="field"><span>Close a road for routing</span><select id="closeR"><option value="">choose segment…</option>${F().flood.roads.map(r => `<option value="${r.id}">${r.name || r.id}${S.route.closed.has(r.id) ? " (closed)" : ""}</option>`).join("")}</select></label></div></div>
  <div class="card"><h3>Interventions ${tag("modelled")}</h3>
    <div class="small muted" style="margin-bottom:8px">Drainage health suggests the drains are about 40% blocked. Candidate actions, each simulated:</div>
    <table><tr><th>Action</th><th class="num">Less flooding</th><th class="num">Surch.</th><th class="num">₹</th><th class="num">Takes</th></tr>
    ${acts.map(a => `<tr class="actrow" data-k="${a.k}" style="cursor:pointer"><td>${a.lab}</td><td class="num" style="color:${a.benefit > 0 ? COL.green : "inherit"}">${a.benefit ? m2(a.benefit) : "–"}</td><td class="num">${a.sur}</td><td class="num">${a.cost ? a.cost.toLocaleString() : "–"}</td><td class="num">${a.mins ? a.mins + " min" : "–"}</td></tr>`).join("")}</table>
    <div style="margin-top:12px;font:400 17px/1.3 var(--serif)">Recommend: ${ranked[0].lab.toLowerCase()}.</div>
    <div class="small muted">Cuts flooded area by ${m2(ranked[0].benefit)} and surcharged nodes from ${bad.surcharged_nodes} to ${ranked[0].sur}.</div>
    <div class="row" style="margin-top:12px"><button class="btn" id="approve" ${S.approvals.action ? "disabled" : ""}>${S.approvals.action ? "Approved · dispatched" : "Request approval"}</button><span class="small muted">Nothing runs without a person signing off.</span></div></div>
  <div class="card"><h3>Where to add sensors ${tag("derived")}</h3><table id="sensRec"></table></div>`;
  P.querySelectorAll("#scList .item, .actrow").forEach(el => el.onclick = () => { S.scen = el.dataset.k; audit("scenario viewed", el.dataset.k); go("actions"); });
  $("#diffT").onchange = e => { S.scenDiff = e.target.checked; go("actions"); };
  $("#closeR").onchange = e => { const id = e.target.value; if (!id) return; S.route.closed.has(id) ? S.route.closed.delete(id) : S.route.closed.add(id); audit("road closure toggled", id); toast(`${id} ${S.route.closed.has(id) ? "closed" : "reopened"} — routing will respect it`); go("actions"); };
  $("#approve").onclick = () => { if (!confirmRole(["Flood Control Operator", "System Administrator", "Infrastructure Engineer"])) return; S.approvals.action = 1; audit("action approved", ranked[0].lab); toast(`Approved: ${ranked[0].lab}`); go("actions"); };
  // sensor placement: greedy on forecast uncertainty around candidate nodes
  const a90 = dec(FC().peak_p90_cm), aE = dec(FC().peak_cm), spread = k => Math.max(a90[k] - aE[k], 0);
  const have = D.twin.sensors.map(s => [s.lat, s.lon]);
  const cand = D.net.nodes.filter(n => n.kind !== "outfall" && !D.twin.sensors.some(s => s.node === n.id)).map(n => {
    const c = cellOfLL(n.lat, n.lon); let u = 0; if (c) for (let di = -4; di <= 4; di++) for (let dj = -4; dj <= 4; dj++) { const i = c.i + di, j = c.j + dj; if (i >= 0 && j >= 0 && i < G.ny && j < G.nx && G.wet[i * G.nx + j]) u += spread(i * G.nx + j) + 2 * D.net.live.node_fill[K0()][n.id]; }
    return { n, u };
  });
  const picks = [], tot = cand.reduce((a, c) => a + c.u, 0) || 1;
  for (let r = 0; r < 3; r++) {
    let best = null; for (const c of cand) { if (picks.includes(c)) continue; const near = [...have, ...picks.map(p => [p.n.lat, p.n.lon])].some(([a, b]) => distM(a, b, c.n.lat, c.n.lon) < 60); const g = c.u * (near ? .35 : 1); if (!best || g > best.g) best = { g, c }; }
    if (best) { best.c.gain = best.g; picks.push(best.c); }
  }
  $("#sensRec").innerHTML = `<tr><th>#</th><th>Location</th><th class="num">Uncertainty cut</th></tr>` + picks.map((p, i) => `<tr><td>${i + 1}</td><td>N-${p.n.id} · ${p.n.kind}</td><td class="num">${fmt(100 * p.gain / tot * 3, 0)}%</td></tr>`).join("");
  picks.forEach((p, i) => mkMarker([p.n.lat, p.n.lon], `<span class="pin s">S${i + 1}</span>`, "Suggested water-level sensor"));
  const s = sc[S.scen];
  $("#timebar").classList.add("hidden");
  const name = SCEN.concat(ACTIONS.map(x => [x[0], x[1]])).find(x => x[0] === S.scen)[1];
  if (S.scenDiff) { const a = dec(s.max_depth_cm), b = dec(base.max_depth_cm);
    paint(k => diffCol(a[k] - b[k]), k => Math.abs(a[k] - b[k]) >= 2 ? { h: Math.abs(a[k] - b[k]) / 100 * WATER_EXAG * 1.5, c: a[k] > b[k] ? COL.red : COL.green } : null);
    legendKeys("Change in peak depth · " + name, [[COL.red, "deeper"], [COL.green, "shallower"]]); }
  else { const a = dec(s.max_depth_cm); paint(k => depthCol(a[k]), depthWater(a)); legendDepth("Peak depth · " + name); }
};
function confirmRole(allowed) { if (allowed.includes(S.role)) return true; toast(`${S.role} cannot approve actions`); audit("approval denied", S.role); return false; }

VIEWS.valid = () => {
  const P = $("#panel"), v = (D.val.by_cycle || {})[D.fc.t0_min] || D.val.verification, sm = D.val.surrogate, b = D.scen.baselines, tw = D.twin;
  const fl = Object.fromEntries(v.flood.map(r => [r.lead_min, r]));
  P.innerHTML = `
  <div class="card"><h3>Which parts matter ${tag("modelled")}</h3>
    <table><tr><th>Model</th><th class="num">CSI</th><th class="num">Prec.</th><th class="num">Recall</th><th class="num">MAE cm</th></tr>
    ${[["B1", "Rain threshold"], ["B2", "+ terrain"], ["B3", "+ runoff"], ["B4", "+ drains, no 2D"], ["B5", "Full coupled 1D/2D"]].map(([k, n]) => `<tr><td><b>${k}</b> <span class="muted">${n}</span></td><td class="num">${fmt(b[k].csi, 2)}</td><td class="num">${fmt(b[k].precision, 2)}</td><td class="num">${fmt(b[k].recall, 2)}</td><td class="num">${fmt(b[k].depth_mae_m * 100, 1)}</td></tr>`).join("")}
    <tr><td><b>B6</b> <span class="muted">+ assimilation</span></td><td colspan="4" class="small">sensor error ${fmt(tw.rmse.open_loop_m * 100, 1)} → ${fmt(tw.rmse.assimilated_m * 100, 1)} cm</td></tr>
    <tr><td><b>B7</b> <span class="muted">+ adaptive forecast</span></td><td colspan="4" class="small">flood CSI ${fmt(fl[60]?.csi_10cm, 2)} at +60 · ${fmt(fl[180]?.csi_10cm, 2)} at +180 min</td></tr></table>
    <div class="small muted" style="margin-top:8px">B1–B4 scored against B5 on the same storm.</div></div>
  <div class="card"><h3>Surrogate against persistence ${tag("modelled")}</h3><canvas id="cSur"></canvas>
    <div class="small muted" style="margin-top:6px">${sm.arch} · ${sm.params.toLocaleString()} parameters · ${sm.training.train_windows.toLocaleString()} training windows · scored on held-out and out-of-range storms.</div></div>
  <div class="card"><h3>Forecast issued T+${v.t0} ${tag("modelled")}</h3>
    <table><tr><th>Lead</th><th class="num">Rain CSI</th><th class="num">Persist.</th><th class="num">Flood CSI</th><th class="num">Brier</th><th class="num">P10–90</th></tr>
    ${v.rain.map(r => { const f = fl[r.lead_min] || {}; return `<tr><td>+${r.lead_min}</td><td class="num">${fmt(r.csi_1mmh, 2)}</td><td class="num">${fmt(r.csi_1mmh_persistence, 2)}</td><td class="num">${fmt(f.csi_10cm, 2)}</td><td class="num">${fmt(f.brier_10cm, 3)}</td><td class="num">${pct(f.p10_p90_coverage)}</td></tr>`; }).join("")}</table>
    <div class="kpis" style="margin-top:12px"><div class="kpi"><small>Warned in time</small><b class="ok">${pct(v.early_warning.hit_rate)}</b></div><div class="kpi"><small>False alarms</small><b>${pct(v.early_warning.false_alarm_ratio)}</b></div>
    <div class="kpi"><small>Median warning</small><b>${fmt(v.early_warning.median_warning_lead_min)} min</b></div><div class="kpi"><small>Cells checked</small><b>${v.early_warning.cells_crossing_after_t0}</b></div></div>
    <div class="small muted" style="margin-top:8px">Replay: ${v.event.kind} storm (seed ${v.event.seed}) moving ${v.event.steering_kmh.map(x => fmt(x, 1)).join(", ")} km/h. Scores are against the reference run, not observed floods. The P10–P90 band is still too narrow.</div></div>
  <div class="card"><h3>Run record</h3><pre>${JSON.stringify(F().provenance, (k, x) => k === "terrain" ? undefined : x, 1)}</pre>
    <button class="btn sm ghost" id="dlProv" style="margin-top:8px">Download</button></div>`;
  $("#dlProv").onclick = () => { download(`${F().forecast_id}_provenance.json`, JSON.stringify(F().provenance, null, 1)); audit("export", "provenance"); };
  const t = sm.metrics.test, o = sm.metrics.ood;
  chart("cSur", { type: "line", data: { labels: t.lead_min.map(l => "+" + l), datasets: [
    { label: "held-out", data: t.csi_10cm, borderColor: COL.teal, pointRadius: 0, borderWidth: 2 }, { label: "out-of-range", data: o.csi_10cm, borderColor: COL.paper, pointRadius: 0, borderWidth: 1.5 },
    { label: "persistence", data: t.csi_10cm_persistence, borderColor: COL.orange, borderDash: [4, 3], pointRadius: 0, borderWidth: 1.2 }] },
    options: { scales: { y: { min: 0, max: 1, title: { display: true, text: "CSI at 10 cm" } } } } });
  $("#timebar").classList.add("hidden");
  const d = dec(FC().p90_cm[LEADS().length - 1]); paint(k => depthCol(d[k]), depthWater(d)); legendDepth("P90 depth at +180 min");
};

const API = [
  ["GET", "/api/v1/observations/status", () => F().quality], ["GET", "/api/v1/rainfall/forecast", () => F().rainfall],
  ["GET", "/api/v1/twin/state", () => F().flood.twin_state], ["GET", "/api/v1/twin/health", () => healthCard()],
  ["GET", "/api/v1/flood/forecast", () => ({ issued_t_min: F().issued_t_min, lead_min: F().flood.lead_min, domain: F().flood.domain, exceedance_area_m2: F().flood.exceedance_area_m2 })],
  ["GET", "/api/v1/flood/hotspots", () => F().flood.hotspots], ["GET", "/api/v1/roads/impact", () => F().flood.roads.slice(0, 5)],
  ["GET", "/api/v1/drainage/anomalies", () => D.twin.anomalies], ["POST", "/api/v1/routing/time-dependent", () => S.route.results.map(r => ({ eta_min: r.eta, length_m: r.len, max_depth_cm: r.maxD, p_exceed: r.maxP }))],
  ["POST", "/api/v1/scenarios/simulate", () => Object.fromEntries(Object.entries(D.scen.scenarios).map(([k, s]) => [k, { flooded_m2: s.flooded_m2, peak_depth_m: s.peak_depth_m, surcharged_nodes: s.surcharged_nodes }]))],
  ["GET", "/api/v1/validation/metrics", () => ({ early_warning: D.val.verification.early_warning, rain: D.val.verification.rain })]];
const ROLES = { "System Administrator": "live forecast prob drain impact actions valid system", "Flood Control Operator": "live forecast prob drain impact actions valid system",
  "Emergency Dispatcher": "live forecast prob impact", "Model Engineer": "live forecast prob drain valid system", "Infrastructure Engineer": "live drain actions valid", "Public Viewer": "live forecast impact" };
VIEWS.system = () => {
  const P = $("#panel"), f = F();
  const steps = Object.entries(f.timings_s).filter(([k]) => k !== "total").map(([k, v], i, a) => [k, v - (i ? a[i - 1][1] : 0)]);
  const tot = f.timings_s.total;
  P.innerHTML = `
  <div class="card"><h3>The five-minute loop</h3>
    ${steps.map(([k, v], i) => `<div style="margin:9px 0"><div class="row" style="margin:0 0 4px;justify-content:space-between"><span class="small"><span style="color:var(--orange);font-family:var(--mono)">${String(i + 1).padStart(2, "0")}</span>&nbsp; ${{ ingest_qc: "Ingest + quality control", mode_bias: "Source choice + gauge bias", nowcast: "Rain ensemble nowcast", twin_state: "Twin state update", surrogate: "Surrogate flood ensemble", adaptive_roads: "Hotspot physics + road impact" }[k] || k}</span><span class="small" style="font-family:var(--mono)">${fmt(v, 1)} s</span></div><div class="bar"><div style="width:${100 * v / tot}%"></div></div></div>`).join("")}
    <div class="row" style="margin-top:12px;justify-content:space-between"><b>Total</b><b style="font-family:var(--mono)">${fmt(tot, 1)} s of a 300 s budget</b></div></div>
  <div class="card"><h3>API</h3><div class="list" id="apiList">${API.map(([m, p], i) => `<div class="item" data-i="${i}"><span class="st ${m === "GET" ? "VALID" : "SUSPECT"}">${m}</span> <code>${p}</code></div>`).join("")}</div><pre id="apiOut" style="margin-top:10px">Pick an endpoint to see its response.</pre></div>
  <div class="card"><h3>Alerts and data exchange</h3><div class="row">
    <button class="btn sm" id="cap">CAP 1.2 alert</button><button class="btn sm ghost" id="geo">Road impact GeoJSON</button><button class="btn sm ghost" id="sta">SensorThings</button></div><pre id="capOut" class="hidden"></pre></div>
  <div class="card"><h3>Who sees what</h3><table><tr><th>Role</th><th>Views</th></tr>${Object.entries(ROLES).map(([r, v]) => `<tr><td>${r}${r === S.role ? ' <span style="color:var(--orange)">●</span>' : ""}</td><td style="font-family:var(--mono)">${v.split(" ").map(x => ({ live: "A", forecast: "B", prob: "C", drain: "D", impact: "E", actions: "F", valid: "G", system: "H" })[x]).join(" ")}</td></tr>`).join("")}</table></div>
  <div class="card"><h3>Audit log</h3><table>${S.audit.slice(0, 14).map(a => `<tr><td class="small muted" style="white-space:nowrap">${a.t}</td><td class="small">${a.role}</td><td class="small">${a.action}<br><span class="muted">${a.detail}</span></td></tr>`).join("") || "<tr><td class='muted'>Nothing yet</td></tr>"}</table></div>`;
  $("#apiList").querySelectorAll(".item").forEach(el => el.onclick = () => { const [m, p, fn] = API[+el.dataset.i]; $("#apiOut").textContent = `${m} ${p}\n200 OK\n\n` + JSON.stringify(fn(), null, 1); audit("api call", p); });
  $("#cap").onclick = () => { const x = capXml(); $("#capOut").textContent = x; $("#capOut").classList.remove("hidden"); download("drishti_alert.cap.xml", x, "application/xml"); audit("CAP alert exported", f.forecast_id); };
  $("#geo").onclick = () => { const rr = roadRows(); download("road_impact.geojson", JSON.stringify({ type: "FeatureCollection", features: D.roads.features.filter(ft => rr["R-" + ft.properties.osm_id]).map(ft => { const r = rr["R-" + ft.properties.osm_id]; return { type: "Feature", geometry: ft.geometry, properties: { id: r.id, name: r.name, expected_peak_m: r.expected_peak_m, p_exceed: r.p_exceed, time_to_threshold_min: r.time_to_threshold_min, status_car: roadStatus(r.expected_peak_m, "car") } }; }) })); audit("export", "road_impact.geojson"); };
  $("#sta").onclick = () => { const tw = D.twin; $("#capOut").textContent = JSON.stringify({ "@iot.id": "Datastream/water-level", value: tw.sensors.map((s, i) => ({ Thing: s.id, phenomenonTime: `T+${D.fc.t0_min}`, result: tw.observed[i][K0()], resultQuality: s.status, unitOfMeasurement: "m" })) }, null, 1); $("#capOut").classList.remove("hidden"); };
  clearOverlay(); $("#timebar").classList.add("hidden"); legendKeys("Drainage network", [[COL.green, "pipes and inlets"]]);
  mkGeo(FCOL(D.net.edges.map(e => { const a = D.net.nodes[e.u], b = D.net.nodes[e.v]; return line([[a.lat, a.lon], [b.lat, b.lon]], {}); })), [{ type: "line", paint: { "line-color": COL.green, "line-width": 1.5, "line-opacity": .6 } }]);
};
function capXml() {
  const f = F(), hs = f.flood.hotspots, now = new Date().toISOString().replace(/\.\d+Z/, "+00:00");
  const area = hs.map((h, i) => { const b = hotspotBounds(h); return `  <area><areaDesc>Hotspot H${i + 1} (P&gt;20cm ${pct(h.p_exceed_20cm_max)})</areaDesc><polygon>${b[0][0].toFixed(5)},${b[0][1].toFixed(5)} ${b[0][0].toFixed(5)},${b[1][1].toFixed(5)} ${b[1][0].toFixed(5)},${b[1][1].toFixed(5)} ${b[1][0].toFixed(5)},${b[0][1].toFixed(5)} ${b[0][0].toFixed(5)},${b[0][1].toFixed(5)}</polygon></area>`; }).join("\n");
  return `<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
 <identifier>drishti-${f.forecast_id}</identifier><sender>drishti@kiet.edu</sender><sent>${now}</sent>
 <status>Exercise</status><msgType>Alert</msgType><scope>Restricted</scope>
 <info><category>Met</category><event>Urban waterlogging</event><urgency>Expected</urgency><severity>Moderate</severity><certainty>Likely</certainty>
  <headline>Street flooding expected on KIET campus within ${hs.length ? Math.min(...hs.map(h => h.time_to_threshold_min ?? 999)) : "–"} min</headline>
  <description>${hs.length} hotspots. Forecast health ${f.health.status}. Probabilities come from a 20-member ensemble.</description>
  <instruction>Avoid flagged roads; use the lowest-risk routes in the Drishti planner.</instruction>
${area}
 </info>
</alert>`;
}

// ------------------------------------------------------------------ shell
function go(view) {
  if (!ROLES[S.role].split(" ").includes(view)) { toast(`${S.role} cannot open this view`); return; }
  S.view = view; stopPlay();
  document.querySelectorAll("#nav button").forEach(b => b.classList.toggle("on", b.dataset.view === view));
  mkClear(); S.selMarker = null;
  Object.values(S.charts).forEach(c => c.destroy()); S.charts = {};
  $("#timebar").classList.remove("hidden");
  const [l, n, sub] = VIEW_META[view]; $("#vtLetter").textContent = l; $("#vtName").textContent = n; $("#vtSub").textContent = sub + " · issued T+" + D.fc.t0_min;
  VIEWS[view]();
  $("#panel").scrollTop = 0;
}
function refreshHeader() {
  const h = F().health, hc = healthCard();
  const p = $("#healthPill"); p.className = "state " + (h.status === "OPERATIONAL" ? "ok" : "bad"); p.textContent = `${h.status} · ${h.rain_source_mode}`;
  const bn = $("#banner"); bn.classList.toggle("hidden", !h.degraded);
  bn.innerHTML = h.degraded ? `DEGRADED FORECAST — ${h.reasons.join(" · ")} · uncertainty ×${h.uncertainty_inflation}` : "";
  const mh = $("#miniHealth"); mh.className = "mini" + (h.degraded ? " bad" : "");
  mh.innerHTML = `<div class="h"><b>Forecast health</b><span class="st ${h.status}">${h.status}</span></div>
    <div class="r"><span>rain source</span><span>${h.rain_source_mode}</span></div><div class="r"><span>gauges valid</span><span>${hc.gauges_valid}</span></div>
    <div class="r"><span>sensors</span><span>${hc.sensor_health.split(" ")[0]}</span></div><div class="r"><span>uncertainty</span><span>${hc.uncertainty}${h.uncertainty_inflation > 1 ? " ×" + h.uncertainty_inflation : ""}</span></div>
    <div class="r"><span>issued</span><span>T+${D.fc.t0_min} · ${fmt(F().timings_s.total, 0)} s</span></div>`;
  document.querySelectorAll("#nav button").forEach(b => b.classList.toggle("locked", !ROLES[S.role].split(" ").includes(b.dataset.view)));
}
const HOME = { center: [77.4978, 28.7527], zoom: 16.9, pitch: 52, bearing: -28 };
function buildBaseMap() {
  map = new maplibregl.Map({ container: "map", attributionControl: { compact: true }, maxPitch: 75, ...HOME,
    style: { version: 8, glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
      sources: { sat: { type: "raster", tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"], tileSize: 256, maxzoom: 19, attribution: "Imagery © Esri" } },
      layers: [{ id: "bg", type: "background", paint: { "background-color": "#0a1218" } },
        { id: "sat", type: "raster", source: "sat", paint: { "raster-saturation": -0.45, "raster-brightness-max": 0.62, "raster-contrast": 0.08 } }] } });
  map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "bottom-right");
  return new Promise(r => { if (map.isStyleLoaded()) r(); else map.once("style.load", r); });
}
function addStaticLayers() {
  const allRoads = FCOL(D.roads.features.filter(f => !["footway", "steps", "path"].includes(f.properties.highway)));
  map.addSource("allroads", { type: "geojson", data: allRoads });
  map.addLayer({ id: "chart-roads", type: "line", source: "allroads", layout: { visibility: "none", "line-cap": "round" }, paint: { "line-color": "#34444f", "line-width": ["interpolate", ["linear"], ["zoom"], 14, 1, 18, 7] } });
  map.addSource("flood", { type: "image", url: "data:image/gif;base64,R0lGODlhAQABAAAAACw=", coordinates: [[G.w, G.nn], [G.e, G.nn], [G.e, G.s], [G.w, G.s]] });
  map.addLayer({ id: "flood", type: "raster", source: "flood", paint: { "raster-opacity": 0, "raster-resampling": "linear", "raster-fade-duration": 0 } });
  map.addSource("campus", { type: "geojson", data: FCOL(D.bnd.features.slice(0, 1)) });
  map.addLayer({ id: "campus-glow", type: "line", source: "campus", paint: { "line-color": COL.paper, "line-width": 6, "line-opacity": .08, "line-blur": 4 } });
  map.addLayer({ id: "campus", type: "line", source: "campus", paint: { "line-color": COL.paper, "line-width": 1.2, "line-dasharray": [3, 2], "line-opacity": .75 } });
  const blds = FCOL(D.bld.features.filter(ft => ft.geometry.type !== "Point" && String(ft.properties.kind || "").includes("building")).map(ft => {
    const m = String(ft.properties.floors || "G+1").match(/\+(\d+)/); const fl = m ? +m[1] + 1 : 2;
    return { ...ft, properties: { ...ft.properties, h: fl * 3.6, name: ft.properties.real_name || ft.properties.sanctioned_name } };
  }));
  map.addSource("blds", { type: "geojson", data: blds });
  map.addSource("water", { type: "geojson", data: FCOL([]) });
  map.addLayer({ id: "water", type: "fill-extrusion", source: "water", paint: { "fill-extrusion-color": ["get", "c"], "fill-extrusion-height": ["get", "h"], "fill-extrusion-base": 0, "fill-extrusion-opacity": 0.82, "fill-extrusion-vertical-gradient": true } });
  map.addLayer({ id: "blds", type: "fill-extrusion", source: "blds", paint: { "fill-extrusion-color": "#c9c2b3", "fill-extrusion-height": ["get", "h"], "fill-extrusion-opacity": 0.78, "fill-extrusion-vertical-gradient": true } });
  map.addLayer({ id: "bld-label", type: "symbol", source: "blds", minzoom: 17, layout: { "text-field": ["get", "name"], "text-font": ["Open Sans Semibold"], "text-size": 11 }, paint: { "text-color": COL.ink, "text-halo-color": COL.paper, "text-halo-width": 1.5 } });
  map.setLight({ anchor: "viewport", color: "#fff5e6", intensity: 0.45, position: [1.3, 210, 40] });
}
function wireMap() {
  map.on("mousemove", e => {
    const ids = MK.hov.map(h => h.layer).filter(l => map.getLayer(l));
    const f = ids.length ? map.queryRenderedFeatures(e.point, { layers: ids })[0] : null;
    if (!f) { if (MK.tip) MK.tip.remove(); map.getCanvas().style.cursor = S.view === "forecast" || S.route.picking ? "crosshair" : ""; return; }
    const h = MK.hov.find(x => x.layer === f.layer.id);
    tipPop().setLngLat(e.lngLat).setHTML(h.tip(f.properties)).addTo(map); map.getCanvas().style.cursor = "pointer";
  });
  map.on("click", e => {
    const ll = { lat: e.lngLat.lat, lng: e.lngLat.lng };
    if (S.view === "impact" && S.route.picking) { const w = nearestWet(ll.lat, ll.lng); if (!w) return toast("Pick a point inside the campus"); S.route[S.route.picking === "origin" ? "origin" : "dest"] = w; S.route.picking = null; S.route.results = []; go("impact"); return; }
    const ids = MK.clk.map(h => h.layer).filter(l => map.getLayer(l));
    const f = ids.length ? map.queryRenderedFeatures(e.point, { layers: ids })[0] : null;
    if (f) { const html = MK.clk.find(x => x.layer === f.layer.id).fn(f.properties); if (html) new maplibregl.Popup({ offset: 10, maxWidth: "300px" }).setLngLat(e.lngLat).setHTML(html).addTo(map); return; }
    const c = llCell(ll); if (!c) return;
    if (S.view === "forecast") { S.sel = c; cellPanel(c); }
    else if (S.view === "live" || S.view === "prob") { S.sel = c; go("forecast"); cellPanel(c); }
  });
  $("#t3d").onclick = () => { S.w3d = !S.w3d; $("#t3d").classList.toggle("on", S.w3d); map.easeTo({ pitch: S.w3d ? 52 : 0, bearing: S.w3d ? -28 : 0, duration: 800 }); map.setLayoutProperty("blds", "visibility", S.w3d ? "visible" : "none"); go(S.view); };
  $("#tbase").onclick = () => { S.sat = !S.sat; $("#tbase").textContent = S.sat ? "Sat" : "Chart"; map.setLayoutProperty("sat", "visibility", S.sat ? "visible" : "none"); map.setLayoutProperty("chart-roads", "visibility", S.sat ? "none" : "visible"); };
  $("#treset").onclick = () => map.easeTo({ ...HOME, pitch: S.w3d ? HOME.pitch : 0, bearing: S.w3d ? HOME.bearing : 0, duration: 900 });
}
function chartTheme() {
  Chart.defaults.color = COL.mut; Chart.defaults.borderColor = "#1c2832";
  Chart.defaults.font.family = "'IBM Plex Mono', monospace"; Chart.defaults.font.size = 10;
  Chart.defaults.plugins.tooltip.backgroundColor = COL.ink; Chart.defaults.plugins.tooltip.borderColor = "#2d3e4b"; Chart.defaults.plugins.tooltip.borderWidth = 1;
  Chart.defaults.plugins.tooltip.cornerRadius = 0; Chart.defaults.elements.bar.borderRadius = 0;
}
async function init() {
  chartTheme();
  const ready = buildBaseMap();
  try { await load(); } catch (e) { $("#panel").innerHTML = `<div class="card"><h3>Data bundle not found</h3><div class="small">${e.message}. Serve the repository root with <code>python -m http.server 8123</code> and open /dashboard/.</div></div>`; return; }
  await ready;
  addStaticLayers(); wireMap();
  document.querySelectorAll("#nav button").forEach(b => b.onclick = () => go(b.dataset.view));
  $("#miniHealth").onclick = () => go("live");
  const cy = $("#cycle"); cy.innerHTML = D.idx.cycles.map(t => `<option value="${t}" ${t === D.idx.default ? "selected" : ""}>T+${t} min</option>`).join("");
  cy.onchange = async e => { await loadCycle(+e.target.value); S.route.results = []; S.sel = null; audit("replay cycle", "T+" + e.target.value); refreshHeader(); go(S.view); };
  $("#degradeToggle").onchange = e => { S.mode = e.target.checked ? "degraded" : "ok"; audit(e.target.checked ? "radar outage drill started" : "radar outage drill ended"); refreshHeader(); go(S.view); };
  $("#role").onchange = e => { S.role = e.target.value; audit("role switched", S.role); refreshHeader(); if (!ROLES[S.role].split(" ").includes(S.view)) go("live"); else go(S.view); };
  audit("session started", "forecast " + F().forecast_id);
  // deep links: #forecast, #prob&lead=6, #actions&scen=pump_failure&diff=1, #impact&drill=1
  const hp = new URLSearchParams(location.hash.slice(1).replace(/^([a-z]+)/, "view=$1"));
  if (hp.get("lead")) S.leadIdx = +hp.get("lead");
  if (hp.get("scen")) S.scen = hp.get("scen");
  if (hp.get("diff")) S.scenDiff = true;
  if (hp.get("layer")) S.layer = hp.get("layer");
  if (hp.get("drill")) { $("#degradeToggle").checked = true; S.mode = "degraded"; }
  refreshHeader(); go(VIEWS[hp.get("view")] ? hp.get("view") : "live");
}
init();
