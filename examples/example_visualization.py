"""
Example: Visualizing missions with PyVista.

This example demonstrates how to use the visualization module to view
terrain and missions in 3D. Requires: pip install pytol[viz]
"""

import os
from pytol import Mission, create_unit, create_objective, MissionVisualizer, TerrainVisualizer

# Check if visualization is available
if MissionVisualizer is None:
    print("[X] Visualization not available!")
    print("Install with: pip install pytol[viz]")
    exit(1)

print("Creating example mission...")

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

# Create a simple mission
mission = Mission(
    scenario_name="Visualization Demo",
    scenario_id="viz_demo",
    description="Demonstrating 3D visualization of missions",
    map_id="hMap2",
    vehicle="FA-26B",
    vtol_directory=vtol_dir
)

# Get some interesting positions from the terrain helper
tc = mission.tc
helper = mission.helper

# Find a city for player start
objectives_list = helper.suggest_objective_locations(20)
city_obj = next((obj for obj in objectives_list if 'city' in obj['name'].lower()), None)
if city_obj:
    player_pos = city_obj['position']
else:
    # Fallback to map center
    map_center = tc.total_map_size_meters / 2
    player_pos = (map_center, tc.get_terrain_height(map_center, map_center) + 100, map_center)

# Add player unit
player = create_unit(
    id_name="PlayerSpawn",
    unit_name="Player",
    team="Allied",
    global_position=player_pos,
    rotation=[0.0, 0.0, 0.0]
)
mission.add_unit(player, placement="ground")

# Find enemy positions
mountain_pos = helper.find_highest_point_in_area(player_pos[0] + 10000, player_pos[2] + 10000, 5000)

# Add some enemy units
for i in range(3):
    offset_x = i * 100
    enemy_pos_2d = (mountain_pos[0] + offset_x, mountain_pos[2])
    placement = tc.get_smart_placement(enemy_pos_2d[0], enemy_pos_2d[1], yaw_degrees=90)
    
    enemy = create_unit(
        id_name="enemyMBT1",
        unit_name=f"Enemy Tank {i+1}",
        team="Enemy",
        global_position=placement['position'],
        rotation=placement['rotation']
    )
    mission.add_unit(enemy, placement="ground")

# Add waypoint at enemy position
from pytol import Waypoint
wp = Waypoint(
    name="Attack Point",
    global_point=[mountain_pos[0], mountain_pos[1], mountain_pos[2]]
)
mission.add_waypoint(wp)

# Add objective
obj = create_objective(
    id_name="Destroy",
    objective_id=1,
    name="Destroy Enemy Tanks",
    info="Eliminate the enemy armor at the mountain position",
    required=True,
    waypoint=wp,
    targets=[],  # Will be set based on unit instance IDs after adding
    min_required=3
)
mission.add_objective(obj)

print(f"[OK] Mission created with {len(mission.units)} units")
print(f"   Player at: {player_pos}")
print(f"   Enemies at: {mountain_pos}")

# Option 1: Visualize just the terrain
print("\n--- Visualizing Terrain Only ---")
print("Close the window to continue to mission visualization...")
terrain_viz = TerrainVisualizer(tc, mesh_resolution=128)
terrain_viz.show()

# Option 2: Visualize the complete mission
print("\n--- Visualizing Complete Mission ---")
mission_viz = MissionVisualizer(mission, mesh_resolution=128)
mission_viz.show()

print("\n[OK] Visualization complete!")
