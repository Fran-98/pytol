# Mission Creation Guide

This guide covers how to create VTOL VR missions programmatically using Pytol.

## Quick Start

```python
from pytol import Mission

# 1. Create a new mission
mission = Mission(
    scenario_name="Strike on Enemy Airbase",
    scenario_id="strike_mission_1",
    description="Destroy enemy aircraft at their forward operating base.",
    vehicle="F/A-26B",
    map_id="hMap2",
    vtol_directory=r"C:\Program Files (x86)\Steam\steamapps\common\VTOL VR",
    verbose=True
)

# 2. Access the terrain calculator (automatically created)
tc = mission.tc  # TerrainCalculator instance
helper = mission.helper  # MissionTerrainHelper instance

# 3. Add a player spawn
mission.add_allied_spawn(
    global_position=(100000, 500, 50000),
    heading=0,
    unit_name="Player"
)

# 4. Add enemy units with terrain-aware placement
enemy_pos = (105000, 0, 52000)
placement = tc.get_smart_placement(enemy_pos[0], enemy_pos[2], yaw_degrees=90)

mission.add_enemy_unit(
    global_position=placement['position'],
    rotation=placement['rotation'],
    unit_name="Enemy Fighter",
    unit_type="EF-24"
)

# 5. Add an objective
mission.add_destroy_objective(
    target_unit_name="Enemy Fighter",
    objective_name="Destroy Enemy Aircraft",
    required=True
)

# 6. Save the mission
mission.save_mission("./output")  # Creates: ./output/strike_mission_1/
```

**Note:** `save_mission()` creates a folder structure with the mission file and map data inside.

## Map Selection and Realism Tips

- Prefer maps with HeightMap terrain for best results with Pytol's terrain sampler. Recommended: `hMap2`, `costaOeste`, `Archipielago_1`.
- The map `Akutan` is primarily mesh-based in Unity (not heightmap-generated), so it can not be used with this library.
- Even with our accurate recreation, expect small height mismatches of up to ~1 m in some spots (bilinear vs mesh interpolation, collider differences). Always validate spawns in-game or add a small offset.

## Core Concepts

### Mission Object

The `Mission` class represents a complete VTOL VR mission file (.vts).

```python
mission = Mission(
    scenario_name="Mission Title",            # Display name in game
    scenario_id="my_mission_01",              # Unique identifier (folder name)
    description="Mission briefing text",      # Briefing shown to player
    vehicle="F/A-26B",                        # Player aircraft (default: "AV-42C")
    map_id="hMap2",                           # Map folder name (case-sensitive)
    vtol_directory=r"C:\...\VTOL VR",        # Path to VTOL VR installation
    verbose=True                              # Print progress messages (default: True)
)

# Optional properties that can be set after creation
mission.campaign_order_idx = 0                # Order in campaign (if part of one)
mission.mission_info.rtb_location = (100000, 500, 50000)  # Return to base waypoint
mission.mission_info.is_training = False      # Training mission flag
mission.mission_info.force_equipment = []     # Lock player loadout (list of equipment IDs)
```

### Units

Units represent aircraft, ground vehicles, ships, and static objects.

#### Creating Aircraft

```python
from pytol import Unit

# Fighter aircraft starting in the air
fighter = Unit.create_aircraft(
    unit_name="CAP Flight 1",
    global_position=(100000, 2000, 50000),  # 2000m altitude
    rotation=(0, 45, 0),                     # (pitch, yaw, roll)
    unit_instance_id=1,
    aircraft_type="FA-26B",
    initial_speed=200.0,                     # m/s
    fuel=1.0,                                 # 0.0 to 1.0
    start_on_ground=False
)

# Aircraft starting on ground (use terrain placement)
tc = TerrainCalculator(map_name="hMap2", vtol_directory=vtol_path)
x, z = 105000, 52000
placement = tc.get_smart_placement(x, z, yaw_degrees=90)

parked = Unit.create_aircraft(
    unit_name="Parked Enemy",
    global_position=placement['position'],
    rotation=placement['rotation'],
    unit_instance_id=2,
    aircraft_type="EF-24",
    initial_speed=0.0,
    start_on_ground=True,
    engine_startup=False  # Engines off
)

mission.add_unit(fighter)
mission.add_unit(parked)
```

**Available Aircraft Types:**
- `"FA-26B"` - F/A-26B (multirole, playable)
- `"AV42C"` - AV-42C (VTOL attack aircraft, playable)
- `"F45A"` - F-45A (air superiority fighter, playable)
- `"T-55"` - T-55 (trainer jet, playable)
- `"AH-94"` - AH-94 (attack helicopter, playable)
- `"EF-24"` - EF-24 (enemy fighter)
- `"ASF30"` - ASF-30 (enemy stealth fighter)
- `"ASF58"` - ASF-58 (enemy bomber)
- `"GAV25"` - GAV-25 (enemy gunship)

#### Creating Ground Units

```python
# Armored vehicle
tank = Unit.create_ground_unit(
    unit_name="Enemy Tank",
    global_position=(106000, 450, 51000),
    rotation=(0, 180, 0),
    unit_instance_id=10,
    unit_type="TANK",
    default_behavior="stationary"
)

# SAM site
sam = Unit.create_ground_unit(
    unit_name="SAM Battery",
    global_position=(107000, 500, 52000),
    unit_instance_id=11,
    unit_type="SAM",
    detection_mode="radar_on"
)

mission.add_unit(tank)
mission.add_unit(sam)
```

**Ground Unit Types:**
- `"TANK"` - Armored vehicle
- `"APC"` - Armored personnel carrier
- `"SAM"` - Surface-to-air missile system
- `"AAA"` - Anti-aircraft artillery
- `"ARTILLERY"` - Artillery piece
- `"TRUCK"` - Supply truck

**Behaviors:**
- `"stationary"` - Unit stays in place
- `"patrol"` - Unit patrols assigned waypoints
- `"defend"` - Unit defends area
- `"attack"` - Unit attacks targets

#### Creating Ships

```python
# Carrier
carrier = Unit.create_ship(
    unit_name="CVN-76 Roosevelt",
    global_position=(95000, 0, 48000),  # Sea level (y=0)
    rotation=(0, 270, 0),
    unit_instance_id=20,
    ship_type="CARRIER",
    speed=10.0  # knots
)

# Destroyer escort
destroyer = Unit.create_ship(
    unit_name="DDG Escort",
    global_position=(95500, 0, 48000),
    unit_instance_id=21,
    ship_type="DESTROYER"
)

mission.add_unit(carrier)
mission.add_unit(destroyer)
```

**Ship Types:**
- `"CARRIER"` - Aircraft carrier (can spawn/recover aircraft)
- `"DESTROYER"` - Guided missile destroyer
- `"CRUISER"` - Cruiser
- `"FRIGATE"` - Frigate
- `"PATROL_BOAT"` - Fast patrol boat
- `"TRANSPORT"` - Transport ship

### Terrain-Aware Placement

Use `TerrainCalculator.get_smart_placement()` to automatically place units on terrain, roads, or building roofs:

```python
tc = TerrainCalculator(map_name="hMap2", vtol_directory=vtol_path)

# Place unit on terrain/road/roof
x, z = 105000, 52000
yaw = 90  # Facing east

placement = tc.get_smart_placement(x, z, yaw_degrees=yaw)
# Returns: {
#     'position': (x, height, z),
#     'rotation': (pitch, yaw, roll),
#     'type': 'terrain'  # or 'road', 'city_roof', 'static_roof'
# }

unit = Unit.create_ground_unit(
    unit_name="Infantry Squad",
    global_position=placement['position'],
    rotation=placement['rotation'],
    unit_instance_id=30,
    unit_type="INFANTRY"
)
```

**Placement Types:**
- `'terrain'` - Natural ground height
- `'road'` - On a road surface
- `'city_roof'` - On a procedural city building roof
- `'static_roof'` - On a static prefab building roof

### Objectives

Objectives define mission goals and success/failure conditions.

```python
from pytol import Objective

# Destroy a specific unit
obj1 = Objective(
    objective_id=1,
    objective_type="DESTROY",
    objective_name="Destroy Enemy Airbase",
    target_unit_id=2,              # Unit instance ID
    required_success=True,          # Mission fails if not completed
    completion_reward=100           # Score points
)

# Reach a waypoint
obj2 = Objective(
    objective_id=2,
    objective_type="WAYPOINT",
    objective_name="Reach Extraction Point",
    waypoint_id="extraction_wp",
    required_success=False,
    completion_reward=50
)

# Protect a unit
obj3 = Objective(
    objective_id=3,
    objective_type="PROTECT",
    objective_name="Defend Allied Convoy",
    target_unit_id=5,
    failure_condition="unit_destroyed",
    required_success=True
)

mission.add_objective(obj1)
mission.add_objective(obj2)
mission.add_objective(obj3)
```

**Objective Types:**
- `"DESTROY"` - Destroy target unit(s)
- `"WAYPOINT"` - Reach a specific location
- `"PROTECT"` - Keep a unit alive
- `"LANDING"` - Land at a specific location
- `"TIME_SURVIVE"` - Survive for a duration
- `"FUEL"` - Maintain fuel above threshold

### Conditionals and Events

Conditionals trigger events based on game state. They enable dynamic mission behavior.

```python
from pytol import Conditional, Action

# When objective completed, spawn reinforcements
cond1 = Conditional(
    conditional_id=1,
    condition_type="objective_complete",
    objective_id=1
)
# Action: Spawn new units
spawn_action = Action(
    action_type="spawn_units",
    unit_ids=[10, 11, 12]  # IDs of units to spawn
)
cond1.add_action(spawn_action)

# When player enters area, activate SAM sites
cond2 = Conditional(
    conditional_id=2,
    condition_type="player_in_zone",
    zone_center=(105000, 500, 52000),
    zone_radius=2000  # meters
)
activate_action = Action(
    action_type="set_unit_behavior",
    unit_id=11,
    new_behavior="attack",
    detection_mode="radar_on"
)
cond2.add_action(activate_action)

# When unit destroyed, fail mission
cond3 = Conditional(
    conditional_id=3,
    condition_type="unit_destroyed",
    unit_id=5
)
fail_action = Action(
    action_type="fail_mission",
    message="Allied convoy destroyed!"
)
cond3.add_action(fail_action)

mission.add_conditional(cond1)
mission.add_conditional(cond2)
mission.add_conditional(cond3)
```

**Condition Types:**
- `"objective_complete"` - When objective is completed
- `"unit_destroyed"` - When a unit is destroyed
- `"player_in_zone"` - When player enters area
- `"time_elapsed"` - After a time duration
- `"global_value"` - When a variable meets criteria

**Action Types:**
- `"spawn_units"` - Spawn additional units
- `"set_unit_behavior"` - Change unit AI behavior
- `"fail_mission"` - End mission as failure
- `"complete_objective"` - Mark objective as complete
- `"set_global_value"` - Set mission variable
- `"play_radio_message"` - Play voice/text radio message

### Global Values (Mission Variables)

Global values are variables that can be read and modified during the mission.

```python
from pytol import GlobalValue

# Counter for enemy kills
kill_counter = GlobalValue(
    value_name="enemy_kills",
    initial_value=0,
    value_type="int"
)

# Boolean flag
alarm_triggered = GlobalValue(
    value_name="alarm_active",
    initial_value=False,
    value_type="bool"
)

mission.add_global_value(kill_counter)
mission.add_global_value(alarm_triggered)

# Use in conditionals
cond = Conditional(
    conditional_id=10,
    condition_type="global_value",
    value_name="enemy_kills",
    comparison=">=",
    target_value=5
)
# Action: Complete bonus objective
bonus_action = Action(
    action_type="complete_objective",
    objective_id=4
)
cond.add_action(bonus_action)
mission.add_conditional(cond)
```

## Complete Example: Strike Mission

```python
from pytol import Mission, Unit, Objective, Conditional, Action

# Setup
vtol_path = r"C:\Program Files (x86)\Steam\steamapps\common\VTOL VR"

mission = Mission(
    scenario_name="Operation Iron Fist",
    scenario_id="custom_strike",
    description="Strike enemy airbase and destroy parked aircraft before they can scramble.",
    vehicle="F/A-26B",
    map_id="hMap2",
    vtol_directory=vtol_path,
    verbose=True
)

tc = mission.tc  # Access the TerrainCalculator
mission.mission_info.rtb_location = (98000, 500, 48000)

# Player starts on carrier
carrier_pos = (95000, 0, 48000)
carrier = Unit.create_ship(
    unit_name="CVN Roosevelt",
    global_position=carrier_pos,
    unit_instance_id=1,
    ship_type="CARRIER"
)
mission.add_unit(carrier)

# Player aircraft
player = Unit.create_aircraft(
    unit_name="Viper 1-1",
    global_position=(95000, 20, 48050),  # On carrier deck
    rotation=(0, 0, 0),
    unit_instance_id=2,
    aircraft_type="FA-26B",
    fuel=1.0,
    start_on_ground=True
)
mission.add_unit(player)

# Enemy airbase/city apron with parked aircraft (hMap2 city cluster)
# Inspired by actual mission coordinates around (x≈58k..65k, z≈114k..120k)
airbase_x, airbase_z = 57935, 114838

for i in range(4):
    offset_x = i * 50
    placement = tc.get_smart_placement(airbase_x + offset_x, airbase_z, yaw_degrees=90)
    enemy = Unit.create_aircraft(
        unit_name=f"Enemy Fighter {i+1}",
        global_position=placement['position'],
        rotation=placement['rotation'],
        unit_instance_id=10 + i,
        aircraft_type="EF-24",
        start_on_ground=True,
        engine_startup=False
    )
    mission.add_unit(enemy)

# SAM defenses
sam_positions = [
    (airbase_x - 500, airbase_z),
    (airbase_x + 500, airbase_z),
    (airbase_x, airbase_z - 500),
    (airbase_x, airbase_z + 500),
]

for i, (sam_x, sam_z) in enumerate(sam_positions):
    placement = tc.get_smart_placement(sam_x, sam_z, yaw_degrees=0)
    sam = Unit.create_ground_unit(
        unit_name=f"SAM Site {i+1}",
        global_position=placement['position'],
        rotation=placement['rotation'],
        unit_instance_id=20 + i,
        unit_type="SAM",
        detection_mode="radar_off"  # Start passive
    )
    mission.add_unit(sam)

# Primary objective: Destroy all parked aircraft
obj_destroy = Objective(
    objective_id=1,
    objective_type="DESTROY",
    objective_name="Destroy Enemy Aircraft",
    target_unit_ids=[10, 11, 12, 13],  # All enemy fighters
    required_success=True,
    completion_reward=200
)
mission.add_objective(obj_destroy)

# Secondary objective: RTB safely
obj_rtb = Objective(
    objective_id=2,
    objective_type="LANDING",
    objective_name="Return to Carrier",
    landing_location=carrier_pos,
    required_success=False,
    completion_reward=100
)
mission.add_objective(obj_rtb)

# Event: SAMs go active when player enters 5km
cond_sams = Conditional(
    conditional_id=1,
    condition_type="player_in_zone",
    zone_center=(110000, 1000, 55000),
    zone_radius=5000
)
for sam_id in range(20, 24):
    action = Action(
        action_type="set_unit_behavior",
        unit_id=sam_id,
        detection_mode="radar_on"
    )
    cond_sams.add_action(action)

mission.add_conditional(cond_sams)

# Save the mission
mission.save_mission("./output")
print("Mission created successfully!")
```

## Resources

Resources allow you to include custom audio briefings and images in your mission. Pytol automatically copies resource files to the mission directory when you save.

### Adding Audio Briefings

```python
# Add a custom audio briefing
mission.add_resource(
    res_id=1,
    path="C:/MyMissions/audio/briefing.wav"
)
```

The audio file will be automatically copied to `<mission_folder>/audio/briefing.wav` when you save the mission.

### Adding Custom Images

```python
# Add a custom HUD overlay or briefing image
mission.add_resource(
    res_id=2,
    path="./images/tactical_map.png"
)
```

The image file will be automatically copied to `<mission_folder>/images/tactical_map.png` when you save the mission.

### Resource IDs

- Resource IDs must be unique integers
- Use IDs 1-999 for your custom resources
- The game uses these IDs to reference resources in briefing notes and other mission elements

### Supported File Types

- **Audio**: `.wav`, `.ogg`, `.mp3` → copied to `audio/` subdirectory
- **Images**: `.png`, `.jpg`, `.jpeg`, `.bmp` → copied to `images/` subdirectory

### Example: Complete Mission with Audio Briefing

```python
from pytol import Mission

mission = Mission(
    scenario_name="Operation Desert Storm",
    scenario_id="desert_storm",
    description="Strike enemy command center",
    map_id="hMap2"
)

# Add custom audio briefing
mission.add_resource(1, "path/to/briefing.wav")

# Add units, objectives, etc...

# Save mission (automatically copies resource files)
mission.save_mission("./output")
```

When you call `save_mission()`, Pytol will:
1. Create the mission directory structure
2. Copy the map files
3. **Automatically copy all resource files to appropriate subdirectories**
4. Generate the `.vts` file with correct relative paths in the ResourceManifest

## Tips and Best Practices

### Terrain Placement
- Always use `TerrainCalculator` for ground units and parked aircraft
- Call `get_smart_placement()` to automatically handle terrain, roads, and buildings
- For ships, always use `y=0` (sea level)
- For airborne aircraft, set appropriate altitude

### Unit IDs
- Must be unique across all units in the mission
- Start from 1 (0 is reserved)
- Use ranges for organization (1-9 player, 10-99 enemies, 100+ allies)

### Objectives
- Set `required_success=True` for mission-critical objectives
- Use `completion_reward` to guide player priorities
- Combine multiple objectives for complex missions

### Testing
- Test missions in-game before distributing
- Use descriptive unit names for debugging
- Check terrain placement with visualization tools

## Troubleshooting

### Units spawn underground
- Ensure you're using `TerrainCalculator.get_smart_placement()`
- Verify the map_name matches the CustomMaps folder name exactly
- Check that VTOL VR directory path is correct

### Mission doesn't load
- Verify `map_id` matches map folder name (case-sensitive)
- Ensure all unit IDs are unique
- Check that required objectives exist

### Objectives don't trigger
- Confirm `objective_id` in conditionals matches defined objectives
- Verify `target_unit_id` refers to existing units
- Check condition types match your intent

### Terrain heights seem wrong
- Some maps (e.g., hm_mtnLake) have encoding issues - see `terrain_behavior.md`
- Use `height_scale` and `height_offset` parameters if needed (experimental)
- Validate with known reference points from in-game

## See Also

- [Terrain Behavior Documentation](terrain_behavior.md) - Height sampling and city behavior
- [API Reference](../README.md) - Complete API documentation
