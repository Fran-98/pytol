"""
Example demonstrating how to use base spawn points and reference points.

This example shows:
1. Spawn points: Precise hangar/helipad locations for spawning units
2. Reference points: Runway endpoints, ATC towers, barracks for objectives/waypoints
3. Helper functions for selecting points by category
"""
import os
import sys

# Add pytol to path
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from pytol import Mission
from pytol.classes.units import PlayerSpawn, GroundUnitSpawn
from pytol.resources.base_spawn_points import (
    get_available_bases, 
    get_spawn_points,
    get_reference_points,
    select_spawn_point
)


def main():
    # Create mission on map_asmTest (has 3 airbases with spawn points)
    vtol_dir = os.environ.get('VTOL_VR_DIR', r'F:\SteamLibrary\steamapps\common\VTOL VR')
    
    mission = Mission(
        scenario_name="Base Spawn Example",
        scenario_id="base_spawn_demo",
        description="Demonstrates precise base spawn point placement",
        map_id="map_asmTest",
        vehicle="AV-42C",
        vtol_directory=vtol_dir
    )
    
    print("\n" + "="*60)
    print("AVAILABLE BASES ON MAP:")
    print("="*60)
    
    # Get all bases
    bases = get_available_bases(mission.tc)
    for i, base in enumerate(bases):
        prefab_type = base.get('prefab_type', 'unknown')
        pos = base['position']
        print(f"\nBase {i}: {prefab_type}")
        print(f"  Position: ({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f})")
        
        # Show available spawn and reference points
        hangars = get_spawn_points(prefab_type, 'hangar')
        helipads = get_spawn_points(prefab_type, 'helipad')
        runways = get_reference_points(prefab_type, 'runway')
        towers = get_reference_points(prefab_type, 'tower')
        
        print(f"  Spawn points: {len(hangars)} hangars, {len(helipads)} helipads")
        print(f"  Reference points: {len(runways)} runway markers, {len(towers)} towers")
    
    print("\n" + "="*60)
    print("SPAWNING UNITS:")
    print("="*60)
    
    # Method 1: Use Mission.add_unit_at_base_spawn() helper
    print("\n1. Player at first hangar of first airbase:")
    player = PlayerSpawn(
        unit_name="Player",
        unit_id="PlayerSpawn",
        team="Allied",
        global_position=[0, 0, 0],  # Will be overridden
        rotation=[0, 0, 0],
        start_mode="Cold"
    )
    mission.add_unit_at_base_spawn(
        player,
        base_index=0,
        category='hangar',
        spawn_index=0  # First hangar
    )
    print(f"   Player spawned at: {player.global_position}")
    
    # Method 2: Manually select spawn point and set position
    print("\n2. Ground unit at base center (using fallback):")
    base2 = bases[1]
    # Note: helipads are actually marked with 'H', so we look for that
    center_pos, center_yaw = select_spawn_point(
        base2, 
        category='hbase',  # 'H' markers in your data
        index=-1  # Random
    )
    
    guard = GroundUnitSpawn(
        unit_name="Base Defense",
        unit_id="EnemySoldier",
        team="Enemy",
        global_position=list(center_pos),
        rotation=[0, center_yaw, 0]
    )
    mission.add_unit(guard, placement="ground", use_smart_placement=False)
    print(f"   Guard spawned at: {center_pos}")
    
    # Method 3: Using reference points (not for spawning units!)
    print("\n3. Reference points (runway endpoints for waypoints/objectives):")
    
    # Get runway reference points
    runways = get_reference_points(bases[0]['prefab_type'], 'runway')
    if runways:
        print(f"   Base 0 has {len(runways)} runway markers:")
        for rw in runways[:2]:  # Show first 2
            rw_pos, rw_yaw = select_spawn_point(bases[0], None, runways.index(rw))
            print(f"     - {rw['name']}: {rw_pos}")
    
    # Method 4: Spawn at different categories
    print("\n4. Units at third airbase (various spawn types):")
    
    # Hangar spawn
    hangar_unit = GroundUnitSpawn(
        unit_name="Hangar Guard", 
        unit_id="AlliedSoldier",
        team="Allied",
        global_position=[0,0,0], 
        rotation=[0,0,0]
    )
    mission.add_unit_at_base_spawn(hangar_unit, base_index=2, category='hangar', spawn_index=0)
    print(f"   Hangar guard at: {hangar_unit.global_position}")
    
    # Big plane spawn
    big_spawn = GroundUnitSpawn(
        unit_name="Large Aircraft Spawn", 
        unit_id="AlliedSoldier",
        team="Allied",
        global_position=[0,0,0], 
        rotation=[0,0,0]
    )
    mission.add_unit_at_base_spawn(big_spawn, base_index=2, category='bigplane', spawn_index=0)
    print(f"   Big plane spawn at: {big_spawn.global_position}")
    
    # Save mission
    print("\n" + "="*60)
    output_path = os.path.join(ROOT, "examples", "build", "base_spawn_demo")
    mission.save_mission(output_path)
    print(f"✓ Mission saved to: {output_path}")
    print("="*60)
    
    print("\n✓ Example complete!")
    print("\nTry loading this mission in VTOL VR to see precise hangar placement!")


if __name__ == "__main__":
    main()
