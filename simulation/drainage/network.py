"""Synthetic stormwater drainage network as a directed graph G = (V, E)  (SRS Module G).

Nodes: inlet | manhole | junction | storage | outfall.  Links: pipe | pump.
EVERY asset is synthetic: verified=False, source="synthetic/inferred". The schema matches a
real municipal survey, so a real network JSON can be dropped in without code changes.

Generation:
 1. Candidate score = log flow accumulation + low-point bonus + road bonus (+ variant noise).
 2. Greedy pick with `inlet_spacing_m` exclusion up to `target_inlets`.
 3. Outfalls = lowest domain-edge cells (water leaves the campus there).
 4. Tree: Dijkstra from the outfalls over node pairs closer than `max_length_m`, cost =
    length with an uphill-ground penalty -> every node has one downstream link (a DAG).
 5. Pipe sizing by the Rational method on each node's accumulated catchment area.
 6. Inverts laid upstream -> downstream with cover depth and minimum slope.
 7. Optional pump station: a storage sump + pump link in front of outfall 0.
"""
from __future__ import annotations

import heapq

import numpy as np

SOURCE = "synthetic/inferred"


def pipe_capacity(diameter_m, slope, n):
    """Manning full-flow capacity of a circular pipe (m3/s)."""
    A = np.pi * diameter_m ** 2 / 4.0
    R = diameter_m / 4.0
    return float(A * R ** (2.0 / 3.0) * np.sqrt(max(slope, 1e-6)) / n)


def _pick_inlets(twin, cfg, rng, variant):
    wet = twin.wet
    score = np.log1p(twin.accum)
    if cfg["placement"].get("low_point_bonus", True):
        score = score + 1.5 * twin.low_points
    near_road = np.zeros_like(wet)
    buf = int(np.ceil(cfg["placement"]["road_buffer_m"] / twin.dx))
    ri, rj = np.where(twin.is_road)
    for di in range(-buf, buf + 1):
        for dj in range(-buf, buf + 1):
            a, b = np.clip(ri + di, 0, twin.ny - 1), np.clip(rj + dj, 0, twin.nx - 1)
            near_road[a, b] = True
    score = score + 2.0 * twin.is_road + 1.0 * near_road
    if variant:
        score = score + rng.normal(0, 0.6, score.shape)
    score = np.where(wet, score, -np.inf)
    excl = cfg["inlet_spacing_m"] / twin.dx
    picked = []
    for flat in np.argsort(-score, axis=None):
        i, j = divmod(int(flat), twin.nx)
        if not np.isfinite(score[i, j]):
            break
        if all((i - a) ** 2 + (j - b) ** 2 >= excl ** 2 for a, b in picked):
            picked.append((i, j))
            if len(picked) >= cfg["target_inlets"]:
                break
    return picked


def _pick_outfalls(twin, cfg, taken):
    wet = twin.wet
    ny, nx = wet.shape
    edge = np.zeros_like(wet)
    for i, j in zip(*np.where(wet)):
        for di, dj in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            a, b = i + di, j + dj
            if not (0 <= a < ny and 0 <= b < nx) or not twin.in_domain[a, b]:
                edge[i, j] = True
    cand = sorted(zip(*np.where(edge)), key=lambda c: twin.dem[c])
    min_sep = 100.0 / twin.dx
    outs = []
    for c in cand:
        if all((c[0] - o[0]) ** 2 + (c[1] - o[1]) ** 2 >= min_sep ** 2 for o in outs) and c not in taken:
            outs.append((int(c[0]), int(c[1])))
            if len(outs) >= int(cfg["outfalls"]["count"]):
                break
    return outs


def _tree(xy, ground, outfall_idx, max_len):
    """Dijkstra from outfalls; returns downstream[k] for every node (outfalls -> -1)."""
    n = len(xy)
    d = np.hypot(xy[:, None, 0] - xy[None, :, 0], xy[:, None, 1] - xy[None, :, 1])
    dist = np.full(n, np.inf)
    down = np.full(n, -1)
    pq = []
    for o in outfall_idx:
        dist[o] = 0.0
        heapq.heappush(pq, (0.0, o))
    while pq:
        dv, v = heapq.heappop(pq)
        if dv > dist[v]:
            continue
        for u in np.where((d[v] <= max_len) & (d[v] > 0))[0]:
            if u in outfall_idx:
                continue
            uphill = max(ground[v] - ground[u], 0.0)  # water would have to climb
            c = dv + d[u, v] * (1.0 + 2.0 * uphill)
            if c < dist[u]:
                dist[u], down[u] = c, v
                heapq.heappush(pq, (c, u))
    # disconnected nodes: trunk link to the nearest connected node
    for u in range(n):
        if down[u] == -1 and u not in outfall_idx:
            ok = [v for v in range(n) if v != u and (np.isfinite(dist[v]))]
            v = min(ok, key=lambda v: d[u, v])
            down[u] = v
            dist[u] = dist[v] + d[u, v]
    return down, d


def generate(twin, cfg, seed=26085, variant=0):
    rng = np.random.default_rng(int(seed) * 100 + int(variant))
    unc = cfg.get("uncertainty", {})
    pc = cfg["pipes"]
    ncfg = cfg["nodes"]

    inlets = _pick_inlets(twin, cfg, rng, variant)
    outs = _pick_outfalls(twin, cfg, set(inlets))
    cells = inlets + outs
    n = len(cells)
    out_idx = set(range(len(inlets), n))
    xy = np.array([(twin.X[c], twin.Y[c]) for c in cells])
    ground = np.array([twin.dem[c] for c in cells])
    down, dmat = _tree(xy, ground, out_idx, float(pc["max_length_m"]))

    # contributing area per node: D8 cells draining to the node cell, accumulated down the tree
    order = np.argsort(-np.array([dmat[k, down[k]] if down[k] >= 0 else 0 for k in range(n)]))
    area = np.array([twin.accum[c] * twin.dx ** 2 for c in cells])
    n_up = np.zeros(n, int)
    for k in range(n):
        if down[k] >= 0:
            n_up[down[k]] += 1
    # topological order (upstream first): Kahn on the tree
    indeg = n_up.copy()
    topo, stack = [], [k for k in range(n) if indeg[k] == 0]
    while stack:
        k = stack.pop()
        topo.append(k)
        if down[k] >= 0:
            indeg[down[k]] -= 1
            if indeg[down[k]] == 0:
                stack.append(down[k])
    acc_area = area.copy()
    for k in topo:
        if down[k] >= 0:
            acc_area[down[k]] += acc_area[k]

    # inverts, upstream -> downstream
    depth0 = float(ncfg["depth_m"])
    smin, smax = float(pc["min_slope"]), float(pc["max_slope"])
    invert = ground - depth0 * (1 + (rng.uniform(-0.1, 0.1, n) if variant else 0))
    for k in topo:
        v = down[k]
        if v >= 0:
            L = max(dmat[k, v], twin.dx)
            invert[v] = min(invert[v], invert[k] - smin * L)
    # design sizing: Rational method Q = C i A, i = design intensity
    C, i_mmh = 0.8, float(pc.get("design_intensity_mmh", 40.0))
    diam_list = sorted(pc["diameters_m"])
    nodes, edges = [], []
    for k, (i, j) in enumerate(cells):
        kind = "outfall" if k in out_idx else (
            "junction" if n_up[k] >= 2 else ("inlet" if twin.is_road[i, j] or twin.low_points[i, j] else "manhole"))
        nodes.append({
            "id": k, "kind": kind, "i": int(i), "j": int(j),
            "x": float(xy[k, 0]), "y": float(xy[k, 1]),
            "lat": float(twin.lat[i, j]), "lon": float(twin.lon[i, j]),
            "ground_m": float(ground[k]), "rim_m": float(ground[k] + ncfg.get("rim_offset_m", 0.0)),
            "invert_m": float(invert[k]), "depth_m": float(ground[k] - invert[k]),
            "area_m2": float(ncfg["storage_area_m2"]),
            "inlet_capacity_m3s": float(ncfg["inlet_capacity_m3s"]) if kind != "outfall" else 0.0,
            "catchment_area_m2": float(acc_area[k]),
            "verified": False, "source": SOURCE, "confidence": round(float(rng.uniform(0.3, 0.7)), 2),
        })
    for k in topo:
        v = down[k]
        if v < 0:
            continue
        L = float(max(dmat[k, v], twin.dx))
        S = float(np.clip((invert[k] - invert[v]) / L, smin, smax))
        n_man = float(rng.uniform(*unc["roughness_range"])) if variant else float(pc["manning_n"])
        Qd = C * i_mmh / 3.6e6 * acc_area[k]
        D = next((d for d in diam_list if pipe_capacity(d, S, n_man) >= Qd), diam_list[-1])
        if variant and rng.random() < 0.25:  # legacy under-sizing
            D = diam_list[max(0, diam_list.index(D) - 1)]
        edges.append({
            "id": len(edges), "u": int(k), "v": int(v), "kind": "pipe", "length_m": L,
            "diameter_m": float(D), "slope": S, "n": n_man,
            "capacity_m3s": pipe_capacity(D, S, n_man),
            "verified": False, "source": SOURCE, "confidence": round(float(rng.uniform(0.3, 0.7)), 2),
        })
    net = {"nodes": nodes, "edges": edges, "variant": int(variant), "seed": int(seed),
           "provenance": "synthetic", "verified": False}
    ps = cfg.get("pump_station", {})
    if ps.get("enabled", False):
        _add_pump_station(net, ps)
    return net


def _add_pump_station(net, ps):
    """Insert storage sump + pump in front of the first outfall: pipes -> sump -> pump -> outfall."""
    nodes, edges = net["nodes"], net["edges"]
    of = next(nd for nd in nodes if nd["kind"] == "outfall")
    sid = len(nodes)
    sump = dict(of, id=sid, kind="storage", area_m2=float(ps["storage_area_m2"]),
                invert_m=of["invert_m"] - float(ps.get("sump_extra_depth_m", 1.0)),
                inlet_capacity_m3s=0.0, catchment_area_m2=of["catchment_area_m2"])
    sump["depth_m"] = sump["ground_m"] - sump["invert_m"]
    nodes.append(sump)
    for e in edges:
        if e["v"] == of["id"]:
            e["v"] = sid
    cap = float(ps["capacity_m3s"])
    edges.append({
        "id": len(edges), "u": sid, "v": of["id"], "kind": "pump", "length_m": 5.0,
        "diameter_m": 0.6, "slope": 0.01, "n": 0.013, "capacity_m3s": cap,
        "pump": {"capacity_m3s": cap, "on_depth_m": float(ps["on_depth_m"]),
                 "off_depth_m": float(ps["off_depth_m"]), "status": "auto"},
        "verified": False, "source": SOURCE, "confidence": 0.5,
    })


def subcatchments(twin, net):
    """Grid of node ids: each wet cell is assigned to the first network node reached by
    following its D8 flow path (-1 = leaves the domain without meeting an inlet)."""
    from simulation.terrain.twin import D8
    node_at = -np.ones(twin.dem.shape, int)
    for nd in net["nodes"]:
        if nd["kind"] in ("inlet", "manhole", "junction"):
            node_at[nd["i"], nd["j"]] = nd["id"]
    out = -np.ones(twin.dem.shape, int)
    for i, j in zip(*np.where(twin.wet)):
        path, a, b = [], i, j
        while True:
            if out[a, b] != -1 or node_at[a, b] != -1:
                tgt = out[a, b] if out[a, b] != -1 else node_at[a, b]
                break
            path.append((a, b))
            k = twin.flowdir[a, b]
            if k < 0 or len(path) > 5000:
                tgt = -1
                break
            a, b = a + D8[k][0], b + D8[k][1]
        for p in path:
            out[p] = tgt
    return out
