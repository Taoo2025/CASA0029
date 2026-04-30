"""
100m grid-first OSM accessibility and route contribution precomputation.

This is the LTRA calculation core for grid cells:
  - derive each 100m grid centroid
  - snap centroids and public transport stops to the OSM walking network
  - compute network walking distance to nearby stops
  - build a per-grid route contribution list
  - calculate baseline AI and disruption-ready route contributions

The full London grid has 159,451 cells. Use --limit for testing, then run the
full script when you are ready for a longer batch job.
"""

import argparse
import gzip
import json
import math
import time
from collections import defaultdict
from pathlib import Path

import geopandas as gpd
import networkx as nx
import numpy as np
from scipy.spatial import cKDTree


BASE_DIR = Path(__file__).resolve().parent
GRID_PATH = BASE_DIR / "DATA" / "PTAL_2023_Grid_100mx100m_Data.geojson"
STOPS_PATH = BASE_DIR / "London_Stops_With_Routes.geojson"
ROADS_PATH = BASE_DIR / "DATA" / "greater-london-260427-free.shp" / "gis_osm_roads_free_1.shp"
OUT_DIR = BASE_DIR / "grid_ai_chunks_osm_network"
OUT_MANIFEST = BASE_DIR / "grid_ai_manifest_osm_network.json"
OUT_CENTROIDS = BASE_DIR / "grid_centroids_100m.geojson"


WALKABLE_CLASSES = {
    "footway", "path", "pedestrian", "steps", "cycleway", "bridleway",
    "track", "track_grade1", "track_grade2", "track_grade3", "track_grade4", "track_grade5",
    "living_street", "residential", "service", "unclassified",
    "tertiary", "tertiary_link", "secondary", "secondary_link", "primary", "primary_link",
}

BUS_CATCHMENT_M = 640
RAIL_CATCHMENT_M = 960


def route_base(route):
    return str(route or "").replace("_Out", "").replace("_Back", "").replace("_In", "").replace("_Both", "")


def route_mode(route):
    route_id = route_base(route)
    if route_id.replace("N", "", 1).replace("H", "", 1).replace("X", "", 1).replace("C", "", 1).isdigit():
        return "bus"
    return "rail"


def impedance(distance_m, catchment_m):
    # PTAL-like decay: nearer stops contribute more; stops at catchment edge
    # contribute a small residual rather than dropping sharply before filtering.
    ratio = min(distance_m / catchment_m, 1)
    return max(0, 1 - ratio)


def route_weight(rank):
    return 1.0 if rank == 0 else 0.5


def build_graph():
    print("[1/6] Loading OSM walking network...")
    roads = gpd.read_file(ROADS_PATH)
    roads = roads[roads["fclass"].isin(WALKABLE_CLASSES)].copy().to_crs("EPSG:27700")
    graph = nx.Graph()
    node_lookup = {}
    coords = []

    def key(x, y):
        return (round(float(x), 3), round(float(y), 3))

    def node_for(x, y):
        item = key(x, y)
        node = node_lookup.get(item)
        if node is None:
            node = len(coords)
            node_lookup[item] = node
            coords.append(item)
            graph.add_node(node)
        return node

    for idx, row in enumerate(roads.itertuples(index=False), start=1):
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        lines = [geom] if geom.geom_type == "LineString" else list(getattr(geom, "geoms", []))
        for line in lines:
            points = list(line.coords)
            for a, b in zip(points[:-1], points[1:]):
                u = node_for(a[0], a[1])
                v = node_for(b[0], b[1])
                dist = math.hypot(a[0] - b[0], a[1] - b[1])
                if dist > 0:
                    graph.add_edge(u, v, weight=dist)
        if idx % 100000 == 0:
            print(f"      processed {idx:,} road features")

    print(f"      nodes={graph.number_of_nodes():,}, edges={graph.number_of_edges():,}")
    return graph, np.array(coords, dtype=float), cKDTree(np.array(coords, dtype=float))


def load_stops():
    with STOPS_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)
    rows = []
    for feature in data["features"]:
        props = feature["properties"]
        lon, lat = feature["geometry"]["coordinates"]
        rows.append({
            "code": str(props["ATCOCode"]),
            "name": str(props.get("StopName", "")),
            "lon": float(lon),
            "lat": float(lat),
            "routes": [route_base(route) for route in props.get("routes", []) if route_base(route)],
        })
    return rows


def load_grid(limit=0):
    print("[2/6] Loading 100m grid and deriving centroids...")
    grid = gpd.read_file(GRID_PATH)
    if limit:
        grid = grid.head(limit).copy()
    grid_27700 = grid.to_crs("EPSG:27700")
    centroids_27700 = grid_27700.geometry.centroid
    centroids_4326 = gpd.GeoSeries(centroids_27700, crs="EPSG:27700").to_crs("EPSG:4326")

    rows = []
    for row, point_m, point_ll in zip(grid.itertuples(index=False), centroids_27700, centroids_4326):
        props = row._asdict()
        geom = props.pop("geometry")
        rows.append({
            "fid": int(props.get("FID")),
            "grid_id": int(props.get("GridID")),
            "baseline_ptal": str(props.get("PTAL_2023")),
            "published_ai": float(props.get("AI") or 0),
            "published_bus": float(props.get("BUS") or 0),
            "published_lul": float(props.get("LUL") or 0),
            "published_rail": float(props.get("RAIL") or 0),
            "published_tram": float(props.get("TRAM") or 0),
            "lon": float(point_ll.x),
            "lat": float(point_ll.y),
            "x": float(point_m.x),
            "y": float(point_m.y),
        })

    centroid_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [row["lon"], row["lat"]]},
                "properties": {
                    "FID": row["fid"],
                    "GridID": row["grid_id"],
                    "PTAL_2023": row["baseline_ptal"],
                    "AI": row["published_ai"],
                },
            }
            for row in rows
        ],
    }
    with OUT_CENTROIDS.open("w", encoding="utf-8") as file:
        json.dump(centroid_geojson, file, separators=(",", ":"))

    print(f"      grid cells={len(rows):,}; wrote {OUT_CENTROIDS.name}")
    return rows


def project_stops(stops):
    gdf = gpd.GeoDataFrame(
        stops,
        geometry=gpd.points_from_xy([s["lon"] for s in stops], [s["lat"] for s in stops]),
        crs="EPSG:4326",
    ).to_crs("EPSG:27700")
    rows = []
    for stop, geom in zip(stops, gdf.geometry):
        item = dict(stop)
        item["x"] = float(geom.x)
        item["y"] = float(geom.y)
        rows.append(item)
    return rows


def snap(rows, node_tree, snap_limit_m):
    missed = 0
    for row in rows:
        dist, node = node_tree.query([row["x"], row["y"]], k=1)
        row["network_node"] = int(node) if dist <= snap_limit_m else None
        row["snap_distance_m"] = round(float(dist), 1)
        if row["network_node"] is None:
            missed += 1
    return missed


def contribution_list(stops, distances, speed_m_per_min):
    best_by_route = {}
    for stop in stops:
        distance = distances.get(stop["network_node"])
        if distance is None:
            continue
        for route in stop["routes"]:
            mode = route_mode(route)
            catchment = BUS_CATCHMENT_M if mode == "bus" else RAIL_CATCHMENT_M
            if distance > catchment:
                continue
            current = best_by_route.get(route)
            if current is None or distance < current["distance_m"]:
                best_by_route[route] = {
                    "route": route,
                    "mode": mode,
                    "stop_code": stop["code"],
                    "stop_name": stop["name"],
                    "distance_m": distance,
                    "walking_time_min": distance / speed_m_per_min,
                    "catchment_m": catchment,
                }

    grouped = defaultdict(list)
    for item in best_by_route.values():
        grouped[item["mode"]].append(item)

    contributors = []
    for mode, items in grouped.items():
        items.sort(key=lambda item: item["distance_m"])
        for rank, item in enumerate(items):
            weight = route_weight(rank)
            contribution = weight * impedance(item["distance_m"], item["catchment_m"]) * 10
            contributors.append({
                "route": item["route"],
                "mode": item["mode"],
                "stop_code": item["stop_code"],
                "stop_name": item["stop_name"],
                "distance_m": round(item["distance_m"], 1),
                "walking_time_min": round(item["walking_time_min"], 1),
                "weight": weight,
                "ai_contribution": round(contribution, 3),
            })

    contributors.sort(key=lambda item: item["ai_contribution"], reverse=True)
    return contributors


def write_chunk(batch_id, records):
    OUT_DIR.mkdir(exist_ok=True)
    filename = f"grid_batch_{batch_id:04d}.json"
    payload = {"batch": batch_id, "type": "grid_osm_ai", "data": records}
    path = OUT_DIR / filename
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, separators=(",", ":"))
    with gzip.open(OUT_DIR / f"{filename}.gz", "wt", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, separators=(",", ":"))
    return filename


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=2500)
    parser.add_argument("--speed-kmh", type=float, default=4.8)
    parser.add_argument("--candidate-radius-m", type=float, default=1200)
    parser.add_argument("--max-network-m", type=float, default=1000)
    parser.add_argument("--snap-limit-m", type=float, default=350)
    parser.add_argument("--progress-every", type=int, default=1000)
    args = parser.parse_args()

    graph, _, node_tree = build_graph()
    grid = load_grid(args.limit)

    print("[3/6] Loading and snapping stops/grid centroids...")
    stops = project_stops(load_stops())
    missed_stops = snap(stops, node_tree, args.snap_limit_m)
    missed_grid = snap(grid, node_tree, args.snap_limit_m)
    print(f"      stops snapped: {len(stops)-missed_stops:,}/{len(stops):,}")
    print(f"      grid snapped: {len(grid)-missed_grid:,}/{len(grid):,}")

    stop_xy = np.array([[s["x"], s["y"]] for s in stops], dtype=float)
    stop_tree = cKDTree(stop_xy)
    speed_m_per_min = args.speed_kmh * 1000 / 60

    print("[4/6] Calculating grid route contribution lists...")
    start = time.time()
    batch_id = 0
    batch = {}
    chunks = []
    grid_to_chunk = {}
    ai_values = []

    for idx, cell in enumerate(grid, start=1):
        if idx == 1 or idx % args.progress_every == 0:
            print(f"      {idx:,}/{len(grid):,} cells ({time.time()-start:.1f}s)")

        contributors = []
        if cell["network_node"] is not None:
            candidate_indices = stop_tree.query_ball_point([cell["x"], cell["y"]], r=args.candidate_radius_m, workers=-1)
            if candidate_indices:
                lengths = nx.single_source_dijkstra_path_length(
                    graph, cell["network_node"], cutoff=args.max_network_m, weight="weight"
                )
                candidate_stops = [stops[i] for i in candidate_indices if stops[i]["network_node"] is not None]
                contributors = contribution_list(candidate_stops, lengths, speed_m_per_min)

        baseline_ai = round(sum(item["ai_contribution"] for item in contributors), 3)
        ai_values.append(baseline_ai)
        record = {
            "grid_id": cell["grid_id"],
            "fid": cell["fid"],
            "center_lon": round(cell["lon"], 7),
            "center_lat": round(cell["lat"], 7),
            "published_ptal": cell["baseline_ptal"],
            "published_ai": round(cell["published_ai"], 3),
            "baseline_ai": baseline_ai,
            "contributors": contributors,
            "top_routes": contributors[:8],
            "snap_distance_m": cell["snap_distance_m"],
            "method": "100m_grid_osm_network_ai_approx",
        }
        batch[str(cell["grid_id"])] = record

        if len(batch) >= args.batch_size:
            batch_id += 1
            filename = write_chunk(batch_id, batch)
            chunks.append({"filename": filename, "grid_count": len(batch)})
            for grid_id in batch:
                grid_to_chunk[grid_id] = filename.replace(".json", "")
            batch = {}

    if batch:
        batch_id += 1
        filename = write_chunk(batch_id, batch)
        chunks.append({"filename": filename, "grid_count": len(batch)})
        for grid_id in batch:
            grid_to_chunk[grid_id] = filename.replace(".json", "")

    print("[5/6] Writing manifest...")
    manifest = {
        "version": "1.0",
        "type": "100m_grid_osm_network_ai",
        "grid_count": len(grid),
        "chunks": chunks,
        "grid_to_chunk": grid_to_chunk,
        "walking_speed_kmh": args.speed_kmh,
        "bus_catchment_m": BUS_CATCHMENT_M,
        "rail_catchment_m": RAIL_CATCHMENT_M,
        "method": "OSM network Dijkstra; PTAL-style route contribution approximation",
        "statistics": {
            "mean_baseline_ai": round(float(np.mean(ai_values)), 3) if ai_values else None,
            "median_baseline_ai": round(float(np.median(ai_values)), 3) if ai_values else None,
        },
    }
    with OUT_MANIFEST.open("w", encoding="utf-8") as file:
        json.dump(manifest, file, ensure_ascii=False, indent=2)

    print("[6/6] Done")
    print(f"      wrote {OUT_MANIFEST.name}")
    print(f"      wrote {len(chunks)} chunks in {OUT_DIR.name}")


if __name__ == "__main__":
    main()
