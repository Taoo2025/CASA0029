"""
London Walking Accessibility System
- Load stops from Stops.csv
- Calculate LSOA centroids
- Map stops to bus routes
- Calculate walking time using OSM network
"""

import pandas as pd
import geopandas as gpd
import json
import numpy as np
from shapely.geometry import Point
from scipy.spatial import cKDTree
import warnings

warnings.filterwarnings('ignore')

print("=" * 80)
print("LONDON WALKING ACCESSIBILITY SYSTEM")
print("=" * 80)

# ============================================================================
# 1. LOAD AND PROCESS STOPS DATA
# ============================================================================
print("\n[1/5] Loading stops data...")
df_stops = pd.read_csv('DATA/Stops.csv', low_memory=False)

# Filter to London (using LSOA boundaries as reference)
lsoa = gpd.read_file('DATA/LSOA_London.shp')
london_bounds = lsoa.total_bounds  # [minx, miny, maxx, maxy] in EPSG:27700

# Convert LSOA bounds to WGS84 (approximate: London is roughly 51.3-51.7N, -0.5-0.3W)
london_bounds_wgs84 = [-0.5, 51.3, 0.3, 51.7]

# Filter stops to London bounds
df_london = df_stops[
    (df_stops['Latitude'] >= london_bounds_wgs84[1]) & 
    (df_stops['Latitude'] <= london_bounds_wgs84[3]) & 
    (df_stops['Longitude'] >= london_bounds_wgs84[0]) & 
    (df_stops['Longitude'] <= london_bounds_wgs84[2])
].copy()

print(f"   Total stops in CSV: {len(df_stops)}")
print(f"   London stops filtered: {len(df_london)}")

# Remove invalid coordinates
df_london = df_london[
    (df_london['Longitude'].notna()) & 
    (df_london['Latitude'].notna()) & 
    (df_london['Longitude'] != 0) & 
    (df_london['Latitude'] != 0)
].copy()

# Deduplicate: keep one stop per unique (CommonName, Longitude, Latitude)
df_london['lockey'] = df_london.apply(
    lambda r: f"{r['CommonName']}|{r['Longitude']:.5f},{r['Latitude']:.5f}", 
    axis=1
)
df_london = df_london.drop_duplicates(subset=['lockey']).copy()
df_london = df_london.rename(columns={'CommonName': 'StopName'})

print(f"   Unique stops after dedup: {len(df_london)}")
print(f"   Sample stops:\n{df_london[['ATCOCode', 'StopName', 'Longitude', 'Latitude']].head()}")

# Save to GeoJSON
stops_geojson = {
    'type': 'FeatureCollection',
    'features': []
}

for idx, row in df_london.iterrows():
    feature = {
        'type': 'Feature',
        'geometry': {
            'type': 'Point',
            'coordinates': [float(row['Longitude']), float(row['Latitude'])]
        },
        'properties': {
            'ATCOCode': str(row['ATCOCode']),
            'StopName': str(row['StopName']),
            'StopType': str(row['StopType']) if pd.notna(row['StopType']) else 'unknown',
            'Latitude': float(row['Latitude']),
            'Longitude': float(row['Longitude'])
        }
    }
    stops_geojson['features'].append(feature)

with open('London_Stops_Unified.geojson', 'w') as f:
    json.dump(stops_geojson, f)

print(f"   ✓ Saved {len(stops_geojson['features'])} stops to London_Stops_Unified.geojson")

# ============================================================================
# 2. CALCULATE LSOA CENTROIDS
# ============================================================================
print("\n[2/5] Calculating LSOA centroids...")

# Convert LSOA to WGS84
lsoa_wgs84 = lsoa.to_crs('EPSG:4326').copy()

# Calculate centroid
lsoa_wgs84['centroid_geom'] = lsoa_wgs84.geometry.centroid
lsoa_wgs84['centroid_lon'] = lsoa_wgs84['centroid_geom'].x
lsoa_wgs84['centroid_lat'] = lsoa_wgs84['centroid_geom'].y

print(f"   Total LSOA areas: {len(lsoa_wgs84)}")
print(f"   Sample centroids:\n{lsoa_wgs84[['lsoa21cd', 'lsoa21nm', 'centroid_lon', 'centroid_lat']].head()}")

# Save to GeoJSON
lsoa_geojson = {
    'type': 'FeatureCollection',
    'features': []
}

for idx, row in lsoa_wgs84.iterrows():
    feature = {
        'type': 'Feature',
        'geometry': {
            'type': 'Point',
            'coordinates': [float(row['centroid_lon']), float(row['centroid_lat'])]
        },
        'properties': {
            'LSOA_CODE': str(row['lsoa21cd']),
            'LSOA_NAME': str(row['lsoa21nm']),
            'LAD_CODE': str(row['lad22cd']),
            'LAD_NAME': str(row['lad22nm'])
        }
    }
    lsoa_geojson['features'].append(feature)

with open('London_LSOA_Centroids.geojson', 'w') as f:
    json.dump(lsoa_geojson, f)

print(f"   ✓ Saved {len(lsoa_geojson['features'])} LSOA centroids to London_LSOA_Centroids.geojson")

# ============================================================================
# 3. MAP STOPS TO ROUTES
# ============================================================================
print("\n[3/5] Mapping stops to bus routes...")

bus_routes = json.load(open('DATA/Bus_Routes__direction_of_travel_.geojson'))

# Create KDTree for fast spatial search
stops_coords = df_london[['Longitude', 'Latitude']].values
stops_tree = cKDTree(stops_coords)

# Map each stop to nearby routes (within 100m)
stops_routes_map = {}

for idx, row in df_london.iterrows():
    stop_id = str(row['ATCOCode'])
    stops_routes_map[stop_id] = []

# Check each route feature
route_count = 0
for feature in bus_routes['features']:
    props = feature['properties']
    route_name = props.get('ROUTE', 'Unknown')
    direction = props.get('DIRECTION', '')
    
    geom = feature['geometry']
    if geom['type'] == 'LineString':
        coords = geom['coordinates']
        # Check each coordinate in the route
        for coord in coords:
            lon, lat = coord
            # Find nearest stop
            dist, idx_list = stops_tree.query([lon, lat], k=1, distance_upper_bound=0.0015)  # ~150m in degrees
            if dist < 0.0015:  # ~150 meters
                stop_idx = idx_list
                stop_id = str(df_london.iloc[stop_idx]['ATCOCode'])
                route_key = f"{route_name}_{direction}"
                if route_key not in stops_routes_map[stop_id]:
                    stops_routes_map[stop_id].append(route_key)
    
    route_count += 1
    if route_count % 500 == 0:
        print(f"   Processed {route_count}/{len(bus_routes['features'])} routes...")

# Add routes to stops GeoJSON
updated_stops_geojson = {
    'type': 'FeatureCollection',
    'features': []
}

for feature in stops_geojson['features']:
    props = feature['properties']
    stop_id = props['ATCOCode']
    props['routes'] = stops_routes_map.get(stop_id, [])
    props['route_count'] = len(props['routes'])
    updated_stops_geojson['features'].append(feature)

with open('London_Stops_With_Routes.geojson', 'w') as f:
    json.dump(updated_stops_geojson, f)

# Summary
stops_with_routes = sum(1 for f in updated_stops_geojson['features'] if f['properties']['route_count'] > 0)
print(f"   ✓ Mapped routes to stops")
print(f"   Stops with at least 1 route: {stops_with_routes}/{len(updated_stops_geojson['features'])}")

# ============================================================================
# 4. SAVE CONFIGURATION FOR WEB APPLICATION
# ============================================================================
print("\n[4/5] Generating configuration for web app...")

config = {
    'stops': {
        'total': len(df_london),
        'geojson_file': 'London_Stops_With_Routes.geojson',
        'properties': ['ATCOCode', 'StopName', 'routes', 'route_count']
    },
    'lsoa': {
        'total': len(lsoa_wgs84),
        'geojson_file': 'London_LSOA_Centroids.geojson',
        'properties': ['LSOA_CODE', 'LSOA_NAME', 'LAD_NAME']
    },
    'walking': {
        'speed_kmh': 4.8,
        'speed_m_per_min': 80,
        'formula': 'walking_time_min = distance_m / 80'
    },
    'osm': {
        'status': 'ready_to_load',
        'note': 'OSM network will be loaded client-side or via OSRM API'
    }
}

with open('accessibility_config.json', 'w') as f:
    json.dump(config, f, indent=2)

print("   ✓ Saved accessibility_config.json")

# ============================================================================
# 5. SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"\n✓ London Stops: {len(df_london)} unique locations")
print(f"✓ LSOA Areas: {len(lsoa_wgs84)}")
print(f"✓ Stops mapped to routes: {stops_with_routes}")
print(f"\nGenerated files:")
print(f"  - London_Stops_Unified.geojson")
print(f"  - London_LSOA_Centroids.geojson")
print(f"  - London_Stops_With_Routes.geojson")
print(f"  - accessibility_config.json")
print(f"\nNext steps:")
print(f"  1. Load OSM network for routing (OSRM API or local)")
print(f"  2. Calculate shortest paths from LSOA centroids to stops")
print(f"  3. Render walking time isochrones on map")

print("\n" + "=" * 80)
