/* Homepage: a live 3D replay of the simulated storm over the real campus terrain + page furniture. */
"use strict";
(async function () {
  const $ = s => document.querySelector(s);
  const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const b64 = s => { const b = atob(s), a = new Uint8Array(b.length); for (let i = 0; i < b.length; i++) a[i] = b.charCodeAt(i); return a; };
  const j = u => fetch(u).then(r => { if (!r.ok) throw new Error(u); return r.json(); });

  // ---------------------------------------------------------------- page furniture
  const nav = $(".nav");
  addEventListener("scroll", () => nav.classList.toggle("solid", scrollY > innerHeight * 0.6), { passive: true });
  document.querySelectorAll(".band .wrap > *, .loop li, .fig, .index li").forEach(el => el.classList.add("reveal"));
  const io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } }), { threshold: 0.15 });
  document.querySelectorAll(".reveal").forEach(el => io.observe(el));
  // deep links (#how, #numbers …) show their content at once; never leave text hidden
  const showAll = () => document.querySelectorAll(".reveal").forEach(el => el.classList.add("in"));
  if (location.hash) showAll();
  setTimeout(() => document.querySelectorAll(".reveal").forEach(el => { if (el.getBoundingClientRect().top < innerHeight) el.classList.add("in"); }), 1200);

  let grid, net;
  try { [grid, net] = await Promise.all([j("dashboard/data/grid.json"), j("dashboard/data/network.json")]); }
  catch (e) { $(".hud-note").textContent = "3D replay needs the data bundle — serve this folder over http (python -m http.server)."; return; }
  const bld = await j("data/campus_accurate.geojson").catch(() => ({ features: [] }));
  fillNumbers();

  // ---------------------------------------------------------------- grid geometry
  const NY = grid.ny, NX = grid.nx, DX = grid.dx_m, N = NY * NX;
  const dem = b64(grid.dem), dom = b64(grid.domain), road = b64(grid.road), bldM = b64(grid.building);
  const V = 1.6, WEXAG = 12;                                   // terrain and water vertical exaggeration
  const [[S_, W_], [N_, E_]] = grid.bounds, dlat = (N_ - S_) / NY, dlon = (E_ - W_) / NX;
  const X = j_ => (j_ - NX / 2 + 0.5) * DX, Z = i_ => (i_ - NY / 2 + 0.5) * DX;
  const llX = lon => (lon - W_) / dlon * DX - NX * DX / 2, llZ = lat => (N_ - lat) / dlat * DX - NY * DX / 2;
  const H = k => dem[k] / 20 * V;                               // metres above the lowest domain cell
  const live = net.live, T = live.depth_cm.length, frames = live.depth_cm.map(b64);

  const canvas = $("#scene");
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  const scene = new THREE.Scene();
  scene.fog = new THREE.Fog(0x0b1117, 520, 1250);
  const camera = new THREE.PerspectiveCamera(34, 1, 1, 4000);
  camera.position.set(330, 300, 470);
  const controls = new THREE.OrbitControls(camera, canvas);
  controls.target.set(-120, -10, 30);
  Object.assign(controls, { enableDamping: true, dampingFactor: 0.06, enableZoom: false, enablePan: false, autoRotate: !REDUCED, autoRotateSpeed: 0.35, minPolarAngle: 0.45, maxPolarAngle: 1.25 });

  scene.add(new THREE.HemisphereLight(0xdfe8ef, 0x1a140c, 0.62));
  const sun = new THREE.DirectionalLight(0xffd2a0, 0.95); sun.position.set(-320, 260, 140); scene.add(sun);
  scene.add(new THREE.AmbientLight(0x223040, 0.35));

  // ground plane + survey grid
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(2400, 2400), new THREE.MeshBasicMaterial({ color: 0x0c141a }));
  ground.rotation.x = -Math.PI / 2; ground.position.y = -1.2; scene.add(ground);
  const gh = new THREE.GridHelper(2400, 120, 0x1a2731, 0x141f27); gh.position.y = -1.1; scene.add(gh);

  // terrain mesh (vertex per cell centre)
  function gridGeometry() {
    const g = new THREE.BufferGeometry(), pos = new Float32Array(N * 3), idx = [];
    for (let i = 0; i < NY; i++) for (let jj = 0; jj < NX; jj++) { const k = i * NX + jj; pos[3 * k] = X(jj); pos[3 * k + 1] = H(k); pos[3 * k + 2] = Z(i); }
    for (let i = 0; i < NY - 1; i++) for (let jj = 0; jj < NX - 1; jj++) { const a = i * NX + jj, b = a + 1, c = a + NX, d = c + 1; idx.push(a, c, b, b, c, d); }
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3)); g.setIndex(idx); return g;
  }
  const tg = gridGeometry(), tcol = new Float32Array(N * 3);
  for (let k = 0; k < N; k++) {
    const c = !dom[k] ? [0.085, 0.12, 0.14] : road[k] ? [0.42, 0.40, 0.36] : bldM[k] ? [0.25, 0.24, 0.22] : [0.24, 0.27, 0.22];
    const shade = 0.85 + (dem[k] / 255) * 0.5; tcol.set(c.map(v => v * shade), 3 * k);
  }
  tg.setAttribute("color", new THREE.BufferAttribute(tcol, 3)); tg.computeVertexNormals();
  scene.add(new THREE.Mesh(tg, new THREE.MeshLambertMaterial({ vertexColors: true })));
  // contour-like wireframe over the campus domain
  const wire = new THREE.LineSegments(new THREE.WireframeGeometry(tg), new THREE.LineBasicMaterial({ color: 0x2b3a44, transparent: true, opacity: 0.18 }));
  wire.position.y = 0.05; scene.add(wire);

  // water surface
  const wg = gridGeometry(), wpos = wg.attributes.position.array, wcol = new Float32Array(N * 3);
  wg.setAttribute("color", new THREE.BufferAttribute(wcol, 3));
  const water = new THREE.Mesh(wg, new THREE.MeshPhongMaterial({ vertexColors: true, transparent: true, opacity: 0.86, shininess: 90, specular: 0x557788 }));
  scene.add(water);
  const RAMP = [[3, [0.74, 0.92, 0.95]], [10, [0.18, 0.77, 0.84]], [20, [0.12, 0.44, 0.85]], [30, [0.95, 0.72, 0.29]], [60, [0.90, 0.28, 0.30]]];
  const ramp = cm => { for (let q = 1; q < RAMP.length; q++) if (cm < RAMP[q][0]) { const t = (cm - RAMP[q - 1][0]) / (RAMP[q][0] - RAMP[q - 1][0]); return RAMP[q - 1][1].map((v, c) => v + (RAMP[q][1][c] - v) * t); } return RAMP[RAMP.length - 1][1]; };

  // buildings from the sanctioned footprints
  const bmat = new THREE.MeshStandardMaterial({ color: 0xd9d2c2, roughness: 0.92, metalness: 0 });
  const emat = new THREE.LineBasicMaterial({ color: 0x6f6a60 });
  bld.features.filter(f => f.geometry.type === "Polygon" && String(f.properties.kind || "").includes("building")).forEach(f => {
    const ring = f.geometry.coordinates[0], shape = new THREE.Shape();
    ring.forEach(([lon, lat], n) => { const x = llX(lon), z = llZ(lat); n ? shape.lineTo(x, -z) : shape.moveTo(x, -z); });
    const m = String(f.properties.floors || "G+1").match(/\+(\d+)/), h = (m ? +m[1] + 1 : 2) * 3.6;
    const geo = new THREE.ExtrudeGeometry(shape, { depth: h, bevelEnabled: false }); geo.rotateX(-Math.PI / 2);
    const [lon0, lat0] = ring[0], ci = Math.min(NY - 1, Math.max(0, Math.floor((N_ - lat0) / dlat))), cj = Math.min(NX - 1, Math.max(0, Math.floor((lon0 - W_) / dlon)));
    const base = H(ci * NX + cj) - 0.3;
    const mesh = new THREE.Mesh(geo, bmat); mesh.position.y = base; scene.add(mesh);
    const edges = new THREE.LineSegments(new THREE.EdgesGeometry(geo), emat); edges.position.y = base; scene.add(edges);
  });

  // drain network schematic (just above the ground)
  const nodeXYZ = net.nodes.map(n => { const x = llX(n.lon), z = llZ(n.lat), ci = Math.round((z + NY * DX / 2) / DX - 0.5), cj = Math.round((x + NX * DX / 2) / DX - 0.5);
    const k = Math.min(NY - 1, Math.max(0, ci)) * NX + Math.min(NX - 1, Math.max(0, cj)); return new THREE.Vector3(x, H(k) + 0.6, z); });
  const pg = new THREE.BufferGeometry().setFromPoints(net.edges.flatMap(e => [nodeXYZ[e.u], nodeXYZ[e.v]]));
  scene.add(new THREE.LineSegments(pg, new THREE.LineBasicMaterial({ color: 0x3fb68b, transparent: true, opacity: 0.55 })));
  const ng = new THREE.BufferGeometry().setFromPoints(nodeXYZ), ncol = new Float32Array(nodeXYZ.length * 3);
  ng.setAttribute("color", new THREE.BufferAttribute(ncol, 3));
  scene.add(new THREE.Points(ng, new THREE.PointsMaterial({ size: 4.5, vertexColors: true, sizeAttenuation: true })));

  // rain streaks
  const DROPS = 2600, rg = new THREE.BufferGeometry(), rpos = new Float32Array(DROPS * 6), rvel = new Float32Array(DROPS);
  for (let d = 0; d < DROPS; d++) { const x = (Math.random() - .5) * 620, y = Math.random() * 220, z = (Math.random() - .5) * 460; rpos.set([x, y, z, x - 0.8, y + 5, z], d * 6); rvel[d] = 90 + Math.random() * 50; }
  rg.setAttribute("position", new THREE.BufferAttribute(rpos, 3));
  const rain = new THREE.LineSegments(rg, new THREE.LineBasicMaterial({ color: 0xa9cfd6, transparent: true, opacity: 0.32 }));
  scene.add(rain);

  // ---------------------------------------------------------------- timeline + HUD
  const scrub = $("#scrub"); scrub.max = T - 1;
  const peak = Math.max(...live.rain_mmh);
  const svg = $("#hyeto"); svg.setAttribute("viewBox", `0 0 ${T} 26`);
  svg.innerHTML = live.rain_mmh.map((r, k) => `<rect x="${k + 0.15}" y="${26 - 24 * r / peak}" width="0.7" height="${24 * r / peak}" fill="${r > 40 ? "#ff7a1a" : "#2ec4d6"}" opacity=".75"/>`).join("");
  let f = REDUCED ? live.rain_mmh.indexOf(peak) + 6 : 0, playing = !REDUCED, lastInt = -1;
  const btn = $("#play");
  const setBtn = () => { btn.textContent = playing ? "❚❚" : "▶"; btn.setAttribute("aria-label", playing ? "Pause replay" : "Play replay"); };
  btn.onclick = () => { playing = !playing; setBtn(); };
  scrub.oninput = () => { f = +scrub.value; lastInt = -1; };
  setBtn();

  function applyFrame(ff) {
    const a = Math.floor(ff), b = Math.min(a + 1, T - 1), t = ff - a, A = frames[a], B = frames[b];
    let flooded = 0, deep = 0;
    for (let k = 0; k < N; k++) {
      const cm = A[k] * (1 - t) + B[k] * t, base = H(k);
      if (dom[k] && !bldM[k] && cm >= 3) {
        wpos[3 * k + 1] = base + 0.15 + cm / 100 * WEXAG; const c = ramp(cm); wcol[3 * k] = c[0]; wcol[3 * k + 1] = c[1]; wcol[3 * k + 2] = c[2];
        if (cm >= 10) flooded++; if (cm > deep) deep = cm;
      } else wpos[3 * k + 1] = base - 0.6;
    }
    wg.attributes.position.needsUpdate = true; wg.attributes.color.needsUpdate = true; wg.computeVertexNormals();
    const fill = live.node_fill[a];
    for (let n = 0; n < fill.length; n++) { const c = fill[n] >= 1 ? [0.9, 0.28, 0.3] : fill[n] > 0.6 ? [0.95, 0.72, 0.29] : [0.25, 0.71, 0.55]; ncol.set(c, 3 * n); }
    ng.attributes.color.needsUpdate = true;
    if (a !== lastInt) {
      lastInt = a; scrub.value = a;
      $("#hTime").textContent = `T+${live.times_min[a]} min`;
      $("#hRain").textContent = `${live.rain_mmh[a].toFixed(1)} mm/h`;
      $("#hArea").textContent = `${(flooded * DX * DX).toLocaleString()} m²`;
      $("#hDeep").textContent = `${Math.round(deep)} cm`;
      $("#hSur").textContent = fill.filter(x => x >= 1).length;
    }
    return live.rain_mmh[a] * (1 - t) + live.rain_mmh[b] * t;
  }

  function resize() { const w = canvas.clientWidth, h = canvas.clientHeight; renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); }
  addEventListener("resize", resize); resize();
  let visible = true;
  new IntersectionObserver(es => { visible = es[0].isIntersecting; }).observe(canvas);
  let prev = performance.now(), frameCount = 0;
  function tick(now) {
    requestAnimationFrame(tick);
    const dt = Math.min((now - prev) / 1000, 0.1); prev = now;
    if (!visible) return;
    if (playing) { f += dt * 1.15; if (f > T - 1) f = 0; }
    const rr = (frameCount++ % 2 === 0 || !playing) ? applyFrame(f) : live.rain_mmh[Math.floor(f)];
    // rain streaks: active count follows intensity
    const active = Math.min(DROPS, Math.floor(DROPS * Math.min(rr / 60, 1)));
    rg.setDrawRange(0, active * 2);
    for (let d = 0; d < active; d++) {
      const o = d * 6; let y = rpos[o + 1] - rvel[d] * dt * 2.2;
      if (y < 0) y += 220;
      rpos[o + 1] = y; rpos[o + 4] = y + 5;
    }
    rg.attributes.position.needsUpdate = true;
    controls.update();
    renderer.render(scene, camera);
  }
  requestAnimationFrame(tick);

  // ---------------------------------------------------------------- numbers + loop timings
  async function fillNumbers() {
    try {
      const [val, twin] = await Promise.all([j("dashboard/data/validation.json"), j("dashboard/data/twin.json")]);
      const sm = val.surrogate.metrics.test, v = (val.by_cycle && val.by_cycle["115"]) || val.verification;
      const set = (k, t) => document.querySelectorAll(`[data-f="${k}"]`).forEach(e => e.textContent = t);
      set("csi", sm.csi_10cm[sm.csi_10cm.length - 1].toFixed(2));
      set("csip", sm.csi_10cm_persistence[sm.csi_10cm_persistence.length - 1].toFixed(2));
      set("warn", Math.round(v.early_warning.hit_rate * 100) + "%");
      set("lead", Math.round(v.early_warning.median_warning_lead_min) + " min");
      set("far", Math.round(v.early_warning.false_alarm_ratio * 100) + "%");
      set("assim", Math.round(100 * (1 - twin.rmse.assimilated_m / twin.rmse.open_loop_m)) + "%");
      const idx = await j("dashboard/data/forecast_index.json");
      const fc = await j(`dashboard/data/forecast_${idx.default}.json`);
      const tm = fc.ok.forecast.timings_s, keys = ["ingest_qc", "mode_bias", "nowcast", "twin_state", "surrogate", "adaptive_roads"];
      const step = {}; keys.forEach((k, i) => step[k] = tm[k] - (i ? tm[keys[i - 1]] : 0));
      set("cycle", Math.round(tm.total) + " s");
      document.querySelectorAll(".loop .t").forEach(el => {
        const s = el.dataset.k.split(",").reduce((a, k) => a + step[k], 0);
        el.innerHTML = `<i></i>${s.toFixed(1)} s`;
        requestAnimationFrame(() => setTimeout(() => el.querySelector("i").style.width = Math.max(4, 100 * s / tm.total) + "%", 300));
      });
      $("#loopTotal").innerHTML = `Measured on the replay cycle at T+${idx.default}: <b>${tm.total.toFixed(1)} s</b> end to end, 20 members, on a laptop CPU.`;
    } catch (e) { /* numbers stay as dashes if the bundle is missing */ }
  }
})();
