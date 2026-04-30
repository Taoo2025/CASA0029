#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
处理伦敦交通数据：
1. 从各GeoJSON文件提取站点坐标
2. 生成transport_lines_detailed.json供HTML使用
3. 过滤Stops.csv到伦敦范围
"""

import json
import pandas as pd
import geopandas as gpd
from pathlib import Path
from shapely.geometry import Point
import warnings

warnings.filterwarnings('ignore')

print("="*80)
print("【伦敦交通数据处理工具】")
print("="*80)

# 设置路径
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "DATA"
LSOA_SHP = DATA_DIR / "LSOA_London.shp"  # 用于获取伦敦边界

print(f"\n📁 工作目录: {BASE_DIR}")
print(f"📁 数据目录: {DATA_DIR}")

# ========== 第一步：获取伦敦范围 ==========
print("\n" + "="*80)
print("【第1步】加载伦敦地理范围")
print("="*80)

london_bounds = None
if LSOA_SHP.exists():
    try:
        print(f"\n加载LSOA Shapefile: {LSOA_SHP}")
        lsoa_gdf = gpd.read_file(str(LSOA_SHP))
        
        # 转换为WGS84
        if lsoa_gdf.crs.to_epsg() != 4326:
            lsoa_gdf = lsoa_gdf.to_crs(epsg=4326)
        
        # 获取伦敦的边界框
        bounds = lsoa_gdf.total_bounds  # [minx, miny, maxx, maxy]
        london_bounds = {
            'min_lon': float(bounds[0]),
            'min_lat': float(bounds[1]),
            'max_lon': float(bounds[2]),
            'max_lat': float(bounds[3])
        }
        
        print(f"✓ 伦敦范围:")
        print(f"  - 经度: {london_bounds['min_lon']:.4f} ~ {london_bounds['max_lon']:.4f}")
        print(f"  - 纬度: {london_bounds['min_lat']:.4f} ~ {london_bounds['max_lat']:.4f}")
    except Exception as e:
        print(f"✗ 加载失败: {e}")
else:
    print(f"✗ 找不到LSOA Shapefile: {LSOA_SHP}")

# ========== 第二步：处理各交通线的GeoJSON ==========
print("\n" + "="*80)
print("【第2步】处理交通线GeoJSON文件")
print("="*80)

# 定义要处理的交通线和对应的GeoJSON文件
transport_files = {
    'Underground': [
        'Underground_Stations.geojson',
        'Bakerloo|Central|Circle|District|Hammersmith|Jubilee|Metropolitan|Northern|Piccadilly|Victoria|Waterloo'
    ],
    'Overground': 'Overground_Stations.geojson',
    'Elizabeth Line': 'Elizabeth_Line_Stations.geojson',
    'Tramlink': 'Tramlink_Stations.geojson',
    'DLR': 'DLR_Stations.geojson',
    'Bus Stops': 'Bus_Stops.geojson',
}

lines_data = {}  # {line_id: [stations]}

for line_type, geojson_file in transport_files.items():
    if isinstance(geojson_file, list):
        geojson_file = geojson_file[0]
    
    file_path = DATA_DIR / geojson_file
    
    if not file_path.exists():
        print(f"⚠️  文件不存在: {geojson_file}")
        continue
    
    try:
        print(f"\n处理: {geojson_file}")
        
        # 读取GeoJSON
        with open(file_path, 'r', encoding='utf-8') as f:
            geojson_data = json.load(f)
        
        print(f"  - 特征数: {len(geojson_data.get('features', []))}")
        
        # 提取站点信息
        stations = []
        for feature in geojson_data.get('features', []):
            try:
                props = feature.get('properties', {})
                coords = feature.get('geometry', {}).get('coordinates', [])
                
                if coords and len(coords) >= 2:
                    # GeoJSON坐标格式是 [lon, lat]
                    lon, lat = coords[0], coords[1]
                    
                    # 检查是否在伦敦范围内（如果有bounds）
                    if london_bounds:
                        if not (london_bounds['min_lon'] <= lon <= london_bounds['max_lon'] and
                                london_bounds['min_lat'] <= lat <= london_bounds['max_lat']):
                            continue
                    
                    station_info = {
                        'name': props.get('name', props.get('station_name', 'Unknown')),
                        'lon': float(lon),
                        'lat': float(lat),
                        'type': props.get('type', line_type)
                    }
                    stations.append(station_info)
            except Exception as e:
                continue
        
        if stations:
            lines_data[line_type] = stations
            print(f"  ✓ 提取了 {len(stations)} 个站点")
        else:
            print(f"  ✗ 未找到有效站点")
            
    except Exception as e:
        print(f"  ✗ 错误: {e}")

# ========== 第三步：生成transport_lines_detailed.json ==========
print("\n" + "="*80)
print("【第3步】生成transport_lines_detailed.json")
print("="*80)

transport_lines_output = {
    'lines': lines_data,
    'summary': {
        'total_stations': sum(len(stations) for stations in lines_data.values()),
        'total_lines': len(lines_data),
        'london_bounds': london_bounds
    }
}

output_file = BASE_DIR / 'transport_lines_detailed.json'
try:
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(transport_lines_output, f, ensure_ascii=False, indent=2)
    
    file_size = output_file.stat().st_size / (1024 * 1024)
    print(f"\n✓ 已生成: {output_file}")
    print(f"  - 文件大小: {file_size:.2f} MB")
    print(f"  - 包含线路: {transport_lines_output['summary']['total_lines']}")
    print(f"  - 总站点数: {transport_lines_output['summary']['total_stations']}")
except Exception as e:
    print(f"\n✗ 生成失败: {e}")

# ========== 第四步：处理Stops.csv - 过滤到伦敦范围 ==========
print("\n" + "="*80)
print("【第4步】处理Stops.csv - 过滤伦敦范围")
print("="*80)

stops_csv = DATA_DIR / "Stops.csv"

if stops_csv.exists():
    try:
        print(f"\n读取: {stops_csv}")
        stops_df = pd.read_csv(stops_csv, low_memory=False)
        print(f"  - 原始记录数: {len(stops_df)}")
        
        # 检查必要列
        if 'Latitude' in stops_df.columns and 'Longitude' in stops_df.columns:
            # 移除缺失的坐标
            stops_df = stops_df.dropna(subset=['Latitude', 'Longitude'])
            print(f"  - 有效坐标数: {len(stops_df)}")
            
            if london_bounds:
                # 过滤到伦敦范围
                london_stops = stops_df[
                    (stops_df['Longitude'] >= london_bounds['min_lon']) &
                    (stops_df['Longitude'] <= london_bounds['max_lon']) &
                    (stops_df['Latitude'] >= london_bounds['min_lat']) &
                    (stops_df['Latitude'] <= london_bounds['max_lat'])
                ]
                
                print(f"  - 伦敦范围内: {len(london_stops)} ⭐")
                
                # 按类型统计
                print(f"\n  按类型分类:")
                if 'StopType' in london_stops.columns:
                    type_counts = london_stops['StopType'].value_counts()
                    for stop_type, count in type_counts.head(10).items():
                        print(f"    - {stop_type}: {count}")
                
                # 保存过滤后的Stops数据
                output_stops = DATA_DIR / "London_Stops_Filtered.csv"
                london_stops.to_csv(output_stops, index=False)
                print(f"\n  ✓ 已保存过滤后的Stops: {output_stops}")
                
                # 也生成GeoJSON版本
                stops_gdf = gpd.GeoDataFrame(
                    london_stops,
                    geometry=gpd.points_from_xy(london_stops['Longitude'], london_stops['Latitude']),
                    crs='EPSG:4326'
                )
                
                output_stops_geojson = DATA_DIR / "London_Stops_Filtered.geojson"
                stops_gdf.to_file(output_stops_geojson, driver='GeoJSON')
                size = output_stops_geojson.stat().st_size / (1024 * 1024)
                print(f"  ✓ 已生成GeoJSON: {output_stops_geojson} ({size:.2f} MB)")
            else:
                print("  ⚠️ 未能获取伦敦范围，跳过过滤")
        else:
            print("  ✗ 缺少必要的坐标列")
    except Exception as e:
        print(f"  ✗ 处理失败: {e}")
else:
    print(f"✗ 找不到: {stops_csv}")

# ========== 完成 ==========
print("\n" + "="*80)
print("【处理完成】")
print("="*80)
print(f"\n✓ 关键文件已生成:")
print(f"  1. transport_lines_detailed.json - 用于HTML加载站点")
print(f"  2. London_Stops_Filtered.csv - 伦敦范围内的所有Stop")
print(f"  3. London_Stops_Filtered.geojson - GeoJSON格式的Stop数据")
print(f"\nHTML现在应该可以加载这些数据了！")
print("="*80)
