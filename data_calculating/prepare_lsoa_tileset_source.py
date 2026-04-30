"""
Prepare a lightweight LSOA GeoJSON source for Tippecanoe / Mapbox upload.

This does not reduce the number of LSOA polygons. It only:
  - keeps fields needed by the map
  - rounds coordinates to 6 decimal places
  - writes compact JSON

Output:
  tileset_sources/lsoa_ptal_tiles_source.geojson
"""

import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
INPUT = BASE_DIR / "DATA" / "LSOA_aggregated_PTAL_stats_2023.geojson"
OUT_DIR = BASE_DIR / "tileset_sources"
OUTPUT = OUT_DIR / "lsoa_ptal_tiles_source.geojson"

KEEP_FIELDS = [
    "FID",
    "LSOA21CD",
    "LSOA21NM",
    "borough",
    "mean_AI",
    "MEAN_PTAL_",
]


def round_coords(value):
    if isinstance(value, list):
        return [round_coords(item) for item in value]
    if isinstance(value, float):
        return round(value, 6)
    return value


def main():
    OUT_DIR.mkdir(exist_ok=True)
    with INPUT.open("r", encoding="utf-8") as file:
        data = json.load(file)

    features = []
    for feature in data["features"]:
        props = feature.get("properties", {})
        clean_props = {field: props.get(field) for field in KEEP_FIELDS}
        features.append(
            {
                "type": "Feature",
                "properties": clean_props,
                "geometry": {
                    "type": feature["geometry"]["type"],
                    "coordinates": round_coords(feature["geometry"]["coordinates"]),
                },
            }
        )

    output = {"type": "FeatureCollection", "features": features}
    with OUTPUT.open("w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, separators=(",", ":"))

    input_mb = INPUT.stat().st_size / 1024 / 1024
    output_mb = OUTPUT.stat().st_size / 1024 / 1024
    print(f"Wrote {OUTPUT}")
    print(f"Features: {len(features)}")
    print(f"Input: {input_mb:.1f} MB")
    print(f"Output: {output_mb:.1f} MB")


if __name__ == "__main__":
    main()
