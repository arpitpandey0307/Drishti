def test_route_avoids_flood():
    import numpy as np
    from api.route import safe_route
    depth = np.zeros((10, 10), np.float32)
    depth[4, :9] = 0.5  # wall of water with a gap at col 9
    valid = np.ones((10, 10), bool)
    r = safe_route(depth, valid, (0, 0), (9, 9), thresh=0.05)
    assert not r["blocked"] and all(depth[p] < 0.05 for p in r["path"])


def test_route_blocked_when_sealed():
    import numpy as np
    from api.route import safe_route
    depth = np.zeros((7, 7), np.float32)
    depth[3, :] = 0.5
    valid = np.ones((7, 7), bool)
    r = safe_route(depth, valid, (0, 0), (6, 6), thresh=0.05)
    assert r["blocked"]
