"""Example: Using MapPillowVisualizer (Pillow-based lightweight overview)

This script demonstrates creating a simple mission and producing a
Pillow Image (in-memory) from the visualizer. It also shows how to save
the image to disk by passing save=True.
"""
import os
from pytol import Mission
from pytol.classes.units import create_unit
from pytol.visualization import MapPillowVisualizer
from pytol.classes.mission_objects import Waypoint

out_dir = '.test_missions/test_missions_out/examples'
os.makedirs(out_dir, exist_ok=True)
filename = os.path.join(out_dir, 'example_pillow_overview.png')

mission = Mission(
    scenario_name="Example Pillow Visualizer",
    scenario_id="example_pillow",
    description="Demonstrates MapPillowVisualizer usage",
    vehicle="AV-42C",
    map_id="archipielago_1",
    vtol_directory=r"F:\\SteamLibrary\\steamapps\\common\\VTOL VR"
)

# Place a couple of units and waypoints
map_size = mission.tc.total_map_size_meters
u1 = create_unit(id_name="F-45A AI", unit_name="Example Ally", team="Allied", global_position=[0.4*map_size,1500,0.3*map_size], rotation=[0,90,0], spawn_on_start=True)
mission.add_unit(u1, placement='airborne')

wp = Waypoint(name='Start', global_point=[0.5*map_size,0,0.5*map_size], id=1)
mission.waypoints = [wp]

viz = MapPillowVisualizer(mission, size=(1024,1024), flip_x=False, flip_y=True)
# Get image (in-memory) and optionally save
img = viz.save_mission_overview(filename=filename, save=True)
print('Saved example overview to', filename)
print('Returned image:', img)
