"""Physics + graph + stability tests for the KIET flood simulator."""
import yaml
from simulation.terrain.twin import Twin
from simulation.drainage.network import generate, pipe_capacity
from simulation.hydraulics.simulate import simulate
from simulation.validation.checks import (
    check_surface, check_mass, check_lowpoints_accumulate, check_graph, check_blockage_effect)
from simulation.rainfall.generator import generate as gen_rain

def _cfgs():
    return (yaml.safe_load(open("config/terrain.yaml")),
            yaml.safe_load(open("config/drainage.yaml")),
            yaml.safe_load(open("config/rainfall.yaml")),
            yaml.safe_load(open("config/hydraulics.yaml")))

def _spec(**kw):
    s = {"seed": 7, "temporal": "peaked", "spatial": "uniform", "duration_h": 1.0,
         "total_mm": 60.0, "network_variant": 0, "blockage_level": 0.0, "blockage_mode": "pipe_uniform"}
    s.update(kw)
    return s

def test_manning_capacity():
    q = pipe_capacity(0.6, 0.005, 0.013)
    assert 0.2 < q < 1.0, q

def test_twin_loads():
    ter, _, _, _ = _cfgs()
    t = Twin(ter)
    assert t.dem.shape == (ter["domain"]["ny"], ter["domain"]["nx"])
    assert t.in_domain.sum() > 1000
    assert t.is_road.sum() > 10
    assert (t.accum[t.in_domain] >= 1).all()

def test_graph_valid():
    ter, dra, _, _ = _cfgs()
    t = Twin(ter)
    for v in range(3):
        net = generate(t, dra, seed=26085, variant=v)
        assert check_graph(net) == [], check_graph(net)
        for nd in net["nodes"]:
            assert nd["verified"] is False and nd["source"] == "synthetic/inferred"

def test_rainfall_normalisation():
    ter, _, rain, _ = _cfgs()
    t = Twin(ter)
    spec = _spec(total_mm=100.0, duration_h=3.0)
    r = gen_rain(spec, t.X, t.Y, rain)
    assert r["rain_mm_per_step"].shape[0] == 36  # 3h / 5min
    assert (r["rain_mm_per_step"] >= 0).all()

def test_simulation_conserves_mass():
    ter, dra, rain, hyd = _cfgs()
    t = Twin(ter)
    net = generate(t, dra, seed=26085, variant=0)
    res = simulate(t, net, _spec(), hyd, rain)
    assert check_surface(res, t) == []
    err, ok = check_mass(res)
    assert ok, err

def test_blockage_reduces_drainage():
    ter, dra, rain, hyd = _cfgs()
    t = Twin(ter)
    net = generate(t, dra, seed=26085, variant=0)
    free = simulate(t, net, _spec(blockage_level=0.0), hyd, rain)
    blocked = simulate(t, net, _spec(blockage_level=0.75), hyd, rain)
    ok, d0, d1 = check_blockage_effect(free, blocked)
    assert ok, (d0, d1)

def test_lowpoints_accumulate():
    ter, dra, rain, hyd = _cfgs()
    t = Twin(ter)
    net = generate(t, dra, seed=26085, variant=0)
    res = simulate(t, net, _spec(total_mm=100.0, duration_h=2.0), hyd, rain)
    ok, a, b = check_lowpoints_accumulate(t, res)
    assert ok, (a, b)

def test_rainfall_runoff_monotonic():
    ter, dra, rain, hyd = _cfgs()
    t = Twin(ter)
    net = generate(t, dra, seed=26085, variant=0)
    small = simulate(t, net, _spec(total_mm=20.0, seed=11), hyd, rain)
    big = simulate(t, net, _spec(total_mm=120.0, seed=11), hyd, rain)
    assert big["max_depth"].max() >= small["max_depth"].max()
