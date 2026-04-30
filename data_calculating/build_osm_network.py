"""
London Walking Accessibility with OSM Network Routing
- Load OSM road network from shapefile
- Build network graph
- Calculate true walking distances from LSOA centroids to stops
"""

import geopandas as gpd
import pandas as pd
import json
import networkx as nx
from shapely.geometry import Point, LineString
from scipy.spatial import cKDTree
import numpy as np
import warnings

warnings.filterwarnings('ignore')

print("=" * 80)
print("BUILDING OSM NETWORK GRAPH FOR ROUTING")
print("=" * 80)

# ============================================================================
# 1. LOAD OSM NETWORK
# ============================================================================
print("\n[1/4] Loading OSM road network...")

try:
    osm_roads = gpd.read_file('DATA/greater-london-260427-free.shp/gis_osm_roads_free_1.shp')
    print(f"   ✓ Loaded OSM road network: {len(osm_roads)} road segments")
    print(f"   Columns: {osm_roads.columns.tolist()}")
    print(f"   CRS: {osm_roads.crs}")
except Exception as e:
    print(f"   Error: {e}")
    print("   Trying alternative file...")
    import os
    shapedir = 'DATA/greater-london-260427-free.shp'
    shapefiles = [f for f in os.listdir(shapedir) if f.endswith('.shp')]
    print(f"   Available shapefiles: {shapefiles}")
    if shapefiles:
        osm_roads = gpd.read_file(f'{shapedir}/{shapefiles[0]}')
        print(f"   ✓ Loaded: {shapefiles[0]}")

# ============================================================================
# 2. BUILD NETWORK GRAPH FROM OSM DATA
# ============================================================================
print("\n[2/4] Building network graph...")

G = nx.MultiDiGraph()

# Convert to WGS84 if needed
if osm_roads.crs != 'EPSG:4326':
    osm_roads = osm_roads.to_crs('EPSG:4326')

node_id = 0
node_coords = {}  # Map node_id to (lon, lat)
coord_to_nodeid = {}  # Map (lon, lat) to node_id

# Extract nodes and edges
for idx, road in osm_roads.iterrows():
    geom = road.geometry
    
    if geom.is_empty:
        continue
    
    if geom.geom_type == 'LineString':
        coords = list(geom.coords)
    elif geom.geom_type == 'MultiLineString':
        # Skip multilinestrings for now
        continue
    else:
        continue
    
    # Add nodes and edges
    for i in range(len(coords) - 1):
        coord1 = tuple(coords[i])
        coord2 = tuple(coords[i + 1])
        
        # Get or create node IDs
        if coord1 not in coord_to_nodeid:
            coord_to_nodeid[coord1] = node_id
            node_coords[node_id] = coord1
            G.add_node(node_id, pos=coord1)
            node_id += 1
        
        if coord2 not in coord_to_nodeid:
            coord_to_nodeid[coord2] = node_id
            node_coords[node_id] = coord2
            G.add_node(node_id, pos=coord2)
            node_id += 1
        
        u = coord_to_nodeid[coord1]
        v = coord_to_nodeid[coord2]
        
        # Calculate distance (Haversine)
        lat1, lon1 = coord1[1], coord1[0]
        lat2, lon2 = coord2[1], coord2[0]
        R = 6371000  # Earth radius in meters
        rad = np.pi / 180
        dLat = (lat2 - lat1) * rad
        dLon = (lon2 - lon1) * rad
        a = np.sin(dLat/2)**2 + np.cos(lat1*rad) * np.cos(lat2*rad) * np.sin(dLon/2)**2
        c = 2 * np.arcsin(np.sqrt(a))
        distance = R * c
        
        # Add edge with distance as weight
        G.add_edge(u, v, weight=distance)

print(f"   ✓ Built network with {len(G.nodes)} nodes and {len(G.edges)} edges")

# ============================================================================
# 3. LOAD STOPS AND LSOA DATA
# ============================================================================
print("\n[3/4] Loading stops and LSOA data...")

# Load stops
with open('London_Stops_With_Routes.geojson', 'r') as f:
    stops_data = json.load(f)

stops_coords = {}  # Map ATCOCode to (lon, lat, stop_name)
for feature in stops_data['features']:
    props = feature['properties']
    coords = feature['geometry']['coordinates']
    stops_coords[props['ATCOCode']] = {
        'lon': coords[0],
        'lat': coords[1],
        'name': props['StopName'],
        'routes': props.get('routes', [])
    }

# Load LSOA centroids
with open('London_LSOA_Centroids.geojson', 'r') as f:
    lsoa_data = json.load(f)

lsoa_coords = {}  # Map LSOA_CODE to (lon, lat)
for feature in lsoa_data['features']:
    props = feature['properties']
    coords = feature['geometry']['coordinates']
    lsoa_coords[props['LSOA_CODE']] = {
        'lon': coords[0],
        'lat': coords[1],
        'name': props['LSOA_NAME'],
        'lad': props['LAD_NAME']
    }

print(f"   ✓ Loaded {len(stops_coords)} stops")
print(f"   ✓ Loaded {len(lsoa_coords)} LSOA areas")

# ============================================================================
# 4. BUILD NEAREST NODE LOOKUP FOR FAST ROUTING
# ============================================================================
print("\n[4/4] Building spatial index...")

# Create KDTree for fast nearest node lookup
node_positions = np.array([node_coords[n] for n in sorted(G.nodes)])
tree = cKDTree(node_positions)
sorted_nodes = sorted(G.nodes)

print(f"   ✓ Built spatial index with {len(node_positions)} nodes")

# ============================================================================
# 5. CALCULATE WALKING TIMES FOR SAMPLE LSOA AND STOPS
# ============================================================================
print("\n" + "=" * 80)
print("SAMPLE: Calculate walking times from first LSOA to nearby stops")
print("=" * 80)

def find_nearest_node(lon, lat):
    """Find nearest network node to given coordinates"""
    dist, idx = tree.query([lon, lat], k=1, distance_upper_bound=0.01)  # ~1km
    if dist < 0.01:
        return sorted_nodes[idx]
    return None

def shortest_path_distance(start_node, end_node):
    """Calculate shortest path distance using Dijkstra"""
    try:
        path_length = nx.shortest_path_length(G, start_node, end_node, weight='weight')
        return path_length
    except nx.NetworkXNoPath:
        return None
    except:
        return None

# Sample: Take first LSOA
sample_lsoa_code = list(lsoa_coords.keys())[0]
sample_lsoa = lsoa_coords[sample_lsoa_code]

print(f"\nSample LSOA: {sample_lsoa['name']} ({sample_lsoa_code})")
print(f"Location: ({sample_lsoa['lon']:.4f}, {sample_lsoa['lat']:.4f})")

# Find nearest network node to LSOA
lsoa_node = find_nearest_node(sample_lsoa['lon'], sample_lsoa['lat'])
if lsoa_node is None:
    print("ERROR: Could not find network node near LSOA")
else:
    print(f"✓ Found nearest network node: {lsoa_node}")
    
    # Calculate distances to nearby stops
    walking_results = []
    
    for stop_code, stop in list(stops_coords.items())[:50]:  # Test with first 50 stops
        stop_node = find_nearest_node(stop['lon'], stop['lat'])
        
        if stop_node is None:
            continue
        
        # Calculate shortest path distance
        distance = shortest_path_distance(lsoa_node, stop_node)
        
        if distance is not None:
            # Calculate walking time: 4.8 km/h = 80 m/min
            walking_time_min = distance / 80
            walking_results.append({
                'stop_code': stop_code,
                'stop_name': stop['name'],
                'distance': distance,
                'walking_time': walking_time_min,
                'routes': len(stop['routes'])
            })
    
    # Sort by distance
    walking_results.sort(key=lambda x: x['distance'])
    
    print(f"\n✓ Calculated network distances to {len(walking_results)} stops")
    print(f"\nClosest stops (network distance):")
    print(f"{'Stop Name':<40} {'Distance (m)':<15} {'Walking Time':<15}")
    print("=" * 70)
    
    for result in walking_results[:10]:
        time_min = result['walking_time']
        if time_min < 1:
            time_str = f"{int(time_min*60)}s"
        else:
            time_str = f"{int(time_min)}min"
        print(f"{result['stop_name']:<40} {result['distance']:>10.0f}m {time_str:>14}")

# ============================================================================
# 6. SAVE NETWORK DATA FOR WEB APP
# ============================================================================
print("\n" + "=" * 80)
print("SAVING NETWORK DATA")
print("=" * 80)

network_config = {
    'nodes': len(G.nodes),
    'edges': len(G.edges),
    'coverage': {
        'stops': len(stops_coords),
        'lsoa': len(lsoa_coords)
    },
    'walking_parameters': {
        'speed_kmh': 4.8,
        'speed_m_per_min': 80,
        'formula': 'walking_time_min = network_distance_m / 80'
    },
    'notes': [
        'Network graph built from OSM shapefile',
        'Distances calculated using Dijkstra shortest path',
        'Haversine formula used for coordinate conversion'
    ]
}

with open('network_config.json', 'w') as f:
    json.dump(network_config, f, indent=2)

print(f"✓ Saved network_config.json")
print(f"\nNetwork Ready for Real-time Analysis!")
print(f"- {len(G.nodes)} network nodes")
print(f"- {len(stops_coords)} bus stops")
print(f"- {len(lsoa_coords)} LSOA areas")
print(f"- Walking speed: 4.8 km/h (80 m/min)")

print("\n" + "=" * 80)
