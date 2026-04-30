import json
import pandas as pd
import geopandas as gpd

print("=" * 80)
print("CHECKING DATA STRUCTURES")
print("=" * 80)

# Check bus_routes_detailed.json
print("\n1. BUS ROUTES DETAILED:")
try:
    data = json.load(open('../bus_routes_detailed.json'))
except:
    data = {}
print(f"   Total routes: {len(data.get('routes', []))}")
if data.get('routes'):
    r = data['routes'][0]
    print(f"   Sample route keys: {list(r.keys())}")
    print(f"   Sample: {r}")

# Check Stops.csv
print("\n2. STOPS.CSV:")
df_stops = pd.read_csv('DATA/Stops.csv', nrows=5)
print(f"   Total rows: {len(pd.read_csv('DATA/Stops.csv'))}")
print(f"   Columns: {df_stops.columns.tolist()}")
print(f"   Sample:\n{df_stops[['ATCOCode', 'CommonName', 'Longitude', 'Latitude', 'StopType']].head()}")

# Check LSOA boundaries
print("\n3. LSOA BOUNDARIES:")
try:
    lsoa = gpd.read_file('DATA/LSOA_London.shp')
    print(f"   Total LSOA areas: {len(lsoa)}")
    print(f"   Columns: {lsoa.columns.tolist()}")
    print(f"   Sample:\n{lsoa[['properties'] if 'properties' in lsoa.columns else lsoa.columns[0:3]].head()}")
    print(f"   CRS: {lsoa.crs}")
except Exception as e:
    print(f"   Error: {e}")

# Check if there's any route-stop mapping
print("\n4. LOOKING FOR ROUTE-STOP MAPPING:")
try:
    bus_geom = json.load(open('DATA/Bus_Routes__direction_of_travel_.geojson'))
    if bus_geom.get('features'):
        f = bus_geom['features'][0]
        print(f"   Sample feature keys: {list(f.get('properties', {}).keys())}")
        print(f"   Sample properties: {f.get('properties', {})}")
except Exception as e:
    print(f"   Error: {e}")

print("\n" + "=" * 80)
