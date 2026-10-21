"""Smoke test of MissionTerrainHelper on hMap2 (needs VTOL_VR_DIR with CustomMaps/hMap2)."""
import os
import random

import numpy as np
import pytest

from pytol.terrain.terrain_calculator import TerrainCalculator
from pytol.terrain.mission_terrain_helper import MissionTerrainHelper


@pytest.fixture(scope='module')
def helper():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    path = os.path.join(os.getenv('VTOL_VR_DIR', '').strip().strip('"'), 'CustomMaps', 'hMap2')
    if not os.path.isdir(path):
        pytest.skip("hMap2 not available")
    random.seed(1)
    return MissionTerrainHelper(TerrainCalculator(map_directory_path=path, verbose=False))


def test_line_of_sight_blocked_by_ridge(helper):
    peak = helper.find_highest_point_in_area(54406.57, 110333.51, 10000)
    a, b = np.array(peak), np.array(peak)
    a[0] -= 3000; b[0] += 3000
    a[1] = helper.tc.get_terrain_height(a[0], a[2]) + 2
    b[1] = helper.tc.get_terrain_height(b[0], b[2]) + 2
    over = (peak[0], peak[1] + 500, peak[2])
    assert helper.has_line_of_sight(over, (peak[0] + 100, peak[1] + 500, peak[2]))
    if a[1] < peak[1] - 50 and b[1] < peak[1] - 50:
        assert not helper.has_line_of_sight(a, b)


def test_roads_and_bridges(helper):
    tc = helper.tc
    assert tc.bridge_segments, "bridges not detected"
    s = tc.road_graph_segments
    route = helper.get_road_path(tuple(s[0]['points'][0][[0, 2]]), tuple(s[311]['points'][-1][[0, 2]]))
    assert len(route) > 20
    hit = helper.get_nearest_road_point(*route[3][::2])
    assert hit['distance'] < 1.0
    br = tc.bridge_segments[0]
    mid = (br['start'] + br['end']) / 2
    assert tc.get_smart_placement(mid[0], mid[2], 0)['type'] in ('bridge', 'static_prefab_roof')


def test_buildings_and_garrison(helper):
    base = helper.tc.get_all_static_prefabs()[0]
    found = helper.get_buildings_in_area(base['position'][0], base['position'][2], 3000)
    statics = [b for b in found if b['type'] == 'static_prefab']
    assert statics
    blocks = [b for b in helper.get_buildings_in_area(57036.29, 115526.57, 3000) if b['type'] == 'city_block']
    if blocks:
        assert helper.get_building_garrison_points(blocks[0])


def test_tactical_methods_exist(helper):
    for name in ('find_defensive_position', 'assess_airbase_suitability', 'find_tactical_positions'):
        assert hasattr(helper, name)
