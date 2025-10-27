# Pytol Visualization

Visualization for VTOL VR missions and terrain with both 2D and 3D options.

## Installation Options

### 2D Visualization (Lightweight)
```bash
pip install pytol[viz-light]
```
Static top-down tactical images using matplotlib. Perfect for mission briefings and documentation.

### 3D Visualization (Interactive)
```bash
pip install pytol[viz]
```
Interactive 3D exploration using PyVista. Great for terrain analysis and mission development.

### Both Options
```bash
pip install pytol[viz] pytol[viz-light]
```

## Quick Start

### 2D Static Maps (Fast & Professional)

```python
from pytol import Mission, Map2DVisualizer, save_mission_map
from pytol.terrain import TerrainCalculator

# Create a mission
mission = Mission(
    scenario_name="Strike Mission",
    scenario_id="strike1", 
    description="Test mission",
    map_id="archipielago_1",
    vtol_directory=r"C:\Path\To\VTOL VR"
)
# ... add units, waypoints, objectives ...

# Generate clean professional overview (recommended)
viz = Map2DVisualizer(mission, figsize=(12, 12), dpi=150)
viz.save_mission_overview("mission_clean.png", clean_mode=True)

# Generate with terrain elevation
viz.save_mission_overview("mission_terrain.png", terrain_style='contour')

# Generate detailed terrain heatmap  
viz.save_terrain_overview("terrain_heatmap.png", style='heatmap')

# Generate spawn points detail for briefings
viz.save_spawn_points_detail("spawn_points.png", base_index=0)

# Quick convenience function
save_mission_map(mission, "quick_map.png", clean_mode=True)

# Terrain-only images
tc = TerrainCalculator("archipielago_1", vtol_directory=r"C:\Path\To\VTOL VR")
Map2DVisualizer(tc).save_terrain_overview("terrain_only.png", style='heatmap')
```

### 3D Interactive Exploration

```python
from pytol.terrain import TerrainCalculator
from pytol.visualization import TerrainVisualizer

# Load terrain
tc = TerrainCalculator("hMap2", verbose=False)

# Interactive 3D visualization
viz = TerrainVisualizer(
    tc,
    mesh_resolution=256,  # Terrain detail (default: 256)
    drape_roads=True,     # Drape roads on terrain (default: True)
    verbose=True          # Show rendering progress (default: True)
)
viz.show()
```

### Visualizing Missions

```python
from pytol import Mission
from pytol.visualization import MissionVisualizer

# Create or load a mission
mission = Mission(
    scenario_name="My Mission",
    scenario_id="my_mission",
    description="A test mission",
    map_id="hMap2",
    verbose=False  # Optional: suppress mission creation messages
)

# ... add units, objectives, etc ...

# Visualize
viz = MissionVisualizer(
    mission,
    mesh_resolution=256,  # Terrain detail
    verbose=True          # Show visualization progress
)
viz.show()
```

## Features

### TerrainVisualizer

Displays:
- **Terrain mesh** with elevation coloring
- **City blocks** (green = spawnable, red = obstacles)
- **Static prefabs** (buildings, hangars, etc.)
- **Road network** (gray lines)
- **Bridges** (blue lines)

### MissionVisualizer

Displays everything from TerrainVisualizer plus:
- **Units** (blue = allied, red = enemy)
- **Waypoints** (yellow markers)
- **Paths** (cyan lines)
- **Mission info** in console

## Controls

- **Mouse**: Click and drag to rotate
- **Scroll**: Zoom in/out
- **Q**: Exit visualization

## Performance Tips

- Lower `mesh_resolution` for faster rendering (default: 256)
- Set `drape_roads=False` to skip road draping on terrain
- Set `verbose=False` to suppress progress messages for cleaner output

```python
# Faster rendering for large maps
viz = TerrainVisualizer(
    tc, 
    mesh_resolution=128, 
    drape_roads=False,
    verbose=False  # Silent mode
)
viz.show()
```

## Examples

See `examples/example_visualization.py` for a complete demonstration.

## Requirements

- Python 3.7+
- pyvista
- numpy
- scipy

All dependencies are automatically installed with `pip install pytol[viz]`
