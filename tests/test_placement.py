"""MissionTerrainHelper placement queries."""
import os
import random

import numpy as np
import pytest

from pytol import Mission


@pytest.fixture(scope='module')
def helper():
    vtol = os.getenv('VTOL_VR_DIR', '').strip().strip('"')
    path = os.getenv('PYTOL_TEST_MAP') or os.path.join(vtol, 'CustomMaps', 'hMap2')
    if not os.path.isdir(path):
        pytest.skip("hMap2 not available (set VTOL_VR_DIR or PYTOL_TEST_MAP)")
    m = Mission(scenario_name="p", scenario_id="p", description="", vehicle="F/A-26B", map_id="hMap2", map_path=path,
                vtol_directory="", verbose=False)
    return m.helper


def test_open_land_is_dry_clear_and_reproducible(helper):
    size = helper.tc.total_map_size_meters
    p = helper.find_open_land(size / 2, size / 2, 6000, footprint=20.0, rng=random.Random(1))
    assert p is not None and helper.is_land(p[0], p[2]) and helper.tc.is_area_clear(p[0], p[2], 20.0)
    assert p == helper.find_open_land(size / 2, size / 2, 6000, footprint=20.0, rng=random.Random(1))
    taken = helper.find_open_land(size / 2, size / 2, 6000, rng=random.Random(1), is_free=lambda x, z, r: False)
    assert taken is None  # the caller's own occupancy test is honored


def test_band_and_offsets(helper):
    size = helper.tc.total_map_size_meters
    c = (size / 2, 0.0, size / 2)
    p = helper.find_land_in_band(c, 3000, 5000, random.Random(2))
    assert p is not None and 3000 <= np.hypot(p[0] - c[0], p[2] - c[2]) <= 5000
    q = helper.point_along((50000.0, 0.0, 50000.0), (60000.0, 0.0, 50000.0), 4000, side=1000)
    assert abs(q[0] - 54000) < 1 and abs(q[2] - 49000) < 1  # 4 km east, 1 km to the right (south) of an eastbound leg


def test_water_queries_on_land_return_none(helper):
    size = helper.tc.total_map_size_meters
    land = helper.find_open_land(size / 2, size / 2, 6000, rng=random.Random(3))
    assert not helper.is_water(land[0], land[2])
    assert helper.water_loop(land, 500.0) is None
