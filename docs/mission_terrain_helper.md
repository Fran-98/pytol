# MissionTerrainHelper Guide

The `MissionTerrainHelper` class provides high-level tactical terrain analysis for mission creation in VTOL VR. It wraps around the `TerrainCalculator` and offers mission-oriented queries like finding observation posts, hidden positions, landing zones, and calculating tactical routes.

## Table of Contents

- [Overview](#overview)
- [Initialization](#initialization)
- [Core Features](#core-features)
  - [Terrain Queries](#terrain-queries)
  - [Tactical Position Finding](#tactical-position-finding)
  - [Pathfinding](#pathfinding)
  - [Formation Generation](#formation-generation)
  - [Line of Sight](#line-of-sight)
  - [Threat Analysis](#threat-analysis)
- [Complete Examples](#complete-examples)
- [Best Practices](#best-practices)

---

## Overview

The `MissionTerrainHelper` is designed to answer common mission design questions:

- "Where can I place an observation post overlooking this area?"
- "Find a hidden spot for a CSAR insertion within 5km of this location"
- "Generate a low-altitude approach path that avoids enemy SAMs"
- "What are good positions for artillery that can hit this target?"

It combines multiple terrain analysis techniques to provide tactically relevant results.

---

## Initialization

### Basic Initialization

```python
from pytol import MissionTerrainHelper

# Create helper from a map name
helper = MissionTerrainHelper(
    map_name="hMap2",
    vtol_directory="C:/Program Files (x86)/Steam/steamapps/common/VTOL VR"
)
```

### With Existing TerrainCalculator

```python
from pytol import TerrainCalculator, MissionTerrainHelper

# First create a TerrainCalculator
tc = TerrainCalculator(map_name="hMap2", vtol_directory="...")

# Then create helper using the existing calculator
helper = MissionTerrainHelper(terrain_calculator=tc)
```

### Parameters

- `terrain_calculator` (optional): Existing `TerrainCalculator` instance
- `map_name` (optional): Map name if creating new TerrainCalculator
- `vtol_directory` (optional): Path to VTOL VR installation
- `map_directory_path` (optional): Direct path to map directory

**Note:** Either provide `terrain_calculator` OR the parameters needed to create one.

---

## Core Features

### Terrain Queries

#### `find_flat_area()`

Find flat areas suitable for landing zones or base placement.

```python
# Find a flat area near coordinates
flat_spots = helper.find_flat_area(
    center_x=50000,
    center_z=50000,
    search_radius=5000,      # Search within 5km
    min_flatness=0.9,        # Require 90% of area to be flat
    area_size=50,            # Need 50x50m flat area
    max_slope=5.0,           # Maximum 5° slope
    num_samples=20           # Check 20 candidate positions
)

for spot in flat_spots:
    print(f"Flat area at ({spot['x']}, {spot['z']}) - Flatness: {spot['flatness']:.2%}")
```

**Use Cases:**
- Emergency landing zones
- FOB placement
- Artillery positions
- Helicopter landing pads

---

#### `find_elevated_positions()`

Find high-ground positions for observation or defense.

```python
# Find hilltops overlooking an area
elevated = helper.find_elevated_positions(
    center_x=100000,
    center_z=100000,
    search_radius=3000,
    min_height_advantage=50,  # At least 50m above surroundings
    num_samples=15
)

for pos in elevated:
    print(f"Elevated at ({pos['x']}, {pos['z']}) - Height: {pos['height']:.1f}m, "
          f"Advantage: {pos['height_advantage']:.1f}m")
```

**Use Cases:**
- Observation posts (OP)
- Sniper positions
- Early warning radar sites
- Command posts

---

#### `find_concealed_positions()`

Find positions with natural concealment (depressions, terrain folds).

```python
# Find hidden positions for covert operations
hidden = helper.find_concealed_positions(
    center_x=75000,
    center_z=75000,
    search_radius=2000,
    min_concealment=0.6,    # Require 60% concealment score
    check_radius=100,        # Check 100m around each point
    num_samples=25
)

for pos in hidden:
    print(f"Concealed at ({pos['x']}, {pos['z']}) - "
          f"Concealment: {pos['concealment_score']:.2%}")
```

**Concealment Score Factors:**
- Below average terrain (depressions)
- Terrain roughness (nearby ridges/hills for cover)
- Distance from roads (less likely to be discovered)

**Use Cases:**
- CSAR insertion zones
- Guerrilla hideouts
- Ambush positions
- Cache locations

---

### Tactical Position Finding

#### `find_observation_posts()`

Find positions with good visibility and elevation over a target area.

```python
# Find OP overlooking enemy base
ops = helper.find_observation_posts(
    target_x=155000,
    target_z=38000,
    search_center_x=150000,
    search_center_z=35000,
    search_radius=8000,
    min_height_advantage=100,
    require_los=True,         # Must have line of sight
    num_candidates=30
)

for op in ops:
    print(f"OP at ({op['x']}, {op['z']}) - "
          f"Distance: {op['distance_to_target']:.0f}m, "
          f"Height advantage: {op['height_advantage']:.0f}m")
```

**Use Cases:**
- Forward air controller (FAC) positions
- Reconnaissance overwatch
- Artillery spotters
- Surveillance positions

---

#### `find_indirect_fire_positions()`

Find positions suitable for artillery or mortar fire on a target.

```python
# Find artillery positions that can hit the target
artillery_pos = helper.find_indirect_fire_positions(
    target_x=120000,
    target_z=60000,
    search_center_x=115000,
    search_center_z=55000,
    search_radius=5000,
    min_distance=2000,        # At least 2km from target
    max_distance=15000,       # Within 15km range
    prefer_defilade=True,     # Prefer hull-down positions
    num_candidates=20
)

for pos in artillery_pos:
    print(f"Fire position at ({pos['x']}, {pos['z']}) - "
          f"Range: {pos['distance_to_target']:.0f}m, "
          f"Defilade: {'Yes' if pos['is_defilade'] else 'No'}")
```

**Defilade:** Position is lower than surrounding terrain, providing protection from direct fire.

**Use Cases:**
- Artillery batteries
- Mortar teams
- Rocket artillery (MLRS)

---

#### `find_choke_points()`

Identify terrain bottlenecks suitable for ambushes or defense.

```python
# Find choke points along an axis
chokes = helper.find_choke_points(
    start_x=50000,
    start_z=50000,
    end_x=60000,
    end_z=55000,
    num_samples=30,
    narrowness_threshold=0.3  # Lower = narrower passages
)

for choke in chokes:
    print(f"Choke point at ({choke['x']}, {choke['z']}) - "
          f"Narrowness: {choke['narrowness_score']:.2f}")
```

**Narrowness Score:** Based on surrounding terrain variance and elevation changes.

**Use Cases:**
- Ambush sites
- Defensive positions
- Roadblock locations
- Interdiction zones

---

### Pathfinding

#### `get_road_path()`

Generate a path that follows roads between two points.

```python
# Create route following roads
road_path = helper.get_road_path(
    start_x=50000,
    start_z=50000,
    end_x=80000,
    end_z=70000,
    road_snap_distance=50,    # Snap to roads within 50m
    max_off_road_distance=200 # Allow 200m off-road segments
)

if road_path:
    print(f"Road path with {len(road_path)} waypoints")
    for i, point in enumerate(road_path):
        print(f"  {i}: ({point['x']:.0f}, {point['y']:.0f}, {point['z']:.0f})")
```

**Use Cases:**
- Ground convoy routes
- AI vehicle waypoints
- Planned patrol routes

---

#### `get_terrain_following_path()`

Generate low-altitude path following terrain contours.

```python
# Create terrain-hugging flight path
path = helper.get_terrain_following_path(
    start_x=40000,
    start_z=40000,
    end_x=60000,
    end_z=60000,
    altitude_agl=100,         # 100m above ground
    num_waypoints=15,
    smoothness=0.8            # Smooth path (0.0=direct, 1.0=very smooth)
)

for wp in path:
    print(f"Waypoint: ({wp['x']:.0f}, {wp['y']:.0f}, {wp['z']:.0f})")
```

**Use Cases:**
- Helicopter insertion routes
- Low-level penetration flights
- Cruise missile paths

---

#### `get_threat_avoiding_path()`

Generate path that avoids known threat positions (SAMs, AAA).

```python
# Define threat positions and ranges
threats = [
    {'x': 70000, 'z': 70000, 'range': 15000},  # SA-10 site
    {'x': 75000, 'z': 68000, 'range': 8000},   # AAA battery
]

# Generate safe path
safe_path = helper.get_threat_avoiding_path(
    start_x=50000,
    start_z=50000,
    end_x=90000,
    end_z=85000,
    threats=threats,
    safety_margin=2000,       # Stay 2km beyond threat range
    altitude=1000,            # Flight altitude
    num_waypoints=10
)

for wp in safe_path:
    print(f"Safe waypoint: ({wp['x']:.0f}, {wp['y']:.0f}, {wp['z']:.0f})")
```

**Use Cases:**
- Strike ingress/egress routes
- SEAD corridor planning
- Safe transit routes

---

### Formation Generation

#### `generate_formation_points()`

Create geometric formations for unit placement.

```python
# Create wedge formation for ground units
formation = helper.generate_formation_points(
    center_x=100000,
    center_z=100000,
    num_units=5,
    formation_type="wedge",   # "line", "wedge", "circle", "column"
    spacing=50,               # 50m between units
    heading=45                # Formation facing 45°
)

for i, pos in enumerate(formation):
    print(f"Unit {i}: ({pos['x']:.1f}, {pos['z']:.1f})")
```

**Formation Types:**
- `"line"` - Horizontal line
- `"wedge"` - V-shaped wedge
- `"circle"` - Circular perimeter
- `"column"` - Vertical column
- `"box"` - Box/square formation (requires exact square number of units)

**Use Cases:**
- Infantry squad placement
- Vehicle convoys
- CAP station positions
- Defensive perimeters

---

### Line of Sight

#### `check_line_of_sight()`

Check if two positions have unobstructed line of sight.

```python
# Check if OP can see target
has_los = helper.check_line_of_sight(
    x1=50000, z1=50000,
    x2=55000, z2=52000,
    height_offset_1=2.0,  # Observer eye height
    height_offset_2=2.0,  # Target height
    num_samples=50        # Check 50 points along the line
)

if has_los:
    print("Clear line of sight")
else:
    print("LOS blocked by terrain")
```

**Use Cases:**
- Validate observation post positions
- Check weapon system coverage
- Verify radar/sensor coverage

---

#### `get_visible_area()`

Calculate all positions visible from a given point.

```python
# Find everything visible from hilltop
visible = helper.get_visible_area(
    observer_x=80000,
    observer_z=80000,
    observer_height_offset=10,  # 10m tower/mast
    max_range=5000,             # Check 5km radius
    angular_resolution=15,      # Check every 15°
    range_samples=20            # Check 20 distance steps
)

print(f"Visible area coverage: {len(visible)} positions")
for pos in visible[:10]:  # Show first 10
    print(f"  Can see ({pos['x']:.0f}, {pos['z']:.0f}) at {pos['distance']:.0f}m")
```

**Use Cases:**
- Radar coverage maps
- Sensor placement optimization
- Overwatch sector calculation

---

### Threat Analysis

#### `calculate_threat_exposure()`

Calculate how exposed a position is to known threats.

```python
# Check how exposed a position is
threats = [
    {'x': 60000, 'z': 60000, 'range': 10000, 'type': 'SAM'},
    {'x': 62000, 'z': 58000, 'range': 5000, 'type': 'AAA'},
]

exposure = helper.calculate_threat_exposure(
    test_x=55000,
    test_z=55000,
    threats=threats,
    height=1000  # Aircraft altitude
)

print(f"Threat exposure: {exposure['total_exposure']:.2f}")
print(f"Threatening units: {exposure['num_threats_in_range']}")
for threat in exposure['active_threats']:
    print(f"  - {threat['type']} at {threat['distance']:.0f}m")
```

**Use Cases:**
- Route planning
- Target prioritization
- Risk assessment

---

## Complete Examples

### Example 1: CSAR Mission Setup

```python
from pytol import MissionTerrainHelper, Mission, create_unit

helper = MissionTerrainHelper(map_name="hMap2", vtol_directory="...")

# Find concealed insertion LZ near crash site
crash_x, crash_z = 100000, 50000
insertion_zones = helper.find_concealed_positions(
    center_x=crash_x,
    center_z=crash_z,
    search_radius=3000,
    min_concealment=0.7,
    num_samples=30
)

# Pick best LZ (highest concealment)
best_lz = max(insertion_zones, key=lambda x: x['concealment_score'])
print(f"LZ: ({best_lz['x']}, {best_lz['z']}) - Concealment: {best_lz['concealment_score']:.0%}")

# Find overwatch position
overwatch = helper.find_observation_posts(
    target_x=crash_x,
    target_z=crash_z,
    search_center_x=best_lz['x'],
    search_center_z=best_lz['z'],
    search_radius=1500,
    min_height_advantage=30,
    require_los=True,
    num_candidates=20
)

if overwatch:
    op_pos = overwatch[0]
    print(f"Overwatch OP: ({op_pos['x']}, {op_pos['z']})")
```

---

### Example 2: Artillery Strike Planning

```python
# Target enemy base
target_x, target_z = 155000, 38000

# Find firing positions 5-12km away
fire_positions = helper.find_indirect_fire_positions(
    target_x=target_x,
    target_z=target_z,
    search_center_x=target_x - 8000,
    search_center_z=target_z - 8000,
    search_radius=5000,
    min_distance=5000,
    max_distance=12000,
    prefer_defilade=True,
    num_candidates=20
)

# Pick position with best defilade
best_pos = max(fire_positions, key=lambda x: x['is_defilade'])
print(f"Artillery position: ({best_pos['x']}, {best_pos['z']}) "
      f"at {best_pos['distance_to_target']:.0f}m range")

# Create formation for battery
battery_positions = helper.generate_formation_points(
    center_x=best_pos['x'],
    center_z=best_pos['z'],
    num_units=6,
    formation_type="line",
    spacing=80,
    heading=0
)

# Place artillery units
mission = Mission(...)
for i, pos in enumerate(battery_positions):
    arty = create_unit(
        id_name="ArtilleryUnitSpawn",
        unit_name=f"Arty {i+1}",
        team="Allied",
        global_position=[pos['x'], 0, pos['z']]
    )
    mission.add_unit(arty, placement="ground")
```

---

### Example 3: Low-Level Penetration Route

```python
# Plan route avoiding SAM coverage
threats = [
    {'x': 80000, 'z': 80000, 'range': 25000},  # Long-range SAM
    {'x': 90000, 'z': 75000, 'range': 12000},  # Medium SAM
]

penetration_route = helper.get_threat_avoiding_path(
    start_x=50000,
    start_z=50000,
    end_x=100000,
    end_z=85000,
    threats=threats,
    safety_margin=3000,
    altitude=300,  # Low altitude
    num_waypoints=12
)

# Add terrain-following between waypoints
detailed_path = []
for i in range(len(penetration_route) - 1):
    wp1 = penetration_route[i]
    wp2 = penetration_route[i + 1]
    
    segment = helper.get_terrain_following_path(
        start_x=wp1['x'],
        start_z=wp1['z'],
        end_x=wp2['x'],
        end_z=wp2['z'],
        altitude_agl=100,
        num_waypoints=8,
        smoothness=0.7
    )
    detailed_path.extend(segment)

print(f"Detailed route: {len(detailed_path)} waypoints")
```

---

## Best Practices

### 1. **Start with Large Search Radii**

When looking for tactical positions, start with broader searches and refine:

```python
# First pass: large area, fewer samples
candidates = helper.find_elevated_positions(
    center_x=x, center_z=z,
    search_radius=10000,
    num_samples=20
)

# Second pass: refine around best candidate
if candidates:
    best = candidates[0]
    refined = helper.find_elevated_positions(
        center_x=best['x'], center_z=best['z'],
        search_radius=2000,
        num_samples=50  # More samples, smaller area
    )
```

### 2. **Validate Results**

Always check if results meet your requirements:

```python
flat_areas = helper.find_flat_area(...)

# Filter results
suitable_lzs = [
    area for area in flat_areas 
    if area['flatness'] > 0.85 and
       area['slope'] < 3.0
]

if not suitable_lzs:
    print("No suitable LZs found, relaxing criteria...")
    # Retry with more lenient parameters
```

### 3. **Combine Multiple Queries**

Use multiple helper methods together for complex requirements:

```python
# Find position that is: elevated + concealed + has LOS
candidates = helper.find_elevated_positions(...)

best = None
best_score = -1

for pos in candidates:
    # Check concealment
    concealed = helper.find_concealed_positions(
        center_x=pos['x'], center_z=pos['z'],
        search_radius=100, num_samples=1
    )
    
    # Check LOS
    has_los = helper.check_line_of_sight(
        x1=pos['x'], z1=pos['z'],
        x2=target_x, z2=target_z
    )
    
    if concealed and has_los:
        score = pos['height_advantage'] + concealed[0]['concealment_score'] * 100
        if score > best_score:
            best = pos
            best_score = score
```

### 4. **Performance Considerations**

- Use fewer `num_samples` for quick prototyping
- Increase samples for production/final missions
- Cache TerrainCalculator instance if creating multiple missions on same map
- Pathfinding methods can be slow on large distances—use waypoint-to-waypoint segments

### 5. **Testing Positions In-Game**

Always verify positions work as expected:

```python
# Add debug markers at found positions
for pos in tactical_positions:
    marker = create_unit(
        id_name="GroundUnitSpawn",
        unit_name=f"DEBUG_{pos['type']}",
        team="Allied",
        global_position=[pos['x'], 0, pos['z']]
    )
    mission.add_unit(marker, placement="ground")
```

---

## Limitations

1. **Road Data**: Road detection depends on map data quality. Some maps have incomplete road networks.

2. **Pathfinding Performance**: Complex path calculations can be slow. Pre-compute paths when possible.

3. **Threat Models**: Threat exposure calculations are simplified. For accurate SAM modeling, consider weapon system specifications.

---

## See Also

- [Mission Creation Guide](mission_creation.md) - Complete mission building workflow
- [Terrain Behavior](terrain_behavior.md) - How terrain sampling works

---

**Happy Mission Building!** 🗺️✈️
