#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快速提取Bus Routes数据
"""

import json
from pathlib import Path

print("="*80)
print("【提取Bus Routes数据】")
print("="*80)

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "DATA"

# ========== 提取Bus Routes数据 ==========
print("\n【提取Bus Routes】")
print("="*80)

routes_path = DATA_DIR / "Bus_Routes__direction_of_travel_.geojson"

if routes_path.exists():
    print(f"\n加载: {routes_path}")
    with open(routes_path, 'r', encoding='utf-8') as f:
        routes_geojson = json.load(f)
    
    print(f"✓ 加载了 {len(routes_geojson['features'])} 个route features")
    
    # 提取unique routes
    routes = {}
    
    for feature in routes_geojson['features']:
        props = feature['properties']
        route_num = props.get('ROUTE', 'Unknown')
        status = props.get('STATUS', 'CURRENT')
        
        if status == 'CURRENT':  # 只保留CURRENT的路由
            if route_num not in routes:
                routes[route_num] = {
                    'id': route_num,
                    'name': f'Bus {route_num}',
                    'type': 'Bus Route',
                    'color': '#EF476F'  # 红色公交车
                }
    
    # 转换为列表并排序
    routes_list = []
    for route_id in sorted(routes.keys()):
        routes_list.append(routes[route_id])
    
    print(f"\n✓ 提取了 {len(routes_list)} 条unique Bus Routes")
    print(f"  示例: {[r['name'] for r in routes_list[:10]]}")
    
    # 保存routes数据
    output_routes = BASE_DIR.parent / 'bus_routes_detailed.json'
    routes_output = {
        'routes': routes_list,
        'summary': {
            'total_routes': len(routes_list)
        }
    }
    
    with open(output_routes, 'w', encoding='utf-8') as f:
        json.dump(routes_output, f, ensure_ascii=False, indent=2)
    
    size = output_routes.stat().st_size / (1024 * 1024)
    print(f"\n✓ 已保存: {output_routes}")
    print(f"  文件大小: {size:.2f} MB")
    print(f"  包含 {len(routes_list)} 条公交线路")
else:
    print(f"✗ 找不到: {routes_path}")

print("\n" + "="*80)
