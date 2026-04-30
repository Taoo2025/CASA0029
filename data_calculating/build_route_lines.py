"""
Build route_lines.geojson  - compact line geometry for all 540 routes.
Build London_Stops_With_Routes.geojson - add rail line membership to rail stops.

Output: route_lines.geojson
  Each feature: { route, mode, color, geometry (LineString or MultiLineString) }
"""

import json, math, os
from collections import defaultdict
from pathlib import Path
import geopandas as gpd
from shapely.ops import unary_union, linemerge
from shapely.geometry import mapping, MultiLineString, LineString

BASE = Path(__file__).resolve().parent
DATA = BASE / "DATA"

# TfL brand colours (matches HTML RAIL_LINE_INFO)
RAIL_COLORS = {
    "Bakerloo":           "#8C4729",
    "Central":            "#E21836",
    "Circle":             "#FFD300",
    "District":           "#00A651",
    "Hammersmith & City": "#F3A9BB",
    "Jubilee":            "#A0A5A9",
    "Metropolitan":       "#9B0056",
    "Northern":           "#1C1C1C",
    "Piccadilly":         "#003688",
    "Victoria":           "#0098D4",
    "Waterloo & City":    "#95CDBA",
    "DLR":                "#00A4A7",
    "Elizabeth Line":     "#6950A1",
    "Overground":         "#EE7C0E",
    "Tramlink":           "#84B817",
}
BUS_COLOR = "#e05c5c"   # generic bus line colour

# ── 1. OSM rail lines ─────────────────────────────────────────────────────────
def classify_rail_name(name):
    """Return list of TfL line names this OSM segment belongs to."""
    if not name:
        return []
    n = name.lower()
    lines = []
    if "bakerloo"       in n: lines.append("Bakerloo")
    if "central"        in n: lines.append("Central")
    if "circle"         in n: lines.append("Circle")
    if "district"       in n: lines.append("District")
    if "hammersmith"    in n: lines.append("Hammersmith & City")
    if "jubilee"        in n: lines.append("Jubilee")
    if "metropolitan"   in n: lines.append("Metropolitan")
    if "northern"       in n: lines.append("Northern")
    if "piccadilly"     in n: lines.append("Piccadilly")
    if "victoria"       in n: lines.append("Victoria")
    if "waterloo"       in n: lines.append("Waterloo & City")
    if "docklands" in n or n == "dlr": lines.append("DLR")
    if "elizabeth" in n: lines.append("Elizabeth Line")
    if "overground" in n: lines.append("Overground")
    if "trams" in n or "tramlink" in n or "london tram" in n: lines.append("Tramlink")
    # deduplicate while preserving order
    seen = set()
    return [x for x in lines if not (x in seen or seen.add(x))]

print("Loading OSM railways …")
osm = gpd.read_file(DATA / "greater-london-260427-free.shp" / "gis_osm_railways_free_1.shp")
# Keep subway, light_rail, tram, and rail (for Overground/Elizabeth)
osm_rail = osm[osm["fclass"].isin(["subway", "light_rail", "tram", "rail"])].copy()
osm_rail = osm_rail.to_crs("EPSG:4326")

rail_segs = defaultdict(list)  # line_name -> list of geometries
for _, row in osm_rail.iterrows():
    lines = classify_rail_name(row.get("name"))
    for ln in lines:
        rail_segs[ln].append(row.geometry)

print("Rail segments per line:")
for ln, segs in sorted(rail_segs.items()):
    print(f"  {ln}: {len(segs)} segments")

# ── 2. Bus route lines ────────────────────────────────────────────────────────
print("\nLoading bus routes …")
bus_gdf = gpd.read_file(DATA / "Bus_Routes__direction_of_travel_.geojson")
bus_gdf = bus_gdf[bus_gdf["STATUS"] == "CURRENT"]

# Load which bus routes we actually use in the impacts file
with open(BASE / "route_grid_impacts_osm_network.json", encoding="utf-8") as f:
    impacts = json.load(f)
all_route_ids = set(impacts["route_grid_loss"].keys())
# keep bus routes only (exclude N/UL and rail lines)
RAIL_NAMES = set(RAIL_COLORS.keys())
bus_route_ids = {r for r in all_route_ids if r not in RAIL_NAMES
                 and not r.startswith("N") and not r.startswith("UL")}
print(f"  Bus routes to draw: {len(bus_route_ids)}")

# Filter and merge Out/In directions per route
bus_gdf = bus_gdf[bus_gdf["ROUTE"].isin(bus_route_ids)]
print(f"  Bus features after filter: {len(bus_gdf)}")

bus_segs = defaultdict(list)  # route_id -> list of geometries
for _, row in bus_gdf.iterrows():
    bus_segs[row["ROUTE"]].append(row.geometry)

# ── 3. Assemble features ──────────────────────────────────────────────────────
print("\nMerging and simplifying geometries …")
features = []
SIMPLIFY_DEG = 0.0001   # ~10 m at London latitude — keeps visual fidelity

def geom_to_multilinestring(geom):
    """Flatten any geometry to a MultiLineString for JSON serialisation."""
    if geom is None or geom.is_empty:
        return None
    if geom.geom_type == "LineString":
        return MultiLineString([geom])
    if geom.geom_type == "MultiLineString":
        return geom
    if geom.geom_type == "GeometryCollection":
        lines = [g for g in geom.geoms if g.geom_type in ("LineString", "MultiLineString")]
        if not lines:
            return None
        coords = []
        for g in lines:
            if g.geom_type == "LineString":
                coords.append(g)
            else:
                coords.extend(g.geoms)
        return MultiLineString(coords)
    return None

# Rail lines
for ln, segs in rail_segs.items():
    try:
        merged = unary_union(segs)
        simplified = merged.simplify(SIMPLIFY_DEG, preserve_topology=True)
        ml = geom_to_multilinestring(simplified)
        if ml is None:
            continue
        features.append({
            "type": "Feature",
            "geometry": mapping(ml),
            "properties": {
                "route": ln,
                "mode": "rail",
                "color": RAIL_COLORS[ln],
            }
        })
    except Exception as e:
        print(f"  WARNING: {ln} geometry error: {e}")

print(f"  Rail features: {len(features)}")

# Bus lines
bus_count = 0
for route_id, segs in bus_segs.items():
    try:
        merged = unary_union(segs)
        simplified = merged.simplify(SIMPLIFY_DEG, preserve_topology=True)
        ml = geom_to_multilinestring(simplified)
        if ml is None:
            continue
        features.append({
            "type": "Feature",
            "geometry": mapping(ml),
            "properties": {
                "route": route_id,
                "mode": "bus",
                "color": BUS_COLOR,
            }
        })
        bus_count += 1
    except Exception as e:
        print(f"  WARNING: route {route_id} geometry error: {e}")

print(f"  Bus features: {bus_count}")
print(f"  Total features: {len(features)}")

out_path = BASE / "route_lines.geojson"
out = {"type": "FeatureCollection", "features": features}
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(out, f, separators=(",", ":"))
sz = os.path.getsize(out_path) / 1024 / 1024
print(f"\nWrote {out_path.name}: {sz:.2f} MB")

# ── 4. Assign rail line membership to stops ───────────────────────────────────
print("\nAssigning rail line membership to stops …")
from scipy.spatial import cKDTree
import numpy as np
from pyproj import Transformer

wgs84_to_bng = Transformer.from_crs("EPSG:4326", "EPSG:27700", always_xy=True)

def to_bng(lon, lat):
    x, y = wgs84_to_bng.transform(lon, lat)
    return float(x), float(y)

# Build spatial indexes for each station type
def load_station_points(geojson_path, route_fn):
    """Returns list of (x_bng, y_bng, [routes]) tuples."""
    with open(geojson_path, encoding="utf-8") as f:
        gj = json.load(f)
    pts = []
    for feat in gj["features"]:
        lon, lat = feat["geometry"]["coordinates"][:2]
        x, y = to_bng(lon, lat)
        routes = route_fn(feat["properties"])
        pts.append((x, y, routes))
    return pts

ug_pts  = load_station_points(DATA / "Underground_Stations.geojson",
    lambda p: [l.strip() for l in (p.get("LINES") or "").split(",") if l.strip()])
dlr_pts  = load_station_points(DATA / "DLR_Stations.geojson",            lambda p: ["DLR"])
eliz_pts = load_station_points(DATA / "Elizabeth_Line_Stations.geojson", lambda p: ["Elizabeth Line"])
og_pts   = load_station_points(DATA / "Overground_Stations.geojson",     lambda p: ["Overground"])
tram_pts = load_station_points(DATA / "Tramlink_Stations.geojson",       lambda p: ["Tramlink"])

all_station_pts = ug_pts + dlr_pts + eliz_pts + og_pts + tram_pts
station_xy  = np.array([[p[0], p[1]] for p in all_station_pts])
station_tree = cKDTree(station_xy)

MATCH_RADIUS_M = 300   # generous — stops may be offset from station centroid

print(f"  Station spatial index: {len(all_station_pts)} points")

# Load and update stops
with open(BASE / "London_Stops_With_Routes.geojson", encoding="utf-8") as f:
    stops_gj = json.load(f)

RAIL_STOP_TYPES = {"MET", "TMU", "PLT", "RLY", "RSE", "FER", "FTD", "GAT"}
updated = 0
for feat in stops_gj["features"]:
    props = feat["properties"]
    if props.get("StopType") not in RAIL_STOP_TYPES:
        continue
    lon, lat = feat["geometry"]["coordinates"][:2]
    x, y = to_bng(lon, lat)
    # Find all stations within radius
    indices = station_tree.query_ball_point([x, y], r=MATCH_RADIUS_M)
    routes = set()
    for idx in indices:
        routes.update(all_station_pts[idx][2])
    if routes:
        props["routes"] = sorted(routes)
        props["route_count"] = len(routes)
        updated += 1

print(f"  Updated {updated} rail stops with line assignments")

# Save updated stops file
with open(BASE / "London_Stops_With_Routes.geojson", "w", encoding="utf-8") as f:
    json.dump(stops_gj, f, separators=(",", ":"))
sz = os.path.getsize(BASE / "London_Stops_With_Routes.geojson") / 1024 / 1024
print(f"  Saved London_Stops_With_Routes.geojson ({sz:.1f} MB)")

print("\nDone.")
