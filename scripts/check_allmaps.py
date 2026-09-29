for p in ["kiet_terrain_map.html","kiet_3d_standalone.html"]:
    h=open(p).read()
    assert "campus_accurate" in h, f"{p} missing accurate"
print("ALLMAPS OK")
