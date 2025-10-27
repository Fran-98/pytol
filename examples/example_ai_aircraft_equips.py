from pytol import Mission
from pytol.classes.units import create_unit

"""
Example: Equippable AI aircraft loadouts
- Demonstrates setting 'equips' on AIAircraftSpawn units (e.g., ASF-30, EBomberAI)
- Uses real equipment IDs from vehicle_equip_database.json

Note: These are AI-only vehicles. For player vehicles, use EquipmentBuilder.
"""

# Minimal mission
mission = Mission(
    scenario_name="AI Equips Demo",
    scenario_id="ai_equips_demo",
    description="Demonstrate AI aircraft equips on ASF-30 and EBomberAI",
    vehicle="AV-42C",  # Player vehicle (not used here, but required by mission schema)
    map_id="hMap2",
    vtol_directory=r"C:\\Program Files (x86)\\Steam\\steamapps\\common\\VTOL VR",
)

# Enemy ASF-30 with guns + MRMs (valid equipment IDs for ASF-30)
asf30 = create_unit(
    id_name="ASF-30",
    unit_name="Enemy ASF-30 #1",
    team="Enemy",
    global_position=[5000.0, 2500.0, 5000.0],
    rotation=[0.0, 90.0, 0.0],
    default_behavior="Orbit",
    orbit_altitude=2500.0,
    equips=[
        "asf30_gun",      # Gun
        "asf_mrmRail",    # Medium-range missile rail
        "asf_mrmRail",    # Another MRM rail
        "asf30_jammer"    # Jammer pod
    ],
)
mission.add_unit(asf30, placement="airborne")

# Enemy EBomberAI with standard rack (the only listed equipment)
ebomber = create_unit(
    id_name="EBomberAI",
    unit_name="Enemy Bomber",
    team="Enemy",
    global_position=[8000.0, 2200.0, 8000.0],
    rotation=[0.0, 45.0, 0.0],
    default_behavior="Path",
    default_nav_speed=180.0,
    equips=[
        "ebomber_stdRack"
    ],
)
mission.add_unit(ebomber, placement="airborne")

# Save mission
out_dir = mission.save_mission("./out")
print(f"Mission saved to: {out_dir}")
