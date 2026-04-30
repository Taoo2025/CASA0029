# London PTAL Resilience Map

Interactive web application for analyzing public transport accessibility resilience in London.https://taoo2025.github.io/CASA0029/

## Features

- Cancel one or more transport routes and see real-time impact
- Recalculate accessibility using AI (Accessibility Index)
- Compare baseline vs disrupted scenarios side-by-side
- 100m grid cell analysis with route-specific impacts
- LSOA context layer
- Route-by-route impact visualization
- White→Red disruption heatmap (white: minimal, red: critical)

## Quick Start

### Step 1: Get Mapbox Token
- Sign up free at https://account.mapbox.com/auth/signup/
- Copy your access token

### Step 2: Setup
```bash
cd E:\CASA\CASA0029_UDV\HTML
git pull  # Get latest code
```

### Step 3: Edit Token in HTML
Open `London_PTAL_Accessibility_Map.html` and find line ~771:
```javascript
mapboxgl.accessToken = 'YOUR_MAPBOX_TOKEN_HERE';
```
Replace with your actual token from step 1.

### Step 4: Run Local Server
```bash
python -m http.server 8080
```
Then open: `http://localhost:8080/London_PTAL_Accessibility_Map.html`


## Data Files

- `route_grid_impacts_osm_network.json` - 540 routes impact data
- `grid_ai_chunks_osm_network/` - 64 grid batches (242 MB)
- `data_chunks_osm_network/` - 33 borough chunks (122 MB)
- `London_Stops_With_Routes.geojson` - 27,553 transit stops
- `route_lines.geojson` - 438 route geometries

## Browser Compatibility

- Chrome/Edge (recommended)
- Firefox
- Safari 14+

## File Structure

```
.
├── London_PTAL_Accessibility_Map.html  # Main application
├── serve_range.py                       # Local server (supports range requests)
├── *.json                               # Manifest and summary data
├── *.geojson                            # Geographic data
├── grid_ai_chunks_osm_network/          # Grid AI batches
├── data_chunks_osm_network/             # Borough network data
└── DATA/                                # Base grid layer
```

## Performance Notes

- Initial load: ~2-5 seconds (map visible with progress indicator)
- Route impact data: ~8 seconds (lazy-loaded, 12 MB)
- Grid calculations: Real-time (~100ms per route change)

## Optimization

For better performance with large datasets, consider:
- PMTiles conversion (see `convert_to_pmtiles.py`)
- Using `serve_range.py` for better HTTP streaming

See [ZOOM_FIX_GUIDE.md](ZOOM_FIX_GUIDE.md) for detailed options.

## Troubleshooting

### Map won't load
- Make sure Mapbox token is filled in (line ~771)
- Check browser console (F12) for errors
- Try incognito mode to clear cache

### Grid data disappears at certain zoom levels
**Status:** ✅ Fixed in latest version
- Grid is now visible at zoom levels 7-16
- Grid outlines appear from zoom 10+
- See [SOLUTION_SUMMARY.md](SOLUTION_SUMMARY.md) for technical details

### Map loading slowly
- Initial load with full data takes 2-5 seconds
- Try clearing browser cache
- Consider PMTiles conversion for faster rendering

## Documentation

- `SOLUTION_SUMMARY.md` - Complete fix summary
- `ZOOM_FIX_GUIDE.md` - Zoom level troubleshooting
- `QUICK_REFERENCE.md` - Quick test commands

## License

CASA project - University of London

---

**Need help?** Check GitHub Issues or contact the project team.
