"""
Compute per-rail-line -> per-grid AI loss and merge into route_grid_impacts_osm_network.json.

Rail lines modelled:
  Underground: Bakerloo, Central, Circle, District, Hammersmith & City,
               Jubilee, Metropolitan, Northern, Piccadilly, Victoria, Waterloo & City
  DLR, Elizabeth Line, Overground, Tramlink

Method:
  - Load grid centroids (already computed by precompute_grid_osm_ai.py)
  - Load raw station GeoJSONs from DATA/
  - Project to EPSG:27700 (BNG metres) for distance calculations
  - For each grid centroid, find rail stations within 960m (RAIL_CATCHMENT_M)
  - Apply the same PTAL formula as the bus precompute script:
      impedance = max(0, 1 - dist / catchment)
      weight = 1.0 for rank-0 route of that mode, 0.5 for others
      ai_contribution = weight * impedance * 10
  - Save the merged file back to route_grid_impacts_osm_network.json
"""

import json
import math
import os
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree
from pyproj import Transformer

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "DATA"
IMPACTS_FILE = BASE_DIR / "route_grid_impacts_osm_network.json"
CENTROIDS_FILE = BASE_DIR / "grid_centroids_100m.geojson"

RAIL_CATCHMENT_M = 960

# ── 1. Transform helper ────────────────────────────────────────────────────────
wgs84_to_bng = Transformer.from_crs("EPSG:4326", "EPSG:27700", always_xy=True)

def to_bng(lon, lat):
    x, y = wgs84_to_bng.transform(lon, lat)
    return float(x), float(y)

# ── 2. Load grid centroids ─────────────────────────────────────────────────────
print("Loading grid centroids …")
with open(CENTROIDS_FILE, encoding="utf-8") as f:
    centroids_gj = json.load(f)

grid_rows = []
for feat in centroids_gj["features"]:
    lon, lat = feat["geometry"]["coordinates"]
    x, y = to_bng(lon, lat)
    grid_rows.append({
        "grid_id": str(feat["properties"]["GridID"]),
        "x": x, "y": y,
    })

grid_xy = np.array([[r["x"], r["y"]] for r in grid_rows], dtype=float)
grid_tree = cKDTree(grid_xy)
print(f"  {len(grid_rows):,} grid cells loaded")

# ── 3. Load rail stations ──────────────────────────────────────────────────────
print("Loading rail station GeoJSONs …")

# Build list of (route_id, x, y, station_name) for all rail stations
rail_stations = []

def load_stations_geojson(path, mode_fn):
    """Load a stations GeoJSON. mode_fn(properties) returns list of route ids."""
    with open(path, encoding="utf-8") as f:
        gj = json.load(f)
    for feat in gj["features"]:
        props = feat["properties"]
        coords = feat["geometry"]["coordinates"]
        lon, lat = float(coords[0]), float(coords[1])
        x, y = to_bng(lon, lat)
        routes = mode_fn(props)
        name = props.get("NAME") or props.get("FULL_NAME") or "Unknown"
        for route in routes:
            rail_stations.append({"route": route, "name": name, "x": x, "y": y})

# Underground: LINES property e.g. "Bakerloo" or "District, Hammersmith & City"
def ug_routes(props):
    lines_str = props.get("LINES") or ""
    if not lines_str:
        return []
    return [l.strip() for l in lines_str.split(",") if l.strip()]

load_stations_geojson(DATA_DIR / "Underground_Stations.geojson", ug_routes)
print(f"  Underground: {sum(1 for s in rail_stations):} route-station entries from {len([f for f in json.load(open(DATA_DIR / 'Underground_Stations.geojson', encoding='utf-8'))['features']])} stations")

ug_count = len(rail_stations)

# DLR
def dlr_routes(props):
    return ["DLR"]
load_stations_geojson(DATA_DIR / "DLR_Stations.geojson", dlr_routes)
print(f"  DLR: {len(rail_stations) - ug_count} route-station entries")
dlr_count = len(rail_stations)

# Elizabeth Line
def eliz_routes(props):
    return ["Elizabeth Line"]
load_stations_geojson(DATA_DIR / "Elizabeth_Line_Stations.geojson", eliz_routes)
print(f"  Elizabeth Line: {len(rail_stations) - dlr_count} route-station entries")
eliz_count = len(rail_stations)

# Overground
def og_routes(props):
    return ["Overground"]
load_stations_geojson(DATA_DIR / "Overground_Stations.geojson", og_routes)
print(f"  Overground: {len(rail_stations) - eliz_count} route-station entries")
og_count = len(rail_stations)

# Tramlink
def tram_routes(props):
    return ["Tramlink"]
load_stations_geojson(DATA_DIR / "Tramlink_Stations.geojson", tram_routes)
print(f"  Tramlink: {len(rail_stations) - og_count} route-station entries")

print(f"  Total rail route-station entries: {len(rail_stations)}")

station_xy = np.array([[s["x"], s["y"]] for s in rail_stations], dtype=float)
station_tree = cKDTree(station_xy)

# ── 4. Compute grid impacts ────────────────────────────────────────────────────
print("Computing rail route grid impacts …")

rail_route_grid_loss = defaultdict(dict)

candidate_radius = RAIL_CATCHMENT_M  # exact: only consider stations within catchment

for i, cell in enumerate(grid_rows):
    if i % 20000 == 0:
        print(f"  {i:,}/{len(grid_rows):,} cells processed …")

    # find all rail stations within catchment radius
    indices = station_tree.query_ball_point([cell["x"], cell["y"]], r=candidate_radius)
    if not indices:
        continue

    # For each candidate station, compute distance and assemble per-route best
    best_by_route = {}
    for idx in indices:
        st = rail_stations[idx]
        dx = st["x"] - cell["x"]
        dy = st["y"] - cell["y"]
        dist = math.sqrt(dx*dx + dy*dy)
        route = st["route"]
        if route not in best_by_route or dist < best_by_route[route]["dist"]:
            best_by_route[route] = {"dist": dist, "name": st["name"]}

    if not best_by_route:
        continue

    # Sort routes by distance (closest first) – all are 'rail' mode
    items = sorted(best_by_route.items(), key=lambda kv: kv[1]["dist"])

    # Apply PTAL formula
    for rank, (route, info) in enumerate(items):
        dist = info["dist"]
        impedance = max(0.0, 1.0 - dist / RAIL_CATCHMENT_M)
        if impedance <= 0:
            continue
        weight = 1.0 if rank == 0 else 0.5
        contribution = round(weight * impedance * 10, 3)
        if contribution > 0.01:
            rail_route_grid_loss[route][cell["grid_id"]] = contribution

# Print summary
all_routes = sorted(rail_route_grid_loss.keys())
print(f"\nRail routes computed: {len(all_routes)}")
for r in all_routes:
    print(f"  {r}: {len(rail_route_grid_loss[r]):,} grids affected")

# ── 5. Merge into existing impacts file ───────────────────────────────────────
print(f"\nLoading existing {IMPACTS_FILE.name} …")
with open(IMPACTS_FILE, encoding="utf-8") as f:
    impacts = json.load(f)

existing_routes = set(impacts["route_grid_loss"].keys())
print(f"  Existing routes: {len(existing_routes)}")

# Check for conflicts (rail route IDs shouldn't clash with bus route IDs)
conflicts = existing_routes & set(rail_route_grid_loss.keys())
if conflicts:
    print(f"  WARNING: {len(conflicts)} conflicting route IDs: {conflicts}")
    print("  Merging by taking max contribution per grid cell for conflicts")
    for route in conflicts:
        for grid_id, loss in rail_route_grid_loss[route].items():
            existing = impacts["route_grid_loss"][route].get(grid_id, 0)
            impacts["route_grid_loss"][route][grid_id] = max(existing, loss)
    # Remove from new routes (already merged)
    for r in conflicts:
        del rail_route_grid_loss[r]

# Add new rail routes
for route, grid_losses in rail_route_grid_loss.items():
    impacts["route_grid_loss"][route] = grid_losses

new_total = len(impacts["route_grid_loss"])
print(f"  Updated routes: {new_total} (added {new_total - len(existing_routes)} rail routes)")

total_entries = sum(len(v) for v in impacts["route_grid_loss"].values())
print(f"  Total (route, grid) entries: {total_entries:,}")

# Update metadata
impacts["rail_routes_added"] = all_routes
impacts["version"] = 2

# Write back
print(f"\nWriting {IMPACTS_FILE.name} …")
with open(IMPACTS_FILE, "w", encoding="utf-8") as f:
    json.dump(impacts, f, separators=(",", ":"))

size_mb = os.path.getsize(IMPACTS_FILE) / 1024 / 1024
print(f"Done. {IMPACTS_FILE.name}: {size_mb:.2f} MB")
print(f"Routes in file: {len(impacts['route_grid_loss'])}")
