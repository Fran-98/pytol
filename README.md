# Pytol - VTOL VR Mission Generation Library

<p align="center">
  <img src="https://raw.githubusercontent.com/Fran-98/pytol/refs/heads/main/docs/img/banner.png" alt="Pytol Banner">
</p>

[![PyPI version](https://badge.fury.io/py/pytol.svg)](https://pypi.org/project/pytol/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-FFDD00?style=flat&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/franman)

**Pytol** is a Python library for procedurally generating missions for the VR flight game **VTOL VR**. It provides tools to:

* Load and analyze VTOL VR custom map data (`.vtm` files).
* Calculate terrain height, surface normals, and object placements.
* Query map features for tactically relevant locations (e.g., hidden positions, observation posts, landing zones, choke points).
* Generate paths following terrain, roads, or avoiding threats.
* Construct and save valid VTOL VR mission files (`.vts`) and campaign files (`.vtc`).
* Create multiplayer missions and campaigns.

This enables automation in mission creation, allowing for more dynamic and complex scenarios. 🗺️✈️

<h3 align="center">
  <br>
  ⚠️ <strong>Disclaimer</strong> ⚠️
  <br><br>
  <em>This library is a work in progress, some features will not work as intended yet. Reading the Known Issues section is recommended.</em>
  <br>
</h3>

---

## Features

* **Terrain Analysis**: Accurately calculate height and surface normals based on map heightmaps.
* **Object Processing**: Identify and process procedural cities, roads, and static prefabs placed in the map editor.
* **Smart Placement**: Place units correctly on terrain, roads, or building rooftops.
* **Base Spawn Points**: Database of precise hangar, helipad, and facility locations for airbase prefabs - works on any map with these bases.
* **Tactical Queries**: High-level functions to find locations based on mission needs (e.g., line-of-sight checks, hidden spots, flat areas, choke points).
* **Pathfinding**: Generate road paths, terrain-following flight paths, and covert insertion routes.
* **Formation Generation**: Create points for standard unit formations (line, wedge, circle).
* **Mission Building**: Construct `.vts` files programmatically, adding units, objectives, triggers, waypoints, and briefing notes.
* **Campaign Support**: Create `.vtc` campaign files with multiple missions, including multiplayer campaigns.
* **Scenario Primitives**: Helpers for generating common scenario setups like CSAR or base defense.
* **2D Visualization** *(optional)*: Lightweight static mission maps and clean overviews using matplotlib - perfect for mission briefings.
* **3D Visualization** *(optional)*: Interactive visualization of terrain and complete missions using PyVista.

---

## Installation

There are two ways to install Pytol:

### 1. From PyPI (Recommended for users)

If you just want to use the library, you can install the latest stable release directly from the Python Package Index (PyPI):

```bash
pip install pytol
```

### Optional: Visualization Modules

For **2D visualization** (lightweight static maps with matplotlib):

```bash
pip install pytol[viz-light]
```

For **3D visualization** (interactive PyVista visualizations):

```bash
pip install pytol[viz]
```

For **both 2D and 3D** visualization:

```bash  
pip install pytol[all]
```

See [Visualization Guide](pytol/visualization/README.md) for details on both systems.

### 2. From Source (For development)


1. Clone the repo
```bash
git clone [https://github.com/Fran-98/pytol](https://github.com/Fran-98/pytol)  # Replace with your actual repo URL
cd Pytol
```

2. Install in editable mode

```bash
# This allows you to make changes to the source code and have them reflected immediately
pip install -e .
```

You also need to ensure the **VTOL VR game directory** is accessible on both methods, either by setting the `VTOL_VR_DIR` environment variable or by providing paths directly during initialization.


## Documentation

📚 **[Mission Creation Guide](docs/mission_creation.md)** - Complete guide to creating missions with Pytol  
🎯 **[Campaign Creation Guide](docs/campaign_creation.md)** - Create multi-mission campaigns and multiplayer missions  
🗺️ **[Terrain Behavior](docs/terrain_behavior.md)** - How terrain height sampling works and accuracy expectations  
🎨 **[Visualization Guide](pytol/visualization/README.md)** - Both 2D static maps and 3D interactive visualization

---

## Getting Started

Here's a basic example of loading a map, finding a location, adding a unit, and saving a mission:

```python
import os
from pytol import TerrainCalculator, MissionTerrainHelper, Mission

# --- 1. Setup ---
# Set VTOL VR directory (replace with your actual path or use environment variable)
VTOL_VR_PATH = "C:/Program Files (x86)/Steam/steamapps/common/VTOL VR"
MAP_NAME = "hMap2" # Example map ID

# --- 2. Load Map Data ---
try:
    tc = TerrainCalculator(map_name=MAP_NAME, vtol_directory=VTOL_VR_PATH)
    helper = MissionTerrainHelper(tc)
    print(f"Map '{MAP_NAME}' loaded successfully.")
except (FileNotFoundError, ValueError) as e:
    print(f"Error loading map: {e}")
    exit()

# --- 3. Use Helper to find a location ---
# Find a flat landing zone near the map center
map_center_x = tc.total_map_size_meters / 2
map_center_z = tc.total_map_size_meters / 2
landing_zones = helper.find_flat_landing_zones(map_center_x, map_center_z, search_radius=5000, min_area_radius=30)

if not landing_zones:
    print("Could not find a suitable landing zone.")
    target_pos = (map_center_x, tc.get_terrain_height(map_center_x, map_center_z), map_center_z)
else:
    target_pos = landing_zones[0] # Use the first LZ found
    print(f"Found landing zone at: {target_pos}")

# --- 4. Build the Mission ---
mission = Mission(
    scenario_name="Pytol Basic Test",
    scenario_id="pytol_test1",
    description="A simple mission generated by Pytol.",
    vehicle="AV-42C",
    map_id=MAP_NAME,
    vtol_directory=VTOL_VR_PATH
)

# Add a simple objective
mission.add_objective(
    objective_id="obj1",
    name="Go To LZ",
    info="Fly to the designated landing zone.",
    obj_type="WAYPOINT",
    fields={'waypointID': 'wpt_lz'}, # Link to a waypoint ID
    required=True
)

# Add the waypoint for the objective
mission.add_waypoint("wpt_lz", "LZ Alpha", target_pos)

# Add an enemy unit near the LZ (example)
enemy_pos = (target_pos[0] + 500, tc.get_terrain_height(target_pos[0] + 500, target_pos[2] + 500), target_pos[2] + 500)
enemy_rot = (0, 180, 0) # Facing towards LZ
mission.add_unit("AlliedInfantry", "Enemy Soldier", enemy_pos, enemy_rot, unit_fields={'team': 'ENEMY'}) #

# Add a briefing note
mission.add_briefing_note("Proceed to LZ Alpha. Expect light resistance.") #

# --- 5. Save the Mission ---
# Define where to save the mission folder (e.g., VTOL VR's CustomScenarios folder)
SAVE_PATH = os.path.join(VTOL_VR_PATH, "CustomScenarios")
try:
    mission_folder = mission.save_mission(SAVE_PATH) #
    print(f"Mission saved to: {mission_folder}")
except Exception as e:
    print(f"Error saving mission: {e}")

```

-----

## Core Components Documentation

### `TerrainCalculator` (`pytol.terrain.terrain_calculator`)

  * **Purpose:** Loads and interprets VTOL VR map data (`.vtm` files and associated textures). It calculates terrain height, surface normals, and processes procedural elements like cities and roads, as well as static map objects.
  * **Initialization:**
    ```python
    tc = TerrainCalculator(
        map_name="hMap2", 
        vtol_directory="C:/Path/To/VTOLVR",
        verbose=True  # Optional: Set to False to suppress progress messages (default: True)
    )
    # or
    tc = TerrainCalculator(map_directory_path="path/to/VTOLVR/CustomMaps/hMap2")
    ```
  * **Key Methods:**
      * `get_terrain_height(world_x, world_z)`: Returns the terrain altitude (Y-coordinate).
      * `get_terrain_normal(world_x, world_z, delta=1.0)`: Calculates the surface normal vector.
      * `get_asset_placement(world_x, world_z, yaw_degrees)`: Calculates terrain height and surface-aligned rotation.
      * `is_on_road(world_x, world_z, tolerance=10.0)`: Checks if coordinates are near a road segment.
      * `get_smart_placement(world_x, world_z, yaw_degrees)`: Snaps placement to terrain, roads, or building rooftops.
      * `get_all_city_blocks()`: Returns data on all procedural city blocks.
      * `get_all_static_prefabs()`: Returns data on all static prefabs.
      * `get_city_density(world_x, world_z)`: Returns city density value.
      * `get_city_layout_at(world_x, world_z)`: Determines city block layout, rotation, and surfaces at coordinates.

-----

### `MissionTerrainHelper` (`pytol.terrain.mission_terrain_helper`)

  * **Purpose:** Builds upon `TerrainCalculator` to provide a high-level query engine specifically for mission generation tasks. It simplifies finding tactically relevant locations and paths.

  * **Initialization:**

    ```python
    helper = MissionTerrainHelper(
        tc,  # Requires an initialized TerrainCalculator
        verbose=None  # Optional: Controls messages. None inherits from TerrainCalculator (default)
    )
    ```

  * **Methods:**

      * `has_line_of_sight(pos1, pos2, steps=20, terrain_offset=0)`: Checks for terrain obstruction between two 3D points. Returns `bool`.
      * `find_observation_post(target_area, min_dist, max_dist, num_candidates=20)`: Finds high ground with LoS to a target (e.g., for snipers). Returns `tuple (x, y, z)` or `None`.
      * `find_artillery_position(target_area, search_radius, standoff_dist=1000)`: Finds a position hidden from a target's view (e.g., for artillery). Returns `tuple (x, y, z)` or `None`.
      * `get_nearest_road_point(world_x, world_z)`: Finds the closest point on the road network. Returns `dict {'position': (x,y,z), 'segment_index': int, 'distance': float}` or `None`.
      * `get_road_path(start_pos, end_pos, max_segments=100)`: Generates waypoints following roads between two (x, z) points (greedy search). Returns `list` of `(x, y, z)`.
      * `get_buildings_in_area(center_x, center_z, radius, spawnable_only=False)`: Finds city blocks and static prefabs within a radius. Returns `list` of `dict`.
      * `find_city_with_statics(required_prefab_ids, search_all=True)`: Finds city areas containing specific static prefabs (e.g., airfields). Returns `list` of `dict`.
      * `find_flat_landing_zones(center_x, center_z, search_radius, min_area_radius, max_slope_degrees=5.0)`: Locates flat areas suitable for landings. Returns `list` of `(x, y, z)`.
      * `find_highest_point_in_area(center_x, center_z, search_radius)`: Finds the highest terrain point in an area. Returns `tuple (x, y, z)` or `None`.
      * `find_lowest_point_in_area(center_x, center_z, search_radius)`: Finds the lowest terrain point in an area. Returns `tuple (x, y, z)` or `None`.
      * `find_hidden_position(observer_pos, target_area_center, search_radius)`: Finds a low-lying point hidden from an observer. Returns `tuple (x, y, z)` or `None`.
      * `get_terrain_following_path(start_pos, end_pos, steps, altitude_agl=150.0)`: Generates waypoints at a constant altitude above ground between two (x, z) points. Returns `list` of `(x, y, z)`.
      * `get_circular_formation_points(center_pos, radius, num_points, start_angle_deg=0)`: Calculates positions for units in a circular formation. Returns `list` of `(x, y, z)`.
      * `get_terrain_type(position, sample_radius=100)`: Classifies terrain at an (x, z) position (e.g., "Urban", "Mountainous"). Returns `str`.
      * `find_choke_point(road_path, check_width=100)`: Finds the most constricted point (valley) along a road path. Returns `tuple (x, y, z)` or `None`.
      * `get_covert_insertion_path(start_pos, end_pos, radar_positions, steps=50)`: Generates a low-altitude path attempting to avoid radar LoS. Returns `list` of `(x, y, z)`.
      * `get_convoy_dispersal_points(road_position, num_points, radius)`: Finds nearby off-road hidden positions for a convoy to scatter to. Returns `list` of `(x, y, z)`.
      * `find_riverbed_path(start_pos, end_pos, steps=100)`: Generates a path following the lowest terrain (simulating valleys). Returns `list` of `(x, y, z)`.
      * `find_bridge_crossing_path(start_pos, end_pos)`: Generates a road path explicitly using the nearest suitable bridge. Returns `list` of `(x, y, z)` or `None`.
      * `find_helicopter_battle_position(target_area, search_radius, min_dist=500, pop_up_alt=30)`: Finds a hide position for a pop-up helicopter attack. Returns `tuple (x, y, z)` or `None`.
      * `generate_bombing_run_path(target_pos, entry_heading_deg, run_in_dist=5000, egress_dist=5000, altitude=1000)`: Creates IP-Target-Egress waypoints for a bombing run. Returns `dict {'ip':(x,y,z), 'target':(x,y,z), 'egress':(x,y,z)}`.
      * `define_safe_air_corridor(start_pos, end_pos, width, altitude, known_threats)`: Analyzes an air corridor's safety from threats. Returns `dict {'path': list, 'safety_score': float}`.
      * `find_naval_bombardment_position(coastal_target, standoff_distance, sea_level=1.0)`: Finds a sea position with LoS to a coastal target. Returns `tuple (x, y, z)` or `None`.
      * `calculate_front_line_trace(friendly_units, enemy_units)`: Estimates the front line based on unit positions. Returns `list` of `(x, y, z)`.
      * `trace_supply_route(start_base_name, end_base_name)`: Finds a road path between two named bases (static prefabs). Returns `list` of `(x, y, z)` or `None`.
      * `analyze_route_vulnerability(road_path, check_width=100)`: Identifies vulnerable points (bridges, choke points) along a path. Returns `dict {'bridges': list, 'choke_points': list}`.
      * `find_radar_dead_zone(radar_positions, search_area_center, search_radius, altitude)`: Finds areas hidden from all listed radars at a specific altitude. Returns `list` of `(x, y, z)`.
      * `get_line_formation_points(center_pos, num_units, spacing, angle_deg)`: Creates points for a straight-line formation on terrain. Returns `list` of `(x, y, z)`.
      * `get_wedge_formation_points(lead_pos, num_units, spacing, angle_deg)`: Creates points for a V-shaped formation on terrain. Returns `list` of `(x, y, z)`.
      * `get_building_garrison_points(building_info, max_units=10)`: *(Conceptual)* Finds spawnable rooftop positions on a building. Returns `list` of `(x, y, z)`.
      * `find_open_area(center_pos, search_radius, min_clear_radius)`: Finds a large, clear area free of buildings. Returns `tuple (x, y, z)` or `None`.
      * `get_random_points_in_area(center_pos, radius, num_points)`: Scatters random points within a radius, snapped to the ground. Returns `list` of `(x, y, z)`.
      * `suggest_objective_locations(num_locations=5, min_city_size=10)`: Identifies potential points of interest on the map. Returns `list` of `dict`.
      * `generate_downed_pilot_scenario(search_area_center, search_radius)`: Creates linked locations (crash site, LZ, patrol spawn) for a CSAR scenario. Returns `dict` or `None`.
      * `generate_base_defense_positions(base_center, num_positions, min_dist=500, max_dist=2000)`: Places defensive units on high ground around a base. Returns `list` of `(x, y, z)`.
      * `generate_convoy_ambush_scenario(convoy_path)`: Finds an ambush spot and places attackers. Returns `dict {'ambush_point': tuple, 'attacker_positions': list}` or `None`.
      * `generate_reconnaissance_flight_path(num_points=5, altitude_agl=500)`: Creates a flight path touring points of interest. Returns `list` of `(x, y, z)`.
      * `find_coastal_landing_area(search_area_center, search_radius, min_area_radius=50, sea_level=1.0)`: Finds a flat beach area for amphibious landings. Returns `tuple (x, y, z)` or `None`.
      * `get_area_control_points(area_center, radius, num_points)`: Generates tactically interesting capture points, snapped to features. Returns `list` of `(x, y, z)`.
      * `create_mission_flow(start_location_name, objective_type, target_location_name)`: Generates waypoints (start, staging, target, egress) based on named locations. Returns `dict` or `None`.
      * `get_procedural_location_name(position)`: Gives a descriptive name (e.g., "Northern Mountains", "vicinity of Airbase Alpha") to a location. Returns `str`.
      * `get_map_briefing_data()`: Generates a summary of key map features (cities, airbases, landmarks). Returns `dict`.
      * `validate_mission_feasibility(unit_list, max_slope_deg=30)`: Checks a list of units for impossible placements (e.g., ground units on steep slopes). Returns `list` of error strings.
      * `find_scenic_overlook(point_of_interest, min_dist=1000, max_dist=4000)`: Finds a point with a dramatic view of a target, favoring height. Returns `tuple (x, y, z)` or `None`.
      * `get_area_defensibility_score(area_center, radius)`: Rates an area's defensibility (0-10) based on terrain, cover, and road access. Returns `float`.
      * `calculate_threat_intervisibility(unit_positions)`: Creates a graph showing which units in a list can see each other. Returns `dict {unit_index: [visible_unit_indices]}`.

-----

### `Mission` (`pytol.parsers.vts_builder`)

  * **Purpose:** Acts as a builder class to construct the structure and content of a VTOL VR mission file (`.vts`). You add units, objectives, triggers, waypoints, etc., to this object.
  * **Initialization:**
    ```python
    mission = Mission(
        scenario_name="Generated Mission",
        scenario_id="PytolGenerated1",
        description="A mission generated by Pytol.",
        vehicle="F/A-26B",
        map_id="hMap2",
        vtol_directory="C:/Path/To/VTOLVR",
        verbose=True  # Optional: Set to False to suppress progress messages (default: True)
    )
    ```
  * **Verbose Mode:** The `verbose` parameter controls whether progress messages are printed during mission creation. When set to `False`, all print statements from `Mission`, `TerrainCalculator`, and `MissionTerrainHelper` are suppressed, which is useful for batch processing or when you want cleaner output. The verbose flag cascades to all sub-components automatically.
  
  * **Key Methods:**
      * `add_unit(...)`: Adds a unit spawner.
      * `add_unit_at_base_spawn(...)`: Adds a unit at precise airbase spawn points (hangars, helipads).
      * `add_path(...)`: Defines a path.
      * `add_waypoint(...)`: Defines a waypoint.
      * `add_unit_to_group(...)`: Assigns a unit to a team group.
      * `add_objective(...)`: Adds a mission objective.
      * `add_static_object(...)`: Adds a static map object.
      * `add_trigger_event(...)`: Adds a trigger event (requires `EventTarget` and `ParamInfo` helpers).
      * `add_base(...)`: Defines an airbase's team.
      * `add_briefing_note(...)`: Adds text to the briefing.
      * `save_mission(base_path)`: Saves the `.vts` file and copies the map folder.

-----

### Supporting Modules

  * **`pytol.parsers.vtm_parser`**: Low-level function `parse_vtol_data` for reading `.vtm` files.
  * **`pytol.parsers.vts_builder`**: Contains `Mission` class, `EventTarget`, `ParamInfo` helpers, and formatting utilities for `.vts` creation.
  * **`pytol.resources`**: Manages loading of packaged data files (JSON databases, noise texture).

-----

## Dependencies

  * **NumPy**: For numerical operations.
  * **SciPy**: For spatial data structures (KDTree) and interpolation.
  * **Pillow**: For loading texture images.

-----

## Visualization (Optional)

### 2D Static Maps (Lightweight)

If you installed `pytol[viz-light]`, you can generate beautiful static mission maps perfect for briefings:

```python
from pytol import Mission, Map2DVisualizer, save_mission_map

# Create mission
mission = Mission(
    scenario_name="Strike Mission",
    scenario_id="strike1", 
    description="Test mission",
    map_id="archipielago_1",
    vtol_directory=r"C:\Path\To\VTOL VR"
)
# ... add units, waypoints, objectives ...

# Generate clean mission overview (recommended)
viz = Map2DVisualizer(mission, figsize=(12, 12), dpi=150)
viz.save_mission_overview("mission_clean.png", clean_mode=True)

# Generate with terrain heightmap
viz.save_mission_overview("mission_full.png", terrain_style='contour')

# Generate terrain heatmap
viz.save_terrain_overview("terrain.png", style='heatmap')

# Generate spawn points detail
viz.save_spawn_points_detail("spawn_points.png", base_index=0)

# Quick convenience function
save_mission_map(mission, "overview.png", clean_mode=True)
```

**2D visualization features:**
- **Clean mode**: Professional mission maps without terrain clutter (perfect for briefings)
- **Terrain layers**: Contour maps or elevation heatmaps
- **Infrastructure**: Roads, cities, and airbases clearly marked
- **Mission elements**: Units with team colors, waypoints, objectives, and spawn points
- **Multiple formats**: PNG, PDF, SVG output with customizable DPI and sizing
- **Small file sizes**: Clean mode generates compact images (typically 50-100KB)

### 3D Interactive Exploration

If you installed `pytol[viz]`, you can visualize terrains and missions in 3D:

```python
from pytol import Mission, MissionVisualizer, TerrainVisualizer
from pytol.terrain import TerrainCalculator

# Visualize terrain only
tc = TerrainCalculator("hMap2", verbose=False)  # Optional: suppress progress messages
terrain_viz = TerrainVisualizer(
    tc, 
    mesh_resolution=256,  # Terrain mesh detail (default: 256)
    verbose=True  # Optional: Set to False to suppress rendering progress (default: True)
)
terrain_viz.show()

# Or visualize a complete mission
mission = Mission(
    scenario_name="Test Mission",
    scenario_id="test",
    description="Test",
    map_id="hMap2",
    verbose=False  # Suppress mission creation messages
)
# ... add units, objectives, etc ...

mission_viz = MissionVisualizer(mission, verbose=True)  # Show visualization progress
mission_viz.show()
```

The visualization shows:
- Terrain elevation with color mapping
- City blocks and buildings (green = spawnable, red = obstacles)
- Road network and bridges
- Mission units with team colors
- Waypoints and paths

See `examples/example_visualization.py` for a complete demo.



-----

## Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.

If you'd like to support the project financially, you can help cover development costs or contribute towards upgrading development hardware (like my Quest 2) by buying me a coffee:

<p align="center">
  <a href="https://www.buymeacoffee.com/franman" target="_blank"><img src="https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png" alt="Buy Me A Coffee" style="height: 41px !important;width: 174px !important;box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;-webkit-box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;" ></a>
</p>

-----
## Known Issues

- Need to pay attention to the terrain around cities as some city blocks deform terrain.
- Height sampling may have small discrepancies (~1-3m) compared to Unity's terrain mesh on steep slopes.

### Not issues but pending
- Support weather presets.
- Support OBJECTIVES_OPFOR.
- Support to add imgs and that kind of stuff to the briefing.
- Support to replay reading. (will be useful to make stateful campaigns or a campaign engine)
-----
## License

This project is licensed under the **GNU General Public License v3.0 only**. See the [LICENSE](https://www.gnu.org/licenses/gpl-3.0.en.html) file for details.



