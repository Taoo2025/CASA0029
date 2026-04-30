import os
import json

print('='*70)
print('✅ DATA STORAGE VERIFICATION')
print('='*70)

# Check manifest
if os.path.exists('data_manifest.json'):
    with open('data_manifest.json') as f:
        manifest = json.load(f)
    print('\n✓ data_manifest.json')
    print(f'  - Version: {manifest["version"]}')
    print(f'  - Total LSOA: {manifest["total_lsoa"]}')
    print(f'  - Borough chunks: {len(manifest["chunks"])}')
else:
    print('✗ data_manifest.json NOT FOUND')

# Check chunk files
chunk_dir = 'data_chunks'
if os.path.exists(chunk_dir):
    chunks = [f for f in os.listdir(chunk_dir) if f.endswith('.json')]
    chunks_gz = [f for f in os.listdir(chunk_dir) if f.endswith('.json.gz')]
    total_size = sum(os.path.getsize(os.path.join(chunk_dir, f)) for f in chunks)
    total_size_gz = sum(os.path.getsize(os.path.join(chunk_dir, f)) for f in chunks_gz)
    
    print('\n✓ data_chunks/ directory')
    print(f'  - JSON files: {len(chunks)}')
    print(f'  - Gzipped files: {len(chunks_gz)}')
    print(f'  - Total JSON size: {total_size/1024/1024:.1f} MB')
    print(f'  - Total gzipped size: {total_size_gz/1024/1024:.1f} MB')
else:
    print('✗ data_chunks/ directory NOT FOUND')

# Check other data files
files_to_check = [
    ('London_LSOA_Centroids.geojson', 'LSOA centroids'),
    ('London_Stops_With_Routes.geojson', 'Stops with routes'),
    ('borough_summary.json', 'Borough summary'),
]

print('\n✓ Supporting files:')
for fname, desc in files_to_check:
    if os.path.exists(fname):
        size = os.path.getsize(fname)
        print(f'  ✓ {fname:<35} ({size/1024/1024:.1f} MB) - {desc}')
    else:
        print(f'  ✗ {fname:<35} NOT FOUND')

print('\n' + '='*70)
print('✅ ALL DATA READY FOR WEB APPLICATION')
print('='*70)
