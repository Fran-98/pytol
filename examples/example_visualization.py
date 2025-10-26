"""
Example: Visualizing missions with PyVista.

This example demonstrates how to use the visualization module to view
terrain and missions in 3D. Requires: pip install pytol[viz]

Updates:
- Visualize the complete mission first (then terrain-only as an optional step)
- Place units using terrain-aware smart placement for correct height/orientation
- Generate and visualize a mission via the ProceduralMissionEngine (default behavior)
"""

import os
from pytol import (
    MissionVisualizer,
    TerrainVisualizer,
    ProceduralMissionEngine,
    ProceduralMissionSpec,
)

# Check if visualization is available
if MissionVisualizer is None:
    print("[X] Visualization not available!")
    print("Install with: pip install pytol[viz]")
    exit(1)

print("Generating procedural mission...")

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

# Generate a procedural mission using the engine
spec = ProceduralMissionSpec(
    scenario_id="proc_viz_demo",
    scenario_name="Procedural Viz Demo",
    description="Generated via ProceduralMissionEngine",
    vehicle="FA-26B",
    map_id="hMap2",
    vtol_directory=vtol_dir,
    mission_type="strike",
    difficulty="normal",
    time_of_day=None,
    seed=13,
)
engine = ProceduralMissionEngine(verbose=True)
mission = engine.generate(spec)
tc = mission.tc
helper = mission.helper
print(f"[OK] Procedural mission generated with {len(mission.units)} units, {len(mission.waypoints)} WPs, {len(mission.objectives)} objectives")

# Visualize the complete mission first
print("\n--- Visualizing Complete Mission ---")
mission_viz = MissionVisualizer(mission, mesh_resolution=128)
mission_viz.show()

# Optional: Visualize terrain only afterwards (useful for map inspection)
print("\n--- Visualizing Terrain Only (optional) ---")
terrain_viz = TerrainVisualizer(tc, mesh_resolution=128)
terrain_viz.show()

print("\n[OK] Visualization complete!")
