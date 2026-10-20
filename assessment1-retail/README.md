# UK Retail Formats & Convenience Store Ratio
**CASA0029 · Individual Visualisation Assessment 1 · Siyan Tao**

An interactive map exploring retail formats and the share of convenience stores across UK Local Authority Districts. The submitted project is titled *Distribution of Retail Formats and Convenience Store Ratio Interactive Map 2025*.

## Open the website

- [Website source / local entry point](index.html)
- Intended GitHub Pages address after this branch is merged: https://taoo2025.github.io/CASA0029/assessment1-retail/

The Pages address is not yet a verified deployment.

## Explore

- View convenience stores and superstores with brand-specific colours.
- Compare Tesco, Sainsbury's, Asda, Morrisons, Waitrose, and Marks & Spencer.
- Hover over a district to see retailer counts and a brand chart.
- Click a district to pin its information, then clear the selection to resume hovering.
- Toggle the convenience-store ratio layer and inspect district-level percentages.
- Expand the legend to inspect the symbols and brand categories.

This is a descriptive visualisation of the selected retailers, not a complete census of every UK retail business or a time-series analysis.

## Implementation

The original coursework website uses **Mapbox GL JS**, a **Mapbox Studio** style with hosted data layers, **Chart.js** and **Turf.js**. Data preparation used Python/GeoPandas and QGIS to connect retailer locations to district boundaries.

The page reads retailer and district features from its hosted Mapbox style. It does not fetch the local raw shapefiles. Brand counts use `querySourceFeatures`, so loaded map tiles and zoom/viewport can affect the features available for counting; do not assume these are independently validated nationwide totals.

## Run locally

From the repository root:

```bash
python -m http.server 8080
```

Open http://localhost:8080/assessment1-retail/ in a browser with WebGL support. Internet access is required for Mapbox, its hosted layers and the JavaScript libraries.

The original public Mapbox browser token and style reference are preserved in the page. Rendering depends on that account's style/tileset availability, token permissions and any URL restrictions. If the map is blank, inspect browser network errors and verify the original style includes the retailer, LAD boundary and aggregated ratio layers. The style's current availability was not verified during this update.

## Files

| File | Role |
|---|---|
| `index.html` | Original coursework map, copied from `mapbox_map.html` |
| `mapbox_map_styles.css` | Original styling |
| `aggregate_lad_data.py` | Deduplicates prepared LAD records and writes the aggregated layer |
| `export_lad_data.py` | Exports prepared LAD data to formats used in the original workflow |

The preparation scripts expect the original `data/UK_LAD/` shapefiles relative to this directory. Those source/intermediate datasets are not included in this addition. The scripts are supporting coursework code, not a complete one-command rebuild of the Mapbox tilesets. Review them before running: aggregation writes shapefiles and backups, while the coordinate export assumes point geometries.

## Data and attribution

- **Geolytix Retail Points** — retailer locations and formats; source link and attribution are retained in the map.
- **ONS Open Geography Portal** — Local Authority District boundaries (May 2024), with the attribution shown in the map.
- Basemap and hosted layers use Mapbox; retain the map's built-in attribution.
- Map design and report: Siyan Tao. The coursework report states that AI assisted code modifications, while the design concept and article writing were the author's work.

## Verification

The inline JavaScript passed a syntax check, and the local stylesheet link resolves to an included file. The original website source is preserved; browser interactions and live Mapbox rendering have not been re-tested in this update.
