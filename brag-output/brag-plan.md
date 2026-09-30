# Brag Plan: Drishti

## What is this app?
Drishti is a street-level urban flood nowcasting system (SIH 2026, PS-26085): a physics + AI digital
twin of the KIET campus that forecasts flood depth in every 5 m street cell for the next 0–180 minutes,
says how sure it is and why, and turns the forecast into routes and actions.

## The angle
A polished, narrated product film: a stranger should finish it knowing the problem, the solution, what is
unique, what every part of the prototype does, and why the team stands out. The user asked for 4–5 minutes
(overriding /brag's 15–25 s default), so this is an explainer in chapters, not a teaser.
The spine is the project's own line: **"Know where the water will stand, three hours before it does."**

## Hook (first ~14 s)
Cold open on the real 3D homepage: the storm replay over the campus terrain, water columns rising.
The headline types in, in the project's own serif. The voice says the problem in one breath and the promise in the next.

## Key moments (the middle)
- The five operator questions (Where / When / How severe / Why / What to do), from the SRS.
- The five-step loop from the homepage, with the real per-step timings (22 s cycle total).
- Four differentiators: physics + AI, probabilistic, closed loop, explains and acts.
- Full prototype walk-through: homepage 3D replay, then dashboard views A–H, each captured live
  from the running app (real MapLibre map, real model bundle), with simulated clicks.
- Real numbers from `dashboard/data/validation.json` + `twin.json`: CSI 0.79 vs 0.24 persistence at +3 h;
  67% of later-flooded cells flagged, median 20 min early, 2% false alarms; 87% less sensor error;
  22 s per forecast cycle.

## Outro / punchline
The project's honesty note (synthetic drainage, twin experiment, ensemble still too confident), then the
wordmark and the tagline again.

## User flow worth showing
1. Operator opens the dashboard → Situation (health card, alerts).
2. Forecast: scrubs 0→180 min, flips P10/P50/P90, clicks a street cell → location forecast + WHY? panel.
3. Acts: radar outage drill → drainage faults → route planner → action lab ranking → Request approval.

## Tone
- Preset: polished
- Creative direction: editorial control-room documentary; calm, confident, precise
- Interpretation: long holds on real UI, soft fades and slides, restrained type, a warm low music bed under a clear voice.

## Format: landscape — 1920x1080, 30 fps
## Duration: ~285 s (voice-paced; target 4:30–4:55)

## Visual identity (from the project: `home/home.css`, `dashboard/style.css`)
- Background: ink `#0b1117` / `#0e141a`
- Text: paper `#e9e4d8`, muted `#8a949c`
- Accents: teal `#2ec4d6`, orange `#ff7a1a`, amber `#f2b84b`, red `#e5484d`, green `#3fb68b`
- Display font: Instrument Serif (italic for emphasis)
- Body / labels: IBM Plex Sans, IBM Plex Mono (uppercase tracked kickers)
- Strongest visual element: the 3D campus with water columns; the satellite dashboard with extruded flood cells.

## Share copy (draft)
Drishti forecasts flood depth street by street, three hours ahead, and says how sure it is, why, and what to do about it. Our SIH 2026 prototype for PS-26085, built on a physics + AI digital twin of the KIET campus.

## Audio direction
- Role: warm bed under narration
- Music: `happy-beats-business-moves-vol-12-by-ende-dot-app.mp3` (steady, clean; polished), looped for length
- Music treatment: fade in over the cold open, duck to ~0.12 under the voice, lift slightly between chapters, fade out on the wordmark
- Music cue guidance: bundled preset read for vol-12; the voice sets pace, so cues are used only for the final wordmark
- Audio-reactive treatment: subtle; the chapter-card rule/glow breathes with the bed. No waveform visuals.
- SFX posture: sparse; soft clicks on simulated UI clicks, a soft drop on chapter cards, one bell on the wordmark
- Restraint rule: nothing competes with the voice

## Storyboard (durations flex to the generated voice)

| # | Scene | What's on screen |
|---|---|---|
| 1 | Cold open | Homepage 3D storm replay, headline |
| 2 | The problem | Kinetic type: the flooding corners; five questions appear one by one |
| 3 | Our solution | The five-step loop with real timings, 22 s total |
| 4 | What's unique | Four differentiator cards |
| 5 | Demo: 3D replay | Homepage replay clip, HUD numbers counting |
| 6 | A Situation | Dashboard live view |
| 7 | B Forecast | Scrub lead time, P10/P50/P90, click a cell, WHY? panel |
| 8 | C Hotspots | Exceedance maps, hotspot list, radar ensemble |
| 9 | Radar outage drill | Toggle drill → DEGRADED banner |
| 10 | D Drainage | Sensors, assimilation chart, suspected faults, work order |
| 11 | E Roads & routes | Vehicle class, route planner finds 3 routes, building access |
| 12 | F Action lab | What-ifs, change vs baseline, ranking, Request approval |
| 13 | G Validation + H System | Skill tables, loop timings, API, CAP, RBAC |
| 14 | The results | Four real figures, count-up |
| 15 | Honest + outro | Data honesty line, wordmark, tagline |

Each demo scene: the captured clip in a framed panel, a chapter label (letter + name in the dashboard's
own style), a short on-screen caption, and 1–2 callouts on the element being described.

## Voiceover script
Voice: Kokoro `af_heart`. Written per scene so every scene is timed to its own line.

1. Monsoon cloudbursts can fill a street in minutes. Yet most warnings only tell you that it will rain. Drishti tells you where the water will stand, three hours before it does.
2. This is Smart India Hackathon problem statement two six zero eight five, from the Ministry of Earth Sciences: urban flood nowcasting. City forecasts stop at the district. But a campus floods one low corner at a time. The lane behind a hostel. The underpass by the main gate. The drain inlet that has been silting up since June. An operator on the ground needs five answers. Where will it flood? When? How deep, and for how long? Why? And what should we do about it?
3. Our answer is Drishti: a flood digital twin of the K I E T campus in Ghaziabad. It models the campus on a five metre grid, with real terrain, real buildings, and a drain network. Every five minutes, it runs one loop. It reads the sky, from radar and eight rain gauges, checking every reading for spikes, frozen sensors and gaps. It nowcasts the rain with a twenty member ensemble. It updates the twin, routing water over the ground and through the pipes. A U-Net, trained on two hundred and ninety physics runs, turns every rain member into a depth map. And hotspots get a full physics re-run. One complete cycle takes about twenty two seconds, on a laptop.
4. So what makes Drishti different? First, physics and A I together: a mass-conserving model of the drains and the surface, with a fast neural surrogate on top. Second, it is probabilistic. Every forecast carries its spread, and the chance of crossing ten, twenty, or thirty centimetres. Third, it closes the loop. Live sensor readings correct the twin, and expose blocked drains. And fourth, it explains its reasoning, and turns forecasts into decisions.
5. Let's see the prototype. The homepage replays a simulated squall over the real campus terrain in three D. Rain falls, drains fill and surcharge, and water rises in the low corners.
6. The operations dashboard has eight views. Situation shows the twin as it stands right now: forecast health, rainfall, observation quality, and live alerts.
7. Forecast plays the depth map from now to three hours ahead. Switch between the expected depth, P ten, P fifty, P ninety, and the peak. Click any street cell, and Drishti forecasts that exact spot: all twenty members, when the threshold is crossed, and a why panel that weighs rainfall, runoff, terrain, drainage and asset faults, to name the main driver.
8. Hotspots maps the chance of exceeding ten, twenty or thirty centimetres, lists an early warning for every hotspot tile, and shows the radar ensemble behind it.
9. And if the radar fails? The outage drill switches to the real degraded forecast. Gauges only, uncertainty widened by half, and a clear degraded banner, so no one trusts it more than they should.
10. Drainage is the closed loop. Nine virtual sensors watch the network. Folding their readings in cuts water level error by eighty seven percent. The residuals point to the likely cause, a blocked pipe or a stuck sensor, with a work order ready to raise.
11. Roads and routes turns depth into impact. Every road is scored for two-wheelers, cars, buses, ambulances and fire trucks. The planner finds three routes that avoid the streets that will be flooded by the time you reach them, and checks access to every building.
12. The action lab runs full physics what-ifs. Heavier rain. Drains at half capacity. A pump failure. A rising nala. It ranks interventions by how much flooding they prevent and what they cost, and nothing runs until a person approves it.
13. Validation scores every cycle against the reference run. And the system view shows the loop timings, a versioned A P I, Common Alerting Protocol alerts, and role-based access for every kind of user.
14. The results. Three hours ahead, on storms it never saw, the fast model scores a critical success index of zero point seven nine, against zero point two four for persistence. Sixty seven percent of the cells that later flooded were flagged in advance, a median twenty minutes early, with just two percent false alarms.
15. And we are honest about it. Every number is labelled observed, derived, modelled, or synthetic. The drainage is synthetic, the scores come from a twin experiment, and the ensemble is still too confident. That is what we fix next. Drishti. Know where the water will stand, three hours before it does.

## Material notes
- All figures come from the shipped model bundle; nothing invented.
- No personal data appears in the app; the header role name is a role, not a person.
