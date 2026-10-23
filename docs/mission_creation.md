# Mission Creation Guide

This guide covers how to create VTOL VR missions programmatically using Pytol.

## Quick Start

```python
import os
from pytol import Mission, Waypoint, Trigger, create_unit, create_objective
from pytol.classes.actions import SystemActions

VTOL_VR_PATH = os.environ.get("VTOL_VR_DIR", "C:/Program Files (x86)/Steam/steamapps/common/VTOL VR")

# --- 1. Mission on a custom map (loads terrain, cities, roads and bases) ---
mission = Mission(
    scenario_name="Pytol Quickstart",
    scenario_id="pytol_quickstart",
    description="Fly to the landing zone and destroy the tank.",
    vehicle="AV-42C",
    map_id="hMap2",
    vtol_directory=VTOL_VR_PATH,
)
tc, helper = mission.tc, mission.helper

# --- 2. Terrain queries: a flat landing zone near the map center ---
cx = cz = tc.total_map_size_meters / 2
zones = helper.find_flat_landing_zones(cx, cz, search_radius=5000, min_area_radius=30)
lz = zones[0] if zones else (cx, tc.get_terrain_height(cx, cz), cz)

# --- 3. Waypoint, units and objectives ---
lz_wpt = Waypoint(name="LZ Alpha", global_point=list(lz))
mission.add_waypoint(lz_wpt)

player = create_unit("PlayerSpawn", "Player", "Allied", [lz[0] - 8000, lz[1] + 1500, lz[2]], [0, 90, 0])
mission.add_unit(player, placement="airborne")
tank = create_unit("enemyMBT1", "Tank", "Enemy", [lz[0] + 500, 0, lz[2] + 500], [0, 180, 0])
tank_id = mission.add_unit(tank, placement="ground")  # snapped to terrain/roads/roofs

fly = create_objective("Fly_To", 0, "Go To LZ", "Fly to LZ Alpha.", waypoint=lz_wpt, trigger_radius=1500)
kill = create_objective("Destroy", 1, "Destroy Tank", "Destroy the tank near the LZ.", prereqs=[fly],
                        targets=[tank_id], min_required=1)
mission.add_objective(fly)
mission.add_objective(kill)

# --- 4. Events: actions come from the game's own [VTEvent] list ---
mission.add_trigger_event(Trigger(
    id=0, name="Near LZ", trigger_type="Proximity", waypoint=lz_wpt, radius=3000,
    spherical_radius=False, trigger_mode="Player", proxy_mode="OnEnter",
    event_targets=[SystemActions().display_message("Tank spotted near the LZ!", 5.0)]))
mission.rtb_wpt_id = lz_wpt
mission.add_briefing_note("Proceed to LZ Alpha. Expect light resistance.")

# --- 5. Save (writes <folder>/pytol_quickstart/pytol_quickstart.vts plus the map) ---
print("Saved to:", mission.save_mission(os.path.join(VTOL_VR_PATH, "CustomScenarios")))
```

**Note:** `save_mission()` creates a folder structure with the mission file and map data inside.

## Map Selection and Realism Tips

- Prefer maps with HeightMap terrain for best results with Pytol's terrain sampler. Recommended: `hMap2`, `costaOeste`, `Archipielago_1`.
- The map `Akutan` is primarily mesh-based (not heightmap-generated), so it can not be used with this library.
- Even with our accurate recreation, expect small height mismatches of up to ~1 m in some spots (bilinear vs mesh interpolation, collider differences). Always validate spawns in-game or add a small offset.

## Terrain Integration Workflow

Pytol mirrors VTOL VR's terrain pipeline on mission load. Use the shared `TerrainCalculator` and `MissionTerrainHelper` instances exposed by `Mission` instead of sampling ad-hoc. The terrain internals are described in [Terrain Behavior](terrain_behavior.md).

1. **Baseline placement:** `mission.tc.get_asset_placement(x, z, yaw)` returns a terrain-aligned `(position, rotation)` tuple that reproduces the editor’s snap-to-ground.
2. **Smart placement:** `mission.tc.get_smart_placement(x, z, yaw)` inspects static prefabs, road splines, and procedural city tiles extracted from the game assets. It will attach vehicles to roads, parking pads, rooftops, or open terrain exactly like the in-game placement gizmos.
3. **High-level searches:** `mission.helper` exposes tactical queries (`find_flat_landing_zones`, `get_road_path`, `find_observation_post`, `has_line_of_sight`) built on the same terrain data.
4. **Base and runway data:** `mission.add_unit_at_base_spawn(...)` pulls spawn pads from the packaged base spawn database, guaranteeing taxi paths and runway headings line up with the game's own data.

Always reuse these helpers when building new features—hand-authored coordinates drift over time as the game's assets change, while the calculators stay synchronized with the data extracted from the game.

## Core Concepts

### Mission Object

`Mission` is a complete VTOL VR scenario (`.vts`). It loads the map once and exposes the terrain tools.

```python
mission = Mission(
    scenario_name="Mission Title",            # display name in game
    scenario_id="my_mission_01",              # unique id, also the output folder name
    description="Mission description",
    vehicle="F/A-26B",                        # player aircraft (default "AV-42C")
    map_id="hMap2",                           # map folder inside CustomMaps (case-sensitive)
    vtol_directory=r"C:\...\VTOL VR",         # game install; or pass map_path=<map folder> directly
    verbose=True,
)
mission.tc          # TerrainCalculator: heights, normals, roads, cities, bases
mission.helper      # MissionTerrainHelper: tactical queries (flat zones, choke points, line of sight)

mission.scenario_name = "New title"           # these can be changed until you save
mission.rtb_wpt_id = home_waypoint            # return-to-base waypoint (object or id)
mission.bullseye_id = bullseye_waypoint.id
mission.env_name = "Night"                    # built-in time of day, or "Custom" with mission.custom_time_of_day = 18.6
mission.add_briefing_note("Text shown in the briefing")
```

### Units

```python
from pytol import create_unit

# create_unit(unit id, name, team, [x, y, z], [pitch, yaw, roll], **fields)
sam = create_unit("SamBattery1", "SAM 1", "Enemy", [x, 0, z], [0, 180, 0])
sam_id = mission.add_unit(sam, placement="ground")      # "ground" snaps to terrain, roads and roofs; "airborne" keeps y

mission.add_unit_to_group("Enemy", "Alpha", sam_id)      # unit groups (AI orders, shared callsign)
```

- Unit ids and their fields are in `pytol.classes.units` (`ID_TO_CLASS`); unknown fields raise an error.
- Teams: `"Allied"` or `"Enemy"`. The prefab decides which side a unit id belongs to.
- Stationary units (fixed SAMs, radars, structures) cannot join unit groups.
- Aircraft that start at an airbase use `mission.add_unit_at_base_spawn(unit, base_index=..., category="hangar")`, see
  Base Spawn Points below.
- Unit actions come from the unit itself: `unit.actions.set_orbit_now(waypoint, radius, altitude)`.

### Terrain-Aware Placement

`placement="ground"` already uses `get_smart_placement`. Call the terrain tools directly for searches:

```python
tc = mission.tc
y = tc.get_terrain_height(x, z)
tc.get_terrain_normal(x, z)                         # surface normal, for slope tests
tc.is_area_clear(x, z, radius)                      # no building or static prefab within radius (open lots count as clear)
tc.get_smart_placement(x, z, yaw_degrees=90)        # {'position', 'rotation'} on a roof, road, bridge or terrain
tc.get_road_route((x0, z0), (x1, z1))               # [(x, y, z), ...] over the road network, or []
mission.helper.find_flat_landing_zones(x, z, search_radius=5000, min_area_radius=30)
```

### Waypoints and paths

```python
from pytol import Waypoint, Path

wp = Waypoint(name="IP", global_point=[x, y, z])
mission.add_waypoint(wp)                            # returns the id; the object can be used wherever an id is expected
route = Path(name="Convoy", points=[[x0, y0, z0], [x1, y1, z1]], loop=False, path_mode="Linear")
mission.add_path(route)
```

Ground units only follow roads on `Linear` paths.

### Objectives

`create_objective(type, id, name, info, ...)` returns an objective of one of the game's types:

| Type | Typical fields |
|---|---|
| `Fly_To` | `waypoint`, `trigger_radius` |
| `Destroy` | `targets=[unit ids]`, `min_required` |
| `Protect` | `target`, `radius`, `completion_mode` ("Waypoint" or "Trigger") |
| `Land` | `waypoint`, `radius` |
| `Pick_Up` / `Drop_Off` | `targets`, `min_required` (+ `unload_radius`, `dropoff_rally_pt`) |
| `Join` | `target_unit`, `radius` |
| `Refuel` | `targets=[tanker ids]`, `fuel_level` |
| `Conditional` | `success_conditional`, `fail_conditional` (ids of conditionals) |
| `Global_Value` | `current_value`, `target_value` (global values; completes on equality) |

Common arguments: `required` (default True: failing it ends the mission), `prereqs=[objectives]`,
`start_mode="Triggered"` (begins only when an event runs `ObjectiveActions(id).begin_objective()`),
`start_event_targets` / `complete_event_targets` / `fail_event_targets` (lists of actions).

```python
from pytol import create_objective

fly = create_objective("Fly_To", 0, "Ingress", "Fly to the IP.", waypoint=ip, trigger_radius=3000)
kill = create_objective("Destroy", 1, "Strike", "Destroy the depot.", prereqs=[fly], waypoint=target_wpt,
                        targets=depot_ids, min_required=3)
land = create_objective("Land", 2, "Return", "Land at base.", waypoint=home, prereqs=[kill], radius=2500)
for o in (fly, kill, land):
    mission.add_objective(o)
```

### Events: triggers, timers, sequences, random events

Actions are the game's own `[VTEvent]` list (`pytol.classes.actions`): `SystemActions` (messages, spawning, weather,
radio), unit actions (`AIAircraftSpawnActions`, `GroundUnitSpawnActions`...), `ObjectiveActions`, `UnitGroupActions`,
`GlobalValueActions`, `TriggerEventActions`, `EventSequenceActions`, `TimedEventGroupActions`, `BaseActions`.

```python
from pytol import Trigger, TimedEventGroup, TimedEventInfo
from pytol.classes.actions import SystemActions

mission.add_trigger_event(Trigger(                   # fires once
    id=0, name="At the IP", trigger_type="Proximity", waypoint=ip, radius=4000, spherical_radius=False,
    trigger_mode="Player", proxy_mode="OnEnter",
    event_targets=[SystemActions().display_message("Push!", 4.0), SystemActions().spawn_units(interceptor_ids)]))

mission.add_timed_event_group(TimedEventGroup(
    group_name="Check in", group_id=1, begin_immediately=True,
    events=[TimedEventInfo(event_name="hello", time=20.0,
                           event_targets=[SystemActions().display_message("Radar contact.", 4.0)])]))
```

Units with `spawn_on_start=False` appear when an event runs `SystemActions().spawn_units([...])`.

### Conditionals

A conditional is a tree of components (`pytol.classes.conditionals`). Register it once; the id it returns is what
triggers, objectives, sequences and random events reference.

```python
from pytol.classes.conditionals import ConditionalTree, create_conditional

tree = ConditionalTree()
tree.add_comp(0, create_conditional("SCCUnitList", unit_list=[str(i) for i in depot_ids], method_name="SCC_NumAlive",
                                    method_parameters=["Less_Than", 2], is_not=False))
tree.add_comp(1, create_conditional("SCCGlobalValue", gv="alarm", comparison="Greater_Than", c_value=0))
tree.add_comp(2, create_conditional("SCCAnd", factors=[0, 1]))
tree.set_root(2)
cond_id = mission.add_conditional(tree)

mission.add_trigger_event(Trigger(id=1, name="Depot hit", trigger_type="Conditional", conditional=cond_id,
                                  event_targets=[SystemActions().display_message("Depot is burning.", 4.0)]))
```

- `SCCUnit` / `SCCUnitList` call a method of the unit's class (`SCC_AltitudeRadar`, `SCC_NumAlive`,
  `SCC_AnyNearWaypoint`...). The method must exist on that class and the parameters must match: some player conditions
  exist on `PlayerSpawn` but not on `MultiplayerSpawn`. `SCC_Airspeed` takes m/s.
- `SCCAnd` / `SCCOr` have no negation; negate their inputs instead.
- `SCCGlobalValue` compares integers against a global value.

### If / else if / else

`ConditionalAction` is the game's IF / ELSE IF / ELSE statement. It runs when an event fires it
(`SystemActions().fire_conditional_action(id)`).

```python
from pytol import ConditionalAction, ConditionalBlock

ca = ConditionalAction(
    id=0, name="Depot check", conditional_id=cond_id,
    actions=[SystemActions().display_message("Depot is down.", 4.0)],
    else_if=[ConditionalBlock(conditional_id=other_cond_id, name="partly",
                              actions=[SystemActions().display_message("Depot is damaged.", 4.0)])],
    else_actions=[SystemActions().display_message("Depot is intact.", 4.0)],
    # nested=[ConditionalBlock(...)]: evaluated after `actions` when the condition is true
)
mission.add_conditional_action(ca)
mission.add_trigger_event(Trigger(id=2, name="Check", trigger_type="Proximity", waypoint=ip, radius=3000,
                                  spherical_radius=False, trigger_mode="Player", proxy_mode="OnEnter",
                                  event_targets=[SystemActions().fire_conditional_action(ca.id)]))
```

Blocks may hold a conditional object or the id of a registered one.

### Global values (mission variables)

```python
from pytol import GlobalValue
from pytol.classes.actions import GlobalValueActions

mission.add_global_value(GlobalValue(name="alarm", initial_value=0))
bump = GlobalValueActions("alarm").increment_value(1.0)     # also set_value, decrement_value, reset_value, ...
```

Use them in `SCCGlobalValue` conditionals or in a `Global_Value` objective (its two values are compared for equality).

### Event sequences and random events

An `EventSequence` runs nodes in order. Each node waits its `delay`, **then** its `conditional`, **then** fires its
actions. With `while_loop=True` it starts over after the last node. A `RandomEvent` picks one `RandomEventAction` by
weight each time it is fired (`SystemActions().fire_random_event(id)`).

```python
from pytol import EventSequence, SequenceEvent, RandomEvent, RandomEventAction

mission.add_event_sequence(EventSequence(
    id=0, sequence_name="Reinforcements", start_immediately=False,
    events=[SequenceEvent(node_name="wait for the hit", conditional=cond_id, delay=0.0, actions=[]),
            SequenceEvent(node_name="launch", delay=90.0,
                          actions=[SystemActions().spawn_units(interceptor_ids)])]))   # 90 s after the hit
mission.add_random_event(RandomEvent(id=0, name="Axis", action_options=[
    RandomEventAction(id=0, action_name="north", fixed_weight=60, actions=[...]),
    RandomEventAction(id=1, action_name="south", fixed_weight=40, actions=[...])]))
```

Start a sequence with `EventSequenceActions(id).begin_event()`, stop it with `.stop()`.

### Base Spawn Points

Use the Base Spawn Points system to place units precisely at airbases (hangars, helipads, large aircraft aprons) and to reference base facilities (runway endpoints, control tower, barracks) for objectives/waypoints.

- Spawn points: hangar, helipad/heli, bigplane
- Reference points: runway, controltower/tower, barracks

Two ways to use it:

1) Mission helper (quickest)

```python
from pytol import create_unit

# Add a unit at a base spawn point
# - base_index: choose which base on the map (0 = first)
# - category: 'hangar' | 'helipad' | 'bigplane'
# - spawn_index: 0 = first, -1 = random within category

player = create_unit(
    id_name="PlayerSpawn",
    unit_name="Player",
    team="Allied",
)

# First airbase, first hangar
mission.add_unit_at_base_spawn(player, base_index=0, category='hangar', spawn_index=0)

# Second airbase, random helipad
heli = create_unit(id_name="HeliSpawn", unit_name="Allied Heli", team="Allied")
mission.add_unit_at_base_spawn(heli, base_index=1, category='helipad', spawn_index=-1)

# First base of a specific type
ai = create_unit(id_name="AI", unit_name="Wingman", team="Allied")
mission.add_unit_at_base_spawn(ai, base_type='airbase2', category='hangar')
```

2) Direct utilities (more control)

```python
from pytol import create_unit, Waypoint
from pytol.resources.base_spawn_points import (
    get_available_bases,
    select_spawn_point,
    get_spawn_points,
    get_reference_points,
    compute_world_from_base,
)

# Get bases (optionally filter by prefab type)
bases = get_available_bases(mission.tc, prefab_type=None)  # 'airbase1' | 'airbase2' | 'airbase3'
base = bases[0]

# Choose a spawn point by category and index
pos, yaw = select_spawn_point(base, category='hangar', index=0)
unit = create_unit(id_name="PlayerSpawn", unit_name="Player", team="Allied",
                   global_position=pos, rotation=[0, yaw, 0])
mission.add_unit(unit, placement="ground", use_smart_placement=False, align_to_surface=False)

# Or list points and transform manually
spawns = get_spawn_points(base['prefab_type'], 'helipad')
((x, y, z), yaw) = compute_world_from_base(base, spawns[0]['offset'], spawns[0]['yaw_offset'])

# Reference points for objectives/waypoints (not for spawning)
runway_pts = get_reference_points(base['prefab_type'], 'runway')  # usually 2 endpoints
r0, yaw0 = compute_world_from_base(base, runway_pts[0]['offset'], runway_pts[0]['yaw_offset'])
r1, yaw1 = compute_world_from_base(base, runway_pts[1]['offset'], runway_pts[1]['yaw_offset'])

# Example: waypoint along runway centerline
wpt0 = Waypoint(name="Takeoff Start", position=r0)
wpt1 = Waypoint(name="Runway End", position=r1)
mission.add_waypoint(wpt0)
mission.add_waypoint(wpt1)
```

Notes:
- Spawn categories are for unit placement; reference categories are for navigation/objectives.
- Works across maps because points are base-local offsets relative to prefab orientation.
- Supported prefab types today: 'airbase1', 'airbase2', 'airbase3'.
- See examples/example_base_spawns.py for a full walkthrough.


## Resources

Resources allow you to include custom audio, imagery, and other mission assets. Pytol registers each asset in the ResourceManifest and copies files into the mission folder when you call `save_mission()`.

### Adding Audio Briefings

```python
mission.add_resource(
    res_id=1,
    path=r"C:\MyMissions\audio\briefing.wav"
)
```

The audio file is copied to `<mission_folder>/audio/briefing.wav` at save time.

### Adding Custom Images

```python
mission.add_resource(
    res_id=2,
    path=r"./images/tactical_map.png"
)
```

Images are copied to `<mission_folder>/images/tactical_map.png` during the same pass.

### Resource IDs

- Resource IDs must be unique integers (reuse logs a warning and overwrites the previous entry)
- Reserve consistent ranges (e.g., 1xx for audio, 2xx for imagery) to keep manifests tidy
- The game looks up resources by ID when rendering briefing notes and HUD overlays

### Supported File Types

- **Audio**: `.wav`, `.ogg`, `.mp3` – copied to the `audio/` subdirectory
- **Images**: `.png`, `.jpg`, `.jpeg`, `.bmp` – copied to the `images/` subdirectory
- Any other extension is routed to `resources/` and emits a warning so you can verify VTOL VR compatibility

### Referencing Resources in Mission Blocks

- Always reference the *relative* path that will exist inside the mission folder (`audio/...`, `images/...`) when populating dataclasses such as `BriefingNote`
- Pytol rewrites absolute source paths to a relative path during `save_mission()`; missing files generate a `?` warning and the manifest entry is removed
- Example linking a briefing note to an audio clip:

```python
from pytol.classes.mission_objects import BriefingNote

mission.add_resource(3, r"E:\Audio\intro.wav")
mission.add_briefing_note(
    BriefingNote(
        text="Secure the airspace south of Bravo Base.",
        audio_clip_path="audio/intro.wav",
    )
)
```

### Example: Complete Mission with Audio Briefing

```python
from pytol import Mission

mission = Mission(
    scenario_name="Operation Desert Storm",
    scenario_id="desert_storm",
    description="Strike enemy command center",
    map_id="hMap2"
)

mission.add_resource(1, "path/to/briefing.wav")

# Add units, objectives, etc...

mission.save_mission("./output")
```

When you call `save_mission()`, Pytol will:
1. Create the mission directory structure
2. Copy the map files
3. Copy every registered resource into `audio/`, `images/`, or `resources/`
4. Generate the `.vts` file with manifest entries pointing to the relative paths

## Tips and Best Practices

### Terrain Placement
- Use `mission.add_unit(..., placement="ground")` for ground units and parked aircraft: it uses the smart placement
- For ships, use `y=0` (sea level); for airborne aircraft set the altitude yourself
- Check an area with `tc.is_area_clear(x, z, radius)` before placing something big in a town

### Objectives
- A required objective that fails ends the mission: make plan A optional when you add a plan B
- Objectives that start `Triggered` need an event that begins them
- Combine a `Conditional` objective with a global value for goals the standard types do not cover

### Testing
- Run `pytol.parsers.vts_validator` on the saved file: it applies the loader's own rules
- Test missions in-game before distributing
- Use descriptive unit names for debugging

## Troubleshooting

### Units spawn underground
- Use `placement="ground"` in `add_unit` (or `tc.get_smart_placement`)
- Verify `map_id` matches the CustomMaps folder name exactly
- Check that the VTOL VR directory path is correct

### Mission doesn't load
- Verify `map_id` matches map folder name (case-sensitive)
- Ensure all unit IDs are unique
- Check that required objectives exist

### Objectives don't trigger
- Check that `targets` are ids returned by `add_unit` and that the units are spawned
- A `Triggered` objective needs an event that begins it
- A conditional method must exist on the unit's class and take the parameters you pass

### Terrain heights seem wrong
- Some maps (e.g., hm_mtnLake) have encoding issues - see `terrain_behavior.md`
- Use `height_scale` and `height_offset` parameters if needed (experimental)
- Validate with known reference points from in-game

## Visualizing Your Mission

Once your mission is created, you can generate professional maps for briefings:

### 2D Static Maps (Lightweight)

```python
# Install: pip install pytol[viz-light]
from pytol import Map2DVisualizer

# Generate clean professional overview
viz = Map2DVisualizer(mission, figsize=(12, 12), dpi=150)
viz.save_mission_overview("mission_briefing.png", clean_mode=True)

# Generate detailed terrain view
viz.save_terrain_overview("terrain_analysis.png", style='heatmap')

# Generate spawn points detail for pilots
viz.save_spawn_points_detail("spawn_points.png", base_index=0)
```

### 3D Interactive Exploration

```python
# Install: pip install pytol[viz]
from pytol import MissionVisualizer

# Interactive 3D visualization
viz = MissionVisualizer(mission)
viz.show()
```

## See Also

- [2D Visualization Guide](../pytol/visualization/README_2D.md) - Complete 2D visualization documentation
- [3D Visualization Guide](../pytol/visualization/README.md) - Interactive 3D visualization
- [Terrain Behavior Documentation](terrain_behavior.md) - Height sampling and city behavior
- [API Reference](../README.md) - Complete API documentation
