import json
from collections import defaultdict
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
CHUNK_DIR = BASE_DIR / "grid_ai_chunks_osm_network"
OUTPUT = BASE_DIR / "grid_resilience_summary_osm_network.json"


def route_base(route):
    return str(route or "").replace("_Out", "").replace("_Back", "").replace("_In", "").replace("_Both", "")


def vulnerability_class(ltrs):
    if ltrs >= 0.8:
        return "resilient"
    if ltrs >= 0.6:
        return "moderate"
    if ltrs >= 0.3:
        return "high"
    return "critical"


def main():
    route_stats = defaultdict(lambda: {
        "affected_grid": 0,
        "baseline_ai_sum": 0.0,
        "lost_ai_sum": 0.0,
        "critical_grid": 0,
        "high_or_critical_grid": 0,
    })
    total_grid = 0
    baseline_positive = 0

    for path in sorted(CHUNK_DIR.glob("*.json")):
        data = json.load(open(path, encoding="utf-8"))["data"]
        for record in data.values():
            total_grid += 1
            baseline_ai = float(record.get("baseline_ai") or 0)
            if baseline_ai > 0:
                baseline_positive += 1

            by_route = defaultdict(float)
            for item in record.get("contributors", []):
                by_route[route_base(item.get("route"))] += float(item.get("ai_contribution") or 0)

            for route, lost_ai in by_route.items():
                if not route or baseline_ai <= 0:
                    continue
                disrupted_ai = max(0, baseline_ai - lost_ai)
                ltrs = disrupted_ai / baseline_ai if baseline_ai else 1
                cls = vulnerability_class(ltrs)

                stats = route_stats[route]
                stats["affected_grid"] += 1
                stats["baseline_ai_sum"] += baseline_ai
                stats["lost_ai_sum"] += lost_ai
                if cls == "critical":
                    stats["critical_grid"] += 1
                if cls in {"high", "critical"}:
                    stats["high_or_critical_grid"] += 1

    impacts = []
    for route, stats in route_stats.items():
        mean_ltrs = 1
        if stats["baseline_ai_sum"] > 0:
            mean_ltrs = max(0, 1 - stats["lost_ai_sum"] / stats["baseline_ai_sum"])
        impacts.append({
            "route": route,
            "affected_grid": stats["affected_grid"],
            "critical_grid": stats["critical_grid"],
            "high_or_critical_grid": stats["high_or_critical_grid"],
            "lost_ai_sum": round(stats["lost_ai_sum"], 3),
            "mean_ltrs": round(mean_ltrs, 4),
            "mean_ai_loss_ratio": round(1 - mean_ltrs, 4),
        })

    impacts.sort(
        key=lambda row: (
            row["high_or_critical_grid"],
            row["critical_grid"],
            row["lost_ai_sum"],
        ),
        reverse=True,
    )

    output = {
        "version": "1.0",
        "type": "100m_grid_resilience_summary",
        "method": "For each route, remove its AI contribution from each 100m grid cell and compute LTRS = disrupted_AI / baseline_AI.",
        "coverage": {
            "grid_count": total_grid,
            "baseline_positive_grid": baseline_positive,
            "routes_count": len(impacts),
        },
        "single_route_impacts": impacts,
    }

    with OUTPUT.open("w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)

    print(f"Wrote {OUTPUT}")
    print(output["coverage"])
    print("Top 10:")
    for row in impacts[:10]:
        print(row)


if __name__ == "__main__":
    main()
