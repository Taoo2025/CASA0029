# London PTAL Resilience Map

Interactive web application for exploring public-transport accessibility resilience in London.

**Live site:** https://taoo2025.github.io/CASA0029/

The Mapbox access token is already embedded in the page — **no token setup is required**. Just open the live link, or run locally with the steps below.

## Features

- Cancel one or more bus / rail routes and see the real-time impact on accessibility
- AI-recomputed accessibility index after each disruption
- Side-by-side comparison of baseline vs disrupted scenarios
- 100 m grid analysis with route-specific impacts
- LSOA context layer (PTAL bands)
- Route-by-route impact visualisation
- White → red disruption heat-map (white = minimal, red = critical)

## Run locally

```powershell
git clone https://github.com/Taoo2025/CASA0029.git
cd CASA0029
python -m http.server 8080
```

Then open http://localhost:8080/ — the root `index.html` redirects straight to the interactive map.

For the full PMTiles experience (HTTP Range support) use the bundled server instead:

```powershell
python serve_range.py
```

## URL presets (embedding & deep links)

The map page reads these query parameters so you can deep-link or embed it cleanly:

| Param | Effect |
|---|---|
| `?cancel=191,99,H12` | Pre-cancel a comma-separated list of route IDs |
| `?panel=collapsed` | Start with the brand panel collapsed |
| `?legend=hidden` | Start with the legend hidden |
| `?embed=1` | Hide chrome for embedding inside an `<iframe>` |

## Project layout

```
.
├── index.html                          # Redirects to the map
├── London_PTAL_Accessibility_Map.html  # Main interactive map
├── story.html                          # Narrative companion page
├── serve_range.py                      # Local server with HTTP Range support
├── data_calculating/                   # Python pipeline + lightweight raw inputs
├── data_chunks_osm_network/            # 33 borough network chunks
├── grid_ai_chunks_osm_network/         # 64 grid AI batches
├── DATA/                               # Base grid layer + LSOA index
├── *.json                              # Manifests, summaries, route impacts
├── *.geojson                           # Stops, route lines, LSOA centroids
└── roundel/                            # UI assets
```

## Data inputs (runtime)

| File | Purpose |
|---|---|
| `route_grid_impacts_osm_network.json` | ~540 routes × grid-cell impact matrix |
| `grid_ai_chunks_osm_network/` | Grid AI summary batches |
| `data_chunks_osm_network/` | Per-borough network data |
| `London_Stops_With_Routes.geojson` | ~27 k transit stops with route lists |
| `route_lines.geojson` | ~438 route geometries |
| `lsoa_ptal.pmtiles` (optional) | Vector tileset for the LSOA layer |

The Python pipeline that produced these files lives in [`data_calculating/`](data_calculating/) — see its README for script roles, regeneration order and links to external open datasets (TfL Open Data, ONS, Geofabrik OSM).

## Performance notes

- Initial map paint: ~2–5 s (progress indicator shown)
- Route impact data: lazy-loaded (~12 MB, ~8 s on first interaction)
- Grid recalculation on a route cancellation: ~100 ms

## Browser compatibility

- Chrome / Edge (recommended)
- Firefox
- Safari 14+

## Troubleshooting

**Map is blank** — open DevTools (F12) and check the Console; usually a network error fetching one of the JSON files. Hard-refresh with Ctrl+Shift+R to bypass cache.

**Grid invisible at some zooms** — fixed; the grid layer is enabled at zoom 7–16, with outlines from zoom 10.

**Slow loading on the first visit** — the impact matrix is lazy-loaded the first time you cancel a route; subsequent interactions are instant.

## License & attribution

- Code: CASA0029 group project, UCL.
- Map base tiles © Mapbox, © OpenStreetMap contributors.
- Transport data: *Powered by TfL Open Data*, contains OS data © Crown copyright and database rights.
- Boundaries © ONS / © Crown copyright and database right.
