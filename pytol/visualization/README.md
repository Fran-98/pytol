# Pytol Visualization

3D visualization for VTOL VR missions and terrain using PyVista.

## Installation

```bash
pip install pytol[viz]
```

This installs pytol with the optional PyVista dependency.

## Quick Start

### Visualizing Terrain

```python
from pytol.terrain import TerrainCalculator
from pytol.visualization import TerrainVisualizer

# Load terrain
tc = TerrainCalculator("hMap2")

# Visualize
viz = TerrainVisualizer(tc)
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
    map_id="hMap2"
)

# ... add units, objectives, etc ...

# Visualize
viz = MissionVisualizer(mission)
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

```python
# Faster rendering for large maps
viz = TerrainVisualizer(tc, mesh_resolution=128, drape_roads=False)
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
