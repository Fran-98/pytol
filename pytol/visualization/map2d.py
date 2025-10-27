"""
Lightweight 2D visualization for VTOL VR missions using matplotlib.

This module provides static image generation for mission overviews,
showing terrain, units, waypoints, and objectives in a top-down tactical view.
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import math
from typing import Tuple
from io import BytesIO
from ..misc.logger import create_logger


class Map2DVisualizer:
    """
    Lightweight 2D mission visualizer using matplotlib.
    
    Creates static top-down tactical maps showing:
    - Terrain elevation with contour lines or heatmap
    - City blocks (green=spawnable, red=obstacles)
    - Road network
    - Units with team colors and facing indicators
    - Waypoints and flight paths
    - Airbases with spawn points
    - Objectives and triggers
    
    Example:
        >>> from pytol import Mission
        >>> from pytol.visualization import Map2DVisualizer
        >>> 
        >>> mission = Mission("Test", "test", "Test mission", map_id="hMap2")
        >>> # ... add units, waypoints, etc ...
        >>> 
        >>> viz = Map2DVisualizer(mission)
        >>> viz.save_mission_overview("mission_map.png")
    """
    
    def __init__(self, mission_or_terrain, figsize: Tuple[int, int] = (12, 12), dpi: int = 150, verbose: bool = True):
        """
        Initialize 2D visualizer.
        
        Args:
            mission_or_terrain: Mission object or TerrainCalculator instance
            figsize: Figure size in inches (width, height)
            dpi: Image resolution (dots per inch)
            verbose: Whether to print progress messages
        """
        self.figsize = figsize
        self.dpi = dpi
        self.verbose = verbose
        self.logger = create_logger(verbose=verbose, name="Map2D")
        
        # Determine input type and extract components
        if hasattr(mission_or_terrain, 'tc'):
            # Mission object
            self.mission = mission_or_terrain
            self.tc = mission_or_terrain.tc
            self.has_mission_data = True
        else:
            # TerrainCalculator object
            self.mission = None
            self.tc = mission_or_terrain
            self.has_mission_data = False
            
        map_name = getattr(self.tc, 'map_name', getattr(self.tc, 'map_id', 'unknown'))
        self.logger.info(f"Initialized 2D visualizer for map '{map_name}'")
        
        # Color schemes
        self.colors = {
            'terrain_low': '#2E4A3D',      # Dark green for low terrain
            'terrain_high': '#8B7355',     # Brown for high terrain
            'water': '#1F4E79',            # Blue for water
            'roads': '#404040',            # Dark gray for roads
            'city_spawnable': '#28A745',   # Green for spawnable buildings
            'city_obstacle': '#DC3545',    # Red for obstacles
            'allied_units': '#0066CC',     # Blue for allied units
            'enemy_units': '#CC0000',      # Red for enemy units
            'neutral_units': '#808080',    # Gray for neutral units
            'waypoints': '#FF6600',        # Orange for waypoints
            'objectives': '#9900CC',       # Purple for objectives
            'airbases': '#FFD700',         # Gold for airbases
        }
    
    def _create_terrain_layer(self, ax, style: str = 'contour', alpha: float = 0.7):
        """Create terrain elevation layer."""
        self.logger.info("Generating terrain layer...")
        
        # Get heightmap data
        heightmap = self.tc.heightmap_data_r
        map_size = self.tc.total_map_size_meters
        
        # Create coordinate arrays
        x = np.linspace(0, map_size, heightmap.shape[1])
        z = np.linspace(0, map_size, heightmap.shape[0])
        X, Z = np.meshgrid(x, z)
        
        # Convert heightmap to world heights
        min_alt, max_alt = self.tc.min_height, self.tc.max_height
        heights = min_alt + (heightmap / 255.0) * (max_alt - min_alt)
        
        if style == 'contour':
            # Contour lines with elevation coloring
            contour_levels = np.linspace(min_alt, max_alt, 20)
            cs = ax.contourf(X, Z, heights, levels=contour_levels, 
                           cmap='terrain', alpha=alpha, extend='both')
            
            # Add contour lines
            ax.contour(X, Z, heights, levels=contour_levels[::2], 
                      colors='black', alpha=0.3, linewidths=0.5)
            
            return cs
        
        elif style == 'heatmap':
            # Simple heatmap
            im = ax.imshow(heights, extent=[0, map_size, 0, map_size], 
                          cmap='terrain', alpha=alpha, origin='lower')
            return im
    
    def _create_roads_layer(self, ax, color: str = None, width: float = 1.0):
        """Create road network layer."""
        if not hasattr(self.tc, 'road_segments') or not self.tc.road_segments:
            return
            
        self.logger.info(f"Drawing {len(self.tc.road_segments)} road segments...")
        color = color or self.colors['roads']
        
        for segment in self.tc.road_segments:
            # Each segment is a tuple (start_3d, end_3d)
            if len(segment) != 2:
                continue
                
            start_3d, end_3d = segment
            xs = [start_3d[0], end_3d[0]]
            zs = [start_3d[2], end_3d[2]]  # Use Z coordinate for 2D plot
            ax.plot(xs, zs, color=color, linewidth=width, alpha=0.8)
    
    def _create_cities_layer(self, ax):
        """Create city blocks layer with spawnable/obstacle distinction."""
        if not hasattr(self.tc, 'city_blocks') or not self.tc.city_blocks:
            return
            
        self.logger.info(f"Drawing {len(self.tc.city_blocks)} city blocks...")
        
        for block in self.tc.city_blocks:
            position = block.get('position', [0, 0, 0])
            surfaces = block.get('surfaces', [])
            
            block_x, block_z = position[0], position[2]
            
            # Draw surfaces as colored rectangles
            for surface in surfaces:
                # Get surface bounds (simplified as rectangle)
                bounds = surface.get('bounds', {})
                min_rel = bounds.get('min', [-10, -1, -10])
                max_rel = bounds.get('max', [10, 10, 10])
                
                width = max_rel[0] - min_rel[0]
                height = max_rel[2] - min_rel[2]
                
                color = (self.colors['city_spawnable'] if surface.get('is_spawnable', False) 
                        else self.colors['city_obstacle'])
                
                rect = patches.Rectangle(
                    (block_x + min_rel[0], block_z + min_rel[2]),
                    width, height,
                    linewidth=0.5, edgecolor='black', facecolor=color, alpha=0.6
                )
                ax.add_patch(rect)
    
    def _create_static_prefabs_layer(self, ax):
        """Create static prefabs layer (airbases, etc.)."""
        if not hasattr(self.tc, 'bases') or not self.tc.bases:
            return
            
        self.logger.info(f"Drawing {len(self.tc.bases)} static prefabs/bases...")
        
        for base in self.tc.bases:
            pos = base.get('position', [0, 0, 0])
            prefab_type = base.get('prefab_type', 'unknown')
            
            # Draw base as a special marker
            if 'airbase' in prefab_type.lower():
                ax.scatter(pos[0], pos[2], s=200, c=self.colors['airbases'], 
                          marker='s', edgecolors='black', linewidth=2, 
                          label='Airbase' if not hasattr(ax, '_airbase_labeled') else "",
                          zorder=10)
                ax._airbase_labeled = True
                
                # Add base label
                ax.annotate(f'{prefab_type}', (pos[0], pos[2]), 
                           xytext=(5, 5), textcoords='offset points',
                           fontsize=8, fontweight='bold')
    
    def _create_units_layer(self, ax, highlight_base_index=None):
        """Create units layer with team colors and facing indicators."""
        if not self.has_mission_data:
            return
            
        units = getattr(self.mission, 'units', [])
        if not units:
            return
            
        self.logger.info(f"Drawing {len(units)} units...")
        
        for unit_data in units:
            # Handle both unit objects and unit dictionaries (from mission.units)
            if isinstance(unit_data, dict):
                unit = unit_data.get('unit_obj', unit_data)
            else:
                unit = unit_data
                
            pos = unit.global_position
            rot = unit.rotation
            team = getattr(unit, 'team', 'Allied')
            
            # Team color
            if team.lower() in ['allied', 'player']:
                color = self.colors['allied_units']
                label = 'Allied Units'
            elif team.lower() == 'enemy':
                color = self.colors['enemy_units']
                label = 'Enemy Units'
            else:
                color = self.colors['neutral_units']
                label = 'Neutral Units'
            
            # Unit position
            ax.scatter(pos[0], pos[2], s=100, c=color, marker='o', 
                      edgecolors='black', linewidth=1,
                      label=label if not hasattr(ax, f'_{team.lower()}_labeled') else "",
                      zorder=8)
            setattr(ax, f'_{team.lower()}_labeled', True)
            
            # Facing indicator (small arrow)
            if rot and len(rot) >= 2:
                yaw_rad = math.radians(rot[1])
                dx = math.cos(yaw_rad) * 50  # Arrow length
                dz = math.sin(yaw_rad) * 50
                
                ax.arrow(pos[0], pos[2], dx, dz, 
                        head_width=20, head_length=15, 
                        fc=color, ec=color, alpha=0.7, zorder=7)
    
    def _create_waypoints_layer(self, ax):
        """Create waypoints and paths layer."""
        if not self.has_mission_data:
            return
            
        waypoints = getattr(self.mission, 'waypoints', [])
        paths = getattr(self.mission, 'paths', [])
        
        if waypoints:
            self.logger.info(f"Drawing {len(waypoints)} waypoints...")
            
            for i, waypoint in enumerate(waypoints):
                pos = waypoint.global_point
                ax.scatter(pos[0], pos[2], s=80, c=self.colors['waypoints'], 
                          marker='^', edgecolors='black', linewidth=1,
                          label='Waypoints' if i == 0 else "", zorder=9)
                
                # Waypoint number
                ax.annotate(f'{i+1}', (pos[0], pos[2]), 
                           xytext=(0, 10), textcoords='offset points',
                           ha='center', fontsize=8, fontweight='bold')
        
        if paths:
            self.logger.info(f"Drawing {len(paths)} paths...")
            
            for path in paths:
                points = path.points
                if len(points) < 2:
                    continue
                    
                xs = [p[0] for p in points]
                zs = [p[2] for p in points]
                ax.plot(xs, zs, color=self.colors['waypoints'], 
                       linewidth=2, linestyle='--', alpha=0.8, zorder=6)
    
    def _create_objectives_layer(self, ax):
        """Create objectives layer."""
        if not self.has_mission_data:
            return
            
        objectives = getattr(self.mission, 'objectives', [])
        if not objectives:
            return
            
        self.logger.info(f"Drawing {len(objectives)} objectives...")
        
        for i, obj in enumerate(objectives):
            # Try to get objective position (this might need adjustment based on objective type)
            pos = None
            if hasattr(obj, 'position'):
                pos = obj.position
            elif hasattr(obj, 'waypoint_id') and self.mission.waypoints:
                # Find associated waypoint
                for wp in self.mission.waypoints:
                    if wp.id == obj.waypoint_id:
                        pos = wp.position
                        break
            
            if pos:
                ax.scatter(pos[0], pos[2], s=120, c=self.colors['objectives'], 
                          marker='*', edgecolors='black', linewidth=1,
                          label='Objectives' if i == 0 else "", zorder=11)
                
                # Objective label
                name = getattr(obj, 'objective_name', f'Obj {i+1}')
                ax.annotate(name, (pos[0], pos[2]), 
                           xytext=(10, 10), textcoords='offset points',
                           fontsize=8, bbox=dict(boxstyle="round,pad=0.3", 
                                                facecolor='white', alpha=0.8))
    
    def save_terrain_overview(self, filename: str, style: str = 'contour') -> str:
        """
        Save a terrain-only overview image.
        
        Args:
            filename: Output filename (with extension)
            style: Terrain style ('contour' or 'heatmap')
            
        Returns:
            Path to saved file
        """
        self.logger.info(f"Creating terrain overview: {filename}")
        
        fig, ax = plt.subplots(figsize=self.figsize, dpi=self.dpi)
        
        # Create terrain layer
        cs = self._create_terrain_layer(ax, style=style)
        
        # Add roads and cities
        self._create_roads_layer(ax)
        self._create_cities_layer(ax)
        self._create_static_prefabs_layer(ax)
        
        # Formatting
        ax.set_xlim(0, self.tc.total_map_size_meters)
        ax.set_ylim(0, self.tc.total_map_size_meters)
        ax.set_xlabel('X (meters)', fontsize=12)
        ax.set_ylabel('Z (meters)', fontsize=12)
        map_name = getattr(self.tc, 'map_name', getattr(self.tc, 'map_id', 'unknown'))
        ax.set_title(f'Terrain Overview - {map_name}', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.set_aspect('equal')
        
        # Add colorbar for elevation
        if cs:
            cbar = plt.colorbar(cs, ax=ax, shrink=0.8)
            cbar.set_label('Elevation (m)', fontsize=10)
        
        # Legend
        ax.legend(loc='upper right', framealpha=0.9)
        
        plt.tight_layout()
        plt.savefig(filename, dpi=self.dpi, bbox_inches='tight')
        plt.close()
        
        self.logger.info(f"✓ Terrain overview saved: {filename}")
        return filename
    
    def save_mission_overview(self, filename: str, terrain_style: str = 'contour', clean_mode: bool = False) -> str:
        """
        Save a complete mission overview image with all layers.
        
        Args:
            filename: Output filename (with extension)
            terrain_style: Terrain style ('contour' or 'heatmap')
            clean_mode: If True, skip terrain heightmap for cleaner look
            
        Returns:
            Path to saved file
        """
        if not self.has_mission_data:
            raise ValueError("Mission data required for mission overview. Use save_terrain_overview() for terrain-only images.")
        
        self.logger.info(f"Creating mission overview: {filename}")
        
        fig, ax = plt.subplots(figsize=self.figsize, dpi=self.dpi)
        
        # Create all layers
        cs = None
        if not clean_mode:
            cs = self._create_terrain_layer(ax, style=terrain_style, alpha=0.6)
        self._create_roads_layer(ax)
        self._create_cities_layer(ax)
        self._create_static_prefabs_layer(ax)
        self._create_units_layer(ax)
        self._create_waypoints_layer(ax)
        self._create_objectives_layer(ax)
        
        # Formatting
        ax.set_xlim(0, self.tc.total_map_size_meters)
        ax.set_ylim(0, self.tc.total_map_size_meters)
        ax.set_xlabel('X (meters)', fontsize=12)
        ax.set_ylabel('Z (meters)', fontsize=12)
        
        # Title with mission info
        scenario_name = getattr(self.mission, 'scenario_name', 'Unknown Mission')
        map_name = getattr(self.tc, 'map_name', getattr(self.tc, 'map_id', 'unknown'))
        ax.set_title(f'{scenario_name} - {map_name}', fontsize=14, fontweight='bold')
        
        ax.grid(True, alpha=0.3)
        ax.set_aspect('equal')
        
        # Add colorbar for elevation
        if cs:
            cbar = plt.colorbar(cs, ax=ax, shrink=0.8)
            cbar.set_label('Elevation (m)', fontsize=10)
        
        # Legend
        ax.legend(loc='upper right', framealpha=0.9, fontsize=10)
        
        plt.tight_layout()
        plt.savefig(filename, dpi=self.dpi, bbox_inches='tight')
        plt.close()
        
        self.logger.info(f"✓ Mission overview saved: {filename}")
        return filename
    
    def save_spawn_points_detail(self, filename: str, base_index: int = 0) -> str:
        """
        Save a detailed view of spawn points at a specific airbase.
        
        Args:
            filename: Output filename (with extension)
            base_index: Which airbase to focus on (0-based)
            
        Returns:
            Path to saved file
        """
        if not hasattr(self.tc, 'bases') or not self.tc.bases:
            raise ValueError("No airbases found on map")
        
        if base_index >= len(self.tc.bases):
            raise ValueError(f"Base index {base_index} out of range (found {len(self.tc.bases)} bases)")
        
        base = self.tc.bases[base_index]
        self.logger.info(f"Creating spawn points detail for base {base_index}: {filename}")
        
        # Import spawn point utilities
        from ..resources.base_spawn_points import get_spawn_points, get_reference_points, compute_world_from_base
        
        prefab_type = base.get('prefab_type', '')
        spawn_points = get_spawn_points(prefab_type)
        reference_points = get_reference_points(prefab_type)
        
        if not spawn_points and not reference_points:
            self.logger.warning(f"No spawn points found for {prefab_type}")
        
        fig, ax = plt.subplots(figsize=(10, 10), dpi=self.dpi)
        
        # Focus area around base (2km radius)
        base_pos = base['position']
        focus_radius = 2000
        x_min, x_max = base_pos[0] - focus_radius, base_pos[0] + focus_radius
        z_min, z_max = base_pos[2] - focus_radius, base_pos[2] + focus_radius
        
        # Terrain background (simplified)
        heightmap = self.tc.heightmap_data_r
        map_size = self.tc.total_map_size_meters
        
        # Create terrain subset
        x_indices = np.clip(np.array([x_min, x_max]) * heightmap.shape[1] / map_size, 0, heightmap.shape[1]-1).astype(int)
        z_indices = np.clip(np.array([z_min, z_max]) * heightmap.shape[0] / map_size, 0, heightmap.shape[0]-1).astype(int)
        
        terrain_subset = heightmap[z_indices[0]:z_indices[1], x_indices[0]:x_indices[1]]
        if terrain_subset.size > 0:
            ax.imshow(terrain_subset, extent=[x_min, x_max, z_min, z_max], 
                     cmap='terrain', alpha=0.3, origin='lower')
        
        # Base center
        ax.scatter(base_pos[0], base_pos[2], s=300, c=self.colors['airbases'], 
                  marker='s', edgecolors='black', linewidth=2, label='Base Center', zorder=10)
        
        # Spawn points
        for i, spawn in enumerate(spawn_points):
            pos, yaw = compute_world_from_base(base, spawn['offset'], spawn['yaw_offset'])
            
            # Color by category
            name = spawn['name'].lower()
            if 'hangar' in name:
                color, marker = '#00AA00', 'o'
            elif 'helipad' in name or 'heli' in name:
                color, marker = '#0066CC', 's'
            elif 'bigplane' in name:
                color, marker = '#CC6600', '^'
            else:
                color, marker = '#666666', 'o'
            
            ax.scatter(pos[0], pos[2], s=150, c=color, marker=marker, 
                      edgecolors='black', linewidth=1, zorder=8)
            
            # Facing arrow
            yaw_rad = math.radians(yaw)
            dx = math.cos(yaw_rad) * 30
            dz = math.sin(yaw_rad) * 30
            ax.arrow(pos[0], pos[2], dx, dz, head_width=10, head_length=8, 
                    fc=color, ec=color, alpha=0.8, zorder=7)
            
            # Label
            ax.annotate(f'{i+1}', (pos[0], pos[2]), xytext=(0, -15), 
                       textcoords='offset points', ha='center', fontsize=8)
        
        # Reference points
        for ref in reference_points:
            pos, yaw = compute_world_from_base(base, ref['offset'], ref['yaw_offset'])
            
            ax.scatter(pos[0], pos[2], s=100, c='purple', marker='*', 
                      edgecolors='black', linewidth=1, zorder=9)
            
            # Label
            ax.annotate(ref['name'], (pos[0], pos[2]), xytext=(5, 5), 
                       textcoords='offset points', fontsize=8, 
                       bbox=dict(boxstyle="round,pad=0.2", facecolor='white', alpha=0.8))
        
        # Formatting
        ax.set_xlim(x_min, x_max)
        ax.set_ylim(z_min, z_max)
        ax.set_xlabel('X (meters)', fontsize=12)
        ax.set_ylabel('Z (meters)', fontsize=12)
        ax.set_title(f'Spawn Points - {prefab_type} (Base {base_index})', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.set_aspect('equal')
        
        # Custom legend
        legend_elements = [
            plt.scatter([], [], s=150, c='#00AA00', marker='o', edgecolors='black', label='Hangars'),
            plt.scatter([], [], s=150, c='#0066CC', marker='s', edgecolors='black', label='Helipads'),
            plt.scatter([], [], s=150, c='#CC6600', marker='^', edgecolors='black', label='Large Aircraft'),
            plt.scatter([], [], s=100, c='purple', marker='*', edgecolors='black', label='Reference Points'),
        ]
        ax.legend(handles=legend_elements, loc='upper right', framealpha=0.9)
        
        plt.tight_layout()
        plt.savefig(filename, dpi=self.dpi, bbox_inches='tight')
        plt.close()
        
        self.logger.info(f"✓ Spawn points detail saved: {filename}")
        return filename

    def get_terrain_overview_bytes(self, style: str = 'contour', format: str = 'PNG') -> bytes:
        """
        Get terrain overview image as bytes for use with PIL/Pillow or other libraries.
        
        Args:
            style: Terrain style ('contour' or 'heatmap')
            format: Image format ('PNG', 'JPEG', 'PDF', 'SVG')
            
        Returns:
            Image data as bytes
            
        Example:
            >>> viz = Map2DVisualizer(mission)
            >>> img_bytes = viz.get_terrain_overview_bytes()
            >>> from PIL import Image
            >>> img = Image.open(BytesIO(img_bytes))
            >>> img.show()
        """
        self.logger.info(f"Creating terrain overview bytes (format: {format})")
        
        fig, ax = plt.subplots(figsize=self.figsize, dpi=self.dpi)
        
        # Create terrain layer
        cs = self._create_terrain_layer(ax, style=style)
        
        # Formatting
        ax.set_xlim(0, self.tc.total_map_size_meters)
        ax.set_ylim(0, self.tc.total_map_size_meters)
        ax.set_xlabel('X (meters)', fontsize=12)
        ax.set_ylabel('Z (meters)', fontsize=12)
        
        # Title
        map_name = getattr(self.tc, 'map_name', getattr(self.tc, 'map_id', 'unknown'))
        ax.set_title(f'Terrain Overview - {map_name}', fontsize=14, fontweight='bold')
        
        ax.grid(True, alpha=0.3)
        ax.set_aspect('equal')
        
        # Add colorbar for elevation
        if cs:
            cbar = plt.colorbar(cs, ax=ax, shrink=0.8)
            cbar.set_label('Elevation (m)', fontsize=10)
        
        plt.tight_layout()
        
        # Save to BytesIO
        buffer = BytesIO()
        plt.savefig(buffer, format=format.lower(), dpi=self.dpi, bbox_inches='tight')
        plt.close()
        
        buffer.seek(0)
        image_bytes = buffer.getvalue()
        buffer.close()
        
        self.logger.info(f"✓ Terrain overview bytes created ({len(image_bytes)} bytes)")
        return image_bytes

    def get_mission_overview_bytes(self, terrain_style: str = 'contour', clean_mode: bool = False, format: str = 'PNG') -> bytes:
        """
        Get complete mission overview image as bytes for use with PIL/Pillow or other libraries.
        
        Args:
            terrain_style: Terrain style ('contour' or 'heatmap')
            clean_mode: If True, skip terrain heightmap for cleaner look
            format: Image format ('PNG', 'JPEG', 'PDF', 'SVG')
            
        Returns:
            Image data as bytes
            
        Example:
            >>> viz = Map2DVisualizer(mission)
            >>> img_bytes = viz.get_mission_overview_bytes(clean_mode=True)
            >>> from PIL import Image
            >>> img = Image.open(BytesIO(img_bytes))
            >>> img.save("mission_copy.png")
        """
        if not self.has_mission_data:
            raise ValueError("Mission data required for mission overview. Use get_terrain_overview_bytes() for terrain-only images.")
        
        self.logger.info(f"Creating mission overview bytes (format: {format})")
        
        fig, ax = plt.subplots(figsize=self.figsize, dpi=self.dpi)
        
        # Create all layers
        cs = None
        if not clean_mode:
            cs = self._create_terrain_layer(ax, style=terrain_style, alpha=0.6)
        self._create_roads_layer(ax)
        self._create_cities_layer(ax)
        self._create_static_prefabs_layer(ax)
        self._create_units_layer(ax)
        self._create_waypoints_layer(ax)
        self._create_objectives_layer(ax)
        
        # Formatting
        ax.set_xlim(0, self.tc.total_map_size_meters)
        ax.set_ylim(0, self.tc.total_map_size_meters)
        ax.set_xlabel('X (meters)', fontsize=12)
        ax.set_ylabel('Z (meters)', fontsize=12)
        
        # Title with mission info
        scenario_name = getattr(self.mission, 'scenario_name', 'Unknown Mission')
        map_name = getattr(self.tc, 'map_name', getattr(self.tc, 'map_id', 'unknown'))
        ax.set_title(f'{scenario_name} - {map_name}', fontsize=14, fontweight='bold')
        
        ax.grid(True, alpha=0.3)
        ax.set_aspect('equal')
        
        # Add colorbar for elevation
        if cs:
            cbar = plt.colorbar(cs, ax=ax, shrink=0.8)
            cbar.set_label('Elevation (m)', fontsize=10)
        
        # Legend
        ax.legend(loc='upper right', framealpha=0.9, fontsize=10)
        
        plt.tight_layout()
        
        # Save to BytesIO
        buffer = BytesIO()
        plt.savefig(buffer, format=format.lower(), dpi=self.dpi, bbox_inches='tight')
        plt.close()
        
        buffer.seek(0)
        image_bytes = buffer.getvalue()
        buffer.close()
        
        self.logger.info(f"✓ Mission overview bytes created ({len(image_bytes)} bytes)")
        return image_bytes

    def get_spawn_points_detail_bytes(self, base_index: int = 0, format: str = 'PNG') -> bytes:
        """
        Get detailed spawn points view as bytes for use with PIL/Pillow or other libraries.
        
        Args:
            base_index: Index of the airbase to focus on
            format: Image format ('PNG', 'JPEG', 'PDF', 'SVG')
            
        Returns:
            Image data as bytes
            
        Example:
            >>> viz = Map2DVisualizer(mission)
            >>> img_bytes = viz.get_spawn_points_detail_bytes(base_index=0)
            >>> from PIL import Image
            >>> img = Image.open(BytesIO(img_bytes))
            >>> img.rotate(45).save("rotated_spawn_points.png")
        """
        if not self.has_mission_data:
            raise ValueError("Mission data required for spawn points detail")
        
        # Find the specified airbase
        airbases = [unit for unit in self.mission.units if hasattr(unit, 'unit_spawn_points')]
        if not airbases:
            raise ValueError("No airbases found in mission")
        
        if base_index >= len(airbases):
            raise ValueError(f"Base index {base_index} not found. Available: 0-{len(airbases)-1}")
        
        base = airbases[base_index]
        self.logger.info(f"Creating spawn points detail bytes for base {base_index} (format: {format})")
        
        # Get base center for focusing
        base_x = base.global_point.x if hasattr(base.global_point, 'x') else base.global_point[0]
        base_z = base.global_point.z if hasattr(base.global_point, 'z') else base.global_point[2]
        
        fig, ax = plt.subplots(figsize=self.figsize, dpi=self.dpi)
        
        # Create layers with focus on base area
        self._create_terrain_layer(ax, style='contour', alpha=0.4)
        self._create_roads_layer(ax)
        self._create_cities_layer(ax)
        self._create_static_prefabs_layer(ax)
        
        # Highlight the selected base and its spawn points
        self._create_units_layer(ax, highlight_base_index=base_index)
        
        # Focus area around the base (±2km)
        focus_range = 2000
        ax.set_xlim(max(0, base_x - focus_range), min(self.tc.total_map_size_meters, base_x + focus_range))
        ax.set_ylim(max(0, base_z - focus_range), min(self.tc.total_map_size_meters, base_z + focus_range))
        
        ax.set_xlabel('X (meters)', fontsize=12)
        ax.set_ylabel('Z (meters)', fontsize=12)
        
        # Title
        scenario_name = getattr(self.mission, 'scenario_name', 'Unknown Mission')
        ax.set_title(f'{scenario_name} - Base {base_index+1} Spawn Points Detail', fontsize=14, fontweight='bold')
        
        ax.grid(True, alpha=0.3)
        ax.set_aspect('equal')
        ax.legend(loc='upper right', framealpha=0.9, fontsize=10)
        
        plt.tight_layout()
        
        # Save to BytesIO
        buffer = BytesIO()
        plt.savefig(buffer, format=format.lower(), dpi=self.dpi, bbox_inches='tight')
        plt.close()
        
        buffer.seek(0)
        image_bytes = buffer.getvalue()
        buffer.close()
        
        self.logger.info(f"✓ Spawn points detail bytes created ({len(image_bytes)} bytes)")
        return image_bytes


# Convenience function
def save_mission_map(mission, filename: str, style: str = 'mission_overview', **kwargs) -> str:
    """
    Convenience function to quickly save a mission map.
    
    Args:
        mission: Mission object or TerrainCalculator
        filename: Output filename
        style: Map style ('mission_overview', 'terrain_only', 'spawn_points')
        **kwargs: Additional arguments passed to Map2DVisualizer
    
    Returns:
        Path to saved file
    """
    viz = Map2DVisualizer(mission, **kwargs)
    
    if style == 'mission_overview':
        clean_mode = kwargs.get('clean_mode', False)
        terrain_style = kwargs.get('terrain_style', 'contour')
        return viz.save_mission_overview(filename, terrain_style=terrain_style, clean_mode=clean_mode)
    elif style == 'terrain_only':
        return viz.save_terrain_overview(filename)
    elif style == 'spawn_points':
        base_index = kwargs.get('base_index', 0)
        return viz.save_spawn_points_detail(filename, base_index)
    else:
        raise ValueError(f"Unknown style: {style}")