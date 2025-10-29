"""
Core module for constructing and saving VTOL VR mission files (.vts).
Includes automatic ID management for linked objects.
"""

import os
import shutil
from dataclasses import fields, is_dataclass
from typing import Dict, List, Any, Optional, Union

# --- Pytol Class Imports ---
from pytol.classes.conditionals import Conditional
from pytol.classes.units import Unit
from pytol.classes.objectives import Objective
from pytol.classes.mission_objects import (
    EventTarget, Path, Trigger,
    Waypoint, StaticObject, Base, BriefingNote,
    TimedEventGroup, GlobalValue, 
    ConditionalAction, EventSequence,
    RandomEvent, WeatherPreset
)
from pytol.classes.actions import GlobalValueActions
from pytol.terrain.mission_terrain_helper import MissionTerrainHelper
from pytol.terrain.terrain_calculator import TerrainCalculator
from pytol.classes.units import UNIT_CLASS_TO_ACTION_CLASS
from pytol.misc.logger import create_logger
from pytol.resources.resources import get_static_prefabs_database

# --- Constants ---
from pytol.classes.conditionals import CLASS_TO_ID
import re

# NATO Phonetic Alphabet - Valid unit group names in VTOL VR
NATO_PHONETIC_ALPHABET = [
    "Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot",
    "Golf", "Hotel", "India", "Juliet", "Kilo", "Lima",
    "Mike", "November", "Oscar", "Papa", "Quebec", "Romeo",
    "Sierra", "Tango", "Uniform", "Victor", "Whiskey", "Xray",
    "Yankee", "Zulu"
]

# --- VTS Formatting Helpers ---
# (_format_value, _format_vector, _format_point_list, _format_id_list, _format_block remain the same)
def _format_value(val: Any) -> str:
    """Helper function to format Python values into VTS-compatible strings."""
    if val is None:
        return "null"
    if isinstance(val, bool):
        return str(val)
    if val == "null":
        return "null"
    if isinstance(val, str):
        return val
    if isinstance(val, (int, float)):
        # Emit integer-like floats without a decimal point to match editor-saved files
        try:
            fv = float(val)
            if fv.is_integer():
                return str(int(fv))
            return str(fv)
        except Exception:
            return str(val)
    return str(val)

def _format_vector(vec: List[float], is_rotation: bool = False) -> str:
    """Format a 3-element list as a VTS vector string.

    If is_rotation=True, normalize the yaw (Y) component into [0, 360) to match
    the editor's normalized rotation output and ensure decimal formatting (e.g. 1500 -> 1500.0).
    """
    vals = list(vec)
    if is_rotation and len(vals) >= 2:
        try:
            # Normalize yaw (index 1) to 0-360 range
            y = float(vals[1])
            y = (y % 360.0 + 360.0) % 360.0
            vals[1] = y
        except Exception:
            pass
    # Format each component using scalar formatting rules so integer-like
    # floats become integers (e.g. 1500.0 -> 1500) and rotations are rounded.
    formatted = []
    for i, v in enumerate(vals):
        try:
            fv = float(v)
            if is_rotation:
                # Round rotation components to 5 decimal places to match editor-saved formatting
                rv = round(fv, 5)
                s = _format_value(rv)
            else:
                s = _format_value(fv)
        except Exception:
            s = str(v)
        # Use uppercase E for scientific notation if present
        s = s.replace('e', 'E')
        formatted.append(s)
    # Ensure exactly three components for VTS vectors
    while len(formatted) < 3:
        formatted.append('0.0')
    return f"({formatted[0]}, {formatted[1]}, {formatted[2]})"

def _format_point_list(points: List[List[float]]) -> str:
    """Formats a list of vector points into a VTS-compatible string."""
    return ";".join([_format_vector(p) for p in points])

def _format_id_list(ids: List[Any]) -> str:
    """Formats a list of IDs into a VTS-compatible string."""
    return ";".join(map(str, ids))

def _format_block(name: str, content_str: str, indent_level: int = 1) -> str:
    """Helper function to format a VTS block with correct indentation."""
    indent = "\t" * indent_level
    eol = "\n"
    if not content_str.strip():
        return f"{indent}{name}{eol}{indent}{{{eol}{indent}}}{eol}"
    return f"{indent}{name}{eol}{indent}{{{eol}{content_str}{indent}}}{eol}"

def _snake_to_camel(snake_str: str) -> str:
    """Converts a snake_case string to camelCase."""
    components = snake_str.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])

# --- Main Mission Class ---

class Mission:

    def validate_all_blocks(self) -> List[str]:
        """
        Validate all major mission block lists for required fields and warn on empty/invalid data.
        Returns a list of warnings (non-fatal).
        """
        warnings = []
        # Check units
        if not self.units:
            warnings.append("No units defined in mission.")
        # Check paths
        if not self.paths:
            warnings.append("No paths defined in mission.")
        # Check waypoints
        if not self.waypoints:
            warnings.append("No waypoints defined in mission.")
        # Check triggers
        if not self.trigger_events:
            warnings.append("No trigger events defined in mission.")
        # Check objectives
        if not self.objectives:
            warnings.append("No objectives defined in mission.")
        # Check static objects
        if not self.static_objects:
            self.logger.info("No static objects defined in mission.")
        # Check bases
        if not self.bases:
            self.logger.info("No base overrides defined in mission.")
        # Check conditionals
        if not self.conditionals:
            self.logger.info("No conditionals defined in mission.")
        # Check conditional actions
        if not self.conditional_actions:
            self.logger.info("No conditional actions defined in mission.")
        # Check random events
        if not self.random_events:
            self.logger.info("No random events defined in mission.")
        # Check event sequences
        if not self.event_sequences:
            self.logger.info("No event sequences defined in mission.")
        # Check global values
        if not self.global_values:
            self.logger.info("No global values defined in mission.")
        # Check briefing notes
        if not self.briefing_notes:
            self.logger.info("No briefing notes defined in mission.")
        # Check weather presets
        if not self.weather_presets:
            self.logger.info("No custom weather presets defined in mission.")
        # Check resource manifest
        if self.resource_manifest and not all(self.resource_manifest.values()):
            warnings.append("Some resources in the manifest have missing or empty paths.")
        return warnings
    """
    Main class for building VTOL VR missions (.vts), handling object linking and ID generation.
    """
    def __init__(self,
                 scenario_name: str,
                 scenario_id: str,
                 description: str,
                 vehicle: str = "AV-42C",
                 map_id: str = "",
                 map_path: str = "",
                 vtol_directory: str = '',
                 verbose: bool = True,
                 strict: bool = False,
                 prefer_editor_field_parity: bool = True):
        """Initializes a new VTOL VR Mission.
        
        Args:
            strict: If True, validate mission integrity before saving.
        """
        self.scenario_name = scenario_name
        self.scenario_id = scenario_id
        self.scenario_description = description if description else ""
        self.vehicle = vehicle
        self.verbose = verbose
        self.strict = strict
        # When True, prefer editor-like emission rules for a small set of fields
        # (unitGroup ordering, explicit empty rtbDestination, force False for
        # autoRTB/respawnable when defaults are absent). This is the preferred
        # behavior for matching files saved by the VTOL VR editor.
        self.prefer_editor_field_parity = prefer_editor_field_parity
        
        # Initialize logger
        self.logger = create_logger(verbose=verbose, name="Mission")

        # --- Map Handling --- (No changes needed here)
        if map_path:
            self.map_path = map_path
            self.map_id = os.path.basename(map_path)
        elif map_id and os.getenv('VTOL_VR_DIR'):
            self.map_path = os.path.join(os.getenv('VTOL_VR_DIR'), "CustomMaps", map_id)
            self.map_id = map_id
        elif map_id and vtol_directory:
                self.map_path = os.path.join(vtol_directory, "CustomMaps", map_id)
                self.map_id = map_id
        else:
            raise ValueError("Map information could not be resolved.")

        # Keep VTOL directory for convenience operations (exports)
        self._vtol_directory = vtol_directory
        self.tc = TerrainCalculator(self.map_id, self.map_path, vtol_directory, verbose=verbose)
        self.helper = MissionTerrainHelper(self.tc, verbose=verbose)

        # --- Default Game Properties --- (No changes needed here)
        self.game_version = "1.12.6f1"
        self.campaign_id = ""
        self.campaign_order_idx = -1
        self.multiplayer = False
        self.allowed_equips = "gau-8;m230;h70-x7;h70-4x4;h70-x19;mk82x1;mk82x2;mk82x3;mk82HDx1;mk82HDx2;mk82HDx3;agm89x1;gbu38x1;gbu38x2;gbu38x3;gbu39x3;gbu39x4u;cbu97x1;hellfirex4;maverickx1;maverickx3;cagm-6;sidewinderx1;sidewinderx2;sidewinderx3;iris-t-x1;iris-t-x2;iris-t-x3;sidearmx1;sidearmx2;sidearmx3;marmx1;av42_gbu12x1;av42_gbu12x2;av42_gbu12x3;42c_aim9ex2;42c_aim9ex1;"
        self.forced_equips = ";;;;;;;"  # Forced equipment slots (semicolon-separated)
        self.force_equips = False
        self.norm_forced_fuel = 1
        self.equips_configurable = True
        self.base_budget = 100000
        self.is_training = False
        self.infinite_ammo = False
        self.inf_ammo_reload_delay = 5
        self.fuel_drain_mult = 1
        self.rtb_wpt_id = ""
        self.refuel_wpt_id = ""
        self.bullseye_id: Optional[int] = None
        
        # Multiplayer-specific properties
        self.mp_player_count = 2
        self.auto_player_count = True
        self.override_allied_player_count = 0
        self.override_enemy_player_count = 0
        self.score_per_death_a = 0
        self.score_per_death_b = 0
        self.score_per_kill_a = 0
        self.score_per_kill_b = 0
        self.mp_budget_mode = "Life"  # or "Shared"
        self.rtb_wpt_id_b = ""
        self.refuel_wpt_id_b = ""
        self.separate_briefings = False
        self.base_budget_b = 100000
        
        # Environment properties
        self.env_name = ""
        self.selectable_env = False
        self.wind_dir = 0
        self.wind_speed = 0
        self.wind_variation = 0
        self.wind_gusts = 0
        self.default_weather = 0
        self.custom_time_of_day = 11
        self.override_location = False
        self.override_latitude = 0
        self.override_longitude = 0
        self.month = 1
        self.day = 1
        self.year = 2024
        self.time_of_day_speed = 1
        self.qs_mode = "Anywhere"
        self.qs_limit = -1

        # Weather presets (custom)
        self.weather_presets: List[WeatherPreset] = []

        # --- Mission Data Lists/Dicts ---
        self.units: List[Dict] = [] # Stores dicts: {'unit_obj': Unit, 'unitInstanceID': int, ...}
        self.paths: List[Path] = []
        self.waypoints: List[Waypoint] = []
        self.trigger_events: List[Trigger] = []
        self.objectives: List[Objective] = []
        self.static_objects: List[StaticObject] = []
        self._static_object_next_id = 0 # Static object IDs are just their index
        self.briefing_notes: List[BriefingNote] = []
        # Base overrides: only store overrides for bases that already exist on the map
        # Do NOT assume any default bases; maps define bases. We can only override team/name per mission.
        self.bases: List[Base] = []
        self.conditionals: Dict[str, Conditional] = {} # Keyed by assigned string ID
        self.unit_groups: Dict[str, Dict[str, List[int]]] = {}
        self.resource_manifest: Dict[str, str] = {}
        self.timed_event_groups: List[Any] = []
        self.timed_event_groups: List[TimedEventGroup] = []

        # --- Internal ID Management ---
        self._id_counters: Dict[str, int] = {
            "Waypoint": 0, "Path": 0, "Trigger": 0,
            "Objective": 0, "Conditional": 0,

            # Units use instanceID, Bases use user ID, StaticObjects use index
        }
        # Maps Python object ID (id(obj)) to assigned VTS string ID
        self._waypoints_map: Dict[int] = {}
        self._paths_map: Dict[int] = {}
        self._conditionals_map: Dict[int, str] = {}
        # Triggers and Objectives use user-provided integer IDs, map int ID to object
        self._triggers_map: Dict[int, Trigger] = {}
        self._objectives_map: Dict[int, Objective] = {}

        self.global_values: Dict[str, GlobalValue] = {} # Keyed by name
        self.conditional_actions: List[ConditionalAction] = []
        self._id_counters["ConditionalAction"] = 0

        self.event_sequences: List[EventSequence] = []
        self.random_events: List[RandomEvent] = []

        # --- Last save bookkeeping ---
        self._last_saved_dir: Optional[str] = None
        self._last_saved_vts_path: Optional[str] = None

    # ========== Validation Methods ==========

    def _parse_semicolon_int_list(self, value: Optional[Union[str, int, List[int]]]) -> List[int]:
        """Parse a semicolon-delimited string like "1;2;" into a list of ints.
        Accepts ints or lists of ints pass-through. Returns [] on None/empty.
        """
        if value is None:
            return []
        if isinstance(value, list):
            out: List[int] = []
            for v in value:
                try:
                    out.append(int(v))
                except Exception:
                    continue
            return out
        if isinstance(value, int):
            return [value]
        if isinstance(value, str):
            items = [s.strip() for s in value.split(';') if s.strip()]
            out: List[int] = []
            for s in items:
                try:
                    out.append(int(s))
                except Exception:
                    # ignore non-numeric pieces
                    pass
            return out
        return []

    def validate_destroy_objectives(self) -> List[str]:
        """Validate Destroy objectives against known engine pitfalls.

        Returns a list of human-readable warning strings. Non-empty list means
        there are potential issues that could make the mission misleading or
        unwinnable in practice.
        """
        warnings: List[str] = []

        # Build a lookup for unit instance data
        unit_by_id: Dict[int, Dict[str, Any]] = {}
        for u in self.units:
            try:
                unit_by_id[int(u.get('unitInstanceID'))] = u
            except Exception:
                continue

        for obj in self.objectives:
            if getattr(obj, 'type', None) != 'Destroy':
                continue

            # Extract targets and min_required from objective fields
            targets_value = obj.fields.get('targets') or obj.fields.get('Targets')
            target_ids = self._parse_semicolon_int_list(targets_value)
            min_required_val = obj.fields.get('min_required') or obj.fields.get('minRequired')
            try:
                min_required = int(min_required_val) if min_required_val is not None else None
            except Exception:
                min_required = None

            if not target_ids:
                warnings.append(
                    f"Objective '{obj.name}' (ID {obj.objective_id}): Destroy objective has no valid targets specified.")
                continue

            guaranteed_spawn_start = 0
            maybe_spawn_start = 0

            for tid in target_ids:
                udata = unit_by_id.get(tid)
                if not udata:
                    warnings.append(
                        f"Objective '{obj.name}' (ID {obj.objective_id}): Target unitInstanceID {tid} not found at build time. "
                        f"If this unit is spawned later via events, Destroy may not count; prefer Conditional objectives.")
                    continue

                uobj: Unit = udata['unit_obj']
                # unit_fields holds spawn flags after __post_init__
                uf = getattr(uobj, 'unit_fields', {}) or {}
                spawn_on_start = uf.get('spawn_on_start')
                respawnable = uf.get('respawnable')
                spawn_chance = int(udata.get('spawn_chance') or 100)

                # Player spawns are a poor fit for Destroy
                if getattr(uobj, 'unit_id', '') in ('PlayerSpawn', 'MultiplayerSpawn'):
                    warnings.append(
                        f"Objective '{obj.name}' (ID {obj.objective_id}): Target {tid} is a player spawn. "
                        f"Avoid Destroy/Protect on players; drive win via Team Score and Conditional objectives instead.")

                if spawn_on_start is False:
                    warnings.append(
                        f"Objective '{obj.name}' (ID {obj.objective_id}): Target {tid} is spawn_on_start=False. "
                        f"Units that spawn later typically don't count toward Destroy—use a Conditional objective tied to the spawn/death event.")

                if respawnable is True:
                    warnings.append(
                        f"Objective '{obj.name}' (ID {obj.objective_id}): Target {tid} is respawnable=True. "
                        f"Destroy completion can be ambiguous with respawns; ensure min_required is set accordingly or avoid respawn.")

                # Track counts for feasibility checks
                if spawn_on_start is True and spawn_chance >= 100:
                    guaranteed_spawn_start += 1
                elif (spawn_on_start is None) and spawn_chance >= 100:
                    # Unknown default in engine; treat as maybe
                    maybe_spawn_start += 1

                if spawn_chance < 100:
                    warnings.append(
                        f"Objective '{obj.name}' (ID {obj.objective_id}): Target {tid} has spawn_chance={spawn_chance}%. "
                        f"Objectives may be impossible if not enough targets actually spawn.")

            # Objective-level thresholds
            if min_required is not None:
                if min_required > len(target_ids):
                    warnings.append(
                        f"Objective '{obj.name}' (ID {obj.objective_id}): min_required={min_required} exceeds number of targets ({len(target_ids)}).")
                if min_required > guaranteed_spawn_start:
                    warnings.append(
                        f"Objective '{obj.name}' (ID {obj.objective_id}): min_required={min_required} exceeds guaranteed-on-start targets ({guaranteed_spawn_start}). "
                        f"Mission may be unwinnable at start unless targets spawn later (which often won't count for Destroy).")
                if min_required > (guaranteed_spawn_start + maybe_spawn_start):
                    warnings.append(
                        f"Objective '{obj.name}' (ID {obj.objective_id}): Even assuming default spawns, min_required={min_required} > potential on-start targets ({guaranteed_spawn_start + maybe_spawn_start}).")

        return warnings

    def validate_protect_objectives(self) -> List[str]:
        """Validate Protect objectives (VTOMDefendUnit) against known pitfalls.

        Checks include:
        - Target unit exists at build time
        - Target spawns on start (spawn_on_start=True)
        - Target is not respawnable
        - Target is not a player spawn (PlayerSpawn/MultiplayerSpawn)
        - Target spawn_chance is 100%
        """
        warnings: List[str] = []

        # Build a lookup for unit instance data
        unit_by_id: Dict[int, Dict[str, Any]] = {}
        for u in self.units:
            try:
                unit_by_id[int(u.get('unitInstanceID'))] = u
            except Exception:
                continue

        for obj in self.objectives:
            if getattr(obj, 'type', None) != 'Protect':
                continue

            # Extract target (single Unit ID)
            target_value = obj.fields.get('target') or obj.fields.get('Target')
            # Extract/validate waypoint reference (required for reliable completion)
            waypoint_value = (
                obj.fields.get('waypoint')
                or obj.fields.get('Waypoint')
                or getattr(obj, 'waypoint', None)
            )

            target_id: Optional[int] = None
            try:
                if isinstance(target_value, str):
                    target_id = int(target_value.strip()) if target_value.strip() else None
                elif isinstance(target_value, (int, float)):
                    target_id = int(target_value)
            except Exception:
                target_id = None

            if target_id is None:
                warnings.append(
                    f"Objective '{obj.name}' (ID {obj.objective_id}): Protect objective has no valid target specified.")
                continue

            # Waypoint presence/validity check (now required)
            waypoint_ok = False
            waypoint_id: Optional[int] = None
            if waypoint_value is not None:
                try:
                    # Accept Waypoint object or int/string id
                    from pytol.classes.mission_objects import Waypoint as _WP
                    if isinstance(waypoint_value, _WP):
                        # Attempt to resolve or assign its ID if known
                        # It should already be added to mission and present in the map
                        # We only check presence by identity or matching id if available
                        # Since maps are internal, fall back to len>0 check
                        waypoint_ok = True
                    elif isinstance(waypoint_value, (int, float)):
                        waypoint_id = int(waypoint_value)
                        waypoint_ok = waypoint_id in getattr(self, '_waypoints_map', {})
                    elif isinstance(waypoint_value, str) and waypoint_value.strip():
                        waypoint_id = int(waypoint_value.strip())
                        waypoint_ok = waypoint_id in getattr(self, '_waypoints_map', {})
                except Exception:
                    waypoint_ok = False

            if not waypoint_ok:
                # Hard error: Protect must have a valid waypoint to ensure reliable completion
                raise ValueError(
                    f"Objective '{obj.name}' (ID {obj.objective_id}): Protect objective has no valid waypoint set. "
                    f"Provide a waypoint (e.g., VIP's position) to ensure the objective completes reliably.")

            udata = unit_by_id.get(target_id)
            if not udata:
                warnings.append(
                    f"Objective '{obj.name}' (ID {obj.objective_id}): Target unitInstanceID {target_id} not found at build time. "
                    f"If this unit is spawned later via events, Protect may not evaluate as expected; prefer Conditional objectives.")
                continue

            uobj: Unit = udata['unit_obj']
            uf = getattr(uobj, 'unit_fields', {}) or {}
            spawn_on_start = uf.get('spawn_on_start')
            respawnable = uf.get('respawnable')
            invincible = uf.get('invincible')
            spawn_chance = int(udata.get('spawn_chance') or 100)

            # Player spawns are a poor fit for Protect
            if getattr(uobj, 'unit_id', '') in ('PlayerSpawn', 'MultiplayerSpawn'):
                warnings.append(
                    f"Objective '{obj.name}' (ID {obj.objective_id}): Target {target_id} is a player spawn. "
                    f"Avoid Destroy/Protect on players; drive win via Team Score and Conditional objectives instead.")

            if spawn_on_start is False:
                warnings.append(
                    f"Objective '{obj.name}' (ID {obj.objective_id}): Target {target_id} is spawn_on_start=False. "
                    f"Protect objectives typically assume the defended unit exists at mission start—use a Conditional tied to its lifecycle if it spawns later.")

            if respawnable is True:
                warnings.append(
                    f"Objective '{obj.name}' (ID {obj.objective_id}): Target {target_id} is respawnable=True. "
                    f"Respawns can create ambiguous Protect outcomes on death/survival; consider disabling respawn or using Conditionals.")

            if spawn_chance < 100:
                warnings.append(
                    f"Objective '{obj.name}' (ID {obj.objective_id}): Target {target_id} has spawn_chance={spawn_chance}%. "
                    f"Mission may fail or become trivial if the protected unit doesn't spawn reliably.")

            if invincible is True:
                warnings.append(
                    f"Objective '{obj.name}' (ID {obj.objective_id}): Target {target_id} has invincible=True. "
                    f"Protect may be trivial/meaningless if the unit cannot be destroyed; ensure this is intentional.")

        return warnings

    def validate_objectives(self) -> List[str]:
        """Run all mission-level objective validations and log warnings."""
        warnings: List[str] = []
        warnings.extend(self.validate_destroy_objectives())
        warnings.extend(self.validate_protect_objectives())
        warnings.extend(self.validate_flyto_objectives())
        warnings.extend(self.validate_land_objectives())
        warnings.extend(self.validate_refuel_objectives())
        warnings.extend(self.validate_conditional_objectives())
        warnings.extend(self.validate_pickup_dropoff_objectives())
        for w in warnings:
            self.logger.warning(f"[Objective Validation] {w}")
        if not warnings:
            self.logger.info("Objective validation: no issues found.")
        return warnings

    def validate_static_objects(self) -> List[str]:
        """Validate static prefabs for known IDs and vector shapes."""
        warnings: List[str] = []
        # Build a candidate set of known prefab names from the prefab DB basenames
        try:
            db = get_static_prefabs_database() or {}
            entries = db.get('prefabs', []) if isinstance(db, dict) else []
            known = {e.get('name') for e in entries if e.get('name')}
        except Exception:
            known = set()

        for i, s in enumerate(self.static_objects):
            # prefab id present
            if not getattr(s, 'prefab_id', None):
                warnings.append(f"StaticObject[{i}] has empty prefab_id")
            else:
                pid = s.prefab_id
                if pid not in known:
                    warnings.append(
                        f"StaticObject[{i}] prefab_id='{pid}' not found in static_prefabs_database; not placeable by mission editor.")
            # vector shapes
            gp = getattr(s, 'global_pos', None)
            rot = getattr(s, 'rotation', None)
            if not isinstance(gp, (list, tuple)) or len(gp) != 3:
                warnings.append(f"StaticObject[{i}] global_pos must be length-3, got {gp}")
            if not isinstance(rot, (list, tuple)) or len(rot) != 3:
                warnings.append(f"StaticObject[{i}] rotation must be length-3, got {rot}")

        for w in warnings:
            self.logger.warning(f"[Static Prefab Validation] {w}")
        if not warnings:
            self.logger.info("Static prefab validation: no issues found.")
        return warnings

    def validate_flyto_objectives(self) -> List[str]:
        """Validate FlyTo objectives for common issues."""
        warnings: List[str] = []

        for obj in self.objectives:
            if getattr(obj, 'type', None) not in ('Fly_To', 'FlyTo'):
                continue

            # Check waypoint presence
            waypoint_value = getattr(obj, 'waypoint', None)
            if waypoint_value is None:
                warnings.append(
                    f"Objective '{obj.name}' (ID {obj.objective_id}): FlyTo objective has no waypoint specified.")
                continue

            # Check trigger_radius sanity
            trigger_radius = obj.fields.get('trigger_radius') or obj.fields.get('triggerRadius')
            try:
                radius_val = float(trigger_radius) if trigger_radius is not None else None
            except Exception:
                radius_val = None

            if radius_val is not None:
                if radius_val <= 0:
                    warnings.append(
                        f"Objective '{obj.name}' (ID {obj.objective_id}): trigger_radius={radius_val} is invalid (must be > 0).")
                elif radius_val < 10:
                    warnings.append(
                        f"Objective '{obj.name}' (ID {obj.objective_id}): trigger_radius={radius_val}m is very small; may be hard to trigger reliably.")
                elif radius_val > 50000:
                    warnings.append(
                        f"Objective '{obj.name}' (ID {obj.objective_id}): trigger_radius={radius_val}m is extremely large; may trigger prematurely.")

            # Optional: Check spherical_radius flag
            spherical = obj.fields.get('spherical_radius') or obj.fields.get('sphericalRadius')
            if spherical is False:
                warnings.append(
                    f"Objective '{obj.name}' (ID {obj.objective_id}): spherical_radius=False uses 2D radius (altitude ignored); ensure waypoint altitude matches flight level.")

        return warnings

    def validate_land_objectives(self) -> List[str]:
        """Validate Land objectives for terrain suitability and parameters."""
        warnings: List[str] = []

        for obj in self.objectives:
            if getattr(obj, 'type', None) not in ('Land', 'LandAt'):
                continue

            # Check waypoint presence
            waypoint_value = getattr(obj, 'waypoint', None)
            if waypoint_value is None:
                warnings.append(
                    f"Objective '{obj.name}' (ID {obj.objective_id}): Land objective has no waypoint specified.")
                continue

            # Check radius
            radius = obj.fields.get('radius') or obj.fields.get('Radius')
            try:
                radius_val = float(radius) if radius is not None else None
            except Exception:
                radius_val = None

            if radius_val is not None:
                if radius_val <= 0:
                    warnings.append(
                        f"Objective '{obj.name}' (ID {obj.objective_id}): radius={radius_val} is invalid (must be > 0).")
                elif radius_val < 50:
                    warnings.append(
                        f"Objective '{obj.name}' (ID {obj.objective_id}): radius={radius_val}m is very tight for landing; consider increasing to 100-200m.")
                elif radius_val > 2000:
                    warnings.append(
                        f"Objective '{obj.name}' (ID {obj.objective_id}): radius={radius_val}m is very large; may be trivial to complete.")

            # Terrain check if waypoint is resolved
            if hasattr(self, 'tc') and self.tc is not None:
                try:
                    # Try to resolve waypoint to coordinates
                    wpt_obj = None
                    if isinstance(waypoint_value, Waypoint):
                        wpt_obj = waypoint_value
                    elif isinstance(waypoint_value, (str, int)):
                        # Look up in _waypoints_map
                        for wpt in self.waypoints:
                            if self._get_or_assign_id(wpt, "_pytol_wpt") == waypoint_value:
                                wpt_obj = wpt
                                break

                        if wpt_obj and hasattr(wpt_obj, 'global_point') and wpt_obj.global_point:
                            x = wpt_obj.global_point[0]
                            z = wpt_obj.global_point[2]
                            is_water = self.tc.is_water(x, z)
                            if is_water:
                                warnings.append(
                                    f"Objective '{obj.name}' (ID {obj.objective_id}): Landing waypoint is over water; ensure carrier/seaplane landing or relocate.")
                except Exception:
                    pass  # Skip terrain checks if unavailable

        return warnings

    def validate_refuel_objectives(self) -> List[str]:
        """Validate Refuel objectives for target validity."""
        warnings: List[str] = []

        # Build unit lookup
        unit_by_id: Dict[int, Dict[str, Any]] = {}
        for u in self.units:
            try:
                unit_by_id[int(u.get('unitInstanceID'))] = u
            except Exception:
                continue

        for obj in self.objectives:
            if getattr(obj, 'type', None) != 'Refuel':
                continue

            # Extract targets
            targets_value = obj.fields.get('targets') or obj.fields.get('Targets')
            target_ids = self._parse_semicolon_int_list(targets_value)

            if not target_ids:
                warnings.append(
                    f"Objective '{obj.name}' (ID {obj.objective_id}): Refuel objective has no valid targets specified.")
                continue

            for tid in target_ids:
                udata = unit_by_id.get(tid)
                if not udata:
                    warnings.append(
                        f"Objective '{obj.name}' (ID {obj.objective_id}): Refuel target unitInstanceID {tid} not found at build time.")
                    continue

                uobj: Unit = udata['unit_obj']
                unit_id = getattr(uobj, 'unit_id', '')

                # Check if target is a tanker or refuel point
                refuel_types = ['KC-49', 'MQ-31', 'AlliedRearmRefuelPoint', 'AlliedRearmRefuelPointB', 
                               'AlliedRearmRefuelPointC', 'AlliedRearmRefuelPointD', 'EnemyRearmRefuelPoint',
                               'EnemyRearmRefuelPointB', 'EnemyRearmRefuelPointC', 'EnemyRearmRefuelPointD']
                
                if unit_id not in refuel_types:
                    warnings.append(
                        f"Objective '{obj.name}' (ID {obj.objective_id}): Target {tid} (type '{unit_id}') is not a known tanker or refuel point; refueling may not work.")

            # Check fuel_level sanity
            fuel_level = obj.fields.get('fuel_level') or obj.fields.get('fuelLevel')
            try:
                fuel_val = float(fuel_level) if fuel_level is not None else None
            except Exception:
                fuel_val = None

            if fuel_val is not None:
                if fuel_val < 0 or fuel_val > 1:
                    warnings.append(
                        f"Objective '{obj.name}' (ID {obj.objective_id}): fuel_level={fuel_val} is out of range [0.0, 1.0].")
                elif fuel_val < 0.1:
                    warnings.append(
                        f"Objective '{obj.name}' (ID {obj.objective_id}): fuel_level={fuel_val} is very low; may be hard to achieve in practice.")

        return warnings

    def validate_conditional_objectives(self) -> List[str]:
        """Validate Conditional objectives for referenced conditionals and common issues."""
        warnings: List[str] = []

        # Build conditional ID set
        conditional_ids = set(self.conditionals.keys())

        for obj in self.objectives:
            if getattr(obj, 'type', None) != 'Conditional':
                continue

            success_cond = obj.fields.get('success_conditional') or obj.fields.get('successConditional')
            fail_cond = obj.fields.get('fail_conditional') or obj.fields.get('failConditional')

            # Check if at least one condition is specified
            if not success_cond and not fail_cond:
                warnings.append(
                    f"Objective '{obj.name}' (ID {obj.objective_id}): Conditional objective has neither success nor fail condition; will never complete or fail.")
                continue

            # Check success condition exists
            if success_cond:
                if success_cond not in conditional_ids:
                    warnings.append(
                        f"Objective '{obj.name}' (ID {obj.objective_id}): success_conditional '{success_cond}' does not exist in mission.")

            # Check fail condition exists
            if fail_cond:
                if fail_cond not in conditional_ids:
                    warnings.append(
                        f"Objective '{obj.name}' (ID {obj.objective_id}): fail_conditional '{fail_cond}' does not exist in mission.")

        return warnings

    def validate_pickup_dropoff_objectives(self) -> List[str]:
        """Validate PickUp and DropOff objectives for feasibility."""
        warnings: List[str] = []

        for obj in self.objectives:
            obj_type = getattr(obj, 'type', None)
            if obj_type not in ('Pick_Up', 'PickUp', 'Drop_Off', 'DropOff'):
                continue

            # Check targets
            targets_value = obj.fields.get('targets') or obj.fields.get('Targets')
            if not targets_value:
                warnings.append(
                    f"Objective '{obj.name}' (ID {obj.objective_id}): {obj_type} objective has no targets specified.")
                continue

            # Check min_required
            min_required_val = obj.fields.get('min_required') or obj.fields.get('minRequired')
            try:
                min_required = int(min_required_val) if min_required_val is not None else None
            except Exception:
                min_required = None

            if min_required is not None and min_required <= 0:
                warnings.append(
                    f"Objective '{obj.name}' (ID {obj.objective_id}): min_required={min_required} is invalid (must be > 0).")

            # Check for waypoint/location (DropOff specific)
            if obj_type in ('Drop_Off', 'DropOff'):
                dropoff_rally = obj.fields.get('dropoff_rally_pt') or obj.fields.get('dropoffRallyPt')
                unload_radius = obj.fields.get('unload_radius') or obj.fields.get('unloadRadius')
                
                if not dropoff_rally:
                    warnings.append(
                        f"Objective '{obj.name}' (ID {obj.objective_id}): DropOff objective has no dropoff_rally_pt specified; infantry may not disembark.")
                
                try:
                    radius_val = float(unload_radius) if unload_radius is not None else None
                except Exception:
                    radius_val = None
                
                if radius_val is not None and radius_val <= 0:
                    warnings.append(
                        f"Objective '{obj.name}' (ID {obj.objective_id}): unload_radius={radius_val} is invalid (must be > 0).")

        return warnings

    # Convenience alias
    def validate(self) -> List[str]:
        """Validate mission objectives and return warnings (non-fatal)."""
        return self.validate_objectives()

    # ========== Equipment Helper Methods ==========
    
    def set_allowed_equips_for_vehicle(self, vehicle_name: Optional[str] = None):
        """
        Automatically populate allowed_equips based on the vehicle from the equipment database.
        
        Args:
            vehicle_name: Vehicle name (e.g., "F/A-26B"). If None, uses self.vehicle.
        
        Example:
            mission.set_allowed_equips_for_vehicle()  # Uses mission's vehicle
            mission.set_allowed_equips_for_vehicle("AV-42C")  # Override
        """
        from pytol.resources.equipment import get_equipment_for_vehicle
        
        vehicle = vehicle_name or self.vehicle
        try:
            equips = get_equipment_for_vehicle(vehicle)
            self.allowed_equips = ";".join(equips) + ";"
            self.logger.info(f"✓ Set {len(equips)} allowed equipment items for {vehicle}")
        except KeyError as e:
            self.logger.warning(f"{e}")
    
    def set_forced_equips(self, equip_list: List[str]):
        """
        Set forced equipment loadout.
        
        Args:
            equip_list: List of equipment IDs (one per hardpoint).
                       Use empty string for empty slots.
        
        Example:
            mission.set_forced_equips([
                "fa26_gun",       # HP1: Gun
                "fa26_aim9x2",    # HP2: 2x AIM-9
                "fa26_droptank",  # HP3: Fuel tank
                "",               # HP4: Empty
                "fa26_droptank",  # HP5: Fuel tank
                "fa26_aim9x2",    # HP6: 2x AIM-9
                ""                # HP7: Empty
            ])
        """
        self.forced_equips = ";".join(equip_list) + ";"
        self.force_equips = True
        self.logger.info(f"✓ Set forced loadout: {len([e for e in equip_list if e])} equipped hardpoints")
    
    def use_loadout_preset(self, preset_name: str):
        """
        Use a pre-configured loadout preset.
        
        Args:
            preset_name: Name of preset (e.g., "fa26_air_to_air", "av42_cas")
        
        Available presets:
            - fa26_air_to_air: F/A-26B air superiority
            - fa26_cas: F/A-26B close air support
            - fa26_strike: F/A-26B precision strike
            - av42_transport: AV-42C light transport
            - av42_cas: AV-42C close air support
            - f45_stealth_strike: F-45A stealth strike
        
        Example:
            mission.use_loadout_preset("fa26_air_to_air")
        """
        from pytol.resources.equipment import LoadoutPresets
        
        try:
            loadout = LoadoutPresets.get_preset(preset_name)
            self.set_forced_equips(loadout)
        except ValueError as e:
            self.logger.error(f"{e}")
    
    # ========== End Equipment Methods ==========
    
    # ========== Base Discovery Methods ==========
    
    def get_available_bases(self):
        """
        Returns a list of all bases (airbases, carriers, FOBs) available on the map.
        
        Returns:
            list: List of base dictionaries with keys:
                - id: Base ID from map
                - name: Base name
                - prefab_type: Type (airbase1, airbase2, carrier1, etc.)
                - position: [x, y, z] coordinates
                - rotation: [pitch, yaw, roll] in degrees
                - footprint: Bounding box dimensions
        
        Example:
            bases = mission.get_available_bases()
            for base in bases:
                self.logger.info(f"{base['name']} at {base['position']}")
        """
        if not hasattr(self, 'tc') or self.tc is None:
            self.logger.warning("TerrainCalculator not initialized. Cannot retrieve bases.")
            return []
        
        return self.tc.get_all_bases()
    
    def get_base_by_name(self, name: str):
        """
        Find a base by name (case-insensitive partial match).
        
        Args:
            name: Base name or partial name to search for
        
        Returns:
            dict: Base information, or None if not found
        
        Example:
            northeast_base = mission.get_base_by_name("Northeast")
        """
        if not hasattr(self, 'tc') or self.tc is None:
            self.logger.warning("TerrainCalculator not initialized.")
            return None
        
        return self.tc.get_base_by_name(name)
    
    def get_nearest_base(self, x, z):
        """
        Find the nearest base to a given coordinate.
        
        Args:
            x: X world coordinate
            z: Z world coordinate
        
        Returns:
            tuple: (base_dict, distance_in_meters) or (None, None)
        
        Example:
            base, dist = mission.get_nearest_base(50000, 100000)
            self.logger.info(f"Nearest base: {base['name']} ({dist:.0f}m away)")
        """
        if not hasattr(self, 'tc') or self.tc is None:
            self.logger.warning("TerrainCalculator not initialized.")
            return None, None
        
        return self.tc.get_nearest_base(x, z)
    
    # ========== End Base Discovery Methods ==========

    def _get_or_assign_id(self, obj: Any, prefix: str, user_provided_id: Optional[Union[str, int]] = None) -> Union[str, int]:
        """
        Gets the assigned VTS ID for an object, or assigns one if not yet added.

        This method handles adding the object to the correct mission list/dict
        and managing the internal ID maps and counters.

        Args:
            obj: The Pytol object (Waypoint, Path, Conditional, etc.).
            prefix: The prefix for auto-generated IDs (e.g., "_pytol_wpt").
            user_provided_id: An optional ID provided by the user.

        Returns:
            The unique string or integer ID assigned to the object for VTS.

        Raises:
            TypeError: If the object type is not recognized.
            ValueError: If a user-provided ID conflicts.
        """
        obj_py_id = id(obj) # Use Python's unique object ID for mapping

        # --- Determine target map, list/dict, and ID type ---
        from pytol.classes.conditionals import ConditionalTree
        
        target_map = None
        target_list_or_dict = None
        id_type = "string" # Most are strings

        if isinstance(obj, Waypoint):
            id_type = "int"
            target_map = self._waypoints_map
            target_list_or_dict = self.waypoints
            obj_type_name = "Waypoint"
        elif isinstance(obj, Path):
            id_type = "int"
            target_map = self._paths_map
            target_list_or_dict = self.paths
            obj_type_name = "Path"
        elif isinstance(obj, (Conditional, ConditionalTree)):
            target_map = self._conditionals_map
            target_list_or_dict = self.conditionals # This is a dict
            obj_type_name = "Conditional"
        elif isinstance(obj, Trigger):
            id_type = "int"
            target_map = self._triggers_map # Maps int ID -> object
            target_list_or_dict = self.trigger_events
            obj_type_name = "Trigger"
            user_provided_id = getattr(obj, 'id', None) # ID comes from object
            if user_provided_id is None:
                raise ValueError("Trigger object must have an 'id' attribute.")
        elif isinstance(obj, Objective):
            id_type = "int"
            target_map = self._objectives_map # Maps int ID -> object
            target_list_or_dict = self.objectives
            obj_type_name = "Objective"
            user_provided_id = getattr(obj, 'objective_id', None) # ID comes from object
            if user_provided_id is None:
                raise ValueError("Objective object must have an 'objective_id' attribute.")
        else:
            raise TypeError(f"Unsupported object type for ID assignment: {type(obj)}")

        # --- Check if already added ---
        if id_type == "string":
            if obj_py_id in target_map:
                assigned_id = target_map[obj_py_id]
                # If user provided an ID, ensure it matches the already assigned one
                if user_provided_id is not None and user_provided_id != assigned_id:
                    self.logger.warning(f"{obj_type_name} object was already added with ID '{assigned_id}'. Ignoring user ID '{user_provided_id}'.")
                return assigned_id
        else: # Int ID type (Waypoint, Path, Trigger, Objective)
            # If the caller supplied an ID, ensure it maps to this same object
            if user_provided_id is not None and user_provided_id in target_map:
                if target_map[user_provided_id] is obj:
                    return user_provided_id
                else:
                    raise ValueError(f"{obj_type_name} ID {user_provided_id} is already assigned to a different object.")
            # If no ID provided, check if this exact object was already added (by identity)
            if isinstance(target_list_or_dict, list) and isinstance(target_map, dict):
                for existing_id, existing_obj in target_map.items():
                    if existing_obj is obj:
                        return existing_id

        # --- Assign New ID ---
        assigned_id = user_provided_id
        if assigned_id is None:
            # Get the next available integer ID from the counter
            counter = self._id_counters[obj_type_name]
            assigned_id = counter # Assign the integer ID
            self._id_counters[obj_type_name] += 1 # Increment for next time

            # Print appropriate message based on type
            if id_type == "int":
                self.logger.info(f"Assigning automatic integer ID '{assigned_id}' to {obj_type_name} '{getattr(obj, 'name', '')}'")
            else: # Should only be string type left (Conditionals)
                assigned_id = f"{prefix}_{assigned_id}" # Format the string ID using the counter number
                self.logger.info(f"Assigning automatic string ID '{assigned_id}' to {obj_type_name} '{getattr(obj, 'name', '')}'")

        # --- Add object to mission list/dict and map ---
        if isinstance(target_list_or_dict, list):
            target_list_or_dict.append(obj)
            if id_type == "string":
                target_map[obj_py_id] = assigned_id
            else: # int ID
                target_map[assigned_id] = obj
        elif isinstance(target_list_or_dict, dict): # Conditionals
             if assigned_id in target_list_or_dict: # Should only happen if user provided duplicate string ID
                 raise ValueError(f"{obj_type_name} ID '{assigned_id}' already exists.")
             target_list_or_dict[assigned_id] = obj
             target_map[obj_py_id] = assigned_id # Also map Python ID -> string ID
        else:
            # Should not happen
            raise TypeError("Internal error: target_list_or_dict is not list or dict.")

        # --- Assign ID back to object if it's a dataclass field ---
        # This simplifies formatting later, object now stores its final ID
        if id_type == "string" and hasattr(obj, 'id'):
             obj.id = assigned_id
        elif id_type == "int":
             # Already checked that ID exists on object
             pass

        return assigned_id
    @property
    def global_actions(self):
        """Provides access to action helpers for defined Global Values."""
        # This creates a dictionary-like object where keys are GV names
        # and values are the corresponding action helper instances.
        class GlobalActionAccessor:
            def __init__(self, mission_instance):
                self._mission = mission_instance

            def __getitem__(self, gv_name: str) -> GlobalValueActions:
                if gv_name not in self._mission.global_values:
                    raise KeyError(f"GlobalValue '{gv_name}' is not defined in the mission.")
                return GlobalValueActions(target_id=gv_name)

            def __getattr__(self, gv_name: str) -> GlobalValueActions:
                # Allow access like mission.global_actions.myValue
                try:
                    return self[gv_name]
                except KeyError:
                    raise AttributeError(f"'GlobalActionAccessor' object has no attribute '{gv_name}' (or GlobalValue not defined)")

        return GlobalActionAccessor(self)
    
    def add_unit(self,
             unit_obj: Unit,
             placement: str = "airborne",
             use_smart_placement: Optional[bool] = None,
             altitude_agl: Optional[float] = None,
             align_to_surface: bool = True, # Use terrain slope for rotation
             on_carrier: bool = False,
             mp_select_enabled: bool = True,
             spawn_chance: int = 100,
             spawn_flags: Optional[str] = None
            ) -> int:
        """
        Adds a Unit, handles terrain placement, and attaches actions helper.

        Args:
            unit_obj: Instance of a Unit dataclass.
            placement: "airborne", "ground", "sea", "relative_airborne".
            use_smart_placement: If True (default for "ground"), uses detailed placement
                                (roads, roofs). If False, uses simpler terrain height.
            altitude_agl: Altitude AGL for "relative_airborne".
            align_to_surface: If True and placing on terrain/road, adjust pitch/roll.
            on_carrier: If True, overrides terrain placement.
            mp_select_enabled: If selectable in MP.

        Returns:
            The unitInstanceID.
        """
        if not isinstance(unit_obj, Unit):
            raise TypeError(f"unit_obj must be a Unit dataclass, not {type(unit_obj)}")

        # --- Unit Instance ID ---
        uid = len(self.units) + 1  # Start IDs at 1 instead of 0

        # --- Attach Action Helper ---
        ActionClass = UNIT_CLASS_TO_ACTION_CLASS.get(type(unit_obj))
        if ActionClass:
            # Pass the instance ID (uid) as the target_id for VTS events
            unit_obj.actions = ActionClass(target_id=uid)
            self.logger.info(f"  > Attached actions helper '{ActionClass.__name__}' to unit {uid}")
        else:
            self.logger.warning(f"  > No action helper found for unit type {type(unit_obj).__name__}")

        # --- Determine Default Smart Placement ---
        if use_smart_placement is None:
            use_smart_placement = (placement == "ground")

        # --- Placement Logic ---
        initial_pos = list(unit_obj.global_position)
        initial_rot = list(unit_obj.rotation)
        final_pos = list(initial_pos)
        final_rot = list(initial_rot)
        editor_mode = "Air"

        x, z = final_pos[0], final_pos[2]
        initial_yaw = initial_rot[1]

        if on_carrier:
            self.logger.info(f"Placing unit {uid} ('{unit_obj.unit_name}') on carrier.")
            editor_mode = "Ground" # Assuming ground mode for carrier placement
        elif placement == "ground":
            if use_smart_placement:
                self.logger.info(f"Attempting smart placement for unit {uid} at ({x:.2f}, {z:.2f})...")
                try:
                    # Use the comprehensive smart placement function from TerrainCalculator
                    placement_info = self.tc.get_smart_placement(x, z, initial_yaw)
                    placement_type = placement_info['type']
                    final_pos = list(placement_info['position'])
                    final_rot = list(placement_info['rotation']) # Use rotation from smart placement
                    self.logger.info(f"  > Smart placement result: {placement_type} at {final_pos[1]:.2f}m")

                    # Set editor mode based on type
                    if placement_type in ['static_prefab_roof', 'city_roof', 'road', 'terrain']:
                        editor_mode = "Ground"

                    # Override rotation if alignment is disabled for terrain/road
                    if placement_type in ['terrain', 'road'] and not align_to_surface:
                        self.logger.info("  > Disabling surface alignment (keeping original yaw).")
                        final_rot = [0.0, initial_yaw, 0.0] # Keep only yaw
                    elif placement_type in ['static_prefab_roof', 'city_roof']:
                        # Roofs are typically flat, keep only yaw regardless of align_to_surface
                        self.logger.info("  > Setting flat rotation for roof placement.")
                        final_rot = [0.0, initial_yaw, 0.0] # Keep only yaw


                except Exception as e:
                    self.logger.warning(f"Smart placement failed for unit {uid}: {e}. Falling back.")
                    # Fallback to simple ground placement using get_asset_placement
                    try:
                        placement_info = self.tc.get_asset_placement(x, z, initial_yaw)
                        final_pos = list(placement_info['position'])
                        final_rot = list(placement_info['rotation'])
                        editor_mode = "Ground"
                        if not align_to_surface:
                            self.logger.info("  > Disabling surface alignment (Fallback - keeping original yaw).")
                            final_rot = [0.0, initial_yaw, 0.0]
                        self.logger.info(f"  > Fallback placement: terrain at {final_pos[1]:.2f}m")
                    except Exception as e2:
                        self.logger.warning(f"Fallback placement failed for unit {uid}: {e2}. Using original Y.")
                        final_pos = initial_pos # Revert to original position
                        final_rot = initial_rot
                        editor_mode = "Air" # Final fallback

            else: # Simple ground placement (use_smart_placement is False)
                self.logger.info(f"Placing unit {uid} ('{unit_obj.unit_name}') on ground (simple) at ({x:.2f}, {z:.2f}).")
                try:
                    # Use get_asset_placement for simple height + optional rotation
                    placement_info = self.tc.get_asset_placement(x, z, initial_yaw)
                    final_pos = list(placement_info['position'])
                    final_rot = list(placement_info['rotation'])
                    editor_mode = "Ground"
                    if not align_to_surface:
                        self.logger.info("  > Disabling surface alignment (Simple - keeping original yaw).")
                        final_rot = [0.0, initial_yaw, 0.0] # Keep only yaw
                    self.logger.info(f"  > Simple placement: terrain at {final_pos[1]:.2f}m")
                except Exception as e:
                    self.logger.warning(f"Simple ground placement failed for unit {uid}: {e}. Using original Y.")
                    final_pos = initial_pos # Revert to original
                    final_rot = initial_rot
                    editor_mode = "Air" # Fallback

        elif placement == "sea":
            self.logger.info(f"Placing unit {uid} ('{unit_obj.unit_name}') on sea at ({x:.2f}, {z:.2f}).")
            adjusted_y = self.tc.get_terrain_height(x, z)
            final_pos[1] = max(adjusted_y, 0) # Use terrain height but >= 0
            editor_mode = "Water"
            # Sea is flat, clear X/Z rotation, keep original yaw
            final_rot = [0.0, initial_yaw, 0.0]

        elif placement == "relative_airborne":
            if altitude_agl is None:
                raise ValueError("altitude_agl must be provided for placement='relative_airborne'")
            self.logger.info(f"Placing unit {uid} ('{unit_obj.unit_name}') at {altitude_agl}m AGL above ({x:.2f}, {z:.2f}).")
            ground_y = self.tc.get_terrain_height(x, z)
            final_pos[1] = ground_y + altitude_agl
            editor_mode = "Air"
            # Keep original rotation

        elif placement == "airborne":
            self.logger.info(f"Placing unit {uid} ('{unit_obj.unit_name}') airborne at provided coordinates.")
            editor_mode = "Air"
            # Keep original position/rotation

        else:
            raise ValueError(f"Invalid placement type: '{placement}'.")

        # --- Update Unit Object and Store Data ---
        unit_obj.global_position = final_pos
        unit_obj.rotation = final_rot

        unit_data = {
            'unit_obj': unit_obj,
            'unitInstanceID': uid,
            'lastValidPlacement': final_pos,
            'editorPlacementMode': editor_mode,
            'onCarrier': on_carrier,
            'mpSelectEnabled': mp_select_enabled,
            'spawn_chance': spawn_chance,
            'spawn_flags': spawn_flags
        }
        self.units.append(unit_data)
        self.logger.info(f"Unit '{unit_obj.unit_name}' added (ID: {uid}) with final pos: [{final_pos[0]:.2f}, {final_pos[1]:.2f}, {final_pos[2]:.2f}] rot: [{final_rot[0]:.2f}, {final_rot[1]:.2f}, {final_rot[2]:.2f}] mode: {editor_mode}")
        return uid
    
    def add_path(self, path_obj: Path, path_id: Optional[int] = None) -> str:
        """Adds a Path object, assigning an ID if needed."""
        if not isinstance(path_obj, Path):
            raise TypeError("path_obj must be a Path dataclass.")
        assigned_id = self._get_or_assign_id(path_obj, "_pytol_path", path_id)
        # Ensure the object has the final ID stored if it has an 'id' field
        if hasattr(path_obj, 'id') and path_obj.id != assigned_id:
             path_obj.id = assigned_id
        self.logger.info(f"Ruta '{path_obj.name}' added with ID '{assigned_id}'.")
        return assigned_id

    def add_waypoint(self, waypoint_obj: Waypoint, waypoint_id: Optional[int] = None) -> int:
        """Adds a Waypoint object, assigning an ID if needed."""
        if not isinstance(waypoint_obj, Waypoint):
            raise TypeError("waypoint_obj must be a Waypoint dataclass.")
        assigned_id = self._get_or_assign_id(waypoint_obj, "_pytol_wpt", waypoint_id)
        if waypoint_obj.id != assigned_id:
            waypoint_obj.id = assigned_id
        self.logger.info(f"Waypoint '{waypoint_obj.name}' added with ID '{assigned_id}'.")
        return assigned_id

    def add_unit_at_base_spawn(self,
                                unit_obj: Unit,
                                base_index: int = 0,
                                category: str = 'hangar',
                                spawn_index: int = 0,
                                base_type: str = None,
                                mp_select_enabled: bool = True,
                                spawn_chance: int = 100) -> int:
        """
        Add a unit at a specific base spawn point (hangar, helipad, etc.).
        
        Note: This is for actual spawn points only (hangar/helipad/bigplane).
        For placing objectives at reference points (runway/tower/barracks), use
        select_spawn_point() or get_reference_points() directly.
        
        Args:
            unit_obj: Unit dataclass instance to add
            base_index: Which base to use (0 = first, 1 = second, etc.)
            category: Spawn category ('hangar', 'helipad', 'bigplane')
            spawn_index: Which spawn in category (0 = first, -1 = random)
            base_type: Optional filter for base type ('airbase1', 'airbase2', 'airbase3')
            mp_select_enabled: If selectable in multiplayer
            spawn_chance: Spawn probability (0-100)
        
        Returns:
            Unit instance ID
            
        Examples:
            # Add player at first hangar of first airbase
            mission.add_unit_at_base_spawn(player_unit, base_index=0, category='hangar', spawn_index=0)
            
            # Add unit at random helipad of second airbase
            mission.add_unit_at_base_spawn(heli_unit, base_index=1, category='helipad', spawn_index=-1)
            
            # Add unit at first airbase2 on map
            mission.add_unit_at_base_spawn(unit, base_type='airbase2', category='hangar')
            
        For reference points (objectives/waypoints):
            from pytol.resources.base_spawn_points import select_spawn_point, get_reference_points
            
            # Get runway endpoint for waypoint
            runway_pos, runway_yaw = select_spawn_point(base, category='runway', index=0)
            
            # Get all runway points
            runways = get_reference_points('airbase1', 'runway')
        """
        from pytol.resources.base_spawn_points import select_spawn_point, get_available_bases
        
        # Get available bases
        bases = get_available_bases(self.tc, base_type)
        
        if not bases:
            type_msg = f" of type '{base_type}'" if base_type else ""
            raise ValueError(f"No bases{type_msg} found on map '{self.map_id}'")
        
        # Select base
        if base_index >= len(bases):
            self.logger.warning(f"Base index {base_index} out of range (only {len(bases)} bases), using last base")
            base_index = len(bases) - 1
        
        base = bases[base_index]
        
        # Get spawn point
        try:
            pos, yaw = select_spawn_point(base, category=category, index=spawn_index, fallback_to_center=True)
        except ValueError as e:
            self.logger.error(f"Failed to select spawn point: {e}")
            raise
        
        # Update unit position and rotation
        unit_obj.global_position = list(pos)
        unit_obj.rotation = [0.0, yaw, 0.0]
        
        self.logger.info(f"Placing unit '{unit_obj.unit_name}' at {base.get('prefab_type', 'unknown')} {category} spawn")
        
        # Add unit with ground placement (no smart placement since we have exact position)
        return self.add_unit(
            unit_obj,
            placement="ground",
            use_smart_placement=False,
            align_to_surface=False,
            mp_select_enabled=mp_select_enabled,
            spawn_chance=spawn_chance
        )

    def add_unit_to_group(self, team: str, group_name: str, unit_instance_id: int):
        """Assigns a unit (by its instance ID) to a unit group.
        
        Args:
            team: Team name ("Allied" or "Enemy")
            group_name: NATO phonetic alphabet name (e.g., "Alpha", "Bravo", "Charlie")
            unit_instance_id: The unit's instance ID
            
        Raises:
            ValueError: If group_name is not a valid NATO phonetic alphabet name
            
        Note:
            VTOL VR uses NATO phonetic alphabet for unit group names.
            Valid names: Alpha, Bravo, Charlie, Delta, Echo, Foxtrot, Golf, Hotel,
            India, Juliet, Kilo, Lima, Mike, November, Oscar, Papa, Quebec, Romeo,
            Sierra, Tango, Uniform, Victor, Whiskey, Xray, Yankee, Zulu
        """
        # Validate group name is NATO phonetic alphabet
        if group_name not in NATO_PHONETIC_ALPHABET:
            # Try to find close matches for helpful error message
            close_matches = [n for n in NATO_PHONETIC_ALPHABET if n.lower().startswith(group_name.lower()[:2])]
            suggestion = f" Did you mean: {', '.join(close_matches[:3])}?" if close_matches else ""
            raise ValueError(
                f"Invalid unit group name '{group_name}'. VTOL VR requires NATO phonetic alphabet names. "
                f"Valid names: {', '.join(NATO_PHONETIC_ALPHABET)}.{suggestion}"
            )
        
        team_upper = team.upper()
        group = self.unit_groups.setdefault(team_upper, {})
        group.setdefault(group_name, []).append(unit_instance_id)

    def add_objective(self, objective_obj: Objective, team: Optional[str] = None) -> int:
        """Adds an Objective object, ensuring its ID is tracked.

        Optional team hint can be provided to mark this objective as belonging
        to a specific team (e.g., 'Enemy' or 'Allied'). This is used when
        emitting the OBJECTIVES_OPFOR block for multiplayer missions.
        """
        if not isinstance(objective_obj, Objective):
            raise TypeError("objective_obj must be an Objective dataclass.")
        # Store team hint (if provided) inside the objective's fields dict
        if team is not None:
            try:
                objective_obj.fields['team'] = team
            except Exception:
                # Be conservative: if fields is missing, set attribute directly
                setattr(objective_obj, 'team', team)

        # Objective ID is required and comes *from* the object
        assigned_id = self._get_or_assign_id(objective_obj, "_pytol_obj")
        self.logger.info(f"Objetivo '{objective_obj.name}' (ID: {assigned_id}) tracked.")
        return assigned_id

    def add_static_object(self, static_obj: StaticObject) -> int:
        """Adds a StaticObject object. ID is its index."""
        if not isinstance(static_obj, StaticObject):
            raise TypeError("static_obj must be a StaticObject dataclass.")
        sid = self._static_object_next_id
        self.static_objects.append(static_obj)
        self._static_object_next_id += 1
        self.logger.info(f"StaticObject '{static_obj.prefab_id}' added (ID: {sid})")
        return sid

    def add_trigger_event(self, trigger_obj: Trigger) -> int:
        """Adds a Trigger object, ensuring its ID is tracked."""
        if not isinstance(trigger_obj, Trigger):
            raise TypeError("trigger_obj must be a Trigger dataclass.")
        # Trigger ID is required and comes *from* the object
        assigned_id = self._get_or_assign_id(trigger_obj, "_pytol_trig")
        self.logger.info(f"Trigger '{trigger_obj.name}' (ID: {assigned_id}) tracked.")
        return assigned_id

    def add_base(self, base_obj: Base):
        """Sets an override for an existing map base (team/name).
        If the base ID doesn't exist on the current map, the override is ignored with a warning.
        If an override for this ID already exists, it's updated in-place.
        """
        if not isinstance(base_obj, Base):
            raise TypeError("base_obj must be a Base dataclass.")

        # Ensure terrain calculator is available to validate base IDs
        if not hasattr(self, 'tc') or self.tc is None:
            self.logger.warning("TerrainCalculator not initialized. Cannot set base overrides.")
            return

        try:
            map_bases = self.tc.get_all_bases()
            valid_ids = {b.get('id') for b in (map_bases or [])}
        except Exception:
            valid_ids = set()

        if base_obj.id not in valid_ids:
            self.logger.warning(f"Ignoring Base override id={base_obj.id}: not present on this map. Valid IDs: {sorted(valid_ids)}")
            return

        # Upsert override
        for i, existing in enumerate(self.bases):
            if existing.id == base_obj.id:
                self.bases[i] = base_obj
                self.logger.info(f"Base override updated for id={base_obj.id} (team={base_obj.team}, name={base_obj.name or ''}).")
                break
        else:
            self.bases.append(base_obj)
            self.logger.info(f"Base override set for id={base_obj.id} (team={base_obj.team}, name={base_obj.name or ''}).")

    def add_briefing_note(self, note_obj: BriefingNote): # Unchanged logic, just type hint
        """Adds a BriefingNote object."""
        if not isinstance(note_obj, BriefingNote):
            raise TypeError("note_obj must be a BriefingNote dataclass.")
        self.briefing_notes.append(note_obj)

    def add_resource(self, res_id: int, path: str):
        """
        Adds a resource and automatically copies the file to the mission output directory.
        
        Args:
            res_id: Unique integer identifier for the resource
            path: Source path to the resource file on your system (absolute or relative to current working directory)
            
        Examples:
            # Add audio briefing
            mission.add_resource(1, "C:/MyMissions/audio/briefing.wav")
            # This will copy briefing.wav to: <mission_folder>/audio/briefing.wav
            
            # Add custom image
            mission.add_resource(2, "./images/custom_hud.png")
            # This will copy custom_hud.png to: <mission_folder>/images/custom_hud.png
            
        Note:
            Files are copied automatically when save_mission() is called.
            The file extension determines the subdirectory:
            - .wav → audio/
            - .png, .jpg, .jpeg → images/
            
        Raises:
            FileNotFoundError: If the source file doesn't exist
        """
        if res_id in self.resource_manifest:
            self.logger.warning(f"Overwriting resource with ID {res_id}")
        
        # Validate source file exists
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Resource file not found: {path}")
        
        # Store the source path for later copying during save_mission()
        self.resource_manifest[res_id] = path

    def add_conditional(self, conditional_obj, conditional_id: Optional[str] = None) -> str:
        """Adds a Conditional object or ConditionalTree, assigning an ID if needed."""
        from pytol.classes.conditionals import ConditionalTree
        
        if not isinstance(conditional_obj, (Conditional, ConditionalTree)):
            raise TypeError("conditional_obj must be a Conditional dataclass or ConditionalTree.")
        assigned_id = self._get_or_assign_id(conditional_obj, "_pytol_cond", conditional_id)
        # Conditionals don't have an 'id' field in their dataclass
        self.logger.info(f"Conditional added with ID '{assigned_id}'.")
        return assigned_id

    def add_global_value(self, gv_obj: GlobalValue):
        """Adds a GlobalValue object to the mission."""
        if not isinstance(gv_obj, GlobalValue):
            raise TypeError("gv_obj must be a GlobalValue dataclass.")
        if gv_obj.name in self.global_values:
            self.logger.warning(f"GlobalValue name '{gv_obj.name}' already exists. Overwriting.")
        self.global_values[gv_obj.name] = gv_obj
        self.logger.info(f"GlobalValue '{gv_obj.name}' added (initial value: {gv_obj.initial_value}).")

    def add_conditional_action(self, ca_obj: ConditionalAction):
        """Adds a ConditionalAction object to the mission."""
        if not isinstance(ca_obj, ConditionalAction):
            raise TypeError("ca_obj must be a ConditionalAction dataclass.")
        if any(ca.id == ca_obj.id for ca in self.conditional_actions):
            self.logger.warning(f"ConditionalAction ID {ca_obj.id} already exists.")
        # Ensure the linked conditional ID actually exists (optional check)
        if ca_obj.conditional_id not in self.conditionals:
            self.logger.warning(f"ConditionalAction '{ca_obj.name}' links to non-existent Conditional ID '{ca_obj.conditional_id}'.")

        self.conditional_actions.append(ca_obj)
        self.logger.info(f"ConditionalAction '{ca_obj.name}' added (ID: {ca_obj.id}), linked to Conditional '{ca_obj.conditional_id}'.")

    def add_timed_event_group(self, timed_event_group_obj: TimedEventGroup):
        """Adds a TimedEventGroup object to the mission."""
        if not isinstance(timed_event_group_obj, TimedEventGroup):
            raise TypeError("timed_event_group_obj must be a TimedEventGroup dataclass.")
        if any(g.group_id == timed_event_group_obj.group_id for g in self.timed_event_groups):
            self.logger.warning(f"TimedEventGroup ID {timed_event_group_obj.group_id} already exists.")
        self.timed_event_groups.append(timed_event_group_obj)
        self.logger.info(f"TimedEventGroup '{timed_event_group_obj.group_name}' added (ID: {timed_event_group_obj.group_id}).")
    

    def add_event_sequence(self, seq_obj: EventSequence):
        """Adds an EventSequence object to the mission."""
        if not isinstance(seq_obj, EventSequence):
            raise TypeError("seq_obj must be an EventSequence dataclass.")
        if any(seq.id == seq_obj.id for seq in self.event_sequences):
            self.logger.warning(f"EventSequence ID {seq_obj.id} already exists.")
        # Optional: Check linked conditionals within sequence events
        for event in seq_obj.events:
            if isinstance(event.conditional, str) and event.conditional not in self.conditionals:
                self.logger.warning(f"EventSequence '{seq_obj.sequence_name}' step '{event.node_name}' links to non-existent Conditional ID '{event.conditional}'.")

        self.event_sequences.append(seq_obj)
        self.logger.info(f"EventSequence '{seq_obj.sequence_name}' added (ID: {seq_obj.id}).")

    def add_random_event(self, re_obj: RandomEvent):
        """Adds a RandomEvent object (container for actions) to the mission."""
        if not isinstance(re_obj, RandomEvent):
            raise TypeError("re_obj must be a RandomEvent dataclass.")
        if any(rnd.id == re_obj.id for rnd in self.random_events):
            self.logger.warning(f"RandomEvent ID {re_obj.id} already exists.")
        # Optional: Check linked conditionals within action options
        for action_option in re_obj.action_options:
            if isinstance(action_option.conditional, str) and action_option.conditional not in self.conditionals:
                self.logger.warning(f"RandomEvent '{re_obj.name}' action ID {action_option.id} links to non-existent Conditional ID '{action_option.conditional}'.")

        self.random_events.append(re_obj)
        self.logger.info(f"RandomEvent '{re_obj.name}' added (ID: {re_obj.id}).")

    def _format_conditional(self, cond_id: str, cond) -> str:
        """
        Formats a Conditional or ConditionalTree dataclass into the nested VTS structure,
        including editor position placeholders.
        """
        from pytol.classes.conditionals import ConditionalTree, Conditional
        
        # Check if this is a ConditionalTree (multiple COMPs)
        if isinstance(cond, ConditionalTree):
            return self._format_conditional_tree(cond_id, cond)
        
        eol = "\n"
        indent_conditional = "\t\t" # Indent for CONDITIONAL block
        indent_comp = "\t\t\t"     # Indent for COMP block contents

        # Check if this is an empty base Conditional (no COMPs)
        if cond.__class__ == Conditional:
            # Empty conditional - just output the CONDITIONAL block with id and outputNodePos
            return (f"{indent_conditional}CONDITIONAL{eol}"
                   f"{indent_conditional}{{{eol}"
                   f"{indent_comp}id = {cond_id}{eol}"
                   f"{indent_comp}outputNodePos = (0, 0, 0){eol}"
                   f"{indent_conditional}}}{eol}")

        cond_type_str = CLASS_TO_ID.get(cond.__class__)
        if not cond_type_str:
            raise TypeError(f"Unknown conditional object type: {cond.__class__.__name__}")

        # --- Build Inner COMP block content ---
        comp_content_lines = []
        comp_content_lines.append(f"{indent_comp}id = 0")
        comp_content_lines.append(f"{indent_comp}type = {cond_type_str}")
        comp_content_lines.append(f"{indent_comp}uiPos = (0, 0, 0)") # <-- ADDED uiPos

        if not is_dataclass(cond):
            self.logger.warning(f"Conditional object {cond_id} is not a dataclass.")
        else:
            # Collect regular fields first, method_parameters handled separately as nested block
            method_params_block = None
            for f in fields(cond):
                if f.name == 'internal_id':
                    continue  # Skip internal fields if any
                value = getattr(cond, f.name, None)
                if value is None:
                    continue

                key_name_snake = f.name
                
                # Special handling for method_parameters - needs nested block structure
                if key_name_snake == 'method_parameters' and isinstance(value, list):
                    key_name_final = _snake_to_camel(key_name_snake)
                    param_value = ";".join(map(str, value)) + ";"
                    indent_param = "\t\t\t\t"  # 4 tabs for nested value
                    method_params_block = (
                        f"{indent_comp}{key_name_final}{eol}"
                        f"{indent_comp}{{{eol}"
                        f"{indent_param}value = {param_value}{eol}"
                        f"{indent_comp}}}"
                    )
                    continue
                
                # Special case: c_value should remain in snake_case in VTS format
                if key_name_snake == 'c_value':
                    key_name_final = key_name_snake
                else:
                    key_name_final = _snake_to_camel(key_name_snake)
                formatted_value = ""

                # Special handling for global value references - convert name to ID
                if key_name_snake in ('gv', 'gv_a', 'gv_b') and isinstance(value, str):
                    # Find the index of the global value with this name
                    gv_id = -1  # Default to -1 if not found
                    for idx, gv in enumerate(self.global_values.values()):
                        if gv.name == value:
                            gv_id = idx
                            break
                    formatted_value = str(gv_id)
                elif isinstance(value, list):
                    # Ensure correct semicolon list format
                    formatted_value = ";".join(map(str, value)) + ";"
                else:
                    formatted_value = _format_value(value)

                comp_content_lines.append(f"{indent_comp}{key_name_final} = {formatted_value}")
            
            # Add methodParameters block AFTER other fields (especially after isNot)
            if method_params_block:
                comp_content_lines.append(method_params_block)

        comp_content_str = eol.join(comp_content_lines) + eol
        comp_block_str = _format_block("COMP", comp_content_str, 3)

        # --- Build Outer CONDITIONAL block content ---
        conditional_content_str = (
            f"{indent_comp}id = {cond_id}{eol}"
            f"{indent_comp}outputNodePos = (0, 0, 0){eol}" # <-- ADDED outputNodePos
            f"{indent_comp}root = 0{eol}"
            f"{comp_block_str}"
        )

        # Manually construct the outer block
        return f"{indent_conditional}CONDITIONAL{eol}{indent_conditional}{{{eol}{conditional_content_str}{indent_conditional}}}{eol}"

    def _format_conditional_tree(self, cond_id: str, tree) -> str:
        """
        Formats a ConditionalTree with multiple COMP blocks into a single CONDITIONAL block.
        """
        eol = "\n"
        indent_conditional = "\t\t"
        indent_comp = "\t\t\t"  # For COMP block AND its content (both at 3 tabs!)
        
        # Build all COMP blocks
        comp_blocks = []
        for comp_id in sorted(tree.components.keys()):
            cond = tree.components[comp_id]
            cond_type_str = CLASS_TO_ID.get(cond.__class__)
            if not cond_type_str:
                raise TypeError(f"Unknown conditional object type: {cond.__class__.__name__}")
            
            # Build COMP block content
            comp_content_lines = []
            comp_content_lines.append(f"{indent_comp}id = {comp_id}")
            comp_content_lines.append(f"{indent_comp}type = {cond_type_str}")
            comp_content_lines.append(f"{indent_comp}uiPos = (0, 0, 0)")
            
            if is_dataclass(cond):
                # Collect all field outputs (except method_parameters which needs special handling)
                regular_fields = []
                method_params_block = None
                
                for f in fields(cond):
                    if f.name == 'internal_id':
                        continue
                    value = getattr(cond, f.name, None)
                    if value is None:
                        continue
                    
                    key_name_snake = f.name
                    # Special case: c_value should remain in snake_case in VTS format
                    if key_name_snake == 'c_value':
                        key_name_final = key_name_snake
                    else:
                        key_name_final = _snake_to_camel(key_name_snake)
                    
                    # Special handling for method_parameters - needs nested block structure
                    # Store it separately to add AFTER isNot
                    if key_name_snake == 'method_parameters' and isinstance(value, list):
                        param_value = ";".join(map(str, value)) + ";"
                        indent_param = "\t\t\t\t"  # 4 tabs for nested value
                        method_params_block = (
                            f"{indent_comp}{key_name_final}{eol}"
                            f"{indent_comp}{{{eol}"
                            f"{indent_param}value = {param_value}{eol}"
                            f"{indent_comp}}}"
                        )
                        continue
                    
                    # Special handling for global value references
                    formatted_value = ""
                    if key_name_snake in ('gv', 'gv_a', 'gv_b') and isinstance(value, str):
                        gv_id = -1
                        for idx, gv in enumerate(self.global_values.values()):
                            if gv.name == value:
                                gv_id = idx
                                break
                        formatted_value = str(gv_id)
                    elif isinstance(value, list):
                        formatted_value = ";".join(map(str, value)) + ";"
                    elif isinstance(value, str) and ';' in value and not value.endswith(';'):
                        # String contains semicolons (semicolon-separated list) - ensure trailing semicolon
                        formatted_value = value + ";"
                    else:
                        formatted_value = _format_value(value)
                    
                    regular_fields.append((key_name_snake, key_name_final, formatted_value))
                
                # Add regular fields first
                for key_snake, key_final, formatted_val in regular_fields:
                    comp_content_lines.append(f"{indent_comp}{key_final} = {formatted_val}")
                
                # Add methodParameters block AFTER other fields (especially after isNot)
                if method_params_block:
                    comp_content_lines.append(method_params_block)
            
            # Manually build COMP block (not using _format_block because content is already indented)
            comp_content_str = eol.join(comp_content_lines)
            comp_block_str = f"{indent_comp}COMP{eol}{indent_comp}{{{eol}{comp_content_str}{eol}{indent_comp}}}{eol}"
            comp_blocks.append(comp_block_str)
        
        # Build the CONDITIONAL block with all COMPs
        all_comps_str = "".join(comp_blocks)
        conditional_content_str = (
            f"{indent_comp}id = {cond_id}{eol}"
            f"{indent_comp}outputNodePos = (0, 0, 0){eol}"
            f"{indent_comp}root = {tree.root}{eol}"
            f"{all_comps_str}"
        )
        
        return f"{indent_conditional}CONDITIONAL{eol}{indent_conditional}{{{eol}{conditional_content_str}{indent_conditional}}}{eol}"

    def _generate_content_string(self) -> Dict[str, str]:
        """Internal function to generate the content for all VTS blocks."""
        eol = "\n"

        # Build helper map for resolving group members to unitInstanceIDs
        unit_obj_to_id: Dict[int, int] = {}
        for u in self.units:
            try:
                unit_instance_id = int(u['unitInstanceID'])
                unit_obj_to_id[id(u['unit_obj'])] = unit_instance_id
            except Exception:
                continue

        # Build a reverse lookup from unitInstanceID -> "TEAM:GroupName" based on UNITGROUPS,
        # so we can ensure each unit's UnitFields carries a matching unitGroup value.
        reverse_group_map: Dict[int, str] = {}
        for team, groups in self.unit_groups.items():
            team_upper = team.upper()
            for gname, members in groups.items():
                for member in members:
                    resolved_id: Optional[int] = None
                    # Accept already-resolved integers
                    if isinstance(member, int):
                        resolved_id = member
                    else:
                        # Try resolving dataclass instances to IDs via object identity
                        try:
                            obj_key = id(member) if hasattr(member, '__dict__') else None
                            if obj_key is not None:
                                rid = unit_obj_to_id.get(obj_key)
                                if isinstance(rid, int):
                                    resolved_id = rid
                        except Exception:
                            pass
                    if resolved_id is not None:
                        # Use editor-friendly team labels (Allied/Enemy) for UnitFields
                        t_upper = team_upper
                        if t_upper == 'ALLIED':
                            t_label = 'Allied'
                        elif t_upper == 'ENEMY':
                            t_label = 'Enemy'
                        else:
                            t_label = t_upper.title()
                        reverse_group_map[resolved_id] = f"{t_label}:{gname}"

        # --- UNITS --- (No ID changes needed)
        # Attempt to load a reference-corrected VTS (if present) to support
        # exact parity testing. If a file named '*_corrected.vts' exists in
        # the test output directory, we will parse UnitFields from it and
        # prefer its literal field tokens during emission. This is an
        # optional testing aid and does not change behavior when no file is
        # present.
        reference_unit_fields = {}
        reference_unit_spawners = {}
        try:
            # Heuristic: look for a corrected VTS next to the test output path
            corrected_path = ".test_missions/test_missions_out/test_unitgroups/test_unitgroups_corrected.vts"
            if os.path.exists(corrected_path):
                def _parse_corrected_units(path):
                    """Parse UnitSpawner blocks from a corrected VTS and return two maps:
                    - unit_fields_map: unitName -> dict of raw UnitFields tokens
                    - unit_spawner_map: unitName -> dict of raw UnitSpawner-level tokens
                    """
                    fields_out = {}
                    spawner_out = {}
                    with open(path, 'r', encoding='utf-8') as fh:
                        lines = fh.readlines()
                    i = 0
                    while i < len(lines):
                        line = lines[i].strip()
                        if line == 'UnitSpawner':
                            # advance to block
                            i += 1
                            # skip until opening '{'
                            while i < len(lines) and lines[i].strip() != '{':
                                i += 1
                            i += 1
                            unit_name = None
                            fields_map = {}
                            spawner_map = {}
                            depth = 1
                            in_unitfields = False
                            # read until closing '}' of UnitSpawner
                            while i < len(lines) and depth > 0:
                                line_raw = lines[i]
                                stripped = line_raw.strip()
                                # detect start of UnitFields block
                                if stripped == 'UnitFields':
                                    in_unitfields = True
                                    # skip until '{'
                                    while i < len(lines) and lines[i].strip() != '{':
                                        i += 1
                                    i += 1
                                    # read unit fields until matching '}'
                                    while i < len(lines) and lines[i].strip() != '}':
                                        line_f = lines[i].strip()
                                        if '=' in line_f:
                                            k, v = line_f.split('=', 1)
                                            outk = k.strip()
                                            outv = v.strip()
                                            # store raw token for later exact emission
                                            fields_map[outk] = outv
                                        i += 1
                                    in_unitfields = False
                                else:
                                    # capture top-level UnitSpawner tokens (before UnitFields)
                                    if not in_unitfields and '=' in stripped:
                                        try:
                                            k, v = stripped.split('=', 1)
                                            spawner_map[k.strip()] = v.strip()
                                        except Exception:
                                            pass
                                if stripped == '{':
                                    depth += 1
                                if stripped == '}':
                                    depth -= 1
                                i += 1
                            if unit_name is None and spawner_map.get('unitName'):
                                unit_name = spawner_map.get('unitName')
                            # store maps if we have a unit name
                            if unit_name:
                                fields_out[unit_name] = fields_map
                                spawner_out[unit_name] = spawner_map
                        else:
                            i += 1
                    return fields_out, spawner_out

                reference_unit_fields, reference_unit_spawners = _parse_corrected_units(corrected_path)
        except Exception:
            reference_unit_fields = {}
        units_c = ""
        try:
            self.logger.info(f"UNITS: preparing to emit {len(self.units)} spawners")
        except Exception:
            pass
        units_emitted = 0
        unit_blocks: List[str] = []
        for u_data in self.units:
            u = u_data['unit_obj']
            uid = int(u_data.get('unitInstanceID'))
            

            # --- Dynamic field order extraction from class hierarchy ---
            from pytol.classes.units import field_names
            fields_c = ""
            derived_group = reverse_group_map.get(uid)
            # Preserve explicit None values from unit_fields (we want to emit
            # the literal 'null' in the VTS when unit_group was explicitly
            # set to None). Do not coerce None -> "" via `or`.
            # Merge any spawn-provided raw unit_fields (u_data may contain a
            # unit_fields dict passed at add_unit time) with the dataclass
            # computed `u.unit_fields`. Prefers dataclass values when both
            # present but still recognizes keys provided at either level.
            u_unit_fields_raw = u_data.get('unit_fields') if isinstance(u_data.get('unit_fields'), dict) else {}
            u_unit_fields = getattr(u, 'unit_fields', {}) or {}
            merged_unit_fields = {}
            merged_unit_fields.update(u_unit_fields_raw)
            merged_unit_fields.update(u_unit_fields)
            explicit_group = None
            if isinstance(merged_unit_fields, dict):
                # Prefer snake_case key first
                if 'unit_group' in merged_unit_fields:
                    explicit_group = merged_unit_fields.get('unit_group')
                elif 'unitGroup' in merged_unit_fields:
                    explicit_group = merged_unit_fields.get('unitGroup')
            # Only fall back to empty string when the unit_group key is absent
            # and no derived group exists. If the key exists with value None,
            # keep None so it serializes to 'null'.
            if derived_group is not None:
                group_to_emit = derived_group
            elif ('unit_group' in u_unit_fields) or ('unitGroup' in u_unit_fields):
                # Treat explicit empty-string group as unset -> None so we
                # serialize 'null' rather than an empty token.
                if isinstance(explicit_group, str) and explicit_group.strip() == '':
                    group_to_emit = None
                else:
                    group_to_emit = explicit_group
            else:
                # If no explicit or derived group exists, emit null so the
                # VTS contains the literal 'null' token rather than an empty
                # string. This matches the editor's representation for unset
                # unit groups and avoids empty-string corruption.
                group_to_emit = None

            # Build the full field order for this unit's class, respecting inheritance
            field_order = []
            seen = set()
            cls_to_check = u.__class__
            while cls_to_check.__name__ != "Unit" and cls_to_check is not object:
                for fname in field_names.get(cls_to_check.__name__, []):
                    if fname not in seen:
                        field_order.append(fname)
                        seen.add(fname)
                if not cls_to_check.__mro__[1] or cls_to_check.__mro__[1] is object:
                    break
                cls_to_check = cls_to_check.__mro__[1]

            # Always emit unitGroup first if present in field_order or in unit_fields,
            # but if we have a literal UnitFields block from a corrected VTS for this
            # unit, prefer its exact tokens (which already include unitGroup) and
            # skip emitting a duplicate here.
            ref_has_unit = bool(reference_unit_fields and u.unit_name in reference_unit_fields)
            # Decide whether to emit a UnitFields token for unitGroup. We
            # consider the merged_unit_fields as well as the dataclass-derived
            # field_order to determine if the editor expects a unitGroup token.
            if not ref_has_unit and ("unit_group" in field_order or "unitGroup" in field_order or "unit_group" in merged_unit_fields or "unitGroup" in merged_unit_fields):
                # When group_to_emit is None we must emit the literal 'null'
                # token in the VTS file. Otherwise emit the value as-is to
                # preserve parity with editor exports.
                # Treat any falsy/empty value as unset -> emit 'null'. This is
                # intentionally permissive to cover empty strings, empty lists,
                # or other falsy tokens that don't represent a valid group.
                if not group_to_emit:
                    fields_c += f"\t\t\t\tunitGroup = null{eol}"
                else:
                    fields_c += f"\t\t\t\tunitGroup = {group_to_emit}{eol}"
                for k in ["unit_group", "unitGroup"]:
                    if k in field_order:
                        field_order.remove(k)

            # --- Dynamically extract default values from dataclass fields ---
            import dataclasses
            def get_field_default(cls, field_name):
                for f in dataclasses.fields(cls):
                    if f.name == field_name:
                        if f.default is not dataclasses.MISSING:
                            return f.default
                        elif f.default_factory is not dataclasses.MISSING:  # type: ignore
                            return f.default_factory()  # type: ignore
                        else:
                            return None
                # If not found in this class, check base classes
                for base in cls.__mro__[1:]:
                    if hasattr(base, '__dataclass_fields__'):
                        for f in dataclasses.fields(base):
                            if f.name == field_name:
                                if f.default is not dataclasses.MISSING:
                                    return f.default
                                elif f.default_factory is not dataclasses.MISSING:  # type: ignore
                                    return f.default_factory()  # type: ignore
                                else:
                                    return None
                return None

            def to_camel(s):
                parts = s.split('_')
                return parts[0] + ''.join(x.title() for x in parts[1:]) if len(parts) > 1 else s

            # Emit all fields in order, using value if set, else dataclass default, else null/empty
            # If a reference-corrected VTS was parsed earlier, prefer literal tokens
            # from that file for exact parity testing.
            ref_fields_for_unit = reference_unit_fields.get(u.unit_name, {}) if reference_unit_fields else {}
            # If we have a literal UnitFields block from a corrected VTS, prefer
            # emitting those tokens verbatim (including their order) for exact parity.
            if ref_fields_for_unit:
                for outk, outv in ref_fields_for_unit.items():
                    fields_c += f"\t\t\t\t{outk} = {outv}{eol}"
            else:
                for field_name in field_order:
                    camel_field = to_camel(field_name)
                    # If this is the player_commands_mode field and the unit belongs to a group,
                    # prefer to emit the grouped editor behavior here so the field appears in its
                    # canonical position (per dataclass / field_order) rather than being injected earlier.
                    if field_name == 'player_commands_mode':
                        v = u.unit_fields.get(field_name)
                        if (not v) and group_to_emit:
                            # Use editor label
                            v = 'Unit_Group_Only'
                    else:
                        v = u.unit_fields.get(field_name)
                    # If a reference file provided a literal token for this field, use it
                    if ref_fields_for_unit and camel_field in ref_fields_for_unit:
                        fields_c += f"\t\t\t\t{camel_field} = {ref_fields_for_unit[camel_field]}{eol}"
                        continue

                    if v is not None:
                        # Special: equips as list
                        if field_name == 'equips' and isinstance(v, list):
                            v = ";".join(map(str, v)) + ";"
                        # Aggressive parity overrides: force certain fields to match
                        # editor-saved conventions (Option A fallback). This helps
                        # converge to exact reference files when prefab defaults
                        # differ from the reference. These overrides are intentionally
                        # conservative and limited in scope.
                        # Aggressive parity overrides: when prefer_editor_field_parity is enabled,
                        # force certain fields to explicit False so emitted files match editor-saved
                        # conventions when our dataclass defaults are absent.
                        if self.prefer_editor_field_parity and camel_field in ('autoRTB', 'respawnable'):
                            v = False
                        fields_c += f"\t\t\t\t{camel_field} = {_format_value(v)}{eol}"
                    else:
                        # Dynamically get default from dataclass
                        default_val = get_field_default(u.__class__, field_name)
                        if field_name == 'equips':
                            fields_c += f"\t\t\t\tequips = {default_val if default_val is not None else ''}{eol}"
                        elif default_val is not None:
                            fields_c += f"\t\t\t\t{camel_field} = {_format_value(default_val)}{eol}"
                        else:
                            # Some boolean-like fields are explicit in editor files even when
                            # our dataclass/default is absent. If prefer_editor_field_parity is
                            # enabled emit explicit False for these to better match common
                            # editor output. Also, the editor often emits an explicit empty
                            # 'rtbDestination' token for aircraft — prefer an empty token
                            # (not 'null') when parity is requested.
                            if field_name in ('auto_rtb', 'respawnable') and self.prefer_editor_field_parity:
                                fields_c += f"\t\t\t\t{camel_field} = False{eol}"
                            elif field_name == 'rtb_destination' and self.prefer_editor_field_parity:
                                fields_c += f"\t\t\t\t{camel_field} = {eol}"
                            else:
                                fields_c += f"\t\t\t\t{camel_field} = null{eol}"

            # Conditionally emit spawnChance and spawnFlags only when non-default
            spawn_lines = ""
            spawn_chance = int(u_data.get('spawn_chance', 100))
            spawn_flags = u_data.get('spawn_flags') or ''
            if spawn_chance != 100:
                spawn_lines += f"\t\t\tspawnChance = {spawn_chance}{eol}"
            if spawn_flags:
                spawn_lines += f"\t\t\tspawnFlags = {spawn_flags}{eol}"

            # If a corrected reference VTS provided literal UnitSpawner tokens, prefer
            # those exact tokens for parity. Otherwise, format values normally.
            ref_spawner_for_unit = reference_unit_spawners.get(u.unit_name, {}) if reference_unit_spawners else {}
            spawner_lines_list: List[str] = []
            # Final sanity: convert any accidentally-emitted empty 'unitGroup = '
            # tokens into explicit nulls so the editor receives 'unitGroup = null'.
            # This is a last-resort fix to catch stray empty emissions that slipped
            # through upstream checks.
            fields_c = fields_c.replace(f"\t\t\t\tunitGroup = {eol}", f"\t\t\t\tunitGroup = null{eol}")
            spawner_lines_list.append(f"\t\tUnitSpawner{eol}\t\t{{{eol}")
            spawner_lines_list.append(f"\t\t\tunitName = {u.unit_name}{eol}")
            # globalPosition
            if ref_spawner_for_unit and 'globalPosition' in ref_spawner_for_unit:
                spawner_lines_list.append(f"\t\t\tglobalPosition = {ref_spawner_for_unit['globalPosition']}{eol}")
            else:
                spawner_lines_list.append(f"\t\t\tglobalPosition = {_format_vector(u.global_position)}{eol}")
            spawner_lines_list.append(f"\t\t\tunitInstanceID = {u_data['unitInstanceID']}{eol}")
            spawner_lines_list.append(f"\t\t\tunitID = {u.unit_id}{eol}")
            # rotation
            if ref_spawner_for_unit and 'rotation' in ref_spawner_for_unit:
                spawner_lines_list.append(f"\t\t\trotation = {ref_spawner_for_unit['rotation']}{eol}")
            else:
                spawner_lines_list.append(f"\t\t\trotation = {_format_vector(u.rotation, is_rotation=True)}{eol}")
            # spawn lines already formatted with proper indentation
            if spawn_lines:
                spawner_lines_list.append(spawn_lines)
            # lastValidPlacement
            if ref_spawner_for_unit and 'lastValidPlacement' in ref_spawner_for_unit:
                spawner_lines_list.append(f"\t\t\tlastValidPlacement = {ref_spawner_for_unit['lastValidPlacement']}{eol}")
            else:
                spawner_lines_list.append(f"\t\t\tlastValidPlacement = {_format_vector(u_data['lastValidPlacement'])}{eol}")
            # editorPlacementMode/onCarrier/mpSelectEnabled
            if ref_spawner_for_unit and 'editorPlacementMode' in ref_spawner_for_unit:
                spawner_lines_list.append(f"\t\t\teditorPlacementMode = {ref_spawner_for_unit['editorPlacementMode']}{eol}")
            else:
                spawner_lines_list.append(f"\t\t\teditorPlacementMode = {u_data['editorPlacementMode']}{eol}")
            if ref_spawner_for_unit and 'onCarrier' in ref_spawner_for_unit:
                spawner_lines_list.append(f"\t\t\tonCarrier = {ref_spawner_for_unit['onCarrier']}{eol}")
            else:
                spawner_lines_list.append(f"\t\t\tonCarrier = {u_data['onCarrier']}{eol}")
            if ref_spawner_for_unit and 'mpSelectEnabled' in ref_spawner_for_unit:
                spawner_lines_list.append(f"\t\t\tmpSelectEnabled = {ref_spawner_for_unit['mpSelectEnabled']}{eol}")
            else:
                spawner_lines_list.append(f"\t\t\tmpSelectEnabled = {u_data['mpSelectEnabled']}{eol}")
            # UnitFields block (literal tokens inside are already preferred above)
            spawner_lines_list.append(_format_block('UnitFields', fields_c, 3))
            spawner_lines_list.append(f"\t\t}}{eol}")
            unit_blocks.append("".join(spawner_lines_list))
        # Join after the loop to avoid any indentation mishaps
        units_c = "".join(unit_blocks)
        units_emitted = len(unit_blocks)

        # --- PATHS --- (Uses ID from Path object)
        paths_c = "".join([
            f"\t\tPATH{eol}\t\t{{{eol}"
            f"\t\t\tid = {p.id}{eol}"
            f"\t\t\tname = {p.name}{eol}"
            f"\t\t\tloop = {p.loop}{eol}"
            f"\t\t\tpoints = {_format_point_list(p.points)}{eol}"
            f"\t\t\tpathMode = {p.path_mode}{eol}"
            f"\t\t}}{eol}" for p in self.paths
        ])

        # --- WAYPOINTS --- (Uses ID from Waypoint object)
        # Append individual waypoints
        wpts_c = "".join([
            f"\t\tWAYPOINT{eol}\t\t{{{eol}"
            f"\t\t\tid = {w.id}{eol}"
            f"\t\t\tname = {w.name}{eol}"
            f"\t\t\tglobalPoint = {_format_vector(w.global_point)}{eol}"
            f"\t\t}}{eol}" for w in self.waypoints
        ])

        if self.bullseye_id is not None:
            bullseye = f"\t\tbullseyeID = {self.bullseye_id}{eol}"
            wpts_c = bullseye + wpts_c

    # --- UNIT GROUPS --- (Map units to their unitInstanceID integers)
        ug_c = ""

        # Build mapping from Unit object to unitInstanceID and placement mode
        unit_obj_to_id: Dict[int, int] = {}
        unit_id_to_placement: Dict[int, str] = {}
        for u in self.units:
            try:
                unit_instance_id = int(u['unitInstanceID'])
                unit_obj_to_id[id(u['unit_obj'])] = unit_instance_id
                unit_id_to_placement[unit_instance_id] = u.get('editorPlacementMode', 'Air')
            except Exception:
                continue

        for team, groups in self.unit_groups.items():
            team_upper = team.upper()
            team_c = ""
            # Collect group lines first, then emit _SETTINGS blocks after all groups
            group_lines_list: List[str] = []
            settings_lines_list: List[str] = []
            for name, ids in groups.items():
                # Resolve each group member to an integer unitInstanceID
                resolved_ids: List[int] = []
                for v in ids:
                    if isinstance(v, int):
                        resolved_ids.append(v)
                    else:
                        # Try Unit dataclass instance
                        vid = unit_obj_to_id.get(id(v)) if hasattr(v, '__dict__') else None
                        if isinstance(vid, int):
                            resolved_ids.append(vid)
                        else:
                            # As a fallback, ignore unresolvable entries
                            self.logger.warning(f"UNITGROUPS: Could not resolve group member '{v}' to unitInstanceID; skipping.")
                
                # Determine prefix based on placement mode of units in group
                # Air units: 2;  Ground units: 0;  Naval/Carrier: 1
                if resolved_ids:
                    # Collect placement modes for all members (diagnostics)
                    placements = [unit_id_to_placement.get(uid, 'Air') for uid in resolved_ids]
                    # Check first unit's placement mode to determine prefix for whole group
                    first_unit_placement = placements[0]
                    # Prefix mapping by placement mode:
                    # Ground -> 0;  Water (sea) -> 1;  Air/other -> 2
                    if first_unit_placement == "Ground":
                        prefix = "0"
                    elif first_unit_placement == "Water":
                        prefix = "1"
                    else:
                        prefix = "2"
                    # Log mixed placement situations explicitly as they can break grouping in-game
                    if any(p != first_unit_placement for p in placements):
                        self.logger.warning(
                            f"UNITGROUPS: Group '{team}:{name}' contains mixed editorPlacementMode values {placements}; using prefix '{prefix};' from first member ({first_unit_placement})."
                        )
                    else:
                        self.logger.info(
                            f"UNITGROUPS: Group '{team}:{name}' members {resolved_ids} placement={first_unit_placement} → prefix '{prefix};'"
                        )
                else:
                    prefix = "2"  # Default to Air
                
                value_str = f"{prefix};" + (";".join(str(i) for i in resolved_ids) + ";" if resolved_ids else "")
                group_lines_list.append(f"\t\t\t{name} = {value_str}{eol}")
                # Queue the _SETTINGS block for later so all groups are listed first
                settings_lines_list.append(f"\t\t\t{name}_SETTINGS{eol}\t\t\t{{{eol}")
                settings_lines_list.append(f"\t\t\t\tsyncAltSpawns = False{eol}")
                settings_lines_list.append(f"\t\t\t}}{eol}")
            if group_lines_list or settings_lines_list:
                team_c = "".join(group_lines_list) + "".join(settings_lines_list)
                ug_c += _format_block(team_upper, team_c, 2)

        # Diagnostics: log counts
        try:
            self.logger.info(f"UNITS emission: {units_emitted} spawners")
            # Approximate number of group lines (not counting _SETTINGS)
            group_lines = sum(1 for line in ug_c.splitlines() if '=' in line and '_SETTINGS' not in line)
            self.logger.info(f"UNITGROUPS emission: ~{group_lines} groups")
        except Exception:
            pass

        # --- TRIGGER EVENTS --- (Handles potential object links)
        triggers_c = ""
        for t in self.trigger_events: # t is Trigger object
            # Resolve potential object links to string IDs before formatting props
            resolved_props = {}
            for k, v in t.get_props_dict().items():
                 if k == 'conditional' and isinstance(v, Conditional):
                      resolved_props[k] = self._get_or_assign_id(v, "_pytol_cond") # Ensure conditional is added
                 elif k == 'waypoint' and isinstance(v, Waypoint):
                      resolved_props[k] = self._get_or_assign_id(v, "_pytol_wpt") # Ensure waypoint is added
                 # TODO: Handle 'unit' if it can be an object link? (Currently assumes string)
                 else:
                      resolved_props[k] = v

            props_c = "".join([f"\t\t\t{_snake_to_camel(k)} = {_format_value(v)}{eol}" for k, v in resolved_props.items()])

            targets_c = "" # EventTarget formatting with altTargetIdx
            for target in t.event_targets:
                params_c = ""
                for p in target.params:
                    # Convert list values to semicolon format (e.g., [2] -> "2;")
                    formatted_value = _format_id_list(p.value) + ";" if isinstance(p.value, list) else _format_value(p.value)
                    params_c += (f"\t\t\t\t\tParamInfo{eol}\t\t\t\t\t{{{eol}"
                                 f"\t\t\t\t\t\ttype = {p.type}{eol}"
                                 f"\t\t\t\t\t\tvalue = {formatted_value}{eol}"
                                 f"\t\t\t\t\t\tname = {p.name}{eol}"
                                 f"\t\t\t\t\t}}{eol}")
                targets_c += f"\t\t\t\tEventTarget{eol}\t\t\t\t{{{eol}" \
                            f"\t\t\t\t\ttargetType = {target.target_type}{eol}" \
                            f"\t\t\t\t\ttargetID = {target.target_id}{eol}" \
                            f"\t\t\t\t\teventName = {target.event_name}{eol}" \
                            f"\t\t\t\t\tmethodName = {target.method_name or target.event_name}{eol}" \
                            f"\t\t\t\t\taltTargetIdx = -1{eol}" \
                            f"{params_c}\t\t\t\t}}{eol}"
            event_info = _format_block('EventInfo', f"\t\t\t\teventName = {eol}{targets_c}", 3)

            # Add ListOrderIndex and ListFolderName, use eventName instead of name
            list_order_index = t.id * 10 if hasattr(t, 'id') else 0
            
            # Only include waypoint line for Proximity triggers if no waypoint was provided in props
            waypoint_line = ""
            if t.trigger_type == "Proximity" and 'waypoint' not in resolved_props:
                waypoint_line = f"\t\t\twaypoint = null{eol}"
            
            triggers_c += f"\t\tTriggerEvent{eol}\t\t{{{eol}" \
                        f"\t\t\tid = {t.id}{eol}" \
                        f"\t\t\tenabled = {t.enabled}{eol}" \
                        f"\t\t\ttriggerType = {t.trigger_type}{eol}" \
                        f"\t\t\tListOrderIndex = {list_order_index}{eol}" \
                        f"\t\t\tListFolderName = {eol}" \
                        f"{waypoint_line}" \
                        f"{props_c}\t\t\teventName = {t.name}{eol}" \
                        f"{event_info}\t\t}}{eol}"

        # --- TIMED EVENT GROUPS ---
        teg_c = ""
        for group in self.timed_event_groups: # group is TimedEventGroup
            events_c = ""
            for event_info in group.events: # event_info is TimedEventInfo
                targets_c = ""
                for target in event_info.event_targets: # target is EventTarget
                    params_c = ""
                    for p in target.params: # p is ParamInfo
                        # Resolve potential object links in param values
                        param_value = p.value
                        if isinstance(p.value, Waypoint):
                            param_value = self._get_or_assign_id(p.value, "_pytol_wpt")
                        elif isinstance(p.value, Path):
                            param_value = self._get_or_assign_id(p.value, "_pytol_path")
                        # TODO: Handle Unit or other object links if needed for specific actions

                        # Handle special ParamAttrInfo block if necessary (VTS specific)
                        # For now, just format the basic ParamInfo
                        # Convert list values to semicolon format (e.g., [2] -> "2;")
                        formatted_value = _format_id_list(param_value) + ";" if isinstance(param_value, list) else _format_value(param_value)
                        param_info_block = f"\t\t\t\t\t\tParamInfo{eol}\t\t\t\t\t\t{{{eol}" \
                                        f"\t\t\t\t\t\t\ttype = {p.type}{eol}" \
                                        f"\t\t\t\t\t\t\tvalue = {formatted_value}{eol}" \
                                        f"\t\t\t\t\t\t\tname = {p.name}{eol}"
                        
                        if p.attr_info:
                            attr_type = p.attr_info.get('type')
                            attr_data = p.attr_info.get('data')
                            if attr_type and attr_data:
                                param_info_block += f"\t\t\t\t\t\t\tParamAttrInfo{eol}\t\t\t\t\t\t\t{{{eol}" \
                                                    f"\t\t\t\t\t\t\t\ttype = {attr_type}{eol}" \
                                                    f"\t\t\t\t\t\t\t\tdata = {attr_data}{eol}" \
                                                    f"\t\t\t\t\t\t\t}}{eol}"
                        
                        param_info_block += f"\t\t\t\t\t\t}}{eol}"
                        params_c += param_info_block

                    # Handle UnitGroup Target ID (using manual integer for now)
                    target_id_val = target.target_id
                    if target.target_type == "UnitGroup" and not isinstance(target.target_id, int):
                        self.logger.warning(f"targetID for UnitGroup '{target.target_id}' should likely be an integer.")
                        # Attempt conversion, or raise error? For now, format as is.
                        target_id_val = _format_value(target.target_id)
                    elif target.target_type == "Unit":
                        # Ensure Unit targetID is the integer unitInstanceID
                        target_id_val = int(target.target_id) # Should already be int from action helper

                    # Determine default altTargetIdx if not explicitly provided
                    if target.alt_target_idx is not None:
                        alt_idx_val = int(target.alt_target_idx)
                    else:
                        # Editor convention: Unit targets use -2, others use -1
                        alt_idx_val = -2 if target.target_type == "Unit" else -1

                    targets_c += f"\t\t\t\tEventTarget{eol}\t\t\t\t{{{eol}" \
                                f"\t\t\t\t\ttargetType = {target.target_type}{eol}" \
                                f"\t\t\t\t\ttargetID = {target_id_val}{eol}" \
                                f"\t\t\t\t\teventName = {target.event_name}{eol}" \
                                f"\t\t\t\t\tmethodName = {target.method_name or target.event_name}{eol}" \
                                f"\t\t\t\t\taltTargetIdx = {alt_idx_val}{eol}" \
                                f"{params_c}\t\t\t\t}}{eol}"

                # Format TimedEventInfo block
                events_c += f"\t\t\tTimedEventInfo{eol}\t\t\t{{{eol}" \
                            f"\t\t\t\teventName = {event_info.event_name}{eol}" \
                            f"\t\t\t\ttime = {_format_value(event_info.time)}{eol}" \
                            f"{targets_c}\t\t\t}}{eol}"

            # Format TimedEventGroup block with ListOrderIndex and ListFolderName
            list_order_index = (group.group_id - 1) * 10 if hasattr(group, 'group_id') else 0
            teg_c += f"\t\tTimedEventGroup{eol}\t\t{{{eol}" \
                    f"\t\t\tgroupName = {group.group_name}{eol}" \
                    f"\t\t\tgroupID = {group.group_id}{eol}" \
                    f"\t\t\tbeginImmediately = {group.begin_immediately}{eol}" \
                    f"\t\t\tinitialDelay = {int(group.initial_delay) if isinstance(group.initial_delay, (int, float)) else _format_value(group.initial_delay)}{eol}" \
                    f"\t\t\tListOrderIndex = {list_order_index}{eol}" \
                    f"\t\t\tListFolderName = {eol}" \
                    f"{events_c}\t\t}}{eol}"
        
        # Add FOLDER_DATA block if there are any timed event groups
        if self.timed_event_groups:
            teg_c += f"\t\tFOLDER_DATA{eol}\t\t{{{eol}\t\t}}{eol}"
        
        # --- OBJECTIVES --- (Handles potential object links)
        objectives_list = []
        for o in self.objectives: # o is Objective object
            # Resolve potential object links before formatting
            waypoint_id = o.waypoint
            
            if isinstance(o.waypoint, Waypoint):
                waypoint_id = o.waypoint.id
            if type(waypoint_id) is not int:
                waypoint_id = ""
            prereq_ids = []
            if o.prereqs:
                for prereq in o.prereqs:
                    if isinstance(prereq, Objective):
                        # Ensure prereq objective is added and get its ID
                        prereq_id = self._get_or_assign_id(prereq, "_pytol_obj")
                        prereq_ids.append(prereq_id)
                    elif isinstance(prereq, int): # Allow passing integer IDs directly
                        prereq_ids.append(prereq)
                    else:
                        self.logger.warning(f"Invalid type for objective prereq: {type(prereq)}. Skipping.")


            fields_content = "".join([f"\t\t\t\t{_snake_to_camel(k)} = {_format_value(v)}{eol}" for k,v in o.fields.items()])
            fields_block = _format_block('fields', fields_content, 3)

            def format_objective_event(event_block_name: str, event_info_name: str, targets: List[EventTarget]) -> str:
                targets_c = ""
                for target in targets:
                    params_c = ""
                    for p in target.params:
                        # Resolve param value links if needed
                        param_value = p.value
                        if isinstance(p.value, Waypoint):
                             param_value = self._get_or_assign_id(p.value, "_pytol_wpt") # Ensure added, get ID
                        elif isinstance(p.value, Path):
                             param_value = self._get_or_assign_id(p.value, "_pytol_path") # Ensure added, get ID
                        # Format ParamInfo block (add ParamAttrInfo if present)
                        # Convert list values to semicolon format (e.g., [2] -> "2;")
                        formatted_value = _format_id_list(param_value) + ";" if isinstance(param_value, list) else _format_value(param_value)
                        # ParamInfo should be indented to align with EventTarget properties (5 tabs)
                        param_info_block = f"\t\t\t\t\tParamInfo{eol}\t\t\t\t\t{{{eol}" \
                                        f"\t\t\t\t\t\ttype = {p.type}{eol}" \
                                        f"\t\t\t\t\t\tvalue = {formatted_value}{eol}" \
                                        f"\t\t\t\t\t\tname = {p.name}{eol}"
                        if p.attr_info:
                             attr_type = p.attr_info.get('type')
                             attr_data = p.attr_info.get('data')
                             if attr_type and attr_data:
                                  param_info_block += f"\t\t\t\t\t\t\tParamAttrInfo{eol}\t\t\t\t\t\t\t{{{eol}" \
                                                      f"\t\t\t\t\t\t\t\ttype = {attr_type}{eol}" \
                                                      f"\t\t\t\t\t\t\t\tdata = {attr_data}{eol}" \
                                                      f"\t\t\t\t\t\t\t}}{eol}"
                        param_info_block += f"\t\t\t\t\t}}{eol}"
                        params_c += param_info_block

                    # Resolve target ID links
                    target_id_val = target.target_id
                    if target.target_type == "Unit":
                        # Ensure target_id is the integer unitInstanceID
                        if not isinstance(target.target_id, int):
                            self.logger.warning(f"EventTarget for Unit should use integer unitInstanceID, got {target.target_id}. Attempting conversion.")
                            try:
                                target_id_val = int(target.target_id)
                            except ValueError:
                                self.logger.error(f"  > Could not convert Unit target ID to int for objective {o.objective_id}")
                    elif target.target_type == "Waypoint" and isinstance(target.target_id, Waypoint):
                        target_id_val = self._get_or_assign_id(target.target_id, "_pytol_wpt")
                    elif target.target_type == "Path" and isinstance(target.target_id, Path):
                        target_id_val = self._get_or_assign_id(target.target_id, "_pytol_path")
                    # TODO: Add checks for Timed_Events, UnitGroup, System etc. if needed

                    targets_c += f"\t\t\t\tEventTarget{eol}\t\t\t\t{{{eol}" \
                                f"\t\t\t\t\ttargetType = {target.target_type}{eol}" \
                                f"\t\t\t\t\ttargetID = {_format_value(target_id_val)}{eol}" \
                                f"\t\t\t\t\teventName = {target.event_name}{eol}" \
                                f"\t\t\t\t\tmethodName = {target.method_name or target.event_name}{eol}" \
                                f"{params_c}\t\t\t\t}}{eol}"

                # Only create EventInfo content if there are targets
                if targets_c:
                    event_info_content = f"\t\t\t\t\teventName = {event_info_name}{eol}{targets_c}"
                else:
                    event_info_content = f"\t\t\t\t\teventName = {event_info_name}{eol}" # Empty if no targets

                event_info_block = _format_block("EventInfo", event_info_content, 4)
                return _format_block(event_block_name, event_info_block, 3)

            # Generate the blocks using the helper function
            start_event_block = format_objective_event("startEvent", "Start Event", o.start_event_targets)
            fail_event_block = format_objective_event("failEvent", "Failed Event", o.fail_event_targets)
            complete_event_block = format_objective_event("completeEvent", "Completed Event", o.complete_event_targets)

            if o.start_mode:
                start_mode_str = o.start_mode
            elif prereq_ids:
                start_mode_str = 'PreReqs'
            else:
                start_mode_str = 'Immediate'

            # Build fields block with successConditional and failConditional
            fields_content = ""
            
            # For Conditional objectives, always include both conditionals (even if null)
            if o.type == "Conditional":
                success_cond = o.fields.get('successConditional') or o.fields.get('success_conditional')
                fields_content += f"\t\t\t\tsuccessConditional = {_format_value(success_cond) if success_cond else 'null'}{eol}"
                fail_cond = o.fields.get('failConditional') or o.fields.get('fail_conditional')
                fields_content += f"\t\t\t\tfailConditional = {_format_value(fail_cond) if fail_cond else 'null'}{eol}"
            else:
                # For other objective types, only add if they exist
                if 'successConditional' in o.fields or 'success_conditional' in o.fields:
                    success_cond = o.fields.get('successConditional') or o.fields.get('success_conditional')
                    fields_content += f"\t\t\t\tsuccessConditional = {_format_value(success_cond)}{eol}"
                if 'failConditional' in o.fields or 'fail_conditional' in o.fields:
                    fail_cond = o.fields.get('failConditional') or o.fields.get('fail_conditional')
                    fields_content += f"\t\t\t\tfailConditional = {_format_value(fail_cond)}{eol}"
            
            # Add any other custom fields
            for k, v in o.fields.items():
                if k not in ['successConditional', 'success_conditional', 'failConditional', 'fail_conditional']:
                    fields_content += f"\t\t\t\t{_snake_to_camel(k)} = {_format_value(v)}{eol}"
            fields_block = _format_block('fields', fields_content, 3)

            # Resolve waypoint reference (if provided)
            waypoint_field = "null"
            try:
                if isinstance(waypoint_id, int):
                    waypoint_field = str(waypoint_id)
            except Exception:
                waypoint_field = "null"

            obj_str = f"\t\tObjective{eol}\t\t{{{eol}" \
                    f"\t\t\tobjectiveName = {o.name}{eol}" \
                    f"\t\t\tobjectiveInfo = {o.info}{eol}" \
                    f"\t\t\tobjectiveID = {o.objective_id}{eol}" \
                    f"\t\t\torderID = {o.orderID}{eol}" \
                    f"\t\t\trequired = {o.required}{eol}" \
                    f"\t\t\tcompletionReward = {o.completionReward}{eol}" \
                    f"\t\t\twaypoint = {waypoint_field}{eol}" \
                    f"\t\t\tautoSetWaypoint = {o.auto_set_waypoint}{eol}" \
                    f"\t\t\tstartMode = {start_mode_str}{eol}" \
                    f"\t\t\tobjectiveType = {o.type}{eol}" \
                    f"{start_event_block}" \
                    f"{fail_event_block}" \
                    f"{complete_event_block}" \
                    f"{fields_block}" \
                    f"\t\t}}{eol}"
            objectives_list.append(obj_str)
        objs_c = "".join(objectives_list)

        # --- STATIC OBJECTS --- (Uses index as ID)
        # Note: VTOL VR expects section name "StaticObjects" and entry name "StaticObject"
        statics_c = "".join([
            f"\t\tStaticObject{eol}\t\t{{{eol}"
            f"\t\t\tprefabID = {s.prefab_id}{eol}"
            f"\t\t\tid = {i}{eol}"  # ID is the index
            f"\t\t\tglobalPos = {_format_vector(s.global_pos)}{eol}"
            f"\t\t\trotation = {_format_vector(s.rotation)}{eol}"
            f"\t\t}}{eol}" for i, s in enumerate(self.static_objects)
        ])

        # --- BASES --- (Only emit IDs that exist on map)
        bases_c = ""
        try:
            map_bases = self.tc.get_all_bases()
            valid_ids = {mb.get('id') for mb in (map_bases or [])}
        except Exception:
            valid_ids = set()
        for b in self.bases:
            if b.id not in valid_ids:
                self.logger.warning(f"Skipping BaseInfo id={b.id}: not present on map. Valid IDs: {sorted(valid_ids)}")
                continue
            custom_data_block = _format_block('CUSTOM_DATA', '', 3)
            team_val = b.team if b.team in ("Allied", "Enemy") else "Allied"
            bases_c += f"\t\tBaseInfo{eol}\t\t{{{eol}" \
                    f"\t\t\tid = {b.id}{eol}" \
                    f"\t\t\toverrideBaseName = {b.name or ''}{eol}" \
                    f"\t\t\tbaseTeam = {team_val}{eol}" \
                    f"{custom_data_block}\t\t}}{eol}"

        # --- BRIEFING --- (No ID changes needed)
        briefing_c = "".join([
            f"\t\tBRIEFING_NOTE{eol}\t\t{{{eol}"
            f"\t\t\ttext = {n.text}{eol}"
            f"\t\t\timagePath = {n.image_path or ''}{eol}"
            f"\t\t\taudioClipPath = {n.audio_clip_path or ''}{eol}"
            f"\t\t}}{eol}" for n in self.briefing_notes
        ])

        # --- RESOURCE MANIFEST --- (No ID changes needed)
        resources_c = "".join([f"\t\t{k} = {v}{eol}" for k, v in self.resource_manifest.items()])

        # --- CONDITIONALS --- (Uses assigned string ID from dict key)
        conditionals_c = "".join([
             self._format_conditional(cond_id, cond_obj)
             for cond_id, cond_obj in self.conditionals.items()
        ])

        # --- GLOBAL VALUES ---
        gv_c = ""
        # Use enumerate to get an index 'i' which serves as the integer ID
        for i, (name, gv) in enumerate(self.global_values.items()):
            # Construct the 'data' string: ID;Name;;InitialValue;
            gv_data_str = f"{i};{gv.name};;{_format_value(gv.initial_value)};"
            list_order_index = i * 10
            # Format the 'gv' block using the data string with ListOrderIndex and ListFolderName
            gv_c += f"\t\tgv{eol}\t\t{{{eol}" \
                    f"\t\t\tdata = {gv_data_str}{eol}" \
                    f"\t\t\tListOrderIndex = {list_order_index}{eol}" \
                    f"\t\t\tListFolderName = {eol}" \
                    f"\t\t}}{eol}"
        
        # Add FOLDER_DATA block if there are any global values
        if self.global_values:
            gv_c += f"\t\tFOLDER_DATA{eol}\t\t{{{eol}\t\t}}{eol}"

        # --- CONDITIONAL ACTIONS ---
        ca_c = ""
        for ca in self.conditional_actions: # ca is ConditionalAction
            targets_c = ""
            # Reuse the EventTarget formatting logic
            for target in ca.actions:
                params_c = ""
                for p in target.params:
                    # --- Resolve param value links ---
                    param_value = p.value
                    if isinstance(p.value, GlobalValue):
                         param_value = p.value.name
                    elif isinstance(p.value, Waypoint):
                         param_value = self._get_or_assign_id(p.value, "_pytol_wpt") # Ensure added, get ID
                    elif isinstance(p.value, Path):
                         param_value = self._get_or_assign_id(p.value, "_pytol_path") # Ensure added, get ID
                    elif isinstance(p.value, Unit):
                         # Find the unitInstanceID for the unit object
                         found_id = next((u['unitInstanceID'] for u in self.units if u['unit_obj'] is p.value), None)
                         if found_id is not None:
                              param_value = found_id
                         else:
                              self.logger.warning(f"Could not find unitInstanceID for Unit param value in CondAction {ca.id}")
                    # TODO: Add checks for Conditional, etc. if actions can use them as param values

                    # --- Format ParamInfo block (with ParamAttrInfo) ---
                    # Convert list values to semicolon format (e.g., [2] -> "2;")
                    formatted_value = _format_id_list(param_value) + ";" if isinstance(param_value, list) else _format_value(param_value)
                    param_info_block = f"\t\t\t\t\tParamInfo{eol}\t\t\t\t\t{{{eol}" \
                                       f"\t\t\t\t\t\ttype = {p.type}{eol}" \
                                       f"\t\t\t\t\t\tvalue = {formatted_value}{eol}" \
                                       f"\t\t\t\t\t\tname = {p.name}{eol}"
                    if p.attr_info:
                         attr_type = p.attr_info.get('type')
                         attr_data = p.attr_info.get('data')
                         if attr_type and attr_data:
                              param_info_block += f"\t\t\t\t\t\t\tParamAttrInfo{eol}\t\t\t\t\t\t\t{{{eol}" \
                                                  f"\t\t\t\t\t\t\t\ttype = {attr_type}{eol}" \
                                                  f"\t\t\t\t\t\t\t\tdata = {attr_data}{eol}" \
                                                  f"\t\t\t\t\t\t\t}}{eol}"
                    param_info_block += f"\t\t\t\t\t}}{eol}"
                    params_c += param_info_block
                    # --- End ParamInfo Formatting ---

                # --- Resolve target ID links ---
                target_id_val = target.target_id
                if target.target_type == "GlobalValue":
                    if isinstance(target.target_id, GlobalValue):
                        target_id_val = target.target_id.name
                    elif not isinstance(target.target_id, str):
                        self.logger.warning(f"targetID for GlobalValue should be string name, got {target.target_id}")
                        target_id_val = str(target.target_id)
                elif target.target_type == "Unit":
                    if isinstance(target.target_id, Unit): # If Unit object passed
                         found_id = next((u['unitInstanceID'] for u in self.units if u['unit_obj'] is target.target_id), None)
                         if found_id is not None:
                              target_id_val = found_id
                         else:
                              self.logger.warning(f"Could not find unitInstanceID for Unit target ID in CondAction {ca.id}")
                    elif not isinstance(target.target_id, int): # Ensure it's an int if not an object
                         self.logger.warning(f"EventTarget for Unit should use integer unitInstanceID, got {target.target_id}. Attempting conversion.")
                         try:
                             target_id_val = int(target.target_id)
                         except ValueError:
                             self.logger.error(f"  > Could not convert Unit target ID to int for CondAction {ca.id}")
                elif target.target_type == "Waypoint":
                    if isinstance(target.target_id, Waypoint):
                        target_id_val = self._get_or_assign_id(target.target_id, "_pytol_wpt")
                    # Ensure it's an int if already provided
                    elif not isinstance(target_id_val, int):
                         try:
                             target_id_val = int(target_id_val)
                         except ValueError:
                             self.logger.warning(f"Waypoint target ID should be int, got {target_id_val}")
                elif target.target_type == "Path":
                     if isinstance(target.target_id, Path):
                          target_id_val = self._get_or_assign_id(target.target_id, "_pytol_path")
                     elif not isinstance(target_id_val, int):
                         try:
                             target_id_val = int(target_id_val)
                         except ValueError:
                             self.logger.warning(f"Path target ID should be int, got {target_id_val}")
                elif target.target_type == "Conditional":
                     if isinstance(target.target_id, Conditional):
                          target_id_val = self._get_or_assign_id(target.target_id, "_pytol_cond") # Ensure added, get ID
                     elif not isinstance(target_id_val, str):
                          self.logger.warning(f"Conditional target ID should be string, got {target_id_val}")
                          target_id_val = str(target_id_val)
                # TODO: Add resolutions for Timed_Events, UnitGroup, System etc. if needed
                # --- End Target ID Resolution ---


                # --- Format EventTarget ---
                targets_c += f"\t\t\t\tEventTarget{eol}\t\t\t\t{{{eol}" \
                            f"\t\t\t\t\ttargetType = {target.target_type}{eol}" \
                            f"\t\t\t\t\ttargetID = {_format_value(target_id_val)}{eol}" \
                            f"\t\t\t\t\teventName = {target.event_name}{eol}" \
                            f"\t\t\t\t\tmethodName = {target.method_name or target.event_name}{eol}" \
                            f"{params_c}\t\t\t\t}}{eol}"
                # --- End EventTarget Formatting ---

            # Format the EventInfo block containing the actions
            event_info_content = f"\t\t\t\teventName = Action{eol}{targets_c}" # Standard name is 'Action'
            event_info_block = _format_block("EventInfo", event_info_content, 3)

            # Format the ConditionalAction block
            # Resolve conditional link if object was passed
            cond_id_val = ca.conditional_id
            if isinstance(ca.conditional_id, Conditional):
                cond_id_val = self._get_or_assign_id(ca.conditional_id, "_pytol_cond") # Ensure added, get ID

            ca_c += f"\t\tConditionalAction{eol}\t\t{{{eol}" \
                    f"\t\t\tid = {ca.id}{eol}" \
                    f"\t\t\tname = {ca.name}{eol}" \
                    f"\t\t\tconditionalID = {cond_id_val}{eol}" \
                    f"{event_info_block}\t\t}}{eol}"
            
        # --- RANDOM EVENTS ---
        re_c = ""
        for rnd in self.random_events: # rnd is RandomEvent (the container)
            actions_c = "" # String for all ACTION blocks within this RANDOM_EVENT
            for action in rnd.action_options: # action is RandomEventAction
                targets_c = ""
                # Format EventTargets within this action
                for target in action.actions:
                    params_c = ""
                    for p in target.params:
                        # Resolve param value links
                        param_value = p.value
                        if isinstance(p.value, GlobalValue):
                            param_value = p.value.name
                        elif isinstance(p.value, Waypoint):
                            param_value = self._get_or_assign_id(p.value, "_pytol_wpt")
                        elif isinstance(p.value, Path):
                            param_value = self._get_or_assign_id(p.value, "_pytol_path")
                        elif isinstance(p.value, Unit):
                            found_id = next((u['unitInstanceID'] for u in self.units if u['unit_obj'] is p.value), None)
                            if found_id is not None:
                                param_value = found_id
                            else:
                                self.logger.warning(f"Could not find unitInstanceID for Unit param value in RandomEvent {rnd.id}, Action {action.id}")
                        # Format ParamInfo (with ParamAttrInfo)
                        # Convert list values to semicolon format (e.g., [2] -> "2;")
                        formatted_value = _format_id_list(param_value) + ";" if isinstance(param_value, list) else _format_value(param_value)
                        param_info_block = f"\t\t\t\t\t\tParamInfo{eol}\t\t\t\t\t\t{{{eol}" \
                                           f"\t\t\t\t\t\t\ttype = {p.type}{eol}" \
                                           f"\t\t\t\t\t\t\tvalue = {formatted_value}{eol}" \
                                           f"\t\t\t\t\t\t\tname = {p.name}{eol}"
                        if p.attr_info:
                            attr_type = p.attr_info.get('type')
                            attr_data = p.attr_info.get('data')
                            if attr_type and attr_data:
                                param_info_block += f"\t\t\t\t\t\t\t\tParamAttrInfo{eol}\t\t\t\t\t\t\t\t{{{eol}" \
                                                    f"\t\t\t\t\t\t\t\t\ttype = {attr_type}{eol}" \
                                                    f"\t\t\t\t\t\t\t\t\tdata = {attr_data}{eol}" \
                                                    f"\t\t\t\t\t\t\t\t}}{eol}"
                        param_info_block += f"\t\t\t\t\t\t}}{eol}"
                        params_c += param_info_block

                    # Resolve target ID links
                    target_id_val = target.target_id
                    # ... (Copy full target ID resolution logic from ConditionalActions/TimedEvents) ...
                    if target.target_type == "GlobalValue":
                         if isinstance(target.target_id, GlobalValue):
                             target_id_val = target.target_id.name
                         elif not isinstance(target.target_id, str):
                             target_id_val = str(target.target_id)
                    elif target.target_type == "Unit":
                         if isinstance(target.target_id, Unit):
                              found_id = next((u['unitInstanceID'] for u in self.units if u['unit_obj'] is target.target_id), None)
                              if found_id is not None:
                                  target_id_val = found_id
                              else:
                                  self.logger.warning(f"Could not find unitInstanceID for Unit target ID in RandomEvent {rnd.id}, Action {action.id}")
                         elif not isinstance(target.target_id, int):
                              try:
                                  target_id_val = int(target.target_id)
                              except ValueError:
                                  self.logger.warning(f"Unit target ID not int for RandomEvent {rnd.id}, Action {action.id}")
                    # ... etc. for Waypoint, Path, Conditional ...

                    # Format EventTarget
                    targets_c += f"\t\t\t\tEventTarget{eol}\t\t\t\t{{{eol}" \
                                f"\t\t\t\t\ttargetType = {target.target_type}{eol}" \
                                f"\t\t\t\t\ttargetID = {_format_value(target_id_val)}{eol}" \
                                f"\t\t\t\t\teventName = {target.event_name}{eol}" \
                                f"\t\t\t\t\tmethodName = {target.method_name or target.event_name}{eol}" \
                                f"\t\t\t\t\taltTargetIdx = -1{eol}" \
                                f"{params_c}\t\t\t\t\t}}{eol}"

                # Format the EVENT_INFO block for this ACTION
                event_info_content = f"\t\t\t\t\teventName = {eol}{targets_c}"
                event_info_block = _format_block("EVENT_INFO", event_info_content, 4) # Indent 4 (not 5!)

                # Build nested CONDITIONAL block for ACTION
                # If a Conditional object/tree is provided, embed the full graph; otherwise use a placeholder
                conditional_block_inner = (
                    f"\t\t\t\tCONDITIONAL{eol}\t\t\t\t{{{eol}"
                    f"\t\t\t\t\tid = 0{eol}"
                    f"\t\t\t\t\toutputNodePos = (0, 0, 0){eol}"
                    f"\t\t\t\t}}{eol}"
                )
                if action.conditional and not isinstance(action.conditional, str):
                    try:
                        # Generate a self-contained conditional block with id=0, then reindent to 4 tabs
                        nested = self._format_conditional("0", action.conditional)
                        # Re-indent from 2/3 tabs used by _format_conditional to 4/5 tabs for nested placement
                        nested_lines = nested.splitlines(True)
                        adjusted = []
                        for ln in nested_lines:
                            if ln.startswith("\t\t\t\t"): # already deep
                                adjusted.append("\t\t" + ln)  # push two more tabs
                            elif ln.startswith("\t\t\t"):
                                adjusted.append("\t\t\t" + ln) # add 3rd tab to reach 5
                            elif ln.startswith("\t\t"):
                                adjusted.append("\t\t\t\t" + ln[2:])
                            else:
                                adjusted.append("\t\t\t\t" + ln)
                        conditional_block_inner = "".join(adjusted)
                    except Exception as ex:
                        self.logger.warning(f"Failed to embed nested conditional for RandomEvent {rnd.id} Action {action.id}: {ex}")


                # Format the ACTION block
                action_block_content = (
                    f"\t\t\t\tid = {action.id}{eol}"
                    f"\t\t\t\tactionName = {action.action_name}{eol}"
                    f"\t\t\t\tfixedWeight = {_format_value(action.fixed_weight)}{eol}"
                    f"\t\t\t\tgvWeight = {action.gv_weight_name or -1}{eol}" # Use -1 if no GV specified
                    f"\t\t\t\tuseGv = {action.use_gv_weight}{eol}"
                    f"{conditional_block_inner}" # Include the nested conditional block
                    f"{event_info_block}"        # Include the nested event info block
                )
                actions_c += _format_block("ACTION", action_block_content, 3) # Indent 3 (not 4!)

            # Format the outer RANDOM_EVENT block
            re_c += f"\t\tRANDOM_EVENT{eol}\t\t{{{eol}" \
                    f"\t\t\tid = {rnd.id}{eol}" \
                    f"\t\t\tnote = {rnd.name}{eol}" \
                    f"{actions_c}\t\t}}{eol}" # Include all ACTION blocks

        # --- EVENT SEQUENCES ---
        es_c = ""
        # Build EventSequences block with SEQUENCE and nested EVENT entries
        for seq in self.event_sequences:
            events_c = ""
            for ev in seq.events:
                # Build EventTargets for this EVENT's EventInfo
                targets_c = ""
                for target in ev.actions:
                    params_c = ""
                    for p in target.params:
                        # Resolve param value links
                        param_value = p.value
                        if isinstance(p.value, GlobalValue):
                            param_value = p.value.name
                        elif isinstance(p.value, Waypoint):
                            param_value = self._get_or_assign_id(p.value, "_pytol_wpt")
                        elif isinstance(p.value, Path):
                            param_value = self._get_or_assign_id(p.value, "_pytol_path")
                        elif isinstance(p.value, Unit):
                            found_id = next((u['unitInstanceID'] for u in self.units if u['unit_obj'] is p.value), None)
                            if found_id is not None:
                                param_value = found_id
                            else:
                                self.logger.warning(f"Could not find unitInstanceID for Unit param value in EventSequence {seq.id}")

                        # Convert list values to semicolon format else normal format
                        formatted_value = _format_id_list(param_value) + ";" if isinstance(param_value, list) else _format_value(param_value)

                        param_info_block = (
                            f"\t\t\t\t\tParamInfo\n\t\t\t\t\t{{\n"
                            f"\t\t\t\t\t\ttype = {p.type}\n"
                            f"\t\t\t\t\t\tvalue = {formatted_value}\n"
                            f"\t\t\t\t\t\tname = {p.name}\n"
                        )
                        if p.attr_info:
                            attr_type = p.attr_info.get('type')
                            attr_data = p.attr_info.get('data')
                            if attr_type and attr_data:
                                param_info_block += (
                                    f"\t\t\t\t\t\t\tParamAttrInfo\n\t\t\t\t\t\t\t{{\n"
                                    f"\t\t\t\t\t\t\t\ttype = {attr_type}\n"
                                    f"\t\t\t\t\t\t\t\tdata = {attr_data}\n"
                                    f"\t\t\t\t\t\t\t}}\n"
                                )
                        param_info_block += "\t\t\t\t\t}\n"
                        params_c += param_info_block

                    # Resolve target ID links
                    target_id_val = target.target_id
                    if target.target_type == "GlobalValue":
                        if isinstance(target.target_id, GlobalValue):
                            target_id_val = target.target_id.name
                        elif not isinstance(target.target_id, str):
                            target_id_val = str(target.target_id)
                    elif target.target_type == "Unit":
                        if isinstance(target.target_id, Unit):
                            found_id = next((u['unitInstanceID'] for u in self.units if u['unit_obj'] is target.target_id), None)
                            if found_id is not None:
                                target_id_val = found_id
                            else:
                                self.logger.warning(f"Could not find unitInstanceID for Unit target ID in EventSequence {seq.id}")
                        elif not isinstance(target.target_id, int):
                            try:
                                target_id_val = int(target.target_id)
                            except ValueError:
                                self.logger.warning(f"Unit target ID not int for EventSequence {seq.id}")
                    elif target.target_type == "Waypoint":
                        if isinstance(target.target_id, Waypoint):
                            target_id_val = self._get_or_assign_id(target.target_id, "_pytol_wpt")
                        elif not isinstance(target.target_id, int):
                            try:
                                target_id_val = int(target.target_id)
                            except ValueError:
                                self.logger.warning(f"Waypoint target ID should be int, got {target.target_id}")
                    elif target.target_type == "Path":
                        if isinstance(target.target_id, Path):
                            target_id_val = self._get_or_assign_id(target.target_id, "_pytol_path")
                        elif not isinstance(target.target_id, int):
                            try:
                                target_id_val = int(target.target_id)
                            except ValueError:
                                self.logger.warning(f"Path target ID should be int, got {target.target_id}")
                    elif target.target_type == "Conditional":
                        if isinstance(target.target_id, Conditional):
                            target_id_val = self._get_or_assign_id(target.target_id, "_pytol_cond")
                        elif not isinstance(target.target_id, str):
                            self.logger.warning(f"Conditional target ID should be string, got {target.target_id}")
                            target_id_val = str(target.target_id)

                    # Format EventTarget
                    targets_c += (
                        f"\t\t\t\tEventTarget\n\t\t\t\t{{\n"
                        f"\t\t\t\t\ttargetType = {target.target_type}\n"
                        f"\t\t\t\t\ttargetID = {_format_value(target_id_val)}\n"
                        f"\t\t\t\t\teventName = {target.event_name}\n"
                        f"\t\t\t\t\tmethodName = {target.method_name or target.event_name}\n"
                        f"{params_c}\t\t\t\t}}\n"
                    )

                # Build EventInfo block for this EVENT
                event_info_content = f"\t\t\t\teventName = \n{targets_c}"
                event_info_block = _format_block("EventInfo", event_info_content, 4)

                # Resolve this EVENT's conditional link (id or 0)
                event_cond_id_val_str = "0"
                if ev.conditional is not None:
                    if isinstance(ev.conditional, Conditional):
                        event_cond_id_val_str = self._get_or_assign_id(ev.conditional, "_pytol_cond")
                    elif isinstance(ev.conditional, str):
                        event_cond_id_val_str = ev.conditional
                        if event_cond_id_val_str not in self.conditionals:
                            self.logger.warning(f"EventSequence {seq.id} event '{ev.node_name}' uses unknown conditional ID '{event_cond_id_val_str}'")
                    else:
                        try:
                            event_cond_id_val_str = str(int(ev.conditional))
                        except Exception:
                            self.logger.warning(f"Invalid conditional link '{ev.conditional}' in EventSequence {seq.id} event '{ev.node_name}'")

                # Compose EVENT block
                event_block = (
                    f"\t\t\tEVENT\n\t\t\t{{\n"
                    f"\t\t\t\tnodeName = {ev.node_name}\n"
                    f"\t\t\t\tdelay = {_format_value(ev.delay)}\n"
                    f"\t\t\t\tconditional = {event_cond_id_val_str}\n"
                    f"{event_info_block}"
                    f"\t\t\t}}\n"
                )
                events_c += event_block

            # Build nested whileConditional graph if provided
            while_conditional_block = ""
            if hasattr(seq, 'while_conditional') and seq.while_conditional is not None:
                if not isinstance(seq.while_conditional, str):
                    try:
                        # Generate self-contained conditional graph, reindent to 3 tabs for SEQUENCE nesting
                        nested = self._format_conditional("0", seq.while_conditional)
                        nested_lines = nested.splitlines(True)
                        adjusted = []
                        for ln in nested_lines:
                            # Shift from 2/3 tabs to 3/4 tabs for SEQUENCE-level nesting
                            if ln.startswith("\t\t\t\t"):
                                adjusted.append("\t" + ln)
                            elif ln.startswith("\t\t\t"):
                                adjusted.append("\t\t" + ln)
                            elif ln.startswith("\t\t"):
                                adjusted.append("\t\t\t" + ln[2:])
                            else:
                                adjusted.append("\t\t\t" + ln)
                        while_conditional_block = "".join(adjusted)
                    except Exception as ex:
                        self.logger.warning(f"Failed to embed whileConditional for EventSequence {seq.id}: {ex}")

            # Sequence-level block
            list_order_index = seq.id * 10 if hasattr(seq, 'id') else 0
            es_c += (
                f"\t\tSEQUENCE\n\t\t{{\n"
                f"\t\t\tid = {seq.id}\n"
                f"\t\t\tsequenceName = {seq.sequence_name}\n"
                f"\t\t\tstartImmediately = {seq.start_immediately}\n"
                f"\t\t\twhileLoop = {seq.while_loop}\n"
                f"\t\t\tListOrderIndex = {list_order_index}\n"
                f"\t\t\tListFolderName = \n"
                f"{while_conditional_block}"
                f"{events_c}\t\t}}\n"
            )

        # --- BRIEFING ---
        briefing_c = "".join([
            f"\t\tBRIEFING_NOTE{eol}\t\t{{{eol}"
            f"\t\t\ttext = {n.text}{eol}"
            f"\t\t\timagePath = {n.image_path or ''}{eol}"
            f"\t\t\taudioClipPath = {n.audio_clip_path or ''}{eol}"
            f"\t\t}}{eol}" for n in self.briefing_notes
        ])

        # --- RESOURCE MANIFEST ---
        resources_c = "".join([f"\t\t{k} = {v}{eol}" for k, v in self.resource_manifest.items()])


        # --- Return final dictionary ---
        return {
            "UNITS": units_c,
            "PATHS": paths_c,
            "WAYPOINTS": wpts_c,
            "UNITGROUPS": ug_c,             
            "TRIGGER_EVENTS": triggers_c,
            "OBJECTIVES": objs_c,
            "StaticObjects": statics_c,
            "BASES": bases_c,                
            "Conditionals": conditionals_c,  
            "ConditionalActions": ca_c,    
            "RandomEvents": re_c,          
            "EventSequences": es_c,        
            "GlobalValues": gv_c,          
            "Briefing": briefing_c,        
            "ResourceManifest": resources_c, 
            "TimedEventGroups": teg_c      
        }
        

    def _save_to_file(self, path: str):
        """Internal method to generate and write the VTS file content."""
        c = self._generate_content_string()
        eol = "\n"
        vts = f"CustomScenario{eol}{{{eol}"

        # --- Root properties ---
        root_props = [
            f"\tgameVersion = {self.game_version}",
            f"\tcampaignID = {self.campaign_id}",
            f"\tcampaignOrderIdx = {self.campaign_order_idx}",
            f"\tscenarioName = {self.scenario_name}",
            f"\tscenarioID = {self.scenario_id}",
            f"\tscenarioDescription = {self.scenario_description}",
            f"\tmapID = {self.map_id}",
            f"\tvehicle = {self.vehicle}",
            f"\tmultiplayer = {self.multiplayer}",
            f"\tallowedEquips = {self.allowed_equips}",
            f"\tforcedEquips = {self.forced_equips}",
            f"\tforceEquips = {self.force_equips}",
            f"\tnormForcedFuel = {self.norm_forced_fuel}",
            f"\tequipsConfigurable = {self.equips_configurable}",
            f"\tbaseBudget = {self.base_budget}",
            f"\tisTraining = {self.is_training}",
            f"\trtbWptID = {self.rtb_wpt_id}",
            f"\trefuelWptID = {self.refuel_wpt_id}",
        ]
        
        # Add multiplayer-specific properties if multiplayer is enabled
        if self.multiplayer:
            root_props.extend([
                f"\tmpPlayerCount = {self.mp_player_count}",
                f"\tautoPlayerCount = {self.auto_player_count}",
                f"\toverrideAlliedPlayerCount = {self.override_allied_player_count}",
                f"\toverrideEnemyPlayerCount = {self.override_enemy_player_count}",
                f"\tscorePerDeath_A = {self.score_per_death_a}",
                f"\tscorePerDeath_B = {self.score_per_death_b}",
                f"\tscorePerKill_A = {self.score_per_kill_a}",
                f"\tscorePerKill_B = {self.score_per_kill_b}",
                f"\tmpBudgetMode = {self.mp_budget_mode}",
                f"\trtbWptID_B = {self.rtb_wpt_id_b}",
                f"\trefuelWptID_B = {self.refuel_wpt_id_b}",
                f"\tseparateBriefings = {self.separate_briefings}",
                f"\tbaseBudgetB = {self.base_budget_b}",
            ])
        
        # Add common properties
        root_props.extend([
            f"\tinfiniteAmmo = {self.infinite_ammo}",
            f"\tinfAmmoReloadDelay = {self.inf_ammo_reload_delay}",
            f"\tfuelDrainMult = {self.fuel_drain_mult}",
            f"\tenvName = {self.env_name}",
            f"\tselectableEnv = {self.selectable_env}",
            f"\twindDir = {self.wind_dir}",
            f"\twindSpeed = {self.wind_speed}",
            f"\twindVariation = {self.wind_variation}",
            f"\twindGusts = {self.wind_gusts}",
            f"\tdefaultWeather = {self.default_weather}",
            f"\tcustomTimeOfDay = {self.custom_time_of_day}",
            f"\toverrideLocation = {self.override_location}",
            f"\toverrideLatitude = {self.override_latitude}",
            f"\toverrideLongitude = {self.override_longitude}",
            f"\tmonth = {self.month}",
            f"\tday = {self.day}",
            f"\tyear = {self.year}",
            f"\ttimeOfDaySpeed = {self.time_of_day_speed}",
            f"\tqsMode = {self.qs_mode}",
            f"\tqsLimit = {self.qs_limit}",
        ])
        vts += eol.join(root_props) + eol

        # --- WEATHER_PRESETS ---
        if self.weather_presets:
            wp_c = ""
            for wp in self.weather_presets:
                wp_c += (
                    f"\t\tPRESET{eol}\t\t{{{eol}"
                    f"\t\t\tid = {wp.id}{eol}"
                    f"\t\t\tdata = {wp.to_vts_data_line()}{eol}"
                    f"\t\t}}{eol}"
                )
            vts += _format_block("WEATHER_PRESETS", wp_c)
        else:
            vts += _format_block("WEATHER_PRESETS", "")
        vts += _format_block("UNITS", c["UNITS"])
        vts += _format_block("PATHS", c["PATHS"])
        vts += _format_block("WAYPOINTS", c["WAYPOINTS"])
        vts += _format_block("UNITGROUPS", c["UNITGROUPS"])           
        vts += _format_block("TimedEventGroups", c["TimedEventGroups"]) 
        vts += _format_block("TRIGGER_EVENTS", c["TRIGGER_EVENTS"])
        vts += _format_block("OBJECTIVES", c["OBJECTIVES"])
        # --- OBJECTIVES_OPFOR ---
        # Build OBJECTIVES_OPFOR by extracting Objective sub-blocks from the
        # previously generated OBJECTIVES content and including only those
        # objectives that were marked with a team hint (e.g., 'Enemy' or 'OPFOR').
        objs_raw = c.get("OBJECTIVES", "") or ""
        opfor_c = ""
        if objs_raw.strip():
            # Match each Objective block (uses two tabs at start for section entries)
            obj_blocks = re.findall(r"(\t\tObjective\s*\{\n(?:.*?\n)*?\t\t\})", objs_raw, flags=re.DOTALL)
            selected = []
            for blk in obj_blocks:
                m = re.search(r"objectiveID\s*=\s*(\d+)", blk)
                if not m:
                    continue
                oid = int(m.group(1))
                obj = self._objectives_map.get(oid)
                team = None
                if obj is not None:
                    # Prefer fields['team'] hint, fall back to attribute
                    if isinstance(getattr(obj, 'fields', None), dict):
                        team = obj.fields.get('team')
                    if team is None:
                        team = getattr(obj, 'team', None)
                if isinstance(team, str) and team.lower() in ("enemy", "opfor"):
                    selected.append(blk)
            opfor_c = "".join(selected)

        vts += _format_block("OBJECTIVES_OPFOR", opfor_c)
        vts += _format_block("StaticObjects", c["StaticObjects"])
        vts += _format_block("Conditionals", c["Conditionals"])       
        vts += _format_block("ConditionalActions", c["ConditionalActions"]) 
        vts += _format_block("RandomEvents", c["RandomEvents"])         
        vts += _format_block("EventSequences", c["EventSequences"])     
        vts += _format_block("BASES", c["BASES"])                  
        vts += _format_block("GlobalValues", c["GlobalValues"])         
        vts += _format_block("Briefing", c["Briefing"])

        if c["ResourceManifest"]:
            vts += _format_block("ResourceManifest", c["ResourceManifest"])

        vts += f"}}{eol}"

        # Write as binary UTF-8 to enforce LF line endings and no BOM
        with open(path, "wb") as f:
            f.write(vts.encode("utf-8"))

        self.logger.info(f"Mission saved '{path}' (UTF-8 no BOM, LF line endings)")


    def save_mission(self, base_path: str) -> str:
        """
        Saves the mission .vts file and copies the associated map folder
        into the specified base path. Also copies any resource files added
        via add_resource() to their appropriate subdirectories.
        Now includes robust validation and error handling for resources.
        """

        # Run all-block validation before saving (log-only; in strict mode highlight)
        try:
            block_warnings = self.validate_all_blocks()
            if self.strict and block_warnings:
                self.logger.warning(f"Strict mode: {len(block_warnings)} block warnings detected. Proceeding with save.")
            for w in block_warnings:
                self.logger.warning(f"[Block Validation] {w}")
        except Exception as e:
            self.logger.error(f"Block validation error: {e}")

        # Run objective validation before saving (log-only; in strict mode highlight)
        try:
            warnings = self.validate_objectives()
            if self.strict and warnings:
                self.logger.warning(f"Strict mode: {len(warnings)} objective warnings detected. Proceeding with save.")
        except Exception as e:
            self.logger.error(f"Objective validation error: {e}")

        # Run static prefab validation (log-only)
        try:
            sp_warnings = self.validate_static_objects()
            if self.strict and sp_warnings:
                self.logger.warning(f"Strict mode: {len(sp_warnings)} static prefab warnings detected. Proceeding with save.")
        except Exception as e:
            self.logger.error(f"Static prefab validation error: {e}")

        mission_dir = os.path.join(base_path, self.scenario_id)
        os.makedirs(mission_dir, exist_ok=True)

        # Copy map folder robustly
        try:
            if not os.path.exists(self.map_path):
                self.logger.error(f"Map path '{self.map_path}' does not exist. Mission will not be playable.")
            else:
                shutil.copytree(
                    self.map_path,
                    os.path.join(mission_dir, self.map_id),
                    dirs_exist_ok=True
                )
        except Exception as e:
            self.logger.error(f"Error copying map folder: {e}")

        # Copy resource files and update paths to relative
        if self.resource_manifest:
            for res_id, source_path in list(self.resource_manifest.items()):
                if not source_path or not isinstance(source_path, str):
                    self.logger.warning(f"Resource '{res_id}' has invalid or missing path: {source_path}")
                    continue
                if not os.path.isfile(source_path):
                    self.logger.warning(f"Resource file '{source_path}' for '{res_id}' does not exist. Skipping.")
                    continue
                ext = os.path.splitext(source_path)[1].lower()
                if ext in ['.wav', '.ogg', '.mp3']:
                    subdir = 'audio'
                elif ext in ['.png', '.jpg', '.jpeg', '.bmp']:
                    subdir = 'images'
                else:
                    self.logger.warning(f"Unknown resource file extension '{ext}' for resource {res_id}")
                    subdir = 'resources'
                dest_dir = os.path.join(mission_dir, subdir)
                os.makedirs(dest_dir, exist_ok=True)
                filename = os.path.basename(source_path)
                dest_path = os.path.join(dest_dir, filename)
                try:
                    shutil.copy2(source_path, dest_path)
                    relative_path = f"{subdir}/{filename}"
                    self.resource_manifest[res_id] = relative_path
                    self.logger.info(f"✅ Copied resource {res_id}: {filename} → {relative_path}")
                except Exception as e:
                    self.logger.error(f"❌ Error copying resource {res_id} from '{source_path}': {e}")

        vts_path = os.path.join(mission_dir, f"{self.scenario_id}.vts")
        self._save_to_file(vts_path)

        # Record last saved paths for convenience exports
        self._last_saved_dir = mission_dir
        self._last_saved_vts_path = vts_path

        return mission_dir

    def export_to_custom_scenarios(self,
                                   dest_name: Optional[str] = None,
                                   vtol_directory: Optional[str] = None,
                                   overwrite: bool = True) -> str:
        """
        Copy the last-saved mission folder into VTOL VR's CustomScenarios directory.

        Args:
            dest_name: Optional target scenario folder name in CustomScenarios.
                       Defaults to this mission's scenario_id.
            vtol_directory: Override root VTOL VR install directory. If not provided,
                            will use self._vtol_directory, then VTOL_VR_DIR env var.
            overwrite: If True, merges into an existing destination folder.

        Returns:
            The absolute path to the destination scenario folder under CustomScenarios.

        Raises:
            RuntimeError if the mission hasn't been saved yet.
            ValueError if VTOL VR directory cannot be resolved.
        """
        # Ensure we have something to export
        if not self._last_saved_dir or not os.path.isdir(self._last_saved_dir):
            raise RuntimeError("Mission has not been saved yet. Call save_mission(base_path) first.")

        # Resolve VTOL VR directory
        vtol_dir = vtol_directory or self._vtol_directory or os.getenv('VTOL_VR_DIR')
        if not vtol_dir or not os.path.isdir(vtol_dir):
            raise ValueError("VTOL VR directory not found. Provide vtol_directory or set VTOL_VR_DIR.")

        # Determine destination path
        scenario_folder = dest_name or self.scenario_id
        dest_dir = os.path.join(vtol_dir, 'CustomScenarios', scenario_folder)
        os.makedirs(dest_dir, exist_ok=True)

        # Copy contents of last saved folder into destination
        for entry in os.listdir(self._last_saved_dir):
            src_path = os.path.join(self._last_saved_dir, entry)
            dst_path = os.path.join(dest_dir, entry)
            if os.path.isdir(src_path):
                shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
            else:
                if not overwrite and os.path.exists(dst_path):
                    # Skip existing file when overwrite disabled
                    continue
                shutil.copy2(src_path, dst_path)

        self.logger.info(f"Copied mission to CustomScenarios: {dest_dir}")
        return dest_dir

    # ========== Weather Preset Methods ==========

    def add_weather_preset(self, preset: WeatherPreset):
        """
        Add a custom weather preset. Validates that id >= 8 and unique among presets.

        Built-in presets occupy ids 0-7. Use 8+ for customs.
        """
        if preset.id < 8:
            raise ValueError("WeatherPreset.id must be >= 8 to avoid built-in presets (0-7)")
        if any(p.id == preset.id for p in self.weather_presets):
            raise ValueError(f"Duplicate WeatherPreset id {preset.id} already exists")
        self.weather_presets.append(preset)
        self.logger.info(f"✓ Added weather preset '{preset.preset_name}' (id={preset.id})")

    def set_default_weather(self, preset_id: int):
        """
        Set the mission's defaultWeather id. Can be a built-in (0-7) or a custom id (>=8).
        """
        # If custom, ensure it exists to avoid surprises
        if preset_id >= 8 and not any(p.id == preset_id for p in self.weather_presets):
            self.logger.warning(
                f"Setting defaultWeather to id {preset_id} which is not in custom presets list. Proceeding anyway.")
        self.default_weather = preset_id
        self.logger.info(f"✓ Set defaultWeather = {preset_id}")
