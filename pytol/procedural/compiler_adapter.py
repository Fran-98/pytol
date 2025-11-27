"""Mission compiler adapters for the procedural pipeline.

Two layers currently exist:

* `apply_world_state_to_mission` transfers units/assets from the in-memory
  `WorldState` into a real :class:`pytol.parsers.vts_builder.Mission` instance
  using the mission creation rules described in `docs/mission_creation.md`.
* `compile_to_placeholder_vts` remains available for quick inspection of the
  pre-mission WorldState (lightweight JSON artifact used during prototyping).
"""
from __future__ import annotations

import json
import logging
import math
import os
import random
from typing import Dict, Any, Tuple, Optional, TYPE_CHECKING

from pytol.classes.units import (
    Unit,
    AIAircraftSpawn,
    AISeaUnitSpawn,
    GroundUnitSpawn,
    ArtilleryUnitSpawn,
    APCUnitSpawn,
    MultiplayerSpawn,
    PlayerSpawn,
    create_unit,
    UNIT_CLASS_TO_ACTION_CLASS,
)
from pytol.classes.mission_objects import BriefingNote, GlobalValue
from pytol.classes.objectives import create_objective
from pytol.procedural.unit_templates import UnitLibrary, UNIT_TEAM_DATABASE
from pytol.procedural.world_state import WorldState
from pytol.procedural.validation import validate_mission_compilation

if TYPE_CHECKING:
    from pytol.parsers.vts_builder import Mission

try:
    import numpy as _np
except Exception:  # pragma: no cover - numpy optional dependency
    _np = None

logger = logging.getLogger(__name__)


def _normalize_position(value: Any) -> Tuple[float, float, float]:
    if value is None:
        return (0.0, 0.0, 0.0)
    if isinstance(value, (list, tuple)):
        if len(value) == 3:
            return (float(value[0]), float(value[1]), float(value[2]))
        if len(value) == 2:
            return (float(value[0]), 0.0, float(value[1]))
        if len(value) == 1:
            return (float(value[0]), 0.0, 0.0)
    try:
        return (float(value["x"]), float(value.get("y", 0.0)), float(value.get("z", 0.0)))  # type: ignore
    except Exception:
        return (0.0, 0.0, 0.0)


def _normalize_rotation(value: Any) -> Tuple[float, float, float]:
    if value is None:
        return (0.0, 0.0, 0.0)
    if isinstance(value, (list, tuple)):
        if len(value) >= 3:
            return (float(value[0]), float(value[1]), float(value[2]))
    try:
        return (float(value["x"]), float(value["y"]), float(value["z"]))  # type: ignore
    except Exception:
        return (0.0, 0.0, 0.0)


def _attach_action_helper(unit_obj: Unit) -> None:
    """Ensure unit has an action helper attached (target_id assigned later)."""
    try:
        action_cls = UNIT_CLASS_TO_ACTION_CLASS.get(type(unit_obj))
        if action_cls:
            if getattr(unit_obj, "actions", None) is None:
                unit_obj.actions = action_cls(target_id=None)  # type: ignore[call-arg]
    except Exception:
        logger.debug("CompilerAdapter: failed to attach action helper for %s", unit_obj.unit_id)


def _infer_team(unit_type: str, explicit: Optional[str] = None) -> str:
    if explicit:
        return explicit
    allowed = UNIT_TEAM_DATABASE.get(unit_type)
    if allowed:
        if "Enemy" in allowed:
            return "Enemy"
        return next(iter(allowed))
    return "Enemy"


def _infer_placement(unit_obj: Unit) -> str:
    """Map Unit subclass to Mission.add_unit placement keyword."""
    if isinstance(unit_obj, AISeaUnitSpawn):
        return "sea"
    if isinstance(unit_obj, (GroundUnitSpawn, ArtilleryUnitSpawn, APCUnitSpawn)):
        return "ground"
    if isinstance(unit_obj, (PlayerSpawn, MultiplayerSpawn)):
        # Player spawns derive placement from team start mode; keep ground for carriers/bases
        try:
            unit_fields = getattr(unit_obj, "unit_fields", {}) or {}
            if unit_fields.get("spawn_on_ground") or unit_fields.get("start_on_ground"):
                return "ground"
        except Exception:
            pass
        return "airborne"
    if isinstance(unit_obj, AIAircraftSpawn):
        # If start_on_ground flag true, place on ground
        try:
            unit_fields = getattr(unit_obj, "unit_fields", {}) or {}
            if unit_fields.get("start_on_ground"):
                return "ground"
        except Exception:
            pass
        return "airborne"
    # As a fallback inspect unit_fields
    try:
        unit_fields = getattr(unit_obj, "unit_fields", {}) or {}
        if unit_fields.get("start_on_ground"):
            return "ground"
    except Exception:
        pass
    return "airborne"


def _get_template_for_unit(unit_type: str):
    """Return the first UnitTemplate matching unit_type if available."""
    for list_name in (
        "ENEMY_VEHICLES",
        "ENEMY_AIR",
        "ENEMY_SAMS",
        "ENEMY_INFANTRY",
        "ALLIED_VEHICLES",
        "ALLIED_SAMS",
        "ALLIED_INFANTRY",
    ):
        try:
            for tpl in getattr(UnitLibrary, list_name):
                if tpl.unit_type == unit_type:
                    return tpl
        except Exception:
            continue
    return None


def _materialize_dict_unit(entry: Dict[str, Any]) -> Unit:
    token = entry.get("type") or entry.get("unit_type")
    if not token:
        raise ValueError("Unit entry missing 'type'")

    resolved = UnitLibrary.resolve_abstract(token) or token

    pos = _normalize_position(entry.get("pos") or entry.get("position"))
    rot = _normalize_rotation(entry.get("rotation") or entry.get("rot"))
    team = _infer_team(resolved, entry.get("team"))
    name = entry.get("name") or entry.get("unit_name") or resolved

    # Ensure registry built so templates are available
    if not UnitLibrary.ENEMY_VEHICLES:
        UnitLibrary.build_from_registry()

    tpl = _get_template_for_unit(resolved)
    if tpl:
        try:
            rng = random.Random(hash(resolved) & 0xFFFFFFFF)
            unit_obj = UnitLibrary.template_to_unit_object(tpl, rng, position=pos, unit_name=name)
            _attach_action_helper(unit_obj)
            return unit_obj
        except Exception as exc:
            logger.warning("CompilerAdapter: template materialization failed for '%s': %s", resolved, exc)

    try:
        unit_obj = create_unit(resolved, name, team, list(pos), list(rot))
    except Exception as exc:
        raise ValueError(f"create_unit failed for '{resolved}' (team={team}): {exc}") from exc

    if unit_obj is None:
        raise ValueError(f"create_unit returned None for '{resolved}'")

    _attach_action_helper(unit_obj)
    return unit_obj


def _extract_world_state(world_state: WorldState | Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """Extract all components from WorldState including unit placements."""
    if isinstance(world_state, WorldState):
        return (world_state.units, world_state.assets, world_state.objectives, 
                world_state.conditionals, world_state.triggers, world_state.global_values,
                world_state.unit_placements)
    if isinstance(world_state, dict):
        units = world_state.get("units") or {}
        assets = world_state.get("assets") or {}
        objectives = world_state.get("objectives") or {}
        conditionals = world_state.get("conditionals") or {}
        triggers = world_state.get("triggers") or {}
        global_values = world_state.get("global_values") or {}
        unit_placements = world_state.get("unit_placements") or {}
        return units, assets, objectives, conditionals, triggers, global_values, unit_placements
    raise TypeError(f"Unsupported world_state type: {type(world_state)}")


def _resolve_target_label_to_unit_ids(target_label: str, unit_id_map: Dict[str, int], units: Dict[str, Any], world_state: Optional[WorldState] = None) -> List[int]:
    """Resolve abstract target_label (e.g., 'enemy_airbase', 'sam_network') to actual unit IDs.
    
    Enhanced resolution patterns:
    - enemy_airbase -> All units at enemy bases (SAMs, aircraft, buildings)
    - sam_network -> All SAM units in threat layers
    - artillery_battery -> All artillery units
    - convoy -> All convoy units
    - enemy_unit -> All enemy units of appropriate type
    """
    resolved_ids = []
    
    # Simple heuristics to match target labels to units
    label_lower = target_label.lower()
    
    # Use WorldState query methods if available for more efficient filtering
    if world_state and hasattr(world_state, 'query_units_by_team'):
        # For enemy_airbase, get all enemy units (more efficient)
        if "enemy" in label_lower and ("airbase" in label_lower or "base" in label_lower):
            enemy_units = world_state.query_units_by_team("Enemy")
            # Map enemy units back to their keys and then to mission IDs
            for unit_obj in enemy_units:
                for wsm_key, u in units.items():
                    if u is unit_obj and wsm_key in unit_id_map:
                        resolved_ids.append(unit_id_map[wsm_key])
                        break
            if resolved_ids:
                return resolved_ids
    
    # Special pattern matching for common target labels - use WorldState query methods if available
    if world_state and hasattr(world_state, 'get_unit_keys_by_pattern'):
        if "sam_network" in label_lower or "sam network" in label_lower:
            # Collect all SAM units using WorldState pattern query
            sam_keys = world_state.get_unit_keys_by_pattern("sam")
            aa_keys = world_state.get_unit_keys_by_pattern("aa")
            all_sam_keys = list(set(sam_keys + aa_keys))
            for wsm_key in all_sam_keys:
                if wsm_key in unit_id_map:
                    resolved_ids.append(unit_id_map[wsm_key])
            if resolved_ids:
                return resolved_ids
        
        if "artillery_battery" in label_lower or "artillery battery" in label_lower:
            # Collect all artillery units using WorldState pattern query
            arty_keys = world_state.get_unit_keys_by_pattern("artillery")
            arty_keys.extend(world_state.get_unit_keys_by_pattern("howitzer"))
            arty_keys = list(set(arty_keys))  # Remove duplicates
            for wsm_key in arty_keys:
                if wsm_key in unit_id_map:
                    resolved_ids.append(unit_id_map[wsm_key])
            if resolved_ids:
                return resolved_ids
        
        if "convoy" in label_lower:
            # Collect convoy units using WorldState pattern query
            convoy_keys = world_state.get_unit_keys_by_pattern("convoy")
            convoy_keys.extend(world_state.get_unit_keys_by_pattern("logistic"))
            convoy_keys = list(set(convoy_keys))  # Remove duplicates
            for wsm_key in convoy_keys:
                if wsm_key in unit_id_map:
                    resolved_ids.append(unit_id_map[wsm_key])
            if resolved_ids:
                return resolved_ids
        
        # Static structure targets (bunkers, factories, missile silos)
        if "static_factories" in label_lower or "factories" in label_lower:
            # Get factory structure IDs from assets
            factory_asset = world_state.assets.get("objective_factories", {})
            if isinstance(factory_asset, dict):
                factory_ids = factory_asset.get("structure_ids", [])
                for struct_id in factory_ids:
                    if struct_id in unit_id_map:
                        resolved_ids.append(unit_id_map[struct_id])
            # Also try pattern matching
            factory_keys = world_state.get_unit_keys_by_pattern("factory")
            for wsm_key in factory_keys:
                if wsm_key in unit_id_map and wsm_key not in [unit_id_map.get(sid) for sid in resolved_ids]:
                    resolved_ids.append(unit_id_map[wsm_key])
            if resolved_ids:
                return resolved_ids
        
        if "static_missile_silos" in label_lower or "missile_silos" in label_lower or "missile silos" in label_lower:
            silo_asset = world_state.assets.get("objective_missile_silos", {})
            if isinstance(silo_asset, dict):
                silo_ids = silo_asset.get("structure_ids", [])
                for struct_id in silo_ids:
                    if struct_id in unit_id_map:
                        resolved_ids.append(unit_id_map[struct_id])
            silo_keys = world_state.get_unit_keys_by_pattern("missilesilo")
            silo_keys.extend(world_state.get_unit_keys_by_pattern("silo"))
            for wsm_key in silo_keys:
                if wsm_key in unit_id_map and wsm_key not in [unit_id_map.get(sid) for sid in resolved_ids]:
                    resolved_ids.append(unit_id_map[wsm_key])
            if resolved_ids:
                return resolved_ids
        
        if "static_bunkers" in label_lower or "bunkers" in label_lower:
            # Get bunker structure IDs from assets (these are WorldState unit keys)
            bunker_asset = world_state.assets.get("objective_bunkers", {})
            if isinstance(bunker_asset, dict):
                bunker_ids = bunker_asset.get("structure_ids", [])
                for struct_id in bunker_ids:
                    # struct_id is a WorldState unit key (e.g., "static_structure_1")
                    if struct_id in unit_id_map:
                        resolved_ids.append(unit_id_map[struct_id])
                    else:
                        # Try to find by matching unit name or type
                        for wsm_key, unit_obj in units.items():
                            if wsm_key == struct_id and wsm_key in unit_id_map:
                                resolved_ids.append(unit_id_map[wsm_key])
                                break
            # Also try pattern matching for bunker units
            if world_state:
                try:
                    bunker_keys = world_state.get_unit_keys_by_pattern("bunker")
                    for wsm_key in bunker_keys:
                        if wsm_key in unit_id_map and unit_id_map[wsm_key] not in resolved_ids:
                            resolved_ids.append(unit_id_map[wsm_key])
                except Exception:
                    pass
            # Try to find static structures with bunker in name or type
            for wsm_key, unit_obj in units.items():
                if wsm_key not in unit_id_map:
                    continue
                if isinstance(unit_obj, dict):
                    unit_name = str(unit_obj.get("name", "")).lower()
                    unit_type = str(unit_obj.get("type", "")).lower()
                else:
                    unit_name = str(getattr(unit_obj, "unit_name", "")).lower()
                    unit_type = str(getattr(unit_obj, "unit_id", "")).lower()
                # Check if it's a bunker by name, type, or if key contains "bunker"
                if "bunker" in unit_name or "bunker" in unit_type or "bunker" in wsm_key.lower():
                    if unit_id_map[wsm_key] not in resolved_ids:
                        resolved_ids.append(unit_id_map[wsm_key])
            if resolved_ids:
                return resolved_ids
    
    # Fallback: manual pattern matching (if WorldState not available or methods not found)
    if "sam_network" in label_lower or "sam network" in label_lower:
        # Collect all SAM units (from threat layers and spawns)
        for wsm_key, unit_obj in units.items():
            if wsm_key not in unit_id_map:
                continue
            if isinstance(unit_obj, dict):
                unit_type = unit_obj.get("type", "").lower()
                placement_info = unit_obj.get("placement_info", {})
                placement = placement_info.get("tactical_role", "").lower() if isinstance(placement_info, dict) else ""
            else:
                unit_type = getattr(unit_obj, "unit_type", "").lower()
                placement_info = getattr(unit_obj, "placement_info", None)
                placement = placement_info.get("tactical_role", "").lower() if isinstance(placement_info, dict) else ""
            # Match SAM units by type or placement role
            if ("sam" in unit_type or "aa" in unit_type) or ("sam" in placement or "air_defense" in placement):
                resolved_ids.append(unit_id_map[wsm_key])
        return resolved_ids
    
    if "artillery_battery" in label_lower or "artillery battery" in label_lower:
        # Collect all artillery units
        for wsm_key, unit_obj in units.items():
            if wsm_key not in unit_id_map:
                continue
            if isinstance(unit_obj, dict):
                unit_type = unit_obj.get("type", "").lower()
            else:
                unit_type = getattr(unit_obj, "unit_type", "").lower()
            if "artillery" in unit_type or "howitzer" in unit_type:
                resolved_ids.append(unit_id_map[wsm_key])
        return resolved_ids
    
    if "convoy" in label_lower:
        # Collect convoy units
        for wsm_key, unit_obj in units.items():
            if wsm_key not in unit_id_map:
                continue
            if isinstance(unit_obj, dict):
                unit_type = unit_obj.get("type", "").lower()
                unit_name = str(unit_obj.get("name", "")).lower()
            else:
                unit_type = getattr(unit_obj, "unit_type", "").lower()
                unit_name = getattr(unit_obj, "unit_name", "").lower()
            if "convoy" in unit_type or "convoy" in unit_name or "logistic" in unit_type:
                resolved_ids.append(unit_id_map[wsm_key])
        return resolved_ids
    
    # Check each unit in the world state
    for wsm_key, unit_obj in units.items():
        if wsm_key not in unit_id_map:
            continue  # Unit wasn't added to mission
            
        mission_uid = unit_id_map[wsm_key]
        
        # Check if unit matches the target label
        matched = False
        if isinstance(unit_obj, dict):
            unit_type = unit_obj.get("type", "").lower()
            unit_name = str(unit_obj.get("name", "")).lower()
            team = unit_obj.get("team", "").lower()
        else:
            unit_type = getattr(unit_obj, "unit_type", "").lower()
            unit_name = getattr(unit_obj, "unit_name", "").lower()
            team = getattr(unit_obj, "team", "").lower()
        
        # Match patterns
        if "enemy" in label_lower and "enemy" in team:
            if "airbase" in label_lower or "base" in label_lower:
                # For airbase/base, match any enemy unit (SAMs, aircraft, vehicles near bases)
                matched = True
            elif "fleet" in label_lower:
                # Match naval units
                if "carrier" in unit_type or "destroyer" in unit_type or "cruiser" in unit_type:
                    matched = True
            elif "sam" in label_lower and ("sam" in unit_type or "aa" in unit_type):
                matched = True
            elif "radar" in label_lower and "radar" in unit_type:
                matched = True
            elif "cap" in label_lower or "aircraft" in label_lower:
                if "ef-" in unit_type or "asf" in unit_type or "fighter" in unit_type:
                    matched = True
            elif "unit" in label_lower:
                # Generic enemy_unit - match any enemy unit
                matched = True
        elif label_lower in unit_name or label_lower in unit_type:
            matched = True
            
        if matched:
            resolved_ids.append(mission_uid)
    
    return resolved_ids


def apply_world_state_to_mission(
    mission: "Mission",
    world_state: WorldState | Dict[str, Any],
    include_assets: bool = True,
) -> Dict[str, int]:
    """Populate a Mission instance using units and assets from WorldState.

    Returns:
        Mapping of world-state unit keys to the assigned mission unitInstanceID.
    """
    units, assets, objectives, conditionals, triggers, global_values, unit_placements = _extract_world_state(world_state)
    # Store WorldState instance if available for query methods
    wsm_instance = world_state if isinstance(world_state, WorldState) else None
    unit_id_map: Dict[str, int] = {}
    objective_id_map: Dict[str, int] = {}
    
    # Step 0: Create player waypoint first (if it exists) so we can set it on player unit
    player_waypoint_id = None
    if include_assets:
        try:
            player_waypoint_asset = assets.get("player_waypoint")
            if player_waypoint_asset and isinstance(player_waypoint_asset, dict):
                waypoint_pos = player_waypoint_asset.get("pos")
                waypoint_name = player_waypoint_asset.get("name", "Objective")
                
                if waypoint_pos and len(waypoint_pos) >= 3:
                    from pytol.classes.mission_objects import Waypoint as WaypointObj
                    waypoint = WaypointObj(
                        name=waypoint_name,
                        global_point=[float(waypoint_pos[0]), float(waypoint_pos[1]), float(waypoint_pos[2])]
                    )
                    player_waypoint_id = mission.add_waypoint(waypoint)
                    logger.info("CompilerAdapter: Created player waypoint '%s' (ID: %s) before adding units", waypoint_name, player_waypoint_id)
        except Exception as exc:
            logger.warning("CompilerAdapter: Failed to create player waypoint early: %s", exc)
    
    # Step 1: Add units first (objectives need unit IDs)
    for key, payload in units.items():
        try:
            if isinstance(payload, Unit):
                unit_obj = payload
            elif isinstance(payload, dict):
                if "cap_waypoints" in payload:
                    logger.info("CompilerAdapter: skipping non-unit entry '%s' (type=%s)", key, payload.get("type"))
                    continue
                unit_obj = _materialize_dict_unit(payload)
            else:
                logger.warning("CompilerAdapter: unsupported unit payload type %s (key=%s)", type(payload), key)
                continue

            # Set player waypoint on player unit BEFORE adding to mission
            is_player = (key == "player" or 
                        (isinstance(unit_obj, Unit) and "player" in unit_obj.unit_name.lower()) or
                        (isinstance(unit_obj, Unit) and unit_obj.unit_id == "PlayerSpawn"))
            
            if is_player and player_waypoint_id is not None:
                # Set waypoint on player unit before adding to mission
                if isinstance(unit_obj, Unit):
                    if unit_obj.unit_fields is None:
                        unit_obj.unit_fields = {}
                    unit_obj.unit_fields['default_waypoint'] = player_waypoint_id
                    logger.info("CompilerAdapter: Set waypoint %s on player unit before adding to mission", player_waypoint_id)
            
            # Check for placement metadata from intelligent placement
            placement_info = unit_placements.get(key)
            
            if placement_info:
                # Check for base_spawn metadata (aircraft cold start)
                base_spawn = placement_info.get("base_spawn")
                if base_spawn:
                    # Use base spawn placement for aircraft
                    try:
                        # Set start_on_ground flag in unit fields
                        if isinstance(unit_obj, Unit):
                            if not hasattr(unit_obj, 'unit_fields') or unit_obj.unit_fields is None:
                                unit_obj.unit_fields = {}
                            unit_obj.unit_fields['start_on_ground'] = True
                        
                        # For player units, use add_unit_at_base_spawn
                        # For other units, we could also use it, but let's be explicit
                        mission_uid = mission.add_unit_at_base_spawn(
                            unit_obj,
                            base_index=base_spawn.get("base_index", 0),
                            category=base_spawn.get("category", "hangar"),
                            spawn_index=base_spawn.get("spawn_index", 0)
                        )
                        logger.debug("CompilerAdapter: Added unit '%s' at base spawn (base=%d, category=%s)", 
                                   key, base_spawn.get("base_index", 0), base_spawn.get("category", "hangar"))
                        
                        # After adding unit, update unit_fields if they were modified
                        # This ensures waypoints and other fields set later are preserved
                        if isinstance(unit_obj, Unit) and unit_obj.unit_fields:
                            # The unit has been added, but we need to ensure fields are preserved
                            # Mission.add_unit_at_base_spawn calls add_unit internally, which should preserve unit_fields
                            pass
                    except Exception as exc:
                        logger.warning("CompilerAdapter: Failed to add unit '%s' at base spawn, falling back to regular placement: %s", key, exc)
                        # Fallback to regular placement
                        placement = placement_info.get("placement_mode", "ground")
                        use_smart = placement_info.get("use_smart_placement", False)  # Base spawn positions are already precise
                        align_to_surface = placement_info.get("align_to_surface", True)
                        mission_uid = mission.add_unit(
                            unit_obj,
                            placement=placement,
                            use_smart_placement=use_smart,
                            align_to_surface=align_to_surface
                        )
                else:
                    # Use placement metadata from intelligent placement
                    placement = placement_info.get("placement_mode", "airborne")
                    use_smart = placement_info.get("use_smart_placement", True)
                    align_to_surface = placement_info.get("align_to_surface", True)
                    
                    # Get position from placement info if available (intelligent placement may have better position)
                    placement_pos = placement_info.get("position")
                    if placement_pos and isinstance(unit_obj, Unit):
                        try:
                            if isinstance(placement_pos, (list, tuple)) and len(placement_pos) >= 3:
                                unit_obj.global_position = [float(placement_pos[0]), float(placement_pos[1]), float(placement_pos[2])]
                        except Exception:
                            pass
                    
                    # Get rotation from placement info if available
                    rotation = placement_info.get("rotation")
                    if rotation and isinstance(unit_obj, Unit):
                        try:
                            unit_obj.rotation = list(rotation) if isinstance(rotation, (list, tuple)) else [0.0, 0.0, 0.0]
                        except Exception:
                            pass
                    
                    mission_uid = mission.add_unit(
                        unit_obj,
                        placement=placement,
                        use_smart_placement=use_smart,
                        align_to_surface=align_to_surface
                    )
                    logger.debug("CompilerAdapter: Added unit '%s' with intelligent placement (mode=%s, query=%s)", 
                               key, placement, placement_info.get("source_query"))
            else:
                # Fallback to inferred placement
                placement = _infer_placement(unit_obj)
                mission_uid = mission.add_unit(unit_obj, placement=placement)
            
            unit_id_map[key] = mission_uid
            
            # Apply mission flow behaviors and waypoints if available
            if placement_info:
                try:
                    from pytol.procedural.mission_flow import WaypointGenerator
                    from pytol.classes.mission_objects import Waypoint, Path
                    
                    waypoint_strategy = placement_info.get("waypoint_strategy")
                    mission_behaviors = placement_info.get("mission_behaviors", [])
                    related_objective = placement_info.get("related_objective")
                    
                    # Check if this unit type should have waypoints
                    # Static structures (bunkers, buildings) don't need waypoints
                    unit_class_name = type(unit_obj).__name__.lower()
                    unit_type_str = ""
                    if isinstance(unit_obj, dict):
                        unit_type_str = str(unit_obj.get("type", "")).lower()
                    else:
                        unit_type_str = str(getattr(unit_obj, "type", "")).lower()
                    
                    # Skip waypoint generation for static structures and ground units
                    # Only aircraft and ships should have waypoints
                    is_static_structure = (
                        unit_class_name == "aiunitspawn" or  # AIUnitSpawn (bunkers/static structures)
                        "bunker" in unit_type_str or
                        ("structure" in unit_type_str and "static" in unit_type_str)
                    )
                    
                    # Check if this is a ground unit (not aircraft or ship)
                    is_ground_unit = (
                        "ground" in unit_class_name or
                        "sam" in unit_class_name or  # SAMs are ground-based
                        "radar" in unit_class_name or  # Radars are ground-based
                        "artillery" in unit_class_name or
                        "apc" in unit_class_name or
                        "truck" in unit_class_name or
                        "logistic" in unit_class_name
                    )
                    
                    # Only aircraft and ships should have waypoints
                    is_aircraft = "aircraft" in unit_class_name or "aircraft" in unit_type_str
                    is_ship = "ship" in unit_class_name or "ship" in unit_type_str or "sea" in unit_class_name
                    
                    if is_static_structure or (is_ground_unit and not is_aircraft and not is_ship):
                        logger.debug("CompilerAdapter: Skipping waypoint generation for static/ground unit '%s' (class: %s)", key, unit_class_name)
                        waypoint_strategy = None
                    
                    # Get terrain helper from mission if available
                    terrain_helper = None
                    if hasattr(mission, 'tc') and mission.tc:
                        try:
                            from pytol.terrain.mission_terrain_helper import MissionTerrainHelper
                            terrain_helper = MissionTerrainHelper(mission.tc)
                            logger.debug("CompilerAdapter: Created terrain helper for waypoint generation")
                        except Exception as exc:
                            logger.debug("CompilerAdapter: Could not create terrain helper: %s", exc)
                    
                    # Log if waypoint strategy is found
                    if waypoint_strategy:
                        logger.info("CompilerAdapter: Unit '%s' has waypoint strategy '%s'", key, waypoint_strategy)
                    
                    # Generate waypoints if strategy is defined
                    if waypoint_strategy and terrain_helper:
                        logger.info("CompilerAdapter: Generating waypoints for unit '%s' with strategy '%s'", key, waypoint_strategy)
                        waypoint_gen = WaypointGenerator(terrain_helper)
                        
                        # Get unit position
                        unit_pos = placement_info.get("position")
                        if not unit_pos and isinstance(unit_obj, Unit):
                            unit_pos = getattr(unit_obj, "global_position", None)
                        if not unit_pos:
                            # Try to get from unit's position attribute
                            unit_pos = getattr(unit_obj, "position", None)
                        if not unit_pos:
                            logger.warning("CompilerAdapter: Unit '%s' has no position, using (0,0,0)", key)
                            unit_pos = (0, 0, 0)
                        else:
                            # Ensure unit_pos is a tuple/list with at least 3 elements
                            if isinstance(unit_pos, (list, tuple)) and len(unit_pos) >= 3:
                                unit_pos = tuple(float(x) for x in unit_pos[:3])
                            else:
                                logger.warning("CompilerAdapter: Unit '%s' has invalid position format: %s", key, unit_pos)
                                unit_pos = (0, 0, 0)
                        
                        # Find target position from objective key points
                        target_pos = None
                        objective_key_point = None
                        if related_objective and wsm_instance:
                            # Get key points from assets
                            key_points_asset = wsm_instance.assets.get("mission_key_points", {})
                            key_points = key_points_asset.get("points", {}) if isinstance(key_points_asset, dict) else {}
                            
                            # Find key point for this objective
                            for kp_id, kp_info in key_points.items():
                                if isinstance(kp_info, dict):
                                    kp_obj_id = kp_info.get("target_label", "").lower()
                                    if related_objective.lower() in kp_obj_id or kp_obj_id in related_objective.lower():
                                        target_pos = kp_info.get("position")
                                        objective_key_point = kp_info
                                        break
                        
                        # Generate waypoints
                        logger.debug("CompilerAdapter: Generating waypoints - unit_pos=%s, target_pos=%s, strategy=%s", unit_pos, target_pos, waypoint_strategy)
                        waypoint_positions = waypoint_gen.generate_waypoints_for_strategy(
                            strategy=waypoint_strategy,
                            unit_position=unit_pos,
                            target_position=target_pos,
                            objective_key_point=objective_key_point,
                            wsm=wsm_instance
                        )
                        
                        if waypoint_positions:
                            logger.info("CompilerAdapter: Generated %d waypoints for unit '%s' (strategy: %s)", len(waypoint_positions), key, waypoint_strategy)
                        else:
                            logger.warning("CompilerAdapter: No waypoints generated for unit '%s' (strategy: %s, unit_pos: %s, target_pos: %s)", key, waypoint_strategy, unit_pos, target_pos)
                        
                        # Create Waypoint objects and add to mission
                        if waypoint_positions:
                            waypoint_ids = []
                            for i, wp_pos in enumerate(waypoint_positions):
                                if len(wp_pos) >= 3:
                                    wp = Waypoint(
                                        name=f"{key}_wp_{i+1}",
                                        global_point=[float(wp_pos[0]), float(wp_pos[1]), float(wp_pos[2])]
                                    )
                                    wp_id = mission.add_waypoint(wp)
                                    waypoint_ids.append(wp_id)
                            
                            # If multiple waypoints, create a path
                            if len(waypoint_ids) > 1:
                                path_points = [[float(p[0]), float(p[1]), float(p[2])] for p in waypoint_positions if len(p) >= 3]
                                if path_points:
                                    path = Path(
                                        name=f"{key}_path",
                                        points=path_points,
                                        loop=(waypoint_strategy in ["patrol_zone", "orbit_pattern", "defensive_patrol"]),
                                        path_mode="Smooth"
                                    )
                                    path_id = mission.add_path(path)
                                    
                                    # Set default_path on unit if it supports it
                                    if isinstance(unit_obj, Unit):
                                        if hasattr(unit_obj, 'default_path'):
                                            unit_obj.default_path = path_id
                                        elif hasattr(unit_obj, 'unit_fields'):
                                            if unit_obj.unit_fields is None:
                                                unit_obj.unit_fields = {}
                                            unit_obj.unit_fields['default_path'] = path_id
                            
                            # Set first waypoint as default_waypoint if unit supports it
                            if waypoint_ids and isinstance(unit_obj, Unit):
                                if hasattr(unit_obj, 'default_waypoint'):
                                    unit_obj.default_waypoint = waypoint_ids[0]
                                elif hasattr(unit_obj, 'waypoint'):
                                    unit_obj.waypoint = waypoint_ids[0]
                                elif hasattr(unit_obj, 'unit_fields'):
                                    if unit_obj.unit_fields is None:
                                        unit_obj.unit_fields = {}
                                    unit_obj.unit_fields['default_waypoint'] = waypoint_ids[0]
                    
                    # Apply behaviors to unit
                    if mission_behaviors and isinstance(unit_obj, Unit):
                        # Set default_behavior based on behavior type
                        behavior_type = mission_behaviors[0].get("type", "") if mission_behaviors else ""
                        
                        if behavior_type in ["escort", "awacs", "tanker"]:
                            # Set orbit behavior for support flights
                            if hasattr(unit_obj, 'default_behavior'):
                                unit_obj.default_behavior = "Orbit"
                            elif hasattr(unit_obj, 'unit_fields'):
                                if unit_obj.unit_fields is None:
                                    unit_obj.unit_fields = {}
                                unit_obj.unit_fields['default_behavior'] = "Orbit"
                                
                                # Set orbit altitude if specified
                                if behavior_type == "awacs":
                                    unit_obj.unit_fields['orbit_altitude'] = 10000  # 10km
                                elif behavior_type == "tanker":
                                    unit_obj.unit_fields['orbit_altitude'] = 6000  # 6km
                        
                        elif behavior_type in ["defensive_patrol", "network_defense", "battery_defense"]:
                            # Set patrol behavior for defensive units
                            if hasattr(unit_obj, 'default_behavior'):
                                unit_obj.default_behavior = "Patrol"
                            elif hasattr(unit_obj, 'unit_fields'):
                                if unit_obj.unit_fields is None:
                                    unit_obj.unit_fields = {}
                                unit_obj.unit_fields['default_behavior'] = "Patrol"
                    
                except Exception as exc:
                    logger.debug("CompilerAdapter: Failed to apply mission flow to unit '%s': %s", key, exc)
            
        except Exception as exc:
            logger.warning("CompilerAdapter: failed to add unit '%s': %s", key, exc)
            continue
    
    # Step 2: Register global values
    for gv_name, gv_info in global_values.items():
        try:
            if isinstance(gv_info, GlobalValue):
                mission.add_global_value(gv_info)
            elif isinstance(gv_info, dict):
                gv = GlobalValue(
                    name=gv_info.get("name", gv_name),
                    initial_value=gv_info.get("initial_value", 0),
                )
                mission.add_global_value(gv)
        except Exception as exc:
            logger.warning("CompilerAdapter: failed to add global value '%s': %s", gv_name, exc)
    
    # Step 3: Register conditionals
    for cond_id, cond_obj in conditionals.items():
        try:
            mission.add_conditional(cond_obj, conditional_id=cond_id)
        except Exception as exc:
            logger.warning("CompilerAdapter: failed to add conditional '%s': %s", cond_id, exc)
    
    # Step 4: Create objectives (after units are added so we can resolve targets)
    obj_counter = 1
    for obj_key, obj_info in objectives.items():
        try:
            if not isinstance(obj_info, dict):
                continue
                
            obj_type = obj_info.get("type", "Destroy")
            obj_name = obj_info.get("name", f"Objective {obj_counter}")
            obj_desc = obj_info.get("description", obj_info.get("info", obj_name))
            target_label = obj_info.get("target_label")
            required = obj_info.get("required", True)
            reward = obj_info.get("completion_reward", obj_info.get("reward", 100))
            
            # Resolve target_label to actual unit IDs if it's a Destroy objective
            target_ids = []
            if target_label and obj_type == "Destroy":
                target_ids = _resolve_target_label_to_unit_ids(target_label, unit_id_map, units, wsm_instance)
                if not target_ids:
                    logger.warning("CompilerAdapter: could not resolve target_label '%s' to any unit IDs for objective '%s'", target_label, obj_name)
                    # Fallback: use all enemy units via WorldState query if available
                    if wsm_instance and hasattr(wsm_instance, 'query_units_by_team'):
                        enemy_units = wsm_instance.query_units_by_team("Enemy")
                        for unit_obj in enemy_units:
                            for wsm_key, u in units.items():
                                if u is unit_obj and wsm_key in unit_id_map:
                                    target_ids.append(unit_id_map[wsm_key])
                                    break
                    else:
                        # Fallback: manual filtering
                        target_ids = [uid for wsm_key, uid in unit_id_map.items() 
                                      if units.get(wsm_key) and (
                                          (isinstance(units[wsm_key], dict) and units[wsm_key].get("team") == "Enemy") or
                                          (hasattr(units[wsm_key], "team") and getattr(units[wsm_key], "team") == "Enemy")
                                      )]
            
            # Handle objective dependencies (unlocks_after)
            prereqs = None
            unlocks_after = obj_info.get("unlocks_after")
            if unlocks_after and unlocks_after in objective_id_map:
                # Secondary/optional objective unlocks after primary completes
                prereqs = [objective_id_map[unlocks_after]]
            
            # Link waypoint to objective if player_waypoint exists
            obj_waypoint = None
            if player_waypoint_id is not None and obj_type == "Destroy":
                # For player objectives, link the waypoint
                # Waypoint ID might be int or string - use as-is
                obj_waypoint = player_waypoint_id
            
            # Create objective object
            obj = create_objective(
                id_name=obj_type,
                objective_id=obj_counter,
                name=obj_name,
                info=obj_desc,
                required=required,
                targets=target_ids if obj_type == "Destroy" and target_ids else None,
                prereqs=prereqs,  # Add prerequisite objectives
                waypoint=obj_waypoint,  # Link waypoint to objective
            )
            # Set completionReward after creation (it's a base field, not a kwarg)
            obj.completionReward = reward
            
            mission_obj_id = mission.add_objective(obj)
            objective_id_map[obj_key] = mission_obj_id
            obj_counter += 1
            
        except Exception as exc:
            logger.warning("CompilerAdapter: failed to create objective '%s': %s", obj_key, exc)
    
    # Step 5: Add triggers (after objectives/conditionals are registered)
    from pytol.classes.mission_objects import Trigger, EventTarget, ParamInfo
    from pytol.classes.mission_objects import Waypoint as WaypointObj
    
    trigger_counter = 1
    for trigger_id, trigger_info in triggers.items():
        try:
            if not isinstance(trigger_info, dict):
                continue
                
            trigger_type = trigger_info.get("type", "proximity")
            trigger_name = trigger_info.get("name", f"Trigger {trigger_counter}")
            
            if trigger_type == "proximity":
                # Create a proximity trigger
                center = trigger_info.get("center", (0, 0, 0))
                radius = trigger_info.get("radius", 5000.0)
                target_unit_key = trigger_info.get("target_unit_key")
                action = trigger_info.get("action", "activate")
                
                # Create waypoint at trigger center for proximity trigger
                # Normalize center position to [x, y, z] format
                center_pos = _normalize_position(center)
                waypoint = WaypointObj(
                    name=f"TriggerWp_{trigger_counter}",
                    global_point=list(center_pos)  # Required: [x, y, z] coordinates
                )
                wpt_id = mission.add_waypoint(waypoint)  # Returns waypoint ID for linking
                
                # Create event targets based on action
                event_targets = []
                if target_unit_key and target_unit_key in unit_id_map:
                    target_unit_id = unit_id_map[target_unit_key]
                    
                    # Get unit object to access actions helper
                    unit_obj = units.get(target_unit_key)
                    if unit_obj and hasattr(unit_obj, "actions"):
                        if action == "activate_sam":
                            # Activate SAM radar
                            try:
                                # Use the unit's actions helper to create activation event
                                if hasattr(unit_obj.actions, "set_detection_mode"):
                                    et = unit_obj.actions.set_detection_mode("radar_on")
                                    if et:
                                        event_targets.append(et)
                            except Exception:
                                pass
                    
                    # Fallback: create a generic activation event target
                    if not event_targets:
                        event_targets.append(EventTarget(
                            target_type="Unit",
                            target_id=str(target_unit_id),
                            event_name="SetDetectionMode",
                            params=[ParamInfo(name="mode", type="string", value="radar_on")]
                        ))
                
                # Create trigger
                trigger = Trigger(
                    id=trigger_counter,
                    name=trigger_name,
                    trigger_type="Proximity",
                    waypoint=wpt_id,
                    radius=float(radius),
                    spherical_radius=True,
                    event_targets=event_targets,
                )
                mission.add_trigger_event(trigger)
                trigger_counter += 1
                
            elif trigger_type == "unit_destroyed":
                # Unit destroyed trigger - use ConditionalAction instead of Trigger
                # Conditionals don't work alone, they need to be used by ConditionalAction or referenced in triggers
                target_unit_key = trigger_info.get("target_unit_key")
                action = trigger_info.get("action", "spawn_reinforcements")
                reinforcement_key = trigger_info.get("reinforcement_unit_key")
                
                if target_unit_key and target_unit_key in unit_id_map:
                    target_unit_id = unit_id_map[target_unit_key]
                    
                    # Create conditional that checks if unit is destroyed
                    # Note: Conditionals use string IDs (e.g., "_pytol_cond_0"), but unit references 
                    # inside COMP blocks should be integers (the unitInstanceID)
                    from pytol.classes.conditionals import Sccunit
                    cond = Sccunit(
                        unit=target_unit_id,  # Unit ID should be integer (unitInstanceID)
                        method_name="IsAlive",
                        is_not=True  # Invert: true when unit is NOT alive (destroyed)
                    )
                    
                    # Register conditional and get its ID
                    conditional_id = mission.add_conditional(cond)
                    
                    # Create ConditionalAction that executes when unit is destroyed
                    from pytol.classes.mission_objects import ConditionalAction
                    
                    # Build event targets based on action
                    event_targets = []
                    if action == "spawn_reinforcements" and reinforcement_key:
                        if reinforcement_key in unit_id_map:
                            # TODO: Create proper spawn action via EventSequence
                            # For now, just log it
                            logger.info(
                                "CompilerAdapter: Reinforcement trigger '%s' registered "
                                "(reinforcement unit: %d) - EventSequence needed for spawning",
                                trigger_name,
                                unit_id_map[reinforcement_key]
                            )
                    
                    # Create ConditionalAction that links the conditional to actions
                    # ConditionalAction needs an id, name, conditional_id (Union[str, int]), and actions
                    # add_conditional() returns an integer ID, but ConditionalAction accepts Union[str, int]
                    conditional_action = ConditionalAction(
                        id=trigger_counter + 1000,  # Offset to avoid conflicts with trigger IDs
                        name=trigger_name,
                        conditional_id=conditional_id,  # add_conditional() returns int, ConditionalAction accepts Union[str, int]
                        actions=event_targets if event_targets else []
                    )
                    
                    # Add ConditionalAction to mission
                    mission.add_conditional_action(conditional_action)
                    
                    trigger_counter += 1
                    logger.info("CompilerAdapter: Created unit_destroyed conditional action '%s' for unit %d (conditional: %s)", 
                              trigger_name, target_unit_id, conditional_id)
                else:
                    logger.warning("CompilerAdapter: unit_destroyed trigger '%s' has invalid target_unit_key '%s'", trigger_id, target_unit_key)
                    
            else:
                # Unknown trigger type - log as note
                logger.debug("CompilerAdapter: unknown trigger type '%s' for trigger '%s'", trigger_type, trigger_id)
                if hasattr(mission, "add_briefing_note"):
                    mission.add_briefing_note(BriefingNote(text=f"Trigger {trigger_id} ({trigger_type}): {trigger_info}"))
        except Exception as exc:
            logger.warning("CompilerAdapter: failed to create trigger '%s': %s", trigger_id, exc)

    if include_assets:
        try:
            # Handle player waypoint from MVP mode
            player_waypoint_asset = assets.get("player_waypoint")
            if player_waypoint_asset and isinstance(player_waypoint_asset, dict):
                try:
                    waypoint_pos = player_waypoint_asset.get("pos")
                    waypoint_name = player_waypoint_asset.get("name", "Objective")
                    
                    if waypoint_pos and len(waypoint_pos) >= 3:
                        from pytol.classes.mission_objects import Waypoint as WaypointObj
                        waypoint = WaypointObj(
                            name=waypoint_name,
                            global_point=[float(waypoint_pos[0]), float(waypoint_pos[1]), float(waypoint_pos[2])]
                        )
                        waypoint_id = mission.add_waypoint(waypoint)
                        logger.info("CompilerAdapter: Added player waypoint '%s' (ID: %d)", waypoint_name, waypoint_id)
                        
                        # Set waypoint on player unit if available
                        player_unit_key = None
                        for wsm_key, unit_obj in units.items():
                            if isinstance(unit_obj, dict):
                                unit_type = unit_obj.get("type", "").lower()
                            else:
                                unit_type = getattr(unit_obj, "unit_id", "").lower()
                            if "player" in unit_type or wsm_key == "player":
                                player_unit_key = wsm_key
                                break
                        
                        if player_unit_key and player_unit_key in unit_id_map:
                            player_unit_id = unit_id_map[player_unit_key]
                            player_unit_obj = units.get(player_unit_key)
                            if player_unit_obj:
                                # Set default_waypoint on player
                                if hasattr(player_unit_obj, 'default_waypoint'):
                                    player_unit_obj.default_waypoint = waypoint_id
                                elif hasattr(player_unit_obj, 'waypoint'):
                                    player_unit_obj.waypoint = waypoint_id
                                elif hasattr(player_unit_obj, 'unit_fields'):
                                    if player_unit_obj.unit_fields is None:
                                        player_unit_obj.unit_fields = {}
                                    player_unit_obj.unit_fields['default_waypoint'] = waypoint_id
                                logger.info("CompilerAdapter: Set waypoint %d as default for player unit", waypoint_id)
                except Exception as exc:
                    logger.warning("CompilerAdapter: Failed to add player waypoint: %s", exc)
            
            # Record other assets as mission notes for manual inspection.
            for key, info in assets.items():
                if key == "player_waypoint":
                    continue  # Already handled above
                # Skip adding assets as briefing notes - they cause KeyNotFoundException
                # The game expects specific briefing note format, and our debug assets don't match
                # Instead, just log them for debugging
                logger.debug("CompilerAdapter: Skipping asset '%s' as briefing note (would cause parsing error)", key)
        except Exception:
            pass

    # Validate mission compilation
    wsm_instance = world_state if isinstance(world_state, WorldState) else None
    if wsm_instance:
        validation_report = validate_mission_compilation(mission, wsm_instance, unit_id_map)
        if validation_report.errors:
            logger.error("CompilerAdapter: Validation found %d errors after compilation", len(validation_report.errors))
            for error in validation_report.errors[:10]:  # Log first 10 errors
                logger.error("CompilerAdapter Validation Error: %s", error)
        if validation_report.warnings:
            logger.warning("CompilerAdapter: Validation found %d warnings after compilation", len(validation_report.warnings))
            for warning in validation_report.warnings[:10]:  # Log first 10 warnings
                logger.warning("CompilerAdapter Validation Warning: %s", warning)
    
    # Validate mission blocks using Mission's built-in validation
    try:
        validation_errors = mission.validate_all_blocks()
        if validation_errors:
            logger.error("CompilerAdapter: Mission.validate_all_blocks() found %d errors", len(validation_errors))
            for error in validation_errors[:10]:  # Log first 10 errors
                logger.error("Mission Validation Error: %s", error)
    except Exception as exc:
        logger.warning("CompilerAdapter: Could not validate mission blocks: %s", exc)

    return unit_id_map


def compile_to_placeholder_vts(world_state: Dict[str, Any], out_path: str) -> str:
    """Write a small JSON placeholder to out_path and return the path.

    This is not a real .vts writer - it's a scaffold so the rest of the
    pipeline can be exercised without having the final serializer ready.
    """
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    payload = {
        "summary": "Placeholder mission generated by pytol procedural MVP",
        "world_state": world_state,
    }

    def _normalize(obj):
        """Recursively convert non-JSON-native types (numpy scalars, tuples)
        into JSON-serializable Python primitives.
        """
        if _np is not None and isinstance(obj, _np.generic):
            return obj.item()
        if _np is not None and isinstance(obj, _np.ndarray):
            return obj.tolist()
        if isinstance(obj, tuple):
            return [_normalize(v) for v in obj]
        if isinstance(obj, dict):
            return {str(k): _normalize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_normalize(v) for v in obj]
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        return obj

    normalized = _normalize(payload)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(normalized, f, indent=2)
    return out_path


__all__ = ["apply_world_state_to_mission", "compile_to_placeholder_vts"]

