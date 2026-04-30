"""
Precompute walking accessibility using the local OSM road/path network.

Outputs are compatible with the web app's existing chunked data structure:
  - data_manifest_osm_network.json
  - data_chunks_osm_network/*.json
  - walking_index_osm_network.json

The existing straight-line data is left untouched unless you explicitly copy
these outputs over the current data_manifest.json and data_chunks directory.
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
ROADS_PATH = BASE_DIR / "DATA" / "greater-london-260427-free.shp" / "gis_osm_roads_free_1.shp"
STOPS_PATH = BASE_DIR / "London_Stops_With_Routes.geojson"
LSOA_PATH = BASE_DIR / "London_LSOA_Centroids.geojson"
OUT_CHUNKS = BASE_DIR / "data_chunks_osm_network"
OUT_MANIFEST = BASE_DIR / "data_manifest_osm_network.json"
OUT_INDEX = BASE_DIR / "walking_index_osm_network.json"

WALKABLE_CLASSES = {
    "footway",
    "path",
    "pedestrian",
    "steps",
    "cycleway",
    "bridleway",
    "track",
    "track_grade1",
    "track_grade2",
    "track_grade3",
    "track_grade4",
    "track_grade5",
    "living_street",
    "residential",
    "service",
    "unclassified",
    "tertiary",
    "tertiary_link",
    "secondary",
    "secondary_link",
    "primary",
    "primary_link",
}


def normalise_borough(name):
    return (
        str(name)
        .lower()
        .replace("&", "and")
        .replace(" ", "_")
        .replace("-", "_")
        .replace("'", "")
    )


def load_points(path, kind):
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    rows = []
    for feature in data["features"]:
        props = feature["properties"]
        lon, lat = feature["geometry"]["coordinates"]
        if kind == "stop":
            rows.append(
                {
                    "code": str(props["ATCOCode"]),
                    "name": str(props.get("StopName", "")),
                    "lon": float(lon),
                    "lat": float(lat),
                    "routes": props.get("routes", []),
                    "route_count": int(props.get("route_count", len(props.get("routes", [])))),
                }
            )
        else:
            rows.append(
                {
                    "code": str(props["LSOA_CODE"]),
                    "name": str(props["LSOA_NAME"]),
                    "lad": str(props["LAD_NAME"]),
                    "lon": float(lon),
                    "lat": float(lat),
                }
            )
    return rows


def project_points(rows):
    gdf = gpd.GeoDataFrame(
        rows,
        geometry=gpd.points_from_xy([r["lon"] for r in rows], [r["lat"] for r in rows]),
        crs="EPSG:4326",
    ).to_crs("EPSG:27700")
    projected = []
    for row, geom in zip(rows, gdf.geometry):
        item = dict(row)
        item["x"] = float(geom.x)
        item["y"] = float(geom.y)
        projected.append(item)
    return projected


def coord_key(x, y):
    return (round(float(x), 3), round(float(y), 3))


def add_node(graph, node_lookup, coords, x, y):
    key = coord_key(x, y)
    node = node_lookup.get(key)
    if node is None:
        node = len(coords)
        node_lookup[key] = node
        coords.append(key)
        graph.add_node(node)
    return node


def build_graph():
    print("[1/5] Loading OSM roads...")
    roads = gpd.read_file(ROADS_PATH)
    roads = roads[roads["fclass"].isin(WALKABLE_CLASSES)].copy()
    roads = roads.to_crs("EPSG:27700")
    print(f"      walkable road/path features: {len(roads):,}")

    print("[2/5] Building NetworkX graph...")
    graph = nx.Graph()
    node_lookup = {}
    coords = []

    for idx, row in enumerate(roads.itertuples(index=False), start=1):
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue

        geometries = [geom] if geom.geom_type == "LineString" else list(getattr(geom, "geoms", []))
        for line in geometries:
            line_coords = list(line.coords)
            for a, b in zip(line_coords[:-1], line_coords[1:]):
                u = add_node(graph, node_lookup, coords, a[0], a[1])
                v = add_node(graph, node_lookup, coords, b[0], b[1])
                distance = math.hypot(a[0] - b[0], a[1] - b[1])
                if distance > 0:
                    graph.add_edge(u, v, weight=distance)

        if idx % 100000 == 0:
            print(f"      processed {idx:,} road/path features")

    print(f"      graph nodes: {graph.number_of_nodes():,}")
    print(f"      graph edges: {graph.number_of_edges():,}")
    return graph, coords


def build_node_index(coords):
    node_array = np.array(coords, dtype=float)
    node_tree = cKDTree(node_array)
    return node_array, node_tree


def attach_nearest_node(rows, node_tree, snap_limit_m):
    snapped = []
    missed = 0
    for row in rows:
        distance, node = node_tree.query([row["x"], row["y"]], k=1)
        item = dict(row)
        item["network_node"] = int(node) if distance <= snap_limit_m else None
        item["snap_distance_m"] = round(float(distance), 1)
        if item["network_node"] is None:
            missed += 1
        snapped.append(item)
    return snapped, missed


def write_outputs(walking_data, stops_count, speed_kmh, max_network_m):
    print("[5/5] Writing chunked outputs...")
    OUT_CHUNKS.mkdir(exist_ok=True)

    by_borough = defaultdict(dict)
    for code, record in walking_data.items():
        by_borough[record["lad_name"]][code] = record

    chunks = []
    lsoa_to_chunk = {}
    total_connections = 0
    nearest_times = []

    for borough, records in sorted(by_borough.items()):
        filename_base = normalise_borough(borough)
        filename = f"{filename_base}.json"
        path = OUT_CHUNKS / filename
        payload = {
            "borough": borough,
            "lsoa_count": len(records),
            "method": "osm_network_dijkstra",
            "data": records,
        }

        with path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, separators=(",", ":"))

        gz_path = OUT_CHUNKS / f"{filename}.gz"
        with gzip.open(gz_path, "wt", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, separators=(",", ":"))

        size_kb = path.stat().st_size / 1024
        size_gz_kb = gz_path.stat().st_size / 1024
        chunks.append(
            {
                "borough": borough,
                "filename": filename,
                "size_kb": round(size_kb, 2),
                "size_gz_kb": round(size_gz_kb, 2),
                "lsoa_count": len(records),
                "compression_ratio": round(size_gz_kb / size_kb, 3) if size_kb else 0,
            }
        )

        for code, record in records.items():
            lsoa_to_chunk[code] = filename_base
            total_connections += len(record["nearby_stops"])
            if record["nearby_stops"]:
                nearest_times.append(record["nearby_stops"][0]["walking_time_min"])

    manifest = {
        "version": "3.0",
        "type": "walking_accessibility_osm_network",
        "method": "OSM road/path network + Dijkstra shortest path",
        "total_lsoa": len(walking_data),
        "total_stops": stops_count,
        "average_stops_per_lsoa": round(total_connections / len(walking_data), 1) if walking_data else 0,
        "walking_speed": speed_kmh,
        "walking_speed_m_per_min": round(speed_kmh * 1000 / 60, 2),
        "max_network_distance_m": max_network_m,
        "chunks": chunks,
        "lsoa_to_chunk": lsoa_to_chunk,
        "statistics": {
            "total_connections": total_connections,
            "mean_nearest_walking_time_min": round(float(np.mean(nearest_times)), 2) if nearest_times else None,
            "median_nearest_walking_time_min": round(float(np.median(nearest_times)), 2) if nearest_times else None,
        },
    }

    with OUT_MANIFEST.open("w", encoding="utf-8") as file:
        json.dump(manifest, file, ensure_ascii=False, indent=2)

    index = {
        "version": "3.0",
        "method": manifest["method"],
        "lsoa_index": {
            code: {
                "name": record["lsoa_name"],
                "lad": record["lad_name"],
                "stops_nearby": record["total_stops_in_range"],
                "closest_stop": record["nearby_stops"][0]["stop_name"] if record["nearby_stops"] else None,
                "closest_distance_m": record["nearby_stops"][0]["distance_m"] if record["nearby_stops"] else None,
                "closest_time_min": record["nearby_stops"][0]["walking_time_min"] if record["nearby_stops"] else None,
            }
            for code, record in walking_data.items()
        },
    }
    with OUT_INDEX.open("w", encoding="utf-8") as file:
        json.dump(index, file, ensure_ascii=False, indent=2)

    print(f"      wrote {OUT_MANIFEST.name}")
    print(f"      wrote {len(chunks)} borough chunks in {OUT_CHUNKS.name}")


def compute(args):
    graph, node_coords = build_graph()
    _, node_tree = build_node_index(node_coords)

    print("[3/5] Loading and snapping stops / LSOA centroids...")
    stops = project_points(load_points(STOPS_PATH, "stop"))
    lsoas = project_points(load_points(LSOA_PATH, "lsoa"))
    if args.limit:
        lsoas = lsoas[: args.limit]

    stops, missed_stops = attach_nearest_node(stops, node_tree, args.snap_limit_m)
    lsoas, missed_lsoas = attach_nearest_node(lsoas, node_tree, args.snap_limit_m)
    print(f"      stops snapped: {len(stops) - missed_stops:,}/{len(stops):,}")
    print(f"      LSOA snapped: {len(lsoas) - missed_lsoas:,}/{len(lsoas):,}")

    stop_xy = np.array([[s["x"], s["y"]] for s in stops], dtype=float)
    stop_tree = cKDTree(stop_xy)
    speed_m_per_min = args.speed_kmh * 1000 / 60

    print("[4/5] Running cutoff Dijkstra from each LSOA...")
    walking_data = {}
    start = time.time()

    for idx, lsoa in enumerate(lsoas, start=1):
        if idx == 1 or idx % args.progress_every == 0:
            elapsed = time.time() - start
            print(f"      {idx:,}/{len(lsoas):,} LSOA ({elapsed:.1f}s)")

        nearby_stop_indices = stop_tree.query_ball_point(
            [lsoa["x"], lsoa["y"]],
            r=args.candidate_radius_m,
            workers=-1,
        )

        nearby_stops = []
        if lsoa["network_node"] is not None and nearby_stop_indices:
            lengths = nx.single_source_dijkstra_path_length(
                graph,
                lsoa["network_node"],
                cutoff=args.max_network_m,
                weight="weight",
            )

            for stop_idx in nearby_stop_indices:
                stop = stops[stop_idx]
                stop_node = stop["network_node"]
                if stop_node is None or stop_node not in lengths:
                    continue

                distance_m = float(lengths[stop_node])
                nearby_stops.append(
                    {
                        "stop_code": stop["code"],
                        "stop_name": stop["name"],
                        "distance_m": round(distance_m, 1),
                        "walking_time_min": round(distance_m / speed_m_per_min, 1),
                        "routes": stop["routes"],
                        "route_count": stop["route_count"],
                        "snap_distance_m": stop["snap_distance_m"],
                    }
                )

        nearby_stops.sort(key=lambda row: row["distance_m"])
        walking_data[lsoa["code"]] = {
            "lsoa_name": lsoa["name"],
            "lsoa_code": lsoa["code"],
            "lad_name": lsoa["lad"],
            "center_lon": round(lsoa["lon"], 6),
            "center_lat": round(lsoa["lat"], 6),
            "nearby_stops": nearby_stops[: args.keep_nearest],
            "total_stops_in_range": len(nearby_stops),
            "speed_kmh": args.speed_kmh,
            "method": "osm_network_dijkstra",
            "lsoa_snap_distance_m": lsoa["snap_distance_m"],
        }

    write_outputs(walking_data, len(stops), args.speed_kmh, args.max_network_m)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Only process the first N LSOAs for testing.")
    parser.add_argument("--speed-kmh", type=float, default=4.8)
    parser.add_argument("--candidate-radius-m", type=float, default=2500)
    parser.add_argument("--max-network-m", type=float, default=2400)
    parser.add_argument("--snap-limit-m", type=float, default=350)
    parser.add_argument("--keep-nearest", type=int, default=150)
    parser.add_argument("--progress-every", type=int, default=100)
    return parser.parse_args()


if __name__ == "__main__":
    compute(parse_args())
