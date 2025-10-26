# Procedural Mission Engine

This package provides complete procedural mission generation with terrain-aware unit placement, intelligent objectives, and player spawning at airbases. It generates fully playable missions ready for VTOL VR.

The engine creates missions with route planning, enemy unit placement, mission-specific objectives, and automatic player spawning using the Base Spawn Points system.

## API

- `pytol.procedural.ProceduralMissionSpec` – inputs for generation
- `pytol.procedural.ProceduralMissionEngine` – facade, single `generate(spec)` method

Key internal modules (placeholders):
- ControlMap, ThreatMap – spatial control and hazard fields
- TimingModel, AltitudePolicy – pace and AGL policies
- StrategySelector – ingress/egress and target anchor selection
- ObjectiveManager, EventGraph, SpawnController, PacingEngine, RadioCommsHelper, EnvironmentController – orchestration helpers

## Minimal usage

```python
from pytol.procedural import ProceduralMissionSpec, ProceduralMissionEngine, TargetBias

spec = ProceduralMissionSpec(
    scenario_id="proc_demo_01",
    scenario_name="Procedural Demo (stub)",
    description="Scaffolded mission",
    vehicle="AV-42C",
    map_id="afMtnsHills",              # or use map_path
    vtol_directory="F:/SteamLibrary/steamapps/common/VTOL VR",
    mission_type="random",             # let the engine pick
    difficulty="random",
    duration_minutes=None,              # let the engine pick
    time_of_day=None,                   # let the engine pick (env apply is placeholder)
    # Optional target selection:
    # - Legacy flags:
    #   prefer_cities=True,
    #   prefer_roads=True,
    #   prefer_open=True,
    #   avoid_water=True,
    # - OR use a single numeric bias:
    #   target_bias=TargetBias(cities=0.5, roads=0.2, open=0.0, water=1.0),
)
mission = ProceduralMissionEngine(verbose=True).generate(spec)
# mission.save_mission(<VTOL VR CustomScenarios path>)
```

Notes:
- If `vtol_directory` is omitted, `Mission` will try to use the `VTOL_VR_DIR` env var.
- Saving the mission copies the map folder into the mission directory as usual.

## Roadmap

- ✅ v0: route planning and altitude policy hooked to actual waypoints
- ✅ v1: objective placement, unit templates, triggers/actions/event sequences
- ✅ v1.5: Validation & error handling, intelligent unit placement, mission-specific objectives
- v2: campaign-engine integration via the `ProceduralMissionSpec`/results contract

## Mission-Specific Objectives

The engine now creates objectives tailored to each mission type:

**Strike Missions:**
- Primary: Navigate to strike zone
- Secondary: Destroy enemy ground units (difficulty-scaled requirements)

**SEAD Missions:**
- Primary: Approach SEAD zone
- Secondary: Suppress air defenses (destroy all SAMs and radars)

**CAS Missions:**
- Primary: Enter CAS area
- Secondary: Eliminate ground threats (destroy 2/3 of enemy units)

**Intercept Missions:**
- Primary: Navigate to intercept zone (spherical trigger for 3D combat)
- Secondary: Destroy enemy aircraft

**Transport Missions:**
- Primary: Navigate to pickup zone
- (Dropoff zone planned for future update)

All Destroy objectives automatically reference the spawned enemy units, ensuring objectives are achievable and relevant to the mission.

## Player Spawning

The procedural engine automatically places the player at the most appropriate location:

**Cold Start at Airbases (Default):**
- When airbases are detected on the map, the engine selects the closest base to the ingress waypoint
- Uses the **Base Spawn Points** system to place the player at a precise hangar location
- The player spawns with accurate position and orientation using the database of 83+ mapped spawn points
- Supports airbase1, airbase2, and airbase3 prefabs
- Fallback: If spawn points aren't available, uses the base's flatten zone centroid

**Flight-Ready Start (Fallback):**
- If no airbases are found on the map, the player spawns airborne at the ingress waypoint
- Oriented toward the target with a default speed of 180 knots
- Positioned at the mission's target AGL (altitude above ground level)

The spawn point system ensures realistic hangar placement that works across all maps with supported airbase prefabs. See the [mission creation guide](mission_creation.md#base-spawn-points) for manual usage of spawn points in custom missions.

## Intelligent Unit Placement

For **Strike** and **SEAD** missions, units are placed using terrain-aware tactical positioning:

- **Placement Zones**: Units are clustered into 2-3 tactical zones based on terrain analysis
- **Terrain Scoring**: Positions are evaluated for:
  - City density (urban vs. open)
  - Slope/defensibility (hills for defensive positions)
  - Road proximity (easier deployment)
  - Water avoidance
- **Mission-Aware**: Strike missions prefer urban areas; SEAD prefers defensive high ground
- **Fallback**: Other mission types use validated random placement within radius

This creates more realistic and challenging enemy deployments compared to pure random placement.

## Validation & Error Handling

The engine includes comprehensive validation to prevent generation failures:

**Route Validation:**
- Checks ingress/egress distances against map size
- Ensures minimum distances (1km) for realistic approach paths
- Maximum distance capped at 80% of map size

**Target Validation:**
- Verifies target is within map bounds
- Checks terrain height validity
- Rejects water targets for strike/cas/sead missions
- Provides clear error messages on failure

**Spawn Location Validation:**
- Validates each unit spawn point (with up to 10 retry attempts)
- Prevents spawning ground units in water
- Checks map bounds and terrain height
- Skips problematic units rather than failing entire mission

**Waypoint Validation:**
- Warns if waypoints are too close together (<500m)
- Ensures reasonable spacing for flight paths

**Error Types:**
```python
from pytol.procedural import (
    ProceduralGenerationError,      # Base exception
    InvalidTargetError,              # No valid target found
    InvalidRouteError,               # Route parameters invalid
    InvalidSpawnLocationError,       # Cannot place units
)
```

The engine is resilient: it will retry failed placements, skip problematic units, and provide detailed logging when `verbose=True`.

## Unit Spawning & Team Validation

The engine includes a validated unit library that ensures units can only be spawned on appropriate teams:

- **Enemy-specific units** (e.g., `enemyMBT1`, `ELogisticsTruck`, `EnemySoldier`) can only be assigned to the Enemy team
- **Allied-specific units** (e.g., `alliedMBT1`, `ALogisticTruck`, `AlliedSoldier`) can only be assigned to the Allied team  
- **Generic units** (e.g., `F-45A AI`, `SamBattery1`, `staticAAA-20x2`) can be used by either team

The validation is based on the official VTOL VR unit database and happens automatically when creating unit templates. If you try to assign a unit to an invalid team, you'll get a `ValueError` with details about which teams are allowed.

### Utility functions

```python
from pytol.procedural.unit_templates import UnitLibrary

# Check if a unit can be used by a team
is_valid = UnitLibrary.validate_unit_team('enemyMBT1', 'Enemy')  # True
is_valid = UnitLibrary.validate_unit_team('enemyMBT1', 'Allied')  # False

# Get all units available for a team
enemy_units = UnitLibrary.get_available_units_for_team('Enemy')
allied_units = UnitLibrary.get_available_units_for_team('Allied')
```

## Randomization & reproducibility

- Set `mission_type="random"`, `difficulty="random"`, `time_of_day=None`, `duration_minutes=None` to allow the engine to choose sensible defaults.
- Provide `seed=<int>` in the spec to make the choices deterministic across runs.
- Weather and time-of-day choices are recorded in the briefing; environment application is a placeholder for now.

## Target selection preferences and bias

- The engine samples target candidates across the whole map and scores them by mission type.
- Nudge selection using:
    - Legacy convenience flags on `ProceduralMissionSpec`:
    - `prefer_cities`: tilt towards urban areas.
    - `prefer_roads`: small bonus near roads (within ~800 m).
    - `prefer_open`: tilt towards open/non-urban areas.
    - `avoid_water`: reject points at or near sea level (default True).
    - Or a single `TargetBias` object with numeric weights:
             - `cities` (float): weight for city density (0..1 range)
             - `roads` (float): weight for road proximity
             - `open` (float): weight for open areas (1 - city density)
             - `water` (float): penalty weight if near sea level (set > 0 to avoid water strongly)

Both approaches are seed-deterministic and layer on top of mission-type defaults.
