h = open("kiet_road_map.html").read()
assert "campus_accurate.geojson" in h, "accurate not wired"
assert "Esri" in h or "World_Imagery" in h, "satellite missing"
assert "'Sanctioned blocks'" not in h, "blue sanctioned layer still present"
assert "'Accurate labels'" in h, "accurate labels missing"
print("ROADMAP WIRED OK")
