"""Task 1 acceptance tests: coupled 1D/2D physics (SRS AC-02 .. AC-06)."""
import numpy as np
import pytest

from simulation import config as C
from simulation.drainage.network import generate, subcatchments
from simulation.drainage.swmm_export import to_inp
from simulation.hydraulics.boundary import Boundary
from simulation.hydraulics.network1d import circ_geom
from simulation.hydraulics.simulate import simulate
from simulation.surface.infiltration import RunoffModel
from simulation.terrain.twin import Twin


@pytest.fixture(scope="module")
def env():
    cf = C.load_all()
    twin = Twin(cf["terrain"])
    net = generate(twin, cf["drainage"], variant=0)
    return cf, twin, net


def _spec(**kw):
    s = {"seed": 7, "temporal": "peaked", "spatial": "uniform", "duration_h": 1.0,
         "total_mm": 80.0, "blockage_level": 0.0, "blockage_mode": "pipe_uniform"}
    s.update(kw)
    return s


def _run(env, **kw):
    cf, twin, net = env
    comp = kw.pop("components", None)
    return simulate(twin, net, _spec(**kw), cf["hydraulics"], cf["rainfall"], components=comp)


def test_terrain_metadata(env):
    _, twin, _ = env
    assert twin.meta["data_tier"] == 1 and twin.meta["vertical_datum"]
    assert (twin.dem_filled >= twin.dem - 1e-9)[twin.wet].all()
    assert twin.low_points[twin.wet].any()


def test_network_has_all_node_kinds(env):
    _, twin, net = env
    kinds = {n["kind"] for n in net["nodes"]}
    assert {"inlet", "junction", "storage", "outfall"} <= kinds
    assert any(e["kind"] == "pump" for e in net["edges"])
    # every pipe drops downstream (min slope honoured by inverts)
    inv = {n["id"]: n["invert_m"] for n in net["nodes"]}
    for e in net["edges"]:
        if e["kind"] == "pipe":
            assert inv[e["u"]] > inv[e["v"]]


def test_subcatchments_cover_domain(env):
    _, twin, net = env
    sc = subcatchments(twin, net)
    assert (sc >= 0)[twin.wet].mean() > 0.5


def test_circular_geometry():
    A, R = circ_geom(np.array([0.3]), np.array([0.6]))
    assert abs(A[0] - np.pi * 0.36 / 8) < 1e-9 and abs(R[0] - 0.15) < 1e-9


def test_runoff_chain_scs_vs_horton():
    cf = C.load_all()
    cls = np.array([[0, 1]]); wet = np.ones_like(cls, bool)
    for method in ("horton", "scs_cn"):
        hyd = dict(cf["hydraulics"], infiltration=dict(cf["hydraulics"]["infiltration"], method=method))
        m = RunoffModel(hyd, cls, wet)
        eff, _ = m.step(600, np.array([[60.0, 60.0]]), np.zeros((1, 2)))
        assert eff[0, 0] > eff[0, 1] >= 0  # road sheds more than open ground


def test_mass_conserved_tightly(env):
    r = _run(env, recession_h=0.5)
    assert abs(r["mass"]["rel_error"]) < 1e-6
    assert r["mass"]["capture_mm"] > 0 and r["mass"]["discharged_mm"] > 0


def test_drainage_reduces_flooding(env):
    full = _run(env)
    nodrain = _run(env, components={"drainage": False})
    assert nodrain["max_depth"].max() >= full["max_depth"].max()
    assert (nodrain["max_depth"] >= 0.05).sum() > (full["max_depth"] >= 0.05).sum()


def test_backwater_boundary_causes_reverse_flow(env):
    free = _run(env)
    high = _run(env, boundary={"type": "fixed_stage", "stage_m": 2.5})
    assert high["mass"]["boundary_in_mm"] > 0          # river water enters the network
    assert high["mass"]["overflow_mm"] > free["mass"]["overflow_mm"]
    assert abs(high["mass"]["rel_error"]) < 1e-6


def test_pump_failure_increases_surcharge(env):
    _, _, net = env
    pump = next(e["id"] for e in net["edges"] if e["kind"] == "pump")
    ok = _run(env)
    failed = _run(env, pump_status={pump: "failed"})
    assert failed["mass"]["overflow_mm"] > ok["mass"]["overflow_mm"]
    assert failed["pipe_flow"][:, pump].max() == 0


def test_boundary_kinds():
    assert Boundary({"type": "free"}).stage(100) == 0
    assert Boundary({"type": "fixed_stage", "stage_m": 1.2}).stage(0) == 1.2
    assert Boundary({"type": "timeseries", "times_min": [0, 60], "stages_m": [0, 2]}).stage(1800) == 1.0
    assert abs(Boundary({"type": "tidal", "amplitude_m": 1, "period_h": 1}).stage(900) - 1) < 1e-9


def test_swmm_export(env):
    _, _, net = env
    inp = to_inp(net)
    for sec in ("[JUNCTIONS]", "[OUTFALLS]", "[STORAGE]", "[CONDUITS]", "[PUMPS]", "[XSECTIONS]"):
        assert sec in inp
