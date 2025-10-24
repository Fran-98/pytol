"""
Core visualization classes for pytol terrain and missions.

This module provides interactive 3D visualization using PyVista.
"""

import numpy as np
from scipy.spatial.transform import Rotation as R
import pyvista as pv
import os
from typing import List, Dict, Tuple, Optional, Any
import random


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
    
    def __init__(self, terrain_calculator, mesh_resolution: int = 256, drape_roads: bool = True):
        """
        Initialize terrain visualizer.
        
        Args:
            terrain_calculator: TerrainCalculator instance
            mesh_resolution: Resolution for terrain mesh (default: 256)
            drape_roads: Whether to drape roads on terrain surface (default: True)
        """
        self.calculator = terrain_calculator
        self.mesh_resolution = mesh_resolution
        self.drape_roads = drape_roads
        self.plotter = None
        
        # Pre-process data
        self._generate_terrain_mesh()
        self._generate_building_meshes()
        self._generate_road_meshes()
        
    def _generate_terrain_mesh(self):
        """Generate the base terrain mesh from heightmap."""
        print(f"Generating {self.mesh_resolution}x{self.mesh_resolution} terrain mesh...")
        total_size = self.calculator.total_map_size_meters
        x_points = np.linspace(0, total_size, self.mesh_resolution)
        z_points = np.linspace(0, total_size, self.mesh_resolution)
        xx, zz = np.meshgrid(x_points, z_points)
        yy = np.array([[self.calculator.get_terrain_height(x, z) for x in x_points] for z in z_points])
        
        self.terrain_surface = pv.StructuredGrid(-xx, yy, zz).extract_surface()
        self.terrain_surface.point_data['Altitude'] = yy.ravel(order='C')
        print("Terrain mesh created.")
        
    def _generate_building_meshes(self):
        """Generate meshes for city blocks and static prefabs."""
        print("Generating building and prefab meshes...")
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
        print(f"Rendered {len(spawnable_meshes) + len(obstacle_meshes)} building/prefab surfaces.")
        
    def _generate_road_meshes(self):
        """Generate road network meshes."""
        print("Generating road network meshes...")
        road_meshes, bridge_meshes = [], []
        
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
        print(f"Rendered {len(road_meshes)} road segments.")
        
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
        
        print("\nVisualization Controls:")
        print("  'q': Exit")
        print("  Mouse: Click and drag to rotate")
        print("  Scroll: Zoom in/out")
        
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
    
    def __init__(self, mission, mesh_resolution: int = 256, drape_roads: bool = True):
        """
        Initialize mission visualizer.
        
        Args:
            mission: Mission instance from pytol
            mesh_resolution: Resolution for terrain mesh (default: 256)
            drape_roads: Whether to drape roads on terrain surface (default: True)
        """
        self.mission = mission
        super().__init__(mission.tc, mesh_resolution, drape_roads)
        
    def _pv_pos(self, pos: Tuple[float, float, float]) -> List[float]:
        """Convert VTOL VR position to PyVista coordinates."""
        return [-pos[0], pos[1], pos[2]]
    
    def _add_labeled_point(self, pos: Tuple[float, float, float], label: str, 
                          color: str, always_visible: bool = True):
        """Add a labeled point to the visualization."""
        return self.plotter.add_point_labels(
            self._pv_pos(pos), [label],
            point_size=15, point_color=color,
            font_size=16, shape_opacity=0.8,
            show_points=True,
            always_visible=always_visible,
            pickable=False
        )
    
    def _add_path(self, points: List[Tuple[float, float, float]], 
                 color: str, width: int = 5):
        """Add a path/line through multiple points."""
        if not points or len(points) < 2:
            return None
        pv_points = np.array([self._pv_pos(p) for p in points])
        mesh = pv.lines_from_points(pv_points)
        return self.plotter.add_mesh(mesh, color=color, line_width=width, pickable=False)
    
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
        
        # Add mission units
        print("Adding mission units to visualization...")
        for unit_data in self.mission.units:
            unit_obj = unit_data['unit_obj']
            pos = unit_data.get('global_position', (0, 0, 0))
            unit_name = unit_obj.unit_name if hasattr(unit_obj, 'unit_name') else f"Unit {unit_data['unitInstanceID']}"
            
            # Color by team
            if hasattr(unit_obj, 'unit_team'):
                color = 'blue' if unit_obj.unit_team == 'Allied' else 'red'
            else:
                color = 'gray'
            
            self._add_labeled_point(pos, unit_name, color)
        
        # Add waypoints
        print("Adding waypoints...")
        for waypoint in self.mission.waypoints:
            pos = (waypoint.global_point.x, waypoint.global_point.y, waypoint.global_point.z)
            name = waypoint.name if waypoint.name else f"WP-{waypoint.id}"
            self._add_labeled_point(pos, name, 'yellow')
        
        # Add paths
        print("Adding paths...")
        for path in self.mission.paths:
            points = [(p.global_point.x, p.global_point.y, p.global_point.z) 
                     for p in path.points]
            self._add_path(points, 'cyan', width=3)
        
        # Setup camera to focus on first unit or map center
        if self.mission.units:
            first_unit_pos = self.mission.units[0].get('global_position', None)
            if first_unit_pos:
                focal_point = self._pv_pos(first_unit_pos)
                self.plotter.camera.position = [focal_point[0] + 5000, 
                                               focal_point[1] + 2000, 
                                               focal_point[2] + 5000]
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
        self.plotter.add_legend()
        self.plotter.add_axes()
        
        print("\n" + "="*50)
        print(f"Mission: {self.mission.scenario_name}")
        print(f"Map: {self.mission.map_id}")
        print(f"Units: {len(self.mission.units)}")
        print(f"Waypoints: {len(self.mission.waypoints)}")
        print(f"Objectives: {len(self.mission.objectives)}")
        print("="*50)
        print("\nVisualization Controls:")
        print("  'q': Exit")
        print("  Mouse: Click and drag to rotate")
        print("  Scroll: Zoom in/out")
        print("="*50)
        
        self.plotter.show()
