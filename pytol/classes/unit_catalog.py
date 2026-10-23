"""
Facts about unit ids that the game's editor knows and a script has to respect.

    from pytol.classes.unit_catalog import can_join_group, footprint, team_of, SAM_SYSTEMS
"""
from typing import Optional

from .units import ID_TO_CLASS

# The mission editor FAQ: stationary units cannot belong to unit groups.
STATIONARY_CLASSES = {'AIFixedSAMSpawn', 'AILockingRadarSpawn', 'AIUnitSpawn', 'AIDecoyLauncherSpawn',
                      'AIDecoyRadarSpawn', 'AIMissileSilo'}

# Ground footprint radius (m) of the big things, for spacing; vehicles and small units use DEFAULT_FOOTPRINT.
FOOTPRINT = {'factory1e': 60.0, 'bunker1': 22.0, 'cylinderTent': 15.0, 'ewRadarPyramid': 20.0}
DEFAULT_FOOTPRINT = 10.0

# Surface-to-air systems: launchers are fed by a locking radar (AIFixedSAMSpawn.radar_units).
SAM_SYSTEMS = {
    'medium': {'launcher': 'SamBattery1', 'radar': 'SamFCR', 'launchers': 3, 'name': 'medium-range SAM battery'},
    'long': {'launcher': 'slmrmLauncher', 'radar': 'slmrmRadar', 'launchers': 2, 'name': 'long-range SAM battery'},
    'heavy': {'launcher': 'MAD-4Launcher', 'radar': 'MAD-4Radar', 'launchers': 2, 'name': 'heavy MAD-4 SAM battery'},
}


def can_join_group(unit_id: str) -> bool:
    """False for stationary units (fixed SAMs, radars, structures, decoys, silos): the game rejects them in groups."""
    cls = ID_TO_CLASS.get(unit_id)
    return cls is not None and cls.__name__ not in STATIONARY_CLASSES


def footprint(unit_id: Optional[str]) -> float:
    """Radius in meters to keep clear around a ground unit or structure."""
    return FOOTPRINT.get(unit_id, DEFAULT_FOOTPRINT)


def team_of(unit_id: str) -> Optional[str]:
    """'Allied' or 'Enemy' as the prefab database lists the unit id, or None when it is unknown."""
    from ..resources.resources import load_json_data
    for team, ids in load_json_data('unit_prefab_database.json').items():
        if unit_id in ids:
            return team
    return None
