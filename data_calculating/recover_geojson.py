#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
恢复GeoJSON数据文件脚本
从现有的Shapefile和CSV数据重新生成HTML所需的GeoJSON文件
"""

import geopandas as gpd
import pandas as pd
import json
import os
from pathlib import Path

print("="*70)
print("【GeoJSON 恢复工具】")
print("="*70)

# 设置路径
base_path = Path(__file__).parent
data_path = base_path / "DATA"
output_path = base_path / "DATA"

print(f"\n📁 基础路径: {base_path}")
print(f"📁 数据路径: {data_path}")
print(f"📁 输出路径: {output_path}")

# ============ 恢复 LSOA GeoJSON ============
print("\n" + "="*70)
print("【第1步】从Shapefile恢复 LSOA GeoJSON")
print("="*70)

lsoa_shp_path = data_path / "LSOA_London.shp"

if lsoa_shp_path.exists():
    try:
        print(f"\n读取Shapefile: {lsoa_shp_path}")
        gdf = gpd.read_file(str(lsoa_shp_path))
        
        print(f"✓ 成功读取LSOA数据")
        print(f"  - 坐标系: {gdf.crs}")
        print(f"  - 行数: {len(gdf)}")
        print(f"  - 列名: {list(gdf.columns)}")
        
        # 转换为WGS84（EPSG:4326）如果需要
        if gdf.crs and gdf.crs.to_epsg() != 4326:
            print(f"\n转换坐标系: {gdf.crs.to_epsg()} → 4326 (WGS84)")
            gdf = gdf.to_crs(epsg=4326)
        
        # 导出为GeoJSON
        output_geojson = output_path / "ptal_lsoa_data.geojson"
        print(f"\n导出为GeoJSON: {output_geojson}")
        gdf.to_file(str(output_geojson), driver='GeoJSON')
        
        # 统计信息
        geojson_size = output_geojson.stat().st_size / (1024 * 1024)  # MB
        print(f"✓ 成功生成 ptal_lsoa_data.geojson")
        print(f"  - 文件大小: {geojson_size:.2f} MB")
        print(f"  - 特征数: {len(gdf)}")
        
    except Exception as e:
        print(f"✗ 错误: {e}")
        print(f"  请检查Shapefile文件是否完整（需要 .shp, .shx, .dbf 等）")
else:
    print(f"✗ 找不到Shapefile: {lsoa_shp_path}")

# ============ 检查100m网格数据 ============
print("\n" + "="*70)
print("【第2步】检查 100m网格数据状态")
print("="*70)

grid_csv_path = data_path / "PTAL_2023_Grid_100mx100m_Data.csv"
grid_geojson_path = output_path / "ptal_grid_100m_data_simplified.geojson"

if grid_csv_path.exists():
    print(f"\n✓ 找到100m网格CSV: {grid_csv_path}")
    print("  可以生成ptal_grid_100m_data_simplified.geojson")
elif grid_geojson_path.exists():
    print(f"\n✓ 已存在100m网格GeoJSON: {grid_geojson_path}")
else:
    print(f"\n✗ 找不到100m网格数据：")
    print(f"  - CSV: {grid_csv_path}")
    print(f"  - GeoJSON: {grid_geojson_path}")
    print(f"\n【需要处理】")
    print(f"  100m网格数据已被删除，需要：")
    print(f"  1. 检查是否有备份副本")
    print(f"  2. 或用Borough级别数据作为替代")
    print(f"  3. 或从官方数据源重新下载")

# ============ 最终状态检查 ============
print("\n" + "="*70)
print("【最终状态】")
print("="*70)

missing_files = []

for filename in ["ptal_lsoa_data.geojson", "ptal_grid_100m_data_simplified.geojson"]:
    filepath = output_path / filename
    if filepath.exists():
        size = filepath.stat().st_size / (1024 * 1024)
        print(f"✓ {filename} ({size:.2f} MB)")
    else:
        print(f"✗ {filename} 【缺失】")
        missing_files.append(filename)

if not missing_files:
    print(f"\n✓ 所有文件已恢复！HTML可以加载数据")
else:
    print(f"\n⚠️ 还需要处理的文件: {missing_files}")

print("\n" + "="*70)
