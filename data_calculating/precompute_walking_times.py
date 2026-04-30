"""
Precompute walking times from all LSOA centroids to nearby stops
Store results in indexed JSON for fast web access
"""

import json
import networkx as nx
import numpy as np
from scipy.spatial import cKDTree
import pandas as pd
from collections import defaultdict
import time

print("=" * 80)
print("PRECOMPUTING WALKING TIMES FOR ALL LSOA AREAS")
print("=" * 80)

# ============================================================================
# 1. LOAD PRECOMPUTED NETWORK DATA
# ============================================================================
print("\n[1/5] Loading network graph...")

# Since the graph is huge (2M nodes), we'll use a sampling approach
# Load the stops and LSOA data instead

with open('London_Stops_With_Routes.geojson', 'r') as f:
    stops_data = json.load(f)

with open('London_LSOA_Centroids.geojson', 'r') as f:
    lsoa_data = json.load(f)

print(f"   ✓ Loaded {len(stops_data['features'])} stops")
print(f"   ✓ Loaded {len(lsoa_data['features'])} LSOA areas")

# ============================================================================
# 2. CREATE LOOKUP TABLES
# ============================================================================
print("\n[2/5] Creating spatial indexes...")

stops_list = []
stops_by_code = {}

for feature in stops_data['features']:
    props = feature['properties']
    coords = feature['geometry']['coordinates']
    stop_code = props['ATCOCode']
    
    stop_info = {
        'code': stop_code,
        'name': props['StopName'],
        'lon': coords[0],
        'lat': coords[1],
        'routes': props.get('routes', []),
        'route_count': len(props.get('routes', []))
    }
    stops_list.append(stop_info)
    stops_by_code[stop_code] = stop_info

# Build KDTree for stops
stops_coords = np.array([[s['lon'], s['lat']] for s in stops_list])
stops_tree = cKDTree(stops_coords)

lsoa_list = []
for feature in lsoa_data['features']:
    props = feature['properties']
    coords = feature['geometry']['coordinates']
    
    lsoa_info = {
        'code': props['LSOA_CODE'],
        'name': props['LSOA_NAME'],
        'lon': coords[0],
        'lat': coords[1],
        'lad': props['LAD_NAME']
    }
    lsoa_list.append(lsoa_info)

print(f"   ✓ Built KDTree with {len(stops_list)} stops")
print(f"   ✓ Built {len(lsoa_list)} LSOA areas")

# ============================================================================
# 3. HAVERSINE DISTANCE CALCULATION
# ============================================================================
def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in meters using Haversine formula"""
    R = 6371000  # Earth radius in meters
    rad = np.pi / 180
    dLat = (lat2 - lat1) * rad
    dLon = (lon2 - lon1) * rad
    a = np.sin(dLat/2)**2 + np.cos(lat1*rad) * np.cos(lat2*rad) * np.sin(dLon/2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    return R * c

def calculate_walking_time(distance_m, speed_kmh=4.8):
    """Calculate walking time in minutes"""
    speed_m_per_min = (speed_kmh * 1000) / 60
    return distance_m / speed_m_per_min

# ============================================================================
# 4. COMPUTE WALKING TIMES FOR EACH LSOA
# ============================================================================
print("\n[3/5] Computing walking times from LSOA to nearby stops...")

# Store results in a dictionary
walking_data = {}
stats = {
    'total_lsoa': len(lsoa_list),
    'total_stops': len(stops_list),
    'average_stops_per_lsoa': 0,
    'total_connections': 0
}

start_time = time.time()

for idx, lsoa in enumerate(lsoa_list):
    if (idx + 1) % 500 == 0:
        elapsed = time.time() - start_time
        print(f"   Processed {idx+1}/{len(lsoa_list)} LSOA areas ({elapsed:.1f}s)")
    
    lsoa_code = lsoa['code']
    lsoa_lon = lsoa['lon']
    lsoa_lat = lsoa['lat']
    
    # Find nearby stops (within 2km radius = ~0.018 degrees)
    nearby_indices = stops_tree.query_ball_point(
        [lsoa_lon, lsoa_lat],
        r=0.018,  # Approximately 2km
        workers=-1
    )
    
    stops_with_distance = []
    
    for stop_idx in nearby_indices:
        stop = stops_list[stop_idx]
        
        # Calculate distance
        distance = haversine_distance(
            lsoa_lat, lsoa_lon,
            stop['lat'], stop['lon']
        )
        
        # Calculate walking time
        walking_time = calculate_walking_time(distance, speed_kmh=4.8)
        
        stops_with_distance.append({
            'stop_code': stop['code'],
            'stop_name': stop['name'],
            'distance_m': round(distance, 1),
            'walking_time_min': round(walking_time, 1),
            'routes': stop['routes'],
            'route_count': stop['route_count']
        })
    
    # Sort by distance
    stops_with_distance.sort(key=lambda x: x['distance_m'])
    
    # Store result
    walking_data[lsoa_code] = {
        'lsoa_name': lsoa['name'],
        'lsoa_code': lsoa_code,
        'lad_name': lsoa['lad'],
        'center_lon': round(lsoa_lon, 6),
        'center_lat': round(lsoa_lat, 6),
        'nearby_stops': stops_with_distance[:100],  # Keep top 100 closest stops
        'total_stops_in_range': len(stops_with_distance),
        'speed_kmh': 4.8
    }
    
    stats['total_connections'] += len(stops_with_distance)

elapsed = time.time() - start_time
print(f"\n   ✓ Computed in {elapsed:.1f} seconds")

stats['average_stops_per_lsoa'] = stats['total_connections'] / stats['total_lsoa']

# ============================================================================
# 5. SAVE RESULTS
# ============================================================================
print("\n[4/5] Saving results...")

# Save full data as JSON
with open('walking_times_data.json', 'w') as f:
    json.dump(walking_data, f, indent=2)

print(f"   ✓ Saved walking_times_data.json ({len(walking_data)} LSOA areas)")

# Create a simplified index for quick lookups
index_data = {
    'version': '1.0',
    'generated': pd.Timestamp.now().isoformat(),
    'statistics': stats,
    'lsoa_index': {
        code: {
            'name': data['lsoa_name'],
            'lad': data['lad_name'],
            'stops_nearby': data['total_stops_in_range'],
            'closest_stop': data['nearby_stops'][0]['stop_name'] if data['nearby_stops'] else None,
            'closest_distance_m': data['nearby_stops'][0]['distance_m'] if data['nearby_stops'] else None
        }
        for code, data in walking_data.items()
    }
}

with open('walking_index.json', 'w') as f:
    json.dump(index_data, f, indent=2)

print(f"   ✓ Saved walking_index.json")

# ============================================================================
# 6. GENERATE STATISTICS
# ============================================================================
print("\n" + "=" * 80)
print("STATISTICS")
print("=" * 80)

distances = []
for lsoa_code, data in walking_data.items():
    if data['nearby_stops']:
        for stop in data['nearby_stops'][:10]:  # Take closest 10
            distances.append(stop['distance_m'])

if distances:
    print(f"\nDistance Statistics (straight-line, from all LSOA to nearby stops):")
    print(f"  Mean distance: {np.mean(distances):.0f}m")
    print(f"  Median distance: {np.median(distances):.0f}m")
    print(f"  Min distance: {np.min(distances):.0f}m")
    print(f"  Max distance: {np.max(distances):.0f}m")
    print(f"  Std deviation: {np.std(distances):.0f}m")

print(f"\nWalking Time Statistics (at 4.8 km/h = 80 m/min):")
walking_times = [d / 80 for d in distances]
print(f"  Mean walking time: {np.mean(walking_times):.1f} minutes")
print(f"  Median walking time: {np.median(walking_times):.1f} minutes")
print(f"  90th percentile: {np.percentile(walking_times, 90):.1f} minutes")

print(f"\nData Summary:")
print(f"  Total LSOA areas: {stats['total_lsoa']}")
print(f"  Total stops analyzed: {stats['total_stops']}")
print(f"  Total distance connections: {stats['total_connections']}")
print(f"  Average stops per LSOA (within 2km): {stats['average_stops_per_lsoa']:.1f}")

print(f"\n✓ Ready for Web Application!")
print(f"  Load 'walking_times_data.json' in your web app")
print(f"  Query by LSOA_CODE to get instant results")

print("\n" + "=" * 80)
