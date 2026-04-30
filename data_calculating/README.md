# data_calculating — Reproducibility Bundle

> Folder name uses `data_calculating` (corrected from the brief's "data caculating") — keeps the path clean and Git/URL friendly. Contents below.

This folder contains the **Python computation pipeline** and the **lightweight raw inputs** used to produce every JSON / GeoJSON / PMTiles artifact consumed by `London_PTAL_Accessibility_Map.html`.

Heavy raw datasets (>50 MB) are **not** vendored here — they come from public open-data portals; download links are given in *External Raw Data* below.

---

## 1. Pipeline scripts (Python)

| Script | Role |
|---|---|
| `process_transport_data.py` | Cleans/merges TfL stops & route metadata into unified GeoJSON |
| `extract_bus_routes.py` / `enhance_lsoa_and_extract_routes.py` | Extracts bus route lists per stop, attaches LSOA codes |
| `build_route_lines.py` | Generates `route_lines.geojson` (one polyline per route) |
| `build_osm_network.py` | Builds OSM walking graph (uses Geofabrik shapefile, see below) |
| `precompute_walking_times.py` / `precompute_osm_network_walking_times.py` | Stop→grid walking-time matrices (640 m bus / 960 m rail catchments) |
| `process_walking_accessibility.py` | Combines PTAL + walking-time index → grid-level accessibility |
| `precompute_grid_osm_ai.py` | Per-grid AI-summary inputs (chunked output) |
| `build_route_grid_impacts.py` / `build_rail_route_impacts.py` | "Disrupt one route → which grids lose service?" matrix |
| `calculate_resilience_summary.py` / `calculate_grid_resilience_summary.py` | Aggregates impacts into LSOA / grid resilience scores |
| `prepare_lsoa_tileset_source.py` / `generate_lsoa_pmtiles.py` / `build_lsoa_mbtiles_python.py` | Builds the LSOA PTAL vector tileset (`lsoa_ptal.pmtiles`) |
| `optimize_data_storage.py` / `verify_data_storage.py` | Splits big JSONs into borough chunks, validates manifests |
| `analyze_data_structure.py` / `check_data.py` / `check_routes.py` | Diagnostic / sanity-check helpers |
| `recover_geojson.py` | Recovers truncated GeoJSON dumps |
| `serve_range.py` / `run_server.py` | Local dev server with HTTP Range support (needed for PMTiles) |

## 2. Vendored lightweight raw data (`DATA/`)

| File | Size | Source |
|---|---|---|
| `london_boroughs.geojson` | 1.3 MB | ONS / London Datastore |
| `Bus_Stops.geojson`, `Bus_Stands.geojson` | 10.6 MB | TfL Open Data |
| `Underground_Stations.geojson`, `Overground_Stations.geojson`, `DLR_Stations.geojson`, `Elizabeth_Line_Stations.geojson`, `Tramlink_Stations.geojson` | < 0.2 MB each | TfL Open Data |
| `London_Stops_Filtered.csv` | 5.9 MB | Derived from TfL NaPTAN |
| `LSOA_London.{cpg,prj,qmd,shx}` | tiny | ONS LSOA 2021 (sidecar files only) |

## 3. Vendored small configs / aggregates (folder root)

| File | Purpose |
|---|---|
| `accessibility_config.json` | PTAL bands, walking budgets (640 m bus / 960 m rail), thresholds |
| `network_config.json` | OSM network build parameters |
| `borough_summary.json` | Pre-computed borough-level resilience aggregate |
| `real_london_transport_lines.json` | Curated rail / tram line catalog |

---

## 4. External raw data (not vendored — download separately)

These exceed GitHub's per-file (100 MB) or sensible repo-size limits. Place them under `DATA/` or `Final_project/DATA/` before re-running the pipeline.

| File | Approx. size | Where to get it |
|---|---|---|
| `LSOA_aggregated_PTAL_stats_2023.geojson` | 104 MB | TfL Open Data → *PTAL 2023 (LSOA aggregated)* |
| `MSOA_aggregated_PTAL_stats_2023.geojson` | 49 MB | TfL Open Data → *PTAL 2023 (MSOA aggregated)* |
| `PTAL_2023_Grid_100mx100m_Data.geojson` | 80 MB | TfL Open Data → *PTAL 2023 100m Grid* |
| `Bus_Routes__direction_of_travel_.geojson` | 60 MB | TfL Open Data → *Bus Routes (direction of travel)* |
| `Stops.csv` | 96 MB | TfL Open Data → *NaPTAN stops* |
| `LSOA_London.shp` (+ `.dbf`, `.shp.xml`) | ~50 MB | ONS LSOA 2021 boundaries (England & Wales) |
| `greater-london-260427-free.shp/` | ~700 MB | Geofabrik OSM extract → *Greater London* |
| `LB_LSOA2021_shp.zip` | 19 MB | London Datastore |

## 5. Generated outputs (not vendored here — already in `HTML/` next to the map page)

The map page at runtime fetches these files from the web-root, *not* from this folder:

`data_manifest_osm_network.json`, `bus_routes_detailed.json`, `resilience_summary_osm_network.json`, `London_LSOA_Centroids.geojson`, `grid_ai_manifest_osm_network.json`, `grid_resilience_summary_osm_network.json`, `route_grid_impacts_osm_network.json`, `route_lines.geojson`, `London_Stops_With_Routes.geojson`, `lsoa_ptal.pmtiles`, plus the `grid_ai_chunks_osm_network/` and `data_chunks_osm_network/` folders.

To regenerate them: install requirements (`geopandas`, `shapely`, `networkx`, `osmnx`, `tippecanoe`/`pmtiles`), drop the external raw data into the expected paths, and run the scripts in roughly this order:

```
process_transport_data.py
build_osm_network.py
precompute_osm_network_walking_times.py
extract_bus_routes.py  →  enhance_lsoa_and_extract_routes.py
process_walking_accessibility.py
build_route_lines.py
build_route_grid_impacts.py
calculate_grid_resilience_summary.py  →  calculate_resilience_summary.py
precompute_grid_osm_ai.py
prepare_lsoa_tileset_source.py  →  generate_lsoa_pmtiles.py
optimize_data_storage.py  →  verify_data_storage.py
```

## 6. License / attribution

- TfL data © Transport for London, *Powered by TfL Open Data*.
- ONS boundary data © Crown copyright and database right.
- OSM extract © OpenStreetMap contributors, ODbL.
