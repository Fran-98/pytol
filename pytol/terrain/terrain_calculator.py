# -*- coding: utf-8 -*-
"""
Terrain, city, road and static prefab reconstruction for VTOL VR heightmap maps.

Mirrors the game code (decompiled):
- Height:   VTMapGenerator.GetHeightmapAltitude -> lerp(-80, 6000, R) sampled bilinearly, max(0, h).
- Flatten:  VTTModFlatRect (airbases, docks) flattens a local rect and blends over flattenRadius.
- Cities:   VTMapCities.ProcessChunk -> one CityBuilderPixel per vertex whose 2x2 pixel quad has G > 0.1.
- Roads:    BezierRoads segments (s, m, e) linked by ns/ps, Intersection nodes and shared endpoints.
"""
import os
import heapq

import numpy as np
from PIL import Image
from scipy.ndimage import map_coordinates
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation as R

from ..parsers.vtm_parser import parse_vtol_data
from ..resources.resources import get_city_layout_database, get_prefab_database, get_noise_image
from ..misc.logger import create_logger

CHUNK_SIZE = 3072.0
VERTS_PER_SIDE = 20  # VTMapCities uses 20 heightmap pixels per chunk
METERS_PER_PIXEL = CHUNK_SIZE / VERTS_PER_SIDE
# VTMapGenerator.hm_minHeight / hm_maxHeight: constants, not stored in the .vtm.
HM_MIN_HEIGHT = -80.0
HM_MAX_HEIGHT = 6000.0
# Local position of every CityBuilderPixel 'RotationTf' (== CityBuilderPixel.pixelCenterPoint).
# Layout DB bounds are relative to this transform; the prefab root sits on the pixel vertex.
CITY_PIXEL_CENTER = np.array([87.75, 0.0, 63.75])
BEZIER_SAMPLES = 5
# VTMapEdStructurePrefab flatten data (prefab YAML: doFlatten, flattenRect center/extents, flattenRadius).
# Only these prefabs have doFlatten = 1.
FLATTEN_PREFABS = {
    'airbase1': {'center': (288.73, -122.06), 'extents': (905.4, 1795.76), 'radius': 579.7},
    'airbase2': {'center': (72.0, 26.42), 'extents': (791.2, 1534.7), 'radius': 550.0},
    'airbase3': {'center': (428.0, -314.0), 'extents': (1660.1, 2042.17), 'radius': 580.0},
    'dock1': {'center': (0.0, -206.0), 'extents': (223.63, 150.0), 'radius': 71.0},
}
BASE_KEYWORDS = ('airbase', 'carrier', 'fob')


def _as_list(node):
    if node is None or node == '':
        return []
    return node if isinstance(node, list) else [node]


def unity_euler_to_matrix(euler_xyz):
    """Unity Euler (x, y, z) degrees -> rotation matrix. Unity applies Z, then X, then Y."""
    x, y, z = euler_xyz
    return R.from_euler('YXZ', [y, x, z], degrees=True).as_matrix()


def normal_to_euler_angles(terrain_normal, yaw_degrees):
    """Unity Euler (pitch, yaw, roll) that yaws an object then tilts its up axis onto terrain_normal."""
    up = np.array([0.0, 1.0, 0.0])
    n = np.asarray(terrain_normal, dtype=float)
    n = n / np.linalg.norm(n) if np.linalg.norm(n) > 1e-6 else up
    axis = np.cross(up, n)
    angle = np.arccos(np.clip(np.dot(up, n), -1.0, 1.0))
    tilt = R.from_rotvec(axis / np.linalg.norm(axis) * angle) if np.linalg.norm(axis) > 1e-6 else R.identity()
    yaw, pitch, roll = (tilt * R.from_euler('Y', yaw_degrees, degrees=True)).as_euler('YXZ', degrees=True)
    return (float(pitch), float(yaw % 360.0), float(roll % 360.0))


def get_bezier_point(s, m, e, t):
    """Point on a quadratic Bezier curve."""
    t = np.clip(t, 0, 1)
    return (1 - t) ** 2 * s + 2 * (1 - t) * t * m + t ** 2 * e


def _box_corners(b):
    """Bounds [minx, maxx, miny, maxy, minz, maxz] -> 8 corners."""
    return np.array([[x, y, z] for x in b[0:2] for y in b[2:4] for z in b[4:6]])


class TerrainCalculator:
    """Terrain height/normals plus city blocks, roads, bases and static prefab surfaces of a custom map."""

    def __init__(self, map_name: str = '', map_directory_path: str = '', vtol_directory: str = '', verbose: bool = True):
        self.verbose = verbose
        self.logger = create_logger(verbose=verbose, name="TerrainCalculator")

        if map_directory_path:
            self.map_dir = map_directory_path
            self.map_name = os.path.basename(os.path.normpath(map_directory_path))
        elif map_name and (vtol_directory or os.getenv('VTOL_VR_DIR')):
            self.map_dir = os.path.join(os.path.normpath(vtol_directory or os.getenv('VTOL_VR_DIR')), 'CustomMaps', map_name)
            self.map_name = map_name
        else:
            raise ValueError("Either 'map_directory_path' or both 'map_name' and 'vtol_directory' must be provided.")

        self.logger.info(f"Initializing TerrainCalculator for: {self.map_dir}")
        self._load_vtm_file()
        self._load_textures()
        self.city_layouts_db = get_city_layout_database()
        self.layouts_by_level = self.city_layouts_db['layouts_by_level']
        self.layout_data_db = self.city_layouts_db['layout_data']
        self.individual_prefabs_db = get_prefab_database()

        self.flatten_mods = self._process_flatten_mods()
        self.bases = self._process_bases()
        self.city_blocks = self._generate_all_city_blocks()
        self.static_surfaces = self._process_static_prefabs()
        self.road_segments = self._process_all_roads()
        self._road_p1 = np.array([[s[0][0], s[0][2]] for s in self.road_segments]).reshape(-1, 2)
        self._road_p2 = np.array([[s[1][0], s[1][2]] for s in self.road_segments]).reshape(-1, 2)

        self.logger.info(f"Map Size: {self.total_map_size_meters / 1000.0:.1f} km ({self.map_size_grids} grids)")
        self.logger.info(f"Processed {len(self.city_blocks)} city blocks, {len(self.static_surfaces)} static surfaces, "
                         f"{len(self.road_segments)} road segments ({len(self.bridge_segments)} on bridges), "
                         f"{len(self.bases)} bases.")

    # --- Loading ---
    def _load_vtm_file(self):
        vtm_path = os.path.join(self.map_dir, self.map_name + ".vtm")
        with open(vtm_path, 'r', encoding='utf-8') as f:
            self.map_data = parse_vtol_data(f.read()).get('VTMapCustom')
        if not self.map_data:
            raise ValueError("The .vtm file does not contain 'VTMapCustom' data.")
        self.map_size_grids = int(self.map_data['mapSize'])
        self.chunk_size_meters = CHUNK_SIZE
        self.total_map_size_meters = self.map_size_grids * CHUNK_SIZE
        self.min_height, self.max_height = HM_MIN_HEIGHT, HM_MAX_HEIGHT
        # ponytail: edge blending (VTTHeightMap.GetBlendedHeight) toward out-of-bounds terrain is not modelled;
        # only the outer ~5% of the map differs. Needs the game's OOB heightmap for edgeMode=Hills.
        self.edge_mode = self.map_data.get('edgeMode', 'Water')

    def _load_textures(self):
        # Unity textures have a bottom-left origin, so flip rows: data[py, px] == Texture2D.GetPixel(px, py).
        with Image.open(os.path.join(self.map_dir, 'height.png')) as image:
            rgb = np.flipud(np.array(image.convert('RGB'))).astype(np.float32) / 255.0
        self.heightmap_data_r, self.heightmap_data_g = rgb[:, :, 0], rgb[:, :, 1]
        self.hm_height, self.hm_width = self.heightmap_data_r.shape
        noise = np.array(get_noise_image().convert('RGB'))[:, :, 0]
        self.noise_texture_data = np.flipud(noise).astype(np.float32) / 255.0
        self.noise_height, self.noise_width = self.noise_texture_data.shape

    # --- Static prefabs, bases and terrain flattening ---
    def get_all_static_prefabs(self):
        return [{'prefab_id': p.get('prefab'), 'id': p.get('id'), 'base_name': p.get('baseName'),
                 'position': [float(c) for c in p.get('globalPos', (0, 0, 0))],
                 'rotation_euler': [float(r) for r in p.get('rotation', (0, 0, 0))]}
                for p in _as_list(self.map_data.get('StaticPrefabs', {}).get('StaticPrefab'))]

    def _process_flatten_mods(self):
        mods = []
        for p in self.get_all_static_prefabs():
            f = FLATTEN_PREFABS.get(p['prefab_id'])
            if f:
                mods.append({'position': np.array(p['position']), 'world_to_local': unity_euler_to_matrix(p['rotation_euler']).T,
                             'center': np.array(f['center']), 'extents': np.array(f['extents']), 'radius': f['radius']})
        return mods

    def _apply_flatten(self, world_x, world_z, h):
        """VTTModFlatRect.ApplyHeightMod: flat inside the rect, linear blend out to `radius` from its edge."""
        for m in self.flatten_mods:
            local = m['world_to_local'] @ (np.stack([world_x - m['position'][0], np.zeros_like(world_x),
                                                     world_z - m['position'][2]]))
            outside = np.abs(np.stack([local[0], local[2]]) - m['center'][:, None]) - m['extents'][:, None]
            dist = np.linalg.norm(np.maximum(outside, 0), axis=0)
            t = np.clip(dist / m['radius'], 0, 1)
            h = m['position'][1] + t * (h - m['position'][1])
        return h

    def _process_bases(self):
        """Bases (airbases, carriers, FOBs) with their flatten rectangle as a world-space XZ polygon."""
        bases = []
        for p in self.get_all_static_prefabs():
            name = (p['prefab_id'] or '').lower()
            if not any(k in name for k in BASE_KEYWORDS):
                continue
            rot = unity_euler_to_matrix(p['rotation_euler'])
            f = FLATTEN_PREFABS.get(p['prefab_id'])
            if f:
                (cx, cz), (ex, ez) = f['center'], f['extents']
                x_min, x_max, z_min, z_max = cx - ex, cx + ex, cz - ez, cz + ez
            else:
                key = f"bases/{p['prefab_id']}.prefab"
                bounds = [s['bounds'] for s in self.individual_prefabs_db.get(key, [])] or [[-500, 500, 0, 0, -1000, 1000]]
                x_min, x_max = min(b[0] for b in bounds), max(b[1] for b in bounds)
                z_min, z_max = min(b[4] for b in bounds), max(b[5] for b in bounds)
            corners = np.array([[x_min, 0, z_min], [x_max, 0, z_min], [x_max, 0, z_max], [x_min, 0, z_max]]) @ rot.T + p['position']
            bases.append({
                'id': p['id'], 'name': p['base_name'] or f"Base {p['id']}", 'prefab_type': p['prefab_id'],
                'position': p['position'], 'rotation': p['rotation_euler'],
                'footprint': {'x_min': x_min, 'x_max': x_max, 'z_min': z_min, 'z_max': z_max,
                              'width': x_max - x_min, 'length': z_max - z_min},
                'flatten_zone': [[float(c[0]), float(c[2])] for c in corners],
                'flatten_height': float(p['position'][1]),
            })
        return bases

    def get_all_bases(self):
        return self.bases.copy()

    def get_base_by_id(self, base_id):
        return next((b.copy() for b in self.bases if b['id'] == base_id), None)

    def get_base_by_name(self, name):
        return next((b.copy() for b in self.bases if name.lower() in b['name'].lower()), None)

    def get_nearest_base(self, world_x, world_z):
        if not self.bases:
            return None, None
        d = [np.hypot(b['position'][0] - world_x, b['position'][2] - world_z) for b in self.bases]
        i = int(np.argmin(d))
        return self.bases[i].copy(), float(d[i])

    def _process_static_prefabs(self):
        name_to_key = {os.path.splitext(os.path.basename(k))[0]: k for k in self.individual_prefabs_db}
        surfaces = []
        for idx, p in enumerate(self.get_all_static_prefabs()):
            key = name_to_key.get(p['prefab_id'])
            if not key:
                continue
            rot, pos = unity_euler_to_matrix(p['rotation_euler']), np.array(p['position'])
            for s in self.individual_prefabs_db[key]:
                corners = _box_corners(s['bounds']) @ rot.T + pos
                lo, hi = corners.min(axis=0), corners.max(axis=0)
                surfaces.append({'name': s.get('go_name', 'N/A'), 'prefab_name': p['prefab_id'], 'prefab_index': idx,
                                 'world_bounds': [float(v) for v in (*lo, *hi)], 'is_spawnable': s.get('is_spawnable', False)})
        return surfaces

    # --- Heightmap ---
    def get_terrain_height(self, world_x, world_z):
        """Ground height (VTMapGenerator.GetHeightmapAltitude plus base flattening). Accepts scalars or arrays."""
        x, z = np.atleast_1d(np.asarray(world_x, dtype=float)), np.atleast_1d(np.asarray(world_z, dtype=float))
        px = np.clip(x / self.total_map_size_meters * (self.hm_width - 1), 0, self.hm_width - 1)
        py = np.clip(z / self.total_map_size_meters * (self.hm_height - 1), 0, self.hm_height - 1)
        r = map_coordinates(self.heightmap_data_r, [py, px], order=1, mode='nearest')
        h = np.maximum(0.0, self.min_height + r * (self.max_height - self.min_height))
        h = self._apply_flatten(x, z, h)
        return float(h[0]) if np.ndim(world_x) == 0 else h

    def get_terrain_normal(self, world_x, world_z, delta=1.0):
        h0 = self.get_terrain_height(world_x, world_z)
        hx = self.get_terrain_height(world_x + delta, world_z)
        hz = self.get_terrain_height(world_x, world_z + delta)
        normal = np.cross([0, hz - h0, delta], [delta, hx - h0, 0])
        mag = np.linalg.norm(normal)
        return normal / mag if mag > 0 else np.array([0.0, 1.0, 0.0])

    def get_asset_placement(self, world_x, world_z, yaw_degrees):
        h = self.get_terrain_height(world_x, world_z)
        return {'position': (world_x, h, world_z),
                'rotation': normal_to_euler_angles(self.get_terrain_normal(world_x, world_z), yaw_degrees)}

    # --- Cities ---
    @staticmethod
    def _world_to_pixel(world_x, world_z):
        """Pixel whose vertex is at or below/left of the point (floor)."""
        return int(np.floor(world_x / METERS_PER_PIXEL)), int(np.floor(world_z / METERS_PER_PIXEL))

    def _city_pixel_g(self, px, py):
        """G of pixel if its 2x2 quad is all city (VTMapCities rule), else 0."""
        if px < 0 or py < 0 or px >= self.hm_width - 1 or py >= self.hm_height - 1:
            return 0.0
        g = self.heightmap_data_g
        quad = (g[py, px], g[py, px + 1], g[py + 1, px + 1], g[py + 1, px])
        return float(quad[0]) if min(quad) > 0.1 else 0.0

    def _city_layout_at_pixel(self, px, py):
        density = self._city_pixel_g(px, py)
        if density <= 0.1:
            return None
        city_level = int(np.clip(np.floor((density - 0.2) / 0.8 * 5.0), 0, 4))
        layouts = self.layouts_by_level.get(str(city_level))
        if not layouts:
            return None
        noise = self.noise_texture_data[py % self.noise_height, px % self.noise_width]
        layout_guid = layouts[int(np.clip(np.floor(noise * len(layouts)), 0, len(layouts) - 1))]
        surfaces = self.layout_data_db.get(layout_guid)
        if surfaces is None:
            return None
        # CityBuilderPixel.SetRotation
        if px % 2 == 0:
            yaw = 0.0 if py % 2 == 0 else 90.0
        else:
            yaw = -90.0 if py % 2 == 0 else 180.0
        return {'layout_guid': layout_guid, 'surfaces': surfaces, 'block_yaw_degrees': yaw,
                'city_level': city_level, 'pixel_coords': (px, py)}

    def _block_pivot(self, px, py):
        """World position of the block's RotationTf (origin of the layout bounds)."""
        vx, vz = px * METERS_PER_PIXEL, py * METERS_PER_PIXEL
        return np.array([vx, self.get_terrain_height(vx, vz), vz]) + CITY_PIXEL_CENTER

    def get_city_density(self, world_x, world_z):
        return self._city_pixel_g(*self._world_to_pixel(world_x, world_z))

    def get_city_layout_at(self, world_x, world_z):
        return self._city_layout_at_pixel(*self._world_to_pixel(world_x, world_z))

    def _generate_all_city_blocks(self):
        g = self.heightmap_data_g
        quad = (g[:-1, :-1] > 0.1) & (g[:-1, 1:] > 0.1) & (g[1:, 1:] > 0.1) & (g[1:, :-1] > 0.1)
        blocks = []
        for py, px in zip(*np.nonzero(quad)):
            info = self._city_layout_at_pixel(int(px), int(py))
            if info:
                blocks.append({'pixel_coord': (int(px), int(py)),
                               'world_position': tuple(float(v) for v in self._block_pivot(px, py)),
                               'layout_guid': info['layout_guid'], 'yaw_degrees': info['block_yaw_degrees'],
                               'city_level': info['city_level']})
        return blocks

    def get_all_city_blocks(self):
        return self.city_blocks

    # --- Roads ---
    def _process_all_roads(self):
        """(start, end) polylines for Bezier roads and the procedural city street grid.

        Also builds `road_graph_segments` (Bezier segment id -> points/length/links), `road_segment_ids`
        (road id per polyline, None for city streets) and `bridge_segments`.
        """
        segments, ids, bridges = [], [], []
        roads = self.map_data.get('BezierRoads', {})
        self.road_graph_segments = {}
        for chunk in _as_list(roads.get('Chunk')):
            for seg in _as_list(chunk.get('Segment')):
                s, m, e = (np.array(seg[k], dtype=float) for k in ('s', 'm', 'e'))
                pts = [get_bezier_point(s, m, e, t) for t in np.linspace(0, 1, BEZIER_SAMPLES)]
                is_bridge = seg.get('bridge') is True
                self.road_graph_segments[seg['id']] = {'points': pts, 'length': float(seg.get('length', 0.0)),
                                                       'ns': seg.get('ns'), 'ps': seg.get('ps'), 'is_bridge': is_bridge}
                for a, b in zip(pts, pts[1:]):
                    segments.append((a, b))
                    ids.append(seg['id'])
                    if is_bridge:
                        bridges.append({'start': a, 'end': b, 'road_id': seg['id']})
        self.road_intersections = [[int(i) for i in _as_list(x.get('segments'))] for x in _as_list(roads.get('Intersection'))]
        self.bridge_segments = bridges

        # ponytail: city streets are approximated as lines between block pivots; the real geometry lives in the layout meshes.
        pos = {b['pixel_coord']: np.array(b['world_position']) for b in self.city_blocks}
        for (px, py), a in pos.items():
            b, c, d = pos.get((px + 1, py)), pos.get((px, py + 1)), pos.get((px + 1, py + 1))
            if b is None or c is None or d is None:
                continue
            if py % 2:
                segments.append((np.array([a[0], 0, (a[2] + c[2]) / 2]), np.array([b[0], 0, (b[2] + d[2]) / 2])))
                ids.append(None)
            if px % 2:
                segments.append((np.array([(a[0] + b[0]) / 2, 0, a[2]]), np.array([(c[0] + d[0]) / 2, 0, c[2]])))
                ids.append(None)
        self.road_segment_ids = ids
        self._road_is_bezier = np.array([i is not None for i in ids], dtype=bool)
        return segments

    def get_all_bridges(self):
        return self.bridge_segments

    def nearest_road(self, world_x, world_z, bezier_only=False):
        """Closest road polyline: {'segment_index', 'position' (x, y, z), 'distance', 'road_id', 'is_bridge'} or None."""
        if not len(self.road_segments) or (bezier_only and not self._road_is_bezier.any()):
            return None
        p = np.array([world_x, world_z])
        d = self._road_p2 - self._road_p1
        len_sq = np.einsum('ij,ij->i', d, d)
        t = np.clip(np.einsum('ij,ij->i', p - self._road_p1, d) / np.where(len_sq == 0, 1, len_sq), 0, 1)
        closest = self._road_p1 + t[:, None] * d
        dist_sq = np.einsum('ij,ij->i', closest - p, closest - p)
        if bezier_only:
            dist_sq = np.where(self._road_is_bezier, dist_sq, np.inf)
        i = int(np.argmin(dist_sq))
        road_id = self.road_segment_ids[i]
        is_bridge = road_id is not None and self.road_graph_segments[road_id]['is_bridge']
        if is_bridge:
            a, b = self.road_segments[i]
            y = float(a[1] + t[i] * (b[1] - a[1]))
        else:
            y = self.get_terrain_height(closest[i, 0], closest[i, 1])
        return {'segment_index': i, 'position': (float(closest[i, 0]), y, float(closest[i, 1])),
                'distance': float(np.sqrt(dist_sq[i])), 'road_id': road_id, 'is_bridge': is_bridge}

    def is_on_road(self, world_x, world_z, tolerance=10.0):
        hit = self.nearest_road(world_x, world_z)
        return bool(hit and hit['distance'] < tolerance)

    def _road_neighbors(self):
        if getattr(self, '_neighbors_cache', None) is None:
            nb = {sid: set() for sid in self.road_graph_segments}
            for sid, seg in self.road_graph_segments.items():
                for n in (seg['ns'], seg['ps']):
                    if n in nb:
                        nb[sid].add(n)
                        nb[n].add(sid)
            for group in self.road_intersections:
                for a in group:
                    if a in nb:
                        nb[a].update(b for b in group if b != a and b in nb)
            # Many segments only share an endpoint (no ns/ps link), so also join coincident endpoints.
            ends = [(sid, p) for sid, seg in self.road_graph_segments.items() for p in (seg['points'][0], seg['points'][-1])]
            if ends:
                for i, j in cKDTree([p for _, p in ends]).query_pairs(r=2.0):
                    a, b = ends[i][0], ends[j][0]
                    if a != b:
                        nb[a].add(b)
                        nb[b].add(a)
            self._neighbors_cache = nb
        return self._neighbors_cache

    def get_road_route(self, start_xz, end_xz):
        """Shortest path over the Bezier road network (Dijkstra on segment ids). Returns [(x, y, z), ...] or []."""
        start = self.nearest_road(*start_xz, bezier_only=True)
        end = self.nearest_road(*end_xz, bezier_only=True)
        if not start or not end:
            return []
        start_id, end_id = start['road_id'], end['road_id']
        neighbors = self._road_neighbors()
        dist, prev, queue = {start_id: 0.0}, {}, [(0.0, start_id)]
        while queue:
            d, sid = heapq.heappop(queue)
            if sid == end_id:
                break
            if d > dist.get(sid, np.inf):
                continue
            for n in neighbors[sid]:
                nd = d + self.road_graph_segments[n]['length']
                if nd < dist.get(n, np.inf):
                    dist[n], prev[n] = nd, sid
                    heapq.heappush(queue, (nd, n))
        if end_id not in dist:
            return []
        chain = [end_id]
        while chain[-1] != start_id:
            chain.append(prev[chain[-1]])
        chain.reverse()

        route = []
        for sid in chain:
            pts = self.road_graph_segments[sid]['points']
            if route and np.linalg.norm(route[-1] - pts[-1]) < np.linalg.norm(route[-1] - pts[0]):
                pts = pts[::-1]  # segment stored in the opposite direction
            route.extend(pts if not route else pts[1:])
        return [(float(p[0]), float(p[1]), float(p[2])) for p in route]

    # --- Placement ---
    def get_smart_placement(self, world_x, world_z, yaw_degrees):
        """Placement on a static prefab roof, bridge/road, city roof, or terrain (in that priority)."""
        best_y, best_name = -np.inf, None
        for s in self.static_surfaces:
            b = s['world_bounds']
            if s['is_spawnable'] and b[0] <= world_x <= b[3] and b[2] <= world_z <= b[5] and b[4] > best_y:
                best_y, best_name = b[4], f"{s['prefab_name']}/{s['name']}"
        if best_name:
            return {'type': 'static_prefab_roof', 'position': (world_x, best_y, world_z),
                    'rotation': (0.0, yaw_degrees, 0.0), 'snapped_to_building': best_name}

        road = self.nearest_road(world_x, world_z)
        if road and road['distance'] < 10.0:
            if road['is_bridge']:
                return {'type': 'bridge', 'position': (world_x, road['position'][1], world_z), 'rotation': (0.0, yaw_degrees, 0.0)}
            return {**self.get_asset_placement(world_x, world_z, yaw_degrees), 'type': 'road'}

        px, py = self._world_to_pixel(world_x, world_z)
        layout = self._city_layout_at_pixel(px, py)
        if layout:
            pivot = self._block_pivot(px, py)
            rot = R.from_euler('Y', layout['block_yaw_degrees'], degrees=True).as_matrix()
            best_y, best_name = -np.inf, None
            for s in layout['surfaces']:
                b = s.get('bounds_rel_layout', [])
                if len(b) != 6 or not s.get('is_spawnable'):
                    continue
                corners = _box_corners(b) @ rot.T + pivot
                lo, hi = corners.min(axis=0), corners.max(axis=0)
                if lo[0] <= world_x <= hi[0] and lo[2] <= world_z <= hi[2] and hi[1] > best_y:
                    best_y, best_name = hi[1], s.get('go_name', 'N/A')
            if best_name:
                return {'type': 'city_roof', 'position': (world_x, float(best_y), world_z),
                        'rotation': (0.0, yaw_degrees, 0.0), 'snapped_to_building': best_name}

        return {**self.get_asset_placement(world_x, world_z, yaw_degrees), 'type': 'terrain'}
