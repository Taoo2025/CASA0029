#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Export UK_LAD_Aggregated.shp to multiple formats for Mapbox and data analysis
"""

import geopandas as gpd
import json
import os

def main():
    # Load the aggregated shapefile
    shp_path = r'data/UK_LAD/UK_LAD_Aggregated.shp'
    print(f"Loading shapefile from: {shp_path}")
    gdf = gpd.read_file(shp_path)
    
    print(f"Shapefile info:")
    print(f"  Records: {len(gdf)}")
    print(f"  Columns: {gdf.columns.tolist()}")
    
    # Export 1: GeoJSON (best for Mapbox)
    print(f"\n[1] Exporting to GeoJSON format...")
    geojson_path = r'data/UK_LAD/UK_LAD_Aggregated.geojson'
    gdf.to_file(geojson_path, driver='GeoJSON')
    file_size = os.path.getsize(geojson_path) / 1024  # KB
    print(f"  Created: {geojson_path}")
    print(f"  File size: {file_size:.2f} KB")
    
    # Export 2: Feature Collection GeoJSON (alternative format)
    print(f"\n[2] Creating Feature Collection GeoJSON...")
    geojson_fc_path = r'data/UK_LAD/UK_LAD_Aggregated_features.geojson'
    geojson_data = json.loads(gdf.to_json())
    with open(geojson_fc_path, 'w', encoding='utf-8') as f:
        json.dump(geojson_data, f, ensure_ascii=False, indent=2)
    file_size = os.path.getsize(geojson_fc_path) / 1024  # KB
    print(f"  Created: {geojson_fc_path}")
    print(f"  File size: {file_size:.2f} KB")
    
    # Export 3: CSV without geometry (for data analysis)
    print(f"\n[3] Exporting to CSV format (without geometry)...")
    csv_path = r'data/UK_LAD/UK_LAD_Aggregated.csv'
    gdf_csv = gdf.drop('geometry', axis=1)
    gdf_csv.to_csv(csv_path, index=False)
    file_size = os.path.getsize(csv_path) / 1024  # KB
    print(f"  Created: {csv_path}")
    print(f"  File size: {file_size:.2f} KB")
    
    # Export 4: CSV with coordinates
    print(f"\n[4] Exporting to CSV with coordinates...")
    csv_coords_path = r'data/UK_LAD/UK_LAD_Aggregated_with_coords.csv'
    gdf_csv_coords = gdf.copy()
    gdf_csv_coords['longitude'] = gdf_csv_coords.geometry.x
    gdf_csv_coords['latitude'] = gdf_csv_coords.geometry.y
    gdf_csv_coords = gdf_csv_coords.drop('geometry', axis=1)
    gdf_csv_coords.to_csv(csv_coords_path, index=False)
    file_size = os.path.getsize(csv_coords_path) / 1024  # KB
    print(f"  Created: {csv_coords_path}")
    print(f"  File size: {file_size:.2f} KB")
    
    # Export 5: JSON (for JavaScript/Mapbox)
    print(f"\n[5] Exporting to JSON format...")
    json_path = r'data/UK_LAD/UK_LAD_Aggregated.json'
    json_data = []
    for idx, row in gdf.iterrows():
        record = {
            'LAD24NM': row['LAD24NM'],
            'conv_cnt': int(row['conv_cnt']),
            'super_cnt': int(row['super_cnt']),
            'ConvRatio': round(float(row['ConvRatio']), 6),
            'longitude': float(row.geometry.x),
            'latitude': float(row.geometry.y)
        }
        json_data.append(record)
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    file_size = os.path.getsize(json_path) / 1024  # KB
    print(f"  Created: {json_path}")
    print(f"  File size: {file_size:.2f} KB")
    
    # Summary
    print(f"\n{'='*60}")
    print(f"[EXPORT COMPLETE]")
    print(f"{'='*60}")
    print(f"\nExported files:")
    print(f"  1. GeoJSON (Mapbox ready): UK_LAD_Aggregated.geojson")
    print(f"  2. GeoJSON (Features):     UK_LAD_Aggregated_features.geojson")
    print(f"  3. CSV (data only):        UK_LAD_Aggregated.csv")
    print(f"  4. CSV (with coords):      UK_LAD_Aggregated_with_coords.csv")
    print(f"  5. JSON (Mapbox/JS):       UK_LAD_Aggregated.json")
    print(f"\nAll files saved to: data/UK_LAD/")
    
    # Show sample data
    print(f"\n{'='*60}")
    print(f"Sample data (first 5 records):")
    print(f"{'='*60}")
    print(gdf[['LAD24NM', 'conv_cnt', 'super_cnt', 'ConvRatio']].head())
    
    print(f"\n{'='*60}")
    print(f"Ready to use in Mapbox!")
    print(f"Recommended: Use 'UK_LAD_Aggregated.geojson' for Mapbox maps")
    print(f"{'='*60}")

if __name__ == '__main__':
    main()
