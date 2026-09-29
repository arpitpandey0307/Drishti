"""Physics / stability / graph validation checks."""
import numpy as np, math

def check_surface(res, twin, tol=0.05):
    errs = []
    H = res["depth"]
    if not np.all(np.isfinite(H)): errs.append("NaN/Inf in depth")
    if (H < -1e-9).any(): errs.append("negative depth")
    if H.max() > 2.0: errs.append(f"unphysical max depth {H.max():.2f} m")
    if res["velocity"].max() > 3.0: errs.append("velocity cap exceeded")
    # rainfall -> runoff monotonic proxy: more rain => >= ponding (checked across suite, not single)
    return errs

def check_mass(res, tol=0.35):
    m = res["mass"]
    lhs = m["rain_mm"]
    # capture (drain_mm) splits into node storage + outfall discharge;
    # use discharged + stored (conservative quantities), not capture.
    rhs = (m["infil_mm"] + m.get("depression_mm", 0) + m.get("discharged_mm", 0)
           + m.get("node_stored_mm", 0) + m["ponded_mm"])
    err = abs(lhs - rhs) / max(lhs, 1e-6)
    return err, err <= tol

def check_blockage_effect(res_free, res_blocked):
    d0 = res_free["mass"]["drain_mm"]; d1 = res_blocked["mass"]["drain_mm"]
    return d1 <= d0 * 1.05, d0, d1

def check_lowpoints_accumulate(twin, res):
    lp = twin.low_points & twin.in_domain
    rest = twin.in_domain & (~twin.low_points) & (~twin.is_building)
    if lp.sum() == 0 or rest.sum() == 0: return True, 0, 0
    a = res["max_depth"][lp].mean(); b = res["max_depth"][rest].mean()
    return a >= b * 0.8, float(a), float(b)

def check_graph(net):
    errs = []
    ids = {n["id"] for n in net["nodes"]}
    for e in net["edges"]:
        if e["u"] not in ids or e["v"] not in ids: errs.append(f"edge {e['id']} bad endpoint")
        if e["length_m"] <= 0: errs.append(f"edge {e['id']} negative length")
        if not (0.1 <= e["diameter_m"] <= 2.0): errs.append(f"edge {e['id']} bad diameter")
        if not (0.0005 <= e["slope"] <= 0.2): errs.append(f"edge {e['id']} bad slope")
        if e["capacity_m3s"] <= 0 or not math.isfinite(e["capacity_m3s"]): errs.append(f"edge {e['id']} bad capacity")
    # orphans
    deg = {n["id"]: 0 for n in net["nodes"]}
    for e in net["edges"]:
        deg[e["u"]] += 1; deg[e["v"]] += 1
    orph = [k for k, v in deg.items() if v == 0]
    if orph: errs.append(f"orphan nodes: {orph[:5]}")
    outs = [n for n in net["nodes"] if n["kind"] == "outfall"]
    if not outs: errs.append("no outfall")
    return errs
