"""
Lightweight 2D visualization using Pillow (PIL).

This module provides a very small, dependency-light alternative to the
matplotlib-based `Map2DVisualizer`. It renders a top-down image of the
terrain and mission objects using Pillow and numpy. Intended for web
export or when matplotlib is not available.

API:
 - MapPillowVisualizer(mission_or_terrain, size=(1024,1024))
 - save_mission_map(..., flip_x=False, flip_y=True)  # helper passes flips through
 - save_terrain_overview(filename)
 - save_mission_overview(filename)

Notes:
 - This intentionally implements a small feature subset (terrain heatmap,
   units, waypoints, static prefabs). For richer visuals use the
   matplotlib visualizer.
"""
from typing import Tuple, Optional
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import math
from ..misc.logger import create_logger


def _heightmap_to_rgb(heightmap: np.ndarray, min_h: float, max_h: float, size: Tuple[int, int], style: str = 'heatmap'):
    """Convert a numeric heightmap to an RGB image matching matplotlib's terrain visualization.
    
    Matches matplotlib's Map2DVisualizer terrain rendering with:
    - Water zones (below 0m): Blue shades (#1E4E79)
    - Sand/beach zones (0-10m): Sand color (#D2B48C)
    - Terrain zones (above 10m): Green -> Brown -> White terrain colormap

    This function accepts either 0..1 float arrays or 0..255 uint8 arrays.
    It resizes to the requested pixel size, computes a simple hillshade
    from gradients, and modulates a color ramp by the shade to improve
    mountains/valleys visibility.
    """
    # Normalize to 0..1
    h = heightmap.astype(np.float32)
    vmax = float(np.nanmax(h))
    if vmax > 1.5:
        h = h / 255.0
    else:
        h = np.clip(h, 0.0, 1.0)

    target_w, target_h = size[0], size[1]
    # Resize heightmap to target using Pillow bilinear for smoothness
    pil_h = Image.fromarray((h * 255).astype(np.uint8), mode='L')
    pil_h = pil_h.resize((target_w, target_h), resample=Image.BILINEAR)
    gray = np.array(pil_h).astype(np.float32) / 255.0

    # Compute simple hillshade: use gradients and a light vector
    # dz/dx, dz/dy (note: y axis is image row -> downwards)
    gy, gx = np.gradient(gray)  # gy: d/drow, gx: d/dcol
    # Light from northwest (azimuth 315 deg), altitude 45 deg
    az = np.deg2rad(315.0)
    alt = np.deg2rad(45.0)
    lx = np.cos(az) * np.cos(alt)
    ly = np.sin(az) * np.cos(alt)
    lz = np.sin(alt)
    # approximate normal vector from gradients
    nx = -gx
    ny = -gy
    nz = 1.0
    norm = np.sqrt(nx * nx + ny * ny + nz * nz) + 1e-8
    nx /= norm
    ny /= norm
    nz /= norm
    # dot product with light vector -> shade [-1,1]; scale to [0,1]
    shade = (nx * lx + ny * ly + nz * lz)
    shade = np.clip((shade + 1.0) * 0.5, 0.0, 1.0)

    # Compute actual elevation in meters from gray [0..1] using provided min/max
    if max_h is None:
        max_h = float(np.nanmax(heightmap))
    if min_h is None:
        min_h = float(np.nanmin(heightmap))

    elev = gray * (max_h - min_h) + min_h

    # Define elevation zones matching matplotlib (water < 0, sand 0-10, terrain > 10)
    water_mask = elev < 0.0
    sand_mask = (elev >= 0.0) & (elev <= 10.0)
    terrain_mask = elev > 10.0

    rgb = np.zeros((target_h, target_w, 3), dtype=np.float32)

    # Water zone: Match matplotlib's blue (#1E4E79 or #1F4E79)
    if np.any(water_mask):
        # Create gradient from shallow (lighter) to deep (darker blue)
        # Matplotlib uses #1E4E79 (30, 78, 121) or #1F4E79 (31, 78, 121)
        depth = np.clip(-elev[water_mask] / (abs(min_h) + 1e-12), 0.0, 1.0)
        c_shallow = np.array((46, 90, 130), dtype=np.float32)  # Slightly lighter for shallow
        c_deep = np.array((30, 78, 121), dtype=np.float32)      # #1E4E79
        interp = c_shallow * (1.0 - depth.reshape(-1, 1)) + c_deep * depth.reshape(-1, 1)
        rgb[water_mask] = interp

    # Sand/beach zone (0-10m): Match matplotlib's sand color #D2B48C (210, 180, 140)
    if np.any(sand_mask):
        sand_norm = (elev[sand_mask] - 0.0) / (10.0 - 0.0 + 1e-12)
        sand_color = np.array((210, 180, 140), dtype=np.float32)  # #D2B48C
        rgb[sand_mask] = sand_color

    # Terrain zone (>10m): Match matplotlib's terrain colormap
    # Low: #2E4A3D (46, 74, 61) -> Medium: #8B7355 (139, 115, 85) -> High: White
    if np.any(terrain_mask):
        terrain_min = 10.0
        terrain_span = max_h - terrain_min
        terrain_elevations = elev[terrain_mask]
        if terrain_span > 0:
            terrain_norm = (terrain_elevations - terrain_min) / (terrain_span + 1e-12)
        else:
            terrain_norm = np.zeros_like(terrain_elevations)
        terrain_norm = np.clip(terrain_norm, 0.0, 1.0)

        # Terrain ramp matching matplotlib: green -> brown -> white
        terrain_ramp = [
            (0.00, (46, 74, 61)),      # #2E4A3D - dark green (low terrain)
            (0.35, (139, 115, 85)),    # #8B7355 - brown (medium terrain)
            (0.65, (200, 200, 200)),   # Light gray (high terrain)
            (1.00, (255, 255, 255)),   # White (snow peaks)
        ]

        # Interpolate colors for terrain pixels
        for i in range(len(terrain_ramp) - 1):
            v0, c0 = terrain_ramp[i]
            v1, c1 = terrain_ramp[i + 1]
            mask_inner = (terrain_norm >= v0) & (terrain_norm <= v1)
            if not np.any(mask_inner):
                continue
            
            t = (terrain_norm[mask_inner] - v0) / (v1 - v0 + 1e-12)
            c0_arr = np.array(c0, dtype=np.float32)
            c1_arr = np.array(c1, dtype=np.float32)
            interp = c0_arr * (1.0 - t[:, None]) + c1_arr * t[:, None]
            
            # Apply to the corresponding pixels in rgb array
            terrain_indices = np.where(terrain_mask)
            rgb[terrain_indices[0][mask_inner], terrain_indices[1][mask_inner]] = interp

    # Convert to 0..1 floats
    rgb = np.clip(rgb / 255.0, 0.0, 1.0)

    # Modulate brightness by hillshade to accentuate relief (lighter for this style)
    shade_factor = 0.6 + 0.7 * (shade - 0.5)
    shade_factor = np.clip(shade_factor, 0.3, 1.5)
    rgb_shaded = rgb * shade_factor[:, :, None]
    rgb_shaded = np.clip(rgb_shaded, 0.0, 1.0)

    # Final contrast/gamma
    gamma = 1.0  # Slightly brighter to match matplotlib
    rgb_out = (rgb_shaded ** gamma) * 255.0
    return Image.fromarray(rgb_out.astype(np.uint8), mode='RGB')


class MapPillowVisualizer:
    """Lightweight 2D mission visualizer using Pillow, matching matplotlib's Map2DVisualizer.
    
    Creates static top-down tactical maps showing:
    - Terrain elevation with water/sand/terrain zones (matching matplotlib)
    - City blocks (green=spawnable, red=obstacles)
    - Road network
    - Units with team colors and facing indicators
    - Waypoints and flight paths
    - Airbases with spawn points
    - Objectives and triggers
    - Territories (friendly/enemy/neutral zones)
    - Key points

    Args:
        mission_or_terrain: Mission object or TerrainCalculator instance
        size: (width, height) in pixels for the output image
        verbose: whether to log progress
        flip_x: Flip image horizontally
        flip_y: Flip image vertically
    """
    def __init__(self, mission_or_terrain, size: Tuple[int, int] = (1024, 1024), verbose: bool = True, flip_x: bool = False, flip_y: bool = True):
        self.size = size
        self.verbose = verbose
        self.logger = create_logger(verbose=verbose, name="MapPillow")

        if hasattr(mission_or_terrain, 'tc'):
            self.mission = mission_or_terrain
            self.tc = mission_or_terrain.tc
            self.has_mission_data = True
        else:
            self.mission = None
            self.tc = mission_or_terrain
            self.has_mission_data = False

        map_name = getattr(self.tc, 'map_name', getattr(self.tc, 'map_id', 'unknown'))
        self.logger.info(f"Initialized Pillow visualizer for map '{map_name}' size={self.size}")

        # Font for labels - try to load a better font if available
        try:
            self._font = ImageFont.load_default()
            # Try to load a truetype font if available (for better text rendering)
            try:
                self._font_large = ImageFont.truetype("arial.ttf", 12)
            except:
                self._font_large = self._font
        except Exception:
            self._font = None
            self._font_large = None
            
        # axis flip controls (useful because different maps/editor exports
        # may have different coordinate handedness)
        self.flip_x = flip_x
        self.flip_y = flip_y
        
        # Color scheme matching matplotlib's Map2DVisualizer exactly
        self.colors = {
            'terrain_low': (46, 74, 61),         # #2E4A3D - Dark green
            'terrain_high': (139, 115, 85),      # #8B7355 - Brown
            'water': (30, 78, 121),              # #1E4E79 - Deep blue
            'roads': (64, 64, 64),               # #404040 - Dark gray
            'city_spawnable': (40, 167, 69),     # #28A745 - Green
            'city_obstacle': (220, 53, 69),      # #DC3545 - Red
            'allied_units': (0, 102, 204),       # #0066CC - Blue
            'enemy_units': (204, 0, 0),          # #CC0000 - Red
            'neutral_units': (128, 128, 128),    # #808080 - Gray
            'waypoints': (255, 102, 0),          # #FF6600 - Orange
            'objectives': (153, 0, 204),         # #9900CC - Purple
            'airbases': (255, 215, 0),           # #FFD700 - Gold
            'friendly_territory': (0, 68, 170),  # #0044AA - Blue
            'enemy_territory': (170, 0, 0),      # #AA0000 - Red
            'neutral_territory': (128, 128, 128), # #808080 - Gray
        }

    def save_terrain_overview(self, filename: Optional[str] = None, save: bool = False, style: str = 'heatmap') -> Image:
        """Create a terrain-only overview using the heightmap, matching matplotlib's Map2DVisualizer.

        Args:
            filename: Output filename (required if save=True)
            save: Whether to save the image to disk
            style: Terrain style ('heatmap' or 'contour'). Note: Pillow implementation
                   uses heatmap-style rendering for both options.
        
        Returns:
            PIL Image object
        
        By default this returns the in-memory PIL Image. If `save=True`, the
        image will be written to `filename` (which must be provided).
        """
        hm = getattr(self.tc, 'heightmap_data_r', None)
        if hm is None:
            raise ValueError("Terrain object has no heightmap_data_r")

        img = _heightmap_to_rgb(hm, getattr(self.tc, 'min_height', 0.0), 
                               getattr(self.tc, 'max_height', 1.0), self.size, style=style)
        if save:
            if not filename:
                raise ValueError("filename must be provided when save=True")
            img.save(filename)
            self.logger.info(f"Terrain overview saved: {filename}")
        return img

    def save_mission_overview(self, filename: Optional[str] = None, save: bool = False, clean_mode: bool = False) -> Image:
        """Create a mission overview showing terrain, units and waypoints.

        Returns the PIL Image. If `save=True`, the image will be written to
        `filename` (which must be provided) and the same Image object is
        returned.
        """
        if not self.has_mission_data:
            raise ValueError("Mission data required for mission overview.")

        self.logger.info(f"Creating mission overview: {filename if save and filename else 'in-memory (not saved)'}")

        # Terrain background
        hm = getattr(self.tc, 'heightmap_data_r', None)
        if hm is not None and not clean_mode:
            base = _heightmap_to_rgb(hm, getattr(self.tc, 'min_height', 0.0), 
                                    getattr(self.tc, 'max_height', 1.0), self.size, style='heatmap')
        else:
            base = Image.new('RGB', self.size, (200, 200, 200))

        # If flip flags are set, flip the base heightmap image so the
        # terrain (heights) and overlays are flipped together.
        try:
            if getattr(self, 'flip_x', False):
                base = base.transpose(Image.FLIP_LEFT_RIGHT)
            if getattr(self, 'flip_y', True):
                base = base.transpose(Image.FLIP_TOP_BOTTOM)
        except Exception:
            # If transpose fails for any reason, continue without flipping
            pass

        # If the TerrainCalculator provides a G channel where green pixels
        # mark city density, overlay those pixels as city markers so the
        # visualizer matches the original heightmap's city depiction.
        try:
            if hasattr(self.tc, 'heightmap_data_g') and self.tc.heightmap_data_g is not None:
                # Create a mask image from the G channel and resize to output
                gchan = (self.tc.heightmap_data_g * 255.0).astype('uint8')
                gimg = Image.fromarray(gchan, mode='L')
                gimg = gimg.resize(self.size, resample=Image.NEAREST)
                # Apply same flips as the base so mask aligns
                try:
                    if getattr(self, 'flip_x', False):
                        gimg = gimg.transpose(Image.FLIP_LEFT_RIGHT)
                    if getattr(self, 'flip_y', True):
                        gimg = gimg.transpose(Image.FLIP_TOP_BOTTOM)
                except Exception:
                    pass

                mask_np = (np.array(gimg) > 64).astype('uint8')
                if np.any(mask_np):
                    # Build an RGBA overlay where city pixels are solid green
                    overlay_arr = np.zeros((self.size[1], self.size[0], 4), dtype='uint8')
                    # Use grey for city pixels to match original visualizer
                    overlay_arr[mask_np == 1, 0] = 160
                    overlay_arr[mask_np == 1, 1] = 160
                    overlay_arr[mask_np == 1, 2] = 160
                    overlay_arr[mask_np == 1, 3] = 255
                    overlay_img = Image.fromarray(overlay_arr, mode='RGBA')
                    base = base.convert('RGBA')
                    try:
                        base = Image.alpha_composite(base, overlay_img)
                    except Exception:
                        # fallback: paste using mask
                        base.paste(overlay_img, (0, 0), overlay_img)
                    base = base.convert('RGB')
        except Exception:
            # If anything goes wrong with city-overlay, continue without it
            pass

        draw = ImageDraw.Draw(base)

        # Coordinate mapping from world meters to pixels
        map_size = getattr(self.tc, 'total_map_size_meters', 1.0)
        w, h = self.size

        def world_to_px(x, z):
            # Match matplotlib's coordinate system: maps use 0 to map_size range
            # (see map2d.py: ax.set_xlim(0, self.tc.total_map_size_meters))
            # Convert world coordinates (0 to map_size) to pixel coordinates
            px = int((x / map_size) * w)
            pz = int((z / map_size) * h)
            
            # Pillow origin is top-left; matplotlib uses bottom-left origin by default.
            # To match matplotlib's visual layout, flip Y coordinate.
            # Honor instance flip flags so callers can control orientation.
            if getattr(self, 'flip_x', False):
                px = w - px
            if getattr(self, 'flip_y', True):
                pz = h - pz
            return px, pz

        # Debug: log flip settings and a couple of sample mappings to help
        # verify that flip flags have effect when running tests.
        try:
            self.logger.info(f"flip_x={getattr(self,'flip_x',False)} flip_y={getattr(self,'flip_y',True)}")
            sample_units = getattr(self.mission, 'units', [])[:2]
            for idx, u in enumerate(sample_units, start=1):
                unit = u if not isinstance(u, dict) else u.get('unit_obj', u)
                pos = getattr(unit, 'global_position', None)
                if pos:
                    mx = pos[0]
                    mz = pos[2]
                    self.logger.info(f"sample unit {idx} world=({mx:.1f},{mz:.1f}) -> px={world_to_px(mx,mz)}")
        except Exception:
            pass

        # Helper layers: roads, cities, bases
        def _draw_roads():
            """Draw road network matching matplotlib style."""
            if not hasattr(self.tc, 'road_segments') or not self.tc.road_segments:
                return
            self.logger.info(f"Drawing {len(self.tc.road_segments)} road segments...")
            # Make roads more visible: scale width with image size
            base_width = max(2, int((w / 1024.0) * 2))
            road_color = self.colors['roads']  # Dark gray #404040
            
            for seg in self.tc.road_segments:
                pts = []
                if isinstance(seg, (list, tuple)) and len(seg) >= 2 and not isinstance(seg[0], (int, float)):
                    for p in seg:
                        pts.append(world_to_px(p[0], p[2]))
                elif isinstance(seg, (list, tuple)) and len(seg) == 2:
                    a, b = seg
                    pts = [world_to_px(a[0], a[2]), world_to_px(b[0], b[2])]
                else:
                    continue
                if len(pts) >= 2:
                    # Draw road line matching matplotlib style (dark gray, thinner)
                    draw.line(pts, fill=road_color, width=base_width)

        def _draw_cities():
            """City blocks are represented by the grey pixels from heightmap G channel overlay.
            We don't draw individual building rectangles - just use the heightmap city overlay."""
            # City blocks are already represented by the heightmap G channel overlay
            # which is applied earlier in the function (lines 294-328)
            # No need to draw individual rectangles
            pass

        def _draw_bases():
            if not hasattr(self.tc, 'bases') or not self.tc.bases:
                return

            def _draw_star(cx, cy, r, fill=(255, 215, 0), outline=(0, 0, 0)):
                pts = []
                inner = r * 0.45
                for i in range(10):
                    angle = i * math.pi / 5.0 - math.pi / 2.0
                    rad = r if (i % 2 == 0) else inner
                    x = cx + math.cos(angle) * rad
                    y = cy + math.sin(angle) * rad
                    pts.append((x, y))
                # Draw filled star then a narrow black outline for clarity
                draw.polygon(pts, fill=fill)
                try:
                    # Connect points with a narrow line to outline the star
                    draw.line(pts + [pts[0]], fill=outline, width=1)
                except TypeError:
                    # Fallback: draw polygon with outline param (may be thicker)
                    draw.polygon(pts, fill=fill, outline=outline)

            for base in self.tc.bases:
                pos = base.get('position', [0, 0, 0])
                px, pz = world_to_px(pos[0], pos[2])
                r = max(10, int((w / 1024.0) * 12))
                _draw_star(px, pz, r, fill=(255, 215, 0), outline=(0, 0, 0))
                name = base.get('name') or base.get('id')
                if name and self._font:
                    draw.text((px + r + 4, pz - r), str(name), fill=(0, 0, 0), font=self._font)

        def _draw_territories():
            """Draw territory zones (friendly/enemy/neutral) matching matplotlib."""
            if not self.has_mission_data:
                return
            # Get world state from mission
            world_state = None
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
            
            from pytol.misc.math_utils import is_position_in_circle
            
            # Draw territories in order: friendly, enemy, neutral
            for territory_type in ['friendly', 'enemy', 'neutral']:
                zones = world_state.territory_zones.get(territory_type, [])
                if not zones:
                    continue
                
                color = territory_colors.get(territory_type, (128, 128, 128))
                
                for zone in zones:
                    try:
                        if zone.get('type') == 'circle':
                            center = zone['center']
                            radius = zone['radius']
                            cx, cz = center[0], center[2] if len(center) > 2 else center[1]
                            px, pz = world_to_px(cx, cz)
                            radius_px = int(radius * (w / map_size))
                            
                            # Draw filled circle with transparency (draw a semi-transparent overlay)
                            # Create a temporary image for alpha blending
                            overlay = Image.new('RGBA', (w, h), (0, 0, 0, 0))
                            overlay_draw = ImageDraw.Draw(overlay)
                            overlay_draw.ellipse((px - radius_px, pz - radius_px, px + radius_px, pz + radius_px),
                                                fill=(color[0], color[1], color[2], 51),  # ~20% alpha
                                                outline=(color[0], color[1], color[2], 200), width=2)
                            base = Image.alpha_composite(base.convert('RGBA'), overlay).convert('RGB')
                            draw = ImageDraw.Draw(base)
                            
                        elif zone.get('type') == 'polygon':
                            vertices = zone.get('vertices', [])
                            if len(vertices) >= 3:
                                # Convert vertices to pixel coordinates
                                pts = []
                                for v in vertices:
                                    vx, vz = v[0], v[2] if len(v) > 2 else v[1]
                                    pts.append(world_to_px(vx, vz))
                                if len(pts) >= 3:
                                    # Close polygon
                                    if pts[0] != pts[-1]:
                                        pts.append(pts[0])
                                    # Draw with transparency using overlay
                                    overlay = Image.new('RGBA', (w, h), (0, 0, 0, 0))
                                    overlay_draw = ImageDraw.Draw(overlay)
                                    overlay_draw.polygon(pts,
                                                        fill=(color[0], color[1], color[2], 51),
                                                        outline=(color[0], color[1], color[2], 200))
                                    base = Image.alpha_composite(base.convert('RGBA'), overlay).convert('RGB')
                                    draw = ImageDraw.Draw(base)
                    except Exception:
                        continue

        # Draw helper layers in correct order (terrain background already done)
        try:
            _draw_roads()
            _draw_territories()
            _draw_cities()
        except Exception:
            pass

        # CRITICAL: Recreate draw object after territories may have modified the base image
        # Territories use alpha_composite which creates a new image, so the draw object becomes stale
        draw = ImageDraw.Draw(base)

        def _draw_objectives():
            """Draw objectives matching matplotlib style."""
            nonlocal base, draw
            if not self.has_mission_data:
                return
            objectives = getattr(self.mission, 'objectives', [])
            if not objectives:
                self.logger.debug("No objectives found in mission")
                return
            self.logger.info(f"Drawing {len(objectives)} objectives...")
            
            for i, obj in enumerate(objectives):
                try:
                    # Try to get objective position from various sources
                    pos = None
                    
                    # 1. Direct position attribute
                    if hasattr(obj, 'position') and getattr(obj, 'position', None):
                        pos = obj.position
                    
                    # 2. Check waypoint attribute (can be Waypoint object or int ID)
                    elif hasattr(obj, 'waypoint') and getattr(obj, 'waypoint', None):
                        wpt_ref = obj.waypoint
                        if hasattr(wpt_ref, 'global_point'):
                            pos = wpt_ref.global_point
                        elif hasattr(wpt_ref, 'position'):
                            pos = wpt_ref.position
                        elif isinstance(wpt_ref, int) and self.mission.waypoints:
                            # Find waypoint by ID
                            matching_wpt = next((w for w in self.mission.waypoints 
                                               if getattr(w, 'id', None) == wpt_ref), None)
                            if matching_wpt:
                                pos = (getattr(matching_wpt, 'global_point', None) or 
                                      getattr(matching_wpt, 'position', None))
                    
                    # 3. Check for waypoint_id (fallback)
                    elif hasattr(obj, 'waypoint_id') and self.mission.waypoints:
                        wpt_id = obj.waypoint_id
                        for wp in self.mission.waypoints:
                            if getattr(wp, 'id', None) == wpt_id:
                                pos = (getattr(wp, 'global_point', None) or 
                                      getattr(wp, 'position', None))
                                break
                    
                    # 4. Check if objective targets units via fields['targets'] (Destroy objectives)
                    # targets can be a list like [1, 2, 3] or a string like "1;2;3;"
                    elif (hasattr(obj, 'fields') and isinstance(obj.fields, dict) and 
                          'targets' in obj.fields):
                        targets = obj.fields.get('targets')
                        self.logger.debug(f"Objective {i+1} has targets field: {targets} (type: {type(targets)})")
                        if isinstance(targets, str):
                            # Parse "1;2;3;" format
                            target_ids = [int(x.strip()) for x in targets.rstrip(';').split(';') 
                                        if x.strip().isdigit()]
                        elif isinstance(targets, list):
                            target_ids = [int(x) for x in targets if isinstance(x, (int, str)) and str(x).isdigit()]
                        else:
                            target_ids = []
                        
                        self.logger.debug(f"Objective {i+1} parsed target_ids: {target_ids}")
                        
                        # For Destroy objectives, use the first target unit's position
                        # Target IDs from VTS are unitInstanceIDs (integers, 1-indexed)
                        # Mission.units stores dicts with 'unitInstanceID' key
                        if target_ids and self.mission.units:
                            target_id = target_ids[0]
                            self.logger.debug(f"Looking for unit with instanceID {target_id} among {len(self.mission.units)} units")
                            for idx, u in enumerate(self.mission.units):
                                # Check if this unit's instance ID matches the target
                                matched = False
                                if isinstance(u, dict):
                                    # Units stored as dicts with 'unitInstanceID' key
                                    stored_id = u.get('unitInstanceID')
                                    self.logger.debug(f"  Unit {idx}: dict with unitInstanceID={stored_id}")
                                    if stored_id == target_id:
                                        matched = True
                                    # Also try index-based matching (unitInstanceID is 1-indexed)
                                    elif (idx + 1) == target_id:
                                        matched = True
                                        self.logger.debug(f"  Unit {idx}: matched by index (idx+1={idx+1} == target_id={target_id})")
                                else:
                                    # If not a dict, try index-based (shouldn't happen but be safe)
                                    self.logger.debug(f"  Unit {idx}: not a dict, trying index match")
                                    if (idx + 1) == target_id:
                                        matched = True
                                
                                if matched:
                                    unit = u if not isinstance(u, dict) else u.get('unit_obj', u)
                                    pos = getattr(unit, 'global_position', None)
                                    if pos is None and isinstance(u, dict):
                                        pos = u.get('lastValidPlacement')
                                    if pos:
                                        self.logger.info(f"Found position for objective '{getattr(obj, 'name', 'unknown')}' via target unit ID {target_id} at index {idx}: {pos}")
                                        break
                            else:
                                self.logger.warning(f"Could not find unit with instanceID {target_id} for objective {i+1}")
                    
                    # 5. Check if objective targets a single unit (get unit position)
                    elif hasattr(obj, 'target_unit_id') or (hasattr(obj, 'fields') and 
                          isinstance(obj.fields, dict) and 'target_unit_id' in obj.fields):
                        target_id = (getattr(obj, 'target_unit_id', None) or 
                                   obj.fields.get('target_unit_id'))
                        if target_id and self.mission.units:
                            # Find unit by ID
                            for u in self.mission.units:
                                unit = u if not isinstance(u, dict) else u.get('unit_obj', u)
                                unit_id = getattr(unit, 'unit_id', None) or getattr(unit, 'id', None) or getattr(unit, 'unit_instance_id', None)
                                if unit_id == target_id:
                                    pos = getattr(unit, 'global_position', None)
                                    if pos is None and isinstance(u, dict):
                                        pos = u.get('lastValidPlacement')
                                    break
                    
                    if not pos or len(pos) < 3:
                        self.logger.debug(f"Objective {i+1} ({getattr(obj, 'name', 'unknown')}) has no valid position")
                        continue
                    
                    # Convert position to float (handle numpy types)
                    try:
                        pos_x = float(pos[0])
                        pos_z = float(pos[2])
                    except (TypeError, ValueError, IndexError):
                        self.logger.warning(f"Objective {i+1} has invalid position format: {pos}")
                        continue
                    
                    # Check pixel bounds
                    margin = 50
                    px, pz = world_to_px(pos_x, pos_z)
                    if px < -margin or px >= w + margin or pz < -margin or pz >= h + margin:
                        continue
                    
                    obj_size = max(8, int((w / 1024.0) * 10))
                    
                    # Draw star marker matching matplotlib (* marker, purple color)
                    # Create a simple star shape
                    star_points = []
                    outer_radius = obj_size
                    inner_radius = obj_size * 0.4
                    for j in range(10):
                        angle = j * math.pi / 5.0 - math.pi / 2.0
                        radius = outer_radius if (j % 2 == 0) else inner_radius
                        star_points.append((px + int(math.cos(angle) * radius),
                                          pz + int(math.sin(angle) * radius)))
                    try:
                        draw.polygon(star_points, fill=self.colors['objectives'], outline=(0, 0, 0))
                    except:
                        # Fallback: simple circle if polygon fails
                        draw.ellipse((px - obj_size, pz - obj_size, px + obj_size, pz + obj_size),
                                   fill=self.colors['objectives'], outline=(0, 0, 0))
                    
                    # Add label
                    name = (getattr(obj, 'name', None) or 
                           getattr(obj, 'objective_name', None) or 
                           f'Obj {i+1}')
                    if self._font:
                        # Draw text with background for readability
                        try:
                            bbox = draw.textbbox((px + obj_size + 4, pz - obj_size), name, font=self._font)
                            draw.rectangle(bbox, fill=(255, 255, 255), outline=(0, 0, 0))
                            draw.text((px + obj_size + 4, pz - obj_size), name, fill=(0, 0, 0), font=self._font)
                        except AttributeError:
                            # Fallback for older Pillow
                            draw.text((px + obj_size + 4, pz - obj_size), name, fill=(0, 0, 0), font=self._font)
                    self.logger.debug(f"Drew objective {i+1} '{name}' at ({pos[0]:.1f}, {pos[2]:.1f})")
                except Exception as e:
                    self.logger.warning(f"Error drawing objective {i+1}: {e}")
                    continue

        def _draw_key_points():
            """Draw mission key points matching matplotlib style."""
            nonlocal base, draw
            if not self.has_mission_data:
                return
            # Get world state
            world_state = None
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
            
            point_styles = {
                'objective': {'marker_size': 150, 'color': (153, 0, 204)},  # Purple
                'threat': {'marker_size': 120, 'color': (255, 0, 0)},       # Red
                'defense': {'marker_size': 100, 'color': (0, 102, 204)},    # Blue
                'staging': {'marker_size': 100, 'color': (0, 170, 0)},      # Green
            }
            
            for point_id, point_info in key_points.items():
                try:
                    pos = point_info.get('position')
                    if not pos or len(pos) < 3:
                        continue
                    
                    point_type = point_info.get('type', 'objective')
                    radius = point_info.get('radius', 5000)
                    priority = point_info.get('priority', 5)
                    mission_role = point_info.get('mission_role', '')
                    
                    style = point_styles.get(point_type, point_styles['objective'])
                    px, pz = world_to_px(pos[0], pos[2])
                    
                    # Draw influence radius circle (semi-transparent)
                    radius_px = int(radius * (w / map_size))
                    overlay = Image.new('RGBA', (w, h), (0, 0, 0, 0))
                    overlay_draw = ImageDraw.Draw(overlay)
                    overlay_draw.ellipse((px - radius_px, pz - radius_px, px + radius_px, pz + radius_px),
                                        fill=(style['color'][0], style['color'][1], style['color'][2], 25),
                                        outline=(style['color'][0], style['color'][1], style['color'][2], 128))
                    base = Image.alpha_composite(base.convert('RGBA'), overlay).convert('RGB')
                    draw = ImageDraw.Draw(base)
                    
                    # Draw key point marker
                    marker_size = max(10, int((w / 1024.0) * (style['marker_size'] / 10)))
                    if point_type == 'objective':
                        # Star
                        star_points = []
                        for j in range(10):
                            angle = j * math.pi / 5.0 - math.pi / 2.0
                            rad = marker_size if (j % 2 == 0) else marker_size * 0.4
                            star_points.append((px + int(math.cos(angle) * rad),
                                              pz + int(math.sin(angle) * rad)))
                        draw.polygon(star_points, fill=style['color'], outline=(0, 0, 0))
                    elif point_type == 'threat':
                        # X marker
                        x_size = marker_size
                        draw.line((px - x_size, pz - x_size, px + x_size, pz + x_size),
                                 fill=style['color'], width=2)
                        draw.line((px - x_size, pz + x_size, px + x_size, pz - x_size),
                                 fill=style['color'], width=2)
                    else:
                        # Square or triangle
                        if point_type == 'defense':
                            # Square
                            draw.rectangle((px - marker_size, pz - marker_size, px + marker_size, pz + marker_size),
                                         fill=style['color'], outline=(0, 0, 0))
                        else:
                            # Triangle
                            draw.polygon([(px, pz - marker_size), (px + marker_size, pz + marker_size),
                                        (px - marker_size, pz + marker_size)],
                                       fill=style['color'], outline=(0, 0, 0))
                    
                    # Label with priority/role
                    label_text = f"{mission_role}\nP{priority}" if mission_role else f"P{priority}"
                    if self._font:
                        try:
                            bbox = draw.textbbox((px + marker_size + 4, pz - marker_size), label_text, font=self._font)
                            draw.rectangle(bbox, fill=(255, 255, 255), outline=style['color'])
                            draw.text((px + marker_size + 4, pz - marker_size), label_text,
                                    fill=(0, 0, 0), font=self._font)
                        except AttributeError:
                            # Fallback for older Pillow
                            draw.text((px + marker_size + 4, pz - marker_size), label_text,
                                    fill=(0, 0, 0), font=self._font)
                except Exception:
                    continue

        # Draw key points FIRST (they modify base with alpha_composite)
        # Note: This function uses nonlocal to update base and draw
        _draw_key_points()
        
        # CRITICAL: Recreate draw object after key_points may have modified base
        draw = ImageDraw.Draw(base)

        # Draw units and waypoints first
        
        # Draw units and waypoints (after objectives so they're visible, but objectives will be on top)
        if self.has_mission_data:
            units = getattr(self.mission, 'units', [])
            if units:
                self.logger.info(f"Drawing {len(units)} units...")
                for u in units:
                    try:
                        unit = u if not isinstance(u, dict) else u.get('unit_obj', u)
                        pos = getattr(unit, 'global_position', None)
                        if pos is None and isinstance(u, dict):
                            pos = u.get('lastValidPlacement')
                        
                        if not pos or len(pos) < 3:
                            continue
                        
                        # Check bounds
                        if pos[0] < 0 or pos[0] > map_size or pos[2] < 0 or pos[2] > map_size:
                            continue
                        
                        x, _, z = pos[0], pos[1], pos[2]
                        px, pz = world_to_px(x, z)
                        
                        # Check if pixel coordinates are within image bounds (with some margin for marker size)
                        margin = 50
                        if px < -margin or px >= w + margin or pz < -margin or pz >= h + margin:
                            continue
                        
                        team = getattr(unit, 'team', 'Allied')
                        
                        # Use color scheme matching matplotlib
                        if team.lower() in ['allied', 'player']:
                            color = self.colors['allied_units']
                        elif team.lower() == 'enemy':
                            color = self.colors['enemy_units']
                        else:
                            color = self.colors['neutral_units']

                        # Make units appropriately sized - not too big
                        r = max(6, int((w / 1024.0) * 8))  # ~16px radius for 2048px images (was too big)
                        
                        # Draw white background circle for visibility
                        bg_r = r + 2
                        try:
                            draw.ellipse((px - bg_r, pz - bg_r, px + bg_r, pz + bg_r), 
                                       fill=(255, 255, 255), outline=(0, 0, 0), width=1)
                        except TypeError:
                            draw.ellipse((px - bg_r, pz - bg_r, px + bg_r, pz + bg_r), 
                                       fill=(255, 255, 255), outline=(0, 0, 0))
                        
                        # Draw main unit circle
                        try:
                            draw.ellipse((px - r, pz - r, px + r, pz + r), 
                                       fill=color, outline=(0, 0, 0), width=2)
                        except TypeError:
                            draw.ellipse((px - r, pz - r, px + r, pz + r), fill=color)
                            # Draw outline manually for older Pillow
                            for outline_r in range(r, r + 2):
                                try:
                                    draw.ellipse((px - outline_r, pz - outline_r, px + outline_r, pz + outline_r), 
                                               outline=(0, 0, 0))
                                except:
                                    pass

                        # Draw facing indicator (arrow)
                        rot = getattr(unit, 'rotation', [0, 0, 0])
                        if rot and len(rot) >= 2:
                            yaw_rad = math.radians(rot[1])
                            arrow_len = r * 2.5  # Shorter arrow for smaller units
                            dx = int(math.cos(yaw_rad) * arrow_len)
                            dy = -int(math.sin(yaw_rad) * arrow_len)
                            draw.line((px, pz, px + dx, pz + dy), fill=color, width=2)
                            
                            # Arrowhead
                            arrow_head_len = max(3, r // 2)
                            arrow_angle = math.atan2(dy, dx)
                            head1_angle = arrow_angle + 2.5
                            head2_angle = arrow_angle - 2.5
                            head1_x = int((px + dx) + math.cos(head1_angle) * arrow_head_len)
                            head1_y = int((pz + dy) + math.sin(head1_angle) * arrow_head_len)
                            head2_x = int((px + dx) + math.cos(head2_angle) * arrow_head_len)
                            head2_y = int((pz + dy) + math.sin(head2_angle) * arrow_head_len)
                            try:
                                draw.polygon([(px + dx, pz + dy), (head1_x, head1_y), (head2_x, head2_y)], 
                                            fill=color, outline=(0, 0, 0))
                            except:
                                pass
                    except Exception as e:
                        self.logger.warning(f"Error drawing unit: {e}")
                        continue
        
        # Recreate draw after units (in case anything modified it)
        draw = ImageDraw.Draw(base)
        
        # Draw waypoints AFTER units so they're both on top
        waypoints = getattr(self.mission, 'waypoints', [])
        if waypoints:
            self.logger.info(f"Drawing {len(waypoints)} waypoints...")
        for i, wp in enumerate(waypoints):
            try:
                gp = getattr(wp, 'global_point', None) or getattr(wp, 'position', None)
                if not gp:
                    continue
                px, pz = world_to_px(gp[0], gp[2])
                
                # Check pixel bounds
                margin = 50
                if px < -margin or px >= w + margin or pz < -margin or pz >= h + margin:
                    continue
                
                # Make waypoints larger and more visible
                wp_size = max(14, int((w / 1024.0) * 18))  # Larger for visibility
                
                # Draw white background for visibility
                bg_size = wp_size + 4
                try:
                    draw.ellipse((px - bg_size, pz - bg_size, px + bg_size, pz + bg_size),
                               fill=(255, 255, 255), outline=(0, 0, 0), width=2)
                except TypeError:
                    draw.ellipse((px - bg_size, pz - bg_size, px + bg_size, pz + bg_size),
                               fill=(255, 255, 255), outline=(0, 0, 0))
                
                # Draw waypoint triangle (pointing up) with thick outline
                triangle_points = [
                    (px, pz - wp_size),           # Top point
                    (px + wp_size, pz + wp_size),  # Bottom right
                    (px - wp_size, pz + wp_size)   # Bottom left
                ]
                try:
                    draw.polygon(triangle_points, fill=self.colors['waypoints'], outline=(0, 0, 0), width=3)
                except TypeError:
                    # Draw filled then outline separately
                    draw.polygon(triangle_points, fill=self.colors['waypoints'])
                    # Draw thick outline
                    triangle_points_closed = triangle_points + [triangle_points[0]]
                    for j in range(len(triangle_points_closed) - 1):
                        draw.line(triangle_points_closed[j], triangle_points_closed[j + 1], 
                                fill=(0, 0, 0), width=3)
                
                # Add waypoint number label
                if self._font:
                    try:
                        label_text = str(i + 1)
                        # Draw text with background for readability
                        bbox = draw.textbbox((px + wp_size + 4, pz - wp_size), label_text, font=self._font)
                        draw.rectangle(bbox, fill=(255, 255, 255), outline=(0, 0, 0))
                        draw.text((px + wp_size + 4, pz - wp_size), label_text, 
                                fill=(0, 0, 0), font=self._font)
                    except (AttributeError, Exception):
                        # Fallback
                        draw.text((px + wp_size + 4, pz - wp_size), label_text, 
                                fill=(255, 255, 255), font=self._font)
            except Exception as e:
                self.logger.warning(f"Error drawing waypoint {i}: {e}")
                continue

        # Draw paths (flight paths between waypoints) matching matplotlib
        paths = getattr(self.mission, 'paths', [])
        if paths:
            self.logger.info(f"Drawing {len(paths)} paths...")
        for path in paths:
            try:
                points = getattr(path, 'points', [])
                if len(points) < 2:
                    continue
                pts_px = []
                for p in points:
                    px, pz = world_to_px(p[0], p[2])
                    pts_px.append((px, pz))
                if len(pts_px) >= 2:
                    # Draw line with waypoint color
                    draw.line(pts_px, fill=self.colors['waypoints'], width=3)
            except Exception:
                continue
        
        # Ensure draw is still current
        draw = ImageDraw.Draw(base)
        
        # Draw objectives LAST so they appear on top of everything (purple stars)
        _draw_objectives()
        
        # Recreate draw after objectives
        draw = ImageDraw.Draw(base)

        # Draw bases on top of units/waypoints so they are visible
        try:
            _draw_bases()
        except Exception:
            pass

        # Draw legend in top-left corner matching matplotlib style
        try:
            legend_items = [
                ("Water", self.colors['water']),
                ("Sand/Beach", (210, 180, 140)),  # #D2B48C
                ("Terrain", self.colors['terrain_low']),
                ("Road", self.colors['roads']),
                ("City (Spawn)", self.colors['city_spawnable']),
                ("City (Block)", self.colors['city_obstacle']),
                ("Base", self.colors['airbases']),
                ("Allied Unit", self.colors['allied_units']),
                ("Enemy Unit", self.colors['enemy_units']),
                ("Waypoint", self.colors['waypoints']),
                ("Objective", self.colors['objectives']),
            ]
            pad = 8
            sw = 18
            lh = 18
            x0 = pad
            y0 = pad
            box_w = 200
            box_h = len(legend_items) * lh + pad
            # background box
            draw.rectangle((x0 - 4, y0 - 4, x0 + box_w, y0 + box_h), fill=(250, 250, 250), outline=(120, 120, 120))
            for idx, (label, color) in enumerate(legend_items):
                cy = y0 + idx * lh
                draw.rectangle((x0, cy, x0 + sw, cy + sw), fill=color, outline=(0, 0, 0))
                if self._font:
                    draw.text((x0 + sw + 6, cy), label, fill=(0, 0, 0), font=self._font)
        except Exception:
            pass

        if save:
            if not filename:
                raise ValueError("filename must be provided when save=True")
            base.save(filename)
            self.logger.info(f"Mission overview saved: {filename}")

        # Always return the PIL Image (callers can decide to save or not).
        return base


def save_mission_map(mission_or_terrain, filename: Optional[str] = None, size: Tuple[int, int] = (1024, 1024), save: bool = False) -> Image:
    """Convenience helper: creates a MapPillowVisualizer and returns the overview Image.

    By default the image is not saved to disk. Pass `save=True` and a
    `filename` to write the PNG to disk.
    """
    viz = MapPillowVisualizer(mission_or_terrain, size=size)
    return viz.save_mission_overview(filename=filename, save=save)
