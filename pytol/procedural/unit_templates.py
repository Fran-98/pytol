from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, Dict, Set, Any
import random
import dataclasses

from pytol.classes.units import ID_TO_CLASS, UNIT_CLASS_TO_ACTION_CLASS, create_unit
from pytol.classes.units import (
        AIAircraftSpawn,
        AISeaUnitSpawn,
        GroundUnitSpawn,
        AIFixedSAMSpawn,
        APCUnitSpawn,
        ArtilleryUnitSpawn,
)
from pytol.resources import resources as resource_utils
import re


def _infer_team_from_unit_id(unit_id: str) -> Set[str]:
    """
    Intelligently infer allowed teams from unit ID naming conventions.
    
    VTOL VR unit naming patterns:
    - Enemy-only: 'enemy*', 'E*' prefix (e.g., enemyMBT1, ELogisticsTruck, EnemyCarrier)
    - Allied-only: 'allied*', 'A*' prefix (e.g., alliedMBT1, ALogisticTruck, AlliedCarrier)
    - Multi-team: Generic names, AI aircraft, neutral units (e.g., Artillery, F-45A AI, bunker1)
    
    Args:
        unit_id: The unit's ID string from ID_TO_CLASS
        
    Returns:
        Set of allowed team names ("Allied", "Enemy", or both)
    """
    lower_id = unit_id.lower()
    
    # Enemy-specific patterns (but not EscortCruiser, E-4, EF-24, etc.)
    if lower_id.startswith('enemy') or (
        lower_id.startswith('e') and 
        not lower_id.startswith(('esc', 'e-', 'ef-', 'ew'))
    ):
        return {"Enemy"}
    
    # Allied-specific patterns (but not Aircraft: AV-42, ASF-*, AEW-*)
    if lower_id.startswith('allied') or (
        lower_id.startswith('a') and 
        not lower_id.startswith(('av-', 'asf', 'aew', 'abomber', 'aiucav', 'artillery'))
    ):
        return {"Allied"}
    
    # Everything else is multi-team (generic units, AI aircraft, static objects)
    return {"Allied", "Enemy"}


# Auto-generate unit team database from complete unit registry
# This provides full coverage of all ~100 VTOL VR units
def _generate_unit_team_database() -> Dict[str, Set[str]]:
    """Generate complete unit team database from ID_TO_CLASS registry."""
    # Use the authoritative ID_TO_CLASS mapping from classes.units
    return {unit_id: _infer_team_from_unit_id(unit_id) for unit_id in ID_TO_CLASS.keys()}


# Unit database: maps unitID -> allowed teams based on VTOL VR naming conventions
# Auto-generated from complete unit registry with intelligent team inference
UNIT_TEAM_DATABASE: Dict[str, Set[str]] = _generate_unit_team_database()


@dataclass
class UnitTemplate:
    """Simple unit template for procedural spawning."""
    unit_type: str
    name: str
    team: str
    behavior: str = "Parked"
    engage_enemies: bool = True
    # Optional introspected capabilities
    fields: Dict[str, Any] = dataclasses.field(default_factory=dict)
    actions: List[str] = dataclasses.field(default_factory=list)
    
    def __post_init__(self):
        """Validate that this unit can be assigned to the specified team."""
        # All units should be in database now (auto-generated from ID_TO_CLASS)
        if self.unit_type not in UNIT_TEAM_DATABASE:
            # This should rarely happen now, but allow with warning
            import warnings
            warnings.warn(
                f"Unit '{self.unit_type}' not in UNIT_TEAM_DATABASE. "
                f"Team assignment cannot be validated.",
                UserWarning
            )
            return
        
        allowed_teams = UNIT_TEAM_DATABASE[self.unit_type]
        if self.team not in allowed_teams:
            raise ValueError(
                f"Unit '{self.unit_type}' cannot be assigned to team '{self.team}'. "
                f"Allowed teams: {allowed_teams}"
            )


class UnitLibrary:
    """Minimal unit template library organized by faction and role.
    
    All units are validated against UNIT_TEAM_DATABASE to ensure
    they can only be assigned to appropriate teams.
    """
    
    # These collections are dynamically built by `build_from_registry` below.
    ENEMY_VEHICLES: List[UnitTemplate] = []
    ENEMY_SAMS: List[UnitTemplate] = []
    ENEMY_AIR: List[UnitTemplate] = []
    ENEMY_INFANTRY: List[UnitTemplate] = []
    ALLIED_VEHICLES: List[UnitTemplate] = []
    ALLIED_SAMS: List[UnitTemplate] = []
    ALLIED_INFANTRY: List[UnitTemplate] = []
    # Captures the unit_type membership of each category after the last build.
    LAST_SNAPSHOT: Dict[str, List[str]] = {}

    @staticmethod
    def _classify_role(unit_cls) -> str:
        """Best-effort role classification based on unit dataclass inheritance."""
        # First apply name-based heuristics for classes that are often
        # represented as specialized ground infantry/AA prefabs.
        try:
            name = getattr(unit_cls, '__name__', '') or ''
            lname = name.lower()
            # Common infantry tokens (these should be treated as infantry)
            if any(tok in lname for tok in ('infantry', 'soldier', 'manpad', 'rifle', 'inf')):
                return 'infantry'
            # Static anti-air tokens (editor prefabs sometimes use 'static' prefixes)
            if any(tok in lname for tok in ('staticaaa', 'staticciws', 'ciws', 'aaa', 'aa')):
                return 'aa'
        except Exception:
            pass

        # Fallback to inheritance checks for higher-fidelity classification
        try:
            if issubclass(unit_cls, AIAircraftSpawn):
                return 'air'
            if issubclass(unit_cls, AISeaUnitSpawn):
                return 'sea'
            if issubclass(unit_cls, AIFixedSAMSpawn):
                return 'sam'
            if issubclass(unit_cls, ArtilleryUnitSpawn):
                return 'artillery'
            if issubclass(unit_cls, APCUnitSpawn):
                return 'apc'
            if issubclass(unit_cls, GroundUnitSpawn):
                return 'ground'
        except Exception:
            pass

        # fallback
        return 'generic'

    @staticmethod
    def _introspect_unit(unit_id: str):
        """Return introspected fields and actions for a unit id using registry maps."""
        unit_cls = ID_TO_CLASS.get(unit_id)
        fields = {}
        actions = []
        if unit_cls is None:
            return fields, actions
        # dataclass fields (name -> type)
        try:
            for f in dataclasses.fields(unit_cls):
                fields[f.name] = f.type
        except Exception:
            # best-effort fallback: read __annotations__
            fields = getattr(unit_cls, '__annotations__', {}) or {}

        # action class mapping
        action_cls = None
        for cls_key, a_cls in UNIT_CLASS_TO_ACTION_CLASS.items():
            try:
                if issubclass(unit_cls, cls_key):
                    action_cls = a_cls
                    break
            except Exception:
                continue
        if action_cls is not None:
            actions = [n for n in dir(action_cls) if not n.startswith('_')]
        return fields, actions

    @classmethod
    def build_from_registry(cls):
        """Build dynamic template lists from the game's ID_TO_CLASS registry.

        This inspects class inheritance, available fields, and linked action
        classes to provide a richer UnitTemplate set for PCG.
        """
        # Reset lists
        cls.ENEMY_VEHICLES = []
        cls.ENEMY_SAMS = []
        cls.ENEMY_AIR = []
        cls.ENEMY_INFANTRY = []
        cls.ALLIED_VEHICLES = []
        cls.ALLIED_SAMS = []
        cls.ALLIED_INFANTRY = []
        snapshot: Dict[str, List[str]] = {
            "ENEMY_VEHICLES": [],
            "ENEMY_SAMS": [],
            "ENEMY_AIR": [],
            "ENEMY_INFANTRY": [],
            "ALLIED_VEHICLES": [],
            "ALLIED_SAMS": [],
            "ALLIED_INFANTRY": [],
        }

        for unit_id, unit_cls in ID_TO_CLASS.items():
            roles = cls._classify_role(unit_cls)
            teams = UNIT_TEAM_DATABASE.get(unit_id, {"Enemy", "Allied"})
            # default team preference when both allowed: Enemy (so pick_enemy_set returns threats)
            team = 'Enemy' if 'Enemy' in teams else next(iter(teams))
            fields, actions = cls._introspect_unit(unit_id)
            # infer behavior
            behavior = 'Parked'
            if 'default_behavior' in fields:
                behavior = 'Default'
            elif 'behavior' in fields:
                behavior = 'Patrol'

            tpl = UnitTemplate(unit_type=unit_id, name=unit_id, team=team, behavior=behavior, engage_enemies=True, fields=fields, actions=actions)

            # Place into best-fit list(s)
            if roles == 'air':
                if team == 'Enemy':
                    cls.ENEMY_AIR.append(tpl)
                    snapshot["ENEMY_AIR"].append(unit_id)
                else:
                    # allied air handled via allied lists (not used much today)
                    pass
            elif roles == 'sam':
                if team == 'Enemy':
                    cls.ENEMY_SAMS.append(tpl)
                    snapshot["ENEMY_SAMS"].append(unit_id)
                else:
                    cls.ALLIED_SAMS.append(tpl)
                    snapshot["ALLIED_SAMS"].append(unit_id)
            elif roles == 'ground' or roles == 'apc' or roles == 'artillery':
                if team == 'Enemy':
                    cls.ENEMY_VEHICLES.append(tpl)
                    snapshot["ENEMY_VEHICLES"].append(unit_id)
                else:
                    cls.ALLIED_VEHICLES.append(tpl)
                    snapshot["ALLIED_VEHICLES"].append(unit_id)
            elif 'infantry' in unit_id.lower() or 'soldier' in unit_id.lower() or 'manpad' in unit_id.lower():
                if team == 'Enemy':
                    cls.ENEMY_INFANTRY.append(tpl)
                    snapshot["ENEMY_INFANTRY"].append(unit_id)
                else:
                    cls.ALLIED_INFANTRY.append(tpl)
                    snapshot["ALLIED_INFANTRY"].append(unit_id)
            else:
                # Generic fallback: enemy vehicles preferred
                if team == 'Enemy':
                    cls.ENEMY_VEHICLES.append(tpl)
                    snapshot["ENEMY_VEHICLES"].append(unit_id)
                else:
                    cls.ALLIED_VEHICLES.append(tpl)
                    snapshot["ALLIED_VEHICLES"].append(unit_id)

        # Keep lists stable order for determinism (sort by unit_type)
        for key in ('ENEMY_VEHICLES', 'ENEMY_SAMS', 'ENEMY_AIR', 'ENEMY_INFANTRY', 'ALLIED_VEHICLES', 'ALLIED_SAMS', 'ALLIED_INFANTRY'):
            lst = getattr(cls, key)
            lst.sort(key=lambda x: x.unit_type)
            snapshot[key] = [tpl.unit_type for tpl in lst]

        cls.LAST_SNAPSHOT = snapshot

    # Mapping from abstract planner terminals to concrete unit IDs in ID_TO_CLASS.
    # Populate with sensible defaults to help PCG materialize abstract tokens.
    # Uses actual unit prefab database to ensure mappings point to real units.
    ABSTRACT_TO_CONCRETE: Dict[str, str] = {
        # Base/Airport tokens
        'enemy_airbase': 'EnemyRearmRefuelPoint',
        'airbase': 'EnemyRearmRefuelPoint',
        'rearm_point': 'EnemyRearmRefuelPoint',
        'friendly_airbase': 'AlliedRearmRefuelPoint',
        
        # Radar tokens
        'radar': 'ewRadarPyramid',
        'Radar': 'ewRadarPyramid',
        'ew_radar': 'ewRadarPyramid',
        'early_warning_radar': 'ewRadarPyramid',
        'fcr': 'SamFCR',
        'fire_control_radar': 'SamFCR',
        
        # SAM/AA tokens
        'SAM': 'SamBattery1',
        'sam': 'SamBattery1',
        'sam_site': 'SamBattery1',
        'mobile_sam': 'SamBattery1',
        'static_sam': 'SamBattery1',
        'battery': 'SamBattery1',
        'aaa': 'staticAAA-20x2',
        'aa': 'staticAAA-20x2',
        'anti_air': 'staticAAA-20x2',
        
        # Naval tokens
        'escort': 'EscortCruiser',
        'carrier': 'EnemyCarrier',
        'carrier_group': 'EnemyCarrier',
        'friendly_carrier': 'AlliedCarrier',
        'cruiser': 'EscortCruiser',
        'destroyer': 'EnemyAAShip',
        'ship': 'EnemyAAShip',
        'aaship': 'EnemyAAShip',
        
        # Logistics/Transport tokens
        'transport': 'ELogisticsTruck',
        'ammo_truck': 'ELogisticsTruck',
        'logistics': 'ELogisticsTruck',
        'logistics_truck': 'ELogisticsTruck',
        'supply_truck': 'ELogisticsTruck',
        'truck': 'ELogisticsTruck',
        'convoy': 'ELogisticsTruck',
        'enemy_convoy_screen': 'ELogisticsTruck',
        
        # Ground vehicle tokens
        'enemy_unit': 'enemyMBT1',
        'enemy_mbt': 'enemyMBT1',
        'mbt': 'enemyMBT1',
        'armour': 'enemyMBT1',
        'tank': 'enemyMBT1',
        'apc': 'EnemyAPC',
        'ifv': 'IFV-1',
        'artillery': 'Artillery',
        'howitzer': 'Artillery',
        'enemy_artillery_battery': 'Artillery',
        
        # Infantry tokens
        'infantry': 'EnemySoldier',
        'soldier': 'EnemySoldier',
        'manpad': 'EnemySoldierMANPAD',
        'man_pad': 'EnemySoldierMANPAD',
        
        # Aircraft tokens
        'fighter': 'ASF-30',
        'cap': 'ASF-30',
        'enemy_cap_flight': 'ASF-30',
        'interceptor': 'ASF-33',
        'bomber': 'EBomberAI',
        'helicopter': 'GAV-25',
        'heli': 'GAV-25',
        'uav': 'AIUCAV',
        'recon': 'AIUCAV',
        'drone': 'AIUCAV',
        
        # Support aircraft tokens (from grammar: AI_TASK:AWACS, AI_TASK:TANKER)
        'awacs': 'AEW-50',  # Enemy AWACS
        'AWACS': 'AEW-50',
        'aew': 'AEW-50',
        'early_warning': 'AEW-50',
        'friendly_awacs': 'E-4',  # Allied AWACS
        'tanker': 'KC-49',  # Allied tanker
        'TANKER': 'KC-49',
        'refuel': 'KC-49',
        'refueler': 'KC-49',
        
        # Static structure tokens
        'bunker': 'bunker1',
        'factory': 'factory1e',
        'missile_silo': 'missileSilo_e',
        'silo': 'missileSilo_e',
        
        # Patrol/Background tokens
        'patrol': 'EnemyAAShip',
        'patrol_boat': 'EnemyAAShip',
        
        # Generic fallbacks (use most common unit type)
        'enemy_aircraft': 'ASF-30',
        'friendly_aircraft': 'F-45A AI',
        'enemy_vehicle': 'enemyMBT1',
        'friendly_vehicle': 'alliedMBT1',
    }

    @staticmethod
    def resolve_abstract(token: str) -> str | None:
        """Resolve an abstract planner terminal to a concrete unit ID if known.

        Returns the concrete unit ID string or None if no mapping exists.
        Validates that the resolved unit exists in ID_TO_CLASS before returning.
        """
        if not token:
            return None
        
        # Direct match first
        resolved = None
        if token in UnitLibrary.ABSTRACT_TO_CONCRETE:
            resolved = UnitLibrary.ABSTRACT_TO_CONCRETE[token]
        else:
            # Case-insensitive match
            low = token.lower()
            for k, v in UnitLibrary.ABSTRACT_TO_CONCRETE.items():
                if k.lower() == low:
                    resolved = v
                    break
        
        if resolved:
            # Validate that the resolved unit actually exists in ID_TO_CLASS
            if resolved in ID_TO_CLASS:
                return resolved
            else:
                # Log warning and try to find a similar unit from the database
                from pytol.resources import get_all_unit_prefabs
                all_units = get_all_unit_prefabs()
                # Try fuzzy match (case-insensitive, partial)
                resolved_lower = resolved.lower()
                for unit_id in all_units:
                    if unit_id.lower() == resolved_lower:
                        return unit_id
                    # Try partial match for common patterns
                    if resolved_lower.replace('-', '').replace('_', '').replace(' ', '') in unit_id.lower().replace('-', '').replace('_', '').replace(' ', ''):
                        return unit_id
        
        return None

    @staticmethod
    def template_to_unit_info(tpl: UnitTemplate, rng: random.Random, position: Tuple[float, float, float], description: str) -> Dict[str, Any]:
        """Materialize a UnitTemplate into a lightweight unit info dict for WSM.

        This fills a small set of commonly-used unit fields when the unit's
        dataclass exposes them (e.g., fuel, default_behavior, equips). The
        values chosen are conservative sensible defaults to make generated
        missions more realistic without touching the full prefab defaults.
        """
        info: Dict[str, Any] = {
            "type": tpl.unit_type,
            "pos": position,
            "description": description,
        }

        # Lightweight defaults keyed by common unit dataclass fields
        defaults: Dict[str, Any] = {
            "fuel": 100.0,
            "default_behavior": tpl.behavior if tpl.behavior in ("Parked", "Orbit", "Path", "TakeOff", "Default", "Patrol") else "Parked",
            "equips": [],
            "unit_group": "",
            "initial_speed": 0.0,
            "default_nav_speed": None,
            "orbit_altitude": 1000.0,
            "auto_refuel": True,
            "allow_reload": False,
            "radar_units": [],
            "carrier_spawns": {},
        }

        # Populate only fields that the template actually exposes
        for fname in tpl.fields.keys():
            if fname in defaults:
                info[fname] = defaults[fname]

        # Merge prefab-specific defaults when available (from resources)
        try:
            _PREFAB_DEFAULTS = resource_utils.load_json_data('prefab_defaults_per_prefab.json') or {}
            prefab_defaults = _PREFAB_DEFAULTS.get(tpl.unit_type, {}).get('defaults', {})
        except Exception:
            prefab_defaults = {}

        def _camel_to_snake(name: str) -> str:
            s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
            return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

        for k, v in prefab_defaults.items():
            # try direct match or camel->snake conversion
            target = None
            if k in tpl.fields:
                target = k
            else:
                sk = _camel_to_snake(k)
                if sk in tpl.fields:
                    target = sk
                elif k.lower() in tpl.fields:
                    target = k.lower()
            if not target:
                # last resort: normalize keys and compare
                norm_k = ''.join(ch.lower() for ch in str(k) if ch.isalnum())
                for cand in tpl.fields.keys():
                    cand_norm = ''.join(ch.lower() for ch in str(cand) if ch.isalnum())
                    if cand_norm == norm_k:
                        target = cand
                        break
            if not target:
                continue
            # don't overwrite position/name
            if target in ('type', 'pos', 'description'):
                continue
            info[target] = v

        return info
    
    @staticmethod
    def template_to_unit_object(tpl: UnitTemplate, rng: random.Random, position: Tuple[float, float, float], unit_name: str | None = None):
        """Create a real Unit dataclass instance using the canonical factory.

        This delegates prefab default merging and field coercion to
        `pytol.classes.units.create_unit`, ensuring the resulting Unit
        instance matches the game's expected dataclass shape and defaulting
        behavior.
        """
        # create_unit expects lists for positions/rotation
        gp = [float(position[0]), float(position[1]), float(position[2])]
        rotation = [0.0, 0.0, 0.0]
        name = unit_name or tpl.name or tpl.unit_type
        # Minimal kwargs: rely on create_unit to merge prefab defaults
        try:
            unit_obj = create_unit(tpl.unit_type, name, tpl.team, gp, rotation)
            return unit_obj
        except Exception:
            # Raise so callers can fallback to legacy behavior
            raise
    @staticmethod
    def pick_enemy_set(mission_type: str, difficulty: str, rng: random.Random, threat_level: str = None) -> List[UnitTemplate]:
        """
        Select enemy units based on mission type, difficulty, and threat level.
        
        All returned units are validated to ensure they can be assigned to Enemy team.
        
        Args:
            mission_type: Mission type (strike, sead, cas, intercept, transport)
            difficulty: Difficulty level (easy, normal, hard)
            rng: Random number generator
            threat_level: Optional threat level (low, medium, high, extreme) - if provided,
                         influences unit selection and counts
        
        Returns list of templates to spawn.
        """
        templates = []
        
        # Map threat level to difficulty if provided, otherwise use difficulty
        if threat_level:
            threat_to_difficulty = {
                'low': 'easy',
                'medium': 'normal',
                'high': 'hard',
                'extreme': 'hard'
            }
            effective_difficulty = threat_to_difficulty.get(threat_level.lower(), difficulty)
        else:
            effective_difficulty = difficulty
        
        # Base spawn count by difficulty (threat level affects this)
        count_mult = {"easy": 1, "normal": 2, "hard": 3}.get(effective_difficulty, 2)
        
        # Threat level also affects diversity - higher threat = more unit types
        if threat_level:
            threat_lower = threat_level.lower()
            if threat_lower == 'low':
                count_mult = max(1, count_mult - 1)  # Fewer units
            elif threat_lower == 'extreme':
                count_mult = count_mult + 1  # More units
        
        if mission_type == "strike":
            # Ground vehicles/structures
            if UnitLibrary.ENEMY_VEHICLES:
                templates.extend(rng.choices(UnitLibrary.ENEMY_VEHICLES, k=2 * count_mult))
            # Add light infantry for defense (fallback to vehicles if none)
            if UnitLibrary.ENEMY_INFANTRY:
                templates.extend(rng.choices(UnitLibrary.ENEMY_INFANTRY, k=count_mult))
            elif UnitLibrary.ENEMY_VEHICLES:
                templates.extend(rng.choices(UnitLibrary.ENEMY_VEHICLES, k=count_mult))
        
        elif mission_type == "sead":
            # SAM sites and radars - primary targets
            if UnitLibrary.ENEMY_SAMS:
                templates.extend(rng.choices(UnitLibrary.ENEMY_SAMS, k=2 * count_mult))
            else:
                # fallback to vehicles
                if UnitLibrary.ENEMY_VEHICLES:
                    templates.extend(rng.choices(UnitLibrary.ENEMY_VEHICLES, k=2 * count_mult))
            # Supporting ground forces
            if UnitLibrary.ENEMY_VEHICLES:
                templates.extend(rng.choices(UnitLibrary.ENEMY_VEHICLES, k=count_mult))
        
        elif mission_type == "cas":
            # Mobile ground targets
            if UnitLibrary.ENEMY_VEHICLES:
                templates.extend(rng.choices(UnitLibrary.ENEMY_VEHICLES, k=2 * count_mult))
            if UnitLibrary.ENEMY_INFANTRY:
                templates.extend(rng.choices(UnitLibrary.ENEMY_INFANTRY, k=2 * count_mult))
            else:
                # fallback to vehicles
                if UnitLibrary.ENEMY_VEHICLES:
                    templates.extend(rng.choices(UnitLibrary.ENEMY_VEHICLES, k=2 * count_mult))
        
        elif mission_type == "intercept":
            # Hostile air patrol
            if UnitLibrary.ENEMY_AIR:
                templates.extend(rng.choices(UnitLibrary.ENEMY_AIR, k=count_mult))
            # Add ground radar support (based on effective difficulty)
            if effective_difficulty in ["normal", "hard"]:
                # Try to find radar template or create one
                radar_found = False
                for tpl in UnitLibrary.ENEMY_SAMS:
                    if 'radar' in tpl.unit_type.lower() or tpl.unit_type == 'ewRadarPyramid':
                        templates.append(tpl)
                        radar_found = True
                        break
                if not radar_found:
                    # Create a simple radar template
                    templates.append(UnitTemplate("ewRadarPyramid", "Early Warning Radar", "Enemy"))
        
        elif mission_type == "transport":
            # Light ground threats near LZ
            if UnitLibrary.ENEMY_INFANTRY:
                templates.extend(rng.choices(UnitLibrary.ENEMY_INFANTRY, k=count_mult))
            elif UnitLibrary.ENEMY_VEHICLES:
                templates.extend(rng.choices(UnitLibrary.ENEMY_VEHICLES, k=count_mult))
            # Add vehicle threats for harder difficulties
            if difficulty == "hard":
                templates.extend(rng.choices(UnitLibrary.ENEMY_VEHICLES, k=1))
        
        return templates
    
    @staticmethod
    def pick_support_set(player_role: str, mission_duration: int, rng: random.Random) -> List[UnitTemplate]:
        """
        Select friendly support units based on player role and mission duration.
        
        Args:
            player_role: Player role (strike, sead, cas, cap, recon)
            mission_duration: Mission duration in minutes
            rng: Random number generator
        
        Returns:
            List of friendly unit templates for support
        """
        templates = []
        
        # Long missions may need tanker support
        if mission_duration > 45:
            # Add tanker (if available in game - placeholder for now)
            # Tankers are typically aircraft units, would need to check ALLIED lists
            pass
        
        # CAS missions benefit from ground support
        if player_role.lower() == 'cas':
            if UnitLibrary.ALLIED_VEHICLES:
                templates.extend(rng.choices(UnitLibrary.ALLIED_VEHICLES, k=1))
        
        # CAP missions might have AWACS support
        if player_role.lower() in ('cap', 'intercept'):
            # AWACS would be air units - placeholder for now
            pass
        
        # SEAD missions might have escort aircraft
        if player_role.lower() in ('sead', 'strike'):
            # Escort aircraft would be air units - placeholder for now
            pass
        
        return templates
    
    @staticmethod
    def pick_allied_set(mission_type: str, difficulty: str, rng: random.Random) -> List[UnitTemplate]:
        """
        Pick allied units for transport/escort missions.
        
        All returned units are validated to ensure they can be assigned to Allied team.
        """
        templates = []
        
        if mission_type == "transport":
            # Units to pick up/escort
            count = {"easy": 1, "normal": 2, "hard": 3}.get(difficulty, 2)
            templates.extend(rng.choices(UnitLibrary.ALLIED_INFANTRY, k=count))
            
            # Add vehicles for harder difficulties
            if difficulty in ["normal", "hard"]:
                templates.extend(rng.choices(UnitLibrary.ALLIED_VEHICLES, k=1))
        
        return templates
    
    @staticmethod
    def validate_unit_team(unit_id: str, team: str) -> bool:
        """
        Check if a unit can be assigned to a specific team.
        
        Args:
            unit_id: The unit's ID from the game database
            team: The team to assign ("Allied", "Enemy", "Neutral")
            
        Returns:
            True if the unit can be used by this team, False otherwise
        """
        if unit_id not in UNIT_TEAM_DATABASE:
            # Unknown unit - could be new/modded content
            return True
        
        allowed_teams = UNIT_TEAM_DATABASE[unit_id]
        return team in allowed_teams
    
    @staticmethod
    def get_available_units_for_team(team: str) -> List[str]:
        """
        Get all unit IDs that can be assigned to a specific team.
        
        Args:
            team: The team name ("Allied", "Enemy", "Neutral")
            
        Returns:
            List of unit IDs that can be used by this team
        """
        return [
            unit_id for unit_id, allowed_teams in UNIT_TEAM_DATABASE.items()
            if team in allowed_teams
        ]


@dataclass
class SpawnPlan:
    """Plan for spawning units at a location."""
    templates: List[UnitTemplate]
    spawn_center: Tuple[float, float, float]
    spread_radius: float = 500.0
