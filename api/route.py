"""Flood-safe routing: A* on 5m grid, flooded cells blocked."""
import heapq


def safe_route(depth, valid, start, end, thresh=0.05):
    import numpy as np
    ny, nx = depth.shape
    ok = (np.asarray(valid, bool)) & (np.asarray(depth) < thresh)
    if not ok[start] or not ok[end]:
        return {"path": [], "length_m": 0.0, "blocked": True}
    openh, came, gs = [(0.0, start)], {start: None}, {start: 0.0}
    while openh:
        _, cur = heapq.heappop(openh)
        if cur == end:
            break
        r, c = cur
        for dr, dc, w in ((1, 0, 5.0), (-1, 0, 5.0), (0, 1, 5.0), (0, -1, 5.0),
                          (1, 1, 7.07), (1, -1, 7.07), (-1, 1, 7.07), (-1, -1, 7.07)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < ny and 0 <= nc < nx and ok[nr, nc] and (nr, nc) not in gs:
                gs[(nr, nc)] = gs[cur] + w
                heapq.heappush(openh, (gs[(nr, nc)] + abs(nr - end[0]) * 5.0
                                       + abs(nc - end[1]) * 5.0, (nr, nc)))
                came[(nr, nc)] = cur
    if end not in came:
        return {"path": [], "length_m": 0.0, "blocked": True}
    path, cur = [], end
    while cur is not None:
        path.append(cur)
        cur = came[cur]
    return {"path": path[::-1], "length_m": gs[end], "blocked": False}
