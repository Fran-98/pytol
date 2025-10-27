# -*- coding: utf-8 -*-
"""
Procedural terrain and city generation module mimicking VTOL VR's system.
"""
import os
import json
import traceback
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_FLOOR

import numpy as np
from PIL import Image
from scipy.ndimage import map_coordinates
from scipy.spatial.transform import Rotation as R

from ..parsers.vtm_parser import parse_vtol_data
from ..resources.resources import get_city_layout_database, get_prefab_database, get_noise_image
from ..misc.logger import create_logger

# --- City layout center offset (meters) ---
# Empirically aligns procedural city placements with in-game meshes
# Can be overridden at runtime via environment variables:
#   PYTOL_MANUAL_OFFSET_X, PYTOL_MANUAL_OFFSET_Z
try:
    MANUAL_OFFSET_X = float(os.getenv('PYTOL_MANUAL_OFFSET_X', '10'))
except Exception:
    MANUAL_OFFSET_X = 10.0
try:
    MANUAL_OFFSET_Z = float(os.getenv('PYTOL_MANUAL_OFFSET_Z', '-10'))
except Exception:
    MANUAL_OFFSET_Z = -10.0

# --- Base flatten zone margin (meters) ---
# Expand base flatten polygons by this margin to match in-game flattening area
# Useful when base footprints are slightly smaller than actual terrain flattening
try:
    BASE_FLATTEN_MARGIN = float(os.getenv('PYTOL_BASE_FLATTEN_MARGIN', '0'))
except Exception:
    BASE_FLATTEN_MARGIN = 0.0


def normal_to_euler_angles(terrain_normal, yaw_degrees):
    """Calculates Euler angles (pitch, yaw, roll) to align an object."""
    yaw_rotation = R.from_euler('y', yaw_degrees, degrees=True)
    source_up = np.array([0, 1, 0])
    if np.linalg.norm(terrain_normal) < 1e-6: 
        terrain_normal = source_up
    axis = np.cross(source_up, terrain_normal)
    angle = np.arccos(np.dot(source_up, terrain_normal))
    if np.linalg.norm(axis) < 1e-6:
        tilt_rotation = R.identity() if angle < np.pi/2 else R.from_euler('x', 180, degrees=True)
    else:
        tilt_rotation = R.from_rotvec(axis / np.linalg.norm(axis) * angle)
    final_rotation = tilt_rotation * yaw_rotation
    euler_angles = final_rotation.as_euler('yxz', degrees=True)
    pitch, yaw, roll = euler_angles[1], euler_angles[0], euler_angles[2]
    if roll < 0: 
        roll += 360
    return (pitch, yaw, roll)

def get_bezier_point(s, m, e, t):
    """Calculates a point on a quadratic Bézier curve."""
    t = np.clip(t, 0, 1)
    a = s + t * (m - s)
    b = m + t * (e - m)
    return a + t * (b - a)


class TerrainCalculator:
    """
    Calculates terrain height, normals, and procedural object placement.
    """

    def __init__(self, map_name: str = '', map_directory_path: str = '', vtol_directory: str = '', verbose: bool = True):
        """Initializes the TerrainCalculator by loading all necessary data."""
        self.verbose = verbose
        # Centralized logger
        self.logger = create_logger(verbose=verbose, name="TerrainCalculator")
        
        if map_directory_path:
            self.map_dir = map_directory_path
            self.map_name = os.path.basename(os.path.normpath(map_directory_path))
        elif map_name and vtol_directory:
            self.map_dir = os.path.join(os.path.normpath(vtol_directory), 'CustomMaps', map_name)
            self.map_name = map_name
        elif map_name and os.getenv('VTOL_VR_DIR'):
            self.map_dir = os.path.join(os.path.normpath(os.getenv('VTOL_VR_DIR')), 'CustomMaps', map_name)
            self.map_name = map_name
        else:
            raise ValueError("Either 'map_directory_path' or both 'map_name' and 'vtol_directory' must be provided.")
        
        # Check for known incompatible maps
        if hasattr(self, 'map_name') and self.map_name == 'afMtnsHills':
            raise ValueError(
                "Map 'afMtnsHills' has known compatibility issues with pytol and cannot be loaded.\n"
                "Please try a different map."
            )
        
        self._log(f"Initializing TerrainCalculator for: {self.map_dir}")

        # --- Load Data ---
        self._load_vtm_file(self.map_dir)
        self._load_textures()
        self._load_databases()

        # --- Calibrate and Pre-process ---
        self.coord_transform_mode = None
        self._discover_coordinate_transform()
        # Optional vertical calibration against known ground-truth points (e.g., roads)
        self._auto_calibrate_height_if_enabled()
        
        # --- Pre-process bases FIRST (before city blocks, as get_terrain_height needs them) ---
        self.bases = self._process_bases() # Extract base information
        
        # Then process other objects that may call get_terrain_height
        self.city_blocks = self._generate_all_city_blocks()
        self.static_surfaces = self._process_static_prefabs()
        self.road_segments = self._process_all_roads() # New
        
        self._log(f"Map Size: {self.total_map_size_meters/1000.0:.1f} km ({self.map_size_grids} grids)")
        self._log(f"Altitude Range: {self.min_height}m to {self.max_height}m")
        self._log(f"Processed {len(self.city_blocks)} city blocks.")
        self._log(f"Processed {len(self.static_surfaces)} static surfaces.")
        self._log(f"Processed {len(self.road_segments)} total road segments.")
        self._log(f"Processed {len(self.bases)} bases.")
        self._log(f"Using Coordinate Transform Mode = {self.coord_transform_mode}")

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

    def _load_vtm_file(self, map_directory_path):
        vtm_filename = os.path.basename(os.path.normpath(map_directory_path)) + ".vtm"
        vtm_path = os.path.join(self.map_dir, vtm_filename)
        try:
            with open(os.path.normpath(vtm_path), 'r', encoding='utf-8') as f:
                vtm_content = f.read()
        except FileNotFoundError as e: 
            raise FileNotFoundError(f"Fatal Error! .vtm file not found: '{vtm_path}'.") from e
        parsed_data = parse_vtol_data(vtm_content)
        self.map_data = parsed_data.get('VTMapCustom')
        if not self.map_data: 
            raise ValueError("The .vtm file does not contain 'VTMapCustom' data.")
        self.map_size_grids = int(self.map_data.get('mapSize'))
        if not self.map_size_grids: 
            raise ValueError("'mapSize' not found in .vtm file.")
        self.chunk_size_meters = 3072.0
        self.total_map_size_meters = float(self.map_size_grids) * self.chunk_size_meters
        # Default/fallback range
        self.max_height = float(self.map_data.get('hm_maxHeight', 6000.0))
        self.min_height = float(self.map_data.get('hm_minHeight', -80.0))

        # Try to read from nested TerrainSettings if available
        ts = self.map_data.get('TerrainSettings', {}) or {}
        def _get_first(ts_dict, keys):
            for k in keys:
                if k in ts_dict:
                    try:
                        return float(ts_dict.get(k))
                    except Exception:
                        continue
            return None

        # Common key variants observed/expected in VTOL VR content
        max_keys = ['maxMtnHeight', 'maxHeight', 'hm_maxHeight']
        min_keys = ['minMtnHeight', 'minHeight', 'seaLevel', 'hm_minHeight']
        max_from_ts = _get_first(ts, max_keys)
        min_from_ts = _get_first(ts, min_keys)
        if max_from_ts is not None:
            self.max_height = max_from_ts
        if min_from_ts is not None:
            self.min_height = min_from_ts

        # Optional: try to read overrides from Unity .meta sidecar (height.png.meta)
        # Some maps may encode custom min/max in TextureImporter.userData or ad-hoc keys
        try:
            self._load_height_meta_if_any()
        except Exception:
            # Non-fatal: continue with existing min/max
            pass

        # Optional post-adjustment scale/offset applied to terrain-derived heights only
        try:
            self.height_post_scale = float(os.getenv('PYTOL_HEIGHT_POST_SCALE', '1.0'))
        except Exception:
            self.height_post_scale = 1.0
        try:
            self.height_post_offset = float(os.getenv('PYTOL_HEIGHT_POST_OFFSET', '0.0'))
        except Exception:
            self.height_post_offset = 0.0

    def _load_height_meta_if_any(self):
        """Optionally parse Unity's height.png.meta for altitude hints.

        Heuristics:
        - If height.png.meta contains userData with JSON (e.g., {"minHeight":-80, "maxHeight":6000}), apply when VTM didn't provide values.
        - Else, look for plain YAML-like keys: minHeight: <num>, maxHeight: <num>.
        - Only override values that were not already set by VTM/TerrainSettings (i.e., when those were missing).
        """
        meta_path = os.path.join(self.map_dir, 'height.png.meta')
        if not os.path.exists(meta_path):
            return
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta_text = f.read()
        except Exception:
            return

        # Track whether VTM/TerrainSettings provided values
        had_vtm_max = 'hm_maxHeight' in self.map_data or ('TerrainSettings' in self.map_data and self.map_data.get('TerrainSettings'))
        had_vtm_min = 'hm_minHeight' in self.map_data or ('TerrainSettings' in self.map_data and self.map_data.get('TerrainSettings'))

        # Try to extract JSON from userData: "{...}"
        import re
        import json
        m = re.search(r'userData:\s*"([^"]+)"', meta_text)
        if m:
            blob = m.group(1)
            try:
                data = json.loads(blob)
                if isinstance(data, dict):
                    if not had_vtm_min and 'minHeight' in data:
                        self.min_height = float(data['minHeight'])
                    if not had_vtm_max and 'maxHeight' in data:
                        self.max_height = float(data['maxHeight'])
            except Exception:
                pass

        # Fallback: parse simple YAML-like lines if present
        if not had_vtm_min:
            m2 = re.search(r'\bminHeight:\s*([-+]?\d+(?:\.\d+)?)', meta_text)
            if m2:
                try:
                    self.min_height = float(m2.group(1))
                except Exception:
                    pass
        if not had_vtm_max:
            m3 = re.search(r'\bmaxHeight:\s*([-+]?\d+(?:\.\d+)?)', meta_text)
            if m3:
                try:
                    self.max_height = float(m3.group(1))
                except Exception:
                    pass

    def _load_textures(self):
        heightmap_path = os.path.join(self.map_dir, 'height.png')
        try:
            with Image.open(heightmap_path) as image:
                image = image.convert('RGB')
                np_image = np.array(image)
                flip_flag = os.getenv('PYTOL_HEIGHT_FLIPUD', '1') != '0'

                # Extract channels as floats 0..1
                chan_r = np_image[:, :, 0].astype(np.float32) / 255.0
                chan_g = np_image[:, :, 1].astype(np.float32) / 255.0
                chan_b = np_image[:, :, 2].astype(np.float32) / 255.0

                # Optional sRGB -> linear correction
                do_linearize = os.getenv('PYTOL_LINEARIZE_SRGB', '0') == '1'
                if do_linearize:
                    def srgb_to_linear(c: np.ndarray) -> np.ndarray:
                        a = 0.055
                        return np.where(c <= 0.04045, c / 12.92, ((c + a) / (1 + a)) ** 2.4)
                    chan_r = srgb_to_linear(chan_r)
                    chan_g = srgb_to_linear(chan_g)
                    chan_b = srgb_to_linear(chan_b)

                # Choose which channel encodes height
                height_channel = os.getenv('PYTOL_HEIGHT_CHANNEL', 'R').upper()
                if height_channel == 'G':
                    chosen_height = chan_g
                elif height_channel == 'B':
                    chosen_height = chan_b
                else:
                    chosen_height = chan_r

                if flip_flag:
                    chosen_height = np.flipud(chosen_height)
                    chan_g = np.flipud(chan_g)

                # Store height channel in R-slot for downstream code
                self.heightmap_data_r = chosen_height
                # Keep G-channel (city density) as-is (after optional flip)
                self.heightmap_data_g = chan_g
            self.hm_height, self.hm_width = self.heightmap_data_r.shape

            noise_img = get_noise_image()
            noise = np.array(noise_img.convert('L')).astype(np.float32) / 255.0
            if flip_flag:
                noise = np.flipud(noise)
            self.noise_texture_data = noise
            self.noise_height, self.noise_width = self.noise_texture_data.shape
        except FileNotFoundError as e: 
            raise FileNotFoundError(f"Fatal Error loading textures: {e}") from e

    def _load_databases(self):
        try:
            self.city_layouts_db = get_city_layout_database()
            self.layouts_by_level = self.city_layouts_db.get('layouts_by_level')
            self.layout_data_db = self.city_layouts_db.get('layout_data')
            
            self.individual_prefabs_db = get_prefab_database()

        except FileNotFoundError as e: 
            raise FileNotFoundError(f"Fatal Error loading databases: {e}") from e

    def _process_static_prefabs(self):
        """Parses static prefabs from .vtm and calculates world-space bounds for all their surfaces."""
        static_prefabs_node = self.map_data.get('StaticPrefabs', {}).get('StaticPrefab', [])
        if not isinstance(static_prefabs_node, list): 
            static_prefabs_node = [static_prefabs_node] if static_prefabs_node else []
        
        processed_surfaces = []
        prefab_name_to_key = {os.path.splitext(os.path.basename(key))[0]: key for key in self.individual_prefabs_db.keys()}

        for static_prefab in static_prefabs_node:
            prefab_name = static_prefab.get('prefab')
            db_key = prefab_name_to_key.get(prefab_name)
            if not db_key or db_key not in self.individual_prefabs_db: 
                continue

            try:
                pos = np.array(static_prefab.get('globalPos'), dtype=float)
                rot = np.array(static_prefab.get('rotation'), dtype=float)
                prefab_rot_matrix = R.from_euler('yxz', [rot[1], rot[0], rot[2]], degrees=True).as_matrix()

                for surface in self.individual_prefabs_db[db_key]:
                    bounds_rel = np.array(surface['bounds'])
                    min_rel, max_rel = np.array([bounds_rel[0],bounds_rel[2],bounds_rel[4]]), np.array([bounds_rel[1],bounds_rel[3],bounds_rel[5]])
                    corners_rel = [np.array([dx,dy,dz]) for dx in [min_rel[0],max_rel[0]] for dy in [min_rel[1],max_rel[1]] for dz in [min_rel[2],max_rel[2]]]
                    corners_abs = [prefab_rot_matrix.dot(c) + pos for c in corners_rel]
                    min_abs, max_abs = np.min(corners_abs, axis=0), np.max(corners_abs, axis=0)
                    processed_surfaces.append({
                        'name': surface.get('go_name', 'N/A'), 'prefab_name': prefab_name,
                        'world_bounds': [float(v) for v in min_abs] + [float(v) for v in max_abs],
                        'is_spawnable': surface.get('is_spawnable', False)
                    })
            except (TypeError, ValueError, KeyError) as e:
                self._log(f"Warning: Could not process static prefab '{prefab_name}'. Invalid data: {e}")
        return processed_surfaces

    def _process_bases(self):
        """
        Extracts base information from static prefabs (airbases, carriers, etc.)
        and calculates their terrain flattening zones.
        
        Returns:
            list: List of dictionaries containing base information including:
                - id: Base ID from VTM
                - name: Base name (if provided in VTM)
                - prefab_type: Type of base (airbase1, airbase2, carrier1, etc.)
                - position: Global position (x, y, z)
                - rotation: Rotation angles (pitch, yaw, roll)
                - footprint: Bounding box dimensions in local space
                - flatten_zone: World-space polygon defining terrain flattening area
        """
        static_prefabs_node = self.map_data.get('StaticPrefabs', {}).get('StaticPrefab', [])
        if not isinstance(static_prefabs_node, list):
            static_prefabs_node = [static_prefabs_node] if static_prefabs_node else []
        
        bases = []
        base_keywords = ['airbase', 'carrier', 'fob']  # Base prefab identifiers
        
        for static_prefab in static_prefabs_node:
            prefab_name = static_prefab.get('prefab', '').lower()
            
            # Check if this is a base prefab
            if not any(keyword in prefab_name for keyword in base_keywords):
                continue
            
            try:
                base_id = static_prefab.get('id')
                base_name = static_prefab.get('baseName', f'Base {base_id}')
                position = np.array(static_prefab.get('globalPos'), dtype=float)
                rotation = np.array(static_prefab.get('rotation'), dtype=float)
                
                # Get footprint dimensions from prefab database
                prefab_key = f"bases/{static_prefab.get('prefab')}.prefab"
                footprint = self._get_base_footprint(prefab_key)
                
                # Calculate world-space flattening zone
                # Bases flatten terrain in a rectangular area matching their footprint
                flatten_zone = self._calculate_flatten_zone(position, rotation, footprint)
                
                base_info = {
                    'id': base_id,
                    'name': base_name,
                    'prefab_type': static_prefab.get('prefab'),
                    'position': position.tolist(),
                    'rotation': rotation.tolist(),
                    'footprint': footprint,
                    'flatten_zone': flatten_zone,
                    'flatten_height': float(position[1])  # Y coordinate is the flatten height
                }
                
                bases.append(base_info)
                
            except (TypeError, ValueError, KeyError) as e:
                self._log(f"Warning: Could not process base '{prefab_name}'. Invalid data: {e}")
        
        return bases
    
    def _get_base_footprint(self, prefab_key):
        """
        Retrieves the bounding box dimensions for a base prefab from the database.
        
        Args:
            prefab_key: The prefab database key (e.g., "bases/airbase1.prefab")
        
        Returns:
            dict: {'x_min', 'x_max', 'z_min', 'z_max', 'width', 'length'} in local space
        """
        if prefab_key not in self.individual_prefabs_db:
            # Default fallback dimensions for unknown bases
            return {
                'x_min': -500, 'x_max': 500,
                'z_min': -1000, 'z_max': 1000,
                'width': 1000, 'length': 2000
            }
        
        surfaces = self.individual_prefabs_db[prefab_key]
        all_bounds = [surf['bounds'] for surf in surfaces]
        
        x_min = min(b[0] for b in all_bounds)
        x_max = max(b[1] for b in all_bounds)
        z_min = min(b[4] for b in all_bounds)
        z_max = max(b[5] for b in all_bounds)
        
        return {
            'x_min': float(x_min), 'x_max': float(x_max),
            'z_min': float(z_min), 'z_max': float(z_max),
            'width': float(x_max - x_min),
            'length': float(z_max - z_min)
        }
    
    def _calculate_flatten_zone(self, position, rotation, footprint):
        """
        Calculates the world-space polygon defining where a base flattens terrain.
        
        Args:
            position: np.array of (x, y, z) global position
            rotation: np.array of (pitch, yaw, roll) in degrees
            footprint: dict with x_min, x_max, z_min, z_max in local space
        
        Returns:
            list: Four corner points [[x1,z1], [x2,z2], [x3,z3], [x4,z4]] defining the rectangular flatten zone
        """
        # Create rotation matrix from Euler angles
        rot_matrix = R.from_euler('yxz', [rotation[1], rotation[0], rotation[2]], degrees=True).as_matrix()
        
        # Apply margin to expand the footprint (if PYTOL_BASE_FLATTEN_MARGIN is set)
        margin = BASE_FLATTEN_MARGIN
        x_min = footprint['x_min'] - margin
        x_max = footprint['x_max'] + margin
        z_min = footprint['z_min'] - margin
        z_max = footprint['z_max'] + margin
        
        # Define the four corners of the footprint rectangle in local space
        corners_local = [
            np.array([x_min, 0, z_min]),  # Bottom-left
            np.array([x_max, 0, z_min]),  # Bottom-right
            np.array([x_max, 0, z_max]),  # Top-right
            np.array([x_min, 0, z_max])   # Top-left
        ]
        
        # Transform to world space
        corners_world = [rot_matrix.dot(c) + position for c in corners_local]
        
        # Return as [x, z] pairs (we only need horizontal coordinates for point-in-polygon test)
        return [[float(c[0]), float(c[2])] for c in corners_world]

    def _process_all_roads(self):
        """
        Generates line segments for both Bézier roads and procedural city grid roads.
        This is run once at initialization.
        """
        all_segments = []
        # 1. Process Bézier roads from .vtm
        road_chunks = self.map_data.get('BezierRoads', {}).get('Chunk', [])
        if not isinstance(road_chunks, list): 
            road_chunks = [road_chunks] if road_chunks else []
        for chunk in road_chunks:
            segments = chunk.get('Segment', [])
            if not isinstance(segments, list): 
                segments = [segments] if segments else []
            for seg in segments:
                try:
                    s, m, e = np.array(seg['s']), np.array(seg['m']), np.array(seg['e'])
                    # Sample points along the curve to create line segments
                    points = [get_bezier_point(s, m, e, t) for t in np.linspace(0, 1, 5)]
                    for i, _ in enumerate(points[:-1]):
                        all_segments.append((points[i], points[i+1]))
                except (KeyError, TypeError, ValueError): 
                    continue
        
        # 2. Process procedural city grid roads using final block positions
        if not self.city_blocks: 
            return all_segments
        
        # Create a map from pixel coordinate to the block's world position for fast lookup
        block_position_map = {tuple(block['pixel_coord']): block['world_position'] for block in self.city_blocks}

        # This new logic calculates road segment endpoints by averaging the
        # positions of prefabs on either side of the road gap.
        for px_py_tuple, p_A_world_full in block_position_map.items():
            px, py = px_py_tuple

            # --- A. Check for a HORIZONTAL road segment ---
            # A horizontal road runs BETWEEN py=1 and py=2, py=3 and py=4, etc.
            # So, we trigger when py is ODD.
            if (py % 2 != 0):
                # We need 4 points to define the road segment:
                # A=(px, py)     B=(px+1, py)
                #   [--ROAD--]
                # C=(px, py+1)   D=(px+1, py+1)
                
                coord_B = (px + 1, py)
                coord_C = (px, py + 1)
                coord_D = (px + 1, py + 1)

                # Check if all 3 other prefabs exist
                if (coord_B in block_position_map) and \
                   (coord_C in block_position_map) and \
                   (coord_D in block_position_map):
                    
                    p_B_world_full = block_position_map[coord_B]
                    p_C_world_full = block_position_map[coord_C]
                    p_D_world_full = block_position_map[coord_D]

                    # Start of segment is midpoint between A and C
                    road_z_start = (p_A_world_full[2] + p_C_world_full[2]) / 2.0
                    road_x_start = p_A_world_full[0] # X is the same as A
                    seg_start = np.array([road_x_start, 0, road_z_start])

                    # End of segment is midpoint between B and D
                    road_z_end = (p_B_world_full[2] + p_D_world_full[2]) / 2.0
                    road_x_end = p_B_world_full[0] # X is the same as B
                    seg_end = np.array([road_x_end, 0, road_z_end])
                    
                    all_segments.append((seg_start, seg_end))


            # --- B. Check for a VERTICAL road segment ---
            # A vertical road runs BETWEEN px=1 and px=2, px=3 and px=4, etc.
            # So, we trigger when px is ODD.
            if (px % 2 != 0):
                # We need 4 points to define the road segment:
                # A=(px, py)   C=(px, py+1)
                #     |
                #   [ROAD]
                #     |
                # B=(px+1, py) D=(px+1, py+1)
                
                coord_B = (px + 1, py)
                coord_C = (px, py + 1)
                coord_D = (px + 1, py + 1)
                
                # Check if all 3 other prefabs exist
                if (coord_B in block_position_map) and \
                   (coord_C in block_position_map) and \
                   (coord_D in block_position_map):

                    p_B_world_full = block_position_map[coord_B]
                    p_C_world_full = block_position_map[coord_C]
                    p_D_world_full = block_position_map[coord_D]
                    
                    # Start of segment is midpoint between A and B
                    road_x_start = (p_A_world_full[0] + p_B_world_full[0]) / 2.0
                    road_z_start = p_A_world_full[2] # Z is the same as A
                    seg_start = np.array([road_x_start, 0, road_z_start])

                    # End of segment is midpoint between C and D
                    road_x_end = (p_C_world_full[0] + p_D_world_full[0]) / 2.0
                    road_z_end = p_C_world_full[2] # Z is the same as C
                    seg_end = np.array([road_x_end, 0, road_z_end])
                    
                    all_segments.append((seg_start, seg_end))

        # --- END MODIFICATION ---
        return all_segments
        
    # --- Other private methods (_discover_coordinate_transform, _world_to_pixel..., etc.) remain unchanged ---
    def _discover_coordinate_transform(self):
        """Determine UV-to-pixel orientation by calibrating against a known prefab.

        We test 8 possible image orientation modes and pick the one whose sampled
        height (from the R channel) matches the prefab's expected height best.
        Fallback to mode 4 if calibration fails.
        """
        try:
            # Optional override via environment variable for quick testing/fixes
            forced_mode = os.getenv('PYTOL_FORCE_COORD_MODE')
            if forced_mode is not None:
                try:
                    mode_val = int(forced_mode)
                    if 0 <= mode_val <= 7:
                        self.coord_transform_mode = mode_val
                        self._log(f"Coordinate transform mode forced via env: {mode_val}")
                        return
                    else:
                        self._log(f"Warning: Ignoring PYTOL_FORCE_COORD_MODE={forced_mode} (out of range 0..7)")
                except ValueError:
                    self._log(f"Warning: Ignoring PYTOL_FORCE_COORD_MODE={forced_mode} (not an int)")

            prefabs_node = self.map_data.get('StaticPrefabs', {}).get('StaticPrefab', [])
            if not isinstance(prefabs_node, list):
                prefabs_node = [prefabs_node] if prefabs_node else []
            if not prefabs_node:
                raise ValueError("No static prefabs found for calibration.")

            prefab_0 = prefabs_node[0]
            if 'globalPos' not in prefab_0:
                raise ValueError("First static prefab lacks 'globalPos'.")

            global_pos = prefab_0['globalPos']
            if not isinstance(global_pos, (list, tuple)) or len(global_pos) != 3:
                raise ValueError("Invalid 'globalPos' format.")

            world_x, expected_y, world_z = map(float, global_pos)
            expected_r = (expected_y - self.min_height) / (self.max_height - self.min_height)
            uv_x = world_x / self.total_map_size_meters
            uv_z = world_z / self.total_map_size_meters

            best_mode = -1
            min_diff = float('inf')
            for mode in range(8):
                found_r = self._get_pixel_value(self.heightmap_data_r, uv_x, uv_z, mode)
                diff = abs(found_r - expected_r)
                if np.isclose(found_r, expected_r, atol=0.001):
                    self.coord_transform_mode = mode
                    return
                if diff < min_diff:
                    min_diff = diff
                    best_mode = mode

            if best_mode != -1:
                self.coord_transform_mode = best_mode
            else:
                raise Exception("Calibration failed - no suitable mode found.")
        except Exception as e:
            self._log(f"Warning: Calibration failed ({e}). Falling back to mode 4.")
            self.coord_transform_mode = 4
    def _world_to_pixel_bankers_rounding(self, world_x, world_z):
        uv_x = Decimal(str(world_x)) / Decimal(str(self.total_map_size_meters))
        uv_z = Decimal(str(world_z)) / Decimal(str(self.total_map_size_meters))

        pixel_x_f, pixel_y_f = Decimal(0), Decimal(0)
        map_width_minus_1 = Decimal(self.hm_width - 1)
        map_height_minus_1 = Decimal(self.hm_height - 1)
        mode = self.coord_transform_mode
        u, v = uv_x, uv_z

        if mode == 0:
            pixel_x_f, pixel_y_f = u * map_width_minus_1, v * map_height_minus_1
        elif mode == 1:
            pixel_x_f, pixel_y_f = v * map_width_minus_1, u * map_height_minus_1
        elif mode == 2:
            pixel_x_f, pixel_y_f = (Decimal(1) - u) * map_width_minus_1, v * map_height_minus_1
        elif mode == 3:
            pixel_x_f, pixel_y_f = v * map_width_minus_1, (Decimal(1) - u) * map_height_minus_1
        elif mode == 4:
            pixel_x_f, pixel_y_f = u * map_width_minus_1, (Decimal(1) - v) * map_height_minus_1
        elif mode == 5:
            pixel_x_f, pixel_y_f = (Decimal(1) - v) * map_width_minus_1, u * map_height_minus_1
        elif mode == 6:
            pixel_x_f, pixel_y_f = (Decimal(1) - u) * map_width_minus_1, (Decimal(1) - v) * map_height_minus_1
        elif mode == 7:
            pixel_x_f, pixel_y_f = (Decimal(1) - v) * map_width_minus_1, (Decimal(1) - u) * map_height_minus_1

        pixel_x = int(pixel_x_f.quantize(Decimal('1'), rounding=ROUND_HALF_EVEN))
        pixel_y = int(pixel_y_f.quantize(Decimal('1'), rounding=ROUND_HALF_EVEN))
        pixel_x = np.clip(pixel_x, 0, self.hm_width - 1)
        pixel_y = np.clip(pixel_y, 0, self.hm_height - 1)
        return pixel_x, pixel_y
    def _pixel_to_world_vtstyle(self, px, py):
        verts_per_side = 20
        chunk_size = float(self.chunk_size_meters)
        chunk_x = int(np.floor(px / verts_per_side))
        chunk_y = int(np.floor(py / verts_per_side))
        px_local = px - (chunk_x * verts_per_side)
        py_local = py - (chunk_y * verts_per_side)
        meters_per_pixel = chunk_size / float(verts_per_side)
        local_x = float(px_local) * meters_per_pixel
        local_z = float(py_local) * meters_per_pixel
        world_x = (chunk_x * chunk_size) + local_x
        world_z = (chunk_y * chunk_size) + local_z
        return world_x, world_z
    def _world_to_pixel_vtstyle_global(self, world_x, world_z):
        verts_per_side = 20
        chunk_size_d = Decimal(str(self.chunk_size_meters))
        meters_per_pixel_d = chunk_size_d / Decimal(verts_per_side)
        if meters_per_pixel_d == 0:
            meters_per_pixel_d = Decimal(1.0)

        world_x_d = Decimal(str(world_x))
        world_z_d = Decimal(str(world_z))
        chunk_x = int((world_x_d / chunk_size_d).to_integral_value(rounding=ROUND_FLOOR))
        chunk_y = int((world_z_d / chunk_size_d).to_integral_value(rounding=ROUND_FLOOR))
        local_x_d = world_x_d - (Decimal(chunk_x) * chunk_size_d)
        local_z_d = world_z_d - (Decimal(chunk_y) * chunk_size_d)
        px_local_d = (local_x_d / meters_per_pixel_d).to_integral_value(rounding=ROUND_FLOOR)
        py_local_d = (local_z_d / meters_per_pixel_d).to_integral_value(rounding=ROUND_FLOOR)
        px_global = chunk_x * verts_per_side + int(px_local_d)
        py_global = chunk_y * verts_per_side + int(py_local_d)
        return int(px_global), int(py_global)
    def _get_pixel_value(self, data_channel, u, v, mode=None):
        if mode is None:
            mode = self.coord_transform_mode

        pixel_x_f, pixel_y_f = 0.0, 0.0
        map_width_minus_1 = float(self.hm_width - 1)
        map_height_minus_1 = float(self.hm_height - 1)
        u_f, v_f = float(u), float(v)

        if mode == 0:
            pixel_x_f, pixel_y_f = u_f * map_width_minus_1, v_f * map_height_minus_1
        elif mode == 1:
            pixel_x_f, pixel_y_f = v_f * map_width_minus_1, u_f * map_height_minus_1
        elif mode == 2:
            pixel_x_f, pixel_y_f = (1.0 - u_f) * map_width_minus_1, v_f * map_height_minus_1
        elif mode == 3:
            pixel_x_f, pixel_y_f = v_f * map_width_minus_1, (1.0 - u_f) * map_height_minus_1
        elif mode == 4:
            pixel_x_f, pixel_y_f = u_f * map_width_minus_1, (1.0 - v_f) * map_height_minus_1
        elif mode == 5:
            pixel_x_f, pixel_y_f = (1.0 - v_f) * map_width_minus_1, u_f * map_height_minus_1
        elif mode == 6:
            pixel_x_f, pixel_y_f = (1.0 - u_f) * map_width_minus_1, (1.0 - v_f) * map_height_minus_1
        elif mode == 7:
            pixel_x_f, pixel_y_f = (1.0 - v_f) * map_width_minus_1, (1.0 - u_f) * map_height_minus_1

        try:
            pixel_y_f_clamped = np.clip(pixel_y_f, 0.0, float(self.hm_height - 1))
            pixel_x_f_clamped = np.clip(pixel_x_f, 0.0, float(self.hm_width - 1))
            return map_coordinates(
                data_channel,
                [[pixel_y_f_clamped], [pixel_x_f_clamped]],
                order=1,
                mode='nearest',
            )[0]
        except Exception:
            px_int = np.clip(int(round(pixel_x_f)), 0, self.hm_width - 1)
            py_int = np.clip(int(round(pixel_y_f)), 0, self.hm_height - 1)
            return data_channel[py_int, px_int]
    def _iter_road_ground_points(self, max_points=200):
        """Yield (x, y, z) points from BezierRoads that should lie on terrain.

        We use the control points s, m, e of each segment as anchors. These Y values
        reflect terrain-conforming roads in VTOL VR, providing good calibration pairs.
        """
        road_chunks = self.map_data.get('BezierRoads', {}).get('Chunk', [])
        if not isinstance(road_chunks, list):
            road_chunks = [road_chunks] if road_chunks else []
        count = 0
        for chunk in road_chunks:
            segments = chunk.get('Segment', [])
            if not isinstance(segments, list):
                segments = [segments] if segments else []
            for seg in segments:
                for key in ('s', 'm', 'e'):
                    pt = seg.get(key)
                    if isinstance(pt, (list, tuple)) and len(pt) == 3:
                        yield float(pt[0]), float(pt[1]), float(pt[2])
                        count += 1
                        if count >= max_points:
                            return
    def _auto_calibrate_height_if_enabled(self):
        """Optionally fit y = A*r + B using road anchor points and adjust min/max.

        Enabled when:
        - PYTOL_AUTO_HEIGHT_CALIBRATE=1, or
        - No explicit height info found in VTM/TerrainSettings (default-on fallback).

        If not enough anchors exist or fit fails, keep existing min/max.
        """
        flag = os.getenv('PYTOL_AUTO_HEIGHT_CALIBRATE', '0')
        enabled = (flag == '1')
        if not enabled:
            return
        try:
            anchors = list(self._iter_road_ground_points(max_points=400))
            if len(anchors) < 3:
                return
            uvs = []
            ys = []
            for (wx, wy, wz) in anchors:
                uvx = wx / self.total_map_size_meters
                uvz = wz / self.total_map_size_meters
                r = self._get_pixel_value(self.heightmap_data_r, uvx, uvz)
                if np.isfinite(r):
                    uvs.append(float(r))
                    ys.append(float(wy))
            if len(uvs) < 3:
                return
            U = np.array(uvs, dtype=float)
            Y = np.array(ys, dtype=float)
            X = np.vstack([U, np.ones(len(U))]).T
            coef, *_ = np.linalg.lstsq(X, Y, rcond=None)
            Y_pred = X @ coef
            resid = np.abs(Y - Y_pred)
            # Robustify: trim top 20% largest residuals and refit if enough points remain
            if len(resid) >= 10:
                thresh = np.quantile(resid, 0.8)
                mask = resid <= thresh
                if np.count_nonzero(mask) >= 3:
                    X2 = X[mask]
                    Y2 = Y[mask]
                    coef, *_ = np.linalg.lstsq(X2, Y2, rcond=None)
            A, B = float(coef[0]), float(coef[1])
            # Update min/max so that y ≈ r*(max-min)+min, with range=A and min=B
            new_min = B
            new_max = B + A
            if np.isfinite(new_min) and np.isfinite(new_max) and new_max > new_min:
                self.min_height = float(new_min)
                self.max_height = float(new_max)
                self._log(f"Calibrated altitude range from roads: {self.min_height:.3f}m to {self.max_height:.3f}m (A={A:.6f}, B={B:.6f})")
        except Exception as e:
            self._log(f"Warning: Auto height calibration failed: {e}")
    
    # --- Public Methods ---
    def get_terrain_height(self, world_x, world_z):
        """
        Returns terrain height at a world coordinate, accounting for terrain deformation.
        
    Checks in priority order:
    1. Base flattening zones (airbases, carriers, etc.)
    2. Natural heightmap terrain

    Note: Procedural cities do not modify the terrain heightmap. In-game, city
    meshes are conformed to the terrain via mesh deformation (raycasts), so
    city areas use the natural height.
        
        Args:
            world_x: X coordinate in world space
            world_z: Z coordinate in world space
        
        Returns:
            float: Terrain height in meters
        """
        if self.coord_transform_mode is None:
            raise Exception("Not calibrated.")
        
        # Check if point is within any base's flattening zone
        for base in self.bases:
            if self._point_in_polygon(world_x, world_z, base['flatten_zone']):
                return base['flatten_height']
        
        # Not in any deformation zone - return natural terrain height
        uv_x = world_x / self.total_map_size_meters
        uv_z = world_z / self.total_map_size_meters
        r_val = self._get_pixel_value(self.heightmap_data_r, uv_x, uv_z)
        height_m = (r_val * (self.max_height - self.min_height)) + self.min_height
        # Apply optional post scale/offset (for calibration on maps with unknown ranges)
        height_m = (height_m * getattr(self, 'height_post_scale', 1.0)) + getattr(self, 'height_post_offset', 0.0)
        return max(0.0, height_m)
    
    def _point_in_polygon(self, x, z, polygon):
        """
        Ray casting algorithm to determine if a point is inside a polygon.
        
        Args:
            x: X coordinate of point
            z: Z coordinate of point
            polygon: List of [x, z] vertex pairs defining the polygon
        
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
        
    def get_terrain_normal(self, world_x, world_z, delta=1.0):
        h0 = self.get_terrain_height(world_x, world_z)
        hx = self.get_terrain_height(world_x + delta, world_z)
        hz = self.get_terrain_height(world_x, world_z + delta)
        vx = np.array([delta, hx - h0, 0])
        vz = np.array([0, hz - h0, delta])
        normal = np.cross(vz, vx)
        norm_mag = np.linalg.norm(normal)
        return normal / norm_mag if norm_mag > 0 else np.array([0, 1, 0])

    def get_asset_placement(self, world_x, world_z, yaw_degrees):
        h = self.get_terrain_height(world_x, world_z)
        n = self.get_terrain_normal(world_x, world_z)
        r = normal_to_euler_angles(n, yaw_degrees)
        return {'position': (world_x, h, world_z), 'rotation': r}

    def is_on_road(self, world_x, world_z, tolerance=10.0):
        """Checks if a world coordinate is on any known road segment."""
        point_2d = np.array([world_x, world_z])
        for start_3d, end_3d in self.road_segments:
            p1 = np.array([start_3d[0], start_3d[2]])
            p2 = np.array([end_3d[0], end_3d[2]])
            
            line_vec = p2 - p1
            point_vec = point_2d - p1
            line_len_sq = np.dot(line_vec, line_vec)
            if line_len_sq == 0.0:
                continue

            t = np.dot(point_vec, line_vec) / line_len_sq
            t = np.clip(t, 0, 1)
            
            closest_point = p1 + t * line_vec
            dist_sq = np.sum((point_2d - closest_point)**2)

            if dist_sq < tolerance**2:
                return True
        return False

    def get_smart_placement(self, world_x, world_z, yaw_degrees):
        """
        Determines placement on terrain, road, static prefab roof, or city block roof.
        """
        # --- 1. Check for Static Prefabs ---
        highest_spawnable_static_y = -float('inf')
        best_static_surface_name = "Static Prefab"
        for surface in self.static_surfaces:
            bounds = surface['world_bounds']
            if (bounds[0] <= world_x <= bounds[3]) and (bounds[2] <= world_z <= bounds[5]):
                if surface['is_spawnable'] and bounds[4] > highest_spawnable_static_y:
                    highest_spawnable_static_y = bounds[4]
                    best_static_surface_name = f"{surface['prefab_name']}/{surface['name']}"
        if highest_spawnable_static_y > -float('inf'):
            return {'type': 'static_prefab_roof', 'position': (world_x, highest_spawnable_static_y, world_z), 'rotation': (0.0, yaw_degrees, 0.0), 'snapped_to_building': best_static_surface_name}

        # --- 2. NEW: Check for Roads ---
        if self.is_on_road(world_x, world_z):
            height = self.get_terrain_height(world_x, world_z)
            return {'type': 'road', 'position': (world_x, height, world_z), 'rotation': (0.0, yaw_degrees, 0.0)}

        # --- 3. Check for City Blocks ---
        try: 
            px, py = self._world_to_pixel_vtstyle_global(world_x, world_z)
        except Exception: 
            px, py = -1, -1
        
        layout_info = None
        if px != -1:
            corner_x, corner_z = self._pixel_to_world_vtstyle(px, py)
            layout_info = self.get_city_layout_at(corner_x, corner_z)
        
        if layout_info:
            meters_per_pixel = self.chunk_size_meters / 20.0
            center_offset = meters_per_pixel / 2.0
            center_x, center_z = corner_x + center_offset, corner_z + center_offset
            final_center_x, final_center_z = center_x + MANUAL_OFFSET_X, center_z + MANUAL_OFFSET_Z
            
            # Sample ground height at the queried point (world_x, world_z) for better roof placement
            # This better mimics VTOL's per-vertex mesh conform and reduces slope-induced errors
            block_base_y = self.get_terrain_height(world_x, world_z)
            block_pos = np.array([final_center_x, block_base_y, final_center_z])
            block_rot = R.from_euler('y', layout_info['block_yaw_degrees'], degrees=True).as_matrix()

            highest_spawnable_city_y = -float('inf')
            best_city_surface_name = "City Block"
            for s in layout_info['surfaces']:
                b = s.get('bounds_rel_layout', [])
                if len(b) != 6:
                    continue
                min_r, max_r = np.array([b[0],b[2],b[4]]), np.array([b[1],b[3],b[5]])
                corners_r = [np.array([dx,dy,dz]) for dx in [min_r[0],max_r[0]] for dy in [min_r[1],max_r[1]] for dz in [min_r[2],max_r[2]]]
                corners_a = [block_rot.dot(c) + block_pos for c in corners_r] # corners_a are now in final, offset world space
                min_a, max_a = np.min(corners_a, axis=0), np.max(corners_a, axis=0)

                # --- MODIFICATION ---
                # Check against the final absolute bounds (min_a, max_a) directly.
                # Do NOT subtract the offset again.
                if (min_a[0] <= world_x <= max_a[0]) and \
                   (min_a[2] <= world_z <= max_a[2]):
                # --- END MODIFICATION ---
                    if s.get('is_spawnable', False) and max_a[1] > highest_spawnable_city_y:
                        highest_spawnable_city_y = max_a[1]
                        best_city_surface_name = s.get('go_name', 'N/A')
            
            if highest_spawnable_city_y > -float('inf'):
                return {'type': 'city_roof', 'position': (world_x, highest_spawnable_city_y, world_z), 'rotation': (0.0, yaw_degrees, 0.0), 'snapped_to_building': best_city_surface_name}

        # --- 4. Default to Terrain ---
        return {**self.get_asset_placement(world_x, world_z, yaw_degrees), 'type': 'terrain'}

    # --- Renamed from public to private ---
    def _generate_all_city_blocks(self):
        """Generates data for all city blocks based on the heightmap G channel."""
        all_blocks = []
        width = self.hm_width
        height = self.hm_height
        city_pixel_channel = self.heightmap_data_g
        meters_per_pixel = self.chunk_size_meters / 20.0
        center_offset = meters_per_pixel / 2.0

        for py in range(height - 1):
            for px in range(width - 1):
                try:
                    g1 = city_pixel_channel[py, px]
                    g2 = city_pixel_channel[py, px + 1]
                    g3 = city_pixel_channel[py + 1, px + 1]
                    g4 = city_pixel_channel[py + 1, px]
                except IndexError:
                    continue

                if g1 > 0.1 and g2 > 0.1 and g3 > 0.1 and g4 > 0.1:
                    corner_x, corner_z = self._pixel_to_world_vtstyle(px, py)
                    center_x = corner_x + center_offset
                    center_z = corner_z + center_offset
                    layout_info = self.get_city_layout_at(corner_x, corner_z)
                    if layout_info:
                        final_x = center_x + MANUAL_OFFSET_X
                        final_z = center_z + MANUAL_OFFSET_Z
                        # Sample at final (offset) block center for consistent Y
                        block_base_y = self.get_terrain_height(final_x, final_z)
                        block_position = (float(final_x), float(block_base_y), float(final_z))
                        block_yaw = float(layout_info['block_yaw_degrees'])
                        city_level = int(layout_info['city_level'])
                        layout_guid = layout_info['layout_guid']
                        all_blocks.append({
                            'pixel_coord': (px, py),
                            'world_position': block_position,
                            'layout_guid': layout_guid,
                            'yaw_degrees': block_yaw,
                            'city_level': city_level,
                        })
        return all_blocks
    
    # --- Public-facing wrappers for pre-processed data ---
    def get_all_city_blocks(self): return self.city_blocks
    def get_all_static_prefabs(self):
        """Returns a formatted list of all static prefabs placed on the map."""
        static_prefabs_node = self.map_data.get('StaticPrefabs', {}).get('StaticPrefab', [])
        if not isinstance(static_prefabs_node, list):
            static_prefabs_node = [static_prefabs_node] if static_prefabs_node else []
        return [
            {
                'prefab_id': p.get('prefab'),
                'position': [float(c) for c in p.get('globalPos', [0, 0, 0])],
                'rotation_euler': [float(r) for r in p.get('rotation', [0, 0, 0])],
            }
            for p in static_prefabs_node
        ]
    
    def get_all_bases(self):
        """
        Returns a list of all bases (airbases, carriers, FOBs) on the map.
        
        Returns:
            list: List of base dictionaries with keys: id, name, prefab_type, position, rotation, footprint
        """
        return self.bases.copy()
    
    def get_base_by_id(self, base_id):
        """
        Finds a base by its ID.
        
        Args:
            base_id: The base's ID from the VTM file
        
        Returns:
            dict: Base information dictionary, or None if not found
        """
        for base in self.bases:
            if base['id'] == base_id:
                return base.copy()
        return None
    
    def get_base_by_name(self, name):
        """
        Finds a base by its name (case-insensitive partial match).
        
        Args:
            name: The base name to search for
        
        Returns:
            dict: Base information dictionary, or None if not found
        """
        name_lower = name.lower()
        for base in self.bases:
            if name_lower in base['name'].lower():
                return base.copy()
        return None
    
    def get_nearest_base(self, world_x, world_z):
        """
        Finds the nearest base to a given world coordinate.
        
        Args:
            world_x: X coordinate
            world_z: Z coordinate
        
        Returns:
            tuple: (base_dict, distance) or (None, None) if no bases exist
        """
        if not self.bases:
            return None, None
        
        point = np.array([world_x, world_z])
        nearest_base = None
        min_distance = float('inf')
        
        for base in self.bases:
            base_pos = np.array([base['position'][0], base['position'][2]])
            distance = np.linalg.norm(point - base_pos)
            if distance < min_distance:
                min_distance = distance
                nearest_base = base
        
        return nearest_base.copy(), float(min_distance)
    
    # Unchanged public methods
    def get_city_density(self, world_x, world_z):
        try:
            px, py = self._world_to_pixel_vtstyle_global(world_x, world_z)
        except Exception:
            px, py = self._world_to_pixel_bankers_rounding(world_x, world_z)

        if px < 0 or py < 0 or px >= self.hm_width - 1 or py >= self.hm_height - 1:
            return 0.0

        try:
            g1 = self.heightmap_data_g[py, px]
            g2 = self.heightmap_data_g[py, px + 1]
            g3 = self.heightmap_data_g[py + 1, px + 1]
            g4 = self.heightmap_data_g[py + 1, px]
            return g1 if (g1 > 0.1 and g2 > 0.1 and g3 > 0.1 and g4 > 0.1) else 0.0
        except IndexError:
            return 0.0
    def get_city_layout_at(self, world_x, world_z):
        density = self.get_city_density(world_x, world_z)
        if density <= 0.1:
            return None

        try:
            px, py = self._world_to_pixel_vtstyle_global(world_x, world_z)
        except Exception:
            px, py = self._world_to_pixel_bankers_rounding(world_x, world_z)

        city_level = np.clip(int(np.floor((density - 0.2) / 0.8 * 5.0)), 0, 4)
        level_key = str(city_level)
        available_layouts = self.layouts_by_level.get(level_key)
        if not available_layouts:
            return None

        noise_px = px % self.noise_width
        noise_py = py % self.noise_height
        try:
            noise_val_r = self.noise_texture_data[noise_py, noise_px]
        except IndexError:
            return None

        layout_index = np.clip(
            int(np.floor(noise_val_r * float(len(available_layouts)))),
            0,
            len(available_layouts) - 1,
        )
        layout_guid = available_layouts[layout_index]
        layout_surfaces = self.layout_data_db.get(layout_guid)
        if layout_surfaces is None:
            return None

        block_yaw = 0.0
        if px % 2 == 0:
            if py % 2 != 0:
                block_yaw = 90.0
        elif py % 2 == 0:
            block_yaw = -90.0
        else:
            block_yaw = 180.0

        return {
            'layout_guid': layout_guid,
            'surfaces': layout_surfaces,
            'block_yaw_degrees': block_yaw,
            'city_level': city_level,
            'pixel_coords': (px, py),
        }

# --- Main Execution Block (Example Usage & Test) ---
if __name__ == "__main__":
    MAP_FOLDER = r"test_map/hMap2"
    LAYOUT_DB_PATH = 'Resources/city_layouts_database.json'
    INDIVIDUAL_DB_PATH = 'Resources/individual_prefabs_database.json'
    OUTPUT_CITY_JSON = 'generated_city_blocks.json'
    OUTPUT_STATIC_JSON = 'generated_static_prefabs.json'

    try:
        # Update constructor to include the new database path
        calculator = TerrainCalculator(MAP_FOLDER, LAYOUT_DB_PATH, INDIVIDUAL_DB_PATH)

        # --- Generate and save all city blocks ---
        print("\nGetting pre-processed city block data...")
        generated_blocks_data = calculator.get_all_city_blocks()
        with open(OUTPUT_CITY_JSON, 'w') as f:
            json.dump(generated_blocks_data, f, indent=2)
        print(f"Saved data for {len(generated_blocks_data)} city blocks to '{OUTPUT_CITY_JSON}'")
        
        # --- Generate and save all static prefabs ---
        print("\nGetting pre-processed static prefab data...")
        generated_static_data = calculator.get_all_static_prefabs()
        with open(OUTPUT_STATIC_JSON, 'w') as f:
            json.dump(generated_static_data, f, indent=2)
        print(f"Saved data for {len(generated_static_data)} static prefabs to '{OUTPUT_STATIC_JSON}'")

        # --- Test get_smart_placement on various locations ---
        if generated_static_data:
            print("\n--- Testing get_smart_placement ---")
            
            # Test 1: On a known static prefab
            first_static = generated_static_data[0]
            test_pos = first_static['position']
            test_x, test_z = test_pos[0], test_pos[2]
            print(f"\nQuerying at static prefab location: ({test_x:.2f}, {test_z:.2f})")
            placement = calculator.get_smart_placement(test_x, test_z, 0)
            print(f" -> Result Type: {placement.get('type')}")
            if placement.get('type') == 'static_prefab_roof':
                print("    SUCCESS! Correctly detected a static prefab roof.")
            else:
                print(f"   WARNING! Expected 'static_prefab_roof', but got '{placement.get('type')}'.")
            
            # Test 2: On a known road
            road_test_x, road_test_z = 53750.0, 118750.0
            print(f"\nQuerying at road location: ({road_test_x:.2f}, {road_test_z:.2f})")
            placement = calculator.get_smart_placement(road_test_x, road_test_z, 0)
            print(f" -> Result Type: {placement.get('type')}")
            if placement.get('type') == 'road':
                print("    SUCCESS! Correctly detected a road.")
            else:
                print(f"   WARNING! Expected 'road', but got '{placement.get('type')}'.")

    except FileNotFoundError as e:
        print(f"\nFile Error: {e}")
    except ValueError as e:
        print(f"\nValue Error: {e}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        traceback.print_exc()


