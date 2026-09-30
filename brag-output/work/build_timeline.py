"""Per-sentence Kokoro narration -> timeline.json + voice track + music bed + final mix.

Run from brag-output/:  python work/build_timeline.py [--tts] [--mix]
"""
import json, re, subprocess, sys, wave
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent
VO_TXT = OUT / "work" / "vo"
SENT = OUT / "work" / "sent"
ASSETS = OUT / "composition" / "assets"
SKILL = Path.home() / ".claude" / "skills" / "brag" / "assets"
MUSIC = SKILL / "music" / "happy-beats-business-moves-vol-12-by-ende-dot-app.mp3"

GAP = 0.18          # silence between sentences in a scene
PRE = {1: 1.4}      # lead-in before the first sentence (per scene; default below)
PRE_DEFAULT = 0.55
POST = {15: 3.0, 14: 0.9}
POST_DEFAULT = 0.75
# extra silence after a specific sentence, e.g. to let a reveal land
HOLD = {}

# scenes whose visuals are a recorded demo clip need at least this long
def split(text):
    parts = re.split(r'(?<=[.?!])\s+', text.strip())
    return [p for p in parts if p]

def dur(p):
    with wave.open(str(p)) as w:
        return w.getnframes() / w.getframerate()

def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=isinstance(cmd, str))

def main():
    tts = "--tts" in sys.argv
    SENT.mkdir(parents=True, exist_ok=True)
    scenes, t = [], 0.0
    for f in sorted(VO_TXT.glob("s*.txt")):
        n = int(f.stem[1:])
        sents = split(f.read_text(encoding="utf-8"))
        pre = PRE.get(n, PRE_DEFAULT)
        start, cur, items = t, t + pre, []
        for i, s in enumerate(sents):
            wav = SENT / f"s{n:02d}_{i:02d}.wav"
            if tts or not wav.exists():
                txt = SENT / f"s{n:02d}_{i:02d}.txt"; txt.write_text(s, encoding="utf-8")
                run(["npx.cmd" if sys.platform == "win32" else "npx", "hyperframes", "tts", str(txt), "--voice", "af_heart", "--output", str(wav)])
            d = dur(wav)
            items.append({"i": i, "text": s, "start": round(cur, 3), "end": round(cur + d, 3), "wav": wav.name})
            cur += d + GAP + HOLD.get((n, i), 0)
        cur -= GAP
        end = cur + POST.get(n, POST_DEFAULT)
        scenes.append({"n": n, "start": round(start, 3), "dur": round(end - start, 3), "sents": items})
        t = end
    total = round(t, 3)
    tl = {"total": total, "scenes": scenes}
    (OUT / "work" / "timeline.json").write_text(json.dumps(tl, indent=1), encoding="utf-8")
    print("total", total)
    for s in scenes:
        print(f"  s{s['n']:02d} start {s['start']:7.2f} dur {s['dur']:6.2f}  sentences {len(s['sents'])}")
    if "--mix" in sys.argv:
        mix(tl)

def mix(tl):
    total = tl["total"]
    sents = [x for s in tl["scenes"] for x in s["sents"]]
    # voice track: each sentence delayed to its start
    inputs, filt = [], []
    for k, x in enumerate(sents):
        inputs += ["-i", str(SENT / x["wav"])]
        ms = int(round(x["start"] * 1000))
        filt.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=mono,adelay={ms}[v{k}]")
    filt.append("".join(f"[v{k}]" for k in range(len(sents))) + f"amix=inputs={len(sents)}:normalize=0,apad,atrim=0:{total}[vo]")
    voice = OUT / "work" / "voice.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filt), "-map", "[vo]", "-ac", "1", "-ar", "48000", str(voice)], check=True)
    # music bed: loop the track with crossfades to cover the film, then shape it
    L = 118.0
    bed_raw = OUT / "work" / "bed_raw.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(MUSIC), "-i", str(MUSIC), "-i", str(MUSIC),
        "-filter_complex", "[0:a][1:a]acrossfade=d=4:c1=tri:c2=tri[a];[a][2:a]acrossfade=d=4:c1=tri:c2=tri[m]", "-map", "[m]", "-ar", "48000", str(bed_raw)], check=True)
    # sidechain-style ducking under the voice, gentle fade in/out
    out = ASSETS / "audio" / "mix.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    fc = (f"[0:a]atrim=0:{total},asetpts=PTS-STARTPTS,volume=0.42,afade=t=in:d=2.5,afade=t=out:st={total-4.5}:d=4.5[m];"
          f"[1:a]asplit=2[vk][vs];"
          f"[m][vk]sidechaincompress=threshold=0.02:ratio=9:attack=60:release=700:makeup=1[md];"
          f"[vs]highpass=f=70,acompressor=threshold=0.12:ratio=2.5:attack=5:release=120:makeup=1.6[vv];"
          f"[md][vv]amix=inputs=2:normalize=0,alimiter=limit=0.93[o]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(bed_raw), "-i", str(voice), "-filter_complex", fc, "-map", "[o]", "-ar", "48000", "-ac", "2", str(out)], check=True)
    print("mix ->", out)

if __name__ == "__main__":
    main()
