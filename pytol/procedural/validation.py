"""Validation utilities for procedural mission generation."""

import logging
from typing import Dict, List, Any, Optional, Tuple
from pytol.procedural.world_state import WorldState

logger = logging.getLogger(__name__)


class ValidationReport:
    """Container for validation results."""
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []
    
    def add_error(self, message: str):
        """Add an error message."""
        self.errors.append(message)
        logger.error(f"Validation Error: {message}")
    
    def add_warning(self, message: str):
        """Add a warning message."""
        self.warnings.append(message)
        logger.warning(f"Validation Warning: {message}")
    
    def add_info(self, message: str):
        """Add an info message."""
        self.info.append(message)
        logger.info(f"Validation Info: {message}")
    
    def is_valid(self) -> bool:
        """Check if validation passed (no errors)."""
        return len(self.errors) == 0
    
    def get_summary(self) -> str:
        """Get a summary of validation results."""
        lines = []
        lines.append(f"Validation: {len(self.errors)} errors, {len(self.warnings)} warnings, {len(self.info)} info")
        
        if self.errors:
            lines.append("\nErrors:")
            for error in self.errors[:10]:
                lines.append(f"  - {error}")
        
        if self.warnings:
            lines.append("\nWarnings:")
            for warning in self.warnings[:10]:
                lines.append(f"  - {warning}")
        
        return "\n".join(lines)


def validate_world_state(wsm: WorldState) -> ValidationReport:
    """Validate a WorldState for common issues.
    
    Args:
        wsm: WorldState instance to validate
        
    Returns:
        ValidationReport with errors, warnings, and info
    """
    report = ValidationReport()
    
    # Check units
    if len(wsm.units) == 0:
        report.add_warning("No units in WorldState")
    else:
        report.add_info(f"WorldState contains {len(wsm.units)} units")
        
        # Check for units without placement info
        units_without_placement = []
        for unit_key in wsm.units.keys():
            if unit_key not in wsm.unit_placements:
                units_without_placement.append(unit_key)
        
        if units_without_placement:
            report.add_warning(f"{len(units_without_placement)} units missing placement info")
    
    # Check objectives
    if len(wsm.objectives) == 0:
        report.add_warning("No objectives in WorldState")
    else:
        report.add_info(f"WorldState contains {len(wsm.objectives)} objectives")
        
        # Check objectives have valid target labels
        for obj_key, obj_info in wsm.objectives.items():
            if isinstance(obj_info, dict):
                obj_type = obj_info.get("type", "")
                target_label = obj_info.get("target_label")
                
                if obj_type == "Destroy" and not target_label:
                    report.add_warning(f"Destroy objective '{obj_key}' missing target_label")
    
    # Check territory system
    if len(wsm.territory_zones) == 0:
        report.add_warning("No territory zones defined")
    else:
        total_zones = sum(len(zones) for zones in wsm.territory_zones.values())
        report.add_info(f"WorldState contains {total_zones} territory zones")
    
    # Check static structures
    static_structures = wsm.assets.get("static_structures", {})
    if isinstance(static_structures, dict):
        structures = static_structures.get("structures", {})
        if structures:
            report.add_info(f"WorldState contains {len(structures)} static structures")
            
            # Check structures have units
            for struct_id, struct_info in structures.items():
                if struct_id not in wsm.units:
                    report.add_error(f"Static structure '{struct_id}' not in units")
    
    # Check key points
    key_points = wsm.assets.get("mission_key_points", {})
    if isinstance(key_points, dict):
        points = key_points.get("points", {})
        if points:
            report.add_info(f"WorldState contains {len(points)} mission key points")
    
    return report


def validate_mission_compilation(
    mission,
    wsm: WorldState,
    unit_id_map: Dict[str, int]
) -> ValidationReport:
    """Validate that WorldState was correctly compiled to Mission.
    
    Args:
        mission: Mission instance
        wsm: Original WorldState
        unit_id_map: Mapping from WSM keys to mission unit IDs
        
    Returns:
        ValidationReport with errors and warnings
    """
    report = ValidationReport()
    
    # Check unit mapping
    wsm_unit_keys = set(wsm.units.keys())
    mapped_keys = set(unit_id_map.keys())
    
    missing = wsm_unit_keys - mapped_keys
    if missing:
        report.add_error(f"{len(missing)} units not mapped to mission: {list(missing)[:5]}")
    
    extra = mapped_keys - wsm_unit_keys
    if extra:
        report.add_warning(f"{len(extra)} mapped keys not in WSM units")
    
    # Check mission units
    if hasattr(mission, 'units'):
        mission_unit_count = len(mission.units)
        if mission_unit_count != len(unit_id_map):
            report.add_warning(
                f"Mission unit count ({mission_unit_count}) != mapped count ({len(unit_id_map)})"
            )
    
    # Check objectives
    if hasattr(mission, 'objectives'):
        mission_obj_count = len(mission.objectives) if mission.objectives else 0
        wsm_obj_count = len(wsm.objectives)
        
        if mission_obj_count != wsm_obj_count:
            report.add_warning(
                f"Mission objective count ({mission_obj_count}) != WSM count ({wsm_obj_count})"
            )
    else:
        report.add_warning("Mission has no objectives attribute")
    
    # Check target resolution for objectives
    for obj_key, obj_info in wsm.objectives.items():
        if isinstance(obj_info, dict):
            obj_type = obj_info.get("type", "")
            target_label = obj_info.get("target_label")
            
            if obj_type == "Destroy" and target_label:
                from pytol.procedural.compiler_adapter import _resolve_target_label_to_unit_ids
                
                resolved = _resolve_target_label_to_unit_ids(
                    target_label,
                    unit_id_map,
                    wsm.units,
                    wsm
                )
                
                if not resolved:
                    report.add_warning(
                        f"Objective '{obj_key}' target_label '{target_label}' resolved to 0 units"
                    )
    
    # Check unit positions
    if hasattr(mission, 'units'):
        invalid_positions = []
        # mission.units can be a list or dict
        units_to_check = mission.units.values() if isinstance(mission.units, dict) else mission.units
        for idx, unit_obj in enumerate(list(units_to_check)[:10]):
            try:
                pos = unit_obj.global_position
                if not pos or len(pos) != 3:
                    invalid_positions.append(idx)
                elif any(not isinstance(x, (int, float)) for x in pos):
                    invalid_positions.append(idx)
            except Exception:
                invalid_positions.append(idx)
        
        if invalid_positions:
            report.add_warning(f"{len(invalid_positions)} units have invalid positions")
    
    return report


def validate_generated_mission(wsm: WorldState) -> ValidationReport:
    """Comprehensive validation of generated mission WorldState.
    
    This is called after PCG.realize_plan() to ensure quality.
    
    Args:
        wsm: WorldState instance to validate
        
    Returns:
        ValidationReport with errors, warnings, and info
    """
    report = validate_world_state(wsm)
    
    # Additional checks specific to generated missions
    
    # Check unit spacing (avoid excessive clustering)
    unit_positions = []
    for unit_key in wsm.units.keys():
        placement = wsm.unit_placements.get(unit_key, {})
        pos = placement.get("position")
        if pos and len(pos) >= 3:
            unit_positions.append((pos[0], pos[2]))
    
    # Check for units too close together (within 10m)
    from pytol.misc.math_utils import calculate_2d_distance
    too_close = []
    for i, pos1 in enumerate(unit_positions):
        for j, pos2 in enumerate(unit_positions[i+1:], i+1):
            dist = calculate_2d_distance(pos1, pos2)
            if dist < 10.0:  # 10m minimum spacing
                too_close.append((i, j, dist))
    
    if too_close:
        report.add_warning(f"{len(too_close)} unit pairs are too close (<10m)")
    
    # Check key points are reasonable
    key_points = wsm.assets.get("mission_key_points", {})
    if isinstance(key_points, dict):
        points = key_points.get("points", {})
        if len(points) == 0:
            report.add_warning("No mission key points defined")
    
    # Check static structures are at valid locations
    static_structures = wsm.assets.get("static_structures", {})
    if isinstance(static_structures, dict):
        structures = static_structures.get("structures", {})
        for struct_id, struct_info in structures.items():
            pos = struct_info.get("position")
            if pos and len(pos) >= 3:
                # Check not in water (rough check)
                if pos[1] < 0:
                    report.add_warning(f"Static structure '{struct_id}' appears to be in water (y={pos[1]})")
    
    return report


__all__ = [
    "ValidationReport",
    "validate_world_state",
    "validate_mission_compilation",
    "validate_generated_mission",
]
