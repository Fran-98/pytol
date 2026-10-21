"""
Provides the MissionTerrainHelper class, an advanced query engine for mission
generation using data from a TerrainCalculator instance.
"""
import numpy as np
import random
from scipy.spatial.transform import Rotation as R
from scipy.spatial import cKDTree
from .terrain_calculator import TerrainCalculator
from ..misc.logger import create_logger

class MissionTerrainHelper:
    """
    Uses a TerrainCalculator instance to provide high-level, mission-centric
    data queries about the map, such as finding landing zones, road points,
    and tactical locations.
    """

    def __init__(self, terrain_calculator: TerrainCalculator, verbose: bool = None):
        """
        Initializes the helper with a pre-loaded TerrainCalculator instance.

        Args:
            terrain_calculator: An initialized instance of the TerrainCalculator class.
            verbose: Whether to print progress messages. If None, inherits from terrain_calculator.
        """
        if not isinstance(terrain_calculator, TerrainCalculator):
            raise TypeError("The provided argument must be an instance of TerrainCalculator.")
        self.tc = terrain_calculator
        self.verbose = verbose if verbose is not None else terrain_calculator.verbose
        self.logger = create_logger(verbose=self.verbose, name="MissionTerrainHelper")
        self._bridges = None
        # Get map size for scale-aware calculations
        self.map_size = getattr(terrain_calculator, 'total_map_size_meters', 196608.0)
        self._log("MissionTerrainHelper initialized.")
    
    def get_unit_spacing_requirement(self, unit_type_str: str) -> float:
        """Get minimum spacing requirement for a unit type in meters.
        
        This accounts for unit footprint size - trucks need less space than SAM sites.
        This should be used when placing multiple units to prevent overlap/clustering.
        
        Args:
            unit_type_str: Unit type string (e.g., "sam_site", "truck", "artillery")
        
        Returns:
            Minimum spacing in meters
        """
        unit_lower = unit_type_str.lower()
        
        # Large systems need more space
        if any(kw in unit_lower for kw in ["sam", "radar", "launcher", "battery", "air_defense"]):
            return 2000.0  # 2km spacing for SAM sites (large radar coverage)
        elif any(kw in unit_lower for kw in ["artillery", "howitzer", "mlrs"]):
            return 1000.0  # 1km spacing for artillery (indirect fire safety zone)
        elif any(kw in unit_lower for kw in ["tank", "apc", "vehicle", "armor"]):
            return 300.0  # 300m spacing for vehicles (tactical separation)
        elif any(kw in unit_lower for kw in ["truck", "transport", "logistic", "convoy"]):
            return 100.0  # 100m spacing for trucks (can convoy closer)
        elif any(kw in unit_lower for kw in ["infantry", "soldier", "squad"]):
            return 50.0  # 50m spacing for infantry
        else:
            return 500.0  # Default 500m spacing for unknown units
    
    def scale_search_radius_by_map_size(self, base_radius: float) -> float:
        """Scale search radius based on map size.
        
        On large maps (196km+), use full radius. On smaller maps, scale down proportionally.
        This ensures tactical distances remain meaningful across different map scales.
        
        Args:
            base_radius: Base search radius in meters
        
        Returns:
            Scaled search radius appropriate for this map size
        """
        # Scale based on map size relative to typical 196km map
        typical_map_size = 196608.0
        if self.map_size >= typical_map_size:
            # Large map, can use full radius
            return base_radius * 1.0
        else:
            # Smaller map, scale down proportionally (minimum 20% of base)
            scale_factor = max(0.2, self.map_size / typical_map_size)
            return base_radius * scale_factor
    
    def check_spacing_from_existing_units(self, candidate_pos: tuple, 
                                         existing_positions: list, 
                                         min_spacing: float) -> bool:
        """Check if a candidate position has sufficient spacing from existing unit positions.
        
        Args:
            candidate_pos: Candidate position (x, y, z) tuple
            existing_positions: List of existing positions [(x1, y1, z1), (x2, y2, z2), ...]
            min_spacing: Minimum required spacing in meters
        
        Returns:
            True if position has sufficient spacing, False otherwise
        """
        if not existing_positions:
            return True
        
        from ..misc.math_utils import calculate_2d_distance
        candidate_2d = (candidate_pos[0], candidate_pos[2])
        
        for existing_pos in existing_positions:
            if len(existing_pos) < 3:
                continue
            existing_2d = (existing_pos[0], existing_pos[2])
            dist = calculate_2d_distance(candidate_2d, existing_2d)
            if dist < min_spacing:
                return False
        return True
    
    def _log(self, message: str):
        """Route messages through centralized logger with simple level detection."""
        msg = str(message).lstrip()
        lower = msg.lower()
        if lower.startswith("warning") or msg.startswith("⚠"):
            self.logger.warning(msg)
        elif lower.startswith("error") or lower.startswith("fatal"):
            self.logger.error(msg)
        else:
            self.logger.info(msg)

    # --- Core Terrain and Objects queries ---
    
    def get_terrain_height_safe(self, x: float, z: float, default: float = 0.0) -> float:
        """
        Get terrain height with error handling and default fallback.
        
        Args:
            x: World X coordinate
            z: World Z coordinate
            default: Default height if query fails
            
        Returns:
            Terrain height or default value
        """
        try:
            height = self.tc.get_terrain_height(x, z)
            return height if height is not None else default
        except Exception as e:
            self._log(f"Warning: Terrain height query failed at ({x:.1f}, {z:.1f}): {e}")
            return default
    
    def sample_terrain_heights(self, positions: list) -> list:
        """
        Sample terrain heights for multiple positions efficiently.
        
        Args:
            positions: List of (x, z) tuples
            
        Returns:
            List of heights corresponding to positions
        """
        heights = []
        for x, z in positions:
            height = self.get_terrain_height_safe(x, z)
            heights.append(height)
        return heights
    
    def get_terrain_height_with_position(self, x: float, z: float, altitude_agl: float = 0.0):
        """
        Get terrain height and return complete 3D position.
        
        Args:
            x: World X coordinate
            z: World Z coordinate
            altitude_agl: Altitude above ground level to add
            
        Returns:
            Tuple of (x, y + altitude_agl, z)
        """
        y = self.get_terrain_height_safe(x, z)
        return (x, y + altitude_agl, z)

    def _validate_position_against_constraints(self, pos_2d, constraint_area=None, excluded_areas=None, position_validator=None):
        """Helper function to validate a position (x, z) against territory constraints.
        
        Args:
            pos_2d: Position tuple (x, z)
            constraint_area: Optional constraint area dict (see find_observation_post for format)
            excluded_areas: Optional list of excluded area dicts
            position_validator: Optional callable(pos_2d) -> bool
        
        Returns:
            bool: True if position is allowed, False otherwise
        """
        from ..misc.math_utils import is_position_in_circle
        x, z = pos_2d
        
        # Check if in constraint area (if specified)
        if constraint_area:
            if constraint_area.get('type') == 'circle':
                center = constraint_area['center']
                radius = constraint_area['radius']
                if not is_position_in_circle((x, z), center, radius):
                    return False
            elif constraint_area.get('type') == 'polygon':
                vertices = constraint_area.get('vertices', [])
                if vertices and not self.tc._point_in_polygon(x, z, vertices):
                    return False
        
        # Check if in excluded areas
        if excluded_areas:
            for excluded in excluded_areas:
                if excluded.get('type') == 'circle':
                    center = excluded['center']
                    radius = excluded['radius']
                    if is_position_in_circle((x, z), center, radius):
                        return False
                elif excluded.get('type') == 'polygon':
                    vertices = excluded.get('vertices', [])
                    if vertices and self.tc._point_in_polygon(x, z, vertices):
                        return False
        
        # Check custom validator
        if position_validator:
            try:
                if not position_validator((x, z)):
                    return False
            except Exception:
                return False
        
        return True
    
    def has_line_of_sight(self, pos1, pos2, steps=20, terrain_offset=0):
        """
        True if the straight line between two (x, y, z) points stays above the terrain (buildings ignored).

        Samples at least every 50 m (heightmap pixels are ~150 m), so long sight lines don't skip ridges.
        """
        p1, p2 = np.asarray(pos1, dtype=float), np.asarray(pos2, dtype=float)
        n = max(steps, int(np.linalg.norm(p2 - p1) / 50.0))
        pts = p1 + np.linspace(0, 1, n + 2)[:, None] * (p2 - p1)
        return bool(np.all(pts[:, 1] >= self.tc.get_terrain_height(pts[:, 0], pts[:, 2]) + terrain_offset))

    def find_observation_post(self, target_area, min_dist, max_dist, num_candidates=20, 
                             constraint_area=None, excluded_areas=None, position_validator=None,
                             existing_unit_positions=None, min_spacing_from_units=None):
        """
        Finds a high-altitude point with LoS to a target, ideal for recon or sniper units.

        Why it's useful: Automates placing spotters, snipers, or SEAD radars in tactically sound positions.
        
        How it works (Math):
        1. It generates random points on an annulus (a ring) around the target area using polar coordinates.
           - `r = sqrt(rand()) * (max_dist - min_dist) + min_dist` (for uniform distribution)
           - `theta = rand() * 2 * pi`
           - `x = cx + r * cos(theta)`, `z = cz + r * sin(theta)`
        2. It gets the terrain height at each point and sorts candidates by altitude (highest first).
        3. It checks Line of Sight (LoS) from the highest candidates to the target and returns the first valid one.
        4. If constraint_area or excluded_areas are provided, candidates are filtered accordingly.

        Args:
            target_area (tuple): The (x, y, z) coordinate of the target to be observed.
            min_dist (float): The minimum distance from the target.
            max_dist (float): The maximum distance from the target.
            num_candidates (int): The number of random points to test.
            constraint_area (dict, optional): Constraint area specification:
                - {'type': 'circle', 'center': (x, z), 'radius': float} for circular constraint
                - {'type': 'polygon', 'vertices': [(x1, z1), (x2, z2), ...]} for polygonal constraint
            excluded_areas (list, optional): List of constraint_area dicts to exclude (same format as constraint_area).
            position_validator (callable, optional): Function(position) -> bool to validate candidate positions.
            existing_unit_positions (list, optional): List of existing unit positions [(x1, y1, z1), ...] to avoid.
            min_spacing_from_units (float, optional): Minimum spacing from existing units in meters. If None, uses default based on unit type.

        Returns:
            tuple: The (x, y, z) coordinate of a suitable observation post, or None.
        """
        from ..misc.math_utils import generate_random_position_in_circle, is_position_in_circle
        
        def _is_position_allowed(pos_2d):
            """Check if position (x, z) is allowed based on constraints."""
            x, z = pos_2d
            
            # Check if in constraint area (if specified)
            if constraint_area:
                if constraint_area.get('type') == 'circle':
                    center = constraint_area['center']
                    radius = constraint_area['radius']
                    if not is_position_in_circle((x, z), center, radius):
                        return False
                elif constraint_area.get('type') == 'polygon':
                    # Use point-in-polygon check from terrain calculator
                    vertices = constraint_area.get('vertices', [])
                    if vertices and not self.tc._point_in_polygon(x, z, vertices):
                        return False
            
            # Check if in excluded areas
            if excluded_areas:
                for excluded in excluded_areas:
                    if excluded.get('type') == 'circle':
                        center = excluded['center']
                        radius = excluded['radius']
                        if is_position_in_circle((x, z), center, radius):
                            return False
                    elif excluded.get('type') == 'polygon':
                        vertices = excluded.get('vertices', [])
                        if vertices and self.tc._point_in_polygon(x, z, vertices):
                            return False
            
            # Check custom validator
            if position_validator:
                try:
                    if not position_validator((x, z)):
                        return False
                except Exception:
                    return False
            
            return True
        
        candidates = []
        attempts = 0
        max_attempts = num_candidates * 3  # Try more times if constraints are tight
        
        while len(candidates) < num_candidates and attempts < max_attempts:
            attempts += 1
            # Uniform distribution within the annulus
            x, z = generate_random_position_in_circle(
                (target_area[0], target_area[2]), max_dist, min_dist, uniform_distribution=True
            )
            
            # Check if position is allowed by constraints
            if not _is_position_allowed((x, z)):
                continue
            
            y = self.tc.get_terrain_height(x, z)
            if y is not None:
                candidate_pos = (x, y, z)
                # Check spacing from existing units if provided
                if existing_unit_positions and min_spacing_from_units:
                    if not self.check_spacing_from_existing_units(candidate_pos, existing_unit_positions, min_spacing_from_units):
                        continue
                candidates.append(candidate_pos)
        
        # Sort by elevation, highest first
        candidates.sort(key=lambda p: p[1], reverse=True)

        for post in candidates:
            # Check LoS from unit height above ground at the post to the target
            # Use 8m offset for radar/SAM units (typical radar mast height), 2m for infantry
            unit_height = 8.0  # Default for observation posts (typically radar/SAM)
            if self.has_line_of_sight((post[0], post[1] + unit_height, post[2]), target_area):
                return post
        return None

    def find_artillery_position(self, target_area, search_radius, standoff_dist=1000,
                                constraint_area=None, excluded_areas=None, position_validator=None,
                                existing_unit_positions=None, min_spacing_from_units=None):
        """
        Finds a position hidden from a target, suitable for indirect fire.

        Why it's useful: Realistically places artillery that can't be seen by the target, requiring other units to spot for it.

        How it works (Math):
        1. Similar to the observation post, it samples points around the target.
        2. It prioritizes points that are *behind* terrain features relative to the target.
        3. It returns the first valid point that *fails* the Line of Sight check.
        4. If constraint_area or excluded_areas are provided, candidates are filtered accordingly.

        Args:
            target_area (tuple): The (x, y, z) of the target.
            search_radius (float): The radius around the target to search within. Will be scaled by map size.
            standoff_dist (float): Minimum distance to keep from the target.
            constraint_area (dict, optional): Constraint area specification (see find_observation_post).
            excluded_areas (list, optional): List of excluded areas (see find_observation_post).
            position_validator (callable, optional): Function(position) -> bool to validate positions.
            existing_unit_positions (list, optional): List of existing unit positions [(x1, y1, z1), ...] to avoid.
            min_spacing_from_units (float, optional): Minimum spacing from existing units in meters. If None, uses default based on unit type.

        Returns:
            tuple: The (x, y, z) coordinate of a hidden artillery position, or None.
        """
        # This function is the inverse of find_observation_post
        from ..misc.math_utils import generate_random_position_in_circle, is_position_in_circle
        
        def _is_position_allowed(pos_2d):
            """Check if position (x, z) is allowed based on constraints."""
            x, z = pos_2d
            
            if constraint_area:
                if constraint_area.get('type') == 'circle':
                    center = constraint_area['center']
                    radius = constraint_area['radius']
                    if not is_position_in_circle((x, z), center, radius):
                        return False
                elif constraint_area.get('type') == 'polygon':
                    vertices = constraint_area.get('vertices', [])
                    if vertices and not self.tc._point_in_polygon(x, z, vertices):
                        return False
            
            if excluded_areas:
                for excluded in excluded_areas:
                    if excluded.get('type') == 'circle':
                        center = excluded['center']
                        radius = excluded['radius']
                        if is_position_in_circle((x, z), center, radius):
                            return False
                    elif excluded.get('type') == 'polygon':
                        vertices = excluded.get('vertices', [])
                        if vertices and self.tc._point_in_polygon(x, z, vertices):
                            return False
            
            if position_validator:
                try:
                    if not position_validator((x, z)):
                        return False
                except Exception:
                    return False
            
            return True
        
        # Scale search radius based on map size
        scaled_search_radius = self.scale_search_radius_by_map_size(search_radius)
        
        candidates = []
        attempts = 0
        max_attempts = 90  # More attempts for hidden positions
        
        while len(candidates) < 30 and attempts < max_attempts:
            attempts += 1
            x, z = generate_random_position_in_circle(
                (target_area[0], target_area[2]), scaled_search_radius, standoff_dist, uniform_distribution=True
            )
            
            if not _is_position_allowed((x, z)):
                continue
            
            y = self.tc.get_terrain_height(x, z)
            if y is not None:
                candidate_pos = (x, y, z)
                # Check spacing from existing units if provided
                if existing_unit_positions and min_spacing_from_units:
                    if not self.check_spacing_from_existing_units(candidate_pos, existing_unit_positions, min_spacing_from_units):
                        continue
                candidates.append(candidate_pos)
            
        # Sort by elevation, lowest first, to prioritize valleys
        candidates.sort(key=lambda p: p[1])

        for pos in candidates:
            if not self.has_line_of_sight((pos[0], pos[1] + 5, pos[2]), target_area):
                return pos
        return None
    
    # --- Road & Convoy Helpers ---

    def get_nearest_road_point(self, world_x, world_z, max_distance=None):
        """
        Closest road point: {'position': (x, y, z), 'segment_index', 'distance', 'road_id', 'is_bridge'},
        or None if the map has no roads or the road is farther than max_distance.
        """
        hit = self.tc.nearest_road(world_x, world_z)
        if hit and max_distance is not None and hit['distance'] > max_distance:
            return None
        return hit

    def get_road_path(self, start_pos, end_pos, max_segments=None):
        """Shortest road route between two (x, z) points as (x, y, z) points ([] if they are not connected)."""
        return self.tc.get_road_route(start_pos, end_pos)

    #region Structure & Target Finding

    def get_buildings_in_area(self, center_x, center_z, radius, spawnable_only=False):
        """City blocks and static prefab instances whose position is within radius (XZ)."""
        found = []
        r2 = radius ** 2
        for block in self.tc.city_blocks:
            pos = block['world_position']
            if (pos[0] - center_x) ** 2 + (pos[2] - center_z) ** 2 <= r2:
                found.append({'type': 'city_block', 'position': pos, 'prefab_id': block['layout_guid'],
                              'pixel_coord': block['pixel_coord'], 'is_spawnable': True})
        spawnable = {s['prefab_index'] for s in self.tc.static_surfaces if s['is_spawnable']}
        for idx, p in enumerate(self.tc.get_all_static_prefabs()):
            pos = p['position']
            if (pos[0] - center_x) ** 2 + (pos[2] - center_z) ** 2 > r2:
                continue
            if idx in spawnable or not spawnable_only:
                found.append({'type': 'static_prefab', 'position': tuple(pos), 'prefab_id': p['prefab_id'],
                              'prefab_index': idx, 'is_spawnable': idx in spawnable})
        return found

    def find_city_with_statics(self, required_prefab_ids, search_all=True):
        """
        Finds a city area that contains specific static prefabs (e.g., an airfield).

        Args:
            required_prefab_ids: A list of prefab names that must be present.
            search_all: If False, returns the first city found. If True, returns all.

        Returns:
            A list of dictionaries, each representing a qualifying city area.
        """
        cities = {}
        # Group static prefabs by their approximate city location (grid cell)
        for prefab in self.tc.get_all_static_prefabs():
            if self.tc.get_city_density(prefab['position'][0], prefab['position'][2]) > 0.1:
                # Discretize position to group into "cities"
                city_key = (int(prefab['position'][0] / 5000), int(prefab['position'][2] / 5000))
                if city_key not in cities:
                    cities[city_key] = {'center': [prefab['position'][0], prefab['position'][2]], 'prefabs': set()}
                cities[city_key]['prefabs'].add(prefab['prefab_id'])
        
        found_cities = []
        required_set = set(required_prefab_ids)
        for key, data in cities.items():
            if required_set.issubset(data['prefabs']):
                city_info = {'center_approx': data['center'], 'found_prefabs': list(data['prefabs'])}
                found_cities.append(city_info)
                if not search_all:
                    return found_cities
        return found_cities

    #region Terrain & Topography

    def find_flat_landing_zones(self, center_x, center_z, search_radius, min_area_radius, max_slope_degrees=5.0,
                                 constraint_area=None, excluded_areas=None, position_validator=None):
        """
        Scans an area for flat ground suitable for landing helicopters or placing bases.
        
        Args:
            center_x: X coordinate of search center
            center_z: Z coordinate of search center
            search_radius: Search radius in meters
            min_area_radius: Minimum radius of flat area required
            max_slope_degrees: Maximum slope angle in degrees
            constraint_area (dict, optional): Constraint area specification (see find_observation_post).
            excluded_areas (list, optional): List of excluded areas (see find_observation_post).
            position_validator (callable, optional): Function(position) -> bool to validate positions.
        
        Returns:
            list: List of (x, y, z) tuples for valid landing zones
        """
        lz_points = []
        min_normal_y = np.cos(np.radians(max_slope_degrees))
        sample_points_x = np.linspace(center_x - search_radius, center_x + search_radius, 25)
        sample_points_z = np.linspace(center_z - search_radius, center_z + search_radius, 25)
        for x in sample_points_x:
            for z in sample_points_z:
                # Check territory constraints first
                if not self._validate_position_against_constraints((x, z), constraint_area, excluded_areas, position_validator):
                    continue
                # Check center point flatness first
                center_normal = self.tc.get_terrain_normal(x, z)
                if center_normal[1] < min_normal_y: 
                    continue
                # Check area around center point
                is_area_flat = True
                for angle in np.linspace(0, 2 * np.pi, 8, endpoint=False):
                    check_x, check_z = x + min_area_radius * np.cos(angle), z + min_area_radius * np.sin(angle)
                    if self.tc.get_terrain_normal(check_x, check_z)[1] < min_normal_y:
                        is_area_flat = False 
                        break
                if is_area_flat:
                    lz_points.append((x, self.tc.get_terrain_height(x, z), z))
        return lz_points

    def find_highest_point_in_area(self, center_x, center_z, search_radius,
                                   existing_unit_positions=None, min_spacing_from_units=None):
        """Finds the highest terrain point in a given area.
        
        Args:
            center_x: Center X coordinate
            center_z: Center Z coordinate
            search_radius: Search radius (will be scaled by map size)
            existing_unit_positions (list, optional): List of existing positions to avoid
            min_spacing_from_units (float, optional): Minimum spacing from existing units
        
        Returns:
            (x, y, z) tuple of highest point, or None
        """
        # Scale search radius by map size
        scaled_radius = self.scale_search_radius_by_map_size(search_radius)
        
        highest_y = -float('inf')
        highest_pos = None
        sample_points_x = np.linspace(center_x - scaled_radius, center_x + scaled_radius, 50)
        sample_points_z = np.linspace(center_z - scaled_radius, center_z + scaled_radius, 50)
        for x in sample_points_x:
            for z in sample_points_z:
                y = self.tc.get_terrain_height(x, z)
                if y is None:
                    continue
                candidate_pos = (x, y, z)
                # Check spacing from existing units if provided
                if existing_unit_positions and min_spacing_from_units:
                    if not self.check_spacing_from_existing_units(candidate_pos, existing_unit_positions, min_spacing_from_units):
                        continue
                if y > highest_y: 
                    highest_y, highest_pos = y, candidate_pos
        return highest_pos


    def find_lowest_point_in_area(self, center_x, center_z, search_radius,
                                  existing_unit_positions=None, min_spacing_from_units=None):
        """Finds the lowest terrain point in a given area.
        
        Args:
            center_x: Center X coordinate
            center_z: Center Z coordinate
            search_radius: Search radius (will be scaled by map size)
            existing_unit_positions (list, optional): List of existing positions to avoid
            min_spacing_from_units (float, optional): Minimum spacing from existing units
        
        Returns:
            (x, y, z) tuple of lowest point, or None
        """
        # Scale search radius by map size
        scaled_radius = self.scale_search_radius_by_map_size(search_radius)
        
        lowest_y = float('inf') 
        lowest_pos = None
        sample_points_x = np.linspace(center_x - scaled_radius, center_x + scaled_radius, 50)
        sample_points_z = np.linspace(center_z - scaled_radius, center_z + scaled_radius, 50)
        for x in sample_points_x:
            for z in sample_points_z:
                y = self.tc.get_terrain_height(x, z)
                if y is None:
                    continue
                candidate_pos = (x, y, z)
                # Check spacing from existing units if provided
                if existing_unit_positions and min_spacing_from_units:
                    if not self.check_spacing_from_existing_units(candidate_pos, existing_unit_positions, min_spacing_from_units):
                        continue
                if y < lowest_y: 
                    lowest_y, lowest_pos = y, candidate_pos
        return lowest_pos


    def find_hidden_position(self, observer_pos, target_area_center, search_radius,
                             constraint_area=None, excluded_areas=None, position_validator=None,
                             existing_unit_positions=None, min_spacing_from_units=None):
        """
        Finds a low-lying point in an area that is hidden from an observer's view.
        
        Args:
            observer_pos (tuple): The (x, y, z) position of the observer.
            target_area_center (tuple): The (x, z) or (x, y, z) center of the area to search.
            search_radius (float): The radius to search within (will be scaled by map size).
            constraint_area (dict, optional): Constraint area specification (see find_observation_post).
            excluded_areas (list, optional): List of excluded areas (see find_observation_post).
            position_validator (callable, optional): Function(position) -> bool to validate positions.
            existing_unit_positions (list, optional): List of existing positions to avoid.
            min_spacing_from_units (float, optional): Minimum spacing from existing units.
        
        Returns:
            tuple: An (x, y, z) hidden position, or None if none found.
        """
        # Scale search radius by map size
        scaled_search_radius = self.scale_search_radius_by_map_size(search_radius)
        
        potential_points = []
        # Find all low points first
        from ..misc.math_utils import generate_random_position_in_circle
        # Extract x, z from target_area_center (handle both 2D and 3D)
        center_2d = (target_area_center[0], target_area_center[2] if len(target_area_center) >= 3 else target_area_center[1])
        attempts = 0
        max_attempts = 150  # More attempts if constraints are tight
        
        while len(potential_points) < 50 and attempts < max_attempts:
            attempts += 1
            x, z = generate_random_position_in_circle(center_2d, scaled_search_radius)
            
            # Check territory constraints
            if not self._validate_position_against_constraints((x, z), constraint_area, excluded_areas, position_validator):
                continue
            
            y = self.tc.get_terrain_height(x, z)
            if y is not None:
                candidate_pos = (x, y, z)
                # Check spacing from existing units if provided
                if existing_unit_positions and min_spacing_from_units:
                    if not self.check_spacing_from_existing_units(candidate_pos, existing_unit_positions, min_spacing_from_units):
                        continue
                potential_points.append(candidate_pos)
        
        # Sort by height, lowest first
        potential_points.sort(key=lambda p: p[1])

        # Return the first one that doesn't have line of sight
        for point in potential_points:
            if not self.has_line_of_sight(observer_pos, point):
                return point
        return None # No hidden point found

    #region Pathing, Placement & Formations 

    def get_terrain_following_path(self, start_pos, end_pos, steps, altitude_agl=150.0):
        """
        Generates a series of waypoints at a constant altitude above ground level.
        
        Args:
            start_pos: 2D tuple (x, z) or 3D tuple (x, y, z) - if 3D, y is ignored
            end_pos: 2D tuple (x, z) or 3D tuple (x, y, z) - if 3D, y is ignored
            steps: Number of waypoints to generate
            altitude_agl: Altitude above ground level in meters
            
        Returns:
            List of (x, y, z) waypoints
        """
        # Extract x, z coordinates (handle both 2D and 3D input)
        start_x = start_pos[0]
        start_z = start_pos[2] if len(start_pos) >= 3 else start_pos[1]
        end_x = end_pos[0]
        end_z = end_pos[2] if len(end_pos) >= 3 else end_pos[1]
        
        waypoints = []
        x_points = np.linspace(start_x, end_x, steps)
        z_points = np.linspace(start_z, end_z, steps)
        for x, z in zip(x_points, z_points):
            terrain_height = self.tc.get_terrain_height(x, z)
            waypoints.append((x, terrain_height + altitude_agl, z))
        return waypoints

    def get_circular_formation_points(self, center_pos, radius, num_points, start_angle_deg=0):
        """
        Calculates positions for units in a circular formation around a point.
        """
        points = []
        center_x, center_z = center_pos[0], center_pos[2]
        for i in range(num_points):
            angle = np.radians(start_angle_deg + (360.0 / num_points) * i)
            x = center_x + radius * np.cos(angle)
            z = center_z + radius * np.sin(angle)
            # Use smart placement to put them correctly on terrain/roofs
            placement = self.tc.get_smart_placement(x, z, 0)
            points.append(placement['position'])
        return points

    def get_terrain_type(self, position, sample_radius=100):
        """
        Classifies terrain into categories like 'Urban', 'Mountainous', 'Plains', etc.

        Why it's useful: Allows for abstract, high-level mission rules and queries.

        How it works (Math):
        1. Checks building density first to classify 'Urban'.
        2. If not urban, it samples the terrain normal vector at multiple points in a radius.
           - The normal vector `(nx, ny, nz)` indicates the slope. `ny` close to 1.0 means flat.
        3. It calculates the average `ny` (mean flatness) and its standard deviation (variance in flatness).
           - High avg `ny`, low std dev -> 'Flat Plains'
           - Low avg `ny`, high std dev -> 'Mountainous'
           - Mid avg `ny`, mid std dev -> 'Rolling Hills'

        Args:
            position (tuple): The (x, z) coordinate (2D) or (x, y, z) coordinate (3D - y ignored).
            sample_radius (float): The radius to sample for slope analysis.

        Returns:
            str: The name of the terrain type (e.g., "Urban", "Mountainous").
        """
        # Extract x, z coordinates (handle both 2D and 3D input)
        pos_x = position[0]
        pos_z = position[2] if len(position) >= 3 else position[1]
        
        if self.tc.get_city_density(pos_x, pos_z) > 0.1:
            return "Urban"
            
        normals_y = []
        from ..misc.math_utils import generate_random_position_in_circle
        for _ in range(20): # Increased samples for better accuracy
            x, z = generate_random_position_in_circle((pos_x, pos_z), sample_radius)
            normals_y.append(self.tc.get_terrain_normal(x, z)[1])
        
        avg_ny = np.mean(normals_y)
        
        if avg_ny < 0.90:  # Very hilly/varied slope
            return "Mountainous"
        if avg_ny > 0.99:  # Consistently very flat
            return "Flat Plains"
        if avg_ny < 0.97:  # Moderately varied slope
            return "Rolling Hills"
        
        return "Plains"

    def find_choke_point(self, road_path, check_width=100):
        """
        Analyzes a road path to find segments in deep valleys, ideal for ambushes.

        Why it's useful: Automates finding the best locations for ambushes along a convoy route. 

        How it works (Math):
        1. It iterates through pairs of points (segments) in the `road_path`.
        2. For each segment's midpoint, it calculates the perpendicular vector.
           - If segment vector is `(dx, dz)`, perpendicular is `(-dz, dx)`.
        3. It samples terrain height along this perpendicular line on both sides of the road.
        4. It calculates the 'wall height' (average height of side points minus road height).
        5. It returns the road point with the highest 'wall height' score.

        Args:
            road_path (list): A list of (x, y, z) tuples representing a road.
            check_width (float): How far to the sides of the road to check for high ground.

        Returns:
            tuple: The (x, y, z) coordinate of the most constricted point on the path.
        """
        best_choke_point = None
        max_wall_height = -1

        for i, _ in enumerate(road_path[:-1]):
            p1, p2 = np.array(road_path[i]), np.array(road_path[i+1])
            mid_point = (p1 + p2) / 2.0
            
            direction_vec = p2 - p1
            # Perpendicular vector in 2D (XZ plane)
            perp_vec = np.array([-direction_vec[2], 0, direction_vec[0]])
            perp_vec_norm = perp_vec / np.linalg.norm(perp_vec) if np.linalg.norm(perp_vec) > 0 else perp_vec

            side_heights = []
            for dist in np.linspace(-check_width, check_width, 10):
                if dist == 0: 
                    continue
                check_pos = mid_point + perp_vec_norm * dist
                side_heights.append(self.tc.get_terrain_height(check_pos[0], check_pos[2]))
            
            avg_wall_height = np.mean(side_heights) - mid_point[1]
            if avg_wall_height > max_wall_height:
                max_wall_height = avg_wall_height
                best_choke_point = tuple(mid_point)
        
        return best_choke_point
    
    def get_covert_insertion_path(self, start_pos, end_pos, radar_positions, steps=50):
        """
        Generates a low-altitude flight path that tries to stay hidden from radars.

        Why it's useful: Creates realistic, challenging ingress routes for AI and players, rewarding terrain-masking flight.

        How it works (Math):
        1. Uses a greedy algorithm, not a full A*. It builds the path step-by-step.
        2. At each step, it generates several candidate next points (e.g., left, right, straight, up, down).
        3. It scores each candidate:
           - `Score = w1 * (distance_to_target) + w2 * (num_radars_with_LoS) + w3 * (altitude_AGL)`
           - `w1` is negative (we want to decrease distance), `w2` and `w3` are positive (we want to minimize visibility and altitude).
        4. It picks the candidate with the lowest score and repeats from there.

        Args:
            start_pos (tuple): The (x, y, z) start point.
            end_pos (tuple): The (x, y, z) end point.
            radar_positions (list): A list of (x, y, z) coordinates for known enemy radars.
            steps (int): The number of waypoints to generate for the path.

        Returns:
            list: A list of (x, y, z) tuples forming the covert path.
        """
        path = [start_pos]

        current_pos = np.array(start_pos, dtype=float) 
        
        for _ in range(steps):
            if np.linalg.norm(current_pos - np.array(end_pos)) < 1000: 
                break # Close enough

            # Ensure end_pos is also treated as a float for subtraction
            direction_to_end = (np.array(end_pos, dtype=float) - current_pos)
            
            norm = np.linalg.norm(direction_to_end)
            if norm > 1e-6: # Check for non-zero length before normalizing
                direction_to_end /= norm # In-place division is now safe
            else:
                break # Already at the destination

            candidates = []
            # Generate 5 candidate moves from current position
            angles = np.radians(np.array([0, -30, 30])) # Straight, left, right
            for angle in angles:
                # Rotation matrix for yaw
                c, s = np.cos(angle), np.sin(angle)
                rot_matrix = np.array([[c, 0, -s], [0, 1, 0], [s, 0, c]])
                candidate_dir = rot_matrix.dot(direction_to_end)
                # Step forward by 500m for the next waypoint
                candidate_pos = current_pos + candidate_dir * 500
                
                # Try two altitudes: low and very low
                alt_low = self.tc.get_terrain_height(candidate_pos[0], candidate_pos[2]) + 100
                alt_very_low = self.tc.get_terrain_height(candidate_pos[0], candidate_pos[2]) + 40
                
                candidates.append(np.array([candidate_pos[0], alt_low, candidate_pos[2]]))
                candidates.append(np.array([candidate_pos[0], alt_very_low, candidate_pos[2]]))
            
            best_candidate = None
            min_score = float('inf')

            for cand in candidates:
                dist_score = np.linalg.norm(cand - np.array(end_pos))
                
                visibility_score = 0
                for radar in radar_positions:
                    if self.has_line_of_sight((radar[0], radar[1]+10, radar[2]), cand):
                        visibility_score += 10000 # Heavy penalty for being seen
                
                alt_score = cand[1] - self.tc.get_terrain_height(cand[0], cand[2]) # Penalty for altitude
                
                total_score = dist_score + visibility_score + alt_score * 2
                if total_score < min_score:
                    min_score = total_score
                    best_candidate = cand
            
            if best_candidate is not None:
                current_pos = best_candidate
                path.append(tuple(current_pos))
            else:
                break # No good path found
                
        path.append(end_pos)
        return path
    
    def get_convoy_dispersal_points(self, road_position, num_points, radius,
                                     constraint_area=None, excluded_areas=None, position_validator=None):
        """
        Finds nearby off-road, hidden positions for a convoy to scatter to when ambushed.

        Why it's useful: Creates dynamic and realistic AI reactions. Instead of just stopping, units can attempt to find cover.

        How it works (Logic):
        1. It uses `find_hidden_position` repeatedly.
        2. The "observer" is a point high above the `road_position`, simulating an attacker's viewpoint.
        3. It searches in a radius around the road for points that are *not* visible from that high vantage point.
        4. It ensures the points found are not on a road themselves.
        5. If constraint_area or excluded_areas are provided, candidates are filtered accordingly.

        Args:
            road_position (tuple): The (x, y, z) point on the road where the convoy is.
            num_points (int): The number of dispersal points to find.
            radius (float): The maximum distance from the road to search for cover.
            constraint_area (dict, optional): Constraint area specification (see find_observation_post).
            excluded_areas (list, optional): List of excluded areas (see find_observation_post).
            position_validator (callable, optional): Function(position) -> bool to validate positions.

        Returns:
            list: A list of (x, y, z) tuples for suitable off-road cover positions.
        """
        dispersal_points = []
        # Observer is high above the road, representing the attacker's general view
        observer_pos = (road_position[0], road_position[1] + 200, road_position[2])
        
        attempts = 0
        max_attempts = num_points * 10  # More attempts if constraints are tight
        
        while len(dispersal_points) < num_points and attempts < max_attempts:
            attempts += 1
            
            # Use the core logic of find_hidden_position to find a suitable spot
            hidden_pos = self.find_hidden_position(
                observer_pos, (road_position[0], road_position[2]), radius,
                constraint_area=constraint_area,
                excluded_areas=excluded_areas,
                position_validator=position_validator
            )

            if hidden_pos and not self.tc.is_on_road(hidden_pos[0], hidden_pos[2]):
                # Check if it's too close to an existing point
                is_too_close = False
                for dp in dispersal_points:
                    if np.linalg.norm(np.array(hidden_pos) - np.array(dp)) < 50: # 50m separation
                        is_too_close = True
                        break
                if not is_too_close:
                    dispersal_points.append(hidden_pos)

        return dispersal_points

    def find_riverbed_path(self, start_pos, end_pos, steps=100):
        """
        Generates a path that follows the lowest terrain, simulating movement through valleys.

        Why it's useful: Creates natural-looking patrol routes for ground units trying to stay concealed.

        How it works (Math):
        1. A greedy algorithm that always moves "downhill" relative to the general direction.
        2. At each step, it samples points in a forward-facing arc.
        3. The score for each point is `Score = w1 * (altitude) + w2 * (distance_to_target_line)`.
        4. It picks the point with the lowest score, which favors low altitude while still progressing towards the goal.

        Args:
            start_pos (tuple): The (x, z) start coordinate (2D) or (x, y, z) (3D - y ignored).
            end_pos (tuple): The (x, z) end coordinate (2D) or (x, y, z) (3D - y ignored).
            steps (int): The number of waypoints to generate.

        Returns:
            list: A list of (x, y, z) waypoints following the valley floor.
        """
        # Extract x, z coordinates (handle both 2D and 3D input)
        start_x = start_pos[0]
        start_z = start_pos[2] if len(start_pos) >= 3 else start_pos[1]
        end_x = end_pos[0]
        end_z = end_pos[2] if len(end_pos) >= 3 else end_pos[1]
        
        start_y = self.tc.get_terrain_height(start_x, start_z)
        path = [(start_x, start_y, start_z)]
        current_pos = np.array([start_x, start_z], dtype=float)
        
        end_pos_2d = np.array([end_x, end_z], dtype=float)
        
        for _ in range(steps):
            if np.linalg.norm(current_pos - end_pos_2d) < 500: 
                break

            direction_to_end = end_pos_2d - current_pos
            norm = np.linalg.norm(direction_to_end)
            if norm < 1e-6: 
                break
            direction_to_end /= norm

            best_candidate = None
            min_score = float('inf')

            angles = np.radians(np.array([0, -25, 25, -45, 45]))
            for angle in angles:
                c, s = np.cos(angle), np.sin(angle)
                # Simple 2D rotation
                cand_dir = np.array([direction_to_end[0]*c - direction_to_end[1]*s, direction_to_end[0]*s + direction_to_end[1]*c])
                cand_pos = current_pos + cand_dir * 150 # 150m segments

                height = self.tc.get_terrain_height(cand_pos[0], cand_pos[1])
                dist_to_target = np.linalg.norm(cand_pos - end_pos_2d)

                # Score favors low altitude but penalizes moving away from the target
                score = height * 2 + dist_to_target
                if score < min_score:
                    min_score = score
                    best_candidate = (cand_pos[0], height, cand_pos[1])
            
            if best_candidate:
                path.append(best_candidate)
                current_pos = np.array([best_candidate[0], best_candidate[2]])
            else:
                break
        
        end_y = self.tc.get_terrain_height(end_x, end_z)
        path.append((end_x, end_y, end_z))
        return path

    def _find_all_bridges(self):
        """Internal helper to find and cache all bridge segments from the TerrainCalculator."""
        if self._bridges is None:
            # This now uses the reliable method from the corrected TerrainCalculator
            self._bridges = self.tc.get_all_bridges()
        return self._bridges

    def find_bridge_crossing_path(self, start_pos, end_pos):
        """
        Road route from start to end (x, z) forced through the bridge closest to the straight line between them.
        Bridge points keep the deck height. Returns (x, y, z) points or None.
        """
        bridges = self._find_all_bridges()
        if not bridges:
            return None
        a, b = np.asarray(start_pos, dtype=float), np.asarray(end_pos, dtype=float)

        def dist_to_line(bridge):
            m = ((bridge['start'] + bridge['end']) / 2.0)[[0, 2]]
            t = np.clip(np.dot(m - a, b - a) / max(np.dot(b - a, b - a), 1e-9), 0, 1)
            return np.linalg.norm(a + t * (b - a) - m)

        best = min(bridges, key=dist_to_line)
        mid = ((best['start'] + best['end']) / 2.0)[[0, 2]]
        path1, path2 = self.tc.get_road_route(tuple(a), tuple(mid)), self.tc.get_road_route(tuple(mid), tuple(b))
        if not path1 or not path2:
            return None
        return path1 + path2[1:]

    #region Air & Naval Operations

    def find_helicopter_battle_position(self, target_area, search_radius, min_dist=500, pop_up_alt=30):
        """
        Finds a "hide" position for a helicopter to perform a pop-up attack.

        Why it's useful: Essential for creating realistic helicopter ambushes and attack runs.

        How it works (Logic):
        1. It searches for a candidate point that is hidden from the target at ground level.
        2. It then confirms that if the helicopter were to ascend vertically (`pop_up_alt`), it would gain line of sight.
        3. This ensures the position is right behind a ridge or obstacle, perfect for terrain-masking.

        Args:
            target_area (tuple): The (x, y, z) of the target.
            search_radius (float): The radius around the target to search for positions.
            min_dist (float): Minimum standoff distance from the target.
            pop_up_alt (float): The altitude the helicopter will 'pop up' to attack.

        Returns:
            tuple: An (x, y, z) coordinate for the hide position, or None if none found.
        """
        from ..misc.math_utils import generate_random_position_in_circle
        for _ in range(50): # Increase candidates for a tricky find
            x, z = generate_random_position_in_circle(
                (target_area[0], target_area[2]), search_radius, min_dist, uniform_distribution=True
            )
            y = self.tc.get_terrain_height(x, z)
            
            hide_pos = (x, y + 2, z) # Position of a landed helicopter
            popup_pos = (x, y + pop_up_alt, z)

            is_hidden = not self.has_line_of_sight(target_area, hide_pos)
            can_see_when_popped = self.has_line_of_sight(target_area, popup_pos)
            
            if is_hidden and can_see_when_popped:
                return (x, y, z)
        
        return None

    def generate_bombing_run_path(self, target_pos, entry_heading_deg, run_in_dist=5000, egress_dist=5000, altitude=1000):
        """
        Creates a structured IP-Target-Egress path for a bombing or strafing run.

        Why it's useful: Simplifies setting up any air-to-ground attack, providing clear waypoints for AI and players.

        How it works (Math):
        1. It takes the target position and an entry heading (e.g., 90 for East).
        2. It calculates a unit vector for that heading using trigonometry: `(cos(angle), sin(angle))`.
        3. The Initial Point (IP) is calculated by moving backward from the target along the vector.
           `IP = Target - vector * run_in_dist`
        4. The Egress point is calculated by moving forward from the target.
           `Egress = Target + vector * egress_dist`

        Args:
            target_pos (tuple): The (x, y, z) of the target.
            entry_heading_deg (float): The compass heading (0-360) of the attack run.
            run_in_dist (float): Distance from the IP to the target.
            egress_dist (float): Distance from the target to the egress point.
            altitude (float): The constant altitude (MSL) for the entire run.

        Returns:
            dict: A dictionary with 'ip', 'target', and 'egress' 3D waypoints.
        """
        angle_rad = np.radians(90 - entry_heading_deg) # Convert from compass heading to math angle
        vector = np.array([np.cos(angle_rad), 0, np.sin(angle_rad)])
        
        target = np.array(target_pos)
        ip = target - vector * run_in_dist
        egress = target + vector * egress_dist

        return {
            'ip': (ip[0], altitude, ip[2]),
            'target': (target[0], altitude, target[2]),
            'egress': (egress[0], altitude, egress[2])
        }

    def define_safe_air_corridor(self, start_pos, end_pos, width, altitude, known_threats):
        """
        Analyzes a high-altitude air corridor and returns a safety score.

        Why it's useful: Helps define safe transit lanes for high-value assets like tankers and AWACS, away from SAMs.

        How it works (Math):
        1. It creates a grid of points within the specified corridor (a long rectangle).
        2. It gets the perpendicular vector to the corridor's centerline.
        3. It samples points by stepping along the centerline and then stepping out left/right along the perpendicular.
        4. It checks `has_line_of_sight` from every known threat to every point in the grid.
        5. The score is `(total_points - visible_points) / total_points`. A score of 1.0 is perfectly safe.

        Args:
            start_pos (tuple): The (x, z) start of the corridor.
            end_pos (tuple): The (x, z) end of the corridor.
            width (float): The width of the corridor in meters.
            altitude (float): The constant altitude (MSL) of the corridor.
            known_threats (list): A list of (x, y, z) positions for enemy SAMs.

        Returns:
            dict: Containing the path waypoints and a 'safety_score' from 0.0 to 1.0.
        """
        p1 = np.array([start_pos[0], start_pos[1]])
        p2 = np.array([end_pos[0], end_pos[1]])
        centerline_vec = p2 - p1
        centerline_len = np.linalg.norm(centerline_vec)
        centerline_dir = centerline_vec / centerline_len if centerline_len > 0 else centerline_vec

        perp_dir = np.array([-centerline_dir[1], centerline_dir[0]])

        total_points = 0
        visible_points = 0
        
        # Sample every 1km along the corridor length (ensure at least 2 points for short corridors)
        num_samples = max(2, int(centerline_len / 1000))
        for dist_along in np.linspace(0, centerline_len, num_samples):
            # Sample across the width
            for dist_across in np.linspace(-width/2, width/2, 5):
                sample_pos_2d = p1 + centerline_dir * dist_along + perp_dir * dist_across
                sample_pos_3d = (sample_pos_2d[0], altitude, sample_pos_2d[1])
                total_points += 1
                for threat in known_threats:
                    if self.has_line_of_sight(threat, sample_pos_3d):
                        visible_points += 1
                        break # Only count each point once if visible by any threat
        
        safety_score = (total_points - visible_points) / total_points if total_points > 0 else 0
        return {
            'path': [(start_pos[0], altitude, start_pos[1]), (end_pos[0], altitude, end_pos[1])],
            'safety_score': safety_score
        }

    def find_naval_bombardment_position(self, coastal_target, standoff_distance, sea_level=1.0):
        """
        Finds a position at sea with a clear line of sight to a coastal target.

        Why it's useful: Automates placing naval fleets for shore bombardment missions.

        How it works (Logic):
        1. It samples points in a ring around the target at the specified `standoff_distance`.
        2. For each point, it checks the terrain height. If it's at or below `sea_level`, it's a valid sea position.
        3. It then performs a `has_line_of_sight` check from the sea position to the target.
        4. The first valid position found is returned.

        Args:
            coastal_target (tuple): The (x, y, z) of the ground target.
            standoff_distance (float): The desired distance from the coast for the ship.
            sea_level (float): The maximum altitude to be considered 'sea'.

        Returns:
            tuple: An (x, y, z) position for the naval unit, or None.
        """
        for angle_deg in np.linspace(0, 360, 72): # Check every 5 degrees
            angle_rad = np.radians(angle_deg)
            x = coastal_target[0] + standoff_distance * np.cos(angle_rad)
            z = coastal_target[2] + standoff_distance * np.sin(angle_rad)
            
            terrain_height = self.tc.get_terrain_height(x, z)
            if terrain_height <= sea_level:
                # This is a sea position. Check LoS.
                # Ship's bridge/weapons are higher than sea level.
                ship_pos = (x, sea_level + 15, z)
                if self.has_line_of_sight(ship_pos, coastal_target):
                    return (x, sea_level, z)
        return None
    
    #region Dynamic Campaign & Intelligence

    def calculate_front_line_trace(self, friendly_units, enemy_units):
        """
        Calculates a list of points representing the front line between two forces.

        Why it's useful: Essential for dynamic campaigns to visualize the state of the battle and generate relevant objectives.

        How it works (Math):
        1. It uses `cKDTree`, a highly efficient data structure for nearest neighbor searches.
        2. It finds the single nearest enemy for each friendly unit and vice-versa.
        3. It calculates the midpoint for each of these "nearest pairs".
        4. This collection of midpoints forms a rough but effective trace of the front line.

        Args:
            friendly_units (list): A list of (x, y, z) positions for friendly units.
            enemy_units (list): A list of (x, y, z) positions for enemy units.

        Returns:
            list: A list of (x, y, z) tuples representing the points along the front line.
        """
        if not friendly_units or not enemy_units:
            return []

        friend_pts = np.array(friendly_units)[:, [0, 2]] # Use X, Z for 2D calculations
        enemy_pts = np.array(enemy_units)[:, [0, 2]]
        
        friend_tree = cKDTree(friend_pts)
        enemy_tree = cKDTree(enemy_pts)

        # Find nearest enemy for each friendly
        dist_fe, idx_fe = enemy_tree.query(friend_pts)
        
        # Find nearest friendly for each enemy
        dist_ef, idx_ef = friend_tree.query(enemy_pts)

        midpoints = []
        for i, friend_pos in enumerate(friend_pts):
            enemy_pos = enemy_pts[idx_fe[i]]
            midpoint = (friend_pos + enemy_pos) / 2.0
            height = self.tc.get_terrain_height(midpoint[0], midpoint[1])
            midpoints.append((midpoint[0], height, midpoint[1]))

        # To avoid duplicates, we can process enemy-to-friendly too and combine,
        # but this is a good first approximation.
        return midpoints


    def trace_supply_route(self, start_base_name, end_base_name):
        """
        Finds a primary road path between two named bases (large static prefabs).

        Why it's useful: Defines the logistical backbone (MSR) of an army, creating targets for ambush and patrol missions.

        How it works (Logic):
        1. It searches through all static prefabs to find the positions of the named bases.
        2. Once found, it simply calls `get_road_path` to find the route between them.

        Args:
            start_base_name (str): The prefab ID of the starting base.
            end_base_name (str): The prefab ID of the ending base.

        Returns:
            list: A list of (x, y, z) waypoints forming the supply route, or None.
        """
        start_pos, end_pos = None, None
        for prefab in self.tc.get_all_static_prefabs():
            if prefab['prefab_id'] == start_base_name:
                start_pos = (prefab['position'][0], prefab['position'][2])
            if prefab['prefab_id'] == end_base_name:
                end_pos = (prefab['position'][0], prefab['position'][2])
            if start_pos and end_pos:
                break
        
        if start_pos and end_pos:
            return self.get_road_path(start_pos, end_pos)
        return None

    def analyze_route_vulnerability(self, road_path, check_width=100):
        """
        Analyzes a route and returns a list of its most vulnerable points.

        Why it's useful: Automatically finds the best places for ambushes (for attackers) or defensive posts (for defenders).

        How it works (Logic):
        1. Identifies all bridge crossings on the path. Bridges are always highly vulnerable.
        2. Calls `find_choke_point` on the entire path to find the best ambush spot in a valley.
        3. (Future enhancement): Could also find long, straight sections vulnerable to air attack.

        Args:
            road_path (list): A list of (x, y, z) waypoints.
            check_width (float): Width to check for surrounding high ground.

        Returns:
            dict: A dictionary containing lists of 'bridges' and 'choke_points'.
        """
        if not road_path: 
            return {}

        vulnerabilities = {'bridges': [], 'choke_points': []}
        
        bridges = self._find_all_bridges()
        for bridge in bridges:
            bridge_midpoint = (bridge['start'] + bridge['end']) / 2.0
            for point in road_path:
                if np.linalg.norm(np.array(point) - bridge_midpoint) < 150:
                    vulnerabilities['bridges'].append(bridge)
                    break 
        
        choke_point = self.find_choke_point(road_path, check_width)
        if choke_point:
            vulnerabilities['choke_points'].append(choke_point)
            
        return vulnerabilities

    def find_radar_dead_zone(self, radar_positions, search_area_center, search_radius, altitude):
        """
        Finds areas on the map that are hidden from all known radar sites at a given altitude.

        Why it's useful: Creates "stealth corridors" for designing challenging ingress/egress routes for strike missions.

        How it works (Logic):
        1. It creates a grid of sample points within the search area.
        2. For each point in the grid, it creates a 3D position at the specified `altitude`.
        3. It then checks `has_line_of_sight` from every radar to this point.
        4. If the point is not visible to *any* of the radars, it is added to the list of dead zones.

        Args:
            radar_positions (list): A list of (x, y, z) radar locations.
            search_area_center (tuple): The (x, z) center of the area to search.
            search_radius (float): The radius of the search area.
            altitude (float): The flight altitude (MSL) to check for dead zones.

        Returns:
            list: A list of (x, y, z) points that are inside a radar dead zone.
        """
        dead_zones = []
        center_x, center_z = search_area_center
        
        # Create a 20x20 grid to sample the area
        for x in np.linspace(center_x - search_radius, center_x + search_radius, 20):
            for z in np.linspace(center_z - search_radius, center_z + search_radius, 20):
                point_3d = (x, altitude, z)
                is_visible = False
                for radar in radar_positions:
                    if self.has_line_of_sight(radar, point_3d):
                        is_visible = True
                        break
                if not is_visible:
                    dead_zones.append(point_3d)
                    
        return dead_zones
    
    #region VI. Formations & Unit Placement

    def get_line_formation_points(self, center_pos, num_units, spacing, angle_deg):
        """
        Creates points for a straight-line formation, correctly placed on the terrain.

        Why it's useful: Essential for setting up a defensive line of tanks or an infantry firing line.

        How it works (Math):
        1. It calculates a perpendicular vector to the facing angle.
           - `perp_angle = angle_deg + 90`
        2. It starts from the center and places units along this perpendicular line.
           - `offset = (i - (num_units - 1) / 2.0) * spacing`
           - `pos = center + perp_vector * offset`
        3. Each point is then snapped to the ground using `get_smart_placement`.

        Args:
            center_pos (tuple): The (x, y, z) center of the formation.
            num_units (int): The total number of units in the line.
            spacing (float): The distance between each unit.
            angle_deg (float): The compass heading the formation should face.

        Returns:
            list: A list of (x, y, z) positions for each unit.
        """
        points = []
        center = np.array(center_pos)
        
        # Convert heading to math angle: math_angle = 90° - heading (so 0° heading → 90° math)
        # For perpendicular: add 90° to math angle = (90° - heading) + 90° = 180° - heading
        # Or subtract 90°: (90° - heading) - 90° = -heading
        perp_angle_rad = np.radians(180 - angle_deg)  # Perpendicular to facing direction
        perp_vec = np.array([np.cos(perp_angle_rad), 0, np.sin(perp_angle_rad)])

        for i in range(num_units):
            # Calculate offset from the center for this unit
            offset = (i - (num_units - 1) / 2.0) * spacing
            pos = center + perp_vec * offset
            
            # Snap to terrain/roof
            placement = self.tc.get_smart_placement(pos[0], pos[2], angle_deg)
            points.append(placement['position'])
            
        return points

    def get_wedge_formation_points(self, lead_pos, num_units, spacing, angle_deg):
        """
        Creates points for a V-shaped attacking formation.

        Why it's useful: The standard attacking formation for armored units. Makes placing groups of tanks easy and realistic.

        How it works (Math):
        1. It starts with the lead vehicle's position.
        2. For subsequent units, it places them alternating left and right, and progressively further back.
           - `left_pos = lead - forward_vec * row * spacing + right_vec * row * spacing`
           - `right_pos = lead - forward_vec * row * spacing - right_vec * row * spacing`
        3. Each point is snapped to the ground.

        Args:
            lead_pos (tuple): The (x, y, z) of the lead unit.
            num_units (int): The total number of units.
            spacing (float): The distance between units.
            angle_deg (float): The compass heading the formation faces.

        Returns:
            list: A list of (x, y, z) positions.
        """
        if num_units == 0: 
            return []
        points = [lead_pos]
        if num_units == 1: 
            return points

        lead = np.array(lead_pos)
        angle_rad = np.radians(90 - angle_deg)
        forward_vec = np.array([np.cos(angle_rad), 0, np.sin(angle_rad)])
        right_vec = np.array([np.sin(angle_rad), 0, -np.cos(angle_rad)])

        for i in range(1, num_units):
            row = (i + 1) // 2
            side = -1 if i % 2 != 0 else 1 # -1 for left, 1 for right
            
            pos = lead - forward_vec * row * spacing * 1.5 + right_vec * row * spacing * side
            
            placement = self.tc.get_smart_placement(pos[0], pos[2], angle_deg)
            points.append(placement['position'])
            
        return points
        
    def get_building_garrison_points(self, building_info, max_units=10):
        """Centers of the spawnable roofs of a building from get_buildings_in_area, highest first."""
        tops = []
        if building_info['type'] == 'city_block':
            layout = self.tc._city_layout_at_pixel(*building_info['pixel_coord'])
            pivot = np.asarray(building_info['position'])
            rot = R.from_euler('Y', layout['block_yaw_degrees'], degrees=True).as_matrix()
            for srf in layout['surfaces']:
                b = srf.get('bounds_rel_layout', [])
                if srf.get('is_spawnable') and len(b) == 6:
                    tops.append(tuple(float(v) for v in rot @ np.array([(b[0] + b[1]) / 2, b[3], (b[4] + b[5]) / 2]) + pivot))
        else:
            for srf in self.tc.static_surfaces:
                w = srf['world_bounds']
                if srf['is_spawnable'] and srf['prefab_index'] == building_info['prefab_index']:
                    tops.append(((w[0] + w[3]) / 2, w[4], (w[2] + w[5]) / 2))
        tops.sort(key=lambda p: -p[1])
        return tops[:max_units]

    def find_open_area(self, center_pos, search_radius, min_clear_radius,
                       constraint_area=None, excluded_areas=None, position_validator=None,
                       existing_unit_positions=None, min_spacing_from_units=None):
        """
        Finds a large, clear area with no buildings or dense forests.

        Why it's useful: For finding a place to set up a FARP, a large-scale battle, or a safe extraction zone.

        How it works (Logic):
        1. It samples random points in the `search_radius` (scaled by map size).
        2. For each point, it checks a smaller `min_clear_radius` around it.
        3. Inside this smaller circle, it verifies there are no cities (`get_city_density`) and no static prefabs (`get_buildings_in_area`).
        4. The first point that passes the check is returned.
        5. If constraint_area or excluded_areas are provided, candidates are filtered accordingly.
        6. If existing_unit_positions and min_spacing_from_units are provided, ensures spacing from existing units.

        Args:
            center_pos (tuple): The (x, z) center of the area to search.
            search_radius (float): The large radius to search within (will be scaled by map size).
            min_clear_radius (float): The required radius of the clear, open space.
            constraint_area (dict, optional): Constraint area specification (see find_observation_post).
            excluded_areas (list, optional): List of excluded areas (see find_observation_post).
            position_validator (callable, optional): Function(position) -> bool to validate positions.
            existing_unit_positions (list, optional): List of existing unit positions [(x1, y1, z1), ...] to avoid.
            min_spacing_from_units (float, optional): Minimum spacing from existing units in meters.

        Returns:
            tuple: An (x, y, z) position in the center of the open area, or None.
        """
        from ..misc.math_utils import generate_random_position_in_circle
        # Scale search radius based on map size
        scaled_search_radius = self.scale_search_radius_by_map_size(search_radius)
        
        attempts = 0
        max_attempts = 150  # More attempts if constraints are tight
        
        while attempts < max_attempts:
            attempts += 1
            check_x, check_z = generate_random_position_in_circle(center_pos, scaled_search_radius)
            
            # Check territory constraints first
            if not self._validate_position_against_constraints((check_x, check_z), constraint_area, excluded_areas, position_validator):
                continue
            
            # Check spacing from existing units if provided
            height = self.tc.get_terrain_height(check_x, check_z)
            if height is None:
                continue
            
            candidate_pos = (check_x, height, check_z)
            if existing_unit_positions and min_spacing_from_units:
                if not self.check_spacing_from_existing_units(candidate_pos, existing_unit_positions, min_spacing_from_units):
                    continue
            
            # Check 1: City density
            if self.tc.get_city_density(check_x, check_z) > 0.05:
                continue
                
            # Check 2: Static prefabs nearby
            if len(self.get_buildings_in_area(check_x, check_z, min_clear_radius)) > 0:
                continue

            # If all checks pass, we found a spot
            return candidate_pos
            
        return None

    def get_random_points_in_area(self, center_pos, radius, num_points,
                                   constraint_area=None, excluded_areas=None, position_validator=None):
        """
        Scatters random points within an area, correctly snapped to the ground.

        Why it's useful: For creating patrol routes, minefields, or adding "clutter" units to make an area feel alive.

        How it works (Math):
        1. It uses polar coordinates to generate random points with a uniform distribution inside a circle.
           - `r = sqrt(rand()) * radius`
           - `theta = rand() * 2 * pi`
        2. Each generated (x, z) point is then snapped to the ground using `get_smart_placement`.
        3. If constraint_area or excluded_areas are provided, candidates are filtered accordingly.

        Args:
            center_pos (tuple): The (x, z) center of the circle.
            radius (float): The radius of the circle.
            num_points (int): The number of points to generate.
            constraint_area (dict, optional): Constraint area specification (see find_observation_post).
            excluded_areas (list, optional): List of excluded areas (see find_observation_post).
            position_validator (callable, optional): Function(position) -> bool to validate positions.

        Returns:
            list: A list of (x, y, z) positions.
        """
        points = []
        attempts = 0
        max_attempts = num_points * 3  # More attempts if constraints are tight
        
        while len(points) < num_points and attempts < max_attempts:
            attempts += 1
            r = radius * np.sqrt(random.random())
            theta = random.random() * 2 * np.pi
            x = center_pos[0] + r * np.cos(theta)
            # Handle both 2D (x, z) and 3D (x, y, z) center_pos
            if len(center_pos) >= 2:
                z = center_pos[1] + r * np.sin(theta)
            else:
                z = center_pos[0] + r * np.sin(theta)  # Fallback (shouldn't happen)
            
            # Check territory constraints
            if not self._validate_position_against_constraints((x, z), constraint_area, excluded_areas, position_validator):
                continue
            
            placement = self.tc.get_smart_placement(x, z, 0)
            points.append(placement['position'])
        return points
    
    #region Scenario & Storytelling Primitives

    def suggest_objective_locations(self, num_locations=5, min_city_size=10):
        """
        Scans the map to find "points of interest" that would make good objectives.

        Why it's useful: A great tool for mission editors, providing instant inspiration and preventing creative blocks.
        
        How it works (Logic):
        1. Identifies unique, important static prefabs by keyword (e.g., "Airbase", "PowerPlant").
        2. Groups city blocks into clusters and finds the centers of large cities.
        3. Finds the absolute highest point on the map.
        4. Compiles a list of these points of interest and returns a sample.

        Args:
            num_locations (int): The number of suggestions to return.
            min_city_size (int): The minimum number of blocks to be considered a "city".

        Returns:
            list: A list of dictionaries, e.g., [{'name': 'Central City', 'position': (x,y,z)}].
        """
        objectives = []
        
        # 1. Find key static prefabs
        key_prefabs = ["airbase", "farp", "power", "command", "comm", "hangar", "dam"]
        for prefab in self.tc.get_all_static_prefabs():
            if any(key in prefab['prefab_id'].lower() for key in key_prefabs):
                objectives.append({'name': prefab['prefab_id'], 'position': tuple(prefab['position'])})

        # 2. Find major cities
        # This is a simplified clustering by grid cell
        city_clusters = {}
        for block in self.tc.city_blocks:
            key = (int(block['world_position'][0] / 4000), int(block['world_position'][2] / 4000))
            if key not in city_clusters:
                city_clusters[key] = []
            city_clusters[key].append(block['world_position'])
        
        for key, positions in city_clusters.items():
            if len(positions) > min_city_size:
                center = np.mean(positions, axis=0)
                objectives.append({'name': f"City Cluster {key}", 'position': tuple(center)})
        
        # 3. Add highest point
        map_size = self.tc.total_map_size_meters
        highest_point = self.find_highest_point_in_area(map_size/2, map_size/2, map_size/2)
        if highest_point:
            objectives.append({'name': "Highest Peak", 'position': highest_point})

        # Return a random sample if we have too many
        if len(objectives) > num_locations:
            return random.sample(objectives, num_locations)
        return objectives

    def find_coastal_landing_area(self, search_area_center, search_radius, min_area_radius=50, sea_level=1.0):
        """
        Finds a flat beach area suitable for an amphibious assault.

        Why it's useful: Instantly finds a beachhead for landing-type missions.

        How it works (Logic):
        1. It samples many points in the search area.
        2. For each point, it checks two conditions:
           a) The altitude is at or very near `sea_level`.
           b) The area around it is flat (using `find_flat_landing_zones` logic).
        3. The first point that satisfies both is returned.

        Args:
            search_area_center (tuple): (x, z) center to search in.
            search_radius (float): Radius to search within.
            min_area_radius (float): The required radius of the flat landing area.
            sea_level (float): The altitude considered to be the sea.

        Returns:
            tuple: An (x, y, z) position for the landing, or None.
        """
        # Extract x, z coordinates (handle both 2D and 3D input)
        center_x = search_area_center[0]
        center_z = search_area_center[2] if len(search_area_center) >= 3 else search_area_center[1]
        candidates = self.find_flat_landing_zones(center_x, center_z, search_radius, min_area_radius, max_slope_degrees=3.0)
        
        for pos in candidates:
            # Check if height is close to sea level
            if abs(pos[1] - sea_level) < 2.0: # Within 2m of sea level
                return pos
        return None

    def get_area_control_points(self, area_center, radius, num_points,
                                 constraint_area=None, excluded_areas=None, position_validator=None):
        """
        Generates tactically interesting capture points for a "King of the Hill" scenario.

        Why it's useful: Automates the setup for area control missions.

        How it works (Logic):
        1. It scatters random points within the area.
        2. For each point, it "snaps" it to the nearest interesting feature:
           - The roof of the nearest building.
           - The center of the nearest road intersection.
           - The top of the nearest small hill.
        3. This ensures points are on meaningful locations, not just random fields.
        4. If constraint_area or excluded_areas are provided, candidates are filtered accordingly.

        Args:
            area_center (tuple): (x, z) center of the mission area.
            radius (float): Radius of the mission area.
            num_points (int): The number of control points to generate.
            constraint_area (dict, optional): Constraint area specification (see find_observation_post).
            excluded_areas (list, optional): List of excluded areas (see find_observation_post).
            position_validator (callable, optional): Function(position) -> bool to validate positions.

        Returns:
            list: A list of (x, y, z) positions for the control points.
        """
        control_points = []
        # Generate more candidates than needed
        candidates = self.get_random_points_in_area(
            area_center, radius, num_points * 3,
            constraint_area=constraint_area,
            excluded_areas=excluded_areas,
            position_validator=position_validator
        )

        for cand in candidates:
            # For simplicity, we'll just use the snapped random point for now.
            # A full implementation would check for nearby buildings/intersections.
            control_points.append(cand)
        
        return random.sample(control_points, min(num_points, len(control_points)))
    
    #region VIII. High-Level Mission Composition & Flavor

    def validate_mission_feasibility(self, unit_list, max_slope_deg=30):
        """
        Performs a sanity check on a list of spawned units to find impossible placements.

        Why it's useful: Catches common procedural generation errors automatically, saving hours of testing.

        How it works (Logic):
        1. Iterates through the list of units.
        2. For ground units ('tank', 'truck'), it checks the terrain slope. If it's too steep, it flags an error.
        3. (Conceptual): Checks if any unit is inside a non-spawnable building's bounding box.

        Args:
            unit_list (list): A list of dicts, e.g., [{'unit_type': 'tank', 'position': (x,y,z)}].
            max_slope_deg (float): The maximum allowable slope for ground units.

        Returns:
            list: A list of strings describing any validation errors found.
        """
        errors = []
        max_slope_normal_y = np.cos(np.radians(max_slope_deg))
        ground_types = ['tank', 'truck', 'apc', 'sam_mobile']

        for i, unit in enumerate(unit_list):
            pos = unit['position']
            u_type = unit.get('unit_type', 'unknown')
            
            if u_type in ground_types:
                normal = self.tc.get_terrain_normal(pos[0], pos[2])
                if normal[1] < max_slope_normal_y:
                    errors.append(f"Unit {i} ('{u_type}') at {pos} is on terrain with slope > {max_slope_deg} degrees.")
        
        return errors

    def find_scenic_overlook(self, point_of_interest, min_dist=1000, max_dist=4000,
                             constraint_area=None, excluded_areas=None, position_validator=None):
        """
        Finds a spot with a dramatic, cinematic view of a target.

        Why it's useful: Perfect for setting an opening cinematic, a briefing camera, or a recon objective.

        How it works (Logic):
        1. It's similar to `find_observation_post` but scores candidates differently.
        2. The score favors points that are significantly higher than the target, creating a downward viewing angle.
           `Score = (pos.y - target.y) - distance * 0.1`

        Args:
            point_of_interest (tuple): The (x, y, z) position of the landmark to view.
            min_dist (float): Minimum distance from the landmark.
            max_dist (float): Maximum distance from the landmark.

        Returns:
            tuple: The (x, y, z) coordinate of the best overlook, or None.
        """
        best_overlook = None
        best_score = -float('inf')

        candidates = []
        from ..misc.math_utils import generate_random_position_in_circle
        attempts = 0
        max_attempts = 150  # More attempts if constraints are tight
        
        while len(candidates) < 50 and attempts < max_attempts:
            attempts += 1
            x, z = generate_random_position_in_circle(
                (point_of_interest[0], point_of_interest[2]), max_dist, min_dist, uniform_distribution=True
            )
            
            # Check territory constraints
            if not self._validate_position_against_constraints((x, z), constraint_area, excluded_areas, position_validator):
                continue
            
            y = self.tc.get_terrain_height(x, z)
            if y is not None:
                candidates.append((x, y, z))

        for pos in candidates:
            if self.has_line_of_sight(pos, point_of_interest):
                # Score based on height advantage minus a penalty for being too far
                height_adv = pos[1] - point_of_interest[1]
                dist = np.linalg.norm(np.array(pos) - np.array(point_of_interest))
                score = height_adv - dist * 0.1
                if score > best_score:
                    best_score = score
                    best_overlook = pos
                    
        return best_overlook

    def get_area_defensibility_score(self, area_center, radius):
        """
        Rates an area on a scale of 0 to 10 on how easy it is to defend.

        Why it's useful: Allows procedural generation to make strategic decisions about where to place high-value assets.

        How it works (Math):
        1. **High Ground Bonus:** Finds the highest and lowest points. A large elevation difference increases the score.
        2. **Cover Bonus:** Counts the number of buildings in the area. More buildings increase the score.
        3. **Choke Point Bonus:** Counts the number of roads entering the area. Fewer roads are better, increasing the score.

        Args:
            area_center (tuple): The (x, z) center of the area.
            radius (float): The radius to analyze.

        Returns:
            float: A score from 0.0 to 10.0.
        """
        highest = self.find_highest_point_in_area(area_center[0], area_center[1], radius)
        lowest = self.find_lowest_point_in_area(area_center[0], area_center[1], radius)
        elevation_diff = highest[1] - lowest[1] if highest and lowest else 0
        high_ground_score = min(elevation_diff / 100.0, 4.0)

        buildings = self.get_buildings_in_area(area_center[0], area_center[1], radius)
        cover_score = min(len(buildings) / 5.0, 3.0)
        
        road_crossings = 0
        center = np.array(area_center)
        radius_sq = radius**2
        for start, end in self.tc.road_segments:
            s_2d, e_2d = np.array([start[0], start[2]]), np.array([end[0], end[2]])
            s_inside = np.sum((s_2d - center)**2) < radius_sq
            e_inside = np.sum((e_2d - center)**2) < radius_sq
            if s_inside != e_inside:
                road_crossings += 1
        
        choke_score = max(0, 3.0 - road_crossings * 0.6)

        return high_ground_score + cover_score + choke_score

    def calculate_threat_intervisibility(self, unit_positions):
        """
        Calculates which units in a list can see each other, creating a visibility graph.

        Why it's useful: Helps a designer validate their defensive placements, ensuring units can mutually support each other.

        How it works (Logic):
        1. It iterates through every unique pair of units in the provided list.
        2. For each pair, it performs a `has_line_of_sight` check.
        3. It returns a dictionary where each key is a unit's index, and the value is a list of indices of other units it can see.

        Args:
            unit_positions (list): A list of (x, y, z) positions for all units on a team.

        Returns:
            dict: A dictionary representing the visibility graph.
        """
        visibility_graph = {i: [] for i in range(len(unit_positions))}
        for i, _ in enumerate(unit_positions):
            for j in range(i + 1, len(unit_positions)):
                pos1 = unit_positions[i]
                pos2 = unit_positions[j]
                if self.has_line_of_sight(pos1, pos2):
                    visibility_graph[i].append(j)
                    visibility_graph[j].append(i)
        return visibility_graph
    


    # --- Military Tactical Functions ---
    # Consolidated military functionality for intelligent mission generation

    def find_defensive_position(self, center_pos, search_radius, system_type='generic', threat_direction=None,
                                constraint_area=None, excluded_areas=None, position_validator=None):
        """
        Find tactically sound defensive position using military doctrine.
        
        Args:
            center_pos: Center of search area (x, y, z)
            search_radius: Search radius in meters
            system_type: Type of system ('radar', 'sam', 'aaa', 'c2', 'logistics', 'generic')
            threat_direction: Expected threat axis in degrees (0-360, None for omnidirectional)
            constraint_area (dict, optional): Constraint area specification (see find_observation_post).
            excluded_areas (list, optional): List of excluded areas (see find_observation_post).
            position_validator (callable, optional): Function(position) -> bool to validate positions.
            
        Returns:
            Dict with position, score, and tactical analysis
        """
        x_center, y_center, z_center = center_pos
        best_pos = None
        best_score = -1
        
        # Generate candidate positions
        candidates = []
        from ..misc.math_utils import generate_random_position_in_circle
        attempts = 0
        max_attempts = 150  # More attempts if constraints are tight
        
        while len(candidates) < 50 and attempts < max_attempts:
            attempts += 1
            x, z = generate_random_position_in_circle(
                (x_center, z_center), search_radius, search_radius * 0.3
            )
            
            # Check territory constraints
            if not self._validate_position_against_constraints((x, z), constraint_area, excluded_areas, position_validator):
                continue
            
            y = self.tc.get_terrain_height(x, z)
            
            if y is not None and y >= 0:
                candidates.append((x, y, z))
        
        # Score each candidate position
        for pos in candidates:
            score = self._score_defensive_position(pos, center_pos, system_type, threat_direction)
            if score > best_score:
                best_score = score
                best_pos = pos
        
        if best_pos:
            return {
                'position': best_pos,
                'score': best_score,
                'terrain_analysis': self._analyze_tactical_terrain(best_pos, system_type),
                'threat_exposure': self._calculate_threat_exposure(best_pos, threat_direction)
            }
        return None
    
    def _score_defensive_position(self, position, center_pos, system_type='generic', threat_direction=None):
        """Score defensive position based on tactical factors."""
        x, y, z = position
        score = 0.0
        
        # 1. Elevation advantage (higher is generally better)
        elevation_bonus = min(y / 1000.0, 2.0)  # Cap at 2 points
        score += elevation_bonus
        
        # 2. Terrain type suitability
        terrain_type = self.get_terrain_type(position)
        terrain_scores = {
            'rocky': 1.5,    # Excellent for fixed positions
            'hilly': 1.2,    # Good elevation options
            'forested': 0.8, # Good concealment but limits radar
            'urban': 0.6,    # Vulnerable but good for C2
            'water': 0.1,    # Generally unsuitable
            'flat': 0.5      # Exposed but easy construction
        }
        score += terrain_scores.get(terrain_type, 0.5)
        
        # 3. System-specific factors
        if system_type == 'radar':
            # Radars need clear lines of sight and elevation
            score += elevation_bonus * 1.5
            if terrain_type in ['rocky', 'hilly']:
                score += 1.0
        elif system_type == 'sam':
            # SAMs need good coverage but some concealment
            if terrain_type in ['rocky', 'hilly', 'forested']:
                score += 0.8
        elif system_type == 'aaa':
            # AAA needs mobility and clear firing lanes
            if terrain_type in ['flat', 'rocky']:
                score += 0.6
        elif system_type == 'c2':
            # C2 needs protection and communications
            if terrain_type in ['rocky', 'hilly', 'urban']:
                score += 0.8
        elif system_type == 'logistics':
            # Logistics needs road access and protection
            road_point = self.get_nearest_road_point(x, z)
            if road_point and road_point['distance'] < 1000:
                score += 1.5 - (road_point['distance'] / 1000.0)
        
        # 4. Threat direction considerations
        if threat_direction is not None:
            # Prefer positions that provide cover from threat direction
            # This is a simplified model - in reality would need full terrain analysis
            threat_cover_bonus = self._calculate_threat_cover(position, threat_direction)
            score += threat_cover_bonus
        
        # 5. Slope considerations (not too steep for construction)
        try:
            from ..misc.math_utils import calculate_slope_from_normal
            normal = self.tc.get_terrain_normal(x, z)
            slope_deg = calculate_slope_from_normal(normal, degrees=True)
            if slope_deg < 5.0:
                score += 1.0
            elif slope_deg < 15.0:
                score += 0.5
            elif slope_deg > 30.0:
                score -= 1.0
        except Exception:
            pass
        
        return max(score, 0.0)
    
    def _analyze_tactical_terrain(self, position, system_type):
        """Analyze terrain for tactical advantages/disadvantages."""
        x, y, z = position
        analysis = {
            'elevation': y,
            'terrain_type': self.get_terrain_type(position),
            'concealment': 'unknown',
            'accessibility': 'unknown',
            'fields_of_fire': 'unknown'
        }
        
        try:
            from ..misc.math_utils import calculate_slope_from_normal
            normal = self.tc.get_terrain_normal(x, z)
            slope_deg = calculate_slope_from_normal(normal, degrees=True)
            analysis['slope'] = slope_deg
            
            # Concealment assessment
            terrain_type = analysis['terrain_type']
            if terrain_type == 'forested':
                analysis['concealment'] = 'excellent'
            elif terrain_type in ['rocky', 'hilly']:
                analysis['concealment'] = 'good'
            elif terrain_type == 'urban':
                analysis['concealment'] = 'fair'
            else:
                analysis['concealment'] = 'poor'
            
            # Accessibility assessment
            road_point = self.get_nearest_road_point(x, z)
            if road_point:
                if road_point['distance'] < 500:
                    analysis['accessibility'] = 'excellent'
                elif road_point['distance'] < 1500:
                    analysis['accessibility'] = 'good'
                else:
                    analysis['accessibility'] = 'poor'
            
            # Fields of fire (simplified)
            if terrain_type in ['flat', 'rocky'] and slope < 10:
                analysis['fields_of_fire'] = 'excellent'
            elif terrain_type == 'hilly':
                analysis['fields_of_fire'] = 'good'
            else:
                analysis['fields_of_fire'] = 'limited'
                
        except Exception as e:
            self._log(f"Warning: Terrain analysis incomplete: {e}")
        
        return analysis
    
    def _calculate_threat_exposure(self, position, threat_direction=None):
        """Calculate how exposed position is to threats."""
        # Simplified threat exposure calculation
        # In a full implementation, this would consider:
        # - Line of sight from likely threat positions
        # - Terrain masking
        # - Distance from likely ingress routes
        
        x, y, z = position
        exposure = 0.5  # Base exposure
        
        try:
            # Higher elevation = more exposed
            if y > 1000:
                exposure += 0.2
            elif y < 200:
                exposure -= 0.1
            
            # Terrain type affects exposure
            terrain_type = self.get_terrain_type(position)
            if terrain_type == 'flat':
                exposure += 0.3
            elif terrain_type in ['forested', 'urban']:
                exposure -= 0.2
            elif terrain_type in ['rocky', 'hilly']:
                exposure -= 0.1
            
        except Exception as e:
            self._log(f"Warning: Threat exposure calculation incomplete: {e}")
        
        return max(0.0, min(1.0, exposure))
    
    def _calculate_threat_cover(self, position, threat_direction):
        """Calculate cover provided against specific threat direction."""
        # Simplified threat cover calculation
        # Would need full terrain analysis for accurate assessment
        return random.uniform(0.0, 0.5)  # Placeholder
    
    def assess_airbase_suitability(self, position, runway_length_required=2000):
        """
        Assess terrain suitability for airbase construction.
        
        Args:
            position: Candidate position (x, y, z)
            runway_length_required: Minimum runway length in meters
            
        Returns:
            Dict with suitability analysis
        """
        x, y, z = position
        assessment = {
            'overall_score': 0.0,
            'terrain_suitable': False,
            'space_available': False,
            'accessibility': 'unknown',
            'strategic_value': 0.0,
            'construction_difficulty': 1.0,
            'issues': []
        }
        
        try:
            # Check if area is large enough and flat enough
            flat_area = self.find_flat_landing_zones(x, z, 5000, runway_length_required/2, max_slope_degrees=3.0)
            if flat_area:
                assessment['terrain_suitable'] = True
                assessment['space_available'] = True
                assessment['overall_score'] += 3.0
            else:
                assessment['issues'].append('Insufficient flat terrain for runway')
                return assessment
            
            # Check terrain type
            terrain_type = self.get_terrain_type(position)
            if terrain_type in ['flat', 'rocky']:
                assessment['overall_score'] += 2.0
                assessment['construction_difficulty'] = 0.8
            elif terrain_type == 'hilly':
                assessment['overall_score'] += 1.0
                assessment['construction_difficulty'] = 1.2
            elif terrain_type == 'forested':
                assessment['overall_score'] += 0.5
                assessment['construction_difficulty'] = 1.5
                assessment['issues'].append('Forest clearing required')
            elif terrain_type == 'water':
                assessment['issues'].append('Location in water')
                return assessment
            
            # Check road accessibility
            road_point = self.get_nearest_road_point(x, z)
            if road_point:
                if road_point['distance'] < 2000:
                    assessment['accessibility'] = 'excellent'
                    assessment['overall_score'] += 1.5
                elif road_point['distance'] < 5000:
                    assessment['accessibility'] = 'good'
                    assessment['overall_score'] += 1.0
                else:
                    assessment['accessibility'] = 'poor'
                    assessment['issues'].append('Remote location - road construction needed')
            
            # Strategic value assessment
            # Higher elevation provides better strategic oversight
            if y > 500:
                assessment['strategic_value'] += 0.5
            
            # Check for nearby strategic features
            buildings = self.get_buildings_in_area(x, z, 10000)
            if buildings:
                assessment['strategic_value'] += min(len(buildings) / 20.0, 1.0)
            
            # Distance from map center (generally more strategic)
            map_center_x, map_center_z = self.tc.map_size[0] / 2, self.tc.map_size[1] / 2
            distance_from_center = np.sqrt((x - map_center_x)**2 + (z - map_center_z)**2)
            center_bonus = max(0, 1.0 - distance_from_center / 50000)  # 50km max range
            assessment['strategic_value'] += center_bonus
            
            assessment['strategic_value'] = min(assessment['strategic_value'], 3.0)
            assessment['overall_score'] += assessment['strategic_value']
            
        except Exception as e:
            self._log(f"Warning: Airbase assessment incomplete: {e}")
            assessment['issues'].append(f'Assessment error: {str(e)}')
        
        return assessment
    
    def find_tactical_positions(self, center_pos, search_radius, position_type, count=1, min_separation=1000,
                                constraint_area=None, excluded_areas=None, position_validator=None):
        """
        Find multiple tactical positions of specified type.
        
        Args:
            center_pos: Center of search area
            search_radius: Search radius in meters
            position_type: Type ('overwatch', 'support', 'ambush', 'rally_point')
            count: Number of positions to find
            min_separation: Minimum distance between positions
            constraint_area (dict, optional): Constraint area specification (see find_observation_post).
            excluded_areas (list, optional): List of excluded areas (see find_observation_post).
            position_validator (callable, optional): Function(position) -> bool to validate positions.
            
        Returns:
            List of position dictionaries
        """
        positions = []
        attempts = 0
        max_attempts = count * 30  # More attempts if constraints are tight
        
        while len(positions) < count and attempts < max_attempts:
            attempts += 1
            
            # Generate candidate position
            x_center, y_center, z_center = center_pos
            from ..misc.math_utils import generate_random_position_in_circle
            x, z = generate_random_position_in_circle(
                (x_center, z_center), search_radius, search_radius * 0.3
            )
            
            # Check territory constraints
            if not self._validate_position_against_constraints((x, z), constraint_area, excluded_areas, position_validator):
                continue
            
            y = self.tc.get_terrain_height(x, z)
            
            if y is None:
                continue
            
            candidate_pos = (x, y, z)
            
            # Check minimum separation from existing positions
            too_close = False
            for existing_pos in positions:
                dist = np.sqrt((x - existing_pos['position'][0])**2 + 
                             (z - existing_pos['position'][2])**2)
                if dist < min_separation:
                    too_close = True
                    break
            
            if too_close:
                continue
            
            # Score position based on type
            score = self._score_tactical_position(candidate_pos, position_type, center_pos)
            
            if score > 0.5:  # Minimum acceptable score
                positions.append({
                    'position': candidate_pos,
                    'type': position_type,
                    'score': score,
                    'terrain_analysis': self._analyze_tactical_terrain(candidate_pos, position_type)
                })
        
        # Sort by score and return best positions
        positions.sort(key=lambda p: p['score'], reverse=True)
        return positions[:count]
    
    def _score_tactical_position(self, position, position_type, reference_pos):
        """Score position based on tactical purpose."""
        x, y, z = position
        ref_x, ref_y, ref_z = reference_pos
        score = 0.0
        
        try:
            terrain_type = self.get_terrain_type(position)
            from ..misc.math_utils import calculate_slope_from_normal
            normal = self.tc.get_terrain_normal(x, z)
            slope = calculate_slope_from_normal(normal, degrees=True)
            elevation_diff = y - ref_y
            
            if position_type == 'overwatch':
                # Overwatch positions need elevation and good fields of fire
                if elevation_diff > 50:
                    score += 2.0
                if terrain_type in ['rocky', 'hilly']:
                    score += 1.5
                if slope < 15:
                    score += 1.0
                    
            elif position_type == 'support':
                # Support positions need protection and accessibility
                if terrain_type in ['forested', 'rocky']:
                    score += 1.5
                road_point = self.get_nearest_road_point(x, z)
                if road_point and road_point['distance'] < 1000:
                    score += 1.0
                    
            elif position_type == 'ambush':
                # Ambush positions need concealment and chokepoint proximity
                if terrain_type in ['forested', 'rocky']:
                    score += 2.0
                if slope > 5 and slope < 25:  # Some elevation but not too steep
                    score += 1.0
                    
            elif position_type == 'rally_point':
                # Rally points need accessibility and some protection
                if terrain_type in ['forested', 'hilly']:
                    score += 1.0
                if slope < 10:
                    score += 1.5
                road_point = self.get_nearest_road_point(x, z)
                if road_point and road_point['distance'] < 2000:
                    score += 1.0
            
        except Exception as e:
            self._log(f"Warning: Tactical position scoring incomplete: {e}")
        
        return max(score, 0.0)
    
    def check_line_of_sight_tactical(self, pos1, pos2, max_range=None, terrain_masking=True):
        """
        Check line of sight between two positions for tactical purposes.
        
        Args:
            pos1: First position (x, y, z)
            pos2: Second position (x, y, z)
            max_range: Maximum effective range in meters (None for unlimited)
            terrain_masking: Whether to consider terrain blocking
            
        Returns:
            Dict with LOS analysis
        """
        x1, y1, z1 = pos1
        x2, y2, z2 = pos2
        
        # Calculate distance
        distance = np.sqrt((x2 - x1)**2 + (y2 - y1)**2 + (z2 - z1)**2)
        
        result = {
            'has_los': False,
            'distance': distance,
            'blocked_by_terrain': False,
            'blocked_by_range': False,
            'elevation_angle': 0.0
        }
        
        # Check range limit
        if max_range and distance > max_range:
            result['blocked_by_range'] = True
            return result
        
        # Calculate elevation angle
        horizontal_distance = np.sqrt((x2 - x1)**2 + (z2 - z1)**2)
        if horizontal_distance > 0:
            result['elevation_angle'] = np.degrees(np.arctan((y2 - y1) / horizontal_distance))
        
        # Check terrain masking if enabled
        if terrain_masking:
            # Simple terrain blocking check - sample points along the path
            steps = max(int(horizontal_distance / 100), 5)  # Sample every 100m or 5 points minimum
            for i in range(1, steps):
                t = i / steps
                sample_x = x1 + t * (x2 - x1)
                sample_z = z1 + t * (z2 - z1)
                sample_y_path = y1 + t * (y2 - y1)  # Linear interpolation of path
                sample_y_terrain = self.tc.get_terrain_height(sample_x, sample_z)
                
                if sample_y_terrain is not None and sample_y_terrain > sample_y_path + 10:  # 10m clearance
                    result['blocked_by_terrain'] = True
                    return result
        
        result['has_los'] = True
        return result
