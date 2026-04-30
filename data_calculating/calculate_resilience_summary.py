import argparse
import json
from collections import defaultdict
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CHUNKS_DIR = BASE_DIR / "data_chunks"
DEFAULT_OUTPUT = BASE_DIR / "resilience_summary.json"


def normalise_route(route):
    value = str(route or "").strip()
    for suffix in ("_Out", "_Back", "_In", "_Both"):
        if value.endswith(suffix):
            return value[: -len(suffix)]
    return value


def classify(minutes):
    if minutes is None:
        return "none"
    if minutes <= 8:
        return "high"
    if minutes <= 12:
        return "medium"
    return "low"


def nearest_time(stops, cancelled_routes=None):
    cancelled_routes = cancelled_routes or set()
    for stop in stops:
        routes = {normalise_route(route) for route in stop.get("routes", [])}
        if not routes:
            continue
        if routes - cancelled_routes:
            return stop.get("walking_time_min")
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunks-dir", default=str(DEFAULT_CHUNKS_DIR))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--method", default="precomputed walking times")
    args = parser.parse_args()

    chunks_dir = Path(args.chunks_dir)
    output_path = Path(args.output)

    lsoa_records = []
    route_to_lsoa = defaultdict(set)

    for chunk_path in sorted(chunks_dir.glob("*.json")):
        with chunk_path.open("r", encoding="utf-8") as file:
            chunk = json.load(file)

        for lsoa_code, record in chunk.get("data", {}).items():
            stops = record.get("nearby_stops", [])
            baseline_time = nearest_time(stops)
            baseline_class = classify(baseline_time)
            routes_seen = set()

            for stop in stops:
                for route in stop.get("routes", []):
                    route_id = normalise_route(route)
                    if route_id:
                        routes_seen.add(route_id)
                        route_to_lsoa[route_id].add(lsoa_code)

            lsoa_records.append(
                {
                    "code": lsoa_code,
                    "name": record.get("lsoa_name", lsoa_code),
                    "borough": record.get("lad_name", ""),
                    "stops": stops,
                    "baseline_time": baseline_time,
                    "baseline_class": baseline_class,
                    "routes": routes_seen,
                }
            )

    baseline_accessible = sum(
        1 for record in lsoa_records if record["baseline_class"] in {"high", "medium"}
    )
    route_results = []

    for route_id, affected_lsoa in sorted(route_to_lsoa.items()):
        cancelled = {route_id}
        lost_access = 0
        worsened_class = 0
        total_delay = 0.0
        delayed_count = 0
        affected_accessible = 0

        for record in lsoa_records:
            if route_id not in record["routes"]:
                continue

            before_time = record["baseline_time"]
            before_class = record["baseline_class"]
            after_time = nearest_time(record["stops"], cancelled)
            after_class = classify(after_time)

            if before_class in {"high", "medium"}:
                affected_accessible += 1
                if after_class not in {"high", "medium"}:
                    lost_access += 1

            class_rank = {"high": 0, "medium": 1, "low": 2, "none": 3}
            if class_rank[after_class] > class_rank[before_class]:
                worsened_class += 1

            if before_time is not None and after_time is not None and after_time > before_time:
                total_delay += after_time - before_time
                delayed_count += 1
            elif before_time is not None and after_time is None:
                total_delay += 12 - min(before_time, 12)
                delayed_count += 1

        retention = 1.0
        if affected_accessible:
            retention = (affected_accessible - lost_access) / affected_accessible

        route_results.append(
            {
                "route": route_id,
                "affected_lsoa": len(affected_lsoa),
                "affected_accessible_lsoa": affected_accessible,
                "lost_12min_access_lsoa": lost_access,
                "worsened_class_lsoa": worsened_class,
                "mean_delay_min": round(total_delay / delayed_count, 2)
                if delayed_count
                else 0,
                "retention_ratio": round(retention, 4),
            }
        )

    route_results.sort(
        key=lambda row: (
            row["lost_12min_access_lsoa"],
            row["worsened_class_lsoa"],
            row["affected_lsoa"],
        ),
        reverse=True,
    )

    output = {
        "method": {
            "source": args.method,
            "walking_speed_kmh": 4.8,
            "thresholds_min": {"high": 8, "medium": 12},
            "route_cancellation_rule": "A stop remains available when at least one non-cancelled route still serves it.",
            "distance_note": "Uses precomputed stop walking times in data_chunks. These are based on the current project data.",
        },
        "coverage": {
            "lsoa_count": len(lsoa_records),
            "routes_count": len(route_results),
            "baseline_12min_accessible_lsoa": baseline_accessible,
        },
        "single_route_impacts": route_results,
    }

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)

    print(f"Wrote {output_path}")
    print(f"LSOA records: {len(lsoa_records)}")
    print(f"Routes: {len(route_results)}")
    print("Top 10 impacts:")
    for row in route_results[:10]:
        print(
            f"  {row['route']}: lost={row['lost_12min_access_lsoa']}, "
            f"worsened={row['worsened_class_lsoa']}, retention={row['retention_ratio']}"
        )


if __name__ == "__main__":
    main()
