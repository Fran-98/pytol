"""Helper functions for defining territory control zones.

Territories can be defined manually or automatically based on bases,
mission configuration, or other criteria.
"""
from typing import Dict, Any, List, Optional, Tuple
import random
import math
import numpy as np
from pytol.procedural.world_state import WorldState

try:
    from scipy.spatial import Voronoi
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    Voronoi = None


def define_territory_from_base(
    wsm: WorldState,
    base_position: Tuple[float, float],
    radius: float,
    territory_type: str = "enemy"
) -> None:
    """
    Define a territory zone centered on a base.
    
    Args:
        wsm: WorldState instance
        base_position: (x, z) coordinates of the base
        radius: Territory radius in meters
        territory_type: 'enemy', 'friendly', or 'neutral'
    
    Example:
        # Define enemy territory around an enemy airbase
        define_territory_from_base(
            wsm=wsm,
            base_position=(50000, 50000),
            radius=30000,  # 30km
            territory_type='enemy'
        )
    """
    zone = {
        'type': 'circle',
        'center': base_position,
        'radius': radius
    }
    wsm.register_territory_zone(territory_type, zone)


def define_territory_from_bases(
    wsm: WorldState,
    bases: List[Dict[str, Any]],
    radius_per_base: float = 20000,
    territory_type: str = "enemy"
) -> None:
    """
    Define territories from a list of bases.
    
    Args:
        wsm: WorldState instance
        bases: List of base dicts with 'position' key (x, y, z) or (x, z)
        radius_per_base: Radius around each base in meters
        territory_type: 'enemy', 'friendly', or 'neutral'
    
    Example:
        # Define enemy territories from all enemy bases
        enemy_bases = [base for base in all_bases if base.get('team') == 'Enemy']
        define_territory_from_bases(
            wsm=wsm,
            bases=enemy_bases,
            radius_per_base=25000,
            territory_type='enemy'
        )
    """
    for base in bases:
        pos = base.get('position', (0, 0, 0))
        if isinstance(pos, (list, tuple)) and len(pos) >= 2:
            # Extract (x, z) from position
            base_2d = (pos[0], pos[2] if len(pos) >= 3 else pos[1])
            define_territory_from_base(wsm, base_2d, radius_per_base, territory_type)


def define_territory_polygon(
    wsm: WorldState,
    vertices: List[Tuple[float, float]],
    territory_type: str = "enemy"
) -> None:
    """
    Define a territory zone using a polygon.
    
    Args:
        wsm: WorldState instance
        vertices: List of (x, z) coordinates forming a closed polygon
        territory_type: 'enemy', 'friendly', or 'neutral'
    
    Example:
        # Define a rectangular enemy territory
        define_territory_polygon(
            wsm=wsm,
            vertices=[
                (40000, 40000),  # Southwest corner
                (60000, 40000),  # Southeast corner
                (60000, 60000),  # Northeast corner
                (40000, 60000),  # Northwest corner
            ],
            territory_type='enemy'
        )
    """
    if len(vertices) < 3:
        raise ValueError("Polygon must have at least 3 vertices")
    
    zone = {
        'type': 'polygon',
        'vertices': vertices
    }
    wsm.register_territory_zone(territory_type, zone)


def define_territory_from_mission_config(
    wsm: WorldState,
    mission_center: Tuple[float, float],
    enemy_territory_radius: Optional[float] = None,
    friendly_territory_radius: Optional[float] = None,
    default_radius: float = 40000
) -> None:
    """
    Define territories based on mission center point.
    
    Useful for simple missions where enemy/friendly territories
    are split by distance from a central point.
    
    Args:
        wsm: WorldState instance
        mission_center: (x, z) center point of the mission area
        enemy_territory_radius: Radius for enemy territory (default: default_radius)
        friendly_territory_radius: Radius for friendly territory (default: default_radius)
        default_radius: Default radius if not specified
    
    Example:
        # Simple front-line scenario: enemy to the east, friendly to the west
        mission_center = (50000, 50000)
        define_territory_from_mission_config(
            wsm=wsm,
            mission_center=mission_center,
            enemy_territory_radius=50000,  # 50km east
            friendly_territory_radius=30000  # 30km west
        )
    """
    if enemy_territory_radius is None:
        enemy_territory_radius = default_radius
    if friendly_territory_radius is None:
        friendly_territory_radius = default_radius
    
    # Define enemy territory (typically to the east/north of center)
    enemy_center = (mission_center[0] + enemy_territory_radius * 0.7, 
                    mission_center[1] + enemy_territory_radius * 0.3)
    define_territory_from_base(wsm, enemy_center, enemy_territory_radius, 'enemy')
    
    # Define friendly territory (typically to the west/south of center)
    friendly_center = (mission_center[0] - friendly_territory_radius * 0.7,
                       mission_center[1] - friendly_territory_radius * 0.3)
    define_territory_from_base(wsm, friendly_center, friendly_territory_radius, 'friendly')


def intelligently_randomize_territories(
    wsm: WorldState,
    terrain_calculator,
    mission_plan,
    seed: Optional[int] = None,
    min_territory_radius: float = 20000,
    max_territory_radius: float = 50000,
    city_weight: float = 1.5,
    base_weight: float = 2.0,
    road_weight: float = 0.8
) -> None:
    """
    Intelligently randomize territory boundaries based on terrain analysis.
    
    This function analyzes the map to create realistic territory divisions:
    - Uses seed for reproducible randomization
    - Considers base positions and strategic value
    - Weights city locations (urban centers are valuable)
    - Analyzes road networks (major routes define front lines)
    - Considers terrain features (natural boundaries)
    
    Args:
        wsm: WorldState instance
        terrain_calculator: TerrainCalculator instance
        mission_plan: MissionPlan object with metadata
        seed: Random seed for reproducibility
        min_territory_radius: Minimum territory radius in meters
        max_territory_radius: Maximum territory radius in meters
        city_weight: Weight factor for city importance (default: 1.5)
        base_weight: Weight factor for base importance (default: 2.0)
        road_weight: Weight factor for road network (default: 0.8)
    
    Example:
        # Randomize territories intelligently
        intelligently_randomize_territories(
            wsm=wsm,
            terrain_calculator=mission.tc,
            mission_plan=plan,
            seed=12345,
            min_territory_radius=25000,
            max_territory_radius=45000
        )
    """
    rng = random.Random(seed)
    
    try:
        map_size = terrain_calculator.total_map_size_meters
        map_center = (map_size / 2, map_size / 2)
    except Exception:
        map_center = (50000, 50000)
        map_size = 100000
    
    archetype = mission_plan.metadata.get('mission_archetype', 'offensive').lower()
    threat_level = mission_plan.metadata.get('threat_level', 'medium').lower()
    
    # Threat level affects territory sizes
    threat_multiplier = {
        'low': 0.9,
        'medium': 1.0,
        'high': 1.15,
        'extreme': 1.3
    }.get(threat_level, 1.0)
    
    base_radius = (min_territory_radius + max_territory_radius) / 2 * threat_multiplier
    
    # Step 1: Analyze bases and their strategic value
    all_bases = []
    try:
        all_bases = terrain_calculator.get_all_bases()
    except Exception:
        pass
    
    base_positions = []
    for base in all_bases:
        pos = base.get('position', (0, 0, 0))
        if isinstance(pos, (list, tuple)) and len(pos) >= 2:
            base_2d = (pos[0], pos[2] if len(pos) >= 3 else pos[1])
            base_positions.append(base_2d)
    
    # Step 2: Analyze city centers (high-density urban areas)
    city_centers = []
    try:
        # Sample map in grid to find city centers
        sample_resolution = max(5000, map_size / 20)  # Adaptive resolution
        for x in np.arange(0, map_size, sample_resolution):
            for z in np.arange(0, map_size, sample_resolution):
                try:
                    density = terrain_calculator.get_city_density(x, z)
                    if density > 0.3:  # Significant urban area
                        city_centers.append((x, z, density))
                except Exception:
                    continue
    except Exception:
        pass
    
    # Step 3: Analyze road network to find major routes
    major_roads = []
    try:
        road_segments = getattr(terrain_calculator, 'road_segments', [])
        if road_segments:
            # Group road segments by approximate routes
            # Find roads that span significant distances (likely major highways)
            for segment in road_segments:
                start = segment.get('start', (0, 0, 0))
                end = segment.get('end', (0, 0, 0))
                if len(start) >= 2 and len(end) >= 2:
                    start_2d = (start[0], start[2] if len(start) >= 3 else start[1])
                    end_2d = (end[0], end[2] if len(end) >= 3 else end[1])
                    
                    from ..misc.math_utils import calculate_2d_distance
                    dist = calculate_2d_distance(start_2d, end_2d)
                    if dist > 5000:  # Significant road segment (>5km)
                        # Use midpoint as route node
                        mid = ((start_2d[0] + end_2d[0]) / 2, (start_2d[1] + end_2d[1]) / 2)
                        major_roads.append(mid)
    except Exception:
        pass
    
    # Step 4: Determine territory division strategy based on archetype
    if archetype == 'offensive':
        # Offensive: Enemy territory should be far from friendly spawn
        # Find player spawn area (likely near map edge or friendly bases)
        if base_positions:
            # Assume first base or closest to origin is friendly
            spawn_base = min(base_positions, key=lambda b: (b[0]**2 + b[1]**2)**0.5)
            friendly_spawn = spawn_base
        else:
            friendly_spawn = (map_size * 0.2, map_size * 0.2)
        
        # Enemy territory centers should be far from spawn
        enemy_centers = []
        friendly_centers = [friendly_spawn]
        
        # Use weighted random selection for enemy territory centers
        # Prefer positions far from spawn, near cities/bases
        candidate_points = []
        
        # Add bases far from spawn (weighted by distance)
        for base_pos in base_positions:
            from ..misc.math_utils import calculate_2d_distance
            dist_from_spawn = calculate_2d_distance(friendly_spawn, base_pos)
            if dist_from_spawn > map_size * 0.3:
                # Weight by distance (farther = better) and base importance
                weight = (dist_from_spawn / map_size) * base_weight
                candidate_points.append((base_pos, weight, 'base'))
        
        # Add city centers far from spawn
        for city_x, city_z, density in city_centers:
            from ..misc.math_utils import calculate_2d_distance
            dist_from_spawn = calculate_2d_distance(friendly_spawn, (city_x, city_z))
            if dist_from_spawn > map_size * 0.25:
                weight = (dist_from_spawn / map_size) * city_weight * density
                candidate_points.append(((city_x, city_z), weight, 'city'))
        
        # Select enemy centers using weighted random
        if candidate_points:
            # Normalize weights
            total_weight = sum(w for _, w, _ in candidate_points)
            if total_weight > 0:
                selected = []
                num_enemy_centers = min(3, len(candidate_points))
                
                for _ in range(num_enemy_centers):
                    if not candidate_points:
                        break
                    # Weighted random selection
                    r = rng.uniform(0, total_weight)
                    cumsum = 0
                    for i, (pos, weight, _) in enumerate(candidate_points):
                        cumsum += weight
                        if r <= cumsum:
                            selected.append(pos)
                            # Remove and recalculate
                            candidate_points.pop(i)
                            total_weight -= weight
                            break
                
                enemy_centers = selected[:2]  # Limit to 2 enemy centers
        
        # If no good candidates, use fallback
        if not enemy_centers:
            # Place enemy territory far from spawn
            offset_x = rng.uniform(0.4, 0.7) * map_size
            offset_z = rng.uniform(0.4, 0.7) * map_size
            enemy_centers = [(map_center[0] + offset_x, map_center[1] + offset_z)]
        
    elif archetype == 'defensive':
        # Defensive: Enemy territory close to player spawn (threatening)
        if base_positions:
            spawn_base = min(base_positions, key=lambda b: (b[0]**2 + b[1]**2)**0.5)
            friendly_spawn = spawn_base
        else:
            friendly_spawn = (map_size * 0.2, map_size * 0.2)
        
        enemy_centers = []
        friendly_centers = [friendly_spawn]
        
        # Enemy territory should be close but not too close
        # Prefer positions near cities or bases but closer to spawn than offensive
        candidate_points = []
        
        for base_pos in base_positions:
            from ..misc.math_utils import calculate_2d_distance
            dist_from_spawn = calculate_2d_distance(friendly_spawn, base_pos)
            if map_size * 0.15 < dist_from_spawn < map_size * 0.4:
                # Close enough to threaten, far enough to be separate
                weight = base_weight * (1.0 - dist_from_spawn / (map_size * 0.5))
                candidate_points.append((base_pos, weight, 'base'))
        
        for city_x, city_z, density in city_centers:
            from ..misc.math_utils import calculate_2d_distance
            dist_from_spawn = calculate_2d_distance(friendly_spawn, (city_x, city_z))
            if map_size * 0.1 < dist_from_spawn < map_size * 0.35:
                weight = city_weight * density * (1.0 - dist_from_spawn / (map_size * 0.4))
                candidate_points.append(((city_x, city_z), weight, 'city'))
        
        if candidate_points:
            total_weight = sum(w for _, w, _ in candidate_points)
            if total_weight > 0:
                # Select 1-2 enemy centers
                selected = []
                for _ in range(min(2, len(candidate_points))):
                    if not candidate_points:
                        break
                    r = rng.uniform(0, total_weight)
                    cumsum = 0
                    for i, (pos, weight, _) in enumerate(candidate_points):
                        cumsum += weight
                        if r <= cumsum:
                            selected.append(pos)
                            candidate_points.pop(i)
                            total_weight -= weight
                            break
                enemy_centers = selected
        
        if not enemy_centers:
            # Fallback: place enemy territory near center
            enemy_centers = [(map_center[0] + rng.uniform(-map_size*0.1, map_size*0.1),
                              map_center[1] + rng.uniform(-map_size*0.1, map_size*0.1))]
    else:
        # Recon/Other: Balanced split using terrain features
        # Divide map using natural boundaries (roads, cities, bases)
        
        # Cluster bases into two groups
        if len(base_positions) >= 2:
            # Use k-means-like clustering (simplified)
            # Split bases roughly in half based on position
            sorted_by_x = sorted(base_positions, key=lambda p: p[0])
            split_idx = len(sorted_by_x) // 2
            
            friendly_centers = [sorted_by_x[0]] if sorted_by_x else []
            enemy_centers = sorted_by_x[split_idx:] if sorted_by_x else []
            
            # Also consider cities closest to each group
            if city_centers and enemy_centers:
                for city_x, city_z, density in city_centers[:3]:  # Top 3 cities
                    from ..misc.math_utils import calculate_2d_distance
                    dist_to_enemy = min(calculate_2d_distance((city_x, city_z), ec) for ec in enemy_centers) if enemy_centers else float('inf')
                    dist_to_friendly = min(calculate_2d_distance((city_x, city_z), fc) for fc in friendly_centers) if friendly_centers else float('inf')
                    
                    if dist_to_enemy < dist_to_friendly and density > 0.4:
                        if len(enemy_centers) < 3:
                            enemy_centers.append((city_x, city_z))
                    elif dist_to_friendly < dist_to_enemy and density > 0.4:
                        if len(friendly_centers) < 3:
                            friendly_centers.append((city_x, city_z))
        else:
            # Fallback: simple split
            friendly_centers = [(map_center[0] - map_size*0.25, map_center[1])]
            enemy_centers = [(map_center[0] + map_size*0.25, map_center[1])]
    
    # Step 5: Define territories with variable radii
    # Use smaller radius for bases, larger for area coverage
    
    # Define friendly territories
    for center in friendly_centers[:2]:  # Limit to 2 centers
        radius = base_radius * rng.uniform(0.9, 1.1)
        define_territory_from_base(wsm, center, radius, 'friendly')
    
    # Define enemy territories
    for center in enemy_centers[:2]:  # Limit to 2 centers
        radius = base_radius * rng.uniform(0.9, 1.2)  # Slightly larger for enemy
        define_territory_from_base(wsm, center, radius, 'enemy')


def define_territories_from_mission_plan(
    wsm: WorldState,
    mission_plan,
    terrain_calculator,
    mission_center: Optional[Tuple[float, float]] = None,
    default_radius: float = 30000
) -> None:
    """
    Intelligently define territories based on mission plan objectives and context.
    
    Uses mission archetype, objectives, and available bases to create realistic
    territory boundaries. This function now delegates to intelligently_randomize_territories
    for more sophisticated terrain analysis.
    
    Args:
        wsm: WorldState instance
        mission_plan: MissionPlan object with objectives and metadata
        terrain_calculator: TerrainCalculator instance
        mission_center: Optional (x, z) center point (if None, uses map center)
        default_radius: Default territory radius in meters
    
    Example:
        # Define territories based on mission plan
        define_territories_from_mission_plan(
            wsm=wsm,
            mission_plan=plan,
            terrain_calculator=mission.tc,
            default_radius=35000
        )
    """
    # Get seed from mission plan
    seed = mission_plan.metadata.get('seed')
    
    # Use intelligent randomization
    intelligently_randomize_territories(
        wsm=wsm,
        terrain_calculator=terrain_calculator,
        mission_plan=mission_plan,
        seed=seed,
        min_territory_radius=default_radius * 0.7,
        max_territory_radius=default_radius * 1.5
    )


def auto_define_territories_from_map(
    wsm: WorldState,
    terrain_calculator,
    enemy_base_names: Optional[List[str]] = None,
    friendly_base_names: Optional[List[str]] = None,
    default_radius: float = 25000
) -> None:
    """
    Automatically define territories based on bases found on the map.
    
    Args:
        wsm: WorldState instance
        terrain_calculator: TerrainCalculator instance to query bases
        enemy_base_names: Optional list of base names/IDs that are enemy (if None, auto-detect)
        friendly_base_names: Optional list of base names/IDs that are friendly (if None, auto-detect)
        default_radius: Default territory radius around each base
    
    Example:
        # Auto-detect territories from map bases
        auto_define_territories_from_map(
            wsm=wsm,
            terrain_calculator=mission.tc,
            default_radius=30000
        )
    """
    try:
        all_bases = terrain_calculator.get_all_bases()
        
        if enemy_base_names:
            # Use specified enemy base names
            enemy_bases = [b for b in all_bases if b.get('name') in enemy_base_names or 
                          b.get('id') in enemy_base_names]
        else:
            # Default: first half of bases are enemy (can be improved with base metadata)
            enemy_bases = all_bases[:len(all_bases)//2] if len(all_bases) > 1 else []
        
        if friendly_base_names:
            # Use specified friendly base names
            friendly_bases = [b for b in all_bases if b.get('name') in friendly_base_names or 
                             b.get('id') in friendly_base_names]
        else:
            # Default: second half of bases are friendly
            friendly_bases = all_bases[len(all_bases)//2:] if len(all_bases) > 1 else []
        
        # Register territories
        if enemy_bases:
            define_territory_from_bases(wsm, enemy_bases, default_radius, 'enemy')
        if friendly_bases:
            define_territory_from_bases(wsm, friendly_bases, default_radius, 'friendly')
        
    except Exception as e:
        # If base detection fails, fall back to no territories
        pass


def _point_in_polygon(x: float, z: float, polygon: List[Tuple[float, float]]) -> bool:
    """
    Ray casting algorithm to determine if a point is inside a polygon.
    
    Args:
        x: X coordinate of point
        z: Z coordinate of point
        polygon: List of (x, z) vertex pairs defining the polygon
    
    Returns:
        bool: True if point is inside polygon
    """
    n = len(polygon)
    inside = False
    
    p1x, p1z = polygon[0]
    for i in range(1, n + 1):
        p2x, p2z = polygon[i % n]
        if z > min(p1z, p2z):
            if z <= max(p1z, p2z):
                if x <= max(p1x, p2x):
                    if p1z != p2z:
                        x_inters = (z - p1z) * (p2x - p1x) / (p2z - p1z) + p1x
                    if p1x == p2x or x <= x_inters:
                        inside = not inside
        p1x, p1z = p2x, p2z
    
    return inside


def _calculate_polygon_area(vertices: List[Tuple[float, float]]) -> float:
    """
    Calculate the area of a polygon using the shoelace formula.
    
    Args:
        vertices: List of (x, z) coordinates forming a closed polygon
    
    Returns:
        Area in square meters
    """
    if len(vertices) < 3:
        return 0.0
    
    area = 0.0
    n = len(vertices)
    for i in range(n):
        j = (i + 1) % n
        area += vertices[i][0] * vertices[j][1]
        area -= vertices[j][0] * vertices[i][1]
    
    return abs(area) / 2.0


def _snap_boundary_to_road(
    boundary_segment: Tuple[Tuple[float, float], Tuple[float, float]],
    road_segments: List[Any],
    snap_threshold: float = 400.0
) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """
    Snap a boundary segment to a nearby road if one exists within threshold.
    
    Args:
        boundary_segment: Tuple of ((x1, z1), (x2, z2)) defining boundary segment
        road_segments: List of road segments (dicts with 'start'/'end' or tuples)
        snap_threshold: Maximum distance to snap (meters)
    
    Returns:
        Snapped boundary segment (may be unchanged if no road nearby)
    """
    from ..misc.math_utils import calculate_2d_distance
    
    seg_start, seg_end = boundary_segment
    
    # Find closest road segment to this boundary segment
    best_road_seg = None
    min_dist = float('inf')
    
    for road_seg in road_segments:
        # Handle both dict format and tuple format
        if isinstance(road_seg, dict):
            road_start = road_seg.get('start', (0, 0, 0))
            road_end = road_seg.get('end', (0, 0, 0))
        else:
            road_start, road_end = road_seg
        
        # Extract 2D coordinates
        if len(road_start) >= 3:
            r_start_2d = (road_start[0], road_start[2])
        else:
            r_start_2d = (road_start[0], road_start[1])
        
        if len(road_end) >= 3:
            r_end_2d = (road_end[0], road_end[2])
        else:
            r_end_2d = (road_end[0], road_end[1])
        
        # Calculate distance from boundary segment midpoint to road segment midpoint
        seg_mid = ((seg_start[0] + seg_end[0]) / 2, (seg_start[1] + seg_end[1]) / 2)
        road_mid = ((r_start_2d[0] + r_end_2d[0]) / 2, (r_start_2d[1] + r_end_2d[1]) / 2)
        dist = calculate_2d_distance(seg_mid, road_mid)
        
        if dist < min_dist and dist < snap_threshold:
            min_dist = dist
            best_road_seg = (r_start_2d, r_end_2d)
    
    # If we found a nearby road, snap the boundary segment to it
    if best_road_seg:
        road_start, road_end = best_road_seg
        # Project boundary segment onto road segment direction
        # For simplicity, move midpoint to road midpoint
        seg_mid = ((seg_start[0] + seg_end[0]) / 2, (seg_start[1] + seg_end[1]) / 2)
        road_mid = ((road_start[0] + road_end[0]) / 2, (road_start[1] + road_end[1]) / 2)
        
        # Calculate offset
        offset_x = road_mid[0] - seg_mid[0]
        offset_z = road_mid[1] - seg_mid[1]
        
        # Apply offset to both endpoints
        snapped_start = (seg_start[0] + offset_x, seg_start[1] + offset_z)
        snapped_end = (seg_end[0] + offset_x, seg_end[1] + offset_z)
        
        return (snapped_start, snapped_end)
    
    return boundary_segment


def define_map_wide_territories(
    wsm: WorldState,
    terrain_calculator,
    mission_plan,
    use_natural_boundaries: bool = True,
    seed: Optional[int] = None
) -> None:
    """
    Divide entire map into Allied, Enemy, and Neutral territories using Voronoi diagram
    with path-following boundary refinement.
    
    Uses Voronoi cells from strategic points (bases, cities, objectives) and refines
    boundaries to follow major roads for realistic jagged front lines. Territory coverage
    percentages are determined by mission archetype:
    
    - Offensive missions: Allied 10-15%, Enemy 60-70%, Neutral 20-25%
      (small rear area, large hostile territory ahead, limited contested zone)
    - Defensive missions: Allied 20-30%, Enemy 40-50%, Neutral 30-40%
      (larger friendly area, moderate threat, large contested front)
    - Recon missions: Allied 15-25%, Enemy 50-60%, Neutral 25-30%
      (balanced with significant no-man's-land)
    
    Args:
        wsm: WorldState instance
        terrain_calculator: TerrainCalculator instance
        mission_plan: MissionPlan object with metadata
        use_natural_boundaries: If True, snap boundaries to roads (default: True)
        seed: Random seed for reproducibility
    
    Example:
        # Define map-wide territories from mission plan
        define_map_wide_territories(
            wsm=wsm,
            terrain_calculator=mission.tc,
            mission_plan=plan,
            use_natural_boundaries=True,
            seed=12345
        )
    """
    if not SCIPY_AVAILABLE:
        raise ImportError("scipy.spatial.Voronoi is required for map-wide territory division. Install scipy: pip install scipy")
    
    rng = random.Random(seed if seed is not None else mission_plan.metadata.get('seed'))
    
    # Get map size
    try:
        map_size = terrain_calculator.total_map_size_meters
    except Exception:
        map_size = 196608.0  # Default VTOL VR map size
    
    # Get mission archetype and determine target percentages
    archetype = mission_plan.metadata.get('mission_archetype', 'offensive').lower()
    
    if archetype == 'offensive':
        target_allied_pct = rng.uniform(0.10, 0.15)
        target_enemy_pct = rng.uniform(0.60, 0.70)
        target_neutral_pct = 1.0 - target_allied_pct - target_enemy_pct
    elif archetype == 'defensive':
        target_allied_pct = rng.uniform(0.20, 0.30)
        target_enemy_pct = rng.uniform(0.40, 0.50)
        target_neutral_pct = 1.0 - target_allied_pct - target_enemy_pct
    else:  # recon or other
        target_allied_pct = rng.uniform(0.15, 0.25)
        target_enemy_pct = rng.uniform(0.50, 0.60)
        target_neutral_pct = 1.0 - target_allied_pct - target_enemy_pct
    
    # Ensure neutral is at least 20% and percentages sum to 1.0
    if target_neutral_pct < 0.20:
        excess = 0.20 - target_neutral_pct
        target_allied_pct -= excess / 2
        target_enemy_pct -= excess / 2
        target_neutral_pct = 0.20
    
    # Step 1: Collect strategic points
    strategic_points = []
    point_types = []  # Track which territory each point represents
    
    # Allied bases (first 1-2 bases by convention)
    # We'll validate after territories are created and exclude problematic bases
    friendly_bases = []
    enemy_bases = []
    
    try:
        all_bases = terrain_calculator.get_all_bases()
        allied_base_count = min(2, max(1, len(all_bases) // 2))
        
        # First, assign bases based on order
        for i, base in enumerate(all_bases[:allied_base_count]):
            pos = base.get('position', (0, 0, 0))
            if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                base_2d = (pos[0], pos[2] if len(pos) >= 3 else pos[1])
                friendly_bases.append((base_2d, base))
        
        # Enemy candidate bases (remaining bases)
        for base in all_bases[allied_base_count:]:
            pos = base.get('position', (0, 0, 0))
            if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                base_2d = (pos[0], pos[2] if len(pos) >= 3 else pos[1])
                enemy_bases.append((base_2d, base))
        
        # Check distances between friendly and enemy bases
        # If bases are too close, we'll assign them more intelligently
        from ..misc.math_utils import calculate_2d_distance
        
        reassigned_bases = []
        
        # Find minimum distance between any friendly and enemy base
        min_friendly_enemy_dist = float('inf')
        if friendly_bases and enemy_bases:
            for fb_pos, _ in friendly_bases:
                for eb_pos, _ in enemy_bases:
                    dist = calculate_2d_distance(fb_pos, eb_pos)
                    min_friendly_enemy_dist = min(min_friendly_enemy_dist, dist)
        
        # If bases are very close (< 20% of map size), don't use both as strategic points
        # Instead, use only the ones that will create better territory separation
        min_separation_distance = map_size * 0.20
        
        if min_friendly_enemy_dist < min_separation_distance and len(all_bases) > 2:
            # Bases too close - use only the first of each type
            if friendly_bases:
                friendly_bases = friendly_bases[:1]
            if enemy_bases:
                enemy_bases = enemy_bases[:1]
        
        # Add friendly bases as strategic points
        for base_2d, base in friendly_bases:
            strategic_points.append(base_2d)
            point_types.append('friendly')
            
            # Add randomized strategic points around base (varies by seed)
            num_satellite_points = rng.randint(2, 4)  # 2-4 satellite points per base
            offset_dist = map_size * rng.uniform(0.06, 0.12)  # Vary distance
            base_angles = rng.sample(range(0, 360, 15), num_satellite_points)  # Random angles
            
            for angle in base_angles:
                angle_rad = math.radians(angle + rng.uniform(-10, 10))  # Add variance
                offset_point = (
                    base_2d[0] + math.cos(angle_rad) * offset_dist,
                    base_2d[1] + math.sin(angle_rad) * offset_dist
                )
                if 0 <= offset_point[0] <= map_size and 0 <= offset_point[1] <= map_size:
                    strategic_points.append(offset_point)
                    point_types.append('friendly')
        
        # Add enemy bases as strategic points
        for base_2d, base in enemy_bases:
            strategic_points.append(base_2d)
            point_types.append('enemy')
            
            # Add randomized strategic points around enemy base too (different from friendly)
            num_satellite_points = rng.randint(2, 4)
            offset_dist = map_size * rng.uniform(0.06, 0.12)
            base_angles = rng.sample(range(0, 360, 15), num_satellite_points)
            
            for angle in base_angles:
                angle_rad = math.radians(angle + rng.uniform(-10, 10))
                offset_point = (
                    base_2d[0] + math.cos(angle_rad) * offset_dist,
                    base_2d[1] + math.sin(angle_rad) * offset_dist
                )
                if 0 <= offset_point[0] <= map_size and 0 <= offset_point[1] <= map_size:
                    strategic_points.append(offset_point)
                    point_types.append('enemy')
        
        # Add random strategic points in neutral/contested areas (seed-dependent)
        num_random_points = rng.randint(2, 5)  # 2-5 random strategic points
        for _ in range(num_random_points):
            # Random position, but weighted toward map center (contested zone)
            center_weight = rng.uniform(0.3, 0.7)  # Vary center bias
            x = map_size * center_weight + rng.uniform(-map_size * 0.2, map_size * 0.2)
            z = map_size * center_weight + rng.uniform(-map_size * 0.2, map_size * 0.2)
            x = max(map_size * 0.1, min(x, map_size * 0.9))
            z = max(map_size * 0.1, min(z, map_size * 0.9))
            
            # Assign to team based on distance from bases
            from ..misc.math_utils import calculate_2d_distance
            friendly_dist = min(calculate_2d_distance((x, z), fp[0]) for fp in friendly_bases) if friendly_bases else float('inf')
            enemy_dist = min(calculate_2d_distance((x, z), ep[0]) for ep in enemy_bases) if enemy_bases else float('inf')
            
            if friendly_dist < enemy_dist:
                strategic_points.append((x, z))
                point_types.append('friendly')
            else:
                strategic_points.append((x, z))
                point_types.append('enemy')
    except Exception:
        pass
    
    # If no bases found, create default strategic points
    if not strategic_points:
        # Place friendly near map edge (west/south)
        strategic_points.append((map_size * 0.15, map_size * 0.15))
        point_types.append('friendly')
        # Place enemy far from friendly
        strategic_points.append((map_size * 0.75, map_size * 0.75))
        point_types.append('enemy')
    
    # Add major city centers as strategic points (important for territory variation)
    try:
        # Use more granular sampling for better city detection
        sample_resolution = max(3000, map_size / 30)  # Finer resolution
        city_centers = []
        
        # Sample map with random seed-dependent variations
        np.random.seed(seed if seed is not None else 42)
        sample_grid_x = np.arange(0, map_size, sample_resolution)
        sample_grid_z = np.arange(0, map_size, sample_resolution)
        
        # Add some jitter to sampling for seed variation
        jitter = sample_resolution * 0.3
        sample_grid_x = sample_grid_x + np.random.uniform(-jitter, jitter, len(sample_grid_x))
        sample_grid_z = sample_grid_z + np.random.uniform(-jitter, jitter, len(sample_grid_z))
        
        for x in sample_grid_x:
            for z in sample_grid_z:
                x = max(0, min(x, map_size))
                z = max(0, min(z, map_size))
                try:
                    density = terrain_calculator.get_city_density(x, z)
                    # Threshold varies by seed for different city selection
                    threshold = 0.25 + (rng.random() * 0.15)  # 0.25-0.4 threshold
                    if density > threshold:
                        city_centers.append((x, z, density))
                except Exception:
                    continue
        
        # Sort by density and take top cities (number varies by seed)
        city_centers.sort(key=lambda c: c[2], reverse=True)
        num_cities_to_use = rng.randint(3, 8)  # 3-8 cities vary territory
        
        # Assign cities to teams based on proximity to bases (with some randomization)
        from ..misc.math_utils import calculate_2d_distance
        
        friendly_points = [p for p, t in zip(strategic_points, point_types) if t == 'friendly']
        enemy_points = [p for p, t in zip(strategic_points, point_types) if t == 'enemy']
        
        for city_x, city_z, density in city_centers[:num_cities_to_use]:
            # Find nearest friendly and enemy points
            min_friendly_dist = min(calculate_2d_distance((city_x, city_z), fp) for fp in friendly_points) if friendly_points else float('inf')
            min_enemy_dist = min(calculate_2d_distance((city_x, city_z), ep) for ep in enemy_points) if enemy_points else float('inf')
            
            # Add some randomization: 10% chance city goes to opposite team (contested)
            contested_chance = rng.random()
            if contested_chance < 0.1:  # 10% contested cities
                # Assign to opposite team (creates interesting territory boundaries)
                if min_friendly_dist < min_enemy_dist:
                    strategic_points.append((city_x, city_z))
                    point_types.append('enemy')  # Friendly city captured by enemy
                else:
                    strategic_points.append((city_x, city_z))
                    point_types.append('friendly')  # Enemy city captured by friendly
            else:
                # Normal assignment
                if min_friendly_dist < min_enemy_dist:
                    strategic_points.append((city_x, city_z))
                    point_types.append('friendly')
                else:
                    strategic_points.append((city_x, city_z))
                    point_types.append('enemy')
    except Exception:
        pass
    
    # Add mission objective locations if available
    try:
        for obj in mission_plan.objectives:
            # Handle PlanObjective dataclass or dict
            if hasattr(obj, 'target'):
                target = obj.target
            elif isinstance(obj, dict):
                target = obj.get('target') or obj.get('data', {}).get('target_location')
            else:
                target = None
            
            if target and isinstance(target, (list, tuple)) and len(target) >= 2:
                target_2d = (target[0], target[2] if len(target) >= 3 else target[1])
                strategic_points.append(target_2d)
                point_types.append('enemy')  # Objectives typically in enemy territory
    except Exception:
        pass
    
    # Ensure we have at least a few points for each territory
    friendly_count = sum(1 for t in point_types if t == 'friendly')
    enemy_count = sum(1 for t in point_types if t == 'enemy')
    
    if friendly_count == 0:
        strategic_points.append((map_size * 0.2, map_size * 0.2))
        point_types.append('friendly')
    if enemy_count == 0:
        strategic_points.append((map_size * 0.8, map_size * 0.8))
        point_types.append('enemy')
    
    # Step 2: Generate Voronoi diagram
    if len(strategic_points) < 2:
        # Fallback: simple split
        define_territory_from_mission_config(
            wsm, (map_size / 2, map_size / 2),
            enemy_territory_radius=map_size * 0.4,
            friendly_territory_radius=map_size * 0.3
        )
        return
    
    # Convert to numpy array for Voronoi
    points_array = np.array(strategic_points)
    
    # Add boundary points to ensure Voronoi covers entire map
    margin = map_size * 0.1
    boundary_points = [
        (-margin, -margin),  # Southwest
        (map_size + margin, -margin),  # Southeast
        (map_size + margin, map_size + margin),  # Northeast
        (-margin, map_size + margin)  # Northwest
    ]
    
    all_points = np.vstack([points_array, np.array(boundary_points)])
    
    # Generate Voronoi diagram
    vor = Voronoi(all_points)
    
    # Step 3: Assign Voronoi cells to territory types and refine boundaries
    # Map each Voronoi region to a territory type
    region_to_territory = {}
    
    for point_idx, point_type in enumerate(point_types):
        region_idx = vor.point_region[point_idx]
        region_to_territory[region_idx] = point_type
    
    # Collect all boundary vertices
    boundary_vertices = {}  # territory_type -> list of polygon vertices
    
    # Process each Voronoi region
    for region_idx, territory_type in region_to_territory.items():
        if region_idx == -1:  # Invalid region
            continue
        
        region = vor.regions[region_idx]
        if -1 in region:  # Region extends to infinity
            continue
        
        # Get vertices for this region
        region_vertices = []
        for vertex_idx in region:
            if vertex_idx != -1:
                vertex = vor.vertices[vertex_idx]
                region_vertices.append((float(vertex[0]), float(vertex[1])))
        
        if len(region_vertices) >= 3:
            # Clip vertices to map bounds
            clipped_vertices = []
            for vx, vz in region_vertices:
                clipped_vertices.append((
                    max(0, min(vx, map_size)),
                    max(0, min(vz, map_size))
                ))
            
            if territory_type not in boundary_vertices:
                boundary_vertices[territory_type] = []
            boundary_vertices[territory_type].extend(clipped_vertices)
    
    # Step 4: Refine boundaries using roads (if enabled)
    if use_natural_boundaries:
        try:
            road_segments = getattr(terrain_calculator, 'road_segments', [])
            if road_segments:
                # For each territory, refine boundary segments near roads
                # This is simplified - in practice, would refine actual boundary edges
                # For now, we'll adjust vertices near roads
                refined_vertices = {}
                
                for territory_type, vertices in boundary_vertices.items():
                    refined_verts = []
                    for i, vertex in enumerate(vertices):
                        # Check if this vertex is near a road
                        from ..misc.math_utils import calculate_2d_distance
                        nearest_road_dist = float('inf')
                        nearest_road_point = None
                        
                        for road_seg in road_segments:
                            if isinstance(road_seg, dict):
                                road_start = road_seg.get('start', (0, 0, 0))
                                road_end = road_seg.get('end', (0, 0, 0))
                            else:
                                road_start, road_end = road_seg
                            
                            if len(road_start) >= 3:
                                r_start_2d = (road_start[0], road_start[2])
                            else:
                                r_start_2d = (road_start[0], road_start[1])
                            
                            if len(road_end) >= 3:
                                r_end_2d = (road_end[0], road_end[2])
                            else:
                                r_end_2d = (road_end[0], road_end[1])
                            
                            # Check distance to road segment midpoint
                            road_mid = ((r_start_2d[0] + r_end_2d[0]) / 2, (r_start_2d[1] + r_end_2d[1]) / 2)
                            dist = calculate_2d_distance(vertex, road_mid)
                            
                            if dist < nearest_road_dist and dist < 500:  # 500m threshold
                                nearest_road_dist = dist
                                nearest_road_point = road_mid
                        
                        # If near a road, snap to it slightly
                        if nearest_road_point:
                            # Blend original vertex with road point
                            blend = 0.3  # 30% toward road
                            refined_vertex = (
                                vertex[0] * (1 - blend) + nearest_road_point[0] * blend,
                                vertex[1] * (1 - blend) + nearest_road_point[1] * blend
                            )
                            refined_verts.append(refined_vertex)
                        else:
                            refined_verts.append(vertex)
                    
                    refined_vertices[territory_type] = refined_verts
                
                boundary_vertices = refined_vertices
        except Exception:
            pass  # If road refinement fails, continue without it
    
    # Step 5: Merge Voronoi regions into territory polygons
    # We'll sample the map and assign each point to the nearest strategic point
    # Then create a boundary polygon from the Voronoi diagram
    
    def _get_region_boundary(territory_type: str, vor: Voronoi, map_size: float) -> List[Tuple[float, float]]:
        """
        Create a boundary polygon by sampling the map on a fine grid and tracing the boundary.
        This creates jagged boundaries that accurately follow the Voronoi diagram.
        """
        # Use coarser resolution for smoother, less jagged boundaries
        sample_resolution = max(3000, map_size / 60)  # Coarser grid = smoother boundaries
        
        from ..misc.math_utils import calculate_2d_distance
        
        # Create grid and determine territory membership
        territory_grid = {}  # (x, z) -> bool
        grid_points = []
        
        for x in np.arange(0, map_size, sample_resolution):
            for z in np.arange(0, map_size, sample_resolution):
                grid_points.append((x, z))
                
                # Find nearest strategic point to determine territory
                min_dist = float('inf')
                nearest_type = None
                
                for point, ptype in zip(strategic_points, point_types):
                    dist = calculate_2d_distance((x, z), point)
                    if dist < min_dist:
                        min_dist = dist
                        nearest_type = ptype
                
                territory_grid[(x, z)] = (nearest_type == territory_type)
        
        # Find boundary points (territory points adjacent to non-territory points)
        boundary_points = []
        boundary_set = set()
        
        for x, z in grid_points:
            if not territory_grid.get((x, z), False):
                continue
            
            # Check 8 neighbors
            neighbors = [
                (x - sample_resolution, z),
                (x + sample_resolution, z),
                (x, z - sample_resolution),
                (x, z + sample_resolution),
                (x - sample_resolution, z - sample_resolution),
                (x + sample_resolution, z + sample_resolution),
                (x - sample_resolution, z + sample_resolution),
                (x + sample_resolution, z - sample_resolution),
            ]
            
            is_boundary = False
            for nx, nz in neighbors:
                if not territory_grid.get((nx, nz), False):
                    is_boundary = True
                    break
            
            if is_boundary:
                boundary_set.add((x, z))
        
        boundary_points = list(boundary_set)
        
        if len(boundary_points) < 3:
            return []
        
        # Trace the boundary by following connected boundary points
        # Start with a point on the boundary
        if not boundary_points:
            return []
        
        # Group boundary points into a polygon
        # Use a simplified approach: sort by angle from centroid for outer boundary
        centroid = (
            sum(p[0] for p in boundary_points) / len(boundary_points),
            sum(p[1] for p in boundary_points) / len(boundary_points)
        )
        
        def angle_from_centroid(point):
            dx = point[0] - centroid[0]
            dz = point[1] - centroid[1]
            return np.arctan2(dz, dx)
        
        # Sort by angle and create polygon
        sorted_points = sorted(boundary_points, key=angle_from_centroid)
        
        # Simplify boundary using Douglas-Peucker-like algorithm
        # Keep points that form significant angles or are far enough apart
        
        def _simplify_polyline(points: List[Tuple[float, float]], 
                               tolerance: float) -> List[Tuple[float, float]]:
            """Simplify polyline using distance-based simplification."""
            if len(points) <= 2:
                return points
            
            simplified = [points[0]]
            
            for i in range(1, len(points) - 1):
                prev = simplified[-1]
                curr = points[i]
                next_pt = points[i + 1]
                
                # Calculate distance from current point to line segment prev->next
                # If distance is significant, keep the point
                dx = next_pt[0] - prev[0]
                dz = next_pt[1] - prev[1]
                segment_length_sq = dx*dx + dz*dz
                
                if segment_length_sq < 0.001:  # Degenerate segment
                    continue
                
                # Project current point onto line segment
                t = max(0, min(1, ((curr[0] - prev[0])*dx + (curr[1] - prev[1])*dz) / segment_length_sq))
                proj = (prev[0] + t*dx, prev[1] + t*dz)
                
                # Distance from current to projected point
                dist_sq = (curr[0] - proj[0])**2 + (curr[1] - proj[1])**2
                
                # Also check angle (keep sharp corners)
                from ..misc.math_utils import calculate_2d_distance
                angle_change = abs(calculate_2d_distance(prev, curr) + 
                                 calculate_2d_distance(curr, next_pt) - 
                                 calculate_2d_distance(prev, next_pt))
                
                if dist_sq > tolerance**2 or angle_change > tolerance:
                    simplified.append(curr)
            
            simplified.append(points[-1])
            return simplified
        
        # Simplify with adaptive tolerance (higher tolerance = fewer sharp corners)
        tolerance = sample_resolution * 8  # Higher tolerance for smoother boundaries
        simplified = _simplify_polyline(sorted_points, tolerance)
        
        # Further simplify by keeping only significant vertices
        # Remove points that are too close together
        filtered_points = []
        min_dist = sample_resolution * 10  # Larger minimum distance for smoother curves
        
        for point in simplified:
            if not filtered_points:
                filtered_points.append(point)
            else:
                last_point = filtered_points[-1]
                dist = calculate_2d_distance(point, last_point)
                if dist >= min_dist:
                    filtered_points.append(point)
        
        # Ensure we have a reasonable number of points (15-40 for smooth, natural boundaries)
        # Fewer points = smoother boundaries (less star-like)
        if len(filtered_points) > 40:
            # More aggressive reduction
            step = len(filtered_points) // 30
            filtered_points = filtered_points[::max(1, step)]
        
        # Further simplify by removing points that don't contribute much to shape
        # Keep only points that create significant angles
        if len(filtered_points) > 20:
            simplified_final = [filtered_points[0]]
            angle_threshold = math.radians(15)  # Keep points with >15 degree angle change
            
            for i in range(1, len(filtered_points) - 1):
                prev = simplified_final[-1]
                curr = filtered_points[i]
                next_pt = filtered_points[i + 1]
                
                # Calculate angle at this point
                vec1 = (curr[0] - prev[0], curr[1] - prev[1])
                vec2 = (next_pt[0] - curr[0], next_pt[1] - curr[1])
                
                # Normalize vectors
                len1 = math.sqrt(vec1[0]**2 + vec1[1]**2)
                len2 = math.sqrt(vec2[0]**2 + vec2[1]**2)
                
                if len1 > 0.001 and len2 > 0.001:
                    # Calculate angle between vectors
                    dot = (vec1[0] * vec2[0] + vec1[1] * vec2[1]) / (len1 * len2)
                    dot = max(-1, min(1, dot))  # Clamp to valid range
                    angle = math.acos(dot)
                    
                    # Keep point if angle is significant
                    if angle > angle_threshold or i % 2 == 0:  # Keep every other point too
                        simplified_final.append(curr)
            
            simplified_final.append(filtered_points[-1])
            filtered_points = simplified_final
        
        if len(filtered_points) < 8:
            # Fallback to convex hull if too few points
            hull = []
            for point in sorted_points:
                while len(hull) > 1:
                    p1, p2, p3 = hull[-2], hull[-1], point
                    cross = (p2[0] - p1[0]) * (p3[1] - p1[1]) - (p2[1] - p1[1]) * (p3[0] - p1[0])
                    if cross > 0:
                        break
                    hull.pop()
                hull.append(point)
            filtered_points = hull if len(hull) >= 3 else filtered_points
        
        # Apply strong smoothing to reduce sharp angles (moving average with larger window)
        if len(filtered_points) >= 5:
            # Apply multiple passes of smoothing for better results
            for smooth_pass in range(3):  # 3 passes for smoother boundaries
                smoothed_points = []
                window_size = 7  # Even larger window for very smooth curves
                
                for i in range(len(filtered_points)):
                    # Get neighboring points for averaging (wrap around for closed polygon)
                    indices = []
                    for offset in range(-window_size//2, window_size//2 + 1):
                        idx = (i + offset) % len(filtered_points)
                        indices.append(idx)
                    
                    # Average positions with weighted average (closer points have more weight)
                    weights = []
                    positions = []
                    for j in indices:
                        dist = abs(j - i)
                        if dist > len(filtered_points) / 2:
                            dist = len(filtered_points) - dist
                        weight = 1.0 / (1.0 + dist * 0.3)  # Softer distance weighting
                        weights.append(weight)
                        positions.append(filtered_points[j])
                    
                    total_weight = sum(weights)
                    avg_x = sum(p[0] * w for p, w in zip(positions, weights)) / total_weight
                    avg_z = sum(p[1] * w for p, w in zip(positions, weights)) / total_weight
                    
                    # Very strong smoothing: 85% smoothed, 15% original
                    original = filtered_points[i]
                    smoothed_points.append((
                        original[0] * 0.15 + avg_x * 0.85,
                        original[1] * 0.15 + avg_z * 0.85
                    ))
                
                filtered_points = smoothed_points
        
        # Apply curve interpolation to create smooth transitions between points
        if len(filtered_points) >= 8:
            # Use Catmull-Rom spline interpolation for smooth curves
            def _interpolate_smooth_curve(points: List[Tuple[float, float]], 
                                        num_segments: int = 3) -> List[Tuple[float, float]]:
                """Create smooth curve between points using linear interpolation with extra points."""
                if len(points) < 2:
                    return points
                
                smooth_points = []
                # Ensure closed curve
                closed_points = points + [points[0]] if points[0] != points[-1] else points
                
                for i in range(len(closed_points) - 1):
                    p1 = closed_points[i]
                    p2 = closed_points[(i + 1) % len(points)]
                    
                    # Add the start point
                    if i == 0:
                        smooth_points.append(p1)
                    
                    # Add interpolated points between p1 and p2
                    for t in np.linspace(0, 1, num_segments + 1)[1:]:  # Skip t=0 (already added)
                        # Simple linear interpolation (can be upgraded to spline later)
                        x = p1[0] + t * (p2[0] - p1[0])
                        z = p1[1] + t * (p2[1] - p1[1])
                        smooth_points.append((x, z))
                
                # Remove last point if it's duplicate of first (closed curve)
                if len(smooth_points) > 1 and smooth_points[0] == smooth_points[-1]:
                    smooth_points.pop()
                
                return smooth_points
            
            # Skip curve interpolation - smoothing is already sufficient
            # filtered_points = _interpolate_smooth_curve(filtered_points, num_segments=2)
        
        if len(filtered_points) >= 8:
            # Ensure closed
            if filtered_points[0] != filtered_points[-1]:
                filtered_points.append(filtered_points[0])
            return filtered_points
        
        # Fallback to convex hull for simple shapes
        hull = []
        for point in sorted_points:
            while len(hull) > 1:
                p1, p2, p3 = hull[-2], hull[-1], point
                cross = (p2[0] - p1[0]) * (p3[1] - p1[1]) - (p2[1] - p1[1]) * (p3[0] - p1[0])
                if cross > 0:
                    break
                hull.pop()
            hull.append(point)
        
        return hull if len(hull) >= 3 else []
    
    def _get_boundary_by_sampling(territory_type: str, map_size: float) -> List[Tuple[float, float]]:
        """Fallback: sample map on grid to find boundary."""
        sample_resolution = max(2000, map_size / 50)
        boundary_points = []
        from ..misc.math_utils import calculate_2d_distance
        
        sample_grid = []
        for x in np.arange(0, map_size, sample_resolution):
            for z in np.arange(0, map_size, sample_resolution):
                sample_grid.append((x, z))
        
        territory_mask = {}
        for x, z in sample_grid:
            min_dist = float('inf')
            nearest_type = None
            for point, ptype in zip(strategic_points, point_types):
                dist = calculate_2d_distance((x, z), point)
                if dist < min_dist:
                    min_dist = dist
                    nearest_type = ptype
            territory_mask[(x, z)] = (nearest_type == territory_type)
        
        boundary_points_set = set()
        for x, z in sample_grid:
            if not territory_mask.get((x, z), False):
                continue
            neighbors = [
                (x - sample_resolution, z), (x + sample_resolution, z),
                (x, z - sample_resolution), (x, z + sample_resolution),
            ]
            for nx, nz in neighbors:
                if not territory_mask.get((nx, nz), False):
                    boundary_points_set.add((x, z))
                    break
        
        if len(boundary_points_set) < 3:
            return []
        
        boundary_points = list(boundary_points_set)
        centroid = (
            sum(p[0] for p in boundary_points) / len(boundary_points),
            sum(p[1] for p in boundary_points) / len(boundary_points)
        )
        
        def angle_from_centroid(point):
            dx = point[0] - centroid[0]
            dz = point[1] - centroid[1]
            return np.arctan2(dz, dx)
        
        sorted_points = sorted(boundary_points, key=angle_from_centroid)
        hull = []
        for point in sorted_points:
            while len(hull) > 1:
                p1, p2, p3 = hull[-2], hull[-1], point
                cross = (p2[0] - p1[0]) * (p3[1] - p1[1]) - (p2[1] - p1[1]) * (p3[0] - p1[0])
                if cross > 0:
                    break
                hull.pop()
            hull.append(point)
        
        return hull if len(hull) >= 3 else []
    
    # Step 6: Create territory polygons from Voronoi regions
    # For each territory type, merge all Voronoi regions assigned to that type
    
    for territory_type in ['friendly', 'enemy']:
        territory_polygon = _get_region_boundary(territory_type, vor, map_size)
        
        if len(territory_polygon) >= 3:
            # Refine polygon by ensuring it's clipped to map bounds
            clipped_polygon = []
            for vx, vz in territory_polygon:
                clipped_polygon.append((
                    max(0, min(vx, map_size)),
                    max(0, min(vz, map_size))
                ))
            
            # Remove any duplicate consecutive points
            cleaned_polygon = []
            for i, point in enumerate(clipped_polygon):
                if i == 0 or point != clipped_polygon[i-1]:
                    cleaned_polygon.append(point)
            
            # Apply road-snapping refinement if enabled
            if use_natural_boundaries and len(cleaned_polygon) >= 3:
                try:
                    road_segments = getattr(terrain_calculator, 'road_segments', [])
                    if road_segments:
                        refined_polygon = []
                        from ..misc.math_utils import calculate_2d_distance
                        
                        for i, vertex in enumerate(cleaned_polygon):
                            # Check if vertex is near a road
                            nearest_road_dist = float('inf')
                            nearest_road_point = None
                            
                            for road_seg in road_segments:
                                if isinstance(road_seg, dict):
                                    road_start = road_seg.get('start', (0, 0, 0))
                                    road_end = road_seg.get('end', (0, 0, 0))
                                else:
                                    road_start, road_end = road_seg
                                
                                if len(road_start) >= 3:
                                    r_start_2d = (road_start[0], road_start[2])
                                else:
                                    r_start_2d = (road_start[0], road_start[1])
                                
                                if len(road_end) >= 3:
                                    r_end_2d = (road_end[0], road_end[2])
                                else:
                                    r_end_2d = (road_end[0], road_end[1])
                                
                                # Check distance to road segment
                                road_mid = ((r_start_2d[0] + r_end_2d[0]) / 2, (r_start_2d[1] + r_end_2d[1]) / 2)
                                dist = calculate_2d_distance(vertex, road_mid)
                                
                                if dist < nearest_road_dist and dist < 1000:  # 1km threshold
                                    nearest_road_dist = dist
                                    nearest_road_point = road_mid
                            
                            # If near a road, blend towards it (makes boundaries follow roads)
                            if nearest_road_point and nearest_road_dist < 1000:
                                blend = 0.5  # 50% toward road for stronger effect
                                refined_vertex = (
                                    vertex[0] * (1 - blend) + nearest_road_point[0] * blend,
                                    vertex[1] * (1 - blend) + nearest_road_point[1] * blend
                                )
                                refined_polygon.append(refined_vertex)
                            else:
                                refined_polygon.append(vertex)
                        
                        cleaned_polygon = refined_polygon
                except Exception:
                    pass  # If road refinement fails, use original polygon
            
            if len(cleaned_polygon) >= 3:
                # Ensure polygon is closed
                if cleaned_polygon[0] != cleaned_polygon[-1]:
                    cleaned_polygon.append(cleaned_polygon[0])
                
                define_territory_polygon(wsm, cleaned_polygon, territory_type)
    
    # Step 7: Validate base assignments - check if bases are in appropriate territories
    try:
        all_bases = terrain_calculator.get_all_bases()
        from ..misc.logger import create_logger
        logger = create_logger(verbose=True, name="TerritorySystem")
        
        base_reassignments = []
        
        for base in all_bases:
            pos = base.get('position', (0, 0, 0))
            if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                base_x = pos[0]
                base_z = pos[2] if len(pos) >= 3 else pos[1]
                base_name = base.get('name', f'Base {base.get("id", "?")}')
                
                # Determine which territory this base is actually in
                actual_territory = wsm.get_territory_at_position(base_x, base_z)
                
                # Determine what we assigned it as (based on initial strategic points)
                # Find which strategic point was nearest to this base
                from ..misc.math_utils import calculate_2d_distance
                base_2d = (base_x, base_z)
                min_dist = float('inf')
                assigned_type = None
                
                for point, ptype in zip(strategic_points, point_types):
                    dist = calculate_2d_distance(base_2d, point)
                    if dist < min_dist:
                        min_dist = dist
                        assigned_type = ptype
                
                # Check if base is in wrong territory
                if actual_territory and assigned_type:
                    expected_territory = assigned_type  # friendly or enemy
                    
                    # Base should be in its assigned territory OR neutral
                    if actual_territory != expected_territory and actual_territory != 'neutral':
                        # Base is in the wrong territory - this is a problem!
                        # Calculate how far into wrong territory
                        wrong_territory_distance = min_dist
                        
                        # Check if base is deep in wrong territory (>10% of map size from boundary)
                        is_deep_in_wrong_territory = wrong_territory_distance > map_size * 0.10
                        
                        logger.warning(
                            f"Base '{base_name}' (ID: {base.get('id', '?')}) at ({base_x:.0f}, {base_z:.0f}) "
                            f"was assigned as '{expected_territory}' but is in '{actual_territory}' territory. "
                            f"Distance to nearest {expected_territory} strategic point: {min_dist:.0f}m. "
                            f"{'This base is deep in enemy territory and should NOT be used!' if is_deep_in_wrong_territory else 'Consider adjusting territory boundaries.'}"
                        )
                        base_reassignments.append({
                            'base': base,
                            'name': base_name,
                            'position': (base_x, base_z),
                            'assigned_as': expected_territory,
                            'actual_territory': actual_territory,
                            'distance_to_assigned': min_dist,
                            'is_deep_in_wrong': is_deep_in_wrong_territory
                        })
                    elif actual_territory == 'neutral':
                        # Base is in neutral territory
                        if min_dist < map_size * 0.15:
                            # Close to assigned territory - acceptable (no man's land)
                            logger.info(
                                f"Base '{base_name}' is in neutral territory near {expected_territory} zone "
                                f"({min_dist:.0f}m from nearest {expected_territory} strategic point) - acceptable"
                            )
                        else:
                            # Far from assigned territory - might be issue
                            logger.warning(
                                f"Base '{base_name}' is in neutral territory but far from {expected_territory} zone "
                                f"({min_dist:.0f}m away) - consider if this assignment makes sense"
                            )
                    else:
                        # Base is correctly in its assigned territory
                        pass
        
        # If we found problematic base assignments, provide summary
        if base_reassignments:
            logger.warning(
                f"Found {len(base_reassignments)} base(s) in incorrect territories. "
                f"Consider adjusting territory boundaries or base assignments."
            )
            for reassign in base_reassignments:
                logger.warning(
                    f"  - {reassign['name']}: assigned as '{reassign['assigned_as']}' "
                    f"but in '{reassign['actual_territory']}' territory"
                )
    except Exception as e:
        # Don't fail if validation has issues
        pass
