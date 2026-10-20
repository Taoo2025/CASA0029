#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Aggregate UK_LAD_Joint_modified data for Mapbox visualization
Keep only LAD24NM and calculated metrics, merge duplicate LAD records into one
"""

import geopandas as gpd
import pandas as pd
import os
import shutil

def main():
    # Load the modified shapefile
    shp_path = r'data/UK_LAD/UK_LAD_Joint_modified.shp'
    print(f"Loading shapefile from: {shp_path}")
    gdf = gpd.read_file(shp_path)
    
    print(f"Original shape: {gdf.shape}")
    print(f"Original columns: {gdf.columns.tolist()}")
    
    # Group by LAD24NM and keep only the first row (all have same conv_cnt, super_cnt, ConvRatio, geometry)
    print(f"\nGrouping by LAD24NM...")
    gdf_aggregated = gdf.groupby('LAD24NM').first().reset_index()
    
    # Keep only essential columns for Mapbox visualization
    columns_to_keep = ['LAD24NM', 'conv_cnt', 'super_cnt', 'ConvRatio', 'geometry']
    gdf_aggregated = gdf_aggregated[columns_to_keep]
    
    print(f"\nAggregated shape: {gdf_aggregated.shape}")
    print(f"Aggregated columns: {gdf_aggregated.columns.tolist()}")
    
    # Display sample data
    print(f"\nSample aggregated data:")
    print(gdf_aggregated.head(10))
    
    print(f"\nSummary statistics:")
    print(f"Total unique LAD areas: {len(gdf_aggregated)}")
    print(f"Conv_cnt range: {gdf_aggregated['conv_cnt'].min()} to {gdf_aggregated['conv_cnt'].max()}")
    print(f"Super_cnt range: {gdf_aggregated['super_cnt'].min()} to {gdf_aggregated['super_cnt'].max()}")
    print(f"ConvRatio range: {gdf_aggregated['ConvRatio'].min():.4f} to {gdf_aggregated['ConvRatio'].max():.4f}")
    
    # Save the aggregated shapefile
    import tempfile
    output_path = r'data/UK_LAD/UK_LAD_Aggregated.shp'
    base_path = r'data/UK_LAD/UK_LAD_Aggregated'
    extensions = ['.shp', '.shx', '.dbf', '.prj', '.cpg']
    
    # Create backup
    print(f"\nCreating backup of modified files...")
    base_modified = r'data/UK_LAD/UK_LAD_Joint_modified'
    base_modified_backup = r'data/UK_LAD/UK_LAD_Joint_modified_backup'
    for ext in extensions:
        src = base_modified + ext
        dst = base_modified_backup + ext
        if os.path.exists(src):
            shutil.copy2(src, dst)
            print(f"  Backed up: {dst}")
    
    # Save to temp directory first, then copy
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = os.path.join(tmpdir, 'UK_LAD_Aggregated.shp')
        print(f"\nSaving to temporary location: {temp_path}")
        gdf_aggregated.to_file(temp_path, driver='ESRI Shapefile')
        
        # Copy from temp to final location
        print(f"Copying aggregated shapefile to: {output_path}")
        for ext in extensions:
            src = os.path.join(tmpdir, f'UK_LAD_Aggregated{ext}')
            dst = base_path + ext
            if os.path.exists(src):
                shutil.copy2(src, dst)
                print(f"  Created: {dst}")
    
    print(f"\n[SUCCESS] Aggregation complete!")
    print(f"Aggregated shapefile saved to: {output_path}")
    print(f"\nColumns in aggregated file:")
    for col in gdf_aggregated.columns:
        print(f"  - {col}")
    
    print(f"\nReady for Mapbox visualization!")
    print(f"Use UK_LAD/UK_LAD_Aggregated.shp for your Mapbox maps")

if __name__ == '__main__':
    main()
