"""
Example: Creating a Campaign with Multiple Missions

This example demonstrates how to create a VTOL VR campaign with multiple missions
that can be played in sequence. Campaigns are also the only way to create multiplayer
missions in VTOL VR.

NOTE: This example requires a valid VTOL VR installation. Update VTOL_DIR below
to point to your VTOL VR installation directory.
"""

import os
from pytol import Mission, Campaign

# UPDATE THIS PATH to your VTOL VR installation!
# Example: r"F:\SteamLibrary\steamapps\common\VTOL VR"
VTOL_DIR = os.getenv('VTOL_VR_DIR')

if not VTOL_DIR:
    print("ERROR: VTOL VR directory not found!")
    print("Please set the VTOL_VR_DIR environment variable or update VTOL_DIR in this script.")
    print("Example: set VTOL_VR_DIR=F:\\SteamLibrary\\steamapps\\common\\VTOL VR")
    exit(1)

if not os.path.exists(VTOL_DIR):
    print(f"ERROR: VTOL VR directory not found at: {VTOL_DIR}")
    print("Please update the VTOL_DIR variable in this script to point to your VTOL VR installation.")
    exit(1)

# Create a new campaign
campaign = Campaign(
    campaign_id="operation_desert_storm",
    campaign_name="Operation Desert Storm",
    description="A series of strike missions against enemy forces in the desert.\\n\\nComplete all missions to achieve victory!",
    vehicle="F/A-26B",
    multiplayer=True,  # Enable multiplayer support
    verbose=True
)

# Set available equipment for the campaign
campaign.set_equipment([
    "gau-8", "m230",
    "mk82x3", "gbu38x3", "gbu39x4u",
    "sidewinderx2", "sidewinderx3",
    "maverickx3", "hellfirex4"
])

print("\n" + "="*60)
print("Creating Mission 1: Initial Strike")
print("="*60)

# Create Mission 1: Initial Strike
mission1 = Mission(
    scenario_name="Initial Strike",
    scenario_id="mission_1_initial_strike",
    description="Destroy enemy radar installations and SAM sites.",
    vehicle="F/A-26B",
    map_id="hMap2",
    vtol_directory=VTOL_DIR,
    verbose=False  # Suppress terrain loading messages
)

# Add player spawn
mission1.add_allied_spawn(
    global_position=(100000, 500, 50000),
    heading=0,
    unit_name="Allied Fighter 1"
)

# Add some enemy units
mission1.add_enemy_unit(
    global_position=(105000, 100, 52000),
    unit_name="Enemy SAM",
    unit_type="AASite"
)

# Add objective
mission1.add_destroy_objective(
    target_unit_name="Enemy SAM",
    objective_name="Destroy SAM Site",
    required=True
)

# Add mission to campaign
campaign.add_mission(mission1)

print("\n" + "="*60)
print("Creating Mission 2: Deep Strike")
print("="*60)

# Create Mission 2: Deep Strike
mission2 = Mission(
    scenario_name="Deep Strike",
    scenario_id="mission_2_deep_strike",
    description="Strike enemy airbase and destroy parked aircraft.",
    vehicle="F/A-26B",
    map_id="hMap2",
    vtol_directory=VTOL_DIR,
    verbose=False
)

# Add player spawn
mission2.add_allied_spawn(
    global_position=(100000, 500, 50000),
    heading=0,
    unit_name="Allied Fighter 1"
)

# Add enemy airbase units
mission2.add_enemy_unit(
    global_position=(110000, 100, 55000),
    unit_name="Enemy Fighter 1",
    unit_type="EF-24"
)

mission2.add_enemy_unit(
    global_position=(110100, 100, 55000),
    unit_name="Enemy Fighter 2",
    unit_type="EF-24"
)

# Add objectives
mission2.add_destroy_objective(
    target_unit_name="Enemy Fighter 1",
    objective_name="Destroy Parked Aircraft",
    required=True
)

# Add mission to campaign
campaign.add_mission(mission2)

print("\n" + "="*60)
print("Creating Mission 3: Final Assault")
print("="*60)

# Create Mission 3: Final Assault
mission3 = Mission(
    scenario_name="Final Assault",
    scenario_id="mission_3_final_assault",
    description="Final push to destroy enemy command center.",
    vehicle="F/A-26B",
    map_id="hMap2",
    vtol_directory=VTOL_DIR,
    verbose=False
)

# Add player spawn
mission3.add_allied_spawn(
    global_position=(100000, 500, 50000),
    heading=0,
    unit_name="Allied Fighter 1"
)

# Add enemy command center
mission3.add_enemy_unit(
    global_position=(115000, 100, 58000),
    unit_name="Enemy HQ",
    unit_type="AArtillery"
)

# Add defensive units
mission3.add_enemy_unit(
    global_position=(114500, 100, 57500),
    unit_name="HQ Defense 1",
    unit_type="AASite"
)

mission3.add_enemy_unit(
    global_position=(115500, 100, 58500),
    unit_name="HQ Defense 2",
    unit_type="AASite"
)

# Add objectives
mission3.add_destroy_objective(
    target_unit_name="Enemy HQ",
    objective_name="Destroy Enemy HQ",
    required=True
)

# Add mission to campaign
campaign.add_mission(mission3)

# Save the campaign
print("\n" + "="*60)
print("Saving Campaign")
print("="*60)

output_folder = "examples/build/operation_desert_storm"
campaign.save(output_folder, copy_map_folders=False)

# Optionally save Workshop metadata
campaign.save_workshop_info(
    output_folder,
    published_file_id="0",  # Use "0" for new uploads
    tags=["Multiplayer Campaigns", "Strike Missions"]
)

print("\n" + "="*60)
print("Campaign Creation Complete!")
print("="*60)
print(f"\nCampaign saved to: {output_folder}")
print(f"Total missions: {len(campaign.missions)}")
print(f"Multiplayer: {campaign.multiplayer}")
print("\nTo play:")
print(f"1. Copy the '{output_folder}' folder to your VTOL VR CustomScenarios/Campaigns folder")
print(f"2. Launch VTOL VR and select 'Campaigns' from the main menu")
print(f"3. Find '{campaign.campaign_name}' in the list")
print("\nEnjoy your campaign!")
