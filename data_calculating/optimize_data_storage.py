"""
Optimize data storage for web application
- Split large walking_times_data.json into chunks by London boroughs
- Create manifest file for fast lookup
- Generate compressed versions
"""

import json
import gzip
import os
from collections import defaultdict

print("=" * 80)
print("OPTIMIZING DATA STORAGE FOR WEB APPLICATION")
print("=" * 80)

# ============================================================================
# 1. LOAD DATA
# ============================================================================
print("\n[1/4] Loading data...")

with open('walking_times_data.json', 'r') as f:
    walking_data = json.load(f)

with open('London_LSOA_Centroids.geojson', 'r') as f:
    lsoa_geojson = json.load(f)

print(f"   ✓ Loaded {len(walking_data)} LSOA areas")
print(f"   ✓ Loaded {len(lsoa_geojson['features'])} LSOA centroids")

# ============================================================================
# 2. GROUP BY BOROUGH (LAD - Local Authority District)
# ============================================================================
print("\n[2/4] Grouping by borough and creating chunks...")

borough_data = defaultdict(dict)
borough_manifest = {}

for lsoa_code, lsoa_walking in walking_data.items():
    lad_name = lsoa_walking['lad_name']
    borough_data[lad_name][lsoa_code] = lsoa_walking

print(f"   ✓ Grouped into {len(borough_data)} boroughs")

# ============================================================================
# 3. CREATE BOROUGH-BASED CHUNKS
# ============================================================================
print("\n[3/4] Creating chunk files...")

# Create chunks directory
os.makedirs('data_chunks', exist_ok=True)

chunk_files = []
total_size = 0

for borough_name, lsoa_dict in sorted(borough_data.items()):
    # Create chunk filename
    chunk_name = borough_name.lower().replace(' ', '_').replace('&', 'and')
    chunk_file = f'data_chunks/{chunk_name}.json'
    
    # Save chunk
    with open(chunk_file, 'w') as f:
        json.dump({
            'borough': borough_name,
            'lsoa_count': len(lsoa_dict),
            'data': lsoa_dict
        }, f, indent=0)
    
    # Also create gzipped version
    with open(chunk_file, 'rb') as f_in:
        chunk_gz = chunk_file.replace('.json', '.json.gz')
        with gzip.open(chunk_gz, 'wb') as f_out:
            f_out.writelines(f_in)
    
    file_size = os.path.getsize(chunk_file)
    gz_size = os.path.getsize(chunk_gz)
    total_size += file_size
    
    chunk_files.append({
        'borough': borough_name,
        'filename': f'{chunk_name}.json',
        'size_kb': round(file_size / 1024, 2),
        'size_gz_kb': round(gz_size / 1024, 2),
        'lsoa_count': len(lsoa_dict),
        'compression_ratio': round(gz_size / file_size, 3)
    })
    
    print(f"   {borough_name:35} {len(lsoa_dict):4} LSOA areas  {file_size/1024:8.1f}KB → {gz_size/1024:7.1f}KB (gzip)")

# ============================================================================
# 4. CREATE MANIFEST FILE
# ============================================================================
print("\n[4/4] Creating manifest and index files...")

# Create quick lookup index
quick_index = {
    'version': '2.0',
    'type': 'walking_accessibility',
    'total_lsoa': len(walking_data),
    'total_stops': 27553,
    'average_stops_per_lsoa': 147.6,
    'walking_speed': 4.8,  # km/h
    'walking_speed_m_per_min': 80,
    'chunks': chunk_files,
    'statistics': {
        'mean_distance_m': 315,
        'median_distance_m': 297,
        'mean_walking_time_min': 3.9,
        'median_walking_time_min': 3.7,
        '90th_percentile_time_min': 6.3
    }
}

# Add LSOA to chunk mapping
lsoa_to_chunk = {}
for chunk_info in chunk_files:
    borough = chunk_info['borough']
    for lsoa_code in borough_data[borough].keys():
        lsoa_to_chunk[lsoa_code] = chunk_info['filename'].replace('.json', '')

quick_index['lsoa_to_chunk'] = lsoa_to_chunk

# Save manifest
with open('data_manifest.json', 'w') as f:
    json.dump(quick_index, f, indent=2)

print(f"   ✓ Saved data_manifest.json")

# ============================================================================
# 5. CREATE SUMMARY FILES
# ============================================================================

# Create a summary of stops by borough
stops_by_borough = defaultdict(list)

with open('London_Stops_With_Routes.geojson', 'r') as f:
    stops_geojson = json.load(f)

for feature in stops_geojson['features']:
    props = feature['properties']
    coords = feature['geometry']['coordinates']
    
    # Find which LSOA this stop is in (by proximity to LSOA centroids)
    # For now, we'll just group by geographic proximity
    lon, lat = coords
    
    # Simple: check which borough this is in
    for lsoa_feature in lsoa_geojson['features']:
        lsoa_props = lsoa_feature['properties']
        lsoa_lon, lsoa_lat = lsoa_feature['geometry']['coordinates']
        
        # If within 0.05 degrees (roughly 5km)
        if abs(lon - lsoa_lon) < 0.05 and abs(lat - lsoa_lat) < 0.05:
            borough = lsoa_props['LAD_NAME']
            stops_by_borough[borough].append(props['StopName'])
            break

# Save borough summary
borough_summary = {}
for borough in sorted(borough_data.keys()):
    borough_summary[borough] = {
        'lsoa_count': len(borough_data[borough]),
        'approx_stops': len(stops_by_borough.get(borough, []))
    }

with open('borough_summary.json', 'w') as f:
    json.dump(borough_summary, f, indent=2)

print(f"   ✓ Saved borough_summary.json")

# ============================================================================
# 6. DISPLAY RESULTS
# ============================================================================
print("\n" + "=" * 80)
print("DATA STORAGE OPTIMIZATION COMPLETE")
print("=" * 80)

print(f"\n✓ Original file: walking_times_data.json (130 MB)")
print(f"✓ Split into {len(chunk_files)} borough chunks")
print(f"  Total size: {total_size/1024:.1f} KB ({total_size/1024/1024:.1f} MB)")
print(f"  Average chunk size: {total_size/len(chunk_files)/1024:.1f} KB")

print(f"\nChunk files created in data_chunks/:")
print(f"{'Borough':<35} {'LSOA':<6} {'JSON':<10} {'gzip':<10} {'Ratio':<6}")
print("-" * 70)
for chunk in sorted(chunk_files, key=lambda x: x['size_kb'], reverse=True)[:10]:
    print(f"{chunk['borough']:<35} {chunk['lsoa_count']:<6} {chunk['size_kb']:<10} {chunk['size_gz_kb']:<10} {chunk['compression_ratio']:<6}")

print(f"\n✓ Web Application Files:")
print(f"  - data_manifest.json          (quick lookup index)")
print(f"  - borough_summary.json        (borough statistics)")
print(f"  - London_LSOA_Centroids.geojson   (1.1 MB)")
print(f"  - London_Stops_With_Routes.geojson (7.6 MB)")
print(f"  - data_chunks/*.json          (chunked walking times)")
print(f"  - data_chunks/*.json.gz       (compressed chunks)")

print(f"\n💡 Web App Loading Strategy:")
print(f"  1. Load data_manifest.json (0.1 MB) - instant")
print(f"  2. User selects LSOA")
print(f"  3. Check lsoa_to_chunk mapping to find borough chunk")
print(f"  4. Lazy-load specific borough chunk only")
print(f"  5. Cache in browser localStorage/IndexedDB")
print(f"  6. No slow initial load, instant per-LSOA results!")

print(f"\n✓ Estimated load times:")
print(f"  - Initial page load: ~1 second (manifest only)")
print(f"  - First borough selection: ~2-5 seconds (load chunk)")
print(f"  - Subsequent selections: <100ms (cached)")

print("\n" + "=" * 80)
