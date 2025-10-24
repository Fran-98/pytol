"""
Advanced Mission Visualization Example

This demonstrates using MissionTerrainHelper with the visualization module
to create interactive test scenarios similar to your original visualize_map_mission.py
"""

import os
from pytol import Mission, MissionVisualizer
from pytol.terrain import TerrainCalculator, MissionTerrainHelper
import random

print("=" * 60)
print("Advanced Mission Visualization Demo")
print("=" * 60)

# Resolve VTOL VR directory
vtol_dir = os.environ.get("VTOL_VR_DIR")
if not vtol_dir:
    print("\nNote: VTOL_VR_DIR environment variable not set.")
    print("Trying common Steam paths...")
    possible_paths = [
        r"F:\SteamLibrary\steamapps\common\VTOL VR",
        r"C:\Program Files (x86)\Steam\steamapps\common\VTOL VR",
        r"D:\Steam\steamapps\common\VTOL VR",
    ]
    for path in possible_paths:
        if os.path.exists(path):
            vtol_dir = path
            print(f"Found VTOL VR at: {vtol_dir}")
            break
    
    if not vtol_dir:
        print("\n[ERROR] Could not find VTOL VR installation!")
        print("Please set VTOL_VR_DIR environment variable or update the script.")
        exit(1)

# Create mission
mission = Mission(
    scenario_name="Tactical Analysis Demo",
    scenario_id="tactical_demo",
    description="Demonstrating tactical queries with visualization",
    map_id="hMap2",
    vehicle="FA-26B",
    vtol_directory=vtol_dir
)

tc = mission.tc
helper = mission.helper

print("\n1. Finding key locations...")

# Get map center
map_center = tc.total_map_size_meters / 2
map_center_pos = (map_center, tc.get_terrain_height(map_center, map_center), map_center)

# Find a city
objectives = helper.suggest_objective_locations(100)
city_pos = None
for obj in objectives:
    if 'city' in obj['name'].lower():
        city_pos = obj['position']
        break
if not city_pos:
    city_pos = (57036.29, tc.get_terrain_height(57036.29, 115526.57), 115526.57)

# Find mountain and coast
mountain_pos = helper.find_highest_point_in_area(map_center, map_center, map_center)
coastal_pos = helper.find_coastal_landing_area((5000, 5000), 10000)
if not coastal_pos:
    coastal_pos = (1000, 1, 1000)

print(f"   City: {city_pos[0]:.0f}, {city_pos[2]:.0f}")
print(f"   Mountain: {mountain_pos[0]:.0f}, {mountain_pos[2]:.0f}")
print(f"   Coast: {coastal_pos[0]:.0f}, {coastal_pos[2]:.0f}")

# Add units at key locations
from pytol import create_unit

print("\n2. Adding units...")

# Player at city
player = create_unit(
    id_name="PlayerSpawn",
    unit_name="Player",
    team="Allied",
    global_position=city_pos,
    rotation=[0.0, 0.0, 0.0]
)
mission.add_unit(player, placement="ground")

# Observation post overlooking target
op_pos = helper.find_observation_post(mountain_pos, 3000, 6000)
if op_pos:
    op_unit = create_unit(
        id_name="AlliedJTAC",
        unit_name="Observation Post",
        team="Allied",
        global_position=op_pos,
        rotation=[0.0, 0.0, 0.0]
    )
    mission.add_unit(op_unit, placement="ground")
    print(f"   Added OP at elevation {op_pos[1]:.0f}m")

# Enemy artillery
arty_pos = helper.find_artillery_position(city_pos, 8000, 4000)
if arty_pos:
    for i in range(3):
        offset = i * 50
        arty_unit = create_unit(
            id_name="AlliedMLRS",
            unit_name=f"Enemy Artillery {i+1}",
            team="Enemy",
            global_position=(arty_pos[0] + offset, arty_pos[1], arty_pos[2]),
            rotation=[0.0, 0.0, 0.0]
        )
        mission.add_unit(arty_unit, placement="ground")
    print("   Added 3 artillery units")

# Enemy CAP
cap_pos = (mountain_pos[0] + 5000, mountain_pos[1] + 3000, mountain_pos[2])
for i in range(2):
    offset = i * 100
    cap_unit = create_unit(
        id_name="ASF30",
        unit_name=f"Enemy CAP {i+1}",
        team="Enemy",
        global_position=(cap_pos[0] + offset, cap_pos[1], cap_pos[2]),
        rotation=[0.0, 0.0, 0.0]
    )
    mission.add_unit(cap_unit, placement="air")
print(f"   Added 2 CAP aircraft at {cap_pos[1]:.0f}m altitude")

# Add waypoints
print("\n3. Adding waypoints...")
from pytol import Waypoint

wp1 = Waypoint(
    name="Navigation Point",
    global_point=[map_center_pos[0], map_center_pos[1] + 500, map_center_pos[2]]
)
mission.add_waypoint(wp1)

wp2 = Waypoint(
    name="Target Area",
    global_point=[
        arty_pos[0] if arty_pos else mountain_pos[0],
        arty_pos[1] + 100 if arty_pos else mountain_pos[1] + 100,
        arty_pos[2] if arty_pos else mountain_pos[2]
    ]
)
mission.add_waypoint(wp2)

# Add objectives
print("\n4. Adding objectives...")
from pytol import create_objective

obj = create_objective(
    id_name="Destroy",
    objective_id=1,
    name="Destroy Enemy Artillery",
    info="Eliminate the enemy artillery positions threatening our forces",
    required=True,
    waypoint=wp2,
    targets=[],  # Will be populated based on unit instance IDs
    min_required=3
)
mission.add_objective(obj)

print("\n5. Generating tactical paths...")

# Generate a terrain-following path
tf_path = helper.get_terrain_following_path(
    (city_pos[0], city_pos[2]), 
    (mountain_pos[0], mountain_pos[2]), 
    30, 250
)

# Generate road path
road_path = helper.get_road_path(
    (city_pos[0], city_pos[2]),
    (map_center_pos[0], map_center_pos[2])
)

if tf_path:
    print(f"   Generated terrain-following path with {len(tf_path)} waypoints")
if road_path:
    print(f"   Generated road path with {len(road_path)} waypoints")

# Display mission summary
print("\n" + "=" * 60)
print("Mission Summary:")
print(f"  Name: {mission.scenario_name}")
print(f"  Map: {mission.map_id}")
print(f"  Units: {len(mission.units)}")
print(f"  Waypoints: {len(mission.waypoints)}")
print(f"  Objectives: {len(mission.objectives)}")
print("=" * 60)

# Visualize
print("\nLaunching 3D visualization...")
print("Controls:")
print("  - Mouse: Click and drag to rotate")
print("  - Scroll: Zoom")
print("  - Q: Exit")
print("\nNote: Blue = Allied, Red = Enemy, Yellow = Waypoints")
print("=" * 60)

viz = MissionVisualizer(mission, mesh_resolution=128)
viz.show()

print("\n✅ Visualization complete!")
