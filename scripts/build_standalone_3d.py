"""Build kiet_3d_standalone.html — self-contained 3D page with terrain payload embedded.
Run: python3 scripts/build_standalone_3d.py
Reads kiet_3d_terrain.html + data/terrain_3d.json, replaces the fetch() call with
inline data so the page works via file:// double-click (no server needed).
Three.js itself still loads from CDN (internet required once)."""
import json
import pathlib

SRC = pathlib.Path("kiet_3d_terrain.html")
DATA = pathlib.Path("data/terrain_3d.json")
OUT = pathlib.Path("kiet_3d_standalone.html")

FETCH_LINE = "const data = await fetch('data/terrain_3d.json').then(r=>{if(!r.ok)throw 0;return r.json();}).catch(()=>null);"

def main() -> None:
    html = SRC.read_text()
    assert FETCH_LINE in html, "fetch line changed — update build script"
    payload = json.loads(DATA.read_text())
    inline = json.dumps(payload, separators=(",", ":")).replace("<", "\\u003c")
    replacement = "const data = window.__KIET3D__;"
    standalone = html.replace(FETCH_LINE, replacement)
    tag = '<script>window.__KIET3D__='
    standalone = standalone.replace(
        '<script type="module">', tag + inline + "</script>\n<script type=\"module\">", 1
    )
    OUT.write_text(standalone)
    print(f"OK {OUT} {OUT.stat().st_size//1024}KB (payload {DATA.stat().st_size//1024}KB embedded)")

if __name__ == "__main__":
    main()
