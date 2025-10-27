# pytol Consolidated Frameworks - Quick Reference

This guide provides quick examples for using the consolidated frameworks in the pytol library.

## 📚 Table of Contents

- [Math Utilities](#math-utilities)
- [Position Scoring](#position-scoring)
- [Validation Framework](#validation-framework)
- [Terrain Queries](#terrain-queries)
- [Common Patterns](#common-patterns)

---

## 🧮 Math Utilities

Location: `pytol.misc.math_utils`

### Distance Calculations

```python
from pytol.misc.math_utils import calculate_2d_distance, calculate_3d_distance

# 2D distance (horizontal plane)
distance_2d = calculate_2d_distance((x1, z1), (x2, z2))

# 3D distance (full 3D space)
distance_3d = calculate_3d_distance((x1, y1, z1), (x2, y2, z2))
```

### Angle Generation

```python
from pytol.misc.math_utils import generate_random_angle

# Random angle in degrees (0-360)
angle_degrees = generate_random_angle(degrees=True)

# Random angle in radians (0-2π)
angle_radians = generate_random_angle(degrees=False)

# Random angle in specific range
angle = generate_random_angle(min_angle=90, max_angle=270, degrees=True)
```

### Position Utilities

```python
from pytol.misc.math_utils import (
    generate_random_position_in_circle,
    clamp_position_to_bounds,
    calculate_formation_positions
)

# Generate random position in circle
center_2d = (50000, 50000)
random_pos = generate_random_position_in_circle(center_2d, radius=10000)

# Clamp position to map bounds
bounds = (0, 100000, 0, 3000, 0, 100000)  # min_x, max_x, min_y, max_y, min_z, max_z
clamped = clamp_position_to_bounds(position, bounds)

# Calculate formation positions
positions = calculate_formation_positions(
    center=(50000, 1000, 50000),
    count=4,
    spacing=200,
    formation_type='line'  # 'line', 'column', 'wedge', 'circle'
)
```

---

## 🎯 Position Scoring

Location: `pytol.procedural.position_scoring`

### Basic Usage

```python
from pytol.procedural.position_scoring import (
    create_scorer,
    PositionRequirements,
    find_best_positions
)

# Define requirements
requirements = PositionRequirements(
    min_altitude=100,
    max_altitude=2000,
    max_slope=15,
    requires_road_access=True,
    max_road_distance=5000,
    threat_tolerance=0.5
)

# Create scorer
scorer = create_scorer('tactical', terrain_helper, position_type='overwatch')

# Score a position
position = (50000, 500, 45000)
result = scorer.score_position(position, requirements)

print(f"Total score: {result.total_score}")
print(f"Valid: {result.meets_requirements}")
```

### Scorer Types

```python
# Airbase positions
airbase_scorer = create_scorer('airbase', terrain_helper)

# Defensive positions (SAM, radar, AAA)
sam_scorer = create_scorer('defensive', terrain_helper, system_type='sam')
radar_scorer = create_scorer('defensive', terrain_helper, system_type='radar')

# Tactical positions
overwatch_scorer = create_scorer('tactical', terrain_helper, position_type='overwatch')
ambush_scorer = create_scorer('tactical', terrain_helper, position_type='ambush')

# Logistics positions
logistics_scorer = create_scorer('logistics', terrain_helper)
```

### Finding Best Positions

```python
# Find multiple good positions automatically
best_positions = find_best_positions(
    scorer=scorer,
    search_center=(50000, 1000, 50000),
    search_radius=20000,
    requirements=requirements,
    count=3,
    min_separation=5000,
    max_attempts=100
)

for position, score in best_positions:
    print(f"Position: {position}, Score: {score.total_score}")
```

---

## ✅ Validation Framework

Location: `pytol.misc.validation_framework`

### Position Validation

```python
from pytol.misc.validation_framework import PositionValidator, validate_data

validator = PositionValidator(
    bounds=(0, 100000, 0, 5000, 0, 100000)
)

position = (50000, 1000, 50000)
result = validate_data(position, validator)

if result.is_valid:
    print("✓ Valid position")
else:
    print(f"✗ {result.get_summary()}")
    for issue in result.issues:
        print(f"  - {issue.message}")
```

### Numeric Validation

```python
from pytol.misc.validation_framework import NumericValidator

altitude_validator = NumericValidator(
    min_value=0,
    max_value=5000,
    allow_negative=False
)

result = validate_data(1500, altitude_validator)
```

### List Validation

```python
from pytol.misc.validation_framework import ListValidator

waypoint_validator = ListValidator(
    min_length=2,
    max_length=10,
    element_validator=PositionValidator(),
    allow_empty=False
)

waypoints = [(1000, 100, 2000), (3000, 200, 4000)]
result = validate_data(waypoints, waypoint_validator)
```

### Dictionary Validation

```python
from pytol.misc.validation_framework import DictValidator, NumericValidator

unit_validator = DictValidator(
    required_fields=['type', 'position', 'heading'],
    optional_fields=['fuel', 'skill'],
    field_validators={
        'position': PositionValidator(),
        'heading': NumericValidator(min_value=0, max_value=360)
    }
)

unit_data = {
    'type': 'F-45A',
    'position': (25000, 1000, 30000),
    'heading': 90
}
result = validate_data(unit_data, unit_validator)
```

### Pre-made Validators

```python
from pytol.misc.validation_framework import (
    create_mission_validator,
    create_unit_validator,
    create_airbase_validator
)

mission_validator = create_mission_validator()
unit_validator = create_unit_validator()
airbase_validator = create_airbase_validator()
```

---

## 🗺️ Terrain Queries

Location: `pytol.terrain.mission_terrain_helper`

### Safe Height Queries

```python
from pytol.terrain.mission_terrain_helper import MissionTerrainHelper

terrain_helper = MissionTerrainHelper(terrain_calculator)

# Safe single query with error handling
height = terrain_helper.get_terrain_height_safe(x, z, default=0.0)

# Batch query multiple points efficiently
positions_2d = [(1000, 2000), (3000, 4000), (5000, 6000)]
heights = terrain_helper.sample_terrain_heights(positions_2d)
```

---

## 🔄 Common Patterns

### Pattern: Find Valid Spawn Location

```python
def find_spawn_location(terrain_helper, search_area, unit_type='ground'):
    from pytol.procedural.position_scoring import create_scorer, PositionRequirements
    
    requirements = PositionRequirements(
        min_altitude=0,
        max_altitude=500 if unit_type == 'ground' else 1000,
        max_slope=15 if unit_type == 'ground' else 5,
        requires_road_access=(unit_type == 'ground')
    )
    
    scorer = create_scorer('logistics', terrain_helper)
    
    positions = find_best_positions(
        scorer=scorer,
        search_center=search_area['center'],
        search_radius=search_area['radius'],
        requirements=requirements,
        count=1
    )
    
    return positions[0][0] if positions else None
```

### Pattern: Validate Mission Data

```python
def validate_mission(mission_data):
    from pytol.misc.validation_framework import create_mission_validator, validate_data
    
    validator = create_mission_validator()
    result = validate_data(mission_data, validator)
    
    if not result.is_valid:
        print(f"❌ {result.get_summary()}")
        for issue in result.issues:
            print(f"  • {issue.message}")
            if issue.suggestion:
                print(f"    💡 {issue.suggestion}")
        return False
    
    print("✅ Mission data is valid")
    return True
```

---

## 🚀 Performance Tips

1. **Batch Operations**: Use `sample_terrain_heights()` for multiple queries
2. **Reuse Validators**: Create once, use many times
3. **Cache Results**: Store scores/validations for reused data
4. **Optimize Search**: Reduce `max_attempts` when speed is critical
5. **Appropriate Strictness**: Use `strict=False` for generation, `strict=True` for final validation

---

## 📖 More Information

- **Comprehensive Guide**: See `CONSOLIDATION_SUMMARY.md`
- **Migration Guide**: Check the adoption section in `CONSOLIDATION_SUMMARY.md`
- **API Documentation**: See individual module docstrings

---

## 🎯 Quick Migration Checklist

- [ ] Replace `math.sqrt((x2-x1)**2 + (z2-z1)**2)` → `calculate_2d_distance()`
- [ ] Replace `random.uniform(0, 2*math.pi)` → `generate_random_angle()`
- [ ] Replace `_score_*_position()` functions → `create_scorer()` + `score_position()`
- [ ] Replace `_validate_*()` functions → Validator classes
- [ ] Replace `tc.get_terrain_height()` → `terrain_helper.get_terrain_height_safe()`

---

**For detailed examples and advanced usage, see the comprehensive documentation in `CONSOLIDATION_SUMMARY.md`**