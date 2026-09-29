import json, math
# Anchors WGS84
A_LAT, A_LON = 28.75257, 77.49851
# Local ENU origin at A-Block SE corner; x=east(m), y=north(m)
# Control points: (e, n, lat, lon) - sanctioned ENU fitted to OSM/Google-verified
# centroids 2026-09-05 via satellite cross-check (browser-mcp). Letters matched
# A/B/C/E/F/G by name, D-star by unique star shape = OSM Auditorium.
CONTROLS = [
    (-22.85, 22.50, 28.75315, 77.49710),   # A-Block centroid -> OSM 'A block'
    (-117.50, 119.00, 28.75239, 77.49805), # B Boys -> OSM 'B-Block'
    (-106.00, 172.50, 28.75233, 77.49773), # C -> OSM 'C block'
    (-119.89, 107.50, 28.75217, 77.49829), # E Eng (40.23 front) -> OSM 'E-Block'
    (-147.75, 150.00, 28.75164, 77.49883), # F Boys -> OSM 'F Block'
    (-140.00, 153.00, 28.75291, 77.49852), # G -> OSM 'G Block'
    (-70.00, 60.00, 28.75209, 77.49982),   # D Lecture star -> OSM 'Auditorium'
]
def solve_affine(pts):
    # Solve lon = ax*e + bx*n + cx, lat = ay*e + by*n + cy via least squares (normal eq, 3x3)
    import copy
    def lstsq(M, Y):
        # M Nx3, Y N -> 3 coeffs
        MtM = [[0.0]*3 for _ in range(3)]
        MtY = [0.0]*3
        for i in range(len(M)):
            for a in range(3):
                MtY[a] += M[i][a]*Y[i]
                for b in range(3):
                    MtM[a][b] += M[i][a]*M[i][b]
        # invert 3x3
        def inv3(m):
            det = (m[0][0]*(m[1][1]*m[2][2]-m[1][2]*m[2][1])-m[0][1]*(m[1][0]*m[2][2]-m[1][2]*m[2][0])+m[0][2]*(m[1][0]*m[2][1]-m[1][1]*m[2][0]))
            assert abs(det) > 1e-18, "singular controls"
            adj = [[0.0]*3 for _ in range(3)]
            adj[0][0]=(m[1][1]*m[2][2]-m[1][2]*m[2][1])/det
            adj[0][1]=-(m[0][1]*m[2][2]-m[0][2]*m[2][1])/det
            adj[0][2]=(m[0][1]*m[1][2]-m[0][2]*m[1][1])/det
            adj[1][0]=-(m[1][0]*m[2][2]-m[1][2]*m[2][0])/det
            adj[1][1]=(m[0][0]*m[2][2]-m[0][2]*m[2][0])/det
            adj[1][2]=-(m[0][0]*m[1][2]-m[0][2]*m[1][0])/det
            adj[2][0]=(m[1][0]*m[2][1]-m[1][1]*m[2][0])/det
            adj[2][1]=-(m[0][0]*m[2][1]-m[0][1]*m[2][0])/det
            adj[2][2]=(m[0][0]*m[1][1]-m[0][1]*m[1][0])/det
            return adj
        inv = inv3(MtM)
        return [sum(inv[a][b]*MtY[b] for b in range(3)) for a in range(3)]
    M = [[e, n, 1.0] for e, n, la, lo in pts]
    clo = lstsq(M, [lo for e, n, la, lo in pts])
    cla = lstsq(M, [la for e, n, la, lo in pts])
    return clo, cla
CLO, CLA = solve_affine(CONTROLS)
def ENU_to_WGS84(e, n):
    lon = CLO[0]*e + CLO[1]*n + CLO[2]
    lat = CLA[0]*e + CLA[1]*n + CLA[2]
    return (round(lon, 5), round(lat, 5))
def rect(e0, n0, w, h):
    pts = [(e0,n0),(e0+w,n0),(e0+w,n0+h),(e0,n0+h),(e0,n0)]
    return [ENU_to_WGS84(e,n) for e,n in pts]
def build_accurate():
    feats = []
    # A-Block G+2 45.00x45.70 at origin
    feats.append({"type":"Feature","properties":{"kind":"sanctioned_building","sanctioned_name":"A","floors":"G+2","footprint_sqm":45.00*45.70,"confidence":"high","source":"11.jpeg 45.00x45.70"},"geometry":{"type":"Polygon","coordinates":[rect(-45.70,0.0,45.70,45.00)]}})
    # E-Block G+5 approx 40.23 frontage, 35m deep, 90m NW of A
    feats.append({"type":"Feature","properties":{"kind":"sanctioned_building","sanctioned_name":"E","floors":"G+5","footprint_sqm":1400,"confidence":"medium","source":"14.jpeg 40.23"},"geometry":{"type":"Polygon","coordinates":[rect(-140.0,90.0,40.23,35.0)]}})
    # Z-Block G+8 new compounding 748.31 sqm, 26.80 long
    feats.append({"type":"Feature","properties":{"kind":"sanctioned_building","sanctioned_name":"Z","floors":"G+8","footprint_sqm":748.31,"confidence":"high","source":"area chart row6"},"geometry":{"type":"Polygon","coordinates":[rect(-90.0,20.0,26.80,27.93)]}})
    # Y-Block G+5 compounding 28.70 wide
    feats.append({"type":"Feature","properties":{"kind":"sanctioned_building","sanctioned_name":"Y","floors":"G+5","footprint_sqm":748.31,"confidence":"medium","source":"14.jpeg 28.70"},"geometry":{"type":"Polygon","coordinates":[rect(-120.0,55.0,28.70,26.0)]}})
    # D-Lecture star G+2 (3-blade approx, centroid near -70,60)
    cx, cy = -70.0, 60.0
    star = [(cx+9.55,cy),(cx+4,cy+4),(cx-4,cy+9),(cx-9.55,cy),(cx-4,cy-4),(cx+4,cy-9),(cx+9.55,cy)]
    feats.append({"type":"Feature","properties":{"kind":"sanctioned_building","sanctioned_name":"D","floors":"G+2","footprint_sqm":900,"confidence":"medium","source":"14.jpeg star 9.55"},"geometry":{"type":"Polygon","coordinates":[[ENU_to_WGS84(e,n) for e,n in star]]}})
    # F-Boys G+3, S-Boys, B-Boys, J-Girls 40.17, L-TBI G+4, U G+4, V G+5 44.34, X, Pharmacy I/J, Canteen, C-1 demolish 41.76
    blocks = [("F","G+3",-160,140,24.51,20,"14.jpeg"),("S","G+? ",-175,150,30,18,"5.jpeg 534.10"),("B","G+3",-130,110,25,18,"5.jpeg 61.10"),("J","G+1",-210,100,40.17,22,"1.jpeg 40.17"),("L","G+4",-150,70,22,20,"14.jpeg"),("U","G+4",-135,70,20,18,"14.jpeg"),("V","G+5",-125,45,44.34,28,"5.jpeg 44.34"),("X","G+1",-230,160,28.95,18,"5.jpeg"),("I","G+4",-165,155,35.16,18,"14.jpeg 35.16"),("PharmaJ","G+2",-150,155,40.90,16,"14.jpeg 40.90"),("Canteen","G+2",-40,55,15,8,"8.jpeg 3.30"),("C1-demolish","G",-110,170,41.76,4.4,"demolish 41.76x184.78"),
        # Missing covered-schedule blocks (setback schedule totals 760.73): C, C1-exist, G, W, X1, Y1
        ("C","G+?",-115,165,18,15,"covered C 285.40"),("C1-exist","G",-108,168,12,7,"covered C1 83.59"),("G","G+?",-145,150,10,6,"covered G 29.55"),("W","G+?",-128,60,12,8,"covered W 45.66"),("X1","G+?",-225,150,10,6,"covered X1 23.22"),("Y1","G+?",-118,50,10,6,"covered Y1 27.54")]
    for nm, fl, e0, n0, w, h, src in blocks:
        feats.append({"type":"Feature","properties":{"kind":"sanctioned_building","sanctioned_name":nm,"floors":fl,"footprint_sqm":round(w*h,2),"confidence":"medium","source":src},"geometry":{"type":"Polygon","coordinates":[rect(e0,n0,w,h)]}})
    # Parking pockets A-R (areas from 1.jpeg table; dims where given, shapes approximated)
    parkings = [("A",1753.14,-45,2,45,39,"front 1753.14"),("B",278.40,-60,58,45.67,6.07,"B 45.67x6.07"),("B1",935.24,-55,62,45.40,20.60,"B1 45.40x20.60"),("D",442.50,-125,80,29.50,15.00,"D 29.50x15.00"),("E",764.60,-140,85,39.21,19.50,"E 39.21x19.50"),("F",193.02,-150,120,32.17,6.00,"F 32.17x6.00"),("G",345.00,-100,120,7.73,44.63,"G 7.73x44.63"),("H",377.87,-95,60,20,19,"H shape 377.87"),("I",521.56,-155,95,11.26,46.32,"I 11.26x46.32"),("J",565.60,-180,110,25,22,"J shape 565.60"),("L",1915.03,-90,25,30.57,62.44,"L 30.57x62.44"),("M",2748.70,-150,40,55,50,"M shape 2748.70"),("N",350.92,-120,48,25.39,17.07,"N 25.39x17.07"),("O",7820.55,-180,10,110,71,"O shape 7820.55 south"),("P",390.00,-70,40,20,19,"P shape 390.00"),("Q",539.60,-65,45,22,24,"Q shape 539.60"),("R",290.40,-60,50,18,16,"R shape 290.40")]
    for nm, area, e0, n0, w, h, src in parkings:
        feats.append({"type":"Feature","properties":{"kind":"parking","sanctioned_name":"P-"+nm,"area_sqm":area,"confidence":"medium","source":"1.jpeg parking "+src},"geometry":{"type":"Polygon","coordinates":[rect(e0,n0,w,h)]}})
    # Solar belts (pink text KW)
    solars = [("33KW",-115,175,30,8,"289 top"),("44-8KW",-95,175,25,8,"288 top"),("100KW",-60,175,30,8,"288 top"),("15KW",-30,175,25,8,"337.48/184.46"),("80KW",-200,130,20,10,"west 80"),("49KW",-185,115,18,10,"49"),("20KW",-170,125,16,10,"20"),("60KW",-160,60,16,10,"60"),("40KW",-50,10,20,10,"40 south"),("93-72KW",-220,80,25,12,"west 93-72")]
    for nm, e0, n0, w, h, src in solars:
        feats.append({"type":"Feature","properties":{"kind":"solar","sanctioned_name":"Solar-"+nm,"confidence":"medium","source":"solar "+src},"geometry":{"type":"Polygon","coordinates":[rect(e0,n0,w,h)]}})
    # Sanctioned roads (widths from plan)
    roads = [(0,5,120,6.0,"6M grid N-S"),(0,50,130,7.5,"7.5M spine"),(0,58,100,3.0,"3M service canteen"),(5,-5,10,200,"NH-58 45M frontage E"),(-100,195,150,8,"Railway Lane N")]
    for i,(e0,n0,w,h,src) in enumerate(roads):
        feats.append({"type":"Feature","properties":{"kind":"road_sanctioned","sanctioned_name":"R"+str(i+1),"width_m":h,"confidence":"medium","source":src},"geometry":{"type":"Polygon","coordinates":[rect(e0,n0,w,h)]}})
    # Khasra boundary approx (KIET core 280-282 + 286 strip)
    bnd = [(-240,200),(-40,200),(-40,180),(0,180),(0,-10),(-60,-10),(-60,20),(-240,20),(-240,200)]
    feats.append({"type":"Feature","properties":{"kind":"boundary_khasra","sanctioned_name":"KIET-khasra-280-282-286","confidence":"medium","source":"13.jpeg khasra"},"geometry":{"type":"Polygon","coordinates":[[ENU_to_WGS84(e,n) for e,n in bnd]]}})
    # Labels with centroids
    for f in [x for x in feats if x["properties"]["kind"]=="sanctioned_building"]:
        ring = f["geometry"]["coordinates"][0]
        lon = sum(p[0] for p in ring[:-1])/ (len(ring)-1)
        lat = sum(p[1] for p in ring[:-1])/ (len(ring)-1)
        feats.append({"type":"Feature","properties":{"kind":"label_accurate","sanctioned_name":f["properties"]["sanctioned_name"],"floors":f["properties"]["floors"],"lat":round(lat,5),"lon":round(lon,5)},"geometry":{"type":"Point","coordinates":[round(lon,5),round(lat,5)]}})
    # Snap matched blocks to OSM/Google-verified polygons (browser-mcp satellite
    # cross-check 2026-09-05). OSM geometry is the truth; sanctioned attrs kept.
    OSM_MATCH = {"A":"A block","B":"B-Block","C":"C block","E":"E-Block","F":"F Block","G":"G Block","D":"Auditorium","L":"TBI"}
    try:
        osm = json.load(open("data/campus.geojson"))
        omap = {}
        for f in osm["features"]:
            if f["geometry"]["type"] == "Polygon" and f["properties"].get("name"):
                omap[f["properties"]["name"]] = f["geometry"]["coordinates"]
        for f in feats:
            p = f["properties"]
            if p.get("kind") == "sanctioned_building" and p.get("sanctioned_name") in OSM_MATCH:
                oname = OSM_MATCH[p["sanctioned_name"]]
                if oname in omap:
                    f["geometry"]["coordinates"] = omap[oname]
                    p["confidence"] = "high"
                    p["osm_match"] = oname
                    p["real_name"] = oname
        # rebuild labels from final (possibly snapped) geometry
        feats = [f for f in feats if f["properties"].get("kind") != "label_accurate"]
        for f in [x for x in feats if x["properties"]["kind"]=="sanctioned_building"]:
            ring = f["geometry"]["coordinates"][0]
            lon = sum(p[0] for p in ring[:-1])/ (len(ring)-1)
            lat = sum(p[1] for p in ring[:-1])/ (len(ring)-1)
            lp = {"kind":"label_accurate","sanctioned_name":f["properties"]["sanctioned_name"],"floors":f["properties"]["floors"],"lat":round(lat,5),"lon":round(lon,5)}
            if "real_name" in f["properties"]:
                lp["real_name"] = f["properties"]["real_name"]
            feats.append({"type":"Feature","properties":lp,"geometry":{"type":"Point","coordinates":[round(lon,5),round(lat,5)]}})
    except FileNotFoundError:
        pass
    fc = {"type":"FeatureCollection","name":"KIET sanctioned accurate","features":feats}
    # SHIP ONLY VERIFIED GEOMETRY. Everything placed via the guessed-ENU affine
    # (unmatched blocks, parking, solar, sanctioned roads, hand-drawn khasra) is
    # dimension-true but position-unverified: write it to a separate file that no
    # map loads, instead of rendering guesses as facts.
    verified, unverified = [], []
    verified_names = set(
        f["properties"].get("sanctioned_name") for f in feats
        if f["properties"].get("kind") == "sanctioned_building" and "osm_match" in f["properties"]
    )
    for f in feats:
        p = f["properties"]
        if p.get("kind") == "label_accurate" and p.get("sanctioned_name") in verified_names:
            verified.append(f)
        elif p.get("kind") == "sanctioned_building" and "osm_match" in p:
            verified.append(f)
        else:
            if p.get("kind") == "sanctioned_building":
                p["confidence"] = "low"
            unverified.append(f)
    # Khasra layer from the OSM/Google-verified boundary ring (same land, no invention)
    try:
        osm2 = json.load(open("data/campus.geojson"))
        for f in osm2["features"]:
            if f["properties"].get("kind") == "boundary" and f["geometry"]["type"] == "Polygon":
                verified.append({"type":"Feature","properties":{"kind":"boundary_khasra","sanctioned_name":"KIET-khasra-280-282-286","confidence":"high","source":"OSM boundary ring, khasra nos from 13.jpeg Shizra"},"geometry":f["geometry"]})
                break
    except FileNotFoundError:
        pass
    json.dump({"type":"FeatureCollection","name":"KIET sanctioned accurate (verified only)","features":verified}, open("data/campus_accurate.geojson","w"), indent=1)
    json.dump({"type":"FeatureCollection","name":"KIET sanctioned sketch (UNVERIFIED positions, do not render)","features":unverified}, open("data/campus_sanctioned_unverified.geojson","w"), indent=1)
    print(f"Wrote {len(verified)} verified + {len(unverified)} unverified feats")
def write_centroids():
    import csv
    acc = json.load(open("data/campus_accurate.geojson"))
    rows = []
    for f in acc["features"]:
        if f["properties"].get("kind") == "label_accurate":
            p = f["properties"]
            rows.append({"name":p["sanctioned_name"],"lat":p["lat"],"lon":p["lon"],"floors":p["floors"],"area":"","source":"campus_accurate"})
    # fill area from buildings
    am = {f["properties"]["sanctioned_name"]:f["properties"].get("footprint_sqm","") for f in acc["features"] if f["properties"].get("kind")=="sanctioned_building"}
    for r in rows:
        r["area"] = am.get(r["name"],"")
    w = csv.DictWriter(open("data/blocks_centroids.csv","w",newline=""), fieldnames=["name","lat","lon","floors","area","source"])
    w.writeheader(); w.writerows(sorted(rows, key=lambda x: x["name"]))
    print(f"Wrote {len(rows)} centroids")
if __name__ == "__main__":
    build_accurate()
    write_centroids()
