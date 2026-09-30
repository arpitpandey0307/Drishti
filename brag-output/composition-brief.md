# Hyperframes Composition Brief: Drishti

## Objective
A narrated 4–5 minute explainer film for Drishti (SIH 2026, PS-26085): problem, solution, uniqueness,
a full walk-through of the working prototype, and results. The user asked for 4–5 minutes, overriding /brag's 15–25 s rule.

## Output
- Composition directory: `brag-output/composition/`
- Rendered video: `brag-output/brag.mp4`
- Format: landscape, 1920×1080, 30 fps
- Duration: 291.3 s (4:51), paced by the narration

## Source Material
- Project root: `Drishti-main/`
- Primary files read: `README.md`, `docs/SRS.md`, `docs/TASKS.md`, `docs/dashboard.md`, `docs/validation.md`, `index.html`, `home/home.js`, `home/home.css`, `dashboard/index.html`, `dashboard/app.js`, `dashboard/style.css`, `dashboard/data/*.json`
- Product name: Drishti
- Tagline: "Know where the water will stand, three hours before it does."
- Real UI shown: the homepage 3D storm replay and all eight dashboard views, recorded from the running app
  (`python -m http.server 8123`) with headless Chrome + a visible cursor; clips in `composition/assets/clips/`.
  Capture script: `work/record.js` (Puppeteer + CDP screencast; actions scheduled on the narration timeline).
- Figures (all from `dashboard/data/validation.json`, `twin.json`, `forecast_115.json`):
  CSI 0.79 vs 0.24 persistence at +180 min; 67% of later-flooded cells flagged, median 20 min early, 2% false alarms;
  87% less sensor error after assimilation; 21.87 s per cycle; mass error 3e-8.

## Creative Direction
- Tone preset: polished — editorial control-room documentary
- Pacing: voice-led; each scene is as long as its narration plus breathing room; dips through ink between scenes
- Avoid: generic SaaS language, invented numbers, abstract filler

## Visual Identity
- Background `#0b1117`, text `#e9e4d8`, muted `#8a949c`, accents teal `#2ec4d6`, orange `#ff7a1a`, amber `#f2b84b`
- Instrument Serif (display, italic teal emphasis), IBM Plex Sans (body), IBM Plex Mono (tracked kickers). Latin woff2 files in `assets/fonts/`.

## Storyboard (see `brag-plan.md`)
1 Cold open (home 3D replay) · 2 Problem (five questions) · 3 Solution (the five-step loop with real timings) ·
4 Four differentiators · 5 Prototype: homepage · 6–13 Dashboard views A–H incl. radar outage drill ·
14 Results (count-ups) · 15 Honesty + wordmark.
Demo scenes: full-bleed clip, a label card (view + one-line claim), punch-ins onto the side panel while the voice describes it.

## Audio
- Narration: Kokoro `af_heart`, synthesised per sentence (`work/sent/`) so subtitles and reveals land on the words
- Music: `happy-beats-business-moves-vol-12` looped with crossfades, sidechain-ducked under the voice, faded in/out
- Mix: premixed to `assets/audio/mix.wav` by `work/build_timeline.py`
- SFX: sparse and quiet — `ui/click2` on the simulated UI clicks, `interface/bong_001` on card/question reveals,
  `impactSoft_medium_001` on chapter openers, `impactBell_heavy_000` on the final wordmark
- Audio-reactive visuals: intentionally omitted — the film is voice-led and readability of dense UI comes first
- Beat sync: not used (the narration sets timing, not the music)

## Build
- `python work/build_timeline.py [--tts] --mix` → `work/timeline.json` + `assets/audio/mix.wav`
- `python work/gen.py` → `composition/index.html` (monolithic by design; the lint's sub-composition suggestions are Studio-organisation warnings)
- Gate: `npx hyperframes check` — passed (0 errors, layout clean, contrast 45/45)
