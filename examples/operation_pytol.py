"""
Operation Pytol – Complete example mission built with Pytol

This script mirrors the "Complete Example: Strike Mission" from docs/mission_creation.md
but is adapted to the current public API:
- Use Mission(...) constructor (scenario metadata + map + VTOL path)
- Use create_unit(...) to instantiate units by prefab ID
- Use create_objective(...) to define objectives
- Use Mission.add_unit(...) for placement (airborne/ground/sea) with smart terrain
- Save using mission.save_mission(<output_dir>)

Prereqs:
- Install VTOL VR and have a custom map like hMap2 in <VTOL_DIR>/CustomMaps/hMap2
- Set VTOL_VR_DIR env var, or edit vtol_dir variable below
"""
from __future__ import annotations

import os
from typing import List

from pytol import Mission, create_unit, create_objective
from pytol.classes.mission_objects import Waypoint


def main():
    # Resolve VTOL VR directory
    vtol_dir = os.environ.get(
        "VTOL_VR_DIR",
        r"C:\\Program Files (x86)\\Steam\\steamapps\\common\\VTOL VR",
    )

    # Build mission
    mission = Mission(
        scenario_name="Operation Pytol",
        scenario_id="operation_pytol",
        description="Strike enemy artillery and destroy parked aircraft before they can scramble.",
        vehicle="F/A-26B",
        map_id="hMap2",
        vtol_directory=vtol_dir,
    )

    # Optional: auto-populate allowed equips for the mission vehicle
    try:
        mission.set_allowed_equips_for_vehicle()
    except Exception:
        pass

    # Player spawns at home base
    # hMap2 airbase is around (50747, 118161)
    # Player spawn at home base (Allied airbase on hMap2)
    # TerrainCalculator now automatically detects airbase footprints and returns
    # the flattened terrain height instead of sampling the original heightmap hills.
    home_base_x, home_base_z = 50747.0, 118161.0
    player_spawn = create_unit(
        id_name="PlayerSpawn",
        unit_name="Viper 1-1",
        team="Allied",
        global_position=[home_base_x, 0.0, home_base_z],  # Y will be set by smart placement
        rotation=[0.0, 347.0, 0.0],
        start_mode="Cold",
        initial_speed=300.0,
        unit_group="Allied:Alpha",
    )
    mission.add_unit(player_spawn, placement="ground")

    # Enemy artillery position (from reference mission AO waypoint)
    artillery_x, artillery_z = 155869.0, 38580.0

    # Create waypoint at artillery AO for navigation
    ao_waypoint = Waypoint(
        name="AO - Artillery",
        global_point=[artillery_x, 1684.0, artillery_z],
    )
    mission.add_waypoint(ao_waypoint)

    # Spawn 5 enemy artillery units
    enemy_unit_ids: List[int] = []
    artillery_offsets = [
        (-23, -79),    # Spread them out around the AO
        (23, -43),
        (73, -15),
        (-9, 61),
        (-62, 27),
    ]
    for i, (dx, dz) in enumerate(artillery_offsets, start=1):
        arty = create_unit(
            id_name="Artillery",
            unit_name=f"MPA-155 #{i}",
            team="Enemy",
            global_position=[artillery_x + dx, 1685.0, artillery_z + dz],
            rotation=[0.0, 326.0, 0.0],
            behavior="Parked",
            engage_enemies=True,
            detection_mode="Default",
            spawn_on_start=True,
        )
        uid = mission.add_unit(arty, placement="ground", use_smart_placement=True)
        enemy_unit_ids.append(uid)

    # Add enemy air defense around artillery
    sam_radar = create_unit(
        id_name="SamFCR2",
        unit_name="SAM S/A Radar",
        team="Enemy",
        global_position=[155063.0, 1658.0, 37909.0],
        rotation=[0.0, 224.0, 0.0],
        engage_enemies=True,
        detection_mode="Default",
        spawn_on_start=True,
    )
    radar_uid = mission.add_unit(sam_radar, placement="ground", use_smart_placement=True)

    sam_launcher = create_unit(
        id_name="SamBattery1",
        unit_name="SAM Launcher",
        team="Enemy",
        global_position=[154890.0, 1653.0, 37891.0],
        rotation=[0.0, 224.0, 0.0],
        radar_units=[radar_uid],
        allow_reload=False,
        engage_enemies=True,
        detection_mode="Default",
        spawn_on_start=True,
        equips=["BSM-66LR"],
    )
    mission.add_unit(sam_launcher, placement="ground", use_smart_placement=True)

    # Enemy infantry and ground units for atmosphere
    infantry_positions = [
        (155402.5, 38971.0),
        (155400.6, 38985.6),
        (155411.0, 38986.9),
        (155420.2, 38998.0),
    ]
    for i, (ix, iz) in enumerate(infantry_positions, start=1):
        inf = create_unit(
            id_name="EnemySoldier",
            unit_name=f"Infantry #{i}",
            team="Enemy",
            global_position=[ix, 1684.0, iz],
            rotation=[0.0, 265.0, 0.0],
            behavior="Parked",
            engage_enemies=True,
            detection_mode="Default",
            spawn_on_start=True,
        )
        mission.add_unit(inf, placement="ground", use_smart_placement=True)

    # Enemy MANPADS
    manpad = create_unit(
        id_name="EnemySoldierMANPAD",
        unit_name="Infantry MANPADS",
        team="Enemy",
        global_position=[155438.8, 1684.0, 39005.6],
        rotation=[0.0, 265.0, 0.0],
        behavior="Parked",
        engage_enemies=True,
        detection_mode="Default",
        spawn_on_start=True,
    )
    mission.add_unit(manpad, placement="ground", use_smart_placement=True)

    # Enemy tanks
    tank_positions = [
        (155404.9, 38931.6),
        (155376.0, 38956.1),
    ]
    for i, (tx, tz) in enumerate(tank_positions, start=1):
        tank = create_unit(
            id_name="enemyMBT1",
            unit_name=f"MBT2-E Tank #{i}",
            team="Enemy",
            global_position=[tx, 1684.0, tz],
            rotation=[0.0, 265.0, 0.0],
            behavior="Parked",
            engage_enemies=True,
            detection_mode="Default",
            spawn_on_start=True,
        )
        mission.add_unit(tank, placement="ground", use_smart_placement=True)

    # Enemy CAP fighters (ASF-30) orbiting at distance
    for i in range(2):
        cap = create_unit(
            id_name="ASF-30",
            unit_name=f"ASF-30 #{i+1}",
            team="Enemy",
            global_position=[161646.0 + i * 44.0, 3778.0, 31256.0 - i * 10.0],
            rotation=[0.0, 329.0, 0.0],
            unit_group="Enemy:Alpha",
            default_behavior="Orbit",
            initial_speed=280.0,
            default_nav_speed=280.0,
            orbit_altitude=3000.0,
            fuel=1.0,
            auto_refuel=True,
            engage_enemies=True,
            detection_mode="Default",
            spawn_on_start=True,
        )
        mission.add_unit(cap, placement="airborne")

    # Primary objective: destroy all artillery (use the instance IDs we captured)
    obj_destroy = create_objective(
        id_name="Destroy",
        objective_id=1,
        name="Strike Artillery",
        info="Destroy the five enemy artillery vehicles.",
        required=True,
        waypoint=ao_waypoint,  # Link waypoint to objective
        targets=enemy_unit_ids,   # list of artillery instance IDs
        min_required=5,
        per_unit_reward=0,
        full_complete_bonus=0,
    )
    mission.add_objective(obj_destroy)

    # Save to ./build (creates folder and copies map content)
    out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "build"))
    os.makedirs(out_dir, exist_ok=True)
    mission_path = mission.save_mission(out_dir)
    print(f"Mission created at: {mission_path}")


if __name__ == "__main__":
    main()
