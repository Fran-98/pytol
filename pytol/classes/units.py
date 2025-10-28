from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Literal, get_origin, get_args
import typing
import re
from pytol.classes.actions import (
    AIAWACSSpawnActions,
    AIAirTankerSpawnActions,
    AIAircraftSpawnActions,
    AICarrierSpawnActions,
    AIDecoyLauncherSpawnActions,
    AIDecoyRadarSpawnActions,
    AIDroneCarrierSpawnActions,
    AIFixedSAMSpawnActions,
    AIGroundECMSpawnActions,
    AIJTACSpawnActions,
    AILockingRadarSpawnActions,
    AIMissileSiloActions,
    AISeaUnitSpawnActions,
    AIUnitSpawnActions,
    AIUnitSpawnEquippableActions,
    APCUnitSpawnActions,
    ArtilleryUnitSpawnActions,
    GroundUnitSpawnActions,
    IFVSpawnActions,
    MultiplayerSpawnActions,
    PlayerSpawnActions
    
)
from ..misc.logger import create_logger
from ..resources import resources as resource_utils
import json
import os
import dataclasses

_logger = create_logger(verbose=False, name="Units")


def _camel_to_snake(name: str) -> str:
    """Convert CamelCase or camelCase to snake_case (best-effort)."""
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def _unwrap_optional(ft):
    """If ft is Optional[T] or Union[T, None], return T, else return ft."""
    try:
        origin = get_origin(ft)
        if origin is typing.Union:
            args = get_args(ft)
            non_none = [a for a in args if a is not type(None)]
            if non_none:
                return non_none[0]
    except Exception:
        pass
    return ft


def _coerce_value_for_field(value, field_type):
    """Coerce a prefab-provided value into the annotated field_type when reasonable.

    Conservative: don't raise on failure, return original value on unknowns.
    Handles Optional[bool|int|float|List[str]] and direct bool/int/float/list types.
    """
    bt = _unwrap_optional(field_type)
    try:
        if bt is bool:
            # Accept 0/1, "0"/"1", "true"/"false", Python truthy values
            if isinstance(value, (int, float)):
                return bool(value)
            if isinstance(value, str):
                v = value.strip().lower()
                if v in ('0', 'false', 'f', 'no', 'n'):
                    return False
                if v in ('1', 'true', 't', 'yes', 'y'):
                    return True
                # fallback: non-empty string => True
                return bool(v)
            return bool(value)
        # Handle Literal[...] enums (common case: dataclasses use Literal[str,...])
        origin = get_origin(bt)
        if origin is typing.Literal:
            args = get_args(bt)
            # If literals are strings and incoming value is numeric index, map by index
            if args and all(isinstance(a, str) for a in args):
                # numeric index mapping: 0 -> first literal, 1 -> second, etc.
                if isinstance(value, (int, float)):
                    idx = int(value)
                    if 0 <= idx < len(args):
                        return args[idx]
                if isinstance(value, str) and value.isdigit():
                    idx = int(value)
                    if 0 <= idx < len(args):
                        return args[idx]
                # If value is already a string and matches one of the literals, pass through
                if isinstance(value, str) and value in args:
                    return value
        if bt is int:
            if isinstance(value, bool):
                return int(value)
            if isinstance(value, (int, float)):
                return int(value)
            if isinstance(value, str) and value.isdigit():
                return int(value)
        if bt is float:
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                try:
                    return float(value)
                except Exception:
                    pass
        if get_origin(bt) in (list, List):
            # If it's already a list, return as-is. If string like 'a;b;' -> split.
            if isinstance(value, list):
                return value
            if isinstance(value, str):
                # common representation in unit_fields is ';' terminated lists
                parts = [p for p in re.split('[,;]', value) if p]
                return parts
    except Exception:
        pass
    return value


def _is_unity_object_ref(value) -> bool:
    """Detect common Unity serialized object reference strings or small dict-like tokens.

    Examples to skip: '{fileID: 0}', '{fileID: 12345, guid: xxxx, type: 2}',
    '{x: 0, y: 0, z: -2.67}'. We treat these as references and don't merge them
    as dataclass defaults.
    """
    if not isinstance(value, str):
        return False
    v = value.strip()
    if not (v.startswith('{') and v.endswith('}')):
        return False
    inner = v[1:-1].strip()
    # If it contains fileID or guid or is a simple x/y/z coord map -> treat as ref
    if 'fileid' in inner.lower() or 'guid' in inner.lower():
        return True
    # coordinate-like
    if re.search(r'\bx\s*:\s*-?\d+(?:\.\d+)?\b', inner.lower()) and re.search(r'\by\s*:\s*-?\d+(?:\.\d+)?\b', inner.lower()):
        return True
    return False

@dataclass
class Unit:
    """Base class for all mission units."""
    unit_id: str
    unit_name: str
    team: str
    global_position: List[float]
    rotation: List[float]
    actions: Optional[Any] = field(default=None, compare=False, init=False, repr=False)

    # This will hold all the 'UnitFields' parameters

    unit_fields: Dict[(str, Any)] = field(default_factory=dict)

    def __post_init__(self):
        '''
        Called after standard dataclass __init__.
        Moves subclass-specific fields (from field_names dict) AND common fields
        into the self.unit_fields dictionary for VTS formatting, applying
        special formatting where needed. Base Unit fields are left untouched.
        '''
        subclass_field_names = set()
        cls_to_check = self.__class__
        while ((cls_to_check is not Unit) and (cls_to_check is not object)):
            subclass_field_names.update(field_names.get(cls_to_check.__name__, []))
            if ((not cls_to_check.__mro__[1]) or (cls_to_check.__mro__[1] is object)):
                break
            cls_to_check = cls_to_check.__mro__[1]
        fields_to_delete = []
        for f_name in subclass_field_names:
            if hasattr(self, f_name):
                val = getattr(self, f_name)
                if (val is not None):
                    if ((f_name == 'carrier_spawns') and isinstance(val, dict)):
                        formatted_spawns = ''.join([f'{bay_idx}:{unit_id};' for (bay_idx, unit_id) in val.items()])
                        self.unit_fields[f_name] = formatted_spawns
                    elif isinstance(val, list):
                        self.unit_fields[f_name] = (';'.join(map(str, val)) + ';')
                    else:
                        self.unit_fields[f_name] = val
                    fields_to_delete.append(f_name)
        common_fields_to_move = ['unitGroup', 'equips']
        for common_f_name in common_fields_to_move:
            if (hasattr(self, common_f_name) and (common_f_name not in subclass_field_names)):
                val = getattr(self, common_f_name)
                if (val is not None):
                    if ((common_f_name == 'equips') and isinstance(val, list)):
                        self.unit_fields[common_f_name] = (';'.join(map(str, val)) + ';')
                    else:
                        self.unit_fields[common_f_name] = val
                    fields_to_delete.append(common_f_name)
        for f_name in fields_to_delete:
            try:
                delattr(self, f_name)
            except AttributeError:
                _logger.warning(f"Could not delete attribute '{f_name}' during __post_init__ for {self.__class__.__name__}.")

field_names: Dict[(str, List[str])] = {}

@dataclass(unsafe_hash=True)
class UnitSpawn(Unit):
    'Dataclass for unit UnitSpawn'
    receive_friendly_damage: Optional[bool] = None

@dataclass(unsafe_hash=True)
class AIUnitSpawn(UnitSpawn):
    'Dataclass for unit AIUnitSpawn'
    engage_enemies: Optional[bool] = None
    detection_mode: Optional[Literal['Default', 'Force_Detected', 'Force_Undetected']] = None
    spawn_on_start: Optional[bool] = True
    invincible: Optional[bool] = False
    combat_target: Optional[bool] = None
    respawnable: Optional[bool] = None

@dataclass(unsafe_hash=True)
class AIDecoyLauncherSpawn(AIUnitSpawn):
    'Dataclass for unit AIDecoyLauncherSpawn'
    pass

@dataclass(unsafe_hash=True)
class AIUnitSpawnEquippable(AIUnitSpawn):
    'Dataclass for unit AIUnitSpawnEquippable'
    equips: Optional[List[str]] = None

@dataclass(unsafe_hash=True)
class AISeaUnitSpawn(AIUnitSpawnEquippable):
    'Dataclass for unit AISeaUnitSpawn'
    unit_group: Optional[str] = None
    default_behavior: Optional[Literal['Parked', 'Move_To_Waypoint', 'Navigate_Path']] = None
    default_waypoint: Optional[str] = None
    default_path: Optional[str] = None
    hull_number: Optional[float] = 0.0

@dataclass(unsafe_hash=True)
class AIDecoyRadarSpawn(AIUnitSpawn):
    'Dataclass for unit AIDecoyRadarSpawn'
    pass

@dataclass(unsafe_hash=True)
class AIAircraftSpawn(AIUnitSpawnEquippable):
    'Dataclass for unit AIAircraftSpawn'
    unit_group: Optional[str] = None
    voice_profile: Optional[str] = None
    player_commands_mode: Optional[Literal['Unit_Group_Only', 'Force_Allow', 'Force_Disallow']] = None
    default_behavior: Optional[Literal['Orbit', 'Path', 'Parked', 'TakeOff']] = None
    initial_speed: Optional[float] = None
    default_nav_speed: Optional[float] = None
    default_orbit_point: Optional[str] = None
    default_path: Optional[str] = None
    orbit_altitude: Optional[float] = None
    fuel: Optional[float] = 100.0
    auto_refuel: Optional[bool] = True
    auto_r_t_b: Optional[bool] = None
    default_radar_enabled: Optional[bool] = True
    allow_jamming_at_will: Optional[bool] = False
    parked_start_mode: Optional[Literal['FlightReady', 'Cold']] = None
    # Editor often emits a blank rtbDestination for aircraft; include it so VTS matches editor output
    rtb_destination: Optional[str] = ""

@dataclass(unsafe_hash=True)
class AIAWACSSpawn(AIAircraftSpawn):
    'Dataclass for unit AIAWACSSpawn'
    awacs_voice_profile: Optional[str] = None
    comms_enabled: Optional[bool] = True
    report_to_groups: Optional[List[str]] = None

@dataclass(unsafe_hash=True)
class AIMissileSilo(AIUnitSpawn):
    'Dataclass for unit AIMissileSilo'
    pass

@dataclass(unsafe_hash=True)
class GroundUnitSpawn(AIUnitSpawnEquippable):
    'Dataclass for unit GroundUnitSpawn'
    unit_group: Optional[str] = None
    move_speed: Optional[Literal['Slow_10', 'Medium_20', 'Fast_30']] = None
    behavior: Optional[Literal['Path', 'Parked', 'StayInRadius', 'Follow', 'RailPath']] = None
    default_path: Optional[str] = None
    waypoint: Optional[str] = None
    stop_to_engage: Optional[bool] = True

@dataclass(unsafe_hash=True)
class AIJTACSpawn(GroundUnitSpawn):
    'Dataclass for unit AIJTACSpawn'
    pass

@dataclass(unsafe_hash=True)
class AIFixedSAMSpawn(GroundUnitSpawn):
    'Dataclass for unit AIFixedSAMSpawn'
    radar_units: Optional[List[str]] = None
    allow_reload: Optional[bool] = False
    reload_time: Optional[float] = 60.0
    allow_h_o_j: Optional[bool] = None

@dataclass(unsafe_hash=True)
class AILockingRadarSpawn(GroundUnitSpawn):
    'Dataclass for unit AILockingRadarSpawn'
    pass

@dataclass(unsafe_hash=True)
class AICarrierSpawn(AISeaUnitSpawn):
    'Dataclass for unit AICarrierSpawn'
    lso_freq: Optional[float] = None
    carrier_spawns: Optional[Dict[(int, int)]] = None

@dataclass(unsafe_hash=True)
class ArtilleryUnitSpawn(GroundUnitSpawn):
    'Dataclass for unit ArtilleryUnitSpawn'
    pass

@dataclass(unsafe_hash=True)
class MultiplayerSpawn(UnitSpawn):
    'Dataclass for unit MultiplayerSpawn'
    vehicle: Optional[str] = None
    selectable_alt_spawn: Optional[bool] = False
    slot_label: Optional[str] = None
    unit_group: Optional[str] = None
    start_mode: Optional[Literal['Cold', 'FlightReady', 'FlightAP']] = None
    equipment: Optional[str] = None
    initial_speed: Optional[float] = 0.0
    rtb_is_spawn: Optional[bool] = False
    limited_lives: Optional[bool] = False
    life_count: Optional[float] = 1.0
    b_eq_assignment_mode: Optional[bool] = False
    livery_ref: Optional[str] = None

@dataclass(unsafe_hash=True)
class AIDroneCarrierSpawn(AISeaUnitSpawn):
    'Dataclass for unit AIDroneCarrierSpawn'
    pass

@dataclass(unsafe_hash=True)
class RearmingUnitSpawn(UnitSpawn):
    'Dataclass for unit RearmingUnitSpawn'
    spawn_on_start: Optional[bool] = True

@dataclass(unsafe_hash=True)
class AIGroundECMSpawn(GroundUnitSpawn):
    'Dataclass for unit AIGroundECMSpawn'
    pass

@dataclass(unsafe_hash=True)
class APCUnitSpawn(GroundUnitSpawn):
    'Dataclass for unit APCUnitSpawn'
    pass

@dataclass(unsafe_hash=True)
class IFVSpawn(APCUnitSpawn):
    'Dataclass for unit IFVSpawn'
    allow_reload: Optional[bool] = True
    reload_time: Optional[float] = 60.0

@dataclass(unsafe_hash=True)
class AIGroundMWSSpawn(GroundUnitSpawn):
    'Dataclass for unit AIGroundMWSSpawn'
    radar_units: Optional[List[str]] = None
    decoy_units: Optional[List[str]] = None
    units_to_defend: Optional[List[str]] = None
    defense_units: Optional[List[str]] = None
    jammer_units: Optional[List[str]] = None

@dataclass(unsafe_hash=True)
class AIAirTankerSpawn(AIAircraftSpawn):
    'Dataclass for unit AIAirTankerSpawn'
    pass

@dataclass(unsafe_hash=True)
class RocketArtilleryUnitSpawn(ArtilleryUnitSpawn):
    'Dataclass for unit RocketArtilleryUnitSpawn'
    default_shots_per_salvo: Optional[float] = 1.0
    ripple_rate: Optional[float] = 60.0
    allow_reload: Optional[bool] = True
    reload_time: Optional[float] = 1.0

@dataclass(unsafe_hash=True)
class PlayerSpawn(UnitSpawn):
    'Dataclass for unit PlayerSpawn'
    start_mode: Optional[Literal['Cold', 'FlightReady', 'FlightAP']] = None
    initial_speed: Optional[float] = 0.0
    unit_group: Optional[str] = None

field_names.update({
    'UnitSpawn': ['receive_friendly_damage'],
    'AIUnitSpawn': ['engage_enemies', 'detection_mode', 'spawn_on_start', 'invincible', 'combat_target', 'respawnable'],
    'AIDecoyLauncherSpawn': [],
    'AIUnitSpawnEquippable': ['equips'],
    'AISeaUnitSpawn': ['unit_group', 'default_behavior', 'default_waypoint', 'default_path', 'hull_number'],
    'AIDecoyRadarSpawn': [],
    'AIAircraftSpawn': ['unit_group', 'voice_profile', 'player_commands_mode', 'default_behavior', 'initial_speed', 'default_nav_speed', 'default_orbit_point', 'default_path', 'orbit_altitude', 'fuel', 'auto_refuel', 'auto_r_t_b', 'default_radar_enabled', 'allow_jamming_at_will', 'parked_start_mode', 'rtb_destination'],
    'AIAWACSSpawn': ['awacs_voice_profile', 'comms_enabled', 'report_to_groups'],
    'AIMissileSilo': [],
    'GroundUnitSpawn': ['unit_group', 'move_speed', 'behavior', 'default_path', 'waypoint', 'stop_to_engage'],
    'AIJTACSpawn': [],
    'AIFixedSAMSpawn': ['radar_units', 'allow_reload', 'reload_time', 'allow_h_o_j'],
    'AILockingRadarSpawn': [],
    'AICarrierSpawn': ['lso_freq', 'carrier_spawns'],
    'ArtilleryUnitSpawn': [],
    'MultiplayerSpawn': ['vehicle', 'selectable_alt_spawn', 'slot_label', 'unit_group', 'start_mode', 'equipment', 'initial_speed', 'rtb_is_spawn', 'limited_lives', 'life_count', 'b_eq_assignment_mode', 'livery_ref'],
    'AIDroneCarrierSpawn': [],
    'RearmingUnitSpawn': ['spawn_on_start'],
    'AIGroundECMSpawn': [],
    'APCUnitSpawn': [],
    'IFVSpawn': ['allow_reload', 'reload_time'],
    'AIGroundMWSSpawn': ['radar_units', 'decoy_units', 'units_to_defend', 'defense_units', 'jammer_units'],
    'AIAirTankerSpawn': [],
    'RocketArtilleryUnitSpawn': ['default_shots_per_salvo', 'ripple_rate', 'allow_reload', 'reload_time'],
    'PlayerSpawn': ['start_mode', 'initial_speed', 'unit_group']
})

ID_TO_CLASS = {
    'ABomberAI': AIAircraftSpawn,
    'aDecoyRadarTransmitter': AIDecoyRadarSpawn,
    'AEW-50': AIAWACSSpawn,
    'aIRMDlauncher': AIUnitSpawn,
    'AIUCAV': AIAircraftSpawn,
    'AJammerTruck': AIGroundECMSpawn,
    'AlliedAAShip': AICarrierSpawn,
    'AlliedBackstopSAM': AIFixedSAMSpawn,
    'AlliedCarrier': AICarrierSpawn,
    'alliedCylinderTent': AIUnitSpawn,
    'AlliedEWRadar': AILockingRadarSpawn,
    'AlliedIFV': IFVSpawn,
    'alliedMBT1': GroundUnitSpawn,
    'AlliedRearmRefuelPoint': RearmingUnitSpawn,
    'AlliedRearmRefuelPointB': RearmingUnitSpawn,
    'AlliedRearmRefuelPointC': RearmingUnitSpawn,
    'AlliedRearmRefuelPointD': RearmingUnitSpawn,
    'AlliedSoldier': AIJTACSpawn,
    'AlliedSoldierMANPAD': GroundUnitSpawn,
    'ALogisticTruck': GroundUnitSpawn,
    'AMWSTruck Variant': AIGroundMWSSpawn,
    'APC': APCUnitSpawn,
    'ARocketTruck': RocketArtilleryUnitSpawn,
    'Artillery': ArtilleryUnitSpawn,
    'ASF-30': AIAircraftSpawn,
    'ASF-33': AIAircraftSpawn,
    'ASF-58': AIAircraftSpawn,
    'AV-42CAI': AIAircraftSpawn,
    'BSTOPRadar': AILockingRadarSpawn,
    'bunker1': AIUnitSpawn,
    'bunker2': AIUnitSpawn,
    'bunkerHillside': AIUnitSpawn,
    'bunkerHillsideAllied': AIUnitSpawn,
    'cylinderTent': AIUnitSpawn,
    'DroneCarrier': AIDroneCarrierSpawn,
    'DroneGunBoat': AISeaUnitSpawn,
    'DroneGunBoatRocket': AISeaUnitSpawn,
    'DroneMissileCruiser': AISeaUnitSpawn,
    'E-4': AIAWACSSpawn,
    'EBomberAI': AIAircraftSpawn,
    'eDecoyRadarTransmitter': AIDecoyRadarSpawn,
    'EF-24 AI': AIAircraftSpawn,
    'eIRMDlauncher': AIUnitSpawn,
    'EJammerTruck': AIGroundECMSpawn,
    'ELogisticsTruck': GroundUnitSpawn,
    'EMWSTruck': AIGroundMWSSpawn,
    'EnemyAPC': APCUnitSpawn,
    'EnemyCarrier': AICarrierSpawn,
    'enemyMBT1': GroundUnitSpawn,
    'EnemyRearmRefuelPoint': RearmingUnitSpawn,
    'EnemyRearmRefuelPointB': RearmingUnitSpawn,
    'EnemyRearmRefuelPointC': RearmingUnitSpawn,
    'EnemyRearmRefuelPointD': RearmingUnitSpawn,
    'EnemySoldier': AIJTACSpawn,
    'EnemySoldierMANPAD': GroundUnitSpawn,
    'ERocketTruck': RocketArtilleryUnitSpawn,
    'EscortCruiser': AICarrierSpawn,
    'ESuperMissileCruiser': AISeaUnitSpawn,
    'ewRadarPyramid': AILockingRadarSpawn,
    'ewRadarSphere': AILockingRadarSpawn,
    'F-45A AI': AIAircraftSpawn,
    'FA-26B AI': AIAircraftSpawn,
    'factory1': AIUnitSpawn,
    'factory1e': AIUnitSpawn,
    'GAV-25': AIAircraftSpawn,
    'IFV-1': IFVSpawn,
    'IRAPC': APCUnitSpawn,
    'KC-49': AIAirTankerSpawn,
    'MAD-4Launcher': AIFixedSAMSpawn,
    'MAD-4Radar': AILockingRadarSpawn,
    'MineBoat': AISeaUnitSpawn,
    'missileSilo_a': AIMissileSilo,
    'missileSilo_e': AIMissileSilo,
    'MQ-31': AIAirTankerSpawn,
    'MultiplayerSpawn': MultiplayerSpawn,
    'MultiplayerSpawnEnemy': MultiplayerSpawn,
    'PatRadarTrailer': AILockingRadarSpawn,
    'PatriotLauncher': AIFixedSAMSpawn,
    'PhallanxTruck': GroundUnitSpawn,
    'PlayerSpawn': PlayerSpawn,
    'SAAW': GroundUnitSpawn,
    'SamBattery1': AIFixedSAMSpawn,
    'SamFCR': AILockingRadarSpawn,
    'SamFCR2': AILockingRadarSpawn,
    'SLAIM120Truck': AIFixedSAMSpawn,
    'slmrmLauncher': AIFixedSAMSpawn,
    'slmrmRadar': AILockingRadarSpawn,
    'SRADTruck': GroundUnitSpawn,
    'staticAAA-20x2': AIUnitSpawn,
    'staticCIWS': AIUnitSpawn,
    'staticDecoyLauncher': AIDecoyLauncherSpawn,
    'staticDecoyLauncherA': AIDecoyLauncherSpawn,
    'staticUcavLauncher': AIUnitSpawn,
    'T-55 AI': AIAircraftSpawn,
    'T-55 AI-E': AIAircraftSpawn,
    'WatchmanTruck': AILockingRadarSpawn,
}

UNIT_CLASS_TO_ACTION_CLASS = {
    AIUnitSpawn: AIUnitSpawnActions,
    AIUnitSpawnEquippable: AIUnitSpawnEquippableActions,
    AIAircraftSpawn: AIAircraftSpawnActions,
    AIAWACSSpawn: AIAWACSSpawnActions,
    AIAirTankerSpawn: AIAirTankerSpawnActions,
    GroundUnitSpawn: GroundUnitSpawnActions,
    AIFixedSAMSpawn: AIFixedSAMSpawnActions,
    AIGroundECMSpawn: AIGroundECMSpawnActions,
    AIJTACSpawn: AIJTACSpawnActions,
    AILockingRadarSpawn: AILockingRadarSpawnActions,
    ArtilleryUnitSpawn: ArtilleryUnitSpawnActions,
    APCUnitSpawn: APCUnitSpawnActions,
    IFVSpawn: IFVSpawnActions,
    AISeaUnitSpawn: AISeaUnitSpawnActions,
    AICarrierSpawn: AICarrierSpawnActions,
    AIDroneCarrierSpawn: AIDroneCarrierSpawnActions,
    AIDecoyLauncherSpawn: AIDecoyLauncherSpawnActions,
    AIDecoyRadarSpawn: AIDecoyRadarSpawnActions,
    AIMissileSilo: AIMissileSiloActions,
    PlayerSpawn: PlayerSpawnActions,
    MultiplayerSpawn: MultiplayerSpawnActions,
}

def create_unit(id_name: str, unit_name: str, team: str, global_position: List[float], rotation: List[float], **kwargs) -> 'Unit':
    '''
    Factory function to create a new unit instance.
    This is the recommended way to add units to your mission.

    Args:
        id_name (str): The prefab ID of the unit (e.g., "fa-26b_ai").
        unit_name (str): The in-game display name for the unit.
        team (str): "Allied" or "Enemy".
        global_position (List[float]): A list of [x, y, z] coordinates.
                                      May be adjusted by Mission.add_unit based on placement.
        rotation (List[float]): A list of [x, y, z] euler angles.
                                May be adjusted by Mission.add_unit based on placement.
        **kwargs: Any additional unit-specific parameters (e.g., path="my_path").

    Returns:
        A Unit subclass instance with all parameters set.
        The 'actions' attribute will be None initially; it's set by Mission.add_unit.
    '''
    # Find Python dataclass for this prefab id using the canonical ID_TO_CLASS map
    unit_cls = ID_TO_CLASS.get(id_name)
    if unit_cls is None:
        _logger.error(f"No unit dataclass mapped for id '{id_name}'. Check ID_TO_CLASS or prefab mappings.")
        return None

    # Build constructor kwargs. Required positional dataclass fields are:
    # unit_id, unit_name, team, global_position, rotation
    ctor_kwargs: Dict[str, Any] = {}
    # copy user-supplied kwargs (they should use snake_case matching dataclass fields)
    ctor_kwargs.update(kwargs)

    # Merge per-prefab defaults (if available). Prefer loading from the package
    # resources (so JSONs live under `pytol/resources`). Fall back to the tools
    # folder for backward compatibility.
    try:
        _PREFAB_DEFAULTS = resource_utils.load_json_data('prefab_defaults_per_prefab.json') or {}
    except Exception:
        _PREFAB_DEFAULTS = {}

    prefab_defaults = _PREFAB_DEFAULTS.get(id_name, {}).get('defaults', {})
    if prefab_defaults:
        # Map allowed constructor fields for this dataclass (includes inherited fields)
        try:
            allowed_fields = {f.name: f.type for f in dataclasses.fields(unit_cls)}
        except Exception:
            # Fallback: best-effort introspection
            allowed_fields = {k: type(getattr(unit_cls, k)) for k in unit_cls.__dict__.keys() if not k.startswith('_')}

        # Merge defaults only when the user didn't explicitly provide a kwarg.
        # Try multiple name variants for prefab keys (snake_case, camelCase).
        applied_prefab_defaults: Dict[str, Any] = {}
        for k, v in prefab_defaults.items():
            # We'll attempt to resolve the target dataclass field name from the prefab key
            target = None
            if k in allowed_fields:
                target = k
            else:
                # Try converting camelCase to snake_case
                sk = _camel_to_snake(k)
                if sk in allowed_fields:
                    target = sk
                else:
                    # Try lowercased key (some keys may differ only by case)
                    low = k.lower()
                    if low in allowed_fields:
                        target = low

            # As a last resort, attempt a "normalized" match where we strip
            # non-alphanumeric characters and compare lowercased tokens. This
            # handles keys like 'auto_rtb' vs dataclass 'auto_r_t_b' and other
            # small naming mismatches produced by prefab extraction.
            if not target:
                def _normalize_key(x: str) -> str:
                    return ''.join(ch.lower() for ch in str(x) if ch.isalnum())
                norm_k = _normalize_key(k)
                for cand in allowed_fields.keys():
                    if _normalize_key(cand) == norm_k:
                        target = cand
                        break

            if not target:
                continue

            # Never override required constructor positional args here
            if target in ('unit_id', 'unit_name', 'team', 'global_position', 'rotation'):
                continue

            if target in ctor_kwargs:
                # caller provided explicit override; skip
                continue

            # Coerce value to annotated type where possible
            ann = allowed_fields.get(target)
            # Skip Unity object refs (fileID/guid/coordinate maps) - these point to other
            # engine objects and should not be used as dataclass defaults.
            if _is_unity_object_ref(v):
                continue
            coerced = _coerce_value_for_field(v, ann) if ann is not None else v
            ctor_kwargs[target] = coerced
            applied_prefab_defaults[target] = coerced

        # Emit a compact, debug-level summary so users can audit which prefab defaults
        # were merged at runtime. This prints only when logger is configured verbose/debug.
        if applied_prefab_defaults:
            # Keep the output concise: list of keys and sample of values
            try:
                short = {kk: (vv if isinstance(vv, (bool, int, float, str)) else type(vv).__name__) for kk, vv in applied_prefab_defaults.items()}
            except Exception:
                short = {kk: type(vv).__name__ for kk, vv in applied_prefab_defaults.items()}
            _logger.debug(f"Applied {len(applied_prefab_defaults)} prefab defaults for '{id_name}': {short}")

    try:
        unit_obj = unit_cls(
            unit_id=id_name,
            unit_name=unit_name,
            team=team,
            global_position=global_position,
            rotation=rotation,
            **ctor_kwargs,
        )
    except TypeError as e:
        _logger.error(f"Failed to construct unit '{id_name}' -> {unit_cls}: {e}")
        return None

    # Actions are attached later by Mission.add_unit; keep None here for clarity.
    return unit_obj
