#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
增强LSOA数据：计算每个LSOA区域内各交通线的站点数量
同时提取Bus Routes数据
"""

import json
import geopandas as gpd
from pathlib import Path
from shapely.geometry import Point, shape
import warnings

warnings.filterwarnings('ignore')

print("="*80)
print("【增强LSOA和提取Bus Routes数据】")
print("="*80)

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "DATA"

# ========== 第一步：加载LSOA和站点数据 ==========
print("\n【第1步】加载地理数据")
print("="*80)

# 读取transport_lines_detailed.json
print("\n加载交通线站点数据...")
transport_file = BASE_DIR / 'transport_lines_detailed.json'
if not transport_file.exists():
    transport_file = BASE_DIR.parent / 'transport_lines_detailed.json'

with open(transport_file, 'r', encoding='utf-8') as f:
    transport_data = json.load(f)

lines_data = transport_data['lines']
print(f"✓ 已加载 {len(lines_data)} 类型交通线，共 {transport_data['summary']['total_stations']} 个站点")

# 按类型统计
for line_type, stations in lines_data.items():
    print(f"  - {line_type}: {len(stations)} 个站点")

# 读取LSOA GeoJSON
print("\n加载LSOA GeoJSON...")
lsoa_path = DATA_DIR / "LSOA_aggregated_PTAL_stats_2023.geojson"
with open(lsoa_path, 'r', encoding='utf-8') as f:
    lsoa_geojson = json.load(f)

print(f"✓ 已加载 {len(lsoa_geojson['features'])} 个LSOA区域")

# ========== 第二步：为每个LSOA计算各线路的站点数量 ==========
print("\n【第2步】计算LSOA内的交通线数量（这可能需要几分钟）")
print("="*80)

count = 0
for feature in lsoa_geojson['features']:
    count += 1
    if count % 100 == 0:
        print(f"处理中: {count}/{len(lsoa_geojson['features'])}...")
    
    # 获取LSOA多边形
    lsoa_geom = shape(feature['geometry'])
    props = feature['properties']
    
    # 为每条交通线计算站点数
    for line_type, stations in lines_data.items():
        # 规范化列名
        col_name = line_type.upper().replace(' ', '_').replace('&', 'AND')
        if col_name == 'UNDERGROUND':
            col_name = 'UG'
        elif col_name == 'ELIZABETH_LINE':
            col_name = 'ELR'
        elif col_name == 'OVERGROUND':
            col_name = 'OG'
        elif col_name == 'BUS_STOPS':
            col_name = 'BUS'
        
        col_name += '_COUNT'
        
        # 计算该LSOA内此交通线的站点数
        count_in_lsoa = 0
        for station in stations:
            point = Point(station['lon'], station['lat'])
            if lsoa_geom.contains(point):
                count_in_lsoa += 1
        
        props[col_name] = count_in_lsoa
    
    # 计算总的交通线数（有站点的线路）
    transport_lines_count = 0
    for line_type in lines_data.keys():
        col_name = line_type.upper().replace(' ', '_').replace('&', 'AND')
        if col_name == 'UNDERGROUND':
            col_name = 'UG'
        elif col_name == 'ELIZABETH_LINE':
            col_name = 'ELR'
        elif col_name == 'OVERGROUND':
            col_name = 'OG'
        elif col_name == 'BUS_STOPS':
            col_name = 'BUS'
        
        col_name += '_COUNT'
        if props.get(col_name, 0) > 0:
            transport_lines_count += 1
    
    props['TOTAL_TRANSPORT_LINES'] = transport_lines_count

print(f"✓ 完成计算，共处理 {count} 个LSOA区域")

# ========== 第三步：保存增强的LSOA GeoJSON ==========
print("\n【第3步】保存增强的LSOA GeoJSON")
print("="*80)

output_lsoa = DATA_DIR / "LSOA_aggregated_PTAL_stats_2023_enhanced.geojson"
with open(output_lsoa, 'w', encoding='utf-8') as f:
    json.dump(lsoa_geojson, f, ensure_ascii=False)

size = output_lsoa.stat().st_size / (1024 * 1024)
print(f"✓ 已保存: {output_lsoa}")
print(f"  文件大小: {size:.2f} MB")

# ========== 第四步：提取Bus Routes数据 ==========
print("\n【第4步】提取Bus Routes数据")
print("="*80)

routes_path = DATA_DIR / "Bus_Routes__direction_of_travel_.geojson"

if routes_path.exists():
    print(f"\n加载: {routes_path}")
    with open(routes_path, 'r', encoding='utf-8') as f:
        routes_geojson = json.load(f)
    
    print(f"✓ 加载了 {len(routes_geojson['features'])} 个route features")
    
    # 提取unique routes
    routes = {}
    route_directions = {}
    
    for feature in routes_geojson['features']:
        props = feature['properties']
        route_num = props.get('ROUTE', 'Unknown')
        direction = props.get('DIRECTION', 'Unknown')
        status = props.get('STATUS', 'CURRENT')
        
        if status == 'CURRENT':  # 只保留CURRENT的路由
            if route_num not in routes:
                routes[route_num] = {
                    'name': route_num,
                    'type': 'Bus Route',
                    'directions': []
                }
            
            if direction not in routes[route_num]['directions']:
                routes[route_num]['directions'].append(direction)
            
            if route_num not in route_directions:
                route_directions[route_num] = []
            if direction not in route_directions[route_num]:
                route_directions[route_num].append(direction)
    
    # 转换为列表并排序
    routes_list = []
    for route_id in sorted(routes.keys()):
        route_data = routes[route_id]
        route_data['id'] = route_id
        routes_list.append(route_data)
    
    print(f"\n✓ 提取了 {len(routes_list)} 条unique Bus Routes")
    print(f"  示例routes: {routes_list[:10]}")
    
    # 保存routes数据
    output_routes = BASE_DIR.parent / 'bus_routes_detailed.json'
    routes_output = {
        'routes': routes_list,
        'summary': {
            'total_routes': len(routes_list),
            'total_directions': sum(len(d) for d in route_directions.values())
        }
    }
    
    with open(output_routes, 'w', encoding='utf-8') as f:
        json.dump(routes_output, f, ensure_ascii=False, indent=2)
    
    size = output_routes.stat().st_size / (1024 * 1024)
    print(f"\n✓ 已保存: {output_routes}")
    print(f"  文件大小: {size:.2f} MB")
else:
    print(f"✗ 找不到: {routes_path}")

# ========== 完成 ==========
print("\n" + "="*80)
print("【处理完成】")
print("="*80)
print(f"\n✓ 生成的文件:")
print(f"  1. LSOA_aggregated_PTAL_stats_2023_enhanced.geojson")
print(f"     - 包含每个LSOA区域内各交通线的站点计数")
print(f"  2. bus_routes_detailed.json")
print(f"     - 包含所有公交线路数据")
print(f"\nHTML现在可以加载这些增强数据！")
print("="*80)
