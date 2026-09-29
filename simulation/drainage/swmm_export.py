"""Export a drainage network to an EPA SWMM 5 `.inp` file for independent cross-checking
of the 1D engine (open the file in EPA SWMM or run it with pyswmm).

Usage: python -m simulation.drainage.swmm_export --variant 0 --out outputs/swmm/net_v0.inp
"""
from __future__ import annotations

import argparse
import os


def to_inp(net, title="Drishti synthetic network", sim_hours=2, rain_mm_per_h=None):
    nodes, edges = net["nodes"], net["edges"]
    name = lambda k: f"N{k}"
    L = [f"[TITLE]\n{title} (synthetic/inferred, verified=false)\n",
         "[OPTIONS]\nFLOW_UNITS CMS\nFLOW_ROUTING DYNWAVE\nALLOW_PONDING NO\n"
         "START_DATE 01/01/2026\nSTART_TIME 00:00:00\nREPORT_STEP 00:05:00\n"
         "ROUTING_STEP 1\nEND_DATE 01/01/2026\n"
         f"END_TIME {int(sim_hours):02d}:00:00\n",
         "[JUNCTIONS]\n;Name Elev MaxDepth InitDepth SurDepth Aponded"]
    for n in nodes:
        if n["kind"] in ("inlet", "manhole", "junction"):
            L.append(f"{name(n['id'])} {n['invert_m']:.3f} {n['depth_m']:.3f} 0 0 0")
    L.append("\n[OUTFALLS]\n;Name Elev Type")
    for n in nodes:
        if n["kind"] == "outfall":
            L.append(f"{name(n['id'])} {n['invert_m']:.3f} FREE")
    L.append("\n[STORAGE]\n;Name Elev MaxDepth InitDepth Shape Area")
    for n in nodes:
        if n["kind"] == "storage":
            L.append(f"{name(n['id'])} {n['invert_m']:.3f} {n['depth_m']:.3f} 0 FUNCTIONAL 0 0 {n['area_m2']:.1f}")
    L.append("\n[CONDUITS]\n;Name From To Length Roughness InOffset OutOffset")
    xs = ["\n[XSECTIONS]\n;Link Shape Geom1"]
    pumps = ["\n[PUMPS]\n;Name From To Curve Status Startup Shutoff"]
    curves = ["\n[CURVES]\n;Name Type X Y"]
    for e in edges:
        lk = f"L{e['id']}"
        if e.get("kind") == "pump":
            p = e["pump"]
            pumps.append(f"{lk} {name(e['u'])} {name(e['v'])} PC{e['id']} ON {p['on_depth_m']} {p['off_depth_m']}")
            curves.append(f"PC{e['id']} PUMP3 0 {p['capacity_m3s']}\nPC{e['id']} 10 {p['capacity_m3s']}")
        else:
            L.append(f"{lk} {name(e['u'])} {name(e['v'])} {e['length_m']:.2f} {e['n']:.4f} 0 0")
            xs.append(f"{lk} CIRCULAR {e['diameter_m']:.3f} 0 0 0 1")
    L += xs + pumps + curves
    L.append("\n[COORDINATES]\n;Node X Y")
    for n in nodes:
        L.append(f"{name(n['id'])} {n['x']:.2f} {n['y']:.2f}")
    return "\n".join(L) + "\n"


def main():
    from simulation import config as C
    from simulation.drainage.network import generate
    from simulation.terrain.twin import Twin
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", type=int, default=0)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    net = generate(Twin(C.load("terrain")), C.load("drainage"), variant=a.variant)
    out = a.out or f"outputs/swmm/drishti_net_v{a.variant}.inp"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w", encoding="utf-8").write(to_inp(net))
    print("wrote", out)


if __name__ == "__main__":
    main()
