# Pytol Examples

This directory contains example scripts demonstrating various features of the Pytol library.

## Core Examples

### Mission Creation
- `example_campaign_creation.py` - Create multi-mission campaigns
- `operation_pytol.py` - Complete tactical mission example

### Visualization Examples

#### 2D Static Maps (requires `pip install pytol[viz-light]`)
- `example_2d_visualization.py` - Static map generation with matplotlib
- `generate_procedural_missions.py` - **⭐ Procedural mission generator with 2D visualization**

#### 3D Interactive (requires `pip install pytol[viz]`)  
- `example_visualization.py` - Interactive 3D terrain and mission exploration
- `advanced_visualization_demo.py` - Advanced 3D visualization features

### Terrain Analysis
- `example_base_spawns.py` - Working with airbase spawn points
- Various analysis scripts in `../test_scripts/` directory

## Quick Start

### Generate Random Missions with Visualization

The most comprehensive example showing both procedural generation and 2D visualization:

```bash
# Install with 2D visualization
pip install pytol[viz-light]

```

### Basic 2D Visualization

```bash
python example_2d_visualization.py
```

Creates static mission maps showing terrain, units, waypoints, and objectives.

### Interactive 3D Exploration

```bash
pip install pytol[viz]
python example_visualization.py
```

Provides interactive 3D terrain and mission visualization.

## Requirements

Most examples require:
- VTOL VR installation (for map data)
- Custom maps (some examples use specific maps like `archipielago_1`)

Visualization examples require additional dependencies:
- 2D: `matplotlib` (install with `pip install pytol[viz-light]`)
- 3D: `pyvista` (install with `pip install pytol[viz]`)

## Map Setup

Examples reference VTOL VR installation at:
- Windows: `F:\SteamLibrary\steamapps\common\VTOL VR` (modify as needed)

Make sure you have the required custom maps in:
- `VTOL_VR_DIR/CustomMaps/map_name/`

Popular test maps:
- `archipielago_1`
- `hMap2`