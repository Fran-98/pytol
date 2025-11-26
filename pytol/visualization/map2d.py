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
            'friendly_territory': '#0044AA',    # Blue for friendly territory
            'enemy_territory': '#AA0000',       # Red for enemy territory
            'neutral_territory': '#808080',     # Gray for neutral territory
        }
    
    def _create_terrain_layer(self, ax, style: str = 'contour', alpha: float = 0.7):
        """Create terrain elevation layer.
        
        Water (below 0m) is rendered in blue.
        Sand/beach (0-10m) is rendered in sand color.
        Terrain (above 10m) uses terrain colormap (green->brown->white).
        """
        self.logger.info("Generating terrain layer...")
        
        # Get heightmap data (already normalized to [0, 1] range)
        heightmap = self.tc.heightmap_data_r
        map_size = self.tc.total_map_size_meters
        
        # Create coordinate arrays
        x = np.linspace(0, map_size, heightmap.shape[1])
        z = np.linspace(0, map_size, heightmap.shape[0])
        X, Z = np.meshgrid(x, z)
        
        # Convert heightmap to world heights
        # Note: heightmap_data_r is already normalized [0, 1], not [0, 255]
        min_alt, max_alt = self.tc.min_height, self.tc.max_height
        heights = min_alt + heightmap * (max_alt - min_alt)
        
        # Define elevation zones
        water_mask = heights < 0  # Below sea level
        sand_mask = (heights >= 0) & (heights <= 10)  # 0-10m above sea level (sand/beach)
        terrain_mask = heights > 10  # Above 10m (terrain)
        
        if style == 'contour':
            # Create a custom visualization that handles water, sand, and terrain separately
            
            # First, render water areas (below 0) in blue
            if np.any(water_mask):
                water_levels = np.linspace(min_alt, 0, 5)  # Fewer levels for water
                cs_water = ax.contourf(X, Z, np.where(water_mask, heights, np.nan), 
                                     levels=water_levels, colors='#1E4E79', alpha=alpha, 
                                     extend='min', zorder=1)
            
            # Render sand/beach areas (0-10m) in sand color
            sand_threshold = 10.0
            if np.any(sand_mask):
                sand_levels = np.linspace(0, sand_threshold, 3)
                cs_sand = ax.contourf(X, Z, np.where(sand_mask, heights, np.nan), 
                                     levels=sand_levels, colors='#D2B48C', alpha=alpha, 
                                     extend='neither', zorder=1)
            
            # Render terrain areas (above 10m) with terrain colormap
            terrain_min = max(10.0, np.nanmin(heights[terrain_mask]) if np.any(terrain_mask) else 10.0)
            terrain_max = max_alt
            if terrain_max > terrain_min:
                terrain_levels = np.linspace(terrain_min, terrain_max, 20)
                cs_terrain = ax.contourf(X, Z, np.where(terrain_mask, heights, np.nan), 
                                       levels=terrain_levels, cmap='terrain', alpha=alpha, 
                                       extend='max', zorder=1)
                
                # Add contour lines for terrain
                ax.contour(X, Z, np.where(terrain_mask, heights, np.nan), 
                          levels=terrain_levels[::3], colors='black', alpha=0.4, 
                          linewidths=0.8, zorder=2)
            
            # Return the terrain contour set for colorbar (if it exists)
            if 'cs_terrain' in locals():
                return cs_terrain
            elif np.any(terrain_mask):
                # Fallback: create a simple terrain visualization
                terrain_levels = np.linspace(terrain_min, terrain_max, 20)
                return ax.contourf(X, Z, heights, levels=terrain_levels, cmap='terrain', alpha=alpha, zorder=1)
            return None
        
        elif style == 'heatmap':
            # For heatmap style, use a custom colormap approach
            # Create RGB image manually
            from matplotlib.colors import LinearSegmentedColormap
            
            # Create custom colormap: blue (water) -> sand -> terrain
            colors_list = [
                '#1E4E79',  # Deep blue (water)
                '#2E5090',  # Medium blue (shallow water)
                '#D2B48C',  # Sand
                '#90EE90',  # Light green (low terrain)
                '#8B7355',  # Brown (medium terrain)
                '#FFFFFF'   # White (high terrain)
            ]
            n_bins = 256
            custom_cmap = LinearSegmentedColormap.from_list('terrain_custom', colors_list, N=n_bins)
            
            # Normalize heights to colormap range
            # Water gets first 20% of colormap (below 0)
            # Sand gets next 5% (0-10m)
            # Terrain gets remaining 75% (10m+)
            normalized_heights = np.zeros_like(heights)
            water_range = 0.2
            sand_range = 0.05
            terrain_start = water_range + sand_range
            
            # Map water to [0, water_range]
            if np.any(water_mask):
                normalized_heights[water_mask] = (heights[water_mask] - min_alt) / (-min_alt) * water_range
            
            # Map sand to [water_range, terrain_start]
            if np.any(sand_mask):
                normalized_heights[sand_mask] = water_range + (heights[sand_mask] / 10.0) * sand_range
            
            # Map terrain to [terrain_start, 1.0]
            if np.any(terrain_mask):
                terrain_min = 10.0
                terrain_span = max_alt - terrain_min
                if terrain_span > 0:
                    normalized_heights[terrain_mask] = terrain_start + ((heights[terrain_mask] - terrain_min) / terrain_span) * (1.0 - terrain_start)
                else:
                    normalized_heights[terrain_mask] = terrain_start
            
            im = ax.imshow(normalized_heights, extent=[0, map_size, 0, map_size], 
                          cmap=custom_cmap, alpha=alpha, origin='lower', zorder=1)
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
            ax.plot(xs, zs, color=color, linewidth=width, alpha=0.8, zorder=3)
    
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
                    linewidth=0.5, edgecolor='black', facecolor=color, alpha=0.6, zorder=3
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
                # Also check for lastValidPlacement in dict (fallback position)
                fallback_pos = unit_data.get('lastValidPlacement')
            else:
                unit = unit_data
                fallback_pos = None
            
            # Check if this is the player unit (make it more visible)
            is_player = False
            if hasattr(unit, 'unit_id'):
                unit_id_lower = str(unit.unit_id).lower()
                is_player = 'player' in unit_id_lower or unit_id_lower == 'playerspawn'
            elif hasattr(unit, 'unit_name'):
                unit_name_lower = str(unit.unit_name).lower()
                is_player = unit_name_lower == 'player'
                
            # Get position with fallback
            try:
                pos = getattr(unit, 'global_position', None) or fallback_pos
                if pos is None:
                    self.logger.warning(f"Unit {getattr(unit, 'unit_name', 'unknown')} has no position, skipping")
                    continue
                # Ensure position is a list/tuple with at least 3 elements
                if not isinstance(pos, (list, tuple)) or len(pos) < 3:
                    self.logger.warning(f"Unit {getattr(unit, 'unit_name', 'unknown')} has invalid position {pos}, skipping")
                    continue
                pos = tuple(pos)
            except (AttributeError, TypeError) as e:
                self.logger.warning(f"Could not get position for unit: {e}, skipping")
                continue
            
            # Check if position is within map bounds
            map_size = getattr(self.tc, 'total_map_size_meters', 196608.0)
            if pos[0] < 0 or pos[0] > map_size or pos[2] < 0 or pos[2] > map_size:
                self.logger.warning(f"Unit {getattr(unit, 'unit_name', 'unknown')} at {pos} is outside map bounds (0-{map_size}), skipping")
                continue
            
            rot = getattr(unit, 'rotation', [0, 0, 0])
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
            
            # Unit position - make player spawn more visible
            if is_player:
                # Player spawn: larger, brighter, with special marker
                ax.scatter(pos[0], pos[2], s=400, c='#00FF00', marker='*', 
                          edgecolors='black', linewidth=3,
                          label='Player Spawn' if not hasattr(ax, '_player_labeled') else "",
                          zorder=15, alpha=0.9)
                ax._player_labeled = True
                
                # Add circle around player spawn for visibility
                circle = plt.Circle((pos[0], pos[2]), 2000, fill=False, 
                                   color='#00FF00', linewidth=3, 
                                   linestyle='--', alpha=0.8, zorder=14)
                ax.add_patch(circle)
                
                # Add label
                ax.annotate('PLAYER', (pos[0], pos[2]), 
                           xytext=(0, -30), textcoords='offset points',
                           ha='center', fontsize=12, fontweight='bold',
                           bbox=dict(boxstyle="round,pad=0.5", 
                                    facecolor='#00FF00', alpha=0.8,
                                    edgecolor='black', linewidth=2),
                           zorder=16, color='black')
            else:
                # Regular units
                ax.scatter(pos[0], pos[2], s=100, c=color, marker='o', 
                          edgecolors='black', linewidth=1,
                          label=label if not hasattr(ax, f'_{team.lower()}_labeled') else "",
                          zorder=8)
                setattr(ax, f'_{team.lower()}_labeled', True)
            
            # Facing indicator (small arrow) - skip for player to avoid clutter
            if rot and len(rot) >= 2 and not is_player:
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
                # Make waypoints smaller and less intrusive
                ax.scatter(pos[0], pos[2], s=40, c=self.colors['waypoints'], 
                          marker='^', edgecolors='black', linewidth=0.5, alpha=0.7,
                          label='Waypoints' if i == 0 else "", zorder=9)
                
                # Only show waypoint numbers for first few waypoints to reduce clutter
                if i < 10:  # Only label first 10 waypoints
                    ax.annotate(f'{i+1}', (pos[0], pos[2]), 
                               xytext=(0, 8), textcoords='offset points',
                               ha='center', fontsize=6, fontweight='normal', alpha=0.8)
        
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
        """Create objectives layer with enhanced visibility."""
        if not self.has_mission_data:
            return
            
        objectives = getattr(self.mission, 'objectives', [])
        if not objectives:
            return
            
        self.logger.info(f"Drawing {len(objectives)} objectives...")
        
        # Get mission units for target resolution
        mission_units = {}
        if hasattr(self.mission, 'units'):
            if isinstance(self.mission.units, dict):
                for unit_entry in self.mission.units.values():
                    if isinstance(unit_entry, dict):
                        unit_obj = unit_entry.get('unit_obj')
                        unit_id = unit_entry.get('unitInstanceID')
                    else:
                        unit_obj = getattr(unit_entry, 'unit_obj', None)
                        unit_id = getattr(unit_entry, 'unitInstanceID', None)
                    if unit_obj and unit_id is not None:
                        mission_units[unit_id] = unit_obj
            elif isinstance(self.mission.units, list):
                for unit_entry in self.mission.units:
                    if isinstance(unit_entry, dict):
                        unit_obj = unit_entry.get('unit_obj')
                        unit_id = unit_entry.get('unitInstanceID')
                    else:
                        unit_obj = getattr(unit_entry, 'unit_obj', None)
                        unit_id = getattr(unit_entry, 'unitInstanceID', None)
                    if unit_obj and unit_id is not None:
                        mission_units[unit_id] = unit_obj
        
        for i, obj in enumerate(objectives):
            obj_name = getattr(obj, 'name', f'Objective {i+1}')
            obj_type = getattr(obj, 'type', 'Unknown')
            obj_required = getattr(obj, 'required', True)
            
            # Collect all positions for this objective
            objective_positions = []
            
            # 1. Check for direct position attribute
            if hasattr(obj, 'position') and obj.position:
                objective_positions.append(obj.position)
            
            # 2. Check for waypoint reference
            elif hasattr(obj, 'waypoint') and obj.waypoint:
                wpt_ref = obj.waypoint
                if hasattr(wpt_ref, 'global_point'):
                    objective_positions.append(wpt_ref.global_point)
                elif hasattr(wpt_ref, 'position'):
                    objective_positions.append(wpt_ref.position)
                elif isinstance(wpt_ref, (int, str)) and self.mission.waypoints:
                    # Find waypoint by ID
                    for wp in self.mission.waypoints:
                        wp_id = getattr(wp, 'id', None)
                        if wp_id == wpt_ref or str(wp_id) == str(wpt_ref):
                            if hasattr(wp, 'global_point'):
                                objective_positions.append(wp.global_point)
                            elif hasattr(wp, 'position'):
                                objective_positions.append(wp.position)
                            break
            
            # 3. For Destroy objectives, find target units via fields['targets']
            if obj_type == "Destroy" and hasattr(obj, 'fields') and isinstance(obj.fields, dict):
                targets_str = obj.fields.get('targets', '')
                if targets_str:
                    # Parse semicolon-separated target IDs: "id1;id2;"
                    target_ids = [tid.strip() for tid in targets_str.split(';') if tid.strip()]
                    for target_id_str in target_ids:
                        try:
                            target_id = int(target_id_str)
                            # Find unit with this ID
                            if target_id in mission_units:
                                unit_obj = mission_units[target_id]
                                if hasattr(unit_obj, 'global_position'):
                                    pos = unit_obj.global_position
                                    if pos and len(pos) >= 3:
                                        objective_positions.append(pos)
                        except (ValueError, TypeError):
                            # Try string matching
                            for uid, unit_obj in mission_units.items():
                                unit_name = getattr(unit_obj, 'unit_name', '')
                                if str(target_id_str) in str(unit_name) or str(target_id_str) == str(uid):
                                    if hasattr(unit_obj, 'global_position'):
                                        pos = unit_obj.global_position
                                        if pos and len(pos) >= 3:
                                            objective_positions.append(pos)
                                            break
            
            # 4. Fallback: check waypoint_id attribute
            if not objective_positions and hasattr(obj, 'waypoint_id') and self.mission.waypoints:
                for wp in self.mission.waypoints:
                    wp_id = getattr(wp, 'id', None)
                    if wp_id == obj.waypoint_id or str(wp_id) == str(obj.waypoint_id):
                        if hasattr(wp, 'global_point'):
                            objective_positions.append(wp.global_point)
                        elif hasattr(wp, 'position'):
                            objective_positions.append(wp.position)
                        break
            
            # Draw objective markers at all found positions
            if objective_positions:
                # Use different colors for required vs optional
                marker_color = '#FF0000' if obj_required else '#FFA500'  # Red for required, orange for optional
                marker_size = 200 if obj_required else 150
                
                for j, pos in enumerate(objective_positions):
                    # Extract x, z coordinates (y is altitude)
                    x = pos[0] if len(pos) > 0 else 0
                    z = pos[2] if len(pos) > 2 else pos[1] if len(pos) > 1 else 0
                    
                    # Draw large star marker
                    ax.scatter(x, z, s=marker_size, c=marker_color, 
                              marker='*', edgecolors='black', linewidth=2,
                              label='Objectives (Required)' if i == 0 and j == 0 and obj_required else 
                                     'Objectives (Optional)' if i == 0 and j == 0 and not obj_required else "",
                              zorder=12, alpha=0.9)
                    
                    # Draw circle around objective for visibility (scale to map size)
                    map_size = self.tc.total_map_size_meters if hasattr(self.tc, 'total_map_size_meters') else 200000
                    circle_radius = max(1000, map_size * 0.01)  # 1% of map size, minimum 1km
                    circle = plt.Circle((x, z), circle_radius, fill=False, 
                                       color=marker_color, linewidth=2, 
                                       linestyle='--', alpha=0.6, zorder=11)
                    ax.add_patch(circle)
                    
                    # Objective label with number (more subtle)
                    label_text = f"{i+1}" if len(objective_positions) == 1 else f"{i+1}-{j+1}"
                    ax.annotate(label_text, (x, z), 
                               xytext=(8, 8), textcoords='offset points',
                               fontsize=8, fontweight='normal',
                               bbox=dict(boxstyle="round,pad=0.2", 
                                        facecolor='white', alpha=0.7,
                                        edgecolor=marker_color, linewidth=1),
                               zorder=13, color='black')
            else:
                # No position found - log warning but don't draw
                self.logger.debug(f"Objective '{obj_name}' has no position information")
    
    def _create_territories_layer(self, ax, world_state=None):
        """Create territories layer showing friendly, enemy, and neutral zones."""
        # Get world state from mission if available
        if world_state is None:
            if hasattr(self.mission, 'world_state'):
                world_state = self.mission.world_state
            elif hasattr(self.mission, 'wsm'):
                world_state = self.mission.wsm
            else:
                return
        
        if not hasattr(world_state, 'territory_zones'):
            return
        
        self.logger.info("Drawing territory zones...")
        
        territory_colors = {
            'friendly': self.colors['friendly_territory'],
            'enemy': self.colors['enemy_territory'],
            'neutral': self.colors['neutral_territory']
        }
        
        territory_labels = {
            'friendly': 'Friendly Territory',
            'enemy': 'Enemy Territory',
            'neutral': 'Neutral Territory'
        }
        
        from pytol.misc.math_utils import is_position_in_circle
        
        # Draw territories in order: friendly, enemy, neutral
        for territory_type in ['friendly', 'enemy', 'neutral']:
            zones = world_state.territory_zones.get(territory_type, [])
            if not zones:
                continue
            
            color = territory_colors.get(territory_type, '#808080')
            label = territory_labels.get(territory_type, territory_type)
            labeled = False
            
            for zone in zones:
                if zone.get('type') == 'circle':
                    center = zone['center']
                    radius = zone['radius']
                    
                    # Draw filled circle
                    circle = patches.Circle(
                        center, radius,
                        color=color, alpha=0.2, edgecolor=color, linewidth=2,
                        label=label if not labeled else "", zorder=2
                    )
                    ax.add_patch(circle)
                    labeled = True
                    
                elif zone.get('type') == 'polygon':
                    vertices = zone.get('vertices', [])
                    if len(vertices) >= 3:
                        # Close the polygon if not already closed
                        if vertices[0] != vertices[-1]:
                            vertices = vertices + [vertices[0]]
                        
                        # Draw filled polygon
                        polygon = patches.Polygon(
                            vertices,
                            color=color, alpha=0.2, edgecolor=color, linewidth=2,
                            label=label if not labeled else "", zorder=2
                        )
                        ax.add_patch(polygon)
                        labeled = True
    
    def _create_key_points_layer(self, ax, world_state=None):
        """Create layer showing mission key points (strategic locations)."""
        # Get world state from mission if available
        if world_state is None:
            if hasattr(self.mission, 'world_state'):
                world_state = self.mission.world_state
            elif hasattr(self.mission, 'wsm'):
                world_state = self.mission.wsm
            else:
                return
        
        # Try to get mission key points from assets
        key_points = None
        try:
            if hasattr(world_state, 'assets'):
                key_points_asset = world_state.assets.get('mission_key_points')
                if key_points_asset and isinstance(key_points_asset, dict):
                    key_points = key_points_asset.get('points')
        except Exception:
            pass
        
        if not key_points:
            return
        
        self.logger.info(f"Drawing {len(key_points)} mission key points...")
        
        # Different markers/colors for different point types
        point_styles = {
            'objective': {'marker': '*', 'color': '#9900CC', 'size': 150},
            'threat': {'marker': 'X', 'color': '#FF0000', 'size': 120},
            'defense': {'marker': 's', 'color': '#0066CC', 'size': 100},
            'staging': {'marker': '^', 'color': '#00AA00', 'size': 100},
        }
        
        for point_id, point_info in key_points.items():
            pos = point_info.get('position')
            if not pos or len(pos) < 3:
                continue
            
            point_type = point_info.get('type', 'objective')
            mission_role = point_info.get('mission_role', '')
            radius = point_info.get('radius', 5000)
            priority = point_info.get('priority', 5)
            
            # Get style for this point type
            style = point_styles.get(point_type, point_styles['objective'])
            
            # Draw influence radius circle (semi-transparent)
            circle = patches.Circle(
                (pos[0], pos[2]), radius,
                color=style['color'], alpha=0.1, edgecolor=style['color'], 
                linewidth=1, linestyle='--', zorder=1
            )
            ax.add_patch(circle)
            
            # Draw key point marker
            ax.scatter(pos[0], pos[2], s=style['size'], c=style['color'],
                      marker=style['marker'], edgecolors='black', linewidth=1.5,
                      label=f'Key Point ({point_type})' if point_id == list(key_points.keys())[0] else "",
                      zorder=10)
            
            # Label with priority/role
            label_text = f"{mission_role}\nP{priority}" if mission_role else f"P{priority}"
            ax.annotate(label_text, (pos[0], pos[2]),
                       xytext=(5, 5), textcoords='offset points',
                       fontsize=7, fontweight='bold',
                       bbox=dict(boxstyle="round,pad=0.2", 
                                facecolor='white', alpha=0.8, edgecolor=style['color']))
    
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
        
        # Add roads, territories, cities
        self._create_roads_layer(ax)
        self._create_territories_layer(ax)
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
        
        self.logger.info(f"Terrain overview saved: {filename}")
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
        
        # Create figure with wider layout to accommodate objectives panel on the right
        # Use gridspec for better control over layout
        from matplotlib.gridspec import GridSpec
        fig = plt.figure(figsize=(self.figsize[0] * 1.8, self.figsize[1]), dpi=self.dpi)
        gs = GridSpec(1, 2, figure=fig, width_ratios=[2, 1.8], wspace=0.1)
        
        # Main map axis (left side)
        ax = fig.add_subplot(gs[0])
        
        # Create all layers (order matters: terrain first as background)
        cs = None
        if not clean_mode:
            # Make terrain more visible with higher alpha and ensure it's background layer
            cs = self._create_terrain_layer(ax, style=terrain_style, alpha=0.85)
        
        # Get world state for layers that need it
        world_state = None
        if hasattr(self.mission, 'world_state'):
            world_state = self.mission.world_state
        elif hasattr(self.mission, 'wsm'):
            world_state = self.mission.wsm
        
        self._create_roads_layer(ax)
        self._create_territories_layer(ax, world_state=world_state)
        self._create_key_points_layer(ax, world_state=world_state)
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
        
        # Legend (move to upper left to avoid overlap with objectives panel)
        ax.legend(loc='upper left', framealpha=0.9, fontsize=10)
        
        # Objectives information panel (right side)
        ax_info = fig.add_subplot(gs[1])
        ax_info.axis('off')  # Hide axes for text panel
        
        # Build objectives text
        objectives_text = ["MISSION OBJECTIVES", "=" * 30, ""]
        
        if hasattr(self.mission, 'objectives') and self.mission.objectives:
            for i, obj in enumerate(self.mission.objectives):
                obj_name = getattr(obj, 'name', f'Objective {i+1}')
                obj_type = getattr(obj, 'type', 'Unknown')
                obj_info = getattr(obj, 'info', '')
                obj_required = getattr(obj, 'required', True)
                obj_reward = getattr(obj, 'completionReward', 0)
                
                # Format objective entry
                required_str = "REQUIRED" if obj_required else "OPTIONAL"
                reward_str = f"Reward: {obj_reward}" if obj_reward > 0 else ""
                
                objectives_text.append(f"{i+1}. {obj_name}")
                objectives_text.append(f"   Type: {obj_type}")
                if obj_info:
                    # Wrap long info text
                    info_lines = obj_info.split('\n')
                    for line in info_lines[:3]:  # Limit to 3 lines
                        if len(line) > 50:
                            line = line[:47] + "..."
                        objectives_text.append(f"   {line}")
                objectives_text.append(f"   Status: {required_str}")
                if reward_str:
                    objectives_text.append(f"   {reward_str}")
                objectives_text.append("")
        else:
            objectives_text.append("No objectives defined")
        
        # Add mission briefing if available
        if hasattr(self.mission, 'description') and self.mission.description:
            objectives_text.append("")
            objectives_text.append("MISSION BRIEFING")
            objectives_text.append("=" * 30)
            # Wrap briefing text
            briefing = self.mission.description
            words = briefing.split()
            lines = []
            current_line = ""
            for word in words:
                if len(current_line + word) < 50:
                    current_line += word + " "
                else:
                    if current_line:
                        lines.append(current_line.strip())
                    current_line = word + " "
            if current_line:
                lines.append(current_line.strip())
            
            for line in lines[:8]:  # Limit to 8 lines
                objectives_text.append(line)
        
        # Display text
        full_text = "\n".join(objectives_text)
        ax_info.text(0.03, 0.97, full_text, transform=ax_info.transAxes,
                    fontsize=11, verticalalignment='top', family='monospace',
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
        
        # Use subplots_adjust instead of tight_layout for GridSpec
        plt.subplots_adjust(left=0.04, right=0.99, top=0.95, bottom=0.05, wspace=0.1)
        plt.savefig(filename, dpi=self.dpi, bbox_inches='tight')
        plt.close()
        
        self.logger.info(f"Mission overview saved: {filename}")
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
        
        self.logger.info(f"Spawn points detail saved: {filename}")
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
        
        self.logger.info(f"Terrain overview bytes created ({len(image_bytes)} bytes)")
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
        
        # Create all layers (order matters: terrain first as background)
        cs = None
        if not clean_mode:
            # Make terrain more visible with higher alpha and ensure it's background layer
            cs = self._create_terrain_layer(ax, style=terrain_style, alpha=0.85)
        self._create_roads_layer(ax)
        self._create_territories_layer(ax)
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
        
        self.logger.info(f"Mission overview bytes created ({len(image_bytes)} bytes)")
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
        
        self.logger.info(f"Spawn points detail bytes created ({len(image_bytes)} bytes)")
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