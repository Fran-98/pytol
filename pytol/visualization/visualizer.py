"""
Core visualization classes for pytol terrain and missions.

This module provides interactive 3D visualization using PyVista.
"""

import numpy as np
from scipy.spatial.transform import Rotation as R
import pyvista as pv
import os
from typing import List, Tuple
from ..misc.logger import create_logger


class TerrainVisualizer:
    """
    Visualizes VTOL VR terrain with buildings, roads, and city blocks.
    
    Example:
        >>> from pytol.terrain import TerrainCalculator
        >>> from pytol.visualization import TerrainVisualizer
        >>> 
        >>> tc = TerrainCalculator("hMap2", map_path="path/to/hMap2")
        >>> viz = TerrainVisualizer(tc)
        >>> viz.show()
    """
    
    def __init__(self, terrain_calculator, mesh_resolution: int = 256, drape_roads: bool = True, verbose: bool = True):
        """
        Initialize terrain visualizer.
        
        Args:
            terrain_calculator: TerrainCalculator instance
            mesh_resolution: Resolution for terrain mesh (default: 256)
            drape_roads: Whether to drape roads on terrain surface (default: True)
            verbose: Whether to print progress messages (default: True)
        """
        self.calculator = terrain_calculator
        self.mesh_resolution = mesh_resolution
        self.drape_roads = drape_roads
        self.verbose = verbose
        self.plotter = None
        self.logger = create_logger(verbose=verbose, name="Visualizer")
        
        # Pre-process data
        self._generate_terrain_mesh()
        self._generate_building_meshes()
        self._generate_road_meshes()
    
    def _log(self, message: str):
        """Route messages through centralized logger."""
        self.logger.info(str(message))
        
    def _generate_terrain_mesh(self):
        """Generate the base terrain mesh from heightmap."""
        self._log(f"Generating {self.mesh_resolution}x{self.mesh_resolution} terrain mesh...")
        total_size = self.calculator.total_map_size_meters
        x_points = np.linspace(0, total_size, self.mesh_resolution)
        z_points = np.linspace(0, total_size, self.mesh_resolution)
        xx, zz = np.meshgrid(x_points, z_points)
        yy = np.array([[self.calculator.get_terrain_height(x, z) for x in x_points] for z in z_points])
        
        self.terrain_surface = pv.StructuredGrid(-xx, yy, zz).extract_surface()
        self.terrain_surface.point_data['Altitude'] = yy.ravel(order='C')
        self._log("Terrain mesh created.")
        
    def _generate_building_meshes(self):
        """Generate meshes for city blocks and static prefabs."""
        self._log("Generating building and prefab meshes...")
        spawnable_meshes, obstacle_meshes = [], []
        
        # City Blocks
        city_blocks = self.calculator.get_all_city_blocks()
        for block_data in city_blocks:
            layout_guid = block_data['layout_guid']
            block_pos = np.array(block_data['world_position'])
            block_yaw = block_data['yaw_degrees']
            layout_surfaces = self.calculator.layout_data_db.get(layout_guid, [])
            block_rot_matrix = R.from_euler('y', block_yaw, degrees=True).as_matrix()
            
            for surface in layout_surfaces:
                bounds_rel = np.array(surface.get('bounds_rel_layout', []))
                if bounds_rel.shape != (6,):
                    continue
                min_rel = np.array([bounds_rel[0], bounds_rel[2], bounds_rel[4]])
                max_rel = np.array([bounds_rel[1], bounds_rel[3], bounds_rel[5]])
                corners_rel = [np.array([dx, dy, dz]) 
                             for dx in [min_rel[0], max_rel[0]] 
                             for dy in [min_rel[1], max_rel[1]] 
                             for dz in [min_rel[2], max_rel[2]]]
                corners_abs = [block_rot_matrix.dot(c) + block_pos for c in corners_rel]
                min_abs, max_abs = np.min(corners_abs, axis=0), np.max(corners_abs, axis=0)
                box = pv.Box(bounds=[-max_abs[0], -min_abs[0], min_abs[1], max_abs[1], min_abs[2], max_abs[2]])
                (spawnable_meshes if surface.get('is_spawnable') else obstacle_meshes).append(box)
        
        # Static Prefabs
        static_prefabs = self.calculator.get_all_static_prefabs()
        prefab_name_to_key = {os.path.splitext(os.path.basename(k))[0]: k 
                             for k in self.calculator.individual_prefabs_db.keys()}
        
        for prefab_data in static_prefabs:
            db_key = prefab_name_to_key.get(prefab_data['prefab_id'])
            if not db_key:
                continue
            prefab_surfaces = self.calculator.individual_prefabs_db.get(db_key, [])
            pos = np.array(prefab_data['position'])
            rot = prefab_data['rotation_euler']
            prefab_rot_matrix = R.from_euler('yxz', [rot[1], rot[0], rot[2]], degrees=True).as_matrix()
            
            for surface in prefab_surfaces:
                bounds_rel = np.array(surface.get('bounds', []))
                if bounds_rel.shape != (6,):
                    continue
                min_rel = np.array([bounds_rel[0], bounds_rel[2], bounds_rel[4]])
                max_rel = np.array([bounds_rel[1], bounds_rel[3], bounds_rel[5]])
                corners_rel = [np.array([dx, dy, dz]) 
                             for dx in [min_rel[0], max_rel[0]] 
                             for dy in [min_rel[1], max_rel[1]] 
                             for dz in [min_rel[2], max_rel[2]]]
                corners_abs = [prefab_rot_matrix.dot(c) + pos for c in corners_rel]
                min_abs, max_abs = np.min(corners_abs, axis=0), np.max(corners_abs, axis=0)
                box = pv.Box(bounds=[-max_abs[0], -min_abs[0], min_abs[1], max_abs[1], min_abs[2], max_abs[2]])
                (spawnable_meshes if surface.get('is_spawnable') else obstacle_meshes).append(box)
        
        self.spawnable_combined = pv.MultiBlock(spawnable_meshes).combine(merge_points=False) if spawnable_meshes else None
        self.obstacle_combined = pv.MultiBlock(obstacle_meshes).combine(merge_points=False) if obstacle_meshes else None
        self._log(f"Rendered {len(spawnable_meshes) + len(obstacle_meshes)} building/prefab surfaces.")
        
    def _generate_road_meshes(self):
        """Generate road network meshes."""
        self._log("Generating road network meshes...")
        road_meshes = []
        
        for seg in self.calculator.road_segments:
            # road_segments is a list of tuples: (start_3d, end_3d)
            start_point = np.array(seg[0])
            end_point = np.array(seg[1])
            points = np.vstack([start_point, end_point])
            
            if self.drape_roads:
                points[0, 1] = self.calculator.get_terrain_height(points[0, 0], points[0, 2]) + 0.5
                points[1, 1] = self.calculator.get_terrain_height(points[1, 0], points[1, 2]) + 0.5
            
            points[:, 0] *= -1  # Invert X-axis for visualization
            
            road_meshes.append(pv.lines_from_points(points))
        
        self.roads_combined = pv.MultiBlock(road_meshes).combine(merge_points=False) if road_meshes else None
        self.bridges_combined = None  # Bridges not distinguished in current format
        self._log(f"Rendered {len(road_meshes)} road segments.")
        
    def show(self, window_size: Tuple[int, int] = (1600, 900)):
        """
        Display the terrain visualization.
        
        Args:
            window_size: Window size as (width, height) tuple
        """
        self.plotter = pv.Plotter(window_size=window_size)
        
        # Add terrain
        self.plotter.add_mesh(self.terrain_surface, cmap='terrain', 
                            scalar_bar_args={'title': 'Altitude (m)'})
        
        # Add buildings
        if self.spawnable_combined:
            self.plotter.add_mesh(self.spawnable_combined, color='#2ecc71', 
                                ambient=0.2, label='Spawnable')
        if self.obstacle_combined:
            self.plotter.add_mesh(self.obstacle_combined, color='#c0392b', 
                                ambient=0.2, label='Obstacle')
        
        # Add roads
        if self.roads_combined:
            self.plotter.add_mesh(self.roads_combined, color='#34495e', 
                                line_width=4, label='Roads')
        
        # Setup camera
        map_center = self.calculator.total_map_size_meters / 2
        focal_point = [-map_center, 
                      self.calculator.get_terrain_height(map_center, map_center), 
                      map_center]
        self.plotter.camera.position = [focal_point[0] + 5000, focal_point[1] + 2000, focal_point[2] + 5000]
        self.plotter.camera.focal_point = focal_point
        self.plotter.camera.zoom(1.5)
        
        self.plotter.enable_terrain_style()
        self.plotter.add_legend()
        self.plotter.add_axes()
        
        self._log("\nVisualization Controls:")
        self._log("  'q': Exit")
        self._log("  Mouse: Click and drag to rotate")
        self._log("  Scroll: Zoom in/out")
        
        self.plotter.show()


class MissionVisualizer(TerrainVisualizer):
    """
    Visualizes a complete VTOL VR mission with units, waypoints, and objectives.
    
    Example:
        >>> from pytol import Mission
        >>> from pytol.visualization import MissionVisualizer
        >>> 
        >>> mission = Mission(scenario_name="Test", scenario_id="test", 
        ...                   description="Test mission", map_id="hMap2")
        >>> # ... add units, objectives, etc ...
        >>> viz = MissionVisualizer(mission)
        >>> viz.show()
    """
    
    def __init__(self, mission, mesh_resolution: int = 256, drape_roads: bool = True, verbose: bool = True):
        """
        Initialize mission visualizer.
        
        Args:
            mission: Mission instance from pytol
            mesh_resolution: Resolution for terrain mesh (default: 256)
            drape_roads: Whether to drape roads on terrain surface (default: True)
            verbose: Whether to print progress messages (default: True)
        """
        self.mission = mission
        super().__init__(mission.tc, mesh_resolution, drape_roads, verbose)
        
    def _pv_pos(self, pos: Tuple[float, float, float]) -> List[float]:
        """Convert VTOL VR position to PyVista coordinates."""
        return [-pos[0], pos[1], pos[2]]
    
    def _add_labeled_point(self, pos: Tuple[float, float, float], label: str, 
                          color: str, always_visible: bool = True, point_size: int = 15):
        """Add a labeled point to the visualization."""
        return self.plotter.add_point_labels(
            self._pv_pos(pos), [label],
            point_size=point_size, point_color=color,
            font_size=16, shape_opacity=0.8,
            show_points=True,
            always_visible=always_visible,
            pickable=False
        )
    
    def _add_sphere(self, center: Tuple[float, float, float], radius: float, 
                    color: str, opacity: float = 0.3, wireframe: bool = False):
        """Add a sphere to the visualization (useful for triggers/zones)."""
        sphere = pv.Sphere(radius=radius, center=self._pv_pos(center))
        if wireframe:
            return self.plotter.add_mesh(sphere, color=color, opacity=opacity, 
                                        style='wireframe', line_width=2)
        else:
            return self.plotter.add_mesh(sphere, color=color, opacity=opacity)
    
    def _add_arrow(self, start: Tuple[float, float, float], direction: Tuple[float, float, float],
                   scale: float = 100.0, color: str = 'white'):
        """Add an arrow to show direction/orientation."""
        start_pv = np.array(self._pv_pos(start))
        # Direction in PyVista coordinates
        dir_pv = np.array([-direction[0], direction[1], direction[2]])
        dir_norm = dir_pv / (np.linalg.norm(dir_pv) + 1e-6)
        arrow = pv.Arrow(start=start_pv, direction=dir_norm, scale=scale)
        return self.plotter.add_mesh(arrow, color=color, opacity=0.7)
    
    def _add_path(self, points: List[Tuple[float, float, float]], 
                 color: str, width: int = 5):
        """Add a path/line through multiple points."""
        if not points or len(points) < 2:
            return None
        pv_points = np.array([self._pv_pos(p) for p in points])
        mesh = pv.lines_from_points(pv_points)
        return self.plotter.add_mesh(mesh, color=color, line_width=width, pickable=False)
    
    def _add_polygon(self, points_xz: List[Tuple[float, float]], color: str = '#8e44ad', opacity: float = 0.15, line_width: int = 2):
        """Add a filled polygon (at terrain height) given XZ points (world coords)."""
        if not points_xz:
            return None
        pts = []
        for (x, z) in points_xz:
            y = self.calculator.get_terrain_height(x, z)
            pts.append(self._pv_pos((x, y, z)))
        # Close the polygon
        if pts[0] != pts[-1]:
            pts.append(pts[0])
        # Outline
        outline = pv.lines_from_points(np.array(pts))
        actor1 = self.plotter.add_mesh(outline, color=color, line_width=line_width, opacity=0.8)
        # Triangulated fill (fan)
        center = np.mean(np.array(pts[:-1]), axis=0)
        tris = []
        for i in range(1, len(pts) - 2):
            tris.extend([3, 0, i, i+1])
        poly = pv.PolyData(np.vstack([center, *pts[:-1]]))
        poly.faces = np.array(tris)
        actor2 = self.plotter.add_mesh(poly, color=color, opacity=opacity)
        return (actor1, actor2)
    
    def show(self, window_size: Tuple[int, int] = (1600, 900)):
        """
        Display the mission visualization.
        
        Args:
            window_size: Window size as (width, height) tuple
        """
        # Create plotter
        self.plotter = pv.Plotter(window_size=window_size)
        
        # Add base terrain/buildings/roads
        self.plotter.add_mesh(self.terrain_surface, cmap='terrain', 
                            scalar_bar_args={'title': 'Altitude (m)'})
        if self.spawnable_combined:
            self.plotter.add_mesh(self.spawnable_combined, color='#2ecc71', 
                                ambient=0.2, label='Spawnable', opacity=0.3)
        if self.obstacle_combined:
            self.plotter.add_mesh(self.obstacle_combined, color='#c0392b', 
                                ambient=0.2, label='Obstacle', opacity=0.3)
        if self.roads_combined:
            self.plotter.add_mesh(self.roads_combined, color='#34495e', 
                                line_width=2, opacity=0.5)
        if self.bridges_combined:
            self.plotter.add_mesh(self.bridges_combined, color='#3498db', 
                                line_width=4, opacity=0.5)
        
        # Holders for toggles
        actors_units, actors_wpts, actors_objs, actors_trigs, actors_bases, actors_spawns, actors_paths = [], [], [], [], [], [], []

        # Add mission units
        self._log("Adding mission units to visualization...")
        unit_positions = []
        for unit_data in self.mission.units:
            unit_obj = unit_data['unit_obj']
            # Prefer the unit object's current global_position; fallback to lastValidPlacement
            pos = getattr(unit_obj, 'global_position', None) or unit_data.get('lastValidPlacement', None)
            if not pos:
                continue
            unit_positions.append(pos)
            unit_name = getattr(unit_obj, 'unit_name', None) or f"Unit {unit_data['unitInstanceID']}"
            
            # Color by team (defaults to gray)
            team = getattr(unit_obj, 'team', None) or getattr(unit_obj, 'unit_team', None)
            color = 'blue' if team == 'Allied' else ('red' if team == 'Enemy' else 'gray')
            
            actors_units.append(self._add_labeled_point(tuple(pos), unit_name, color, point_size=20))
            
            # Add orientation arrow for ground units
            rotation = getattr(unit_obj, 'rotation', None)
            if rotation and len(rotation) >= 2:
                yaw = rotation[1]  # Yaw in degrees
                yaw_rad = np.radians(yaw)
                direction = (np.sin(yaw_rad), 0, np.cos(yaw_rad))
                actors_units.append(self._add_arrow(tuple(pos), direction, scale=150.0, color=color))
        
        # Add waypoints
        self._log("Adding waypoints...")
        waypoint_positions = []
        for waypoint in self.mission.waypoints:
            gp = getattr(waypoint, 'global_point', None)
            if not gp or len(gp) != 3:
                continue
            pos = (gp[0], gp[1], gp[2])
            waypoint_positions.append(pos)
            name = waypoint.name if getattr(waypoint, 'name', None) else f"WP-{waypoint.id}"
            actors_wpts.append(self._add_labeled_point(pos, name, 'yellow', point_size=25))
        
        # Add objectives
        self._log("Adding objectives...")
        objective_positions = []
        for obj_idx, objective in enumerate(self.mission.objectives):
            # Try to find waypoint reference
            wpt_ref = getattr(objective, 'waypoint', None)
            obj_pos = None
            
            if wpt_ref is not None:
                # Could be Waypoint object or ID
                if hasattr(wpt_ref, 'global_point'):
                    obj_pos = tuple(wpt_ref.global_point)
                elif isinstance(wpt_ref, int):
                    # Find waypoint by ID
                    matching_wpt = next((w for w in self.mission.waypoints if w.id == wpt_ref), None)
                    if matching_wpt:
                        obj_pos = tuple(matching_wpt.global_point)
            
            if obj_pos:
                objective_positions.append(obj_pos)
                obj_name = getattr(objective, 'name', f"Objective {obj_idx+1}")
                obj_required = getattr(objective, 'required', False)
                marker = "★" if obj_required else "○"
                actors_objs.append(self._add_labeled_point(obj_pos, f"{marker} {obj_name}", 'lime', point_size=30))
                
                # Add objective zone sphere if it has radius info
                radius = None
                if hasattr(objective, 'fields') and isinstance(objective.fields, dict):
                    radius = objective.fields.get('trigger_radius') or objective.fields.get('radius')
                if radius:
                    actors_objs.append(self._add_sphere(obj_pos, radius, 'lime', opacity=0.15))
        
        # Add triggers
        self._log("Adding triggers...")
        for trigger in self.mission.trigger_events:
            trigger_name = getattr(trigger, 'name', 'Trigger')
            trigger_type = getattr(trigger, 'trigger_type', 'Unknown')
            
            # Try to find trigger position (proximity triggers have waypoint reference)
            if trigger_type == 'Proximity':
                wpt_ref = getattr(trigger, 'waypoint', None)
                radius = getattr(trigger, 'radius', 500.0)
                
                trig_pos = None
                if wpt_ref is not None:
                    if hasattr(wpt_ref, 'global_point'):
                        trig_pos = tuple(wpt_ref.global_point)
                    elif isinstance(wpt_ref, int):
                        matching_wpt = next((w for w in self.mission.waypoints if w.id == wpt_ref), None)
                        if matching_wpt:
                            trig_pos = tuple(matching_wpt.global_point)
                
                if trig_pos:
                    actors_trigs.append(self._add_labeled_point(trig_pos, f"⚡ {trigger_name}", 'purple', point_size=18))
                    actors_trigs.append(self._add_sphere(trig_pos, radius, 'purple', opacity=0.2, wireframe=True))
        
        # Add paths
        self._log("Adding paths...")
        for path in self.mission.paths:
            pts = getattr(path, 'points', []) or []
            points = [(p[0], p[1], p[2]) for p in pts if isinstance(p, (list, tuple)) and len(p) == 3]
            if points:
                actors_paths.append(self._add_path(points, 'cyan', width=3))

        # Add base footprints and spawn point previews (if any)
        try:
            from pytol.resources.base_spawn_points import get_spawn_points_for, compute_world_from_base
            bases = getattr(self.calculator, 'bases', []) or []
            for base in bases:
                fz = base.get('flatten_zone', [])
                if fz:
                    try:
                        actors_bases.append(self._add_polygon([(x, z) for (x, z) in fz], color='#8e44ad', opacity=0.12))
                    except Exception:
                        pass
                # Spawn points
                spawns = get_spawn_points_for(base.get('prefab_type', ''))
                for sp in spawns:
                    (wx, wy, wz), wyaw = compute_world_from_base(base, tuple(sp.get('offset', (0.0, 0.0))), sp.get('yaw_offset', 0.0))
                    actors_spawns.append(self._add_labeled_point((wx, wy, wz), sp.get('name', 'Spawn'), '#e67e22', point_size=22))
        except Exception:
            pass
        
        # Calculate mission center of mass for better camera positioning
        all_positions = unit_positions + waypoint_positions + objective_positions
        
        # Setup camera to focus on mission center
        if all_positions:
            # Calculate center of all mission elements
            center_x = sum(p[0] for p in all_positions) / len(all_positions)
            center_y = sum(p[1] for p in all_positions) / len(all_positions)
            center_z = sum(p[2] for p in all_positions) / len(all_positions)
            focal_point = self._pv_pos((center_x, center_y, center_z))
            
            # Calculate appropriate camera distance based on spread
            max_dist = 0
            for pos in all_positions:
                dist = np.sqrt((pos[0] - center_x)**2 + (pos[2] - center_z)**2)
                max_dist = max(max_dist, dist)
            
            camera_dist = max(max_dist * 1.5, 5000)
            self.plotter.camera.position = [focal_point[0] + camera_dist, 
                                           focal_point[1] + camera_dist * 0.5, 
                                           focal_point[2] + camera_dist]
            self.plotter.camera.focal_point = focal_point
        else:
            map_center = self.calculator.total_map_size_meters / 2
            focal_point = [-map_center, 
                          self.calculator.get_terrain_height(map_center, map_center), 
                          map_center]
            self.plotter.camera.position = [focal_point[0] + 5000, 
                                           focal_point[1] + 2000, 
                                           focal_point[2] + 5000]
            self.plotter.camera.focal_point = focal_point
        
        self.plotter.camera.zoom(1.5)
        self.plotter.enable_terrain_style()
        # Build legend with counts
        legend_items = [
            (f"Units: {len(self.mission.units)}", None),
            (f"Waypoints: {len(self.mission.waypoints)}", None),
            (f"Objectives: {len(self.mission.objectives)}", None),
            (f"Triggers: {len(self.mission.trigger_events)}", None),
        ]
        try:
            bases_count = len(getattr(self.calculator, 'bases', []) or [])
            legend_items.append((f"Bases: {bases_count}", None))
        except Exception:
            pass
        try:
            from pytol.resources.base_spawn_points import BASE_SPAWN_POINTS
            sp_count = sum(len(v) for v in (BASE_SPAWN_POINTS or {}).values())
            legend_items.append((f"Spawn Points (DB): {sp_count}", None))
        except Exception:
            pass
        self.plotter.add_legend(labels=legend_items)
        self.plotter.add_axes()
        
        self._log("\n" + "="*50)
        self._log(f"Mission: {self.mission.scenario_name}")
        self._log(f"Map: {self.mission.map_id}")
        self._log(f"Units: {len(self.mission.units)}")
        self._log(f"Waypoints: {len(self.mission.waypoints)}")
        self._log(f"Objectives: {len(self.mission.objectives)}")
        self._log("="*50)
        # Visibility toggles
        def _toggle(actors_list):
            for a in actors_list:
                if a is None:
                    continue
                if isinstance(a, tuple):
                    for sub in a:
                        if sub is not None:
                            sub.SetVisibility(not sub.GetVisibility())
                else:
                    try:
                        a.SetVisibility(not a.GetVisibility())
                    except Exception:
                        pass
            self.plotter.render()

        self.plotter.add_key_event('u', lambda: _toggle(actors_units))
        self.plotter.add_key_event('w', lambda: _toggle(actors_wpts))
        self.plotter.add_key_event('o', lambda: _toggle(actors_objs))
        self.plotter.add_key_event('t', lambda: _toggle(actors_trigs))
        self.plotter.add_key_event('b', lambda: _toggle(actors_bases))
        self.plotter.add_key_event('s', lambda: _toggle(actors_spawns))

        self._log("\nVisualization Controls:")
        self._log("  'q': Exit")
        self._log("  u: toggle Units | w: Waypoints | o: Objectives | t: Triggers | b: Bases | s: Spawn points")
        self._log("  Mouse: Click and drag to rotate")
        self._log("  Scroll: Zoom in/out")
        self._log("="*50)
        
        self.plotter.show()

