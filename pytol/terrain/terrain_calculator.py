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

# --- MANUAL FINE-TUNING OFFSET (in meters) ---
MANUAL_OFFSET_X = 10
MANUAL_OFFSET_Z = -10


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

    def __init__(self, map_name: str = '', map_directory_path: str = '', vtol_directory: str = ''):
        """Initializes the TerrainCalculator by loading all necessary data."""

        
        if map_directory_path:
            self.map_dir = map_directory_path
            self.map_name = os.path.basename(os.path.normpath(map_directory_path))
        elif map_name and vtol_directory:
            self.map_dir = os.path.join(os.path.normpath(vtol_directory), 'CustomMaps', map_name)
        elif map_name and os.getenv('VTOL_VR_DIR'):
            self.map_dir = os.path.join(os.path.normpath(os.getenv('VTOL_VR_DIR')), 'CustomMaps', map_name)
        else:
            raise ValueError("Either 'map_directory_path' or both 'map_name' and 'vtol_directory' must be provided.")
        
        print(f"Initializing TerrainCalculator for: {self.map_dir}")

        # --- Load Data ---
        self._load_vtm_file(self.map_dir)
        self._load_textures()
        self._load_databases()

        # --- Calibrate and Pre-process ---
        self.coord_transform_mode = None
        self._discover_coordinate_transform()
        
        # Pre-process all static and procedural objects on initialization
        self.city_blocks = self._generate_all_city_blocks()
        self.static_surfaces = self._process_static_prefabs()
        self.road_segments = self._process_all_roads() # New
        
        print(f"Map Size: {self.total_map_size_meters/1000.0:.1f} km ({self.map_size_grids} grids)")
        print(f"Altitude Range: {self.min_height}m to {self.max_height}m")
        print(f"Processed {len(self.city_blocks)} city blocks.")
        print(f"Processed {len(self.static_surfaces)} static surfaces.")
        print(f"Processed {len(self.road_segments)} total road segments.")
        print(f"Using Coordinate Transform Mode = {self.coord_transform_mode}")

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
        self.max_height = float(self.map_data.get('hm_maxHeight', 6000.0))
        self.min_height = float(self.map_data.get('hm_minHeight', -80.0))

    def _load_textures(self):
        heightmap_path = os.path.join(self.map_dir, 'height.png')
        try:
            with Image.open(heightmap_path) as image:
                image = image.convert('RGB')
                np_image = np.array(image)
                self.heightmap_data_r = np.flipud(np_image[:, :, 0].astype(np.float32) / 255.0)
                self.heightmap_data_g = np.flipud(np_image[:, :, 1].astype(np.float32) / 255.0)
            self.hm_height, self.hm_width = self.heightmap_data_r.shape

            noise_img = get_noise_image()
            self.noise_texture_data = np.flipud(np.array(noise_img.convert('L'))).astype(np.float32) / 255.0
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
                print(f"Warning: Could not process static prefab '{prefab_name}'. Invalid data: {e}")
        return processed_surfaces

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
                    for i in range(len(points) - 1):
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
        try:
            prefabs_node=self.map_data.get('StaticPrefabs',{}).get('StaticPrefab',[]);
            if not isinstance(prefabs_node,list):prefabs_node=[prefabs_node] if prefabs_node else[]
            if not prefabs_node:raise ValueError("No static prefabs found for calibration.")
            prefab_0=prefabs_node[0];
            if'globalPos'not in prefab_0:raise ValueError("First static prefab lacks 'globalPos'.")
            global_pos=prefab_0['globalPos'];
            if not isinstance(global_pos,(list,tuple))or len(global_pos)!=3:raise ValueError("Invalid 'globalPos' format.")
            world_x,expected_y,world_z=map(float,global_pos);expected_r=(expected_y-self.min_height)/(self.max_height-self.min_height);uv_x=world_x/self.total_map_size_meters;uv_z=world_z/self.total_map_size_meters;best_mode=-1;min_diff=float('inf')
            for mode in range(8):
                found_r=self._get_pixel_value(self.heightmap_data_r,uv_x,uv_z,mode);diff=abs(found_r-expected_r)
                if np.isclose(found_r,expected_r,atol=0.001):self.coord_transform_mode=mode;return
                if diff<min_diff:min_diff=diff;best_mode=mode
            if best_mode!=-1:self.coord_transform_mode=best_mode
            else:raise Exception("Calibration failed - no suitable mode found.")
        except Exception as e:print(f"Warning: Calibration failed ({e}). Falling back to mode 4.");self.coord_transform_mode=4
    def _world_to_pixel_bankers_rounding(self,world_x,world_z):
        uv_x=Decimal(str(world_x))/Decimal(str(self.total_map_size_meters));uv_z=Decimal(str(world_z))/Decimal(str(self.total_map_size_meters));pixel_x_f,pixel_y_f=Decimal(0),Decimal(0);map_width_minus_1=Decimal(self.hm_width-1);map_height_minus_1=Decimal(self.hm_height-1);mode=self.coord_transform_mode;u,v=uv_x,uv_z;
        if mode==0:pixel_x_f,pixel_y_f=u*map_width_minus_1,v*map_height_minus_1
        elif mode==1:pixel_x_f,pixel_y_f=v*map_width_minus_1,u*map_height_minus_1
        elif mode==2:pixel_x_f,pixel_y_f=(Decimal(1)-u)*map_width_minus_1,v*map_height_minus_1
        elif mode==3:pixel_x_f,pixel_y_f=v*map_width_minus_1,(Decimal(1)-u)*map_height_minus_1
        elif mode==4:pixel_x_f,pixel_y_f=u*map_width_minus_1,(Decimal(1)-v)*map_height_minus_1
        elif mode==5:pixel_x_f,pixel_y_f=(Decimal(1)-v)*map_width_minus_1,u*map_height_minus_1
        elif mode==6:pixel_x_f,pixel_y_f=(Decimal(1)-u)*map_width_minus_1,(Decimal(1)-v)*map_height_minus_1
        elif mode==7:pixel_x_f,pixel_y_f=(Decimal(1)-v)*map_width_minus_1,(Decimal(1)-u)*map_height_minus_1
        pixel_x=int(pixel_x_f.quantize(Decimal('1'),rounding=ROUND_HALF_EVEN));pixel_y=int(pixel_y_f.quantize(Decimal('1'),rounding=ROUND_HALF_EVEN));pixel_x=np.clip(pixel_x,0,self.hm_width-1);pixel_y=np.clip(pixel_y,0,self.hm_height-1);return pixel_x,pixel_y
    def _pixel_to_world_vtstyle(self,px,py):
        verts_per_side=20;chunk_size=float(self.chunk_size_meters);chunk_x=int(np.floor(px/verts_per_side));chunk_y=int(np.floor(py/verts_per_side));px_local=px-(chunk_x*verts_per_side);py_local=py-(chunk_y*verts_per_side);meters_per_pixel=chunk_size/float(verts_per_side);local_x=float(px_local)*meters_per_pixel;local_z=float(py_local)*meters_per_pixel;world_x=(chunk_x*chunk_size)+local_x;world_z=(chunk_y*chunk_size)+local_z;return world_x,world_z
    def _world_to_pixel_vtstyle_global(self,world_x,world_z):
        verts_per_side=20;chunk_size_d=Decimal(str(self.chunk_size_meters));meters_per_pixel_d=chunk_size_d/Decimal(verts_per_side);
        if meters_per_pixel_d==0:meters_per_pixel_d=Decimal(1.0)
        world_x_d=Decimal(str(world_x));world_z_d=Decimal(str(world_z));chunk_x=int((world_x_d/chunk_size_d).to_integral_value(rounding=ROUND_FLOOR));chunk_y=int((world_z_d/chunk_size_d).to_integral_value(rounding=ROUND_FLOOR));local_x_d=world_x_d-(Decimal(chunk_x)*chunk_size_d);local_z_d=world_z_d-(Decimal(chunk_y)*chunk_size_d);px_local_d=(local_x_d/meters_per_pixel_d).to_integral_value(rounding=ROUND_FLOOR);py_local_d=(local_z_d/meters_per_pixel_d).to_integral_value(rounding=ROUND_FLOOR);px_global=chunk_x*verts_per_side+int(px_local_d);py_global=chunk_y*verts_per_side+int(py_local_d);return int(px_global),int(py_global)
    def _get_pixel_value(self,data_channel,u,v,mode=None):
        if mode is None:mode=self.coord_transform_mode
        pixel_x_f,pixel_y_f=0.0,0.0;map_width_minus_1=float(self.hm_width-1);map_height_minus_1=float(self.hm_height-1);u_f,v_f=float(u),float(v)
        if mode==0:pixel_x_f,pixel_y_f=u_f*map_width_minus_1,v_f*map_height_minus_1
        elif mode==1:pixel_x_f,pixel_y_f=v_f*map_width_minus_1,u_f*map_height_minus_1
        elif mode==2:pixel_x_f,pixel_y_f=(1.0-u_f)*map_width_minus_1,v_f*map_height_minus_1
        elif mode==3:pixel_x_f,pixel_y_f=v_f*map_width_minus_1,(1.0-u_f)*map_height_minus_1
        elif mode==4:pixel_x_f,pixel_y_f=u_f*map_width_minus_1,(1.0-v_f)*map_height_minus_1
        elif mode==5:pixel_x_f,pixel_y_f=(1.0-v_f)*map_width_minus_1,u_f*map_height_minus_1
        elif mode==6:pixel_x_f,pixel_y_f=(1.0-u_f)*map_width_minus_1,(1.0-v_f)*map_height_minus_1
        elif mode==7:pixel_x_f,pixel_y_f=(1.0-v_f)*map_width_minus_1,(1.0-u_f)*map_height_minus_1
        try:pixel_y_f_clamped=np.clip(pixel_y_f,0.0,float(self.hm_height-1));pixel_x_f_clamped=np.clip(pixel_x_f,0.0,float(self.hm_width-1));return map_coordinates(data_channel,[[pixel_y_f_clamped],[pixel_x_f_clamped]],order=1,mode='nearest')[0]
        except Exception:px_int=np.clip(int(round(pixel_x_f)),0,self.hm_width-1);py_int=np.clip(int(round(pixel_y_f)),0,self.hm_height-1);return data_channel[py_int,px_int]
    
    # --- Public Methods ---
    def get_terrain_height(self, world_x, world_z):
        if self.coord_transform_mode is None: raise Exception("Not calibrated.")
        uv_x = world_x / self.total_map_size_meters; uv_z = world_z / self.total_map_size_meters
        r_val = self._get_pixel_value(self.heightmap_data_r, uv_x, uv_z)
        return max(0.0, (r_val * (self.max_height - self.min_height)) + self.min_height)
        
    def get_terrain_normal(self, world_x, world_z, delta=1.0):
        h0=self.get_terrain_height(world_x,world_z);hx=self.get_terrain_height(world_x+delta,world_z);hz=self.get_terrain_height(world_x,world_z+delta);vx=np.array([delta,hx-h0,0]);vz=np.array([0,hz-h0,delta]);normal=np.cross(vz,vx);norm_mag=np.linalg.norm(normal);return normal/norm_mag if norm_mag>0 else np.array([0,1,0])

    def get_asset_placement(self, world_x, world_z, yaw_degrees):
        h=self.get_terrain_height(world_x,world_z);n=self.get_terrain_normal(world_x,world_z);r=normal_to_euler_angles(n,yaw_degrees);return{'position':(world_x,h,world_z),'rotation':r}

    def is_on_road(self, world_x, world_z, tolerance=10.0):
        """Checks if a world coordinate is on any known road segment."""
        point_2d = np.array([world_x, world_z])
        for start_3d, end_3d in self.road_segments:
            p1 = np.array([start_3d[0], start_3d[2]])
            p2 = np.array([end_3d[0], end_3d[2]])
            
            line_vec = p2 - p1
            point_vec = point_2d - p1
            line_len_sq = np.dot(line_vec, line_vec)
            if line_len_sq == 0.0: continue

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
        highest_spawnable_static_y = -float('inf'); best_static_surface_name = "Static Prefab"
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
            meters_per_pixel = self.chunk_size_meters / 20.0; center_offset = meters_per_pixel / 2.0
            center_x, center_z = corner_x + center_offset, corner_z + center_offset
            final_center_x, final_center_z = center_x + MANUAL_OFFSET_X, center_z + MANUAL_OFFSET_Z
            block_base_y = self.get_terrain_height(center_x, center_z)
            block_pos = np.array([final_center_x, block_base_y, final_center_z]) # This position includes the offset
            block_rot = R.from_euler('y', layout_info['block_yaw_degrees'], degrees=True).as_matrix()

            highest_spawnable_city_y = -float('inf'); best_city_surface_name = "City Block"
            for s in layout_info['surfaces']:
                b = s.get('bounds_rel_layout',[]);
                if len(b)!=6: continue
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
        all_blocks=[];width=self.hm_width;height=self.hm_height;city_pixel_channel=self.heightmap_data_g;meters_per_pixel=self.chunk_size_meters/20.0;center_offset=meters_per_pixel/2.0
        for py in range(height-1):
            for px in range(width-1):
                try:g1=city_pixel_channel[py,px];g2=city_pixel_channel[py,px+1];g3=city_pixel_channel[py+1,px+1];g4=city_pixel_channel[py+1,px]
                except IndexError:continue
                if g1>0.1 and g2>0.1 and g3>0.1 and g4>0.1:
                    corner_x,corner_z=self._pixel_to_world_vtstyle(px,py);center_x=corner_x+center_offset;center_z=corner_z+center_offset;layout_info=self.get_city_layout_at(corner_x,corner_z)
                    if layout_info:
                        block_base_y=self.get_terrain_height(center_x,center_z);final_x=center_x+MANUAL_OFFSET_X;final_z=center_z+MANUAL_OFFSET_Z;block_position=(float(final_x),float(block_base_y),float(final_z));block_yaw=float(layout_info['block_yaw_degrees']);city_level=int(layout_info['city_level']);all_blocks.append({'pixel_coord':(px,py),'world_position':block_position,'layout_guid':layout_info['layout_guid'],'yaw_degrees':block_yaw,'city_level':city_level})
        return all_blocks
    
    # --- Public-facing wrappers for pre-processed data ---
    def get_all_city_blocks(self): return self.city_blocks
    def get_all_static_prefabs(self):
        """Returns a formatted list of all static prefabs placed on the map."""
        static_prefabs_node = self.map_data.get('StaticPrefabs', {}).get('StaticPrefab', [])
        if not isinstance(static_prefabs_node, list): static_prefabs_node = [static_prefabs_node] if static_prefabs_node else []
        return [{'prefab_id': p.get('prefab'), 'position': [float(c) for c in p.get('globalPos', [0,0,0])], 'rotation_euler': [float(r) for r in p.get('rotation', [0,0,0])]} for p in static_prefabs_node]
    
    # Unchanged public methods
    def get_city_density(self, world_x, world_z):
        try:px,py=self._world_to_pixel_vtstyle_global(world_x,world_z)
        except Exception:px,py=self._world_to_pixel_bankers_rounding(world_x,world_z)
        if px<0 or py<0 or px>=self.hm_width-1 or py>=self.hm_height-1:return 0.0
        try:g1=self.heightmap_data_g[py,px];g2=self.heightmap_data_g[py,px+1];g3=self.heightmap_data_g[py+1,px+1];g4=self.heightmap_data_g[py+1,px];return g1 if g1>0.1 and g2>0.1 and g3>0.1 and g4>0.1 else 0.0
        except IndexError:return 0.0
    def get_city_layout_at(self, world_x, world_z):
        density=self.get_city_density(world_x,world_z);
        if density<=0.1:return None
        try:px,py=self._world_to_pixel_vtstyle_global(world_x,world_z)
        except Exception:px,py=self._world_to_pixel_bankers_rounding(world_x,world_z)
        city_level=np.clip(int(np.floor((density-0.2)/0.8*5.0)),0,4);level_key=str(city_level);available_layouts=self.layouts_by_level.get(level_key)
        if not available_layouts:return None
        noise_px=px%self.noise_width;noise_py=py%self.noise_height
        try:noise_val_r=self.noise_texture_data[noise_py,noise_px]
        except IndexError:return None
        layout_index=np.clip(int(np.floor(noise_val_r*float(len(available_layouts)))),0,len(available_layouts)-1);layout_guid=available_layouts[layout_index];layout_surfaces=self.layout_data_db.get(layout_guid)
        if layout_surfaces is None:return None
        block_yaw=0.0
        if px%2==0:
            if py%2!=0:block_yaw=90.0
        elif py%2==0:block_yaw=-90.0
        else:block_yaw=180.0
        return{'layout_guid':layout_guid,'surfaces':layout_surfaces,'block_yaw_degrees':block_yaw,'city_level':city_level,'pixel_coords':(px,py)}

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
        with open(OUTPUT_CITY_JSON, 'w') as f: json.dump(generated_blocks_data, f, indent=2)
        print(f"Saved data for {len(generated_blocks_data)} city blocks to '{OUTPUT_CITY_JSON}'")
        
        # --- Generate and save all static prefabs ---
        print("\nGetting pre-processed static prefab data...")
        generated_static_data = calculator.get_all_static_prefabs()
        with open(OUTPUT_STATIC_JSON, 'w') as f: json.dump(generated_static_data, f, indent=2)
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

