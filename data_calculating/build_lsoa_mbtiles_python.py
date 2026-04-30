"""
Build an LSOA Mapbox Vector Tile MBTiles file without tippecanoe.

This is a Windows-friendly fallback when tippecanoe is not installed.
It preserves all LSOA features and required attributes, clips polygons per tile,
and writes an MBTiles file suitable for upload to Mapbox Studio.
"""

import argparse
import gzip
import json
import math
import sqlite3
import time
from pathlib import Path

import geopandas as gpd
import mercantile
from mapbox_vector_tile import encode
from shapely.geometry import box, mapping, shape
from shapely.validation import make_valid


BASE_DIR = Path(__file__).resolve().parent
SOURCE = BASE_DIR / "tileset_sources" / "lsoa_ptal_tiles_source.geojson"
OUTPUT = BASE_DIR / "tileset_sources" / "lsoa_ptal_z6_z14.mbtiles"
LAYER_NAME = "lsoa_ptal"


def create_schema(conn):
    conn.execute("DROP TABLE IF EXISTS metadata")
    conn.execute("DROP TABLE IF EXISTS tiles")
    conn.execute("CREATE TABLE metadata (name TEXT, value TEXT)")
    conn.execute(
        "CREATE TABLE tiles (zoom_level INTEGER, tile_column INTEGER, tile_row INTEGER, tile_data BLOB)"
    )
    conn.execute(
        "CREATE UNIQUE INDEX tile_index ON tiles (zoom_level, tile_column, tile_row)"
    )


def insert_metadata(conn, bounds, minzoom, maxzoom):
    metadata = {
        "name": LAYER_NAME,
        "type": "overlay",
        "version": "1.0",
        "description": "London LSOA PTAL context layer",
        "format": "pbf",
        "bounds": ",".join(f"{value:.6f}" for value in bounds),
        "center": f"{(bounds[0] + bounds[2]) / 2:.6f},{(bounds[1] + bounds[3]) / 2:.6f},10",
        "minzoom": str(minzoom),
        "maxzoom": str(maxzoom),
        "json": json.dumps(
            {
                "vector_layers": [
                    {
                        "id": LAYER_NAME,
                        "description": "London LSOA PTAL context layer",
                        "minzoom": minzoom,
                        "maxzoom": maxzoom,
                        "fields": {
                            "FID": "Number",
                            "LSOA21CD": "String",
                            "LSOA21NM": "String",
                            "borough": "String",
                            "mean_AI": "Number",
                            "MEAN_PTAL_": "String",
                        },
                    }
                ]
            }
        ),
    }
    conn.executemany("INSERT INTO metadata (name, value) VALUES (?, ?)", metadata.items())


def valid_geom(geom):
    if geom.is_empty:
        return None
    if not geom.is_valid:
        geom = make_valid(geom)
    if geom.is_empty:
        return None
    if geom.geom_type == "GeometryCollection":
        parts = [part for part in geom.geoms if part.geom_type in {"Polygon", "MultiPolygon"} and not part.is_empty]
        if not parts:
            return None
        return parts[0] if len(parts) == 1 else parts[0].union(parts[1:])
    return geom


def feature_to_mvt(row, tile_bounds_geom, tile_bounds):
    geom = row.geometry.intersection(tile_bounds_geom)
    geom = valid_geom(geom)
    if geom is None:
        return None

    props = {
        "FID": int(row.FID) if row.FID is not None else None,
        "LSOA21CD": str(row.LSOA21CD),
        "LSOA21NM": str(row.LSOA21NM),
        "borough": str(row.borough),
        "mean_AI": float(row.mean_AI) if row.mean_AI is not None else None,
        "MEAN_PTAL_": str(row.MEAN_PTAL_),
    }
    return {"geometry": mapping(geom), "properties": props}


def build_mbtiles(minzoom, maxzoom, output):
    start = time.time()
    print(f"Loading {SOURCE}...")
    gdf = gpd.read_file(SOURCE)
    gdf = gdf.set_crs("EPSG:4326", allow_override=True)
    bounds = tuple(float(value) for value in gdf.total_bounds)
    sindex = gdf.sindex
    print(f"Features: {len(gdf):,}")
    print(f"Bounds: {bounds}")

    if output.exists():
        output.unlink()
    conn = sqlite3.connect(output)
    create_schema(conn)
    insert_metadata(conn, bounds, minzoom, maxzoom)

    total_tiles = 0
    written_tiles = 0
    rows = []

    for z in range(minzoom, maxzoom + 1):
        tiles = list(mercantile.tiles(bounds[0], bounds[1], bounds[2], bounds[3], [z]))
        total_tiles += len(tiles)
        zoom_written = 0
        print(f"Zoom {z}: {len(tiles):,} candidate tiles")

        for idx, tile in enumerate(tiles, start=1):
            b = mercantile.bounds(tile)
            tile_bounds = (b.west, b.south, b.east, b.north)
            tile_geom = box(*tile_bounds)
            candidate_idx = list(sindex.query(tile_geom, predicate="intersects"))
            if not candidate_idx:
                continue

            features = []
            for row in gdf.iloc[candidate_idx].itertuples(index=False):
                feature = feature_to_mvt(row, tile_geom, tile_bounds)
                if feature:
                    features.append(feature)

            if not features:
                continue

            tile_bytes = encode(
                [{"name": LAYER_NAME, "features": features}],
                default_options={"quantize_bounds": tile_bounds, "extents": 4096},
            )
            tile_bytes = gzip.compress(tile_bytes)
            tms_y = (1 << z) - 1 - tile.y
            rows.append((z, tile.x, tms_y, sqlite3.Binary(tile_bytes)))
            written_tiles += 1
            zoom_written += 1

            if len(rows) >= 500:
                conn.executemany(
                    "INSERT OR REPLACE INTO tiles (zoom_level, tile_column, tile_row, tile_data) VALUES (?, ?, ?, ?)",
                    rows,
                )
                conn.commit()
                rows = []

            if idx % 1000 == 0:
                print(f"  z{z}: {idx:,}/{len(tiles):,} checked, {zoom_written:,} written")

        print(f"  z{z}: wrote {zoom_written:,} tiles")

    if rows:
        conn.executemany(
            "INSERT OR REPLACE INTO tiles (zoom_level, tile_column, tile_row, tile_data) VALUES (?, ?, ?, ?)",
            rows,
        )
        conn.commit()

    conn.execute("VACUUM")
    conn.close()
    size_mb = output.stat().st_size / 1024 / 1024
    elapsed = time.time() - start
    print(f"Wrote {output}")
    print(f"Candidate tiles: {total_tiles:,}")
    print(f"Written tiles: {written_tiles:,}")
    print(f"Size: {size_mb:.1f} MB")
    print(f"Elapsed: {elapsed:.1f}s")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--minzoom", type=int, default=6)
    parser.add_argument("--maxzoom", type=int, default=14)
    parser.add_argument("--output", default=str(OUTPUT))
    args = parser.parse_args()
    build_mbtiles(args.minzoom, args.maxzoom, Path(args.output))


if __name__ == "__main__":
    main()
