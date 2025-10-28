"""
Quick Reference Guide for pytol Library Consolidated Frameworks

This guide provides quick examples and patterns for using the consolidated
frameworks throughout the pytol library.
"""

# =============================================================================
# MATH UTILITIES (pytol.misc.math_utils)
# =============================================================================

"""
Distance Calculations
-------------------
"""
# OLD WAY - Don't use
import math
distance_2d = math.sqrt((x2-x1)**2 + (z2-z1)**2)
distance_3d = math.sqrt((x2-x1)**2 + (y2-y1)**2 + (z2-z1)**2)

# NEW WAY - Use consolidated utilities
from pytol.misc.math_utils import calculate_2d_distance, calculate_3d_distance

distance_2d = calculate_2d_distance((x1, z1), (x2, z2))
distance_3d = calculate_3d_distance((x1, y1, z1), (x2, y2, z2))

"""
Angle Generation
--------------
"""
# OLD WAY - Don't use
import random
angle_radians = random.uniform(0, 2 * math.pi)
angle_degrees = random.uniform(0, 360)

# NEW WAY - Use consolidated utilities
from pytol.misc.math_utils import generate_random_angle

angle_radians = generate_random_angle(degrees=False)
angle_degrees = generate_random_angle(degrees=True)
angle_in_range = generate_random_angle(min_angle=90, max_angle=270, degrees=True)

"""
Position Utilities
----------------
"""
# Generate random position in circle
from pytol.misc.math_utils import generate_random_position_in_circle

center_2d = (50000, 50000)
radius = 10000
random_pos = generate_random_position_in_circle(center_2d, radius)

# Clamp position to bounds
from pytol.misc.math_utils import clamp_position_to_bounds

position_3d = (150000, 1000, 75000)  # Out of bounds
bounds = (0, 100000, 0, 3000, 0, 100000)
clamped = clamp_position_to_bounds(position_3d, bounds)

# Formation positioning
from pytol.misc.math_utils import calculate_formation_positions

center = (50000, 1000, 50000)
unit_count = 4
spacing = 200
formation_positions = calculate_formation_positions(
    center, unit_count, spacing, formation_type='line'
)

# =============================================================================
# POSITION SCORING (pytol.procedural.position_scoring)
# =============================================================================

"""
Basic Position Scoring
--------------------
"""
from pytol.procedural.position_scoring import (
    create_scorer, PositionRequirements, find_best_positions
)
from pytol.terrain.mission_terrain_helper import MissionTerrainHelper

# Create terrain helper (requires TerrainCalculator)
terrain_helper = MissionTerrainHelper(terrain_calculator)

# Define requirements
requirements = PositionRequirements(
    min_altitude=100,
    max_altitude=2000,
    max_slope=15,  # degrees
    requires_road_access=True,
    max_road_distance=5000,  # meters
    threat_tolerance=0.5  # 0-1, higher = more tolerant
)

# Create scorer for specific purpose
airbase_scorer = create_scorer('airbase', terrain_helper)
defensive_scorer = create_scorer('defensive', terrain_helper, system_type='sam')
tactical_scorer = create_scorer('tactical', terrain_helper, position_type='overwatch')
logistics_scorer = create_scorer('logistics', terrain_helper)

# Score a position
position = (50000, 500, 45000)
score_result = airbase_scorer.score_position(position, requirements)

# Check results
print(f"Total score: {score_result.total_score}")
print(f"Meets requirements: {score_result.meets_requirements}")
print(f"Issues: {score_result.issues}")

# Find best positions automatically
best_positions = find_best_positions(
    scorer=tactical_scorer,
    search_center=(50000, 1000, 50000),
    search_radius=20000,
    requirements=requirements,
    count=3,  # Find 3 positions
    min_separation=5000  # At least 5km apart
)

for pos, score in best_positions:
    print(f"Position {pos}: Score {score.total_score}")

# =============================================================================
# VALIDATION FRAMEWORK (pytol.misc.validation_framework)
# =============================================================================

"""
Position Validation
-----------------
"""
from pytol.misc.validation_framework import (
    PositionValidator, ValidationSeverity, validate_data
)

# Create validator with bounds
validator = PositionValidator(
    strict=False,  # Warnings don't fail validation
    bounds=(0, 100000, 0, 5000, 0, 100000)  # min_x, max_x, min_y, max_y, min_z, max_z
)

# Validate position
position = (50000, 1000, 50000)
result = validate_data(position, validator)

if result.is_valid:
    print("✓ Position is valid")
else:
    print(f"✗ Validation failed: {result.get_summary()}")
    for issue in result.issues:
        print(f"  - {issue.message}")

"""
Numeric Validation
----------------
"""
from pytol.misc.validation_framework import NumericValidator

# Create validator for altitude
altitude_validator = NumericValidator(
    min_value=0,
    max_value=5000,
    allow_negative=False,
    allow_zero=True,
    integer_only=False
)

altitude = 1500
result = validate_data(altitude, altitude_validator, print_results=False)

"""
List Validation
-------------
"""
from pytol.misc.validation_framework import ListValidator

# Validate waypoint list
waypoint_validator = ListValidator(
    min_length=2,
    max_length=10,
    element_validator=PositionValidator(),
    allow_empty=False,
    unique_elements=False
)

waypoints = [(1000, 100, 2000), (3000, 200, 4000)]
result = validate_data(waypoints, waypoint_validator)

"""
Dictionary Validation
-------------------
"""
from pytol.misc.validation_framework import DictValidator

# Validate unit data
unit_validator = DictValidator(
    required_fields=['type', 'position', 'heading'],
    optional_fields=['fuel', 'ammo', 'skill'],
    field_validators={
        'position': PositionValidator(),
        'heading': NumericValidator(min_value=0, max_value=360),
        'fuel': NumericValidator(min_value=0, max_value=1)
    },
    allow_extra_fields=True
)

unit_data = {
    'type': 'F-45A',
    'position': (25000, 1000, 30000),
    'heading': 90,
    'fuel': 0.8
}
result = validate_data(unit_data, unit_validator)

"""
Pre-made Validators
-----------------
"""
from pytol.misc.validation_framework import (
    create_mission_validator,
    create_unit_validator,
    create_airbase_validator
)

mission_validator = create_mission_validator()
unit_validator = create_unit_validator()
airbase_validator = create_airbase_validator()

"""
Strict Mode
---------
"""
# In strict mode, warnings become errors
strict_validator = NumericValidator(min_value=10, max_value=100, strict=True)

value = 5  # Below minimum - will be WARNING in normal mode, ERROR in strict mode
result = validate_data(value, strict_validator, print_results=False)
# result.is_valid will be False in strict mode

# =============================================================================
# TERRAIN QUERIES (pytol.terrain.mission_terrain_helper)
# =============================================================================

"""
Safe Terrain Height Queries
--------------------------
"""
from pytol.terrain.mission_terrain_helper import MissionTerrainHelper

terrain_helper = MissionTerrainHelper(terrain_calculator)

# OLD WAY - Direct call, no error handling
height = terrain_calculator.get_terrain_height(x, z)  # May raise exception

# NEW WAY - Safe query with error handling
height = terrain_helper.get_terrain_height_safe(x, z, default=0.0)

# Batch query multiple points
positions_2d = [(1000, 2000), (3000, 4000), (5000, 6000)]
heights = terrain_helper.sample_terrain_heights(positions_2d)

# =============================================================================
# COMMON PATTERNS
# =============================================================================

"""
Pattern: Find Valid Spawn Location
---------------------------------
"""
from pytol.procedural.position_scoring import create_scorer, PositionRequirements
from pytol.misc.validation_framework import PositionValidator

# ============================================================================
# PYTOL LIBRARY - DEVELOPER QUICK REFERENCE
# ============================================================================
# This file serves as a comprehensive quick reference for pytol library
# development. Use this as context for AI assistants and for your own
# development to avoid duplicating existing functionality.
#
# Last Updated: October 27, 2025 (Phase 3 Consolidation Complete)
# ============================================================================

"""
PYTOL Library Quick Reference

This document catalogs all available utilities, classes, methods, and patterns
in the pytol library.

============================================================================
HOW TO USE THIS REFERENCE FOR DEVELOPMENT:
============================================================================

📋 FOR YOU (Human Developer):
-----------------------------
1. **Before Writing New Code:**
   - Press Ctrl+F and search for keywords (e.g., "distance", "random position", "bearing")
   - Check if functionality already exists before implementing
   - Review examples to understand correct usage patterns

2. **When Stuck:**
   - Search for your use case (e.g., "tactical position", "validation", "equipment")
   - Find the relevant section and import statement
   - Copy the example and adapt to your needs

3. **For Code Reviews:**
   - Use Section 9 (Common Patterns) as checklist
   - Check Section 10 (Anti-Patterns) to catch issues
   - Reference correct patterns when suggesting changes

4. **Quick Imports:**
   - Jump to Section 12 for copy-paste import statements
   - Common operations are grouped by frequency of use

5. **When Adding New Features:**
   - Add your new APIs to the appropriate section
   - Include usage examples with actual code
   - Update the import cheatsheet if widely used
   - Update Section 11 (Code Quality) with any consolidations


🤖 FOR AI ASSISTANTS:
---------------------------------
1. **Always Check This File First:**
   - Before suggesting new utility functions, search this file
   - Use existing consolidated functions instead of duplicating
   - Follow the patterns shown in examples

2. **When User Asks to Implement Something:**
   - Search for keywords in this file
   - If it exists, show them how to use the existing function
   - If it doesn't exist, implement following established patterns

3. **Provide This File as Context:**
   - User should include this file when asking for code help
   - This prevents suggesting duplicate implementations
   - Ensures consistent coding patterns across the library

4. **Anti-Pattern Detection:**
   - Check Section 10 before suggesting any code
   - If user's code matches an anti-pattern, suggest the correct pattern from Section 9
   - Reference the specific section when explaining why

5. **Code Review Mode:**
   - Compare user's code against patterns in Section 9
   - Flag any anti-patterns from Section 10
   - Suggest imports from Section 12


💡 QUICK START EXAMPLES:
-------------------------
# Need to calculate distance?
>>> Search: "distance"
>>> Find: Section 1 - calculate_2d_distance, calculate_3d_distance
>>> Import: from pytol.misc.math_utils import calculate_2d_distance

# Need random position in circle?
>>> Search: "random position"
>>> Find: Section 1 - generate_random_position_in_circle
>>> Copy example with uniform_distribution option

# Need to validate mission data?
>>> Search: "validation"
>>> Find: Section 4 - validation framework
>>> Use: create_mission_validator()

# Need terrain queries?
>>> Search: "terrain"
>>> Find: Section 2 - TerrainCalculator, MissionTerrainHelper
>>> Review available methods and examples


🎯 WHAT THIS FILE PROVIDES:
----------------------------
1. Quickly find existing functionality before implementing new features
2. Understand the standard patterns and practices
3. Provide context to AI assistants to avoid code duplication
4. Reference correct import statements and usage examples
5. Learn from real usage examples with actual code
6. Avoid common mistakes (anti-patterns we've already eliminated)
7. Understand the consolidation work completed (900+ lines eliminated!)

Organization:
- Core Math & Geometry Utilities
- Terrain System & Queries
- Procedural Generation Systems
- Data Structures & Parsers
- Validation & Scoring Frameworks
- Visualization Tools
- Resources & Equipment
- Common Patterns & Anti-Patterns
- Quick Import Cheatsheet
- Development Workflow

============================================================================
"""

# ============================================================================
# 1. CORE MATH & GEOMETRY UTILITIES
# ============================================================================
# Location: pytol.misc.math_utils
# Purpose: Consolidated mathematical operations for position, distance, angles

"""
✅ ALWAYS USE THESE - DO NOT DUPLICATE!

Distance Calculations:
----------------------
from pytol.misc.math_utils import (
    calculate_2d_distance,      # (x,z) to (x,z) distance
    calculate_3d_distance,      # (x,y,z) to (x,y,z) distance  
    calculate_horizontal_distance  # Ignores Y altitude
)

# Examples:
dist_2d = calculate_2d_distance((x1, z1), (x2, z2))
dist_3d = calculate_3d_distance((x1, y1, z1), (x2, y2, z2))
horizontal = calculate_horizontal_distance((x1, y1, z1), (x2, y2, z2))


Angle & Bearing Functions:
--------------------------
from pytol.misc.math_utils import (
    generate_random_angle,      # Random angle 0-2π or 0-360°
    calculate_bearing,          # Direction from pos1 to pos2 (0°=North)
    normalize_angle,            # Wrap angle to 0-2π or 0-360°
    angle_difference           # Shortest angular difference
)

# Examples:
angle = generate_random_angle(degrees=True)  # 0-360°
bearing = calculate_bearing(from_pos, to_pos, degrees=True)  # Navigation bearing
norm = normalize_angle(450, degrees=True)  # Returns 90°
diff = angle_difference(350, 10, degrees=True)  # Returns 20°

⚠️ CRITICAL: calculate_bearing() uses correct atan2(dx, dz) order!
             3 bugs were fixed during consolidation - always use this!


Position Generation (Random):
-----------------------------
from pytol.misc.math_utils import (
    generate_random_position_in_circle,  # Random pos in circle/annulus
    generate_random_position_in_ring    # Random pos in ring (donut)
)

# Examples:
# 2D position
pos_2d = generate_random_position_in_circle((cx, cz), radius=1000)

# 3D position (preserves Y coordinate)  
pos_3d = generate_random_position_in_circle((cx, cy, cz), radius=1000)

# Uniform spatial distribution (prevents clustering at center)
pos_uniform = generate_random_position_in_circle(
    center=(x, z), 
    radius=500, 
    uniform_distribution=True  # Uses sqrt for even distribution
)

# Annular distribution (min/max radius)
pos_ring = generate_random_position_in_circle(
    center=(x, y, z),
    radius=2000,         # Outer radius
    min_distance=500,    # Inner radius (exclusion zone)
    uniform_distribution=True
)

✅ Phase 3: This function replaces 20+ duplicate implementations!


Position Operations:
-------------------
from pytol.misc.math_utils import (
    interpolate_positions,         # Linear interpolation between points
    is_position_in_circle,        # Check if pos within circle
    find_closest_position,        # Find nearest from list
    calculate_centroid,           # Center of multiple positions
    distribute_positions_in_circle,  # Evenly space around circle
    calculate_formation_positions    # Military formations
)

# Examples:
waypoints = interpolate_positions(start, end, steps=10)
is_inside = is_position_in_circle((x, z), center=(cx, cz), radius=500)
closest, dist = find_closest_position(target, candidates_list)
center = calculate_centroid([(x1,z1), (x2,z2), (x3,z3)])
ring_positions = distribute_positions_in_circle((cx, cz), radius=100, count=8)
formation = calculate_formation_positions(
    leader_pos=(x, z), 
    leader_heading=heading_rad,
    formation_type='wedge',  # 'line', 'wedge', 'diamond', 'box'
    count=3, 
    spacing=100
)


Terrain Slope Calculation:
--------------------------
from pytol.misc.math_utils import calculate_slope_from_normal

# Get terrain normal from TerrainCalculator
normal = terrain_calculator.get_terrain_normal(x, z)
slope_degrees = calculate_slope_from_normal(normal, degrees=True)

if slope_degrees <= 15:
    # Flat enough for building placement
    pass

✅ Phase 2: Consolidated 13+ duplicate slope calculations
⚠️ Always clamps normal[1] to [-1, 1] to prevent math errors
"""

# ============================================================================
# 2. TERRAIN SYSTEM & QUERIES
# ============================================================================
# Location: pytol.terrain.terrain_calculator, pytol.terrain.mission_terrain_helper

"""
TerrainCalculator - Low-Level Terrain Data:
------------------------------------------
from pytol.terrain.terrain_calculator import TerrainCalculator

tc = TerrainCalculator(scenario_folder="path/to/scenario", verbose=True)

# Core terrain queries:
height = tc.get_terrain_height(x, z)           # Get Y elevation
normal = tc.get_terrain_normal(x, z)           # Surface normal (x,y,z)
tile_type = tc.get_terrain_tile_type(x, z)     # Terrain type index

# Heatmap and areas:
heatmap = tc.get_hmap2()                       # Full heightmap
water_level = tc.get_water_level()             # Sea level
safe_zone = tc.get_landmass_safe_zone()        # Valid terrain area

# Object queries:
units = tc.get_all_units()                     # All scenario units
buildings = tc.get_all_buildings()             # All buildings
waypoints = tc.get_waypoints_for_unit(unit_id) # Unit path


MissionTerrainHelper - High-Level Mission Queries:
--------------------------------------------------
from pytol.terrain.mission_terrain_helper import MissionTerrainHelper

helper = MissionTerrainHelper(terrain_calculator, verbose=True)

# Safe terrain queries (with fallback):
height = helper.get_terrain_height_safe(x, z, default=0.0)
pos_3d = helper.get_terrain_height_with_position(x, z, altitude_agl=100)
heights_list = helper.sample_terrain_heights([(x1,z1), (x2,z2), ...])

# Line of sight:
visible = helper.has_line_of_sight(pos1, pos2, steps=20, terrain_offset=2)

# Tactical position finding:
observer = helper.find_observation_post(
    target_area=(tx, ty, tz),
    min_dist=500,
    max_dist=2000,
    num_candidates=20
)

arty = helper.find_artillery_position(
    target_area=(tx, ty, tz),
    search_radius=3000,
    standoff_dist=1000
)

heli_hide = helper.find_helicopter_hide_position(
    threat_pos=(tx, ty, tz),
    search_center=(sx, sy, sz),
    search_radius=2000
)

dispersal = helper.find_dispersal_area(
    center=(x, y, z),
    radius=500,
    num_positions=4,
    spacing=50
)

# Road and bridge queries:
roads = helper.get_road_points()               # All road points
nearest_road = helper.find_nearest_road_point((x, z))
bridges = helper.get_bridges()                 # Bridge locations

# Landing zones:
landing_zones = helper.find_flat_landing_zones(
    center_x=x,
    center_z=z,
    search_radius=1000,
    min_area_radius=100,
    max_slope_degrees=5.0
)

# Terrain elevation queries:
highest = helper.find_highest_point_in_area(center_x=x, center_z=z, search_radius=2000)
lowest = helper.find_lowest_point_in_area(center_x=x, center_z=z, search_radius=2000)

# Hidden positions:
hidden = helper.find_hidden_position(
    observer_pos=(ox, oy, oz),
    target_area_center=(tx, ty, tz),
    search_radius=1500
)

# Terrain-following paths:
waypoints = helper.get_terrain_following_path(
    start_pos=(x1, y1, z1),
    end_pos=(x2, y2, z2),
    steps=20,
    altitude_agl=150.0  # Altitude above ground level
)

# Formation points (circular):
positions = helper.get_circular_formation_points(
    center_pos=(x, y, z),
    radius=200,
    num_points=6,
    start_angle_deg=0
)

# Terrain type detection:
terrain_info = helper.get_terrain_type(
    position=(x, y, z),
    sample_radius=100
)

# Road path finding:
road_path = helper.get_road_path(
    start_pos=(x1, z1),
    end_pos=(x2, z2),
    max_segments=100
)

# Choke points (for ambushes):
choke = helper.find_choke_point(
    road_path=road_points,
    check_width=100
)

# Covert insertion paths (avoid radar):
covert_path = helper.get_covert_insertion_path(
    start_pos=(x1, y1, z1),
    end_pos=(x2, y2, z2),
    radar_positions=[(r1x, r1y, r1z), (r2x, r2y, r2z)],
    steps=50
)

# Buildings in area:
buildings = helper.get_buildings_in_area(
    center_x=x,
    center_z=z,
    radius=500,
    spawnable_only=True  # Only buildings that can spawn units
)

# Find city with specific static objects:
city = helper.find_city_with_statics(
    required_prefab_ids=['hangar', 'tower'],
    search_all=True
)
"""

# ============================================================================
# 3. PROCEDURAL GENERATION SYSTEMS
# ============================================================================

"""
Smart Asset Placement:
---------------------
from pytol.procedural.smart_asset_placement import (
    SmartAssetPlacementSystem,
    AssetType,
    AssetRequirements
)

placer = SmartAssetPlacementSystem(mission_helper)

# Place military assets intelligently:
sam_site = placer.place_asset(
    asset_type=AssetType.SAM_SITE,
    center=(x, y, z),
    search_radius=2000,
    requirements=AssetRequirements(
        max_slope=15,
        min_distance_to_roads=50,
        requires_line_of_sight=True
    )
)

airbase = placer.place_airbase(center, runway_heading, runway_length=2000)
fob = placer.place_forward_operating_base(center, radius=500)


Intelligent Threat Networks:
----------------------------
from pytol.procedural.intelligent_threat_network import (
    IntelligentThreatNetwork,
    ThreatType,
    AlertState
)

threat_net = IntelligentThreatNetwork(mission_helper)

# Create layered defense:
network = threat_net.create_layered_defense(
    center=(x, y, z),
    threat_level='high',
    radius=5000,
    include_radars=True,
    include_sams=True
)

# Generate SAM coverage:
sam_systems = threat_net.place_sam_coverage(
    area_center=(x, y, z),
    coverage_radius=10000,
    threat_density='medium'
)


Terrain-Aware Formations:
-------------------------
from pytol.procedural.terrain_aware_formations import (
    TerrainAwareFormationGenerator,
    FormationType,
    UnitFormationRequirements
)

formation_gen = TerrainAwareFormationGenerator(mission_helper)

positions = formation_gen.generate_formation(
    leader_position=(x, y, z),
    formation_type=FormationType.WEDGE,
    unit_count=4,
    spacing=100,
    requirements=UnitFormationRequirements(
        max_slope=20,
        avoid_water=True,
        min_spacing=50
    )
)


Tactical AI Behaviors:
---------------------
from pytol.procedural.tactical_ai_behaviors import (
    TacticalAISystem,
    AIUnit,
    BehaviorState,
    UnitType
)

ai_system = TacticalAISystem(mission_helper)

unit = AIUnit(
    position=(x, y, z),
    unit_type=UnitType.TANK,
    behavior_state=BehaviorState.PATROL
)

waypoints = ai_system.generate_patrol_route(
    unit=unit,
    patrol_area=(cx, cy, cz),
    patrol_radius=1000,
    num_waypoints=6
)


Tactical Waypoint Generator:
----------------------------
from pytol.procedural.tactical_waypoint_generator import (
    TacticalWaypointGenerator,
    FlightProfile
)

waypoint_gen = TacticalWaypointGenerator(mission_helper)

waypoints = waypoint_gen.generate_waypoints(
    start_pos=(x1, y1, z1),
    end_pos=(x2, y2, z2),
    flight_profile=FlightProfile.LOW_ALTITUDE,
    threat_positions=[(tx1, ty1, tz1), ...],
    num_waypoints=8
)


Altitude Policy (Threat-Aware):
-------------------------------
from pytol.procedural.altitude_policy import AltitudePolicy, ThreatEnvironment

policy = AltitudePolicy(mission_helper)

altitude = policy.get_recommended_altitude(
    position=(x, y, z),
    threat_environment=ThreatEnvironment.HIGH,
    flight_profile='ingress'  # 'ingress', 'egress', 'transit'
)


Procedural Mission Engine:
--------------------------
from pytol.procedural.engine import ProceduralMissionEngine

engine = ProceduralMissionEngine(mission_helper)

mission = engine.generate_strike_mission(
    target_position=(tx, ty, tz),
    spawn_position=(sx, sy, sz),
    difficulty='medium',
    mission_type='SEAD'  # 'SEAD', 'CAS', 'CAP', 'STRIKE'
)


Mission Narrative System:
-------------------------
from pytol.procedural.mission_narrative_system import (
    MissionNarrativeSystem,
    CallsignGenerator
)

narrative = MissionNarrativeSystem()

briefing = narrative.generate_briefing(
    mission_type='STRIKE',
    target_info={'name': 'SAM Site', 'grid': 'AB1234'},
    situation='Enemy air defenses active',
    player_role='Flight Lead'
)

callsign = CallsignGenerator.generate_callsign(unit_type='fighter')
"""

# ============================================================================
# 4. POSITION SCORING & VALIDATION FRAMEWORKS
# ============================================================================

"""
Position Scoring System:
-----------------------
from pytol.procedural.position_scoring import (
    create_scorer,
    find_best_positions,
    PositionRequirements,
    BasePositionScorer,
    AirbaseScorer,
    DefensivePositionScorer,
    TacticalPositionScorer
)

# Create scorer for specific purpose:
scorer = create_scorer(
    'airbase',  # 'airbase', 'defensive', 'tactical', 'logistics'
    terrain_helper,
    requirements=PositionRequirements(
        max_slope=10,
        min_area=200,
        avoid_water=True
    )
)

# Find best positions:
positions = find_best_positions(
    scorer=scorer,
    search_area=(cx, cy, cz),
    search_radius=5000,
    num_candidates=50,
    num_results=3
)

# Each position includes score and reasoning:
for pos, score in positions:
    print(f"Position {pos}: Score {score.total_score:.2f}")
    print(f"  Slope: {score.slope_score:.2f}")
    print(f"  Flatness: {score.flatness_score:.2f}")


Validation Framework:
--------------------
from pytol.misc.validation_framework import (
    create_mission_validator,
    create_unit_validator,
    ValidationResult,
    ValidationSeverity,
    validate_data
)

# Validate mission data:
validator = create_mission_validator()
result = validate_data(mission_data, validator, print_results=True)

if not result.is_valid:
    for issue in result.get_errors():
        print(f"ERROR: {issue.message}")

# Custom validators:
from pytol.misc.validation_framework import (
    PositionValidator,
    NumericValidator,
    CompositeValidator
)

position_val = PositionValidator(
    valid_range=((-10000, 10000), (-1000, 5000), (-10000, 10000))
)
altitude_val = NumericValidator(min_value=0, max_value=20000)
"""

# --- Unit Prefab Database Reference ---
#
# The authoritative list of all Allied and Enemy unit prefabs is generated from the Unity project and stored in:
#   pytol/resources/unit_prefab_database.json
#
# Use these helpers from pytol.resources:
#   from pytol.resources import get_all_unit_prefabs, get_allied_unit_prefabs, get_enemy_unit_prefabs
#
# - get_all_unit_prefabs(): returns all unique unit prefab names (Allied + Enemy)
# - get_allied_unit_prefabs(): returns all Allied unit prefab names
# - get_enemy_unit_prefabs(): returns all Enemy unit prefab names
#
# Example usage:
#   all_units = get_all_unit_prefabs()
#   allied_units = get_allied_unit_prefabs()
#   enemy_units = get_enemy_unit_prefabs()
#
# This database is the reference for spawnable units, team compatibility, and prefab validation.
#

# ============================================================================
# 5. DATA STRUCTURES & PARSERS
# ============================================================================

"""
VTS Parser (VTOL VR Scenario Files):
------------------------------------
from pytol.parsers import vts_parser

# Load .vts scenario file:
data = vts_parser.load_vts("path/to/scenario.vts")

# Access scenario data:
units = data.get('units', [])
waypoints = data.get('waypoints', [])
conditionals = data.get('conditionals', [])

# Save modified scenario:
vts_parser.save_vts("path/to/output.vts", data)


Weather Presets (Custom):
------------------------
from pytol import Mission, WeatherPreset

# Create mission and add a custom weather preset (ids 0-7 are built-ins; use 8+):
mission = Mission(
    scenario_name="Test Weather",
    scenario_id="test_weather",
    description="Demo mission with custom weather",
    vehicle="AV-42C",
    map_id="hMap2",
    vtol_directory="C:/Program Files (x86)/Steam/steamapps/common/VTOL VR"
)
wp = WeatherPreset(
    id=8,
    preset_name="Red Fog",
    cloud_plane_altitude=1500,
    cloudiness=0.0,
    macro_cloudiness=0.0,
    cirrus=0.5,
    stratocumulus=0.0,
    precipitation=0.0,
    lightning_chance=0.0,
    fog_density=0.65,
    fog_color=(1, 0, 0, 1),
    fog_height=1.0,
    fog_falloff=1000.0,
    cloud_density=0.0,
)
mission.add_weather_preset(wp)
mission.set_default_weather(8)
mission.save_mission("./out")


Unit Classes:
------------
from pytol.classes import Unit, UnitFields

# Create unit:
unit = Unit(
    id=1,
    unit_name="Fighter-1",
    global_position=(5000, 1000, 3000),
    unit_instance_id="FA-26B"
)

# Access fields:
pos = unit.get_position()
unit.set_position((5100, 1000, 3000))
waypoints = unit.get_waypoints()


Campaign System:
---------------
from pytol.classes import Campaign, Mission

campaign = Campaign(name="Operation Thunder")
mission = Mission(
    name="Strike Package Alpha",
    description="Destroy enemy air defenses",
    difficulty="medium"
)
campaign.add_mission(mission)
"""

# ============================================================================
# 6. RESOURCES & EQUIPMENT
# ============================================================================

"""
Equipment System:
----------------
from pytol.resources.equipment import (
    EquipmentBuilder,
    LoadoutPresets,
    get_available_vehicles,
    get_playable_vehicles,
    get_equipment_for_vehicle,
    search_equipment
)

# List all vehicles (including AI):
vehicles = get_available_vehicles()

# List only playable vehicles (excludes AI):
playable = get_playable_vehicles()  # Filters out AIUCAV, EBomberAI, etc.

# Get equipment for vehicle:
weapons = get_equipment_for_vehicle("FA-26B")

# Build custom loadout:
builder = EquipmentBuilder("FA-26B")
loadout = builder.add_weapon("AIM-120", hardpoint=0) \\
                .add_weapon("AGM-88", hardpoint=2) \\
                .add_fuel_tank("center") \\
                .build()

# Use presets:
cas_loadout = LoadoutPresets.fighter_cas("FA-26B")
sead_loadout = LoadoutPresets.fighter_sead("FA-26B")


Resource Loaders:
----------------
from pytol.resources.resources import (
    load_json_data,
    load_image_asset,
    get_city_layout_database,
    get_prefab_database,
    get_vehicle_equipment_database
)

data = load_json_data("custom_data.json")
city_layouts = get_city_layout_database()
prefabs = get_prefab_database()


Base Spawn Points:
-----------------
from pytol.resources.base_spawn_points import get_base_spawn_points

spawn_points = get_base_spawn_points(map_id="akutan")
for spawn in spawn_points:
    print(f"Base: {spawn['name']} at {spawn['position']}")
"""

# ============================================================================
# 7. VISUALIZATION TOOLS
# ============================================================================

"""
2D Map Visualization:
--------------------
from pytol.visualization.map2d import Map2DVisualizer, save_mission_map

viz = Map2DVisualizer(terrain_calculator)

# Generate mission overview map:
map_path = viz.generate_mission_overview(
    units=units_list,
    waypoints=waypoints_list,
    threats=threat_positions,
    output_file="mission_map.png"
)

# Quick save:
save_mission_map(mission, "output.png", style='tactical')


3D Terrain Visualization:
-------------------------
from pytol.visualization.visualizer import (
    TerrainVisualizer,
    MissionVisualizer
)

terrain_viz = TerrainVisualizer(terrain_calculator)
terrain_viz.plot_heightmap(resolution=512, colormap='terrain')

mission_viz = MissionVisualizer(mission_helper)
mission_viz.plot_mission_overview(
    spawn=(sx, sy, sz),
    target=(tx, ty, tz),
    threats=[(t1x, t1y, t1z), ...]
)
"""

# ============================================================================
# 8. LOGGING SYSTEM
# ============================================================================

"""
Centralized Logging:
-------------------
from pytol.misc.logger import create_logger, PytolLogger

# Create logger for module:
logger = create_logger(verbose=True, name="MyModule")

logger.info("Processing started")
logger.warning("Low memory condition")
logger.error("Failed to load data")

# Custom logger with file output:
logger = PytolLogger(
    name="MissionGen",
    log_file="mission_generation.log",
    level=logging.INFO
)

✅ DO NOT use print() statements in library code
✅ Use logger.info/warning/error instead
✅ Print statements are OK in test scripts and __main__ blocks
"""

# ============================================================================
# 9. COMMON PATTERNS & BEST PRACTICES
# ============================================================================

"""
✅ DO THESE THINGS:

1. Distance Calculations:
   # ✅ CORRECT:
   from pytol.misc.math_utils import calculate_2d_distance
   dist = calculate_2d_distance(pos1, pos2)
   
   # ❌ WRONG:
   dist = math.sqrt((x2-x1)**2 + (z2-z1)**2)  # DO NOT DUPLICATE!

2. Random Positions in Circle:
   # ✅ CORRECT:
   from pytol.misc.math_utils import generate_random_position_in_circle
   pos = generate_random_position_in_circle(center, radius)
   
   # ❌ WRONG:
   angle = random.uniform(0, 2*math.pi)  # DO NOT DUPLICATE!
   r = random.uniform(0, radius)
   x = cx + r * math.cos(angle)
   z = cz + r * math.sin(angle)

3. Bearing Calculations:
   # ✅ CORRECT:
   from pytol.misc.math_utils import calculate_bearing
   bearing = calculate_bearing(from_pos, to_pos, degrees=True)
   
   # ❌ WRONG:
   bearing = math.atan2(dx, dz)  # Parameter order bugs fixed in Phase 2!

4. Slope from Normal:
   # ✅ CORRECT:
   from pytol.misc.math_utils import calculate_slope_from_normal
   slope = calculate_slope_from_normal(normal, degrees=True)
   
   # ❌ WRONG:
   slope = math.degrees(math.acos(normal[1]))  # Missing clamp!

5. Error Handling:
   # ✅ CORRECT:
   try:
       dangerous_operation()
   except Exception as e:
       logger.error(f"Operation failed: {e}")
   
   # ❌ WRONG:
   except:  # Catches SystemExit, KeyboardInterrupt!
       pass

6. Iterating with Index:
   # ✅ CORRECT:
   for i, item in enumerate(items):
       process(i, item)
   
   # ❌ WRONG:
   for i in range(len(items)):  # Anti-pattern!
       process(i, items[i])

7. Logging vs Print:
   # ✅ CORRECT (in library code):
   logger.info("Mission generated successfully")
   
   # ✅ CORRECT (in test scripts):
   if __name__ == "__main__":
       print("Test results:")  # OK in __main__
   
   # ❌ WRONG (in library code):
   print("Debug output")  # Use logger instead!
"""

# ============================================================================
# 10. ANTI-PATTERNS TO AVOID
# ============================================================================

"""
❌ NEVER DO THESE:

1. Inline Distance Calculations:
   dist = math.sqrt((x2-x1)**2 + (z2-z1)**2)  # Use calculate_2d_distance()!

2. Manual Polar Coordinate Generation:
   angle = random.uniform(0, 2*math.pi)  # Use generate_random_position_in_circle()!
   r = random.uniform(0, radius)
   x = cx + r * math.cos(angle)
   z = cz + r * math.sin(angle)

3. Wrong atan2 Parameter Order:
   bearing = math.atan2(dz, dx)  # WRONG! Should be atan2(dx, dz) for navigation!

4. Bare except Clauses:
   except:  # Catches SystemExit, KeyboardInterrupt - BAD!
       pass

5. Private Distance Methods in Classes:
   def _calculate_distance(self, pos):  # Use math_utils instead!
       return math.sqrt(...)

6. Unclamped Slope Calculations:
   slope = math.acos(normal[1])  # May crash if normal[1] > 1.0!

7. range(len()) Pattern:
   for i in range(len(items)):  # Use enumerate() instead!
       item = items[i]

8. Print Statements in Library Code:
   print("Processing...")  # Use logger.info() instead!

9. Direct Terrain Queries Without Error Handling:
   height = tc.get_terrain_height(x, z)  # Use helper.get_terrain_height_safe()!

10. Duplicate Validation Logic:
    if not (0 <= x <= 10000):  # Use validation_framework instead!
        raise ValueError()
"""

# ============================================================================
# 11. CODE QUALITY METRICS & IMPROVEMENTS
# ============================================================================

"""
Consolidation Progress (Updated October 27, 2025):

Phase 1 (Initial):
- Lines Eliminated: 800-1000
- Patterns Fixed: 8
- Files Updated: 15+
- Functions Created: 20+

Phase 2 (Slopes & Bearings):
- Lines Eliminated: 45
- Patterns Fixed: 4 (slope calculations, bearings, private methods, range/len)
- Critical Bugs Fixed: 3 (wrong atan2 parameter order)
- Files Updated: 8
- Functions Enhanced: 2

Phase 3 (Polar Coordinates):
- Lines Eliminated: 60-80
- Patterns Fixed: 3 (polar generation, inline distance, bare except)
- Critical Bugs Fixed: 1 (bare except clause)
- Files Updated: 8
- Functions Enhanced: 1

TOTAL CONSOLIDATION ACHIEVEMENT:
- Lines Eliminated: 905-1125
- Issues Resolved: 31 (from 336 → 305)
- Files Updated: 31+
- Critical Bugs Fixed: 7
- Functions Created/Enhanced: 22+

Current Code Quality: 305 issues remaining (mostly low-priority):
- 220 missing type hints (gradual improvement)
- 65 direct terrain queries (consider wrappers)
- 16 custom validation/scoring (optional)
- 2 angle generation patterns
- 1 distance calculation
- 1 range(len()) pattern
"""

# ============================================================================
# 12. QUICK IMPORT CHEATSHEET
# ============================================================================

"""
# Math utilities (MOST COMMONLY USED):
from pytol.misc.math_utils import (
    calculate_2d_distance, calculate_3d_distance,
    generate_random_position_in_circle,
    calculate_bearing, generate_random_angle,
    calculate_slope_from_normal
)

# Terrain system:
from pytol.terrain.terrain_calculator import TerrainCalculator
from pytol.terrain.mission_terrain_helper import MissionTerrainHelper

# Procedural generation:
from pytol.procedural.engine import ProceduralMissionEngine
from pytol.procedural.smart_asset_placement import SmartAssetPlacementSystem
from pytol.procedural.intelligent_threat_network import IntelligentThreatNetwork
from pytol.procedural.terrain_aware_formations import TerrainAwareFormationGenerator

# Scoring & validation:
from pytol.procedural.position_scoring import create_scorer, find_best_positions
from pytol.misc.validation_framework import create_mission_validator, validate_data

# Resources:
from pytol.resources.equipment import EquipmentBuilder, LoadoutPresets
from pytol.resources.resources import get_city_layout_database

# Logging:
from pytol.misc.logger import create_logger
"""

# ============================================================================
# 13. DEVELOPMENT WORKFLOW
# ============================================================================

"""
When Implementing New Features:

1. CHECK THIS FILE FIRST!
   - Search for existing functionality
   - Review similar patterns in other modules
   - Understand standard practices

2. Use Existing Utilities:
   - Don't duplicate distance/angle/position functions
   - Use consolidated scoring/validation frameworks
   - Follow established patterns

3. Add to This Reference:
   - Document new public APIs
   - Add usage examples
   - Update import cheatsheet

4. Run Code Quality Checks:
   python tools/code_quality_analyzer.py pytol
   
5. Update Documentation:
   - Add docstrings with examples
   - Update DUPLICATION_SUMMARY.md if consolidating
   - Keep this quick reference current

6. Test Thoroughly:
   - Unit tests for new utilities
   - Integration tests for systems
   - Validate against existing missions
"""

# =============================================================================
# END OF QUICK REFERENCE
# ============================================================================

def find_valid_spawn_location(terrain_helper, search_area, unit_type='ground'):
    """Find a valid spawn location for a unit."""
    
    # Define requirements based on unit type
    if unit_type == 'ground':
        requirements = PositionRequirements(
            min_altitude=0,
            max_altitude=500,
            max_slope=15,
            requires_road_access=True,
            max_road_distance=2000
        )
    elif unit_type == 'air':
        requirements = PositionRequirements(
            min_altitude=0,
            max_altitude=1000,
            max_slope=5,  # Flat for airbase
            requires_road_access=False
        )
    else:
        requirements = PositionRequirements()
    
    # Create appropriate scorer
    scorer = create_scorer('logistics', terrain_helper)
    
    # Find best positions
    positions = find_best_positions(
        scorer=scorer,
        search_center=search_area['center'],
        search_radius=search_area['radius'],
        requirements=requirements,
        count=5,
        min_separation=1000
    )
    
    # Validate best position
    if positions:
        best_pos, best_score = positions[0]
        
        validator = PositionValidator(
            bounds=(0, 100000, 0, 5000, 0, 100000)
        )
        result = validate_data(best_pos, validator, print_results=False)
        
        if result.is_valid:
            return best_pos
    
    return None

"""
Pattern: Generate Mission with Validated Data
--------------------------------------------
"""
def create_validated_mission(mission_data, terrain_helper):
    """Create a mission with comprehensive validation."""
    from pytol.misc.validation_framework import create_mission_validator, validate_data
    
    # Validate mission structure
    validator = create_mission_validator()
    result = validate_data(mission_data, validator)
    
    if not result.is_valid:
        raise ValueError(f"Invalid mission data: {result.get_summary()}")
    
    # Validate and score objective positions
    from pytol.procedural.position_scoring import create_scorer, PositionRequirements
    
    scorer = create_scorer('tactical', terrain_helper, position_type='objective')
    requirements = PositionRequirements(
        min_altitude=50,
        max_altitude=2000,
        max_slope=30
    )
    
    validated_objectives = []
    for obj in mission_data['objectives']:
        score = scorer.score_position(obj['position'], requirements)
        if score.meets_requirements:
            validated_objectives.append(obj)
        else:
            print(f"Objective rejected: {score.issues}")
    
    mission_data['objectives'] = validated_objectives
    return mission_data

# =============================================================================
# MIGRATION CHECKLIST
# =============================================================================

"""
When updating existing code to use consolidated frameworks:

1. ✓ Replace distance calculations
   - Search for: sqrt((x2-x1)**2 + (z2-z1)**2)
   - Replace with: calculate_2d_distance((x1, z1), (x2, z2))

2. ✓ Replace angle generation
   - Search for: random.uniform(0, 2*math.pi)
   - Replace with: generate_random_angle(degrees=False)

3. ✓ Replace position scoring
   - Search for: def _score_*_position
   - Replace with: create_scorer() + score_position()

4. ✓ Replace validation functions
   - Search for: def _validate_*
   - Replace with: Validator classes from validation_framework

5. ✓ Replace terrain height queries
   - Search for: tc.get_terrain_height(x, z)
   - Replace with: terrain_helper.get_terrain_height_safe(x, z)

6. ✓ Add type hints where missing
7. ✓ Update documentation to reference new APIs
8. ✓ Test thoroughly to ensure behavior is preserved
"""

# =============================================================================
# UNIT GROUPS (NATO Phonetic Alphabet)
# =============================================================================

"""
Unit groups in VTOL VR MUST use NATO phonetic alphabet names.
pytol validates this automatically and provides helpful error messages.

Valid Group Names:
-----------------
from pytol import NATO_PHONETIC_ALPHABET

# List of all valid names:
# Alpha, Bravo, Charlie, Delta, Echo, Foxtrot, Golf, Hotel, India, Juliet,
# Kilo, Lima, Mike, November, Oscar, Papa, Quebec, Romeo, Sierra, Tango,
# Uniform, Victor, Whiskey, Xray, Yankee, Zulu

Adding Units to Groups:
----------------------
from pytol import Mission
from pytol.classes.units import create_unit

mission = Mission(...)

# Create units
fighter = create_unit(
    id_name="F-45A AI",
    unit_name="Fighter 1",
    team="Allied",
    global_position=[0, 1500, 0],
    rotation=[0, 0, 0]
)
unit_id = mission.add_unit(fighter, placement="airborne")

# Add to group - validates NATO name automatically
mission.add_unit_to_group("Allied", "Alpha", unit_id)   # ✓ Valid
mission.add_unit_to_group("Enemy", "Bravo", unit_id)    # ✓ Valid

# These will raise ValueError with helpful suggestions:
mission.add_unit_to_group("Allied", "Fighters", unit_id)  # ✗ Invalid
mission.add_unit_to_group("Allied", "Squad1", unit_id)    # ✗ Invalid

Error Messages:
--------------
# Invalid name provides full list and suggestions:
ValueError: Invalid unit group name 'Fighters'. VTOL VR requires NATO phonetic 
alphabet names. Valid names: Alpha, Bravo, Charlie, Delta, Echo, Foxtrot, Golf, 
Hotel, India, Juliet, Kilo, Lima, Mike, November, Oscar, Papa, Quebec, Romeo, 
Sierra, Tango, Uniform, Victor, Whiskey, Xray, Yankee, Zulu.

# Close match provides suggestion:
ValueError: Invalid unit group name 'Br'. VTOL VR requires NATO phonetic alphabet 
names. Valid names: ... Did you mean: Bravo?

Best Practices:
--------------
# Check available names programmatically
from pytol import NATO_PHONETIC_ALPHABET

for i, name in enumerate(NATO_PHONETIC_ALPHABET[:4]):
    # Create squadron with sequential NATO names
    mission.add_unit_to_group("Allied", name, unit_ids[i])

# Alpha, Bravo, Charlie, Delta squadrons created automatically
"""

"""
Group Prefix Codes and Placement Modes
-------------------------------------
VTOL VR stores group membership with a prefix that encodes the group's placement type.
This library assigns the correct prefix automatically based on each group's first member's
editorPlacementMode and warns if a group mixes different placement modes.

Prefix mapping used by VTOL VR (and pytol):
- Ground → prefix "0;"
- Sea/Water (naval/carrier/boats) → prefix "1;"
- Air (airborne/other) → prefix "2;"

Notes:
- Mixed placement groups are supported but discouraged; pytol will pick the prefix from the
    first member and log a warning with the mixed modes encountered.
- Each group automatically gets a required `<GroupName>_SETTINGS` block with `syncAltSpawns = False`.

Example:
        # Air group → prefix 2;
        mission.add_unit_to_group("Allied", "Alpha", fighter1)
        mission.add_unit_to_group("Allied", "Alpha", fighter2)

        # Ground group → prefix 0;
        mission.add_unit_to_group("Enemy", "Delta", tank1)
        mission.add_unit_to_group("Enemy", "Delta", tank2)

        # Sea group → prefix 1;
        mission.add_unit_to_group("Enemy", "Echo", boat1)
        mission.add_unit_to_group("Enemy", "Echo", boat2)
"""

# =============================================================================
# PERFORMANCE TIPS
# =============================================================================

"""
1. Batch Operations
   - Use sample_terrain_heights() for multiple height queries
   - Use find_best_positions() instead of scoring positions one by one

2. Reuse Validators
   - Create validators once and reuse them
   - Avoid creating new validator instances in loops

3. Cache Results
   - Store position scores if reusing same positions
   - Cache validation results for static data

4. Choose Appropriate Strictness
   - Use strict=False for exploratory/generation tasks
   - Use strict=True for final validation before saving

5. Optimize Search Parameters
   - Reduce max_attempts when performance is critical
   - Increase min_separation to reduce collision checks
"""

print("pytol Consolidated Frameworks Quick Reference Guide")
print("=" * 60)
print("Import this module for quick examples and patterns!")
print("See CONSOLIDATION_SUMMARY.md for comprehensive documentation.")

"""
Event Sequences & Random Events
------------------------------
EventSequences allow you to script ordered event chains with optional looping and conditional logic. RandomEvents let you define weighted random actions, each with its own conditional graph.

# EventSequence with whileConditional (loop while counter < 5)
from pytol.classes.mission_objects import EventSequence, SequenceEvent, EventTarget, ParamInfo, GlobalValue
from pytol.classes.conditionals import Sccglobalvalue

loop_cond = Sccglobalvalue(gv="counter", comparison="Less_Than", c_value=5)
seq = EventSequence(
    id=1,
    sequence_name="Counter Loop",
    start_immediately=True,
    while_loop=True,
    while_conditional=loop_cond,  # Full graph embedded in SEQUENCE
    events=[
        SequenceEvent(
            node_name="Increment Counter",
            delay=2.0,
            actions=[
                EventTarget(
                    target_type="GlobalValue",
                    target_id="counter",
                    event_name="Increment",
                    params=[ParamInfo(name="value", type="float", value=1.0)]
                )
            ]
        )
    ]
)
mission.add_event_sequence(seq)

# RandomEvent with nested conditional graph
from pytol.classes.mission_objects import RandomEvent, RandomEventAction
cond = Sccglobalvalue(gv="counter", comparison="Greater_Than", c_value=2)
re = RandomEvent(
    id=1,
    name="Random Test",
    action_options=[
        RandomEventAction(
            id=0,
            action_name="Action A",
            fixed_weight=50,
            conditional=cond,  # Full graph embedded in ACTION
            actions=[...]
        ),
        RandomEventAction(
            id=1,
            action_name="Action B",
            fixed_weight=50,
            conditional=None,  # Placeholder (id=0)
            actions=[...]
        )
    ]
)
mission.add_random_event(re)

Notes:
- If you pass a Conditional object to while_conditional or RandomEventAction.conditional, pytol emits the full graph as a nested CONDITIONAL block.
- If you pass a string ID, only a reference (or placeholder) is emitted.
- methodParameters in simple conditionals are now always formatted as a nested block for full VTS compatibility.
- Proximity triggers only emit `waypoint = null` if no waypoint is provided.
"""