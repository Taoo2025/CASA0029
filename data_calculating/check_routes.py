#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json

with open('Bus_Routes__direction_of_travel_.geojson', 'r') as f:
    data = json.load(f)

print(f"总features: {len(data.get('features', []))}")

if data['features']:
    sample = data['features'][0]
    print(f"\n示例feature属性:")
    for k, v in list(sample['properties'].items())[:15]:
        if isinstance(v, str) and len(v) > 50:
            print(f"  {k}: {v[:50]}...")
        else:
            print(f"  {k}: {v}")
    
    print(f"\n几何类型: {sample['geometry']['type']}")
