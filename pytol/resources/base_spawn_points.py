"""
Per-base spawn points and reference points database.

This module stores base-local coordinates for:
- **Spawn points**: Hangars, helipads, big plane spawns (where units spawn)
- **Reference points**: Runway endpoints, ATC towers, barracks (for objectives/waypoints)

All points are defined in base-local coordinates (meters) relative to the base's
center, with +X to the right and +Z forward in the base's local frame.

Point categories:
- 'hangar': Aircraft spawn locations in hangars
- 'helipad': Helicopter spawn pads (marked with 'H')
- 'bigplane': Large aircraft spawn positions
- 'runway': Runway start/end points (reference, not spawns - defines runway line)
- 'controltower': ATC tower location (reference for objectives)
- 'barracks': Barracks/base facilities (reference for objectives)

How to add points:
1) In-game editor: place markers at desired locations
2) Extract coordinates using tools/import_base_points.py
3) Points are stored with base-local offsets and yaw_offset

Example entry:
{
  'name': 'Hangarbase1',
  'offset': [15.0, -60.0],  # (dx, dz) in base-local coords
  'yaw_offset': 90.0        # degrees to add to base yaw
}
"""
from __future__ import annotations

from typing import Dict, List, Tuple
import os
import json
import math

# Map prefab_type -> list of spawn point dicts
# Prefab types come from base['prefab_type'] (e.g., 'airbase1', 'airbase2')
BASE_SPAWN_POINTS: Dict[str, List[dict]] = {
    # Populate with real offsets as you collect them in-game.
    # 'airbase1': [
    #     {'name': 'Hangar A', 'offset': [15.0, -60.0], 'yaw_offset': 90.0},
    #     {'name': 'Apron 1', 'offset': [-20.0, 40.0], 'yaw_offset': 0.0},
    # ],
    # 'airbase2': [
    #     {'name': 'Hangar North', 'offset': [30.0, -80.0], 'yaw_offset': 180.0},
    # ],
}

# Optional JSON file for persistent storage
_THIS_DIR = os.path.dirname(__file__)
_JSON_PATH = os.path.join(_THIS_DIR, "base_spawn_points.json")


def _load_json_if_present():
    global BASE_SPAWN_POINTS
    try:
        if os.path.isfile(_JSON_PATH):
            with open(_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    # normalize entries
                    for k, v in list(data.items()):
                        if not isinstance(v, list):
                            data.pop(k)
                    BASE_SPAWN_POINTS.update(data)
    except Exception:
        # Non-fatal; keep in-memory defaults
        pass


def save_json() -> str:
    """Persist current BASE_SPAWN_POINTS to JSON next to this module."""
    try:
        with open(_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(BASE_SPAWN_POINTS, f, indent=2)
        return _JSON_PATH
    except Exception:
        return ""


def get_spawn_points_for(prefab_type: str) -> List[dict]:
    """Return the configured spawn points for a base prefab type (may be empty)."""
    return BASE_SPAWN_POINTS.get(prefab_type, [])


def compute_world_from_base(base_info: dict, offset_dx_dz: Tuple[float, float], yaw_offset: float = 0.0) -> Tuple[Tuple[float, float, float], float]:
    """
    Convert a base-local offset and yaw into world coordinates and absolute yaw.

    Args:
        base_info: Base dict from TerrainCalculator.bases
        offset_dx_dz: (dx, dz) in base-local coordinates (meters)
        yaw_offset: Yaw to add on top of base yaw (degrees)

    Returns:
        (world_pos_xyz, world_yaw_deg)
    """
    bx, by, bz = base_info['position']
    base_yaw_deg = float(base_info['rotation'][1]) if isinstance(base_info.get('rotation'), (list, tuple)) and len(base_info['rotation']) >= 2 else 0.0
    dx, dz = float(offset_dx_dz[0]), float(offset_dx_dz[1])

    # Rotate local offset by base yaw around Y (right-handed, +yaw rotates toward +Z)
    yaw_rad = math.radians(base_yaw_deg)
    rx = dx * math.cos(yaw_rad) + dz * math.sin(yaw_rad)
    rz = -dx * math.sin(yaw_rad) + dz * math.cos(yaw_rad)

    # Use flatten height for a level apron/hangar surface if available
    y = float(base_info.get('flatten_height', by))
    world_pos = (bx + rx, y, bz + rz)
    world_yaw = (base_yaw_deg + float(yaw_offset)) % 360.0
    return world_pos, world_yaw


def add_base_spawn_point(prefab_type: str, name: str, offset_dx: float, offset_dz: float, yaw_offset: float = 0.0):
    """Register a new spawn point at runtime (useful while collecting data)."""
    BASE_SPAWN_POINTS.setdefault(prefab_type, []).append({
        'name': name,
        'offset': [float(offset_dx), float(offset_dz)],
        'yaw_offset': float(yaw_offset),
    })
    # Try to persist immediately (best-effort)
    save_json()


def get_spawn_by_category(prefab_type: str, category: str = None) -> List[dict]:
    """
    Get points filtered by category (based on name).
    
    Categories:
    - 'hangar': Aircraft hangars (spawn points)
    - 'helipad' or 'heli': Helicopter pads (spawn points)
    - 'bigplane': Large aircraft spawns (spawn points)
    - 'runway': Runway endpoints (reference points for objectives/waypoints)
    - 'controltower' or 'tower': ATC tower (reference point)
    - 'barracks': Base facilities (reference point)
    
    Args:
        prefab_type: Base type ('airbase1', 'airbase2', 'airbase3')
        category: Filter by category keyword in the point name
                 If None, returns all points
    
    Returns:
        List of point dicts matching the category
    """
    spawns = get_spawn_points_for(prefab_type)
    if not category:
        return spawns
    
    category_lower = category.lower()
    return [sp for sp in spawns if category_lower in sp['name'].lower()]


def select_spawn_point(base_info: dict, category: str = 'hangar', index: int = 0, fallback_to_center: bool = True) -> Tuple[Tuple[float, float, float], float]:
    """
    Select a point from a base by category and index.
    
    Use this for:
    - Spawning units: category='hangar', 'helipad', 'bigplane'
    - Placing objectives: category='runway', 'controltower', 'barracks'
    - Creating waypoints: category='runway' (for takeoff/landing patterns)
    
    Args:
        base_info: Base dict from TerrainCalculator.bases
        category: Category to filter (spawn: 'hangar'/'helipad'/'bigplane', 
                                      reference: 'runway'/'controltower'/'barracks')
                 Use None to select from all points
        index: Which point in the filtered list (0 = first, -1 = random)
        fallback_to_center: If no points found, return base center
    
    Returns:
        (world_pos_xyz, world_yaw_deg) tuple
        
    Examples:
        # Spawn player at first hangar
        pos, yaw = select_spawn_point(base, category='hangar', index=0)
        
        # Random helipad spawn
        pos, yaw = select_spawn_point(base, category='helipad', index=-1)
        
        # Place objective at ATC tower
        pos, yaw = select_spawn_point(base, category='controltower', index=0)
        
        # Runway start point for waypoint
        pos, yaw = select_spawn_point(base, category='runway', index=0)
        
        # Runway end point for waypoint
        pos, yaw = select_spawn_point(base, category='runway', index=1)
    """
    import random
    
    prefab_type = base_info.get('prefab_type', '')
    spawns = get_spawn_by_category(prefab_type, category)
    
    if not spawns:
        if fallback_to_center:
            # Return base center facing north (base yaw)
            bx, by, bz = base_info['position']
            base_yaw = float(base_info['rotation'][1]) if isinstance(base_info.get('rotation'), (list, tuple)) and len(base_info['rotation']) >= 2 else 0.0
            y = float(base_info.get('flatten_height', by))
            return (bx, y, bz), base_yaw
        else:
            raise ValueError(f"No spawn points found for {prefab_type} category='{category}'")
    
    # Select spawn point
    if index == -1:
        # Random selection
        spawn = random.choice(spawns)
    else:
        # Specific index (with wraparound)
        spawn = spawns[index % len(spawns)]
    
    # Transform to world coordinates
    offset = tuple(spawn['offset'])
    yaw_offset = spawn['yaw_offset']
    return compute_world_from_base(base_info, offset, yaw_offset)


def get_available_bases(tc, prefab_type: str = None) -> List[dict]:
    """
    Get list of bases from TerrainCalculator, optionally filtered by type.
    
    Args:
        tc: TerrainCalculator instance
        prefab_type: Filter by base type ('airbase1', 'airbase2', 'airbase3')
                    If None, returns all bases
    
    Returns:
        List of base dicts
    """
    bases = getattr(tc, 'bases', []) or []
    if not prefab_type:
        return bases
    return [b for b in bases if b.get('prefab_type') == prefab_type]


def get_reference_points(prefab_type: str, category: str = None) -> List[dict]:
    """
    Get non-spawn reference points (runways, towers, facilities).
    
    Reference point categories:
    - 'runway': Runway start/end points (for takeoff/landing waypoints)
    - 'controltower' or 'tower': ATC tower location
    - 'barracks': Base facilities/barracks
    
    Args:
        prefab_type: Base type ('airbase1', 'airbase2', 'airbase3')
        category: Filter by category (None returns all reference points)
    
    Returns:
        List of reference point dicts
        
    Examples:
        # Get runway endpoints for a base
        runways = get_reference_points('airbase1', 'runway')
        start_pos, start_yaw = compute_world_from_base(base, runways[0]['offset'], runways[0]['yaw_offset'])
        end_pos, end_yaw = compute_world_from_base(base, runways[1]['offset'], runways[1]['yaw_offset'])
    """
    all_points = get_spawn_points_for(prefab_type)
    
    # Filter for reference point types
    reference_keywords = ['runway', 'controltower', 'tower', 'barracks', 'nearbarracks']
    reference_points = [
        p for p in all_points 
        if any(keyword in p['name'].lower() for keyword in reference_keywords)
    ]
    
    if category:
        category_lower = category.lower()
        reference_points = [p for p in reference_points if category_lower in p['name'].lower()]
    
    return reference_points


def get_spawn_points(prefab_type: str, category: str = None) -> List[dict]:
    """
    Get actual unit spawn points (excludes reference points).
    
    Spawn point categories:
    - 'hangar': Aircraft hangar spawns
    - 'helipad' or 'heli': Helicopter pad spawns
    - 'bigplane': Large aircraft spawns
    
    Args:
        prefab_type: Base type ('airbase1', 'airbase2', 'airbase3')
        category: Filter by category (None returns all spawn points)
    
    Returns:
        List of spawn point dicts (excludes runway/tower/barracks references)
    """
    all_points = get_spawn_points_for(prefab_type)
    
    # Exclude reference point types
    reference_keywords = ['runway', 'controltower', 'tower', 'barracks', 'nearbarracks']
    spawn_points = [
        p for p in all_points 
        if not any(keyword in p['name'].lower() for keyword in reference_keywords)
    ]
    
    if category:
        category_lower = category.lower()
        spawn_points = [p for p in spawn_points if category_lower in p['name'].lower()]
    
    return spawn_points


# Initialize from JSON if present
_load_json_if_present()
