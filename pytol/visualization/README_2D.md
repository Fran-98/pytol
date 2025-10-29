# 2D Mission Visualization

Professional static image generation for VTOL VR missions using matplotlib. Create beautiful top-down tactical maps perfect for mission briefings, documentation, and analysis. Features both clean professional overview maps and detailed terrain visualizations.

## Installation

```bash
pip install pytol[viz-light]
```

This installs matplotlib for 2D visualization without the heavier PyVista dependency.

## Quick Start

### Clean Mission Overview (Recommended)

```python
from pytol import Mission, Map2DVisualizer

# Create or load a mission
mission = Mission(
    scenario_name="Strike Mission",
    scenario_id="strike_001", 
    description="A tactical strike mission",
    map_id="archipielago_1",
    vtol_directory=r"C:\Path\To\VTOL VR"
)

# ... add units, waypoints, objectives ...

# Create 2D visualizer
viz = Map2DVisualizer(mission, figsize=(12, 12), dpi=150)

# Save clean mission overview (professional look, small file size)
viz.save_mission_overview("mission_clean.png", clean_mode=True)

# Save with terrain elevation details
viz.save_mission_overview("mission_terrain.png", terrain_style='contour')

# Save terrain heatmap 
viz.save_terrain_overview("terrain_heatmap.png", style='heatmap')

# Save spawn points detail for pilot briefings
viz.save_spawn_points_detail("spawn_points.png", base_index=0)
```

## Lightweight Pillow visualizer

For quick previews, web-friendly thumbnails or environments where matplotlib
is not available, pytol provides a very small Pillow-based visualizer:

```python
from pytol.visualization import MapPillowVisualizer, save_mission_map

# Create visualizer for a mission or TerrainCalculator
viz = MapPillowVisualizer(mission_or_terrain, size=(1024, 1024), flip_x=False, flip_y=True)

# By default the Pillow visualizer returns a PIL Image (no file written):
img = viz.save_mission_overview()

# To write to disk set save=True and provide a filename
img = viz.save_mission_overview(filename='overview.png', save=True)

# Convenience helper also returns the PIL Image (pass save=True to write file):
img = save_mission_map(mission, filename='overview.png', save=True)
```

Key behaviors:
- Returns: PIL.Image.Image object (always). Use `save=True` + `filename` to persist.
- City overlay: uses the original `height.png` G channel (from the TerrainCalculator)
    to mark city pixels. This preserves the exact pixel locations that appear as
    city on the original heightmap — city pixels are rendered as grey tiles.
- Roads: rendered as outlined polylines with endpoint caps so short segments
    remain visible at small sizes.
- Flips: pass `flip_x`/`flip_y` when constructing `MapPillowVisualizer` or use the
    helper parameters to match editor/map coordinate handedness.
- Markers: unit/waypoint/base icons have narrow black outlines for legibility.

This visualizer is intentionally lightweight and aimed at quick previews and
web/export usage. For publication-quality maps, prefer `Map2DVisualizer`.

### Terrain-Only View

```python
from pytol import TerrainCalculator, Map2DVisualizer

# Load terrain data
tc = TerrainCalculator("hMap2")

# Create visualizer
viz = Map2DVisualizer(tc, figsize=(10, 10))

# Save terrain overview
viz.save_terrain_overview("terrain.png", style='contour')
```

### Convenience Function

```python
from pytol import save_mission_map

# Quick mission overview
save_mission_map(mission, "overview.png", style='mission_overview')

# Quick terrain view
save_mission_map(terrain_calculator, "terrain.png", style='terrain_only')

# Spawn points detail
save_mission_map(mission, "spawns.png", style='spawn_points', base_index=0)
```

## Visualization Layers

The 2D visualizer combines multiple data layers:

### Terrain Layer
- **Contour style**: Elevation contours with color-coded height
- **Heatmap style**: Smooth elevation coloring
- Automatic elevation range detection and color mapping

### City Blocks
- **Green rectangles**: Spawnable building surfaces (rooftops, etc.)
- **Red rectangles**: Obstacle buildings
- Based on procedural city data from map

### Road Network
- **Dark gray lines**: Road segments and intersections
- Follows actual map road data

### Static Prefabs
- **Gold squares**: Airbases with labels (airbase1, airbase2, etc.)
- **Annotations**: Prefab type labels

### Units (Mission Data)
- **Blue circles**: Allied units with facing arrows
- **Red circles**: Enemy units with facing arrows  
- **Gray circles**: Neutral units
- Arrows show unit orientation (yaw)

### Waypoints & Paths
- **Orange triangles**: Waypoints with sequential numbers
- **Dashed orange lines**: Flight paths connecting waypoints

### Objectives
- **Purple stars**: Mission objectives
- **Text boxes**: Objective names and descriptions
- Positioned at associated waypoints or target locations

### Spawn Points Detail
- **Green circles**: Hangar spawn points
- **Blue squares**: Helipad spawn points
- **Orange triangles**: Large aircraft spawns
- **Purple stars**: Reference points (runways, towers, barracks)
- **Arrows**: Spawn point orientations
- **Focus view**: 2km radius around selected airbase

## Configuration Options

### Map2DVisualizer Parameters

```python
viz = Map2DVisualizer(
    mission_or_terrain,       # Mission or TerrainCalculator
    figsize=(12, 12),         # Figure size in inches (width, height)
    dpi=150,                  # Image resolution (dots per inch)
    verbose=True              # Print progress messages
)
```

### Terrain Styles

```python
# Contour lines with elevation coloring (default)
viz.save_mission_overview("map.png", terrain_style='contour')

# Smooth heatmap coloring
viz.save_mission_overview("map.png", terrain_style='heatmap')

# Clean mode: No terrain heightmap for professional appearance
viz.save_mission_overview("map.png", clean_mode=True)
```

### Clean Mode (Recommended)

Clean mode removes terrain elevation clutter while preserving essential infrastructure:

**✅ Included in clean mode:**
- Roads and intersections
- City blocks and buildings  
- Airbases and static objects
- Units with team identification
- Waypoints and flight paths
- Mission objectives

**❌ Removed in clean mode:**
- Terrain elevation contours
- Height coloring and shading
- Elevation colorbar

**Benefits:**
- **Professional appearance** - Clean, uncluttered maps perfect for briefings
- **Small file sizes** - Typically 50-100KB vs 200-500KB with terrain
- **High contrast** - Mission elements stand out clearly
- **Print friendly** - Excellent for black & white printing

### Color Scheme

The visualizer uses a tactical color scheme:

- **Terrain**: Green (low) to brown (high) elevation
- **Water**: Dark blue
- **Roads**: Dark gray
- **Cities**: Green (spawnable) / Red (obstacles)
- **Allied Units**: Blue
- **Enemy Units**: Red
- **Waypoints**: Orange
- **Objectives**: Purple
- **Airbases**: Gold

## Output Formats

All methods save PNG images by default. You can specify other formats:

```python
viz.save_mission_overview("map.pdf")    # PDF vector format
viz.save_mission_overview("map.svg")    # SVG vector format
viz.save_mission_overview("map.jpg")    # JPEG (smaller file)
```

## Performance & File Sizes

- **Typical image size**: 200-800 KB PNG files
- **Generation time**: 2-5 seconds for complex missions
- **Memory usage**: Minimal (much less than 3D visualization)
- **Dependencies**: Only matplotlib (lightweight)

## Working with Image Data (Bytes Methods)

For integration with PIL/Pillow, image processing, or web applications, the visualizer provides methods that return image data as bytes instead of saving to files:

### Get Image as Bytes

```python
from io import BytesIO
from PIL import Image

# Mission overview as bytes
viz = Map2DVisualizer(mission)
img_bytes = viz.get_mission_overview_bytes(clean_mode=True, format='PNG')

# Use with PIL/Pillow
img = Image.open(BytesIO(img_bytes))
img.show()  # Display
img.save("processed_mission.png")  # Save copy

# Process with PIL
rotated = img.rotate(45)
thumbnail = img.copy()
thumbnail.thumbnail((200, 200))
```

### Terrain Overview Bytes

```python
# Get terrain data for processing
terrain_bytes = viz.get_terrain_overview_bytes(style='heatmap', format='PNG')

# Convert to numpy array for analysis
from PIL import Image
import numpy as np

img = Image.open(BytesIO(terrain_bytes))
img_array = np.array(img)
print(f"Image shape: {img_array.shape}")  # (height, width, channels)
```

### Spawn Points Detail Bytes

```python
# Get spawn points for specific base
spawn_bytes = viz.get_spawn_points_detail_bytes(base_index=0, format='JPEG')

# Create composite images
from PIL import Image
img1 = Image.open(BytesIO(viz.get_mission_overview_bytes(clean_mode=True)))
img2 = Image.open(BytesIO(spawn_bytes))

# Side-by-side comparison
combined = Image.new('RGB', (img1.width + img2.width, max(img1.height, img2.height)))
combined.paste(img1, (0, 0))
combined.paste(img2, (img1.width, 0))
combined.save("mission_comparison.png")
```

### Supported Formats

All bytes methods support multiple image formats:

```python
# Different formats
png_bytes = viz.get_mission_overview_bytes(format='PNG')    # Default, lossless
jpg_bytes = viz.get_mission_overview_bytes(format='JPEG')   # Smaller files
pdf_bytes = viz.get_mission_overview_bytes(format='PDF')    # Vector format
svg_bytes = viz.get_mission_overview_bytes(format='SVG')    # Scalable vector
```

### Web Application Integration

```python
# Flask web app example
from flask import Flask, Response
from io import BytesIO

app = Flask(__name__)

@app.route('/mission/<mission_id>/map')
def get_mission_map(mission_id):
    mission = load_mission(mission_id)  # Your mission loading logic
    viz = Map2DVisualizer(mission)
    img_bytes = viz.get_mission_overview_bytes(clean_mode=True, format='PNG')
    
    return Response(img_bytes, mimetype='image/png')
```

### Memory Management

The bytes methods handle memory efficiently:

```python
# Memory is automatically cleaned up
img_bytes = viz.get_mission_overview_bytes()
print(f"Image size: {len(img_bytes)} bytes")

# For multiple images, consider processing in batches
missions = [mission1, mission2, mission3]
for i, mission in enumerate(missions):
    viz = Map2DVisualizer(mission)
    img_bytes = viz.get_mission_overview_bytes(clean_mode=True)
    
    # Process immediately to free memory
    process_image(img_bytes)
    # viz goes out of scope, memory freed
```

## Use Cases

### Mission Planning
- Overview of unit positions and terrain
- Waypoint validation and route planning
- Objective placement verification

### Documentation
- Mission briefing images
- Campaign documentation
- Tutorial materials

### Debugging
- Visual validation of unit placement
- Spawn point verification
- Terrain analysis

### Batch Processing
- Automated mission image generation
- Campaign overview creation
- Testing and validation workflows

## Integration with 3D Visualization

2D and 3D visualization can be used together:

```python
from pytol import Mission, Map2DVisualizer, MissionVisualizer

mission = Mission(...)  # Create mission

# Generate static overview for documentation
Map2DVisualizer(mission).save_mission_overview("briefing.png")

# Interactive 3D exploration
MissionVisualizer(mission).show()
```

## Procedural Mission Generator

The 2D visualization system integrates perfectly with the procedural mission engine:

```python
# Run the procedural mission generator
python generate_procedural_missions.py
```

This creates randomized missions and visualizes them automatically:
- **Random mission types**: Strike, CAS, SEAD, Transport, Intercept
- **Variable complexity**: 3-15 units, multiple waypoints and objectives  
- **Smart placement**: Units positioned on actual terrain features
- **Professional visualization**: Clean mission overviews and detailed terrain maps
- **Unique every time**: Different missions each run for variety

Generated files for each mission:
- `mission_clean.png` - Professional clean overview map
- `mission_full.png` - Full terrain with elevation (optional)
- `terrain.png` - Detailed terrain heatmap (optional) 
- `spawn_points.png` - Airbase spawn point details
- `mission_info.txt` - Complete mission briefing
- `mission.vts` - Flyable VTOL VR mission file

Perfect for testing the visualization system and seeing how procedural missions look!

## Examples

See `examples/example_2d_visualization.py` for a complete demonstration including:
- Mission creation with units and waypoints
- Multiple visualization styles
- Output file management
- Error handling

## Troubleshooting

### Import Errors
```python
# ImportError: 2D visualization requires matplotlib
pip install pytol[viz-light]
```

### Empty Images
- Check that mission has units/waypoints added
- Verify map data loaded correctly
- Use `verbose=True` to see processing messages

### Performance Issues
- Reduce `dpi` for faster generation
- Use smaller `figsize` for complex maps
- Consider 'heatmap' terrain style for large maps

### Missing Data
- Some maps may not have city/road data (normal)
- Missing spawn points indicate unsupported airbase types
- Use `terrain_only` style if mission data is incomplete