import json
import pandas as pd
import geopandas as gpd
import os

print("=" * 80)
print("CHECKING DATA STRUCTURES")
print("=" * 80)

os.chdir('e:\\CASA\\CASA0029_UDV\\Final_project')

# Check Stops.csv
print("\n1. STOPS.CSV:")
df_stops = pd.read_csv('DATA/Stops.csv')
print(f"   Total stops: {len(df_stops)}")
print(f"   Key columns: ATCOCode, CommonName, Longitude, Latitude, StopType")
print(f"   Sample:\n{df_stops[['ATCOCode', 'CommonName', 'Longitude', 'Latitude', 'StopType']].head()}")

# Check LSOA boundaries
print("\n2. LSOA BOUNDARIES:")
lsoa = gpd.read_file('DATA/LSOA_London.shp')
print(f"   Total LSOA areas: {len(lsoa)}")
print(f"   Columns: {lsoa.columns.tolist()}")
print(f"   CRS: {lsoa.crs}")
print(f"   Bounds: {lsoa.total_bounds}")
lsoa_center = lsoa.geometry.centroid.head()
print(f"   Sample centroids:\n{lsoa_center}")

# Check if there's any route-stop mapping in GeoJSON
print("\n3. BUS ROUTES GEOJSON:")
try:
    bus_geom = json.load(open('DATA/Bus_Routes__direction_of_travel_.geojson'))
    print(f"   Total features: {len(bus_geom.get('features', []))}")
    if bus_geom.get('features'):
        f = bus_geom['features'][0]
        props = f.get('properties', {})
        print(f"   Sample properties keys: {list(props.keys())[:10]}")
        print(f"   Sample properties: {props}")
except Exception as e:
    print(f"   Error: {e}")

print("\n" + "=" * 80)
