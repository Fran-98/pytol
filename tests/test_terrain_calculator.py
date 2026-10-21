"""Checks TerrainCalculator against ground truth stored in real maps (needs VTOL_VR_DIR with CustomMaps).

Run: python -m pytest tests/test_terrain_calculator.py  (or python tests/test_terrain_calculator.py)
"""
import os

import numpy as np

from pytol.terrain.terrain_calculator import TerrainCalculator, normal_to_euler_angles


def _maps():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    root = os.path.join(os.getenv('VTOL_VR_DIR', '').strip().strip('"'), 'CustomMaps')
    if not os.path.isdir(root):
        return []
    return [os.path.join(root, m) for m in sorted(os.listdir(root))
            if os.path.isfile(os.path.join(root, m, m + '.vtm')) and os.path.isfile(os.path.join(root, m, 'height.png'))]


def _road_anchor_errors(tc):
    """|terrain height - road control point height| for non-bridge Bezier roads (roads conform to terrain)."""
    pts = np.array([p for s in tc.road_graph_segments.values() if not s['is_bridge'] for p in s['points']])
    if not len(pts):
        return np.array([])
    return np.abs(tc.get_terrain_height(pts[:, 0], pts[:, 2]) - pts[:, 1])


def test_flat_ground_keeps_pure_yaw():
    assert np.allclose(normal_to_euler_angles([0, 1, 0], 33.0), (0.0, 33.0, 0.0), atol=1e-6)


def test_heights_match_maps():
    maps = _maps()
    if not maps:
        import pytest
        pytest.skip("VTOL_VR_DIR/CustomMaps not available")
    for path in maps:
        tc = TerrainCalculator(map_directory_path=path, verbose=False)
        err = _road_anchor_errors(tc)
        statics = tc.get_all_static_prefabs()
        serr = [abs(tc.get_terrain_height(p['position'][0], p['position'][2]) - p['position'][1]) for p in statics]
        print(f"{os.path.basename(path):22s} roads median {np.median(err) if len(err) else float('nan'):7.2f} m  "
              f"statics median {np.median(serr) if serr else float('nan'):7.2f} m  bridges {len(tc.bridge_segments)}")
        # Static prefabs sit exactly on the (flattened) ground. Roads are only reported: they are smoothed
        # and, on Coast maps, the unmodelled edge blending shifts them by a few meters.
        if serr:
            assert np.median(serr) < 3.0, f"{path}: terrain height does not match static prefabs"


if __name__ == '__main__':
    test_flat_ground_keeps_pure_yaw()
    test_heights_match_maps()
    print("OK")
