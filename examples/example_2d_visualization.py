"""
Example demonstrating 2D mission visualization with matplotlib.

This example shows how to create lightweight static images of missions
that show terrain, units, waypoints, and other mission elements in a 
top-down tactical view.
"""
import os
import sys

# Add pytol to path
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from pytol import Mission, Map2DVisualizer, save_mission_map
from pytol.classes.units import PlayerSpawn, GroundUnitSpawn


def main():
    # Use environment variable or default path
    vtol_dir = os.environ.get('VTOL_VR_DIR', r'F:\SteamLibrary\steamapps\common\VTOL VR')
    
    print("=" * 60)
    print("2D MISSION VISUALIZATION EXAMPLE")
    print("=" * 60)
    
    # Create a mission with some content
    mission = Mission(
        scenario_name="2D Visualization Demo",
        scenario_id="viz_2d_demo",
        description="Demonstrates the 2D visualization system",
        map_id="map_asmTest",  # Map with known airbases
        vehicle="AV-42C",
        vtol_directory=vtol_dir,
        verbose=True
    )
    
    # Add player spawn at airbase
    try:
        player = PlayerSpawn(
            id_name="PlayerSpawn",
            unit_name="Player",
            global_position=(13216, 300, 17232),  # Near airbase1
            rotation=[0, 90, 0],
        )
        mission.add_unit_at_base_spawn(player, base_index=0, category='hangar', spawn_index=0)
        print("✓ Added player spawn at airbase hangar")
    except Exception as e:
        print(f"Warning: Could not add player at airbase spawn: {e}")
        # Fallback to manual position
        mission.add_unit(player, placement="ground")
    
    # Add some enemy units
    enemy_positions = [
        (14000, 300, 18000),  # Near player
        (15000, 350, 17500),  # Another location
        (12500, 280, 16800),  # Third location
    ]
    
    for i, pos in enumerate(enemy_positions):
        enemy = GroundUnitSpawn(
            id_name=f"Enemy{i+1}",
            unit_name=f"Enemy Unit {i+1}",
            global_position=pos,
            rotation=[0, 180, 0],  # Facing player
            team="Enemy"
        )
        mission.add_unit(enemy, placement="ground")
    
    print(f"✓ Added {len(enemy_positions)} enemy units")
    
    # Add waypoints for a simple route
    waypoints = [
        (13500, 400, 17500),  # Takeoff
        (14500, 600, 18500),  # Navigate
        (15500, 500, 17000),  # Target area
        (13000, 400, 16500),  # Return
    ]
    
    for i, pos in enumerate(waypoints):
        from pytol.classes.mission_objects import Waypoint
        wp = Waypoint(
            id=f"wp{i+1}",
            name=f"Waypoint {i+1}",
            position=pos
        )
        mission.add_waypoint(wp)
    
    print(f"✓ Added {len(waypoints)} waypoints")
    
    # Add an objective
    from pytol.classes.objectives import create_objective
    objective = create_objective(
        objective_id="obj1",
        name="Destroy Enemy Forces",
        description="Eliminate enemy units in the target area",
        obj_type="DESTROY",
        target_unit_id="Enemy1",
        required=True,
        completion_reward=100
    )
    mission.add_objective(objective)
    print("✓ Added destroy objective")
    
    # Create output directory
    output_dir = os.path.join(ROOT, "examples", "build", "viz_2d_demo")
    os.makedirs(output_dir, exist_ok=True)
    
    print("\n" + "=" * 60)
    print("GENERATING 2D VISUALIZATIONS")
    print("=" * 60)
    
    # Method 1: Using Map2DVisualizer class
    viz = Map2DVisualizer(mission, figsize=(12, 12), dpi=150, verbose=True)
    
    # Save mission overview
    overview_file = os.path.join(output_dir, "mission_overview.png")
    viz.save_mission_overview(overview_file, terrain_style='contour')
    print(f"✓ Mission overview: {overview_file}")
    
    # Save terrain-only view
    terrain_file = os.path.join(output_dir, "terrain_only.png")  
    viz.save_terrain_overview(terrain_file, style='heatmap')
    print(f"✓ Terrain overview: {terrain_file}")
    
    # Save spawn points detail (if bases are available)
    try:
        spawn_file = os.path.join(output_dir, "spawn_points_detail.png")
        viz.save_spawn_points_detail(spawn_file, base_index=0)
        print(f"✓ Spawn points detail: {spawn_file}")
    except Exception as e:
        print(f"⚠ Could not create spawn points detail: {e}")
    
    # Method 2: Using convenience function
    quick_file = os.path.join(output_dir, "quick_overview.png")
    save_mission_map(mission, quick_file, style='mission_overview', figsize=(10, 10))
    print(f"✓ Quick overview: {quick_file}")
    
    # Terrain-only with TerrainCalculator
    terrain_only_file = os.path.join(output_dir, "terrain_calculator_only.png")
    save_mission_map(mission.tc, terrain_only_file, style='terrain_only', figsize=(8, 8))
    print(f"✓ Terrain calculator only: {terrain_only_file}")
    
    print("\n" + "=" * 60)
    print("✓ 2D VISUALIZATION DEMO COMPLETE!")
    print("=" * 60)
    print(f"Output files saved to: {output_dir}")
    print()
    print("Generated files:")
    for filename in os.listdir(output_dir):
        if filename.endswith('.png'):
            filepath = os.path.join(output_dir, filename)
            size_kb = os.path.getsize(filepath) // 1024
            print(f"  - {filename} ({size_kb} KB)")
    
    print("\n🎯 Try opening these PNG files to see your mission layout!")


if __name__ == "__main__":
    main()