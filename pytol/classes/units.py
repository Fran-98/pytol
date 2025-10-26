from dataclasses import dataclass, field
from typing import List, Optional, Union, Dict, Any, cast, Literal
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

_logger = create_logger(verbose=False, name="Units")

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
    unit_fields: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """
        Called after standard dataclass __init__.
        Moves subclass-specific fields (from field_names dict) AND common fields
        into the self.unit_fields dictionary for VTS formatting, applying
        special formatting where needed. Base Unit fields are left untouched.
        """
        subclass_field_names = set()
        cls_to_check = self.__class__
        while cls_to_check is not Unit and cls_to_check is not object:
            subclass_field_names.update(field_names.get(cls_to_check.__name__, []))
            if not cls_to_check.__mro__[1] or cls_to_check.__mro__[1] is object:
                break
            cls_to_check = cls_to_check.__mro__[1]

        fields_to_delete = [] # Keep track of attributes to delete safely later

        # --- Process Subclass-Specific Fields ---
        for f_name in subclass_field_names:
            if hasattr(self, f_name):
                val = getattr(self, f_name)
                if val is not None:
                    # Apply special formatting if needed
                    if f_name == 'carrier_spawns' and isinstance(val, dict):
                        formatted_spawns = "".join([f"{bay_idx}:{unit_id};" for bay_idx, unit_id in val.items()])
                        self.unit_fields[f_name] = formatted_spawns
                    elif isinstance(val, list): # General list formatting
                        # Convert all items to string before joining
                        self.unit_fields[f_name] = ";".join(map(str, val)) + ";"
                    else: # Default handling
                        self.unit_fields[f_name] = val
                    # Mark the original attribute for deletion
                    fields_to_delete.append(f_name)

        # --- ADDED: Process Common Fields Explicitly ---
        common_fields_to_move = ["unitGroup", "equips"] # Add any other common fields here
        for common_f_name in common_fields_to_move:
             # Check if the field exists and hasn't already been processed as a subclass field
             if hasattr(self, common_f_name) and common_f_name not in subclass_field_names:
                  val = getattr(self, common_f_name)
                  if val is not None:
                       # Apply special formatting if needed (e.g., equips list)
                       if common_f_name == 'equips' and isinstance(val, list):
                            self.unit_fields[common_f_name] = ";".join(map(str, val)) + ";"
                       else: # unitGroup is usually just string/null
                            self.unit_fields[common_f_name] = val
                       # Mark for deletion
                       fields_to_delete.append(common_f_name)
        # --- END ADDED SECTION ---

        # Safely delete the original attributes after processing
        for f_name in fields_to_delete:
            try:
                # Use pop to remove from unit_fields if it was supposed to be deleted
                # This check ensures we don't delete base class fields accidentally
                # if f_name in self.unit_fields:
                delattr(self, f_name)
            except AttributeError:
                _logger.warning(f"Could not delete attribute '{f_name}' during __post_init__ for {self.__class__.__name__}.")
    
# This helper dict stores the field names for each class,
# used by the base class's __post_init__
field_names: Dict[str, List[str]] = {}

@dataclass(unsafe_hash=True)
class UnitSpawn(Unit):
    """Dataclass for unit UnitSpawn"""
    receive_friendly_damage: Optional[bool] = None
    # (C#: Receive Friendly Damage - bool)


@dataclass(unsafe_hash=True)
class AIUnitSpawn(UnitSpawn):
    """Dataclass for unit AIUnitSpawn"""
    engage_enemies: Optional[bool] = None
    # (C#: Engage Enemies - bool)
    detection_mode: Optional[Literal["Default", "Force_Detected", "Force_Undetected"]] = None
    # (C#: Detection Mode - string)
    #     Format: Unknown complex type: InitialDetectionModes
    spawn_on_start: Optional[bool] = None
    # (C#: Spawn Immediately - bool)
    invincible: Optional[bool] = None
    # (C#: Invincible - bool)
    combat_target: Optional[bool] = None
    # (C#: Combat Target - bool)
    respawnable: Optional[bool] = None
    # (C#: Respawnable - bool)


@dataclass(unsafe_hash=True)
class AIDecoyLauncherSpawn(AIUnitSpawn):
    """Dataclass for unit AIDecoyLauncherSpawn"""
    pass


@dataclass(unsafe_hash=True)
class AIUnitSpawnEquippable(AIUnitSpawn):
    """Dataclass for unit AIUnitSpawnEquippable"""
    equips: Optional[List[str]] = None
    # (C#: Equips - string)
    #     Format: A semi-colon (;) separated list. Original type: string_List


@dataclass(unsafe_hash=True)
class AISeaUnitSpawn(AIUnitSpawnEquippable):
    """Dataclass for unit AISeaUnitSpawn"""
    unit_group: Optional[str] = None
    # (C#: Sea Group - string)
    #     Format: The ID (string) of a Unit Group.
    default_behavior: Optional[Literal["Parked", "Move_To_Waypoint", "Navigate_Path"]] = None
    # (C#: Default Behavior - string)
    #     Format: Unknown complex type: SeaUnitDefaultBehaviors
    default_waypoint: Optional[str] = None
    # (C#: Waypoint - string)
    #     Format: The ID of a Waypoint.
    default_path: Optional[str] = None
    # (C#: Path - string)
    #     Format: The ID of a Path object.
    hull_number: Optional[float] = None
    # (C#: Hull Number - float)


@dataclass(unsafe_hash=True)
class AIDecoyRadarSpawn(AIUnitSpawn):
    """Dataclass for unit AIDecoyRadarSpawn"""
    pass


@dataclass(unsafe_hash=True)
class AIAircraftSpawn(AIUnitSpawnEquippable):
    """Dataclass for unit AIAircraftSpawn"""
    unit_group: Optional[str] = None
    # (C#: Aircraft Group - string)
    #     Format: The ID (string) of a Unit Group.
    voice_profile: Optional[str] = None
    # (C#: Voice - string)
    #     Format: Unknown complex type: WingmanVoiceProfile
    player_commands_mode: Optional[Literal["Unit_Group_Only", "Force_Allow", "Force_Disallow"]] = None
    # (C#: Player Commands - string)
    #     Format: Unknown complex type: PlayerCommandsModes
    default_behavior: Optional[Literal["Orbit", "Path", "Parked", "TakeOff"]] = None
    # (C#: Default Behavior - string)
    #     Format: Unknown complex type: DefaultBehaviors
    initial_speed: Optional[float] = None
    # (C#: Initial Airspeed - float)
    default_nav_speed: Optional[float] = None
    # (C#: Default Nav Speed - float)
    default_orbit_point: Optional[str] = None
    # (C#: Default Orbit Point - string)
    #     Format: The ID of a Waypoint.
    default_path: Optional[str] = None
    # (C#: Default Path - string)
    #     Format: The ID of a Path object.
    orbit_altitude: Optional[float] = None
    # (C#: Default Altitude - float)
    fuel: Optional[float] = None
    # (C#: Fuel % - float)
    auto_refuel: Optional[bool] = None
    # (C#: Auto Refuel - bool)
    auto_r_t_b: Optional[bool] = None
    # (C#: Auto RTB - bool)
    default_radar_enabled: Optional[bool] = None
    # (C#: Radar Enabled - bool)
    allow_jamming_at_will: Optional[bool] = None
    # (C#: Allow Jamming at Will - bool)
    parked_start_mode: Optional[Literal["FlightReady", "Cold"]] = None
    # (C#: Parked Start Mode - string)
    #     Format: Unknown complex type: ParkedStartModes


@dataclass(unsafe_hash=True)
class AIAWACSSpawn(AIAircraftSpawn):
    """Dataclass for unit AIAWACSSpawn"""
    awacs_voice_profile: Optional[str] = None
    # (C#: AWACS Voice - string)
    #     Format: The name of the AWACSVoiceProfile (e.g., 'default').
    comms_enabled: Optional[bool] = None
    # (C#: Comms Enabled - bool)
    report_to_groups: Optional[List[str]] = None
    # (C#: Report Contacts To Groups - string)
    #     Format: A semi-colon (;) separated list of Unit Group names (e.g., 'Allied:Alpha').


@dataclass(unsafe_hash=True)
class AIMissileSilo(AIUnitSpawn):
    """Dataclass for unit AIMissileSilo"""
    pass


@dataclass(unsafe_hash=True)
class GroundUnitSpawn(AIUnitSpawnEquippable):
    """Dataclass for unit GroundUnitSpawn"""
    unit_group: Optional[str] = None
    # (C#: Unit Group - string)
    #     Format: The ID (string) of a Unit Group.
    move_speed: Optional[Literal["Slow_10", "Medium_20", "Fast_30"]] = None
    # (C#: Move Speed - string)
    #     Format: Unknown complex type: MoveSpeeds
    behavior: Optional[Literal["Path", "Parked", "StayInRadius", "Follow", "RailPath"]] = None
    # (C#: Behavior - string)
    #     Format: Unknown complex type: Behaviors
    default_path: Optional[str] = None
    # (C#: Default Path - string)
    #     Format: The ID of a Path object.
    waypoint: Optional[str] = None
    # (C#: Default Waypoint - string)
    #     Format: The ID of a Waypoint.
    stop_to_engage: Optional[bool] = None
    # (C#: Stop to Engage - bool)


@dataclass(unsafe_hash=True)
class AIJTACSpawn(GroundUnitSpawn):
    """Dataclass for unit AIJTACSpawn"""
    pass


@dataclass(unsafe_hash=True)
class AIFixedSAMSpawn(GroundUnitSpawn):
    """Dataclass for unit AIFixedSAMSpawn"""
    radar_units: Optional[List[str]] = None
    # (C#: Radars - string)
    #     Format: A semi-colon (;) separated list of Unit IDs.
    allow_reload: Optional[bool] = None
    # (C#: Allow Reload - bool)
    reload_time: Optional[float] = None
    # (C#: Reload Time (sec) - float)
    allow_h_o_j: Optional[bool] = None
    # (C#: Allow HOJ - bool)


@dataclass(unsafe_hash=True)
class AILockingRadarSpawn(GroundUnitSpawn):
    """Dataclass for unit AILockingRadarSpawn"""
    pass


@dataclass(unsafe_hash=True)
class AICarrierSpawn(AISeaUnitSpawn):
    """Dataclass for unit AICarrierSpawn"""
    lso_freq: Optional[float] = None
    carrier_spawns: Optional[Dict[int, int]] = None
    # (C#: LSO Frequency - float)


@dataclass(unsafe_hash=True)
class ArtilleryUnitSpawn(GroundUnitSpawn):
    """Dataclass for unit ArtilleryUnitSpawn"""
    pass


@dataclass(unsafe_hash=True)
class MultiplayerSpawn(UnitSpawn):
    """Dataclass for unit MultiplayerSpawn"""
    vehicle: Optional[str] = None
    # (C#: Vehicle - string)
    #     Format: Unknown complex type: PlayerVehicleReference
    selectable_alt_spawn: Optional[bool] = None
    # (C#: Selectable Alt Spawns - bool)
    slot_label: Optional[str] = None
    # (C#: Slot Label - string)
    unit_group: Optional[str] = None
    # (C#: Aircraft Group - string)
    #     Format: The ID (string) of a Unit Group.
    start_mode: Optional[Literal["Cold", "FlightReady", "FlightAP"]] = None
    # (C#: Start Mode - string)
    #     Format: Unknown complex type: FlightStartModes
    equipment: Optional[str] = None
    # (C#: Available Equipment - string)
    #     Format: Unknown complex type: VehicleEquipmentList
    initial_speed: Optional[float] = None
    # (C#: Initial Airspeed - float)
    rtb_is_spawn: Optional[bool] = None
    # (C#: RTB Waypoint is Spawn - bool)
    limited_lives: Optional[bool] = None
    # (C#: Limit Lives - bool)
    life_count: Optional[float] = None
    # (C#: Lives - float)
    b_eq_assignment_mode: Optional[bool] = None
    # (C#: Assign Equipment - bool)
    livery_ref: Optional[str] = None
    # (C#: Livery - string)
    #     Format: Unknown complex type: VTLiveryReference


@dataclass(unsafe_hash=True)
class AIDroneCarrierSpawn(AISeaUnitSpawn):
    """Dataclass for unit AIDroneCarrierSpawn"""
    pass


@dataclass(unsafe_hash=True)
class RearmingUnitSpawn(UnitSpawn):
    """Dataclass for unit RearmingUnitSpawn"""
    spawn_on_start: Optional[bool] = None
    # (C#: Spawn Immediately - bool)


@dataclass(unsafe_hash=True)
class AIGroundECMSpawn(GroundUnitSpawn):
    """Dataclass for unit AIGroundECMSpawn"""
    pass


@dataclass(unsafe_hash=True)
class APCUnitSpawn(GroundUnitSpawn):
    """Dataclass for unit APCUnitSpawn"""
    pass


@dataclass(unsafe_hash=True)
class IFVSpawn(APCUnitSpawn):
    """Dataclass for unit IFVSpawn"""
    allow_reload: Optional[bool] = None
    # (C#: Allow Reload - bool)
    reload_time: Optional[float] = None
    # (C#: Reload Time - float)


@dataclass(unsafe_hash=True)
class AIGroundMWSSpawn(GroundUnitSpawn):
    """Dataclass for unit AIGroundMWSSpawn"""
    radar_units: Optional[List[str]] = None
    # (C#: Radars To Command - string)
    #     Format: A semi-colon (;) separated list of Unit IDs.
    decoy_units: Optional[List[str]] = None
    # (C#: Decoys - string)
    #     Format: A semi-colon (;) separated list of Unit IDs.
    units_to_defend: Optional[List[str]] = None
    # (C#: Units To Defend - string)
    #     Format: A semi-colon (;) separated list of Unit IDs.
    defense_units: Optional[List[str]] = None
    # (C#: Missile Defenses - string)
    #     Format: A semi-colon (;) separated list of Unit IDs.
    jammer_units: Optional[List[str]] = None
    # (C#: Jammers - string)
    #     Format: A semi-colon (;) separated list of Unit IDs.


@dataclass(unsafe_hash=True)
class AIAirTankerSpawn(AIAircraftSpawn):
    """Dataclass for unit AIAirTankerSpawn"""
    pass


@dataclass(unsafe_hash=True)
class RocketArtilleryUnitSpawn(ArtilleryUnitSpawn):
    """Dataclass for unit RocketArtilleryUnitSpawn"""
    default_shots_per_salvo: Optional[float] = None
    # (C#: Default Shots Per Salvo - float)
    ripple_rate: Optional[float] = None
    # (C#: Ripple Rate - float)
    allow_reload: Optional[bool] = None
    # (C#: Allow Reload - bool)
    reload_time: Optional[float] = None
    # (C#: Reload Time (s) - float)


@dataclass(unsafe_hash=True)
class PlayerSpawn(UnitSpawn):
    """Dataclass for unit PlayerSpawn"""
    start_mode: Optional[Literal["Cold", "FlightReady", "FlightAP"]] = None
    # (C#: Start Mode - string)
    #     Format: Unknown complex type: FlightStartModes
    initial_speed: Optional[float] = None
    # (C#: Initial Airspeed - float)
    unit_group: Optional[str] = None
    # (C#: Aircraft Group - string)
    #     Format: The ID (string) of a Unit Group.


# Populate the helper dict
field_names.update({
    "UnitSpawn": [
        "receive_friendly_damage"
    ],
    "AIUnitSpawn": [
        "engage_enemies",
        "detection_mode",
        "spawn_on_start",
        "invincible",
        "combat_target",
        "respawnable"
    ],
    "AIDecoyLauncherSpawn": [],
    "AIUnitSpawnEquippable": [
        "equips"
    ],
    "AISeaUnitSpawn": [
        "unit_group",
        "default_behavior",
        "default_waypoint",
        "default_path",
        "hull_number"
    ],
    "AIDecoyRadarSpawn": [],
    "AIAircraftSpawn": [
        "unit_group",
        "voice_profile",
        "player_commands_mode",
        "default_behavior",
        "initial_speed",
        "default_nav_speed",
        "default_orbit_point",
        "default_path",
        "orbit_altitude",
        "fuel",
        "auto_refuel",
        "auto_r_t_b",
        "default_radar_enabled",
        "allow_jamming_at_will",
        "parked_start_mode"
    ],
    "AIAWACSSpawn": [
        "awacs_voice_profile",
        "comms_enabled",
        "report_to_groups"
    ],
    "AIMissileSilo": [],
    "GroundUnitSpawn": [
        "unit_group",
        "move_speed",
        "behavior",
        "default_path",
        "waypoint",
        "stop_to_engage"
    ],
    "AIJTACSpawn": [],
    "AIFixedSAMSpawn": [
        "radar_units",
        "allow_reload",
        "reload_time",
        "allow_h_o_j"
    ],
    "AILockingRadarSpawn": [],
    "AICarrierSpawn": [
        "lso_freq",
        "carrier_spawns"
    ],
    "ArtilleryUnitSpawn": [],
    "MultiplayerSpawn": [
        "vehicle",
        "selectable_alt_spawn",
        "slot_label",
        "unit_group",
        "start_mode",
        "equipment",
        "initial_speed",
        "rtb_is_spawn",
        "limited_lives",
        "life_count",
        "b_eq_assignment_mode",
        "livery_ref"
    ],
    "AIDroneCarrierSpawn": [],
    "RearmingUnitSpawn": [
        "spawn_on_start"
    ],
    "AIGroundECMSpawn": [],
    "APCUnitSpawn": [],
    "IFVSpawn": [
        "allow_reload",
        "reload_time"
    ],
    "AIGroundMWSSpawn": [
        "radar_units",
        "decoy_units",
        "units_to_defend",
        "defense_units",
        "jammer_units"
    ],
    "AIAirTankerSpawn": [],
    "RocketArtilleryUnitSpawn": [
        "default_shots_per_salvo",
        "ripple_rate",
        "allow_reload",
        "reload_time"
    ],
    "PlayerSpawn": [
        "start_mode",
        "initial_speed",
        "unit_group"
    ]
})

# --- FACTORY ---

# This maps the ID to the correct Python class
ID_TO_CLASS = {
    "ABomberAI": AIAircraftSpawn,
    "aDecoyRadarTransmitter": AIDecoyRadarSpawn,
    "AEW-50": AIAWACSSpawn,
    "aIRMDlauncher": AIUnitSpawn,
    "AIUCAV": AIAircraftSpawn,
    "AJammerTruck": AIGroundECMSpawn,
    "AlliedAAShip": AICarrierSpawn,
    "AlliedBackstopSAM": AIFixedSAMSpawn,
    "AlliedCarrier": AICarrierSpawn,
    "alliedCylinderTent": AIUnitSpawn,
    "AlliedEWRadar": AILockingRadarSpawn,
    "AlliedIFV": IFVSpawn,
    "alliedMBT1": GroundUnitSpawn,
    "AlliedRearmRefuelPoint": RearmingUnitSpawn,
    "AlliedRearmRefuelPointB": RearmingUnitSpawn,
    "AlliedRearmRefuelPointC": RearmingUnitSpawn,
    "AlliedRearmRefuelPointD": RearmingUnitSpawn,
    "AlliedSoldier": AIJTACSpawn,
    "AlliedSoldierMANPAD": GroundUnitSpawn,
    "ALogisticTruck": GroundUnitSpawn,
    "AMWSTruck Variant": AIGroundMWSSpawn,
    "APC": APCUnitSpawn,
    "ARocketTruck": RocketArtilleryUnitSpawn,
    "Artillery": ArtilleryUnitSpawn,
    "ASF-30": AIAircraftSpawn,
    "ASF-33": AIAircraftSpawn,
    "ASF-58": AIAircraftSpawn,
    "AV-42CAI": AIAircraftSpawn,
    "BSTOPRadar": AILockingRadarSpawn,
    "bunker1": AIUnitSpawn,
    "bunker2": AIUnitSpawn,
    "bunkerHillside": AIUnitSpawn,
    "bunkerHillsideAllied": AIUnitSpawn,
    "cylinderTent": AIUnitSpawn,
    "DroneCarrier": AIDroneCarrierSpawn,
    "DroneGunBoat": AISeaUnitSpawn,
    "DroneGunBoatRocket": AISeaUnitSpawn,
    "DroneMissileCruiser": AISeaUnitSpawn,
    "E-4": AIAWACSSpawn,
    "EBomberAI": AIAircraftSpawn,
    "eDecoyRadarTransmitter": AIDecoyRadarSpawn,
    "EF-24 AI": AIAircraftSpawn,
    "eIRMDlauncher": AIUnitSpawn,
    "EJammerTruck": AIGroundECMSpawn,
    "ELogisticsTruck": GroundUnitSpawn,
    "EMWSTruck": AIGroundMWSSpawn,
    "EnemyAPC": APCUnitSpawn,
    "EnemyCarrier": AICarrierSpawn,
    "enemyMBT1": GroundUnitSpawn,
    "EnemyRearmRefuelPoint": RearmingUnitSpawn,
    "EnemyRearmRefuelPointB": RearmingUnitSpawn,
    "EnemyRearmRefuelPointC": RearmingUnitSpawn,
    "EnemyRearmRefuelPointD": RearmingUnitSpawn,
    "EnemySoldier": AIJTACSpawn,
    "EnemySoldierMANPAD": GroundUnitSpawn,
    "ERocketTruck": RocketArtilleryUnitSpawn,
    "EscortCruiser": AICarrierSpawn,
    "ESuperMissileCruiser": AISeaUnitSpawn,
    "ewRadarPyramid": AILockingRadarSpawn,
    "ewRadarSphere": AILockingRadarSpawn,
    "F-45A AI": AIAircraftSpawn,
    "FA-26B AI": AIAircraftSpawn,
    "factory1": AIUnitSpawn,
    "factory1e": AIUnitSpawn,
    "GAV-25": AIAircraftSpawn,
    "IFV-1": IFVSpawn,
    "IRAPC": APCUnitSpawn,
    "KC-49": AIAirTankerSpawn,
    "MAD-4Launcher": AIFixedSAMSpawn,
    "MAD-4Radar": AILockingRadarSpawn,
    "MineBoat": AISeaUnitSpawn,
    "missileSilo_a": AIMissileSilo,
    "missileSilo_e": AIMissileSilo,
    "MQ-31": AIAirTankerSpawn,
    "MultiplayerSpawn": MultiplayerSpawn,
    "MultiplayerSpawnEnemy": MultiplayerSpawn,
    "PatRadarTrailer": AILockingRadarSpawn,
    "PatriotLauncher": AIFixedSAMSpawn,
    "PhallanxTruck": GroundUnitSpawn,
    "PlayerSpawn": PlayerSpawn,
    "SAAW": GroundUnitSpawn,
    "SamBattery1": AIFixedSAMSpawn,
    "SamFCR": AILockingRadarSpawn,
    "SamFCR2": AILockingRadarSpawn,
    "SLAIM120Truck": AIFixedSAMSpawn,
    "slmrmLauncher": AIFixedSAMSpawn,
    "slmrmRadar": AILockingRadarSpawn,
    "SRADTruck": GroundUnitSpawn,
    "staticAAA-20x2": AIUnitSpawn,
    "staticCIWS": AIUnitSpawn,
    "staticDecoyLauncher": AIDecoyLauncherSpawn,
    "staticDecoyLauncherA": AIDecoyLauncherSpawn,
    "staticUcavLauncher": AIUnitSpawn,
    "T-55 AI": AIAircraftSpawn,
    "T-55 AI-E": AIAircraftSpawn,
    "WatchmanTruck": AILockingRadarSpawn,

}

UNIT_CLASS_TO_ACTION_CLASS = {
    # --- Base AI Classes ---
    AIUnitSpawn: AIUnitSpawnActions,
    AIUnitSpawnEquippable: AIUnitSpawnEquippableActions,

    # --- Aircraft Hierarchy ---
    AIAircraftSpawn: AIAircraftSpawnActions,
    AIAWACSSpawn: AIAWACSSpawnActions,
    AIAirTankerSpawn: AIAirTankerSpawnActions,

    # --- Ground Unit Hierarchy ---
    GroundUnitSpawn: GroundUnitSpawnActions,
    AIFixedSAMSpawn: AIFixedSAMSpawnActions,
    AIGroundECMSpawn: AIGroundECMSpawnActions,
    AIJTACSpawn: AIJTACSpawnActions,
    AILockingRadarSpawn: AILockingRadarSpawnActions,
    ArtilleryUnitSpawn: ArtilleryUnitSpawnActions,
    APCUnitSpawn: APCUnitSpawnActions,
    IFVSpawn: IFVSpawnActions,
    # Note: AIGroundMWSSpawn and RocketArtilleryUnitSpawn will inherit actions
    # from their parents (GroundUnitSpawn and ArtilleryUnitSpawn respectively)
    # as they don't have specific action classes listed in the imports.

    # --- Sea Unit Hierarchy ---
    AISeaUnitSpawn: AISeaUnitSpawnActions,
    AICarrierSpawn: AICarrierSpawnActions,
    AIDroneCarrierSpawn: AIDroneCarrierSpawnActions,

    # --- Other AI Units ---
    AIDecoyLauncherSpawn: AIDecoyLauncherSpawnActions,
    AIDecoyRadarSpawn: AIDecoyRadarSpawnActions,
    AIMissileSilo: AIMissileSiloActions,

    # --- Player/Multiplayer ---
    PlayerSpawn: PlayerSpawnActions,
    MultiplayerSpawn: MultiplayerSpawnActions,

    # Note: RearmingUnitSpawn does not have a specific action class
}

def create_unit(
    id_name: str,
    unit_name: str,
    team: str,
    global_position: List[float],
    rotation: List[float],
    **kwargs
) -> "Unit":
    """
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
    """
    id_name_str = str(id_name)
    if id_name_str not in ID_TO_CLASS:
        raise KeyError(f"Unit ID '{id_name_str}' not found in database.")

    ClassToCreate = ID_TO_CLASS[id_name_str]

    # Get allowed field names (no changes needed here)
    allowed_field_names = set()
    cls_to_check = ClassToCreate
    while cls_to_check is not Unit:
        allowed_field_names.update(field_names.get(cls_to_check.__name__, []))
        if not cls_to_check.__mro__[1] or cls_to_check.__mro__[1] is object: break
        cls_to_check = cls_to_check.__mro__[1]

    # Validate kwargs (no changes needed here)
    for kwarg in kwargs:
        if kwarg not in allowed_field_names:
            raise TypeError(f"'{kwarg}' is not a valid parameter for Unit '{id_name_str}'.")

    # Base args (no changes needed here)
    base_args = {
        "unit_id": id_name, "unit_name": unit_name, "team": team,
        "global_position": global_position, "rotation": rotation,
    }

    # Create the instance (no changes needed here)
    unit_instance = ClassToCreate(**base_args, **kwargs)

    # --- Action attachment REMOVED from here ---
    # It will be handled in Mission.add_unit after the unitInstanceID is known.

    return cast("Unit", unit_instance)
