"""Build a compact per-route -> per-grid AI loss lookup from the chunk files.

Output: route_grid_impacts_osm_network.json
Schema: {
  "version": 1,
  "baseline_ai": {grid_id_str: baseline_ai_float, ...},
  "route_grid_loss": {route_id: {grid_id_str: ai_loss_float, ...}, ...}
}

ai_loss for a route in a grid = sum of ai_contribution of all that route's
contributor rows for that grid. This file lets the web client compute disrupted
AI for every grid quickly: disrupted = baseline - sum_over_cancelled_routes(loss).
"""
import json
import os
from collections import defaultdict

CHUNK_DIR = "grid_ai_chunks_osm_network"
OUT = "route_grid_impacts_osm_network.json"

route_grid_loss = defaultdict(dict)
baseline_ai = {}

files = sorted(f for f in os.listdir(CHUNK_DIR) if f.endswith(".json"))
print(f"Processing {len(files)} chunks")
for i, fname in enumerate(files):
    with open(os.path.join(CHUNK_DIR, fname), encoding="utf-8") as f:
        chunk = json.load(f)
    data = chunk.get("data", chunk)
    for grid_id, rec in data.items():
        b = float(rec.get("baseline_ai") or 0)
        if b > 0:
            baseline_ai[grid_id] = round(b, 3)
        per_route = defaultdict(float)
        for c in rec.get("contributors", []) or []:
            route = c.get("route")
            if not route:
                continue
            # base route id (strip direction suffix if any) — match HTML routeBase
            route = str(route).split("_")[0]
            per_route[route] += float(c.get("ai_contribution") or 0)
        for route, loss in per_route.items():
            if loss > 0.01:
                route_grid_loss[route][grid_id] = round(loss, 3)
    if (i + 1) % 16 == 0:
        print(f"  {i+1}/{len(files)} processed")

print(f"Routes: {len(route_grid_loss)}; grids with baseline: {len(baseline_ai)}")
total_entries = sum(len(v) for v in route_grid_loss.values())
print(f"Total (route, grid) entries: {total_entries}")

out = {
    "version": 1,
    "type": "route_grid_impacts",
    "baseline_ai": baseline_ai,
    "route_grid_loss": route_grid_loss,
}
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(out, f, separators=(",", ":"))
print(f"Wrote {OUT} ({os.path.getsize(OUT)/1024/1024:.2f} MB)")
