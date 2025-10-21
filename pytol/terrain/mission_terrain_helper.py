"""
Provides the MissionTerrainHelper class, an advanced query engine for mission
generation using data from a TerrainCalculator instance.
"""
import numpy as np
import random
import os
import traceback
from scipy.spatial.transform import Rotation as R
from scipy.spatial import cKDTree
from .terrain_calculator import TerrainCalculator

class MissionTerrainHelper:
    """
    Uses a TerrainCalculator instance to provide high-level, mission-centric
    data queries about the map, such as finding landing zones, road points,
    and tactical locations.
    """

    def __init__(self, terrain_calculator: TerrainCalculator):
        """
        Initializes the helper with a pre-loaded TerrainCalculator instance.

        Args:
            terrain_calculator: An initialized instance of the TerrainCalculator class.
        """
        if not isinstance(terrain_calculator, TerrainCalculator):
            raise TypeError("The provided argument must be an instance of TerrainCalculator.")
        self.tc = terrain_calculator
        self._bridges = None
        self._pois_cache = None
        print("MissionTerrainHelper initialized.")

    # --- Core Terrain and Objects queries ---

    def has_line_of_sight(self, pos1, pos2, steps=20, terrain_offset=0):
        """
        Checks for clear line of sight between two 3D points, accounting for terrain.

        Args:
            pos1 (tuple): The 3D coordinate (x, y, z) of the starting point.
            pos2 (tuple): The 3D coordinate (x, y, z) of the ending point.
            steps (int): The number of points to check along the line. Higher is more accurate.
            terrain_offset (float): An optional vertical buffer. For example, use 2 for a person's height.

        Returns:
            bool: True if there is clear line of sight, False if it is obstructed.
        """
        p1, p2 = np.array(pos1), np.array(pos2)
        for i in range(1, steps + 1):
            t = i / float(steps)
            # Linear interpolation: p = (1-t)*p1 + t*p2
            interp_point = p1 + t * (p2 - p1)
            terrain_h = self.tc.get_terrain_height(interp_point[0], interp_point[2])
            if interp_point[1] < (terrain_h + terrain_offset):
                return False # Obstructed by terrain
        return True
    
    def find_observation_post(self, target_area, min_dist, max_dist, num_candidates=20):
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

        Args:
            target_area (tuple): The (x, y, z) coordinate of the target to be observed.
            min_dist (float): The minimum distance from the target.
            max_dist (float): The maximum distance from the target.
            num_candidates (int): The number of random points to test.

        Returns:
            tuple: The (x, y, z) coordinate of a suitable observation post, or None.
        """
        candidates = []
        for _ in range(num_candidates):
            angle = random.uniform(0, 2 * np.pi)
            # Uniform distribution within the annulus
            radius = np.sqrt(random.uniform(min_dist**2, max_dist**2))
            x = target_area[0] + radius * np.cos(angle)
            z = target_area[2] + radius * np.sin(angle)
            y = self.tc.get_terrain_height(x, z)
            candidates.append((x, y, z))
        
        # Sort by elevation, highest first
        candidates.sort(key=lambda p: p[1], reverse=True)

        for post in candidates:
            # Check LoS from slightly above the ground at the post to the target
            if self.has_line_of_sight((post[0], post[1] + 2, post[2]), target_area):
                return post
        return None

    def find_artillery_position(self, target_area, search_radius, standoff_dist=1000):
        """
        Finds a position hidden from a target, suitable for indirect fire.

        Why it's useful: Realistically places artillery that can't be seen by the target, requiring other units to spot for it.

        How it works (Math):
        1. Similar to the observation post, it samples points around the target.
        2. It prioritizes points that are *behind* terrain features relative to the target.
        3. It returns the first valid point that *fails* the Line of Sight check.

        Args:
            target_area (tuple): The (x, y, z) of the target.
            search_radius (float): The radius around the target to search within.
            standoff_dist (float): Minimum distance to keep from the target.

        Returns:
            tuple: The (x, y, z) coordinate of a hidden artillery position, or None.
        """
        # This function is the inverse of find_observation_post
        candidates = []
        for _ in range(30): # More candidates to find a hidden spot
            angle = random.uniform(0, 2 * np.pi)
            radius = np.sqrt(random.uniform(standoff_dist**2, search_radius**2))
            x = target_area[0] + radius * np.cos(angle)
            z = target_area[2] + radius * np.sin(angle)
            y = self.tc.get_terrain_height(x, z)
            candidates.append((x, y, z))
            
        # Sort by elevation, lowest first, to prioritize valleys
        candidates.sort(key=lambda p: p[1])

        for pos in candidates:
            if not self.has_line_of_sight((pos[0], pos[1] + 5, pos[2]), target_area):
                return pos
        return None
    
    # --- Road & Convoy Helpers ---

    def get_nearest_road_point(self, world_x, world_z):
        """
        Finds the closest point on any road segment to the given world coordinates.

        Args:
            world_x: The world X coordinate.
            world_z: The world Z coordinate.

        Returns:
            A dictionary with {'position': (x, y, z), 'segment_index': int, 'distance': float}
            or None if no roads exist on the map.
        """
        if not self.tc.road_segments:
            return None

        point_2d = np.array([world_x, world_z])
        min_dist_sq = float('inf')
        best_point_3d = None
        best_segment_index = -1

        for i, seg in enumerate(self.tc.road_segments):
            start_3d, end_3d = seg['start'], seg['end']
            p1 = np.array([start_3d[0], start_3d[2]])
            p2 = np.array([end_3d[0], end_3d[2]])
            
            line_vec = p2 - p1
            point_vec = point_2d - p1
            line_len_sq = np.dot(line_vec, line_vec)
            
            if line_len_sq == 0.0: 
                continue

            t = np.dot(point_vec, line_vec) / line_len_sq
            t = np.clip(t, 0, 1)
            
            closest_point_2d = p1 + t * line_vec
            dist_sq = np.sum((point_2d - closest_point_2d)**2)

            if dist_sq < min_dist_sq:
                min_dist_sq = dist_sq
                height = self.tc.get_terrain_height(closest_point_2d[0], closest_point_2d[1])
                best_point_3d = (closest_point_2d[0], height, closest_point_2d[1])
                best_segment_index = i

        if best_point_3d:
            return {
                'position': best_point_3d,
                'segment_index': best_segment_index,
                'distance': np.sqrt(min_dist_sq)
            }
        return None

    def get_road_path(self, start_pos, end_pos, max_segments=100):
        """
        Generates a sequence of road points from a start to an end position.
        Note: This is a simplified greedy search, not a full A* pathfinder.

        Args:
            start_pos: An (x, z) tuple for the start.
            end_pos: An (x, z) tuple for the end.
            max_segments: A safe limit to prevent infinite loops.

        Returns:
            A list of (x, y, z) waypoints following the road network.
        """
        start_road_info = self.get_nearest_road_point(start_pos[0], start_pos[1])
        end_road_info = self.get_nearest_road_point(end_pos[0], end_pos[1])

        if not start_road_info or not end_road_info:
            return []

        path_points = [start_road_info['position']]
        current_seg_index = start_road_info['segment_index']
        visited_indices = {current_seg_index}

        for _ in range(max_segments):
            if current_seg_index == end_road_info['segment_index']:
                break

            current_seg_data = self.tc.road_segments[current_seg_index]
            current_seg_start, current_seg_end = current_seg_data['start'], current_seg_data['end']
            
            best_next_seg = -1
            min_dist_to_target = float('inf')

            end_point_2d = np.array([current_seg_end[0], current_seg_end[2]])

            for i, next_seg in enumerate(self.tc.road_segments):
                if i in visited_indices:
                    continue
                
                next_start, next_end = next_seg['start'], next_seg['end']
                
                if np.linalg.norm(end_point_2d - np.array([next_start[0], next_start[2]])) < 20.0:
                    dist_to_end = np.linalg.norm(np.array([next_end[0], next_end[2]]) - np.array([end_pos[0], end_pos[1]]))
                    if dist_to_end < min_dist_to_target:
                        min_dist_to_target = dist_to_end
                        best_next_seg = i
            
            if best_next_seg != -1:
                next_start_pos = self.tc.road_segments[best_next_seg]['start']
                height = self.tc.get_terrain_height(next_start_pos[0], next_start_pos[2])
                path_points.append((next_start_pos[0], height, next_start_pos[2]))
                current_seg_index = best_next_seg
                visited_indices.add(current_seg_index)
            else:
                break

        path_points.append(end_road_info['position'])
        return path_points

    #region Structure & Target Finding

    def get_buildings_in_area(self, center_x, center_z, radius, spawnable_only=False):
        """
        Finds all city blocks and static prefabs within a given radius.

        Args:
            center_x: The center X coordinate of the search area.
            center_z: The center Z coordinate of the search area.
            radius: The radius of the search area in meters.
            spawnable_only: If True, only returns spawnable surfaces.

        Returns:
            A list of dictionaries, each representing a found building.
        """
        found_buildings = []
        radius_sq = radius**2
        
        # 1. Check City Blocks
        for block in self.tc.city_blocks:
            pos = block['world_position']
            dist_sq = (pos[0] - center_x)**2 + (pos[2] - center_z)**2
            if dist_sq <= radius_sq:
                found_buildings.append({
                    'type': 'city_block', 'position': pos,
                    'prefab_id': block['layout_guid'], 'is_spawnable': True
                })
        
        # 2. Check Static Prefabs
        processed_prefabs = set()
        for surface in self.tc.static_surfaces:
            if spawnable_only and not surface.get('is_spawnable', False):
                continue
            bounds = surface['world_bounds']
            s_center_x = (bounds[0] + bounds[3]) / 2.0
            s_center_z = (bounds[2] + bounds[5]) / 2.0
            dist_sq = (s_center_x - center_x)**2 + (s_center_z - center_z)**2
            if dist_sq <= radius_sq:
                prefab_name = surface['prefab_name']
                if prefab_name not in processed_prefabs:
                    for p in self.tc.get_all_static_prefabs():
                        if p['prefab_id'] == prefab_name:
                             found_buildings.append({
                                'type': 'static_prefab', 'position': tuple(p['position']),
                                'prefab_id': prefab_name, 'is_spawnable': surface.get('is_spawnable', False)
                            })
                             processed_prefabs.add(prefab_name)
                             break
        return found_buildings

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

    def find_flat_landing_zones(self, center_x, center_z, search_radius, min_area_radius, max_slope_degrees=5.0):
        """
        Scans an area for flat ground suitable for landing helicopters or placing bases.
        """
        lz_points = []
        min_normal_y = np.cos(np.radians(max_slope_degrees))
        sample_points_x = np.linspace(center_x - search_radius, center_x + search_radius, 25)
        sample_points_z = np.linspace(center_z - search_radius, center_z + search_radius, 25)
        for x in sample_points_x:
            for z in sample_points_z:
                if self.tc.get_terrain_normal(x, z)[1] < min_normal_y: 
                    continue
                is_area_flat = True
                for angle in np.linspace(0, 2 * np.pi, 8, endpoint=False):
                    check_x, check_z = x + min_area_radius * np.cos(angle), z + min_area_radius * np.sin(angle)
                    if self.tc.get_terrain_normal(check_x, check_z)[1] < min_normal_y:
                        is_area_flat = False 
                        break
                if is_area_flat:
                    lz_points.append((x, self.tc.get_terrain_height(x, z), z))
        return lz_points

    def find_highest_point_in_area(self, center_x, center_z, search_radius):
        """Finds the highest terrain point in a given area."""
        
        highest_y = -float('inf')
        highest_pos = None
        sample_points_x = np.linspace(center_x - search_radius, center_x + search_radius, 50)
        sample_points_z = np.linspace(center_z - search_radius, center_z + search_radius, 50)
        for x in sample_points_x:
            for z in sample_points_z:
                y = self.tc.get_terrain_height(x, z)
                if y > highest_y: 
                    highest_y, highest_pos = y, (x, y, z)
        return highest_pos


    def find_lowest_point_in_area(self, center_x, center_z, search_radius):
        """Finds the lowest terrain point in a given area."""
        
        lowest_y = float('inf') 
        lowest_pos = None
        sample_points_x = np.linspace(center_x - search_radius, center_x + search_radius, 50)
        sample_points_z = np.linspace(center_z - search_radius, center_z + search_radius, 50)
        for x in sample_points_x:
            for z in sample_points_z:
                y = self.tc.get_terrain_height(x, z)
                if y < lowest_y: 
                    lowest_y, lowest_pos = y, (x, y, z)
        return lowest_pos


    def find_hidden_position(self, observer_pos, target_area_center, search_radius):
        """
        Finds a low-lying point in an area that is hidden from an observer's view.
        """
        potential_points = []
        # Find all low points first
        for _ in range(50): # Sample 50 random points
            angle = random.uniform(0, 2 * np.pi)
            rad = random.uniform(0, search_radius)
            x, z = target_area_center[0] + rad * np.cos(angle), target_area_center[1] + rad * np.sin(angle)
            y = self.tc.get_terrain_height(x, z)
            potential_points.append((x, y, z))
        
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
        """
        # ... (implementation unchanged)
        waypoints = []
        x_points = np.linspace(start_pos[0], end_pos[0], steps)
        z_points = np.linspace(start_pos[1], end_pos[1], steps)
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
            position (tuple): The (x, z) coordinate to classify.
            sample_radius (float): The radius to sample for slope analysis.

        Returns:
            str: The name of the terrain type (e.g., "Urban", "Mountainous").
        """
        if self.tc.get_city_density(position[0], position[1]) > 0.1:
            return "Urban"
            
        normals_y = []
        for _ in range(20): # Increased samples for better accuracy
            angle = random.uniform(0, 2 * np.pi)
            radius = random.uniform(0, sample_radius)
            x = position[0] + radius * np.cos(angle)
            z = position[1] + radius * np.sin(angle)
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

        for i in range(len(road_path) - 1):
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
    
    def get_convoy_dispersal_points(self, road_position, num_points, radius):
        """
        Finds nearby off-road, hidden positions for a convoy to scatter to when ambushed.

        Why it's useful: Creates dynamic and realistic AI reactions. Instead of just stopping, units can attempt to find cover.

        How it works (Logic):
        1. It uses `find_hidden_position` repeatedly.
        2. The "observer" is a point high above the `road_position`, simulating an attacker's viewpoint.
        3. It searches in a radius around the road for points that are *not* visible from that high vantage point.
        4. It ensures the points found are not on a road themselves.

        Args:
            road_position (tuple): The (x, y, z) point on the road where the convoy is.
            num_points (int): The number of dispersal points to find.
            radius (float): The maximum distance from the road to search for cover.

        Returns:
            list: A list of (x, y, z) tuples for suitable off-road cover positions.
        """
        dispersal_points = []
        # Observer is high above the road, representing the attacker's general view
        observer_pos = (road_position[0], road_position[1] + 200, road_position[2])
        
        for _ in range(num_points * 5): # Try more times than needed to get good results
            if len(dispersal_points) >= num_points:
                break
            
            # Use the core logic of find_hidden_position to find a suitable spot
            hidden_pos = self.find_hidden_position(observer_pos, (road_position[0], road_position[2]), radius)

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
            start_pos (tuple): The (x, z) start coordinate.
            end_pos (tuple): The (x, z) end coordinate.
            steps (int): The number of waypoints to generate.

        Returns:
            list: A list of (x, y, z) waypoints following the valley floor.
        """
        path = [(start_pos[0], self.tc.get_terrain_height(start_pos[0], start_pos[1]), start_pos[1])]
        current_pos = np.array(start_pos, dtype=float)
        
        for _ in range(steps):
            if np.linalg.norm(current_pos - np.array(end_pos)) < 500: 
                break

            direction_to_end = (np.array(end_pos, dtype=float) - current_pos)
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
                dist_to_target = np.linalg.norm(cand_pos - np.array(end_pos))

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
        
        path.append((end_pos[0], self.tc.get_terrain_height(end_pos[0], end_pos[1]), end_pos[1]))
        return path

    def _find_all_bridges(self):
        """Internal helper to find and cache all bridge segments from the TerrainCalculator."""
        if self._bridges is None:
            # This now uses the reliable method from the corrected TerrainCalculator
            self._bridges = self.tc.get_all_bridges()
        return self._bridges

    def find_bridge_crossing_path(self, start_pos, end_pos):
        """
        Generates a road path between two points that explicitly uses a bridge.

        Why it's useful: Ensures ground units can cross canyons or rivers, making pathfinding much more robust.

        How it works (Logic):
        1. First, it finds all static prefabs identified as bridges.
        2. It selects the bridge whose center is closest to the straight line between start and end.
        3. It generates three sub-paths using `get_road_path`:
           - `start_pos` -> `bridge_start`
           - `bridge_end` -> `end_pos`
        4. It stitches these paths together with the bridge's own segment.

        Args:
            start_pos (tuple): The (x, z) start coordinate.
            end_pos (tuple): The (x, z) end coordinate.

        Returns:
            list: A list of (x, y, z) waypoints forming the complete path, or None if no suitable bridge is found.
        """
        bridges = self._find_all_bridges()
        if not bridges:
            return None

        mid_point = (np.array(start_pos) + np.array(end_pos)) / 2.0
        # Find the best bridge by its segment's midpoint
        best_bridge = min(bridges, key=lambda b: np.linalg.norm(((b['start'] + b['end']) / 2)[:2] - mid_point))
        
        bridge_start_2d = np.array([best_bridge['start'][0], best_bridge['start'][2]])
        bridge_end_2d = np.array([best_bridge['end'][0], best_bridge['end'][2]])

        start_dist_to_b_start = np.linalg.norm(np.array(start_pos) - bridge_start_2d)
        start_dist_to_b_end = np.linalg.norm(np.array(start_pos) - bridge_end_2d)

        # Determine which end of the bridge is the entry and which is the exit
        bridge_entry_2d, bridge_exit_2d = (bridge_start_2d, bridge_end_2d) if start_dist_to_b_start < start_dist_to_b_end else (bridge_end_2d, bridge_start_2d)

        path1 = self.get_road_path(start_pos, tuple(bridge_entry_2d))
        path2 = self.get_road_path(tuple(bridge_exit_2d), end_pos)

        if not path1 or not path2:
            return None

        full_path = path1
        # Reconstruct 3D positions with correct height for the bridge segment
        bridge_start_pos = (bridge_entry_2d[0], self.tc.get_terrain_height(bridge_entry_2d[0], bridge_entry_2d[1]), bridge_entry_2d[1])
        bridge_end_pos = (bridge_exit_2d[0], self.tc.get_terrain_height(bridge_exit_2d[0], bridge_exit_2d[1]), bridge_exit_2d[1])
        
        # Avoid duplicating the last point of path1 if it's the same as the bridge start
        if not full_path or np.linalg.norm(np.array(full_path[-1]) - np.array(bridge_start_pos)) > 1.0:
            full_path.append(bridge_start_pos)
        full_path.append(bridge_end_pos)
        
        full_path.extend(path2)
        
        return full_path
    
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
        for _ in range(50): # Increase candidates for a tricky find
            angle = random.uniform(0, 2 * np.pi)
            radius = np.sqrt(random.uniform(min_dist**2, search_radius**2))
            x = target_area[0] + radius * np.cos(angle)
            z = target_area[2] + radius * np.sin(angle)
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
        
        # Sample every 1km along the corridor length
        for dist_along in np.linspace(0, centerline_len, int(centerline_len / 1000)):
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
        
        perp_angle_rad = np.radians(90 - (angle_deg + 90)) # Perpendicular to facing direction
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
        """
        Finds all available spawnable roof surfaces on a building to place infantry.

        Why it's useful: Allows you to quickly and automatically garrison a building with units.

        How it works (Logic):
        1. Takes `building_info` (from `get_buildings_in_area`).
        2. If it's a static prefab, it iterates through all its surfaces in the database, returning the center of spawnable ones.
        3. If it's a city block, it does the same for the city layout database.

        Args:
            building_info (dict): A dictionary representing a single building.
            max_units (int): The maximum number of points to return.

        Returns:
            list: A list of (x, y, z) positions on the building's rooftops.
        """
        garrison_points = []
        # This requires more detailed info from TerrainCalculator that is not exposed.
        # This is a conceptual implementation. A real one would need tc.get_surfaces_for_prefab().
        print("NOTE: get_building_garrison_points is a conceptual placeholder.")
        # Dummy implementation: returns a point slightly above the building center.
        pos = building_info['position']
        garrison_points.append((pos[0], pos[1] + 20, pos[2]))
        return garrison_points[:max_units]
        
    def find_open_area(self, center_pos, search_radius, min_clear_radius):
        """
        Finds a large, clear area with no buildings or dense forests.

        Why it's useful: For finding a place to set up a FARP, a large-scale battle, or a safe extraction zone.

        How it works (Logic):
        1. It samples random points in the `search_radius`.
        2. For each point, it checks a smaller `min_clear_radius` around it.
        3. Inside this smaller circle, it verifies there are no cities (`get_city_density`) and no static prefabs (`get_buildings_in_area`).
        4. The first point that passes the check is returned.

        Args:
            center_pos (tuple): The (x, z) center of the area to search.
            search_radius (float): The large radius to search within.
            min_clear_radius (float): The required radius of the clear, open space.

        Returns:
            tuple: An (x, y, z) position in the center of the open area, or None.
        """
        for _ in range(50): # 50 attempts to find a suitable spot
            angle = random.uniform(0, 2 * np.pi)
            radius = random.uniform(0, search_radius)
            check_x = center_pos[0] + radius * np.cos(angle)
            check_z = center_pos[1] + radius * np.sin(angle)
            
            # Check 1: City density
            if self.tc.get_city_density(check_x, check_z) > 0.05:
                continue
                
            # Check 2: Static prefabs nearby
            if len(self.get_buildings_in_area(check_x, check_z, min_clear_radius)) > 0:
                continue

            # If all checks pass, we found a spot
            height = self.tc.get_terrain_height(check_x, check_z)
            return (check_x, height, check_z)
            
        return None

    def get_random_points_in_area(self, center_pos, radius, num_points):
        """
        Scatters random points within an area, correctly snapped to the ground.

        Why it's useful: For creating patrol routes, minefields, or adding "clutter" units to make an area feel alive.

        How it works (Math):
        1. It uses polar coordinates to generate random points with a uniform distribution inside a circle.
           - `r = sqrt(rand()) * radius`
           - `theta = rand() * 2 * pi`
        2. Each generated (x, z) point is then snapped to the ground using `get_smart_placement`.

        Args:
            center_pos (tuple): The (x, z) center of the circle.
            radius (float): The radius of the circle.
            num_points (int): The number of points to generate.

        Returns:
            list: A list of (x, y, z) positions.
        """
        points = []
        for _ in range(num_points):
            r = radius * np.sqrt(random.random())
            theta = random.random() * 2 * np.pi
            x = center_pos[0] + r * np.cos(theta)
            z = center_pos[1] + r * np.sin(theta)
            
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

    def generate_downed_pilot_scenario(self, search_area_center, search_radius):
        """
        Generates a set of linked locations for a Combat Search and Rescue (CSAR) mission.

        Why it's useful: Instantly sets up the entire geographic layout for a CSAR mission with one call.

        How it works (Logic):
        1. Finds a difficult-to-access crash site (low flatness, not near roads).
        2. Searches nearby for a suitable flat "Rescue LZ".
        3. Finds a spawn point on the nearest road for an "Enemy Patrol".

        Args:
            search_area_center (tuple): (x, z) center of the area to generate the scenario in.
            search_radius (float): Radius to search within.

        Returns:
            dict: A dictionary with 'crash_site', 'rescue_lz', and 'enemy_patrol_spawn', or None.
        """
        # 1. Find a crash site
        crash_site = None
        for _ in range(50):
            pos = self.get_random_points_in_area(search_area_center, search_radius, 1)[0]
            # Prefer rough, remote terrain
            if self.get_terrain_type((pos[0], pos[2])) in ["Mountainous", "Rolling Hills"]:
                road_info = self.get_nearest_road_point(pos[0], pos[2])
                if road_info and road_info['distance'] > 500: # At least 500m from a road
                    crash_site = pos
                    break
        if not crash_site: 
            return None

        # 2. Find a nearby LZ
        lcs = self.find_flat_landing_zones(crash_site[0], crash_site[2], 2000, 20)
        lz = min(lcs, key=lambda p: np.linalg.norm(np.array(p) - np.array(crash_site)), default=None)
        if not lz: 
            return None

        # 3. Find enemy patrol spawn
        patrol_spawn_info = self.get_nearest_road_point(crash_site[0], crash_site[2])
        if not patrol_spawn_info: 
            return None
        
        return {'crash_site': crash_site, 'rescue_lz': lz, 'enemy_patrol_spawn': patrol_spawn_info['position']}

    def generate_base_defense_positions(self, base_center, num_positions, min_dist=500, max_dist=2000):
        """
        Intelligently places defensive units on surrounding high ground and choke points.

        Why it's useful: Automates the setup of a tactically sound defensive perimeter.

        How it works (Logic):
        1. It calls `find_observation_post` in a 360-degree arc around the base to find overwatch positions.
        2. It finds all major roads leading to the base and uses `find_choke_point` on them to place roadblocks.
        3. It returns a mix of these overwatch and checkpoint positions.

        Args:
            base_center (tuple): The (x, y, z) position of the base to defend.
            num_positions (int): The number of defensive positions to generate.
            min_dist (float): Minimum distance from the base for a position.
            max_dist (float): Maximum distance from the base.

        Returns:
            list: A list of (x, y, z) tuples for defensive units.
        """
        positions = []
        # Find overwatch positions
        for _ in range(num_positions):
            op = self.find_observation_post(base_center, min_dist, max_dist)
            if op:
                positions.append(op)
        return positions # Simplified for now, road chokepoints can be added

    def generate_convoy_ambush_scenario(self, convoy_path):
        """
        Finds the best ambush spot on a path and places enemy forces accordingly.

        Why it's useful: Creates a complete, intelligent ambush scenario with a single function call.

        How it works (Logic):
        1. Uses `analyze_route_vulnerability` to find the best choke point on the path.
        2. Calls `find_hidden_position` from the ridges overlooking the choke point to place ambush units.
        3. Defines an ingress/egress route for the ambush force.

        Args:
            convoy_path (list): The list of (x, y, z) waypoints for the convoy.

        Returns:
            dict: With keys 'ambush_point', 'attacker_positions', or None.
        """
        vuln = self.analyze_route_vulnerability(convoy_path)
        if not vuln or not vuln['choke_points']:
            return None
        
        ambush_point = vuln['choke_points'][0]
        
        # Find positions on the high ground nearby
        attacker_positions = []
        for _ in range(5): # Find 5 attacker positions
            # Search for hidden spots on the hills around the ambush point
            pos = self.find_hidden_position(ambush_point, (ambush_point[0], ambush_point[2]), 400)
            if pos:
                # Make sure it's actually higher than the road
                if pos[1] > ambush_point[1] + 10:
                    attacker_positions.append(pos)
        
        return {'ambush_point': ambush_point, 'attacker_positions': attacker_positions}

    def generate_reconnaissance_flight_path(self, num_points=5, altitude_agl=500):
        """
        Creates a logical flight path that tours the map's most interesting locations.

        Why it's useful: Procedurally generates an interesting reconnaissance or patrol mission.

        How it works (Logic):
        1. Calls `suggest_objective_locations` to get a list of points of interest.
        2. Orders them by proximity to create a logical tour (nearest neighbor path).
        3. Connects each point with `get_terrain_following_path`.

        Args:
            num_points (int): The number of points of interest to visit.
            altitude_agl (float): The desired altitude above ground for the flight.

        Returns:
            list: A list of (x, y, z) waypoints for the full recon path.
        """
        pois = self.suggest_objective_locations(num_points)
        if not pois or len(pois) < 2: 
            return []
        
        # Simple nearest neighbor sort to create a tour
        path_order = []
        remaining = pois[:]
        current = remaining.pop(0)
        path_order.append(current)

        while remaining:
            next_one = min(remaining, key=lambda p: np.linalg.norm(np.array(p['position']) - np.array(current['position'])))
            path_order.append(next_one)
            remaining.remove(next_one)
            current = next_one
        
        # Generate the full flight path
        full_path = []
        for i in range(len(path_order) - 1):
            start_pos = (path_order[i]['position'][0], path_order[i]['position'][2])
            end_pos = (path_order[i+1]['position'][0], path_order[i+1]['position'][2])
            segment = self.get_terrain_following_path(start_pos, end_pos, 20, altitude_agl)
            full_path.extend(segment)
            
        return full_path

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
        candidates = self.find_flat_landing_zones(search_area_center[0], search_area_center[1], search_radius, min_area_radius, max_slope_degrees=3.0)
        
        for pos in candidates:
            # Check if height is close to sea level
            if abs(pos[1] - sea_level) < 2.0: # Within 2m of sea level
                return pos
        return None

    def get_area_control_points(self, area_center, radius, num_points):
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

        Args:
            area_center (tuple): (x, z) center of the mission area.
            radius (float): Radius of the mission area.
            num_points (int): The number of control points to generate.

        Returns:
            list: A list of (x, y, z) positions for the control points.
        """
        control_points = []
        # Generate more candidates than needed
        candidates = self.get_random_points_in_area(area_center, radius, num_points * 3)

        for cand in candidates:
            # For simplicity, we'll just use the snapped random point for now.
            # A full implementation would check for nearby buildings/intersections.
            control_points.append(cand)
        
        return random.sample(control_points, min(num_points, len(control_points)))
    
    #region VIII. High-Level Mission Composition & Flavor

    def create_mission_flow(self, start_location_name, objective_type, target_location_name):
        """
        Generates a logical geographic sequence of waypoints for a complete mission.
        (Refined Logic)
        """
        if self._pois_cache is None:
            # Prime the cache by calling the function that populates it
            self.get_procedural_location_name((0,0,0)) 

        start_obj = next((o for o in self._pois_cache if o['name'] == start_location_name), None)
        target_obj = next((o for o in self._pois_cache if o['name'] == target_location_name), None)

        if not start_obj or not target_obj: 
            return None
        start_pos, target_pos = start_obj['position'], target_obj['position']
        
        # --- REFINED STAGING LOGIC ---
        if objective_type.upper() == 'CAS': # Close Air Support needs line of sight
            staging_pos = self.find_observation_post(target_pos, min_dist=4000, max_dist=8000)
        else: # Default to hidden for STRIKE, etc.
            staging_pos = self.find_artillery_position(target_pos, search_radius=8000, standoff_dist=4000)
        if not staging_pos: 
            staging_pos = start_pos # Fallback

        # --- REFINED EGRESS LOGIC ---
        # Find the safest map edge to egress towards (away from center)
        map_center = self.tc.total_map_size_meters / 2.0
        egress_target = np.array([target_pos[0], target_pos[2]])
        map_corners = [np.array([0,0]), np.array([map_center*2, 0]), np.array([0, map_center*2]), np.array([map_center*2, map_center*2])]
        safest_corner = min(map_corners, key=lambda c: -np.linalg.norm(c - egress_target)) # Furthest corner
        
        egress_vec = safest_corner - egress_target
        norm = np.linalg.norm(egress_vec)
        if norm > 0: 
            egress_vec /= norm
        egress_pos = np.array(target_pos) + np.array([egress_vec[0], 0, egress_vec[1]]) * 15000 # 15km away
        egress_pos = (egress_pos[0], egress_pos[1], egress_pos[2])

        return {'start': start_pos, 'staging': staging_pos, 'target': target_pos, 'egress': egress_pos}

    def get_procedural_location_name(self, position):
        """
        Gives a descriptive, procedural name to a location based on its characteristics.
        """
        if self._pois_cache is None:
            # This is where the cache is populated
            self._pois_cache = self.suggest_objective_locations(100)

        for poi in self._pois_cache:
            if np.linalg.norm(np.array(position) - np.array(poi['position'])) < 3000:
                return f"vicinity of {poi['name']}"

        map_center = self.tc.total_map_size_meters / 2.0
        terrain = self.get_terrain_type((position[0], position[2]))
        
        direction = ""
        if position[2] > map_center * 1.3: 
            direction += "Northern "
        elif position[2] < map_center * 0.7: 
            direction += "Southern "
        if position[0] > map_center * 1.3: 
            direction += "Eastern "
        elif position[0] < map_center * 0.7: 
            direction += "Western "
        
        return f"{direction}{terrain}"

    def get_map_briefing_data(self):
        """
        Generates a text summary of the map's key features for mission briefings.

        Why it's useful: Can be used to procedurally generate immersive mission briefing text.

        How it works (Logic):
        1. Calls `suggest_objective_locations` to get all major POIs.
        2. Categorizes them by name (e.g., 'airbase', 'city').
        3. Finds the most prominent terrain feature (e.g., the highest mountain).
        
        Returns:
            dict: A summary dictionary, e.g., {'cities': 2, 'airbases': 1, 'landmarks': ['Mount Kaylar']}.
        """
        if self._pois_cache is None: 
            self.get_procedural_location_name((0,0,0))
        
        summary = {'cities': 0, 'airbases': 0, 'landmarks': []}
        for poi in self._pois_cache:
            name = poi['name'].lower()
            if 'city' in name: 
                summary['cities'] += 1
            elif 'airbase' in name: 
                summary['airbases'] += 1
            elif 'peak' in name: 
                summary['landmarks'].append(poi['name'])
        
        return summary

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

    def find_scenic_overlook(self, point_of_interest, min_dist=1000, max_dist=4000):
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
        for _ in range(50):
            angle = random.uniform(0, 2 * np.pi)
            radius = np.sqrt(random.uniform(min_dist**2, max_dist**2))
            x = point_of_interest[0] + radius * np.cos(angle)
            z = point_of_interest[2] + radius * np.sin(angle)
            y = self.tc.get_terrain_height(x, z)
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
        # --- FIX: Iterate over list of dictionaries ---
        for seg in self.tc.road_segments:
            start, end = seg['start'], seg['end']
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
        for i in range(len(unit_positions)):
            for j in range(i + 1, len(unit_positions)):
                pos1 = unit_positions[i]
                pos2 = unit_positions[j]
                if self.has_line_of_sight(pos1, pos2):
                    visibility_graph[i].append(j)
                    visibility_graph[j].append(i)
        return visibility_graph
    

if __name__ == "__main__":
    # --- SETUP ---
    MAP_FOLDER = r"test_map/hMap2"
    LAYOUT_DB_PATH = 'Resources/city_layouts_database.json'
    INDIVIDUAL_DB_PATH = 'Resources/individual_prefabs_database.json'

    if not os.path.exists(MAP_FOLDER):
        print(f"Error: Map folder not found at '{MAP_FOLDER}'")
        print("Please ensure the test map is available to run this test script.")
    else:
        try:
            print("--- Initializing TerrainCalculator & MissionTerrainHelper ---")
            calculator = TerrainCalculator(MAP_FOLDER, LAYOUT_DB_PATH, INDIVIDUAL_DB_PATH)
            mission_helper = MissionTerrainHelper(calculator)
            print("-" * 50)

            # --- DATA FOR TESTING based on hMap2---
            # Use realistic coordinates based on a large map size
            map_center_x, map_center_z = calculator.total_map_size_meters / 2, calculator.total_map_size_meters / 2
            
            # A known city-like area for targeted tests
            city_pos = (57036.29, calculator.get_terrain_height(57036.29, 115526.57), 115526.57)
            
            # A known mountainous area
            mountain_pos = mission_helper.find_highest_point_in_area(54406.57, 110333.51, 10000)
            if not mountain_pos: 
                mountain_pos = (map_center_x + 50000, 1500, map_center_z + 50000) # Fallback

            # A known coastal area (assuming sea level is low)
            coastal_pos = (1000, 5, map_center_z)


            # --- CATEGORY I: Core Terrain & Object Queries ---
            print("\n--- CATEGORY I: Core Terrain & Object Queries ---")
            print("1.1 Testing has_line_of_sight...")
            los_result = mission_helper.has_line_of_sight(city_pos, (mountain_pos[0], mountain_pos[1] + 20, mountain_pos[2]))
            print(f"  -> LoS from city to mountain peak: {los_result}")
            
            print("\n1.2 Testing find_hidden_position...")
            hidden_pos = mission_helper.find_hidden_position(mountain_pos, (city_pos[0], city_pos[2]), 2000)
            print(f"  -> Found hidden position near city: {hidden_pos is not None}")


            # --- CATEGORY II: Strategic Area Analysis & Placement ---
            print("\n--- CATEGORY II: Strategic Area Analysis & Placement ---")
            print("2.1 Testing find_observation_post...")
            op = mission_helper.find_observation_post(city_pos, 3000, 6000)
            print(f"  -> Found observation post: {op is not None}")

            print("\n2.2 Testing find_artillery_position...")
            artillery_pos = mission_helper.find_artillery_position(city_pos, 8000, 4000)
            print(f"  -> Found artillery position: {artillery_pos is not None}")
            
            print("\n2.3 Testing get_terrain_type...")
            print(f"  -> Terrain type at city: '{mission_helper.get_terrain_type((city_pos[0], city_pos[2]))}'")
            print(f"  -> Terrain type at mountain: '{mission_helper.get_terrain_type((mountain_pos[0], mountain_pos[2]))}'")
            
            # This test requires a valid road path first
            road_path_for_choke = mission_helper.get_road_path((map_center_x, map_center_z), (mountain_pos[0], mountain_pos[2]))
            if road_path_for_choke:
                print("\n2.4 Testing find_choke_point...")
                choke = mission_helper.find_choke_point(road_path_for_choke)
                print(f"  -> Found choke point on path: {choke is not None}")


            # --- CATEGORY III: Advanced Pathfinding & Movement ---
            print("\n--- CATEGORY III: Advanced Pathfinding & Movement ---")
            # We already have a road path test in the previous section
            print("3.1 Testing get_convoy_dispersal_points...")
            road_info = mission_helper.get_nearest_road_point(city_pos[0], city_pos[2])
            if road_info:
                dispersal_pts = mission_helper.get_convoy_dispersal_points(road_info['position'], 4, 500)
                print(f"  -> Found {len(dispersal_pts)} dispersal points.")
            
            print("\n3.2 Testing find_riverbed_path...")
            river_path = mission_helper.find_riverbed_path((map_center_x, map_center_z), (mountain_pos[0], mountain_pos[2]))
            print(f"  -> Generated riverbed path with {len(river_path)} points.")

            # print("\n3.3 Testing find_bridge_crossing_path...")
            # bridge_path = mission_helper.find_bridge_crossing_path((map_center_x - 20000, map_center_z), (map_center_x + 20000, map_center_z))
            # print(f"  -> Found bridge path: {bridge_path is not None}")
            

            # --- CATEGORY IV: Air & Naval Operations ---
            print("\n--- CATEGORY IV: Air & Naval Operations ---")
            print("4.1 Testing find_helicopter_battle_position...")
            heli_pos = mission_helper.find_helicopter_battle_position(city_pos, 5000)
            print(f"  -> Found helicopter hide position: {heli_pos is not None}")

            print("\n4.2 Testing generate_bombing_run_path...")
            bomb_run = mission_helper.generate_bombing_run_path(city_pos, 180)
            print(f"  -> Generated bombing run IP: {bomb_run['ip']}")

            print("\n4.3 Testing define_safe_air_corridor...")
            corridor = mission_helper.define_safe_air_corridor((10000, 10000), (map_center_x, map_center_z), 5000, 3000, [mountain_pos])
            print(f"  -> Safe corridor score: {corridor['safety_score']:.2f}")

            print("\n4.4 Testing find_naval_bombardment_position...")
            naval_pos = mission_helper.find_naval_bombardment_position(coastal_pos, 5000)
            print(f"  -> Found naval bombardment position: {naval_pos is not None}")


            # --- CATEGORY V: Dynamic Campaign & Intelligence ---
            print("\n--- CATEGORY V: Dynamic Campaign & Intelligence ---")
            friendly_units = [(map_center_x - 5000, 100, map_center_z), (map_center_x - 6000, 100, map_center_z + 1000)]
            enemy_units = [(map_center_x + 5000, 100, map_center_z), (map_center_x + 6000, 100, map_center_z - 1000)]
            print("5.1 Testing calculate_front_line_trace...")
            front_line = mission_helper.calculate_front_line_trace(friendly_units, enemy_units)
            print(f"  -> Generated {len(front_line)} front line points.")

            print("\n5.2 Testing analyze_route_vulnerability...")
            vuln = mission_helper.analyze_route_vulnerability(road_path_for_choke)
            print(f"  -> Found {len(vuln.get('bridges',[]))} bridges and {len(vuln.get('choke_points',[]))} choke points on route.")

            print("\n5.3 Testing find_radar_dead_zone...")
            dead_zones = mission_helper.find_radar_dead_zone([mountain_pos], (city_pos[0], city_pos[2]), 10000, city_pos[1] + 150)
            print(f"  -> Found {len(dead_zones)} points in radar dead zones.")


            # --- CATEGORY VI: Formations & Unit Placement ---
            print("\n--- CATEGORY VI: Formations & Unit Placement ---")
            print("6.1 Testing get_line_formation_points...")
            line = mission_helper.get_line_formation_points(city_pos, 5, 100, 90)
            print(f"  -> Generated {len(line)} points for line formation.")

            print("\n6.2 Testing get_wedge_formation_points...")
            wedge = mission_helper.get_wedge_formation_points(city_pos, 5, 100, 0)
            print(f"  -> Generated {len(wedge)} points for wedge formation.")

            print("\n6.3 Testing find_open_area...")
            open_area = mission_helper.find_open_area((city_pos[0], city_pos[2]), 10000, 500)
            print(f"  -> Found open area: {open_area is not None}")


            # --- CATEGORY VII: Scenario & Storytelling Primitives ---
            print("\n--- CATEGORY VII: Scenario & Storytelling Primitives ---")
            print("7.1 Testing suggest_objective_locations...")
            objectives = mission_helper.suggest_objective_locations(3)
            print(f"  -> Suggested {len(objectives)} objective locations.")
            if objectives:
                print(f"     - Example: {objectives[0]['name']}")

            print("\n7.2 Testing generate_downed_pilot_scenario...")
            csar = mission_helper.generate_downed_pilot_scenario((mountain_pos[0], mountain_pos[2]), 10000)
            print(f"  -> Generated CSAR scenario: {csar is not None}")

            print("\n7.3 Testing generate_base_defense_positions...")
            def_pos = mission_helper.generate_base_defense_positions(city_pos, 4)
            print(f"  -> Generated {len(def_pos)} base defense positions.")
            
            print("\n7.4 Testing find_coastal_landing_area...")
            landing_area = mission_helper.find_coastal_landing_area((coastal_pos[0], coastal_pos[2]), 5000)
            print(f"  -> Found coastal landing area: {landing_area is not None}")


            # --- CATEGORY VIII: High-Level Mission Composition & Flavor ---
            print("\n--- CATEGORY VIII: High-Level Mission Composition & Flavor ---")
            if objectives and len(objectives) >= 2:
                print("8.1 Testing create_mission_flow...")
                flow = mission_helper.create_mission_flow(objectives[0]['name'], 'STRIKE', objectives[1]['name'])
                print(f"  -> Generated mission flow: {flow is not None}")

            print("\n8.2 Testing get_procedural_location_name...")
            name = mission_helper.get_procedural_location_name(mountain_pos)
            print(f"  -> Procedural name for mountain position: '{name}'")

            print("\n8.3 Testing get_area_defensibility_score...")
            score = mission_helper.get_area_defensibility_score((city_pos[0], city_pos[2]), 2000)
            print(f"  -> Defensibility score for city area: {score:.1f}/10")

            print("\n8.4 Testing calculate_threat_intervisibility...")
            vis_graph = mission_helper.calculate_threat_intervisibility(wedge)
            print(f"  -> Calculated intervisibility for {len(vis_graph)} units.")
            
            print("\n8.5 Testing validate_mission_feasibility...")
            units_to_check = [
                {'unit_type': 'tank', 'position': city_pos}, # Should be fine
                {'unit_type': 'truck', 'position': mountain_pos}, # Should fail
            ]
            errors = mission_helper.validate_mission_feasibility(units_to_check)
            print(f"  -> Validation found {len(errors)} errors.")

            print("\n8.6 Testing find_scenic_overlook...")
            overlook = mission_helper.find_scenic_overlook(city_pos)
            print(f"  -> Found scenic overlook: {overlook is not None}")
            
            print("\n8.7 Testing get_map_briefing_data...")
            briefing = mission_helper.get_map_briefing_data()
            print(f"  -> Generated briefing data: {briefing}")


        except Exception as e:
            print(f"\nAN ERROR OCCURRED DURING TESTING: {e}")
            traceback.print_exc()

