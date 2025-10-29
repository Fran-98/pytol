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


def _heightmap_to_rgb(heightmap: np.ndarray, min_h: float, max_h: float, size: Tuple[int, int]):
    """Convert a numeric heightmap to an RGB image with a gentle color ramp
    and hillshading to accentuate relief.

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
    # Note: callers may pass min_h/max_h; if they are None fall back to 0..1 mapping
    if max_h is None:
        max_h = float(np.nanmax(heightmap))
    if min_h is None:
        min_h = float(np.nanmin(heightmap))

    elev = gray * (max_h - min_h) + min_h

    # Separate water (elev <= 0) from land for different palettes
    # Treat exact sea level (0.0) as water as requested
    water_mask = elev <= 0.0

    # Land normalized between 0..1 relative to sea level..max_h
    land_norm = np.zeros_like(elev)
    if max_h > 0:
        land_norm = np.clip((elev - 0.0) / (max_h - 0.0 + 1e-12), 0.0, 1.0)
    else:
        land_norm = np.clip((elev - min_h) / (max_h - min_h + 1e-12), 0.0, 1.0)

    rgb = np.zeros((target_h, target_w, 3), dtype=np.float32)

    # Land ramp (0..1): low green -> brown -> rock -> snow
    land_ramp = [
        (0.00, (50, 160, 60)),
        (0.35, (160, 120, 80)),
        (0.65, (140, 140, 140)),
        (0.90, (220, 220, 220)),
        (1.00, (245, 245, 255)),
    ]

    for i in range(len(land_ramp) - 1):
        v0, c0 = land_ramp[i]
        v1, c1 = land_ramp[i + 1]
        mask = (~water_mask) & (land_norm >= v0) & (land_norm <= v1)
        if not np.any(mask):
            continue
        t = (land_norm[mask] - v0) / (v1 - v0 + 1e-12)
        c0 = np.array(c0, dtype=np.float32).reshape(1, 3)
        c1 = np.array(c1, dtype=np.float32).reshape(1, 3)
        interp = c0 * (1.0 - t.reshape(-1, 1)) + c1 * t.reshape(-1, 1)
        rgb[mask] = interp

    # Water ramp: shallow (shore) -> deep blue
    if np.any(water_mask):
        # depth normalized to min_h (e.g., min_h negative)
        depth = np.clip(-elev[water_mask] / (abs(min_h) + 1e-12), 0.0, 1.0)
        # shallow: sandy (200,200,120) -> deep: (10,30,120)
        c_shore = np.array((200, 200, 120), dtype=np.float32)
        c_deep = np.array((10, 30, 120), dtype=np.float32)
        interp = c_shore * (1.0 - depth.reshape(-1, 1)) + c_deep * depth.reshape(-1, 1)
        rgb[water_mask] = interp

    # Convert to 0..1 floats
    rgb = np.clip(rgb / 255.0, 0.0, 1.0)

    # Modulate brightness by hillshade to accentuate relief
    shade_factor = 0.5 + 0.9 * (shade - 0.5)
    shade_factor = np.clip(shade_factor, 0.2, 2.0)
    rgb_shaded = rgb * shade_factor[:, :, None]
    rgb_shaded = np.clip(rgb_shaded, 0.0, 1.0)

    # NOTE: iso/contour overlay removed - user requested no iso lines for clarity

    # Final contrast/gamma
    gamma = 0.95
    rgb_out = (rgb_shaded ** gamma) * 255.0
    return Image.fromarray(rgb_out.astype(np.uint8), mode='RGB')


class MapPillowVisualizer:
    """Tiny mission visualizer using Pillow.

    Args:
        mission_or_terrain: Mission object or TerrainCalculator instance
        size: (width, height) in pixels for the output image
        verbose: whether to log progress
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

        # Font for labels (Pillow default)
        try:
            self._font = ImageFont.load_default()
        except Exception:
            self._font = None
        # axis flip controls (useful because different maps/editor exports
        # may have different coordinate handedness)
        self.flip_x = flip_x
        self.flip_y = flip_y

    def save_terrain_overview(self, filename: Optional[str] = None, save: bool = False) -> Image:
        """Create a terrain-only overview using the heightmap.

        By default this returns the in-memory PIL Image. If `save=True`, the
        image will be written to `filename` (which must be provided).
        """
        hm = getattr(self.tc, 'heightmap_data_r', None)
        if hm is None:
            raise ValueError("Terrain object has no heightmap_data_r")

        img = _heightmap_to_rgb(hm, getattr(self.tc, 'min_height', 0.0), getattr(self.tc, 'max_height', 1.0), self.size)
        if save:
            if not filename:
                raise ValueError("filename must be provided when save=True")
            img.save(filename)
            self.logger.info(f"✓ Terrain overview saved: {filename}")
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
            base = _heightmap_to_rgb(hm, getattr(self.tc, 'min_height', 0.0), getattr(self.tc, 'max_height', 1.0), self.size)
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
            # Terrain coordinates are typically centered around 0. Map extents
            # go from -map_size/2 .. +map_size/2. Convert to pixel coords
            half = map_size * 0.5
            px = int(((x + half) / map_size) * w)
            pz = int(((z + half) / map_size) * h)
            # Pillow origin is top-left; adjust orientation to match editor.
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
            if not hasattr(self.tc, 'road_segments') or not self.tc.road_segments:
                return
            # Make roads more visible: scale width with image size
            base_width = max(3, int((w / 1024.0) * 8))
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
                    # outline then core to make roads pop
                    draw.line(pts, fill=(20, 20, 20), width=base_width + 4)
                    draw.line(pts, fill=(240, 200, 100), width=max(2, base_width))

                    # For short segments draw endpoint caps so small stretches are visible
                    try:
                        for p in pts:
                            draw.ellipse((p[0] - base_width, p[1] - base_width, p[0] + base_width, p[1] + base_width), fill=(240,200,100), outline=(20,20,20))
                    except Exception:
                        pass

        def _draw_cities():
            if not hasattr(self.tc, 'city_blocks') or not self.tc.city_blocks:
                return
            # City blocks in the TerrainCalculator may be stored in several
            # formats. Commonly we have dicts with 'world_position' or
            # 'pixel_coord'. Draw a small green square for each city tile so
            # they are visible over the terrain.
            pad_px = max(3, int((w / 1024.0) * 4))
            for block in self.tc.city_blocks:
                try:
                    if isinstance(block, dict):
                        wp = block.get('world_position') or block.get('position')
                        if wp:
                            bx, _, bz = wp
                            px, pz = world_to_px(bx, bz)
                        else:
                            pc = block.get('pixel_coord')
                            if pc:
                                px, pz = int(pc[0]), int(pc[1])
                            else:
                                continue
                    elif hasattr(block, '__len__') and len(block) >= 3:
                        # fallback for array-like entries
                        bx, _, bz = block[0], block[1], block[2]
                        px, pz = world_to_px(bx, bz)
                    else:
                        continue
                except Exception:
                    continue

                # Draw a green city tile (slightly darker outline)
                lx = px - pad_px
                ty = pz - pad_px
                rx = px + pad_px
                by = pz + pad_px
                try:
                    draw.rectangle((lx, ty, rx, by), fill=(160, 160, 160), outline=(0, 0, 0), width=1)
                except TypeError:
                    draw.rectangle((lx, ty, rx, by), fill=(160, 160, 160), outline=(0, 0, 0))

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

        # Draw helper layers first (roads and cities)
        try:
            _draw_roads()
            _draw_cities()
        except Exception:
            pass

        # Draw units
        units = getattr(self.mission, 'units', [])
        for u in units:
            unit = u if not isinstance(u, dict) else u.get('unit_obj', u)
            pos = getattr(unit, 'global_position', None)
            if not pos:
                continue
            x, _, z = pos
            px, pz = world_to_px(x, z)
            team = getattr(unit, 'team', 'Allied')
            if team.lower() in ['allied', 'player']:
                # Friendly color (brighter green)
                color = (0, 200, 100)
            elif team.lower() == 'enemy':
                color = (204, 0, 0)
            else:
                color = (128, 128, 128)

            r = max(6, int((w / 1024.0) * 8))
            # Draw core with a narrow black outline (width=1) for all units
            try:
                draw.ellipse((px - r, pz - r, px + r, pz + r), fill=color, outline=(0, 0, 0), width=1)
            except TypeError:
                # Older Pillow may not support width param; fall back to basic outline
                draw.ellipse((px - r, pz - r, px + r, pz + r), fill=color, outline=(0, 0, 0))

            # Draw facing as a short line
            rot = getattr(unit, 'rotation', [0, 0, 0])
            if rot and len(rot) >= 2:
                yaw = rot[1]
                dx = int(math.cos(math.radians(yaw)) * (r * 2.4))
                dy = -int(math.sin(math.radians(yaw)) * (r * 2.4))
                draw.line((px, pz, px + dx, pz + dy), fill=color, width=2)

        # Waypoints
        waypoints = getattr(self.mission, 'waypoints', [])
        for i, wp in enumerate(waypoints):
            gp = getattr(wp, 'global_point', None) or getattr(wp, 'position', None)
            if not gp:
                continue
            px, pz = world_to_px(gp[0], gp[2])
            draw.polygon([(px, pz - 6), (px + 6, pz + 6), (px - 6, pz + 6)], fill=(255, 140, 0), outline=(0,0,0))
            if self._font:
                draw.text((px + 8, pz - 8), str(i + 1), fill=(0, 0, 0), font=self._font)

        # Draw bases on top of units/waypoints so they are visible
        try:
            _draw_bases()
        except Exception:
            pass

        # Draw legend in top-left corner
        try:
            legend_items = [
                ("Water", (40, 80, 180)),
                ("Lowland", (50, 160, 60)),
                ("Highland", (220, 220, 220)),
                ("Road", (240, 200, 100)),
                ("City", (160, 160, 160)),
                ("Base", (255, 215, 0)),
                ("Allied Unit", (0, 160, 60)),
                ("Enemy Unit", (204, 0, 0)),
                ("Waypoint", (255, 140, 0)),
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
            self.logger.info(f"✓ Mission overview saved: {filename}")

        # Always return the PIL Image (callers can decide to save or not).
        return base


def save_mission_map(mission_or_terrain, filename: Optional[str] = None, size: Tuple[int, int] = (1024, 1024), save: bool = False) -> Image:
    """Convenience helper: creates a MapPillowVisualizer and returns the overview Image.

    By default the image is not saved to disk. Pass `save=True` and a
    `filename` to write the PNG to disk.
    """
    viz = MapPillowVisualizer(mission_or_terrain, size=size)
    return viz.save_mission_overview(filename=filename, save=save)
