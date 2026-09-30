// Records real clips of the running Drishti app (http://localhost:8123) with a visible fake cursor.
// usage: node record.js <clipName|all>
const puppeteer = require('puppeteer-core');
const fs = require('fs'), path = require('path'), { execFileSync } = require('child_process');
const B = 'http://localhost:8123/';
const OUT = process.env.OUT || 'clips';
const sleep = ms => new Promise(r => setTimeout(r, ms));

const CURSOR = `(() => {
  if (document.getElementById('__cur')) return;
  const s = document.createElement('style');
  s.textContent = '#__cur{position:fixed;left:0;top:0;width:28px;height:28px;z-index:2147483647;pointer-events:none;transform:translate(-100px,-100px);filter:drop-shadow(0 2px 4px rgba(0,0,0,.6))}' +
    '.__rip{position:fixed;width:44px;height:44px;margin:-22px 0 0 -22px;border:2px solid #ff7a1a;border-radius:50%;z-index:2147483646;pointer-events:none;animation:__r .6s ease-out forwards}' +
    '@keyframes __r{from{transform:scale(.3);opacity:1}to{transform:scale(1.4);opacity:0}}';
  document.head.appendChild(s);
  const c = document.createElement('div'); c.id = '__cur';
  c.innerHTML = '<svg viewBox="0 0 24 24" width="28" height="28"><path d="M4 2l15 11-6.5 1.2L16 21l-3 1.4-3.4-6.9L4 20z" fill="#e9e4d8" stroke="#0b1117" stroke-width="1.4" stroke-linejoin="round"/></svg>';
  document.body.appendChild(c);
  addEventListener('mousemove', e => c.style.transform = 'translate(' + (e.clientX - 4) + 'px,' + (e.clientY - 2) + 'px)', true);
  addEventListener('mousedown', e => { const r = document.createElement('div'); r.className = '__rip'; r.style.left = e.clientX + 'px'; r.style.top = e.clientY + 'px'; document.body.appendChild(r); setTimeout(() => r.remove(), 700); }, true);
})()`;

async function rec(page, name, fn) {
  const dir = path.join(OUT, name + '_frames'); fs.rmSync(dir, { recursive: true, force: true }); fs.mkdirSync(dir, { recursive: true });
  const cdp = await page.target().createCDPSession();
  const frames = [];
  cdp.on('Page.screencastFrame', async f => {
    frames.push({ t: f.metadata.timestamp, data: f.data });
    cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }).catch(() => {});
  });
  await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 92, maxWidth: 1920, maxHeight: 1080, everyNthFrame: 1 });
  const t0 = Date.now() / 1000; global.T0 = Date.now();
  await fn();
  const t1 = Date.now() / 1000;
  await cdp.send('Page.stopScreencast');
  // write frames + concat list with real durations, then resample to 30 fps CFR
  let list = '';
  frames.forEach((f, i) => { const fn = `f${String(i).padStart(5, '0')}.jpg`; fs.writeFileSync(path.join(dir, fn), Buffer.from(f.data, 'base64'));
    const next = i + 1 < frames.length ? frames[i + 1].t : t1; list += `file '${fn}'\nduration ${Math.max(0.001, next - f.t).toFixed(4)}\n`; });
  list += `file 'f${String(frames.length - 1).padStart(5, '0')}.jpg'\n`;
  fs.writeFileSync(path.join(dir, 'list.txt'), list);
  const out = path.join(OUT, name + '.mp4');
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', path.join(dir, 'list.txt'),
    '-vf', 'fps=30,scale=1920:1080:flags=lanczos,format=yuv420p', '-c:v', 'libx264', '-crf', '15', '-preset', 'medium', '-movflags', '+faststart', out]);
  fs.rmSync(dir, { recursive: true, force: true });
  console.log(name, frames.length, 'frames', (t1 - t0).toFixed(1) + 's', '->', out);
}

// ---------- helpers bound to a page
function kit(p) {
  let mx = 960, my = 600;
  const move = async (x, y, ms = 700) => { const steps = Math.max(8, Math.round(ms / 16)); await p.mouse.move(x, y, { steps }); mx = x; my = y; };
  const box = async sel => { const h = await p.waitForSelector(sel, { timeout: 15000 }); await h.evaluate(e => e.scrollIntoView({ block: 'nearest', behavior: 'instant' })); await sleep(120); const b = await h.boundingBox(); return { x: b.x + b.width / 2, y: b.y + b.height / 2 }; };
  const click = async (sel, ms = 800) => { const b = await box(sel); await move(b.x, b.y, ms); await sleep(180); await p.mouse.click(b.x, b.y); };
  const clickXY = async (x, y, ms = 800) => { await move(x, y, ms); await sleep(180); await p.mouse.click(x, y); };
  const select = async (sel, value, ms = 800) => { const b = await box(sel); await move(b.x, b.y, ms); await sleep(150); await p.mouse.down(); await p.mouse.up();
    await p.evaluate((s, v) => { const e = document.querySelector(s); e.value = v; e.dispatchEvent(new Event('change', { bubbles: true })); }, sel, value); };
  const panelTo = async (sel, dur = 1200) => p.evaluate((s, d) => new Promise(res => { const P = document.querySelector('#panel'), el = document.querySelector(s); if (!el) return res();
    const from = P.scrollTop, to = Math.max(0, from + el.getBoundingClientRect().top - P.getBoundingClientRect().top - 70), t0 = performance.now();
    const st = now => { const k = Math.min(1, (now - t0) / d), e = k < .5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2; P.scrollTop = from + (to - from) * e; k < 1 ? requestAnimationFrame(st) : res(); }; requestAnimationFrame(st); }), sel, dur);
  const panelTop = () => p.evaluate(() => { document.querySelector('#panel').scrollTop = 0; });
  const go = async v => { await p.evaluate(v => go(v), v); await sleep(300); await panelTop(); };
  const wheel = async (x, y, dy, n = 6) => { await move(x, y, 400); for (let i = 0; i < n; i++) { await p.mouse.wheel({ deltaY: dy }); await sleep(90); } };
  return { move, click, clickXY, select, panelTo, go, wheel, box };
}

const CLIPS = {
  // homepage: the storm replay, slow orbit drag in the middle
  async home(p) {
    await p.goto(B + 'index.html', { waitUntil: 'networkidle2' }); await p.evaluate(CURSOR); await sleep(1500);
    const k = kit(p);
    await rec(p, 'home', async () => { await sleep(26000); await k.move(1400, 620, 900); await p.mouse.down(); await k.move(1180, 640, 3500); await p.mouse.up(); await k.move(1880, 1060, 900); await sleep(26000); });
  },
  // home "how it works" + numbers sections (scroll)
  async homeScroll(p) {
    await p.goto(B + 'index.html', { waitUntil: 'networkidle2' }); await p.evaluate(CURSOR); await sleep(1500);
    await rec(p, 'homeScroll', async () => {
      for (const id of ['how', 'numbers', 'spec', 'tools']) {
        await p.evaluate(id => new Promise(res => { const to = document.getElementById(id).getBoundingClientRect().top + scrollY - 40, from = scrollY, t0 = performance.now();
          const st = n => { const k = Math.min(1, (n - t0) / 1600), e = k < .5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2; scrollTo(0, from + (to - from) * e); k < 1 ? requestAnimationFrame(st) : res(); }; requestAnimationFrame(st); }), id);
        await sleep(3500);
      }
    });
  },
  async dash(p, name, fn) {},
};

// wait until `s` seconds after the recording started
const at = async s => { const w = global.T0 + s * 1000 - Date.now(); if (w > 0) await sleep(w); };
const h3 = t => `xpath/.//aside[@id="panel"]//h3[starts-with(normalize-space(.),"${t}")]`;
async function panelToH3(p, t, dur = 1100) {
  await p.evaluate((t, d) => new Promise(res => { const P = document.querySelector('#panel'); const el = [...P.querySelectorAll('h3')].find(h => h.textContent.trim().startsWith(t)); if (!el) return res();
    const from = P.scrollTop, to = Math.max(0, from + el.getBoundingClientRect().top - P.getBoundingClientRect().top - 20), t0 = performance.now();
    const st = n => { const k = Math.min(1, (n - t0) / d), e = k < .5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2; P.scrollTop = from + (to - from) * e; k < 1 ? requestAnimationFrame(st) : res(); }; requestAnimationFrame(st); }), t, dur);
}
const DASH = {
  async situation(p, k) {
    await k.go('live'); await sleep(2000); await k.move(700, 600, 300);
    await rec(p, 'situation', async () => {
      await at(0.3); await k.move(45, 95, 700); await k.move(45, 520, 2000);
      await at(3.0); await k.move(1700, 190, 800);
      await at(5.2); await k.panelTo('#cRain', 1000); await k.move(1720, 330, 600);
      await at(7.0); await panelToH3(p, 'Observation quality'); await k.move(1700, 300, 600);
      await at(8.7); await k.panelTo('#alerts', 1000); await k.move(1650, 260, 600);
      await at(12.0);
    });
  },
  async forecast(p, k) {
    await k.go('forecast'); await sleep(2000);
    await p.evaluate(() => { const s = document.querySelector('#slider'); s.value = 0; s.dispatchEvent(new Event('input')); }); await k.move(700, 700, 300); await sleep(800);
    await rec(p, 'forecast', async () => {
      await at(0.1); await k.click('#play', 500);
      await at(3.7); await k.click('#play', 400);
      let t = 4.0; for (const l of ['p10', 'p50', 'p90', 'peak', 'expected']) { await at(t); await k.click(`#layerSeg button[data-k="${l}"]`, 450); t += 1.0; }
      await at(9.0); await k.clickXY(1222, 700, 800);
      await at(13.6); await k.panelTo('#why', 1200); await k.move(1700, 560, 700);
      await at(23.4);
    });
  },
  async hotspots(p, k) {
    await k.go('prob'); await sleep(2500); await k.move(900, 600, 300);
    await rec(p, 'hotspots', async () => {
      await at(1.2); await k.click('#thrSeg button[data-t="20"]', 700);
      await at(2.5); await k.click('#thrSeg button[data-t="30"]', 450);
      await at(3.7); await k.click('#thrSeg button[data-t="10"]', 450);
      await at(4.6); await k.panelTo('#hsList', 1000); await k.move(1700, 400, 500);
      await at(7.3); await k.panelTo('#rl', 1000);
      const nl = await p.$$eval('#rl button', b => b.length); let t = 8.2;
      for (const i of [1, Math.floor(nl / 2), nl - 1]) { await at(t); await k.click(`#rl button[data-i="${i}"]`, 400); t += 1.0; }
      await at(12.0);
    });
  },
  async drill(p, k) {
    await k.go('live'); await sleep(2000); await k.move(900, 500, 300);
    await rec(p, 'drill', async () => {
      await at(0.6); await k.move(636, 27, 1200);
      await at(2.1); await k.click('label.switch:has(#degradeToggle)', 250);
      await at(3.6); await k.move(1000, 72, 900);
      await at(5.6); await k.move(1650, 200, 900);
      await at(8.5); await k.move(1650, 330, 900);
      await at(14.0);
    });
    await p.evaluate(() => { const t = document.querySelector('#degradeToggle'); t.checked = false; t.dispatchEvent(new Event('change')); });
  },
  async drainage(p, k) {
    await k.go('drain'); await sleep(2500); await k.move(900, 500, 300);
    await rec(p, 'drainage', async () => {
      await at(0.5); await k.move(1150, 560, 1200);
      await at(2.4); const opts = await p.$$eval('#sensSel option', o => o.map(x => x.value)); await k.select('#sensSel', opts[Math.min(2, opts.length - 1)], 700);
      await at(4.7); await panelToH3(p, 'Assimilation'); await k.move(1720, 300, 700);
      await at(9.0); await panelToH3(p, 'Suspected faults'); await k.move(1700, 330, 700);
      await at(12.4); const b = await (await p.$('#anoms .btn')).boundingBox(); await k.clickXY(b.x + b.width / 2, b.y + b.height / 2, 800);
      await at(17.0);
    });
  },
  async routes(p, k) {
    await k.go('impact'); await sleep(2500); await k.move(900, 500, 300);
    await rec(p, 'routes', async () => {
      await at(0.5); await k.move(760, 560, 1300);
      let t = 3.2; for (const v of ['two-wheeler', 'bus', 'ambulance']) { await at(t); await k.select('#veh', v, 600); t += 1.5; }
      await at(8.2); await k.panelTo('#goRoute', 800);
      await at(9.0); await k.select('#fromB', '0', 500);
      const n = await p.$$eval('#toB option', o => o.length);
      await at(9.8); await k.select('#toB', String(Math.max(0, n - 3)), 500);
      await at(10.6); await k.click('#goRoute', 500);
      await at(11.6); await k.move(820, 600, 900);
      await at(13.6); await panelToH3(p, 'Building access'); await k.move(1700, 420, 700);
      await at(17.2);
    });
  },
  async actions(p, k) {
    await k.go('actions'); await sleep(2500); await k.move(900, 500, 300);
    await rec(p, 'actions', async () => {
      await at(0.5); await k.move(1700, 200, 1000);
      let t = 3.1; for (const s of ['rain_plus20', 'capacity_minus50', 'pump_failure', 'downstream_plus20']) { await at(t); await k.click(`#scList .item[data-k="${s}"]`, 450); t += s === 'capacity_minus50' ? 1.6 : 1.3; }
      await at(8.6); await panelToH3(p, 'Interventions'); await k.move(1700, 300, 700);
      await at(13.0); await k.click('#approve', 800);
      await at(17.0);
    });
  },
  async system(p, k) {
    await k.go('valid'); await sleep(2500); await k.move(900, 500, 300);
    await rec(p, 'system', async () => {
      await at(0.5); await k.move(1700, 250, 900);
      await at(1.8); await p.evaluate(() => document.querySelector('#panel').scrollBy({ top: 420, behavior: 'smooth' }));
      await at(3.8); await k.click('#nav button[data-view="system"]', 700); await p.evaluate(() => { document.querySelector('#panel').scrollTop = 0; });
      await at(5.2); await k.move(1700, 240, 600);
      await at(6.8); await panelToH3(p, 'API'); await k.move(1700, 300, 500);
      await at(8.6); await k.panelTo('#cap', 900); await k.click('#cap', 500);
      await at(11.0); await panelToH3(p, 'Who sees what'); await k.move(1700, 300, 500);
      await at(14.5);
    });
  },
};
(async () => {
  const want = process.argv[2] || 'all';
  fs.mkdirSync(OUT, { recursive: true });
  const br = await puppeteer.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: 'new',
    args: ['--window-size=1920,1080', '--use-angle=d3d11', '--enable-gpu', '--ignore-gpu-blocklist', '--hide-scrollbars'] });
  const p = await br.newPage(); await p.setViewport({ width: 1920, height: 1080 });
  const cdp = await p.target().createCDPSession(); await cdp.send('Browser.setDownloadBehavior', { behavior: 'deny' }).catch(() => {});
  p.on('pageerror', e => console.log('pageerror', e.message));
  for (const n of ['home', 'homeScroll']) if (want === 'all' || want === n) await CLIPS[n](p);
  const dn = Object.keys(DASH).filter(n => want === 'all' || want === n);
  if (dn.length) {
    await p.goto(B + 'dashboard/', { waitUntil: 'networkidle2' }); await sleep(5000); await p.evaluate(CURSOR);
    const k = kit(p);
    for (const n of dn) await DASH[n](p, k);
  }
  await br.close();
})();
