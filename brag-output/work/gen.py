"""Generate composition/index.html from work/timeline.json.  Run from brag-output/:  python work/gen.py"""
import json, re, html
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent
TL = json.loads((OUT / "work" / "timeline.json").read_text(encoding="utf-8"))
FONTS = (OUT / "work" / "fonts.css").read_text(encoding="utf-8")
TOTAL = TL["total"]
SC = {s["n"]: s for s in TL["scenes"]}

def S(n): return SC[n]["start"]
def D(n): return SC[n]["dur"]
def ss(n, i): return SC[n]["sents"][i]["start"]            # absolute sentence start
def se(n, i): return SC[n]["sents"][i]["end"]
def r(x): return round(x, 3)

H = []     # scene html
J = []     # timeline js lines
A = []     # extra audio
tr = [20]  # sfx track counter

import subprocess
_SD = {}
def sfx_len(src):
    if src not in _SD:
        _SD[src] = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(OUT / "composition" / "assets" / "sfx" / src)]).decode().strip())
    return _SD[src]
def sfx(src, t, vol=0.5):
    tr[0] += 1
    A.append(f'<audio id="sfx{tr[0]}" data-start="{r(t)}" data-duration="{r(sfx_len(src))}" data-track-index="{tr[0]}" data-volume="{vol}" src="assets/sfx/{src}"></audio>')

def scene(n, inner, cls=""):
    H.append(f'<section id="s{n}" class="clip scene {cls}" data-start="{r(S(n))}" data-duration="{r(D(n))}" data-track-index="2">\n{inner}\n</section>')
    # scene-level dip: inner content fades in / out
    J.append(f'tl.fromTo("#s{n} .fx", {{opacity:0}}, {{opacity:1, duration:0.45, ease:"power2.out"}}, {r(S(n)+0.02)});')
    J.append(f'tl.to("#s{n} .fx", {{opacity:0, duration:0.35, ease:"power2.in"}}, {r(S(n)+D(n)-0.4)});')

def rise(sel, t, dur=0.6, y=24):
    J.append(f'tl.fromTo("{sel}", {{opacity:0, y:{y}}}, {{opacity:1, y:0, duration:{dur}, ease:"power3.out"}}, {r(t)});')

def fade_out(sel, t, dur=0.35):
    J.append(f'tl.to("{sel}", {{opacity:0, duration:{dur}, ease:"power2.in"}}, {r(t)});')

def video(vid, src, n, media_start=0, dur=None, extra_cls=""):
    dur = D(n) if dur is None else dur
    H.append(f'''<div class="vwrap {extra_cls}" id="w_{vid}"><video id="{vid}" class="clip vid" src="assets/clips/{src}" data-start="{r(S(n))}" data-duration="{r(dur)}" data-media-start="{media_start}" data-track-index="1" muted playsinline></video></div>''')

def zoom(vid, n, t0, t1, scale, ox, oy, ease_in=0.9):
    """punch-in on wrapper around the timed video, scene-relative times"""
    a, b = S(n) + t0, S(n) + t1
    J.append(f'tl.fromTo("#w_{vid}", {{scale:1}}, {{scale:{scale}, transformOrigin:"{ox}px {oy}px", duration:{ease_in}, ease:"power2.inOut", immediateRender:false}}, {r(a)});')
    J.append(f'tl.to("#w_{vid}", {{scale:1, transformOrigin:"{ox}px {oy}px", duration:{ease_in}, ease:"power2.inOut"}}, {r(b)});')

def wrap_fade(vid, n, fin=0.45, fout=0.35):
    J.append(f'tl.fromTo("#w_{vid}", {{opacity:0}}, {{opacity:1, duration:{fin}, ease:"power2.out"}}, {r(S(n))});')
    J.append(f'tl.to("#w_{vid}", {{opacity:0, duration:{fout}, ease:"power2.in"}}, {r(S(n)+D(n)-fout-0.05)});')

esc = html.escape

# --------------------------------------------------------------------------------------------- scene 1 — cold open
video("v1", "home_open.mp4", 1)
J.append(f'tl.fromTo("#w_v1", {{opacity:0}}, {{opacity:1, duration:1.2, ease:"power1.out"}}, 0);')
fade_out("#w_v1", D(1) - 0.45, 0.4)

# --------------------------------------------------------------------------------------------- backdrop for text scenes
bd_dur = S(5) - S(2)
H.append(f'<div class="vwrap bd" id="w_bd1"><video id="bd1" class="clip vid" src="assets/clips/backdrop.mp4" data-start="{r(S(2))}" data-duration="{r(bd_dur)}" data-media-start="0" data-track-index="0" muted playsinline></video></div>')
J.append(f'tl.fromTo("#w_bd1", {{opacity:0}}, {{opacity:0.30, duration:1.2}}, {r(S(2))});')
fade_out("#w_bd1", S(5) - 0.6, 0.5)
bd2 = S(15) + D(15) - S(14)
H.append(f'<div class="vwrap bd" id="w_bd2"><video id="bd2" class="clip vid" src="assets/clips/backdrop.mp4" data-start="{r(S(14))}" data-duration="{r(bd2)}" data-media-start="30" data-track-index="0" muted playsinline></video></div>')
J.append(f'tl.fromTo("#w_bd2", {{opacity:0}}, {{opacity:0.30, duration:1.2}}, {r(S(14))});')

def kicker(txt, cls=""): return f'<p class="kicker {cls}">{txt}</p>'

# --------------------------------------------------------------------------------------------- scene 2 — the problem
n = 2
scene(n, f'''<div class="fx">
  <div class="page">
    {kicker('01 — The problem &nbsp;·&nbsp; SIH 2026 &nbsp;·&nbsp; PS-26085 &nbsp;·&nbsp; Ministry of Earth Sciences')}
    <div class="stack" id="s2h">
      <h2 class="big" id="s2a">Urban flood <em>nowcasting.</em></h2>
      <h2 class="big" id="s2b">City forecasts stop <em>at the district.</em></h2>
      <h2 class="big" id="s2c">A campus floods <em>one low corner at a time.</em></h2>
      <h2 class="big" id="s2d">An operator needs <em>five answers.</em></h2>
    </div>
    <ol class="corners" id="s2corners">
      <li><span class="n">01</span>The lane behind a hostel</li>
      <li><span class="n">02</span>The underpass by the main gate</li>
      <li><span class="n">03</span>The drain inlet silting up since June</li>
    </ol>
    <div class="qs" id="s2qs">
      <div class="q"><b>Where?</b><span>Which streets, junctions and buildings flood</span></div>
      <div class="q"><b>When?</b><span>When the depth threshold is crossed</span></div>
      <div class="q"><b>How severe?</b><span>How deep, how fast, for how long</span></div>
      <div class="q"><b>Why?</b><span>Rain, terrain, drain surcharge or blockage</span></div>
      <div class="q"><b>What to do?</b><span>Which action or route cuts the impact most</span></div>
    </div>
  </div></div>''')
rise("#s2 .kicker", S(n) + 0.3)
heads = [("#s2a", ss(n, 0) + 0.2), ("#s2b", ss(n, 1)), ("#s2c", ss(n, 2)), ("#s2d", ss(n, 6))]
for k, (sel, t) in enumerate(heads):
    rise(sel, t, 0.7, 30)
    if k + 1 < len(heads): fade_out(sel, heads[k + 1][1] - 0.35, 0.3)
for i, idx in enumerate([3, 4, 5]):
    rise(f"#s2corners li:nth-child({i+1})", ss(n, idx) - 0.1, 0.55, 18)
fade_out("#s2corners", ss(n, 6) - 0.35, 0.3)
for i, idx in enumerate([7, 8, 9, 10, 11]):
    rise(f"#s2qs .q:nth-child({i+1})", ss(n, idx) - 0.12, 0.5, 26)
    sfx("bong_001.ogg", ss(n, idx) - 0.12, 0.22)
sfx("impactSoft_medium_001.ogg", S(n) + 0.25, 0.4)

# --------------------------------------------------------------------------------------------- scene 3 — the solution
n = 3
steps = [("Read the sky", "Radar mosaic + 8 rain gauges, checked for spikes, frozen sensors, clock drift and gaps", 0.14, 3),
         ("Nowcast the rain", "Optical-flow tracking and a 20-member STEPS ensemble, 0–180 min", 7.81, 4),
         ("Update the twin", "Coupled 1D drains + 2D surface over real terrain, mass conserved to 3×10⁻⁸", 2.71, 5),
         ("Forecast the flood", "U-Net surrogate trained on 290 physics runs, one depth map per rain member", 0.24, 6),
         ("Look closer where it matters", "Hotspot tiles get a full physics re-run, then roads and access are scored", 10.85, 7)]
rows = "".join(f'''<li class="step" id="st{i}"><span class="n">0{i+1}</span><div class="sx"><h3>{a}</h3><p>{b}</p></div>
  <div class="tm"><div class="bar"><i id="stb{i}"></i></div><b>{c:.2f} s</b></div></li>''' for i, (a, b, c, _) in enumerate(steps))
scene(n, f'''<div class="fx">
  <div class="page">
    {kicker('02 — Our solution')}
    <div id="s3a" class="lock">
      <h1 class="word">Drishti</h1>
      <p class="subline">A flood digital twin of the <b>KIET campus</b>, Ghaziabad.</p>
      <div class="chips" id="s3chips"><span>5 m grid · 76 × 104 cells</span><span>Copernicus GLO-30 terrain</span><span>OSM buildings &amp; roads</span><span>63-node drain network · pump · 2 outfalls</span></div>
    </div>
    <div id="s3b">
      <h2 class="mid">One loop, <em>every five minutes.</em></h2>
      <ol class="loop">{rows}</ol>
      <div class="total" id="s3tot"><span class="lab">One full forecast cycle, 20 members, laptop CPU</span><b><span id="s3cnt">0.0</span> s</b><span class="lab">of a 300 s budget</span></div>
    </div>
  </div></div>''')
rise("#s3 .kicker", S(n) + 0.3)
rise("#s3a .word", ss(n, 0) + 0.3, 0.9, 40)
rise("#s3a .subline", ss(n, 0) + 1.6, 0.7)
J.append(f'tl.fromTo("#s3chips span", {{opacity:0, y:14}}, {{opacity:1, y:0, duration:0.45, stagger:0.12, ease:"power3.out"}}, {r(ss(n,1)+0.3)});')
fade_out("#s3a", ss(n, 2) - 0.45, 0.35)
rise("#s3b .mid", ss(n, 2) - 0.1, 0.6)
tot = 21.87
for i, (_, _, c, si) in enumerate(steps):
    t = ss(n, si) - 0.15
    rise(f"#st{i}", t, 0.5, 16)
    J.append(f'tl.fromTo("#stb{i}", {{scaleX:0}}, {{scaleX:{max(0.02, c/tot):.3f}, duration:0.9, ease:"power2.out"}}, {r(t+0.3)});')
    J.append(f'tl.fromTo("#st{i} .n", {{color:"#8a949c"}}, {{color:"#ff7a1a", duration:0.3}}, {r(t)});')
    sfx("click2.ogg", t, 0.25)
rise("#s3tot", ss(n, 8) - 0.1, 0.5)
J.append(f'(function(){{const o={{v:0}}, el=document.getElementById("s3cnt"); tl.fromTo(o,{{v:0}},{{v:{tot}, duration:1.6, ease:"power2.out", onUpdate:()=>{{el.textContent=o.v.toFixed(1);}}}}, {r(ss(n,8)+0.2)});}})();')

# --------------------------------------------------------------------------------------------- scene 4 — uniqueness
n = 4
cards = [("Physics + AI", "A mass-conserving model of the drains and the street surface, with a fast neural surrogate on top.", "1D pipes · 2D surface · U-Net", 1),
         ("Probabilistic", "Every forecast carries its spread, and the chance of crossing 10, 20 or 30 cm.", "P10 · P50 · P90 · P(depth &gt; x)", 2),
         ("Closed loop", "Live sensor readings correct the twin, and expose blocked drains and stuck sensors.", "Kalman update · drainage health", 4),
         ("Explains &amp; acts", "A <i>why?</i> for every street cell, then routes, what-ifs and actions a person approves.", "WHY? · routing · action lab", 6)]
cc = "".join(f'<div class="card" id="c{i}"><span class="n">0{i+1}</span><h3>{a}</h3><p>{b}</p><small>{c}</small></div>' for i, (a, b, c, _) in enumerate(cards))
scene(n, f'''<div class="fx"><div class="page">
    {kicker('03 — What makes it different')}
    <h2 class="mid" id="s4h">Not a rain warning. <em>A street-level forecast you can act on.</em></h2>
    <div class="cards">{cc}</div>
  </div></div>''')
rise("#s4 .kicker", S(n) + 0.3)
rise("#s4h", ss(n, 0), 0.7)
for i, (_, _, _, si) in enumerate(cards):
    t = ss(n, si) - 0.1
    rise(f"#c{i}", t, 0.6, 30)
    J.append(f'tl.fromTo("#c{i}", {{borderColor:"rgba(46,196,214,0.9)"}}, {{borderColor:"rgba(35,49,60,1)", duration:1.2, ease:"power1.out", immediateRender:false}}, {r(t+1.6)});')
    sfx("bong_001.ogg", t, 0.22)

# --------------------------------------------------------------------------------------------- demo scenes
def demo(n, vid, src, kick, line, zooms=(), media_start=0, card_pos=("170px", "150px"), clicks=()):
    video(vid, src, n, media_start)
    wrap_fade(vid, n)
    for z in zooms: zoom(vid, n, *z)
    H.append(f'''<div class="clip label" id="lb{n}" data-start="{r(S(n))}" data-duration="{r(D(n))}" data-track-index="3" style="left:{card_pos[0]};top:{card_pos[1]}">
  <p class="kicker">{kick}</p><p class="ln">{line}</p></div>''')
    rise(f"#lb{n}", S(n) + 0.35, 0.6, 16)
    fade_out(f"#lb{n}", S(n) + D(n) - 0.45, 0.35)
    for t in clicks: sfx("click2.ogg", S(n) + t, 0.35)

# scene 5: homepage replay
n = 5
H.append(f'''<div class="clip title" id="t5" data-start="{r(S(n))}" data-duration="2.6" data-track-index="3"><div class="fx5">
  <p class="kicker">04 — The prototype</p><h2 class="big">Let’s see it <em>work.</em></h2></div></div>''')
rise("#t5 .fx5", S(n) + 0.1, 0.6)
fade_out("#t5 .fx5", S(n) + 2.1, 0.4)
sfx("impactSoft_medium_001.ogg", S(n) + 0.1, 0.4)
H.append(f'<div class="vwrap" id="w_v5"><video id="v5" class="clip vid" src="assets/clips/home_demo.mp4" data-start="{r(S(n)+2.2)}" data-duration="{r(D(n)-2.2)}" data-media-start="0" data-track-index="1" muted playsinline></video></div>')
J.append(f'tl.fromTo("#w_v5", {{opacity:0}}, {{opacity:1, duration:0.6}}, {r(S(n)+2.2)});')
fade_out("#w_v5", S(n) + D(n) - 0.4, 0.35)
H.append(f'''<div class="clip label" id="lb5" data-start="{r(S(n)+2.4)}" data-duration="{r(D(n)-2.4)}" data-track-index="3" style="left:34px;top:800px">
  <p class="kicker">Prototype · Homepage</p><p class="ln">A simulated squall, replayed in 3D over the real campus terrain.</p></div>''')
rise("#lb5", S(n) + 2.8, 0.6, 16)
fade_out("#lb5", S(n) + D(n) - 0.45, 0.35)

RX = 1920
demo(6, "v6", "situation.mp4", "Prototype · 01 / 08 · View A", "Situation — the twin, as it stands right now.",
     zooms=[(3.0, 10.4, 1.4, RX, 330)], clicks=())
demo(7, "v7", "forecast.mp4", "Prototype · 02 / 08 · View B", "Forecast — every street cell, 0 to 180 minutes ahead.",
     zooms=[(4.0, 8.6, 1.5, RX, 110), (10.0, 22.0, 1.4, RX, 560)], clicks=(0.7, 3.95, 4.5, 5.5, 6.5, 7.5, 8.5, 9.9))
demo(8, "v8", "hotspots.mp4", "Prototype · 03 / 08 · View C", "Hotspots — the chance of crossing 10, 20 or 30 cm.",
     zooms=[(4.4, 10.6, 1.4, RX, 560)], clicks=(1.9, 2.95, 4.15, 8.6, 9.6, 10.6))
demo(9, "v9", "drill.mp4", "Prototype · 04 / 08 · Radar outage drill", "When data fails, Drishti says so.",
     zooms=[(3.0, 5.3, 1.3, 960, 0), (5.7, 12.8, 1.4, RX, 330)], clicks=(2.35,))
demo(10, "v10", "drainage.mp4", "Prototype · 05 / 08 · View D", "Drainage — sensors correct the twin, and find the fault.",
     zooms=[(4.6, 15.7, 1.4, RX, 420)], clicks=(3.1, 13.2))
demo(11, "v11", "routes.mp4", "Prototype · 06 / 08 · View E", "Roads &amp; routes — depth becomes impact.",
     zooms=[(3.0, 7.9, 1.45, RX, 220), (13.5, 16.0, 1.4, RX, 760)], clicks=(3.8, 5.3, 6.8, 9.5, 10.3, 11.1))
demo(12, "v12", "actions.mp4", "Prototype · 07 / 08 · View F", "Action lab — test the fix before the crew goes out.",
     zooms=[(2.9, 8.3, 1.35, RX, 330), (8.7, 15.8, 1.4, RX, 820)], clicks=(3.55, 4.95, 6.55, 7.85, 13.8))
demo(13, "v13", "system.mp4", "Prototype · 08 / 08 · Views G + H", "Validation &amp; system — scored, versioned, ready to plug in.",
     zooms=[(1.0, 13.2, 1.35, RX, 420)], clicks=(4.5, 9.4))

# --------------------------------------------------------------------------------------------- scene 14 — results
n = 14
figs = [("s14f0", "0.79", 0.79, 2, "critical success index for flooding, 3 hours ahead, on storms it never saw", "vs <b>0.24</b> for “it stays as it is”", ss(n, 1) + 4.2),
        ("s14f1", "67%", 67, 0, "of the cells that later flooded were flagged in advance", "", ss(n, 2) + 0.2),
        ("s14f2", "20 min", 20, 0, "median warning ahead of the water", "", ss(n, 2) + 4.2),
        ("s14f3", "2%", 2, 0, "false alarms", "", ss(n, 2) + 6.4)]
fh = "".join(f'<div class="fig" id="{i}"><b><span class="cnt">0</span>{"" if not v.endswith(("%", "min")) else ("%" if v.endswith("%") else " min")}</b><p>{d}</p>{f"<small>{x}</small>" if x else ""}</div>' for i, v, _, _, d, x, _ in figs)
scene(n, f'''<div class="fx"><div class="page">
    {kicker('05 — The results &nbsp;·&nbsp; measured against the reference run')}
    <h2 class="mid" id="s14h">Earlier, and <em>right more often.</em></h2>
    <div class="figs">{fh}</div>
    <div class="also" id="s14also"><span><b>87%</b> less water-level error at drain sensors after assimilation</span><span><b>21.9 s</b> per full forecast cycle</span><span><b>3×10⁻⁸</b> relative mass error in the physics</span></div>
  </div></div>''')
rise("#s14 .kicker", S(n) + 0.3)
rise("#s14h", ss(n, 0), 0.7)
for i, v, num, dec, d, x, t in figs:
    rise(f"#{i}", t - 0.2, 0.5, 24)
    J.append(f'(function(){{const o={{v:0}}, el=document.querySelector("#{i} .cnt"); tl.fromTo(o,{{v:0}},{{v:{num}, duration:1.3, ease:"power2.out", onUpdate:()=>{{el.textContent=o.v.toFixed({dec});}}}}, {r(t)});}})();')
    sfx("bong_001.ogg", t - 0.2, 0.22)
J.append(f'tl.fromTo("#s14f0 small", {{opacity:0}}, {{opacity:1, duration:0.5}}, {r(ss(n,1)+7.6)});')
rise("#s14also", ss(n, 2) + 7.6, 0.6, 14)

# --------------------------------------------------------------------------------------------- scene 15 — honesty + outro
n = 15
scene(n, f'''<div class="fx"><div class="page">
    <div id="s15a">
      {kicker('06 — Honest by design')}
      <h2 class="mid">Every number says <em>where it came from.</em></h2>
      <div class="tags" id="s15tags"><span class="tg obs">observed</span><span class="tg der">derived</span><span class="tg mod">modelled</span><span class="tg syn">synthetic</span></div>
      <ul class="caveats" id="s15cav"><li>Drainage network — synthetic, marked unverified</li><li>Scores — a synthetic twin experiment, not a real flood</li><li>Ensemble — still too confident. <b>That is what we fix next.</b></li></ul>
    </div>
    <div id="s15b" class="lock">
      <h1 class="word xl">Drishti</h1>
      <p class="tag2">Know where the water will stand, <em>three hours before it does.</em></p>
      <p class="foot">Smart India Hackathon 2026 &nbsp;·&nbsp; PS-26085 &nbsp;·&nbsp; KIET Group of Institutions, Ghaziabad</p>
    </div>
  </div></div>''')
rise("#s15a .kicker", S(n) + 0.3)
rise("#s15a .mid", ss(n, 0), 0.7)
J.append(f'tl.fromTo("#s15tags .tg", {{opacity:0, y:12}}, {{opacity:1, y:0, duration:0.4, stagger:0.45, ease:"power3.out"}}, {r(ss(n,1)+1.3)});')
J.append(f'tl.fromTo("#s15cav li", {{opacity:0, x:-16}}, {{opacity:1, x:0, duration:0.45, stagger:1.6, ease:"power3.out"}}, {r(ss(n,2)+0.3)});')
fade_out("#s15a", ss(n, 4) - 0.5, 0.4)
t_word = ss(n, 4) - 0.05
J.append(f'tl.fromTo("#s15b .word", {{opacity:0, scale:0.94}}, {{opacity:1, scale:1, duration:1.1, ease:"power3.out"}}, {r(t_word)});')
rise("#s15b .tag2", ss(n, 5), 0.8, 20)
rise("#s15b .foot", ss(n, 5) + 1.4, 0.7, 10)
sfx("impactBell_heavy_000.ogg", t_word, 0.45)
J.append(f'tl.to("#fadeout", {{opacity:1, duration:1.2, ease:"power1.in"}}, {r(TOTAL-1.3)});')

# --------------------------------------------------------------------------------------------- subtitles
def chunks(text, start, end, maxc=96):
    words, out, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > maxc: out.append(cur); cur = w
        else: cur = (cur + " " + w).strip()
    out.append(cur)
    # balance: avoid a tiny tail
    total = sum(len(c) for c in out); t, res = start, []
    for c in out:
        d = (end - start) * len(c) / total; res.append((c, t, t + d)); t += d
    return res

def spoken_to_screen(s):
    rep = [("K I E T", "KIET"), ("A I", "AI"), ("A P I", "API"), ("three D", "3D"), ("P ten", "P10"), ("P fifty", "P50"), ("P ninety", "P90"),
           ("two six zero eight five", "26085"), ("five metre", "5-metre"), ("twenty member", "20-member"), ("two hundred and ninety", "290"),
           ("twenty two seconds", "22 seconds"), ("eighty seven percent", "87%"), ("zero point seven nine", "0.79"), ("zero point two four", "0.24"),
           ("Sixty seven percent", "67%"), ("twenty minutes", "20 minutes"), ("two percent", "2%"), ("ten, twenty, or thirty centimetres", "10, 20 or 30 cm"),
           ("ten, twenty or thirty centimetres", "10, 20 or 30 cm"), ("eight views", "eight views"), ("eight rain gauges", "8 rain gauges")]
    for a, b in rep: s = s.replace(a, b)
    return s

subs = []
k = 0
for s in TL["scenes"]:
    for x in s["sents"]:
        ch = chunks(spoken_to_screen(x["text"]), x["start"], x["end"])
        for j, (c, a, b) in enumerate(ch):
            k += 1
            dur = (b - a + 0.12) if j == len(ch) - 1 else (b - a)
            subs.append(f'<div class="clip sub" id="sb{k}" data-start="{r(a)}" data-duration="{r(dur)}" data-track-index="9"><span>{esc(c)}</span></div>')

# --------------------------------------------------------------------------------------------- page
CSS = FONTS + r"""
:root{--ink:#0b1117;--ink2:#0e141a;--rule:#23313c;--paper:#e9e4d8;--mut:#8a949c;--teal:#2ec4d6;--orange:#ff7a1a;--amber:#f2b84b;--red:#e5484d;--green:#3fb68b;
  --serif:'Instrument Serif',Georgia,serif;--sans:'IBM Plex Sans',system-ui,sans-serif;--mono:'IBM Plex Mono',ui-monospace,monospace}
html,body{margin:0;background:#0b1117}
body{color:var(--paper);font-family:var(--sans);-webkit-font-smoothing:antialiased}
#root{position:relative;width:100%;height:100%;overflow:hidden;background:var(--ink)}
.vwrap{position:absolute;inset:0;overflow:hidden;will-change:transform,opacity}
.vid{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.bd .vid{filter:saturate(.8)}
.vig{position:absolute;inset:0;pointer-events:none;background:radial-gradient(ellipse at 50% 45%,rgba(11,17,23,0) 55%,rgba(11,17,23,.55) 100%)}
.scene{position:absolute;inset:0}
.fx{position:absolute;inset:0}
.page{position:absolute;left:150px;right:150px;top:120px;bottom:150px}
.kicker{margin:0 0 26px;font:500 19px/1.2 var(--mono);letter-spacing:.16em;text-transform:uppercase;color:var(--orange)}
em{font-style:italic;color:var(--teal)}
.big{margin:0;font:400 104px/1.02 var(--serif);letter-spacing:-.01em;color:var(--paper);max-width:1500px}
.mid{margin:0 0 44px;font:400 74px/1.05 var(--serif);color:var(--paper);max-width:1560px}
.stack{position:relative;height:230px}
.stack .big{position:absolute;left:0;top:0}
.corners{list-style:none;margin:70px 0 0;padding:0;display:grid;grid-template-columns:repeat(3,1fr);gap:28px}
.corners li{border-top:1px solid var(--rule);padding-top:22px;font:400 34px/1.3 var(--sans);color:var(--paper)}
.corners .n,.q b,.card .n,.step .n{font-family:var(--mono)}
.corners .n{display:block;font:500 18px var(--mono);color:var(--orange);margin-bottom:10px;letter-spacing:.1em}
.qs{position:absolute;left:0;right:0;top:330px;display:grid;grid-template-columns:repeat(5,1fr);gap:22px}
.q{border:1px solid var(--rule);background:rgba(14,20,26,.86);padding:30px 26px 34px;min-height:220px}
.q b{display:block;font:400 54px/1 var(--serif);font-family:var(--serif);color:var(--teal);margin-bottom:18px}
.q span{font:400 25px/1.35 var(--sans);color:var(--paper)}
.lock{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:center;align-items:flex-start}
#s3a{inset:40px 0 0}
.word{margin:0;font:400 230px/.9 var(--serif);letter-spacing:-.02em;color:var(--paper)}
.word.xl{font-size:250px}
.subline{margin:22px 0 40px;font:400 44px/1.25 var(--sans);color:var(--paper)}
.subline b{font-weight:500;color:var(--teal)}
.chips{display:flex;flex-wrap:wrap;gap:14px}
.chips span{font:500 22px var(--mono);letter-spacing:.04em;color:var(--paper);border:1px solid var(--rule);background:rgba(14,20,26,.88);padding:12px 18px}
#s3b{position:absolute;inset:56px 0 0}
.loop{list-style:none;margin:0;padding:0}
.step{display:grid;grid-template-columns:80px 1fr 360px;align-items:center;gap:26px;border-top:1px solid var(--rule);padding:11px 0}
.step .n{font:500 24px var(--mono);color:var(--mut)}
.step h3{margin:0 0 3px;font:400 36px/1.1 var(--serif);color:var(--paper)}
.step p{margin:0;font:400 22px/1.3 var(--sans);color:#c9c4b8}
.tm{display:flex;align-items:center;gap:18px}
.tm .bar{flex:1;height:8px;background:var(--rule)}
.tm .bar i{display:block;height:100%;background:var(--teal);transform-origin:0 50%}
.tm b{font:500 24px var(--mono);color:var(--paper);min-width:96px;text-align:right}
.total{display:flex;align-items:baseline;gap:26px;margin-top:14px;border-top:1px solid var(--rule);padding-top:16px}
.total b{font:400 68px/1 var(--serif);color:var(--orange)}
.total .lab{font:500 20px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--mut)}
.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:24px}
.card{border:1px solid #23313c;background:rgba(14,20,26,.9);padding:34px 30px 30px;min-height:380px;display:flex;flex-direction:column}
.card .n{font:500 22px var(--mono);color:var(--orange);margin-bottom:22px}
.card h3{margin:0 0 18px;font:400 52px/1.02 var(--serif);color:var(--paper)}
.card p{margin:0 0 22px;font:400 26px/1.4 var(--sans);color:var(--paper);flex:1}
.card p i{font-family:var(--serif);font-size:30px;color:var(--teal)}
.card small{font:500 18px var(--mono);letter-spacing:.06em;color:var(--teal)}
.label{position:absolute;width:640px;background:rgba(11,17,23,.9);border-left:3px solid var(--orange);padding:18px 24px 20px;box-shadow:0 10px 30px rgba(0,0,0,.35)}
.label .kicker{margin:0 0 8px;font-size:15px}
.label .ln{margin:0;font:400 36px/1.15 var(--serif);color:var(--paper)}
.title{position:absolute;inset:0;background:var(--ink);display:flex;align-items:center}
.fx5{padding-left:150px}
.figs{display:grid;grid-template-columns:1.25fr 1fr 1fr 1fr;gap:26px}
.fig{border-top:2px solid var(--rule);padding-top:26px}
.fig b{display:block;font:400 132px/1 var(--serif);color:var(--paper);font-variant-numeric:tabular-nums;white-space:nowrap}
#s14f0 b{color:var(--teal)}
.fig p{margin:16px 0 10px;font:400 25px/1.4 var(--sans);color:var(--paper)}
.fig small{font:500 20px var(--mono);color:var(--mut)}
.fig small b{display:inline;font:600 20px var(--mono);color:var(--orange)}
.also{display:flex;gap:44px;margin-top:56px;border-top:1px solid var(--rule);padding-top:24px}
.also span{font:400 23px var(--sans);color:#c9c4b8}
.also b{font:500 25px var(--mono);color:var(--orange);margin-right:8px}
.tags{display:flex;gap:18px;margin:0 0 50px}
.tg{font:600 22px var(--mono);letter-spacing:.14em;text-transform:uppercase;padding:10px 18px;border:1px solid}
.tg.obs{color:var(--green);border-color:var(--green)} .tg.der{color:var(--teal);border-color:var(--teal)}
.tg.mod{color:var(--amber);border-color:var(--amber)} .tg.syn{color:#ff9aa0;border-color:#ff9aa0}
.caveats{list-style:none;margin:0;padding:0}
.caveats li{font:400 34px/1.35 var(--sans);color:var(--paper);border-top:1px solid var(--rule);padding:18px 0}
.caveats b{font-weight:500;color:var(--orange)}
#s15b{align-items:center;text-align:center;inset:-40px 0 0}
.tag2{margin:26px 0 0;font:400 62px/1.15 var(--serif);color:var(--paper)}
.foot{margin:46px 0 0;font:500 19px var(--mono);letter-spacing:.14em;text-transform:uppercase;color:var(--mut)}
.sub.clip{position:absolute;left:0;right:0;top:auto;bottom:34px;height:auto;display:flex;justify-content:center;pointer-events:none}
.sub.clip span{max-width:1560px;text-align:center;font:500 33px/1.35 var(--sans);color:#f4f1ea;background:rgba(8,12,16,.8);padding:9px 22px 11px;border-radius:6px}
#fadeout{position:absolute;inset:0;background:#000;opacity:0;pointer-events:none}
"""

doc = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=1920, height=1080" />
<title>Drishti — urban flood nowcasting (SIH 2026 · PS-26085)</title>
<script src="assets/js/gsap.min.js"></script>
<style>
{CSS}
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-width="1920" data-height="1080" data-duration="{r(TOTAL)}" data-fps="30">
{chr(10).join(H)}
<div class="vig"></div>
{chr(10).join(subs)}
<div id="fadeout"></div>
<audio id="mix" data-start="0" data-duration="{r(TOTAL)}" data-track-index="10" data-volume="1" src="assets/audio/mix.wav"></audio>
{chr(10).join(A)}
</div>
<script>
const tl = gsap.timeline({{ paused: true }});
{chr(10).join(J)}
// subtitles: quick fade on each caption
document.querySelectorAll(".sub.clip").forEach(el => {{
  const a = +el.dataset.start, d = +el.dataset.duration;
  tl.fromTo(el.firstElementChild, {{opacity:0}}, {{opacity:1, duration:0.12}}, a);
}});
window.__timelines["main"] = tl;
</script>
</body>
</html>
'''
(OUT / "composition" / "index.html").write_text(doc, encoding="utf-8")
print("ok", len(H), "blocks,", len(subs), "subs,", len(A), "sfx, total", TOTAL)
