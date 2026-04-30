#!/usr/bin/env python3
"""
Generate lsoa_ptal.pmtiles from LSOA GeoJSON.

This creates a local PMTiles file covering zoom 7-12 so that LSOA PTAL
colours are visible at all zoom levels without Mapbox's automatic
tile-simplification truncating lower zoom levels.

Run once:
    python generate_lsoa_pmtiles.py

Then serve with serve_range.py (Range-request-capable HTTP server) and
load in the map via the pmtiles:// protocol.
"""

import sys
import os
import time
from pathlib import Path

import geopandas as gpd
import mercantile
import mapbox_vector_tile
from shapely.geometry import mapping, box as shapely_box
from shapely.ops import unary_union
from pmtiles.writer import Writer
from pmtiles.tile import zxy_to_tileid, TileType, Compression

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent
LSOA_INPUT = ROOT / "DATA" / "LSOA_aggregated_PTAL_stats_2023.geojson"
OUTPUT = ROOT / "lsoa_ptal.pmtiles"

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
MIN_ZOOM = 7
MAX_ZOOM = 12
LAYER_NAME = "lsoa"
KEEP_PROPS = ["LSOA21CD", "MEAN_PTAL_"]

# London bounding box (WGS84: west, south, east, north)
LONDON_BOUNDS = (-0.54, 51.26, 0.36, 51.72)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    t0 = time.time()
    print(f"Loading LSOA GeoJSON: {LSOA_INPUT}")
    gdf = gpd.read_file(LSOA_INPUT)
    print(f"  {len(gdf):,} features loaded")

    # Keep only needed columns
    keep_cols = [c for c in KEEP_PROPS if c in gdf.columns] + ["geometry"]
    gdf = gdf[keep_cols].copy()

    # Reproject to Web Mercator (EPSG:3857) – required for MVT pixel encoding
    print("Reprojecting to EPSG:3857 …")
    gdf_m = gdf.to_crs("EPSG:3857")
    gdf_m = gdf_m[gdf_m.geometry.is_valid & ~gdf_m.geometry.is_empty].copy()

    # Build spatial index once
    sindex = gdf_m.sindex

    tiles_written = 0
    tiles_empty = 0

    print(f"Writing PMTiles (zoom {MIN_ZOOM}-{MAX_ZOOM}) → {OUTPUT}")

    with open(OUTPUT, "wb") as f:
        writer = Writer(f)

        for zoom in range(MIN_ZOOM, MAX_ZOOM + 1):
            zt0 = time.time()
            west, south, east, north = LONDON_BOUNDS
            all_tiles = list(mercantile.tiles(west, south, east, north, zooms=zoom))
            print(f"  Zoom {zoom}: {len(all_tiles)} candidate tiles …", end="", flush=True)

            z_written = 0
            for tile in all_tiles:
                xy = mercantile.xy_bounds(tile)
                tile_box = shapely_box(xy.left, xy.bottom, xy.right, xy.top)

                # Fast spatial-index pre-filter
                cand_idx = list(sindex.intersection(tile_box.bounds))
                if not cand_idx:
                    tiles_empty += 1
                    continue

                cand = gdf_m.iloc[cand_idx]
                hits = cand[cand.geometry.intersects(tile_box)]
                if hits.empty:
                    tiles_empty += 1
                    continue

                features = []
                for _, row in hits.iterrows():
                    try:
                        geom = row.geometry.intersection(tile_box)
                        if geom is None or geom.is_empty:
                            continue
                        props = {p: row[p] for p in KEEP_PROPS if p in row.index}
                        features.append({"geometry": mapping(geom), "properties": props})
                    except Exception:
                        continue

                if not features:
                    tiles_empty += 1
                    continue

                try:
                    tile_data = mapbox_vector_tile.encode(
                        [{"name": LAYER_NAME, "features": features}],
                        default_options={
                            "extents": 4096,
                            "quantize_bounds": (xy.left, xy.bottom, xy.right, xy.top),
                            "y_coord_down": False,
                        },
                    )
                except Exception as e:
                    print(f"\n    Warning: encode failed for {tile}: {e}")
                    continue

                tileid = zxy_to_tileid(tile.z, tile.x, tile.y)
                writer.write_tile(tileid, tile_data)
                tiles_written += 1
                z_written += 1

            print(f" {z_written} written ({time.time() - zt0:.1f}s)")

        header = {
            "tile_type": TileType.MVT,
            "tile_compression": Compression.NONE,
            "min_lon_e7": int(LONDON_BOUNDS[0] * 10_000_000),
            "min_lat_e7": int(LONDON_BOUNDS[1] * 10_000_000),
            "max_lon_e7": int(LONDON_BOUNDS[2] * 10_000_000),
            "max_lat_e7": int(LONDON_BOUNDS[3] * 10_000_000),
            "center_zoom": 10,
            "center_lon_e7": int(-0.09 * 10_000_000),
            "center_lat_e7": int(51.505 * 10_000_000),
        }
        metadata = {
            "name": "LSOA PTAL 2023",
            "description": "London LSOA PTAL 2023 – local PMTiles, zoom 7-12",
            "vector_layers": [
                {
                    "id": LAYER_NAME,
                    "fields": {
                        "LSOA21CD": "String",
                        "MEAN_PTAL_": "String",
                    },
                }
            ],
        }
        if not writer.tile_entries:
            print("\nERROR: No tiles were written – check encode errors above.")
            sys.exit(1)
        writer.finalize(header, metadata)

    size_mb = os.path.getsize(OUTPUT) / 1e6
    print(f"\nDone in {time.time() - t0:.1f}s")
    print(f"  Tiles written : {tiles_written:,}")
    print(f"  Tiles empty   : {tiles_empty:,}")
    print(f"  Output size   : {size_mb:.1f} MB → {OUTPUT}")


if __name__ == "__main__":
    main()
