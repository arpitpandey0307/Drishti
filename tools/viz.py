"""Viz tools: terrain / network / flood PNGs + GeoJSON. Synthetic labels mandatory."""
import json, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def _im(ax, arr, title, cmap="viridis", vmin=None, vmax=None):
    im = ax.imshow(arr, cmap=cmap, vmin=vmin, vmax=vmax, origin="upper")
    ax.set_title(title, fontsize=9); ax.axis("off")
    plt.colorbar(im, ax=ax, fraction=0.046)

def plot_scenario_grids(twin, net, res, out_png):
    fig, ax = plt.subplots(2, 3, figsize=(13, 8))
    _im(ax[0, 0], np.where(twin.in_domain, twin.dem, np.nan), "DEM (m) — 30m source, upsampled SYNTHETIC")
    lc = np.where(twin.is_building, 2, np.where(twin.is_road, 1, np.where(twin.in_domain, 0, -1)))
    from matplotlib.colors import ListedColormap
    cmap_lc = ListedColormap(["#1f77b4", "#2ca02c", "#7f7f7f", "#d62728"])  # outside, open, road, building
    im = ax[0, 1].imshow(lc + 1, cmap=cmap_lc, vmin=0, vmax=3, origin="upper", interpolation="nearest")
    ax[0, 1].set_title("Landcover: blue=outside green=open grey=road red=building", fontsize=9)
    ax[0, 1].axis("off")
    a = ax[0, 2]; a.set_title("SYNTHETIC drainage (red=inlet, blue=outfall)", fontsize=9); a.axis("off")
    a.imshow(np.where(twin.in_domain, twin.dem, np.nan), cmap="gray", origin="upper", alpha=0.5)
    for nd in net["nodes"]:
        a.plot(nd["j"], nd["i"], "ro" if nd["kind"] == "inlet" else "bo", ms=3)
    for e in net["edges"]:
        u = net["nodes"][e["u"]]; v = net["nodes"][e["v"]]
        a.plot([u["j"], v["j"]], [u["i"], v["i"]], "r-", lw=0.5, alpha=0.6)
    _im(ax[1, 0], res["rain"].sum(axis=0), "Event rainfall total (mm)", cmap="Blues")
    _im(ax[1, 1], res["max_depth"], "Max water depth (m)", cmap="Blues", vmin=0, vmax=max(0.2, res["max_depth"].max()))
    _im(ax[1, 2], res["flooded"].any(axis=0) if res["flooded"].ndim == 3 else res["flooded"], "Flood extent (depth>5cm)", cmap="Reds", vmin=0, vmax=1)
    fig.suptitle("KIET flood digital twin — SYNTHETIC drainage + interpolated DEM (NOT real infrastructure)", fontsize=10)
    fig.tight_layout()
    fig.savefig(out_png, dpi=110)
    plt.close(fig)

def export_network_geojson(net, out_path):
    feats = []
    for nd in net["nodes"]:
        feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [nd["lon"], nd["lat"]]},
                      "properties": {k: nd[k] for k in ("id", "kind", "ground_m", "confidence", "source", "verified")}})
    for e in net["edges"]:
        u = net["nodes"][e["u"]]; v = net["nodes"][e["v"]]
        feats.append({"type": "Feature", "geometry": {"type": "LineString",
                      "coordinates": [[u["lon"], u["lat"]], [v["lon"], v["lat"]]]},
                      "properties": {k: e[k] for k in ("id", "u", "v", "diameter_m", "slope", "capacity_m3s", "confidence", "source", "verified")}})
    json.dump({"type": "FeatureCollection", "features": feats,
               "note": "SYNTHETIC network — NOT real KIET infrastructure"}, open(out_path, "w"))
