"""Validation and error handling for procedural mission generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from pytol.terrain.mission_terrain_helper import MissionTerrainHelper


class ProceduralGenerationError(Exception):
    """Base exception for procedural generation failures."""
    pass


class InvalidTargetError(ProceduralGenerationError):
    """Raised when no valid target location can be found."""
    pass


class InvalidRouteError(ProceduralGenerationError):
    """Raised when route parameters are invalid."""
    pass


class InvalidSpawnLocationError(ProceduralGenerationError):
    """Raised when unit spawn locations cannot be determined."""
    pass


@dataclass
class ValidationResult:
    """Result of a validation check."""
    valid: bool
    message: str = ""
    
    def raise_if_invalid(self, error_class: type = ProceduralGenerationError):
        """Raise an error if validation failed."""
        if not self.valid:
            raise error_class(self.message)


class MissionValidator:
    """Validates mission generation parameters and results."""
    
    def __init__(self, helper: MissionTerrainHelper):
        self.helper = helper
        self.tc = helper.tc
    
    def validate_target_location(
        self, 
        target: Optional[Tuple[float, float, float]],
        mission_type: str
    ) -> ValidationResult:
        """
        Validate that a target location is suitable.
        
        Args:
            target: (x, y, z) coordinates, or None
            mission_type: The mission type
            
        Returns:
            ValidationResult indicating if target is valid
        """
        if target is None:
            return ValidationResult(
                valid=False,
                message="No target location was selected. Map may be too restricted or all candidates rejected."
            )
        
        tx, ty, tz = target
        
        # Check if target is within map bounds [0, map_size]
        map_size = self.tc.total_map_size_meters
        if tx < 0 or tz < 0 or tx > map_size or tz > map_size:
            return ValidationResult(
                valid=False,
                message=f"Target location ({tx:.0f}, {tz:.0f}) is outside map bounds (0..{map_size:.0f}m)"
            )
        
        # Check if target height is valid
        if ty < self.tc.min_height:
            return ValidationResult(
                valid=False,
                message=f"Target location is below minimum terrain height ({ty:.1f} < {self.tc.min_height:.1f})"
            )
        
        if ty > self.tc.max_height + 100:  # allow some margin
            return ValidationResult(
                valid=False,
                message=f"Target location is above maximum terrain height ({ty:.1f} > {self.tc.max_height:.1f})"
            )
        
        # For strike/cas missions, warn if target appears to be in water
        if mission_type in ("strike", "cas", "sead"):
            if ty <= self.tc.min_height + 2.0:
                return ValidationResult(
                    valid=False,
                    message=f"Target location for {mission_type} mission appears to be in water (y={ty:.1f}m)"
                )
        
        return ValidationResult(valid=True)
    
    def validate_route(
        self,
        ingress_dist: float,
        egress_dist: float,
        map_size: float
    ) -> ValidationResult:
        """
        Validate route distance parameters.
        
        Args:
            ingress_dist: Distance from target to ingress point (meters)
            egress_dist: Distance from target to egress point (meters)
            map_size: Total map size in meters
            
        Returns:
            ValidationResult indicating if route is valid
        """
        min_dist = 1000.0  # 1km minimum
        max_dist = map_size * 0.8  # don't exceed 80% of map size
        
        if ingress_dist < min_dist:
            return ValidationResult(
                valid=False,
                message=f"Ingress distance too short: {ingress_dist:.0f}m (minimum {min_dist:.0f}m)"
            )
        
        if egress_dist < min_dist:
            return ValidationResult(
                valid=False,
                message=f"Egress distance too short: {egress_dist:.0f}m (minimum {min_dist:.0f}m)"
            )
        
        if ingress_dist > max_dist:
            return ValidationResult(
                valid=False,
                message=f"Ingress distance exceeds map size: {ingress_dist:.0f}m (max {max_dist:.0f}m for {map_size:.0f}m map)"
            )
        
        if egress_dist > max_dist:
            return ValidationResult(
                valid=False,
                message=f"Egress distance exceeds map size: {egress_dist:.0f}m (max {max_dist:.0f}m for {map_size:.0f}m map)"
            )
        
        return ValidationResult(valid=True)
    
    def validate_spawn_location(
        self,
        spawn_x: float,
        spawn_z: float,
        unit_type: str,
        team: str
    ) -> ValidationResult:
        """
        Validate a unit spawn location.
        
        Args:
            spawn_x: X coordinate
            spawn_z: Z coordinate
            unit_type: Type of unit being spawned
            team: Team the unit belongs to
            
        Returns:
            ValidationResult indicating if spawn location is valid
        """
        # Check map bounds [0, map_size]
        map_size = self.tc.total_map_size_meters
        if spawn_x < 0 or spawn_z < 0 or spawn_x > map_size or spawn_z > map_size:
            return ValidationResult(
                valid=False,
                message=f"Spawn location ({spawn_x:.0f}, {spawn_z:.0f}) for {unit_type} is outside map bounds (0..{map_size:.0f}m)"
            )
        
        # Get terrain height
        try:
            spawn_y = self.tc.get_terrain_height(spawn_x, spawn_z)
        except Exception as e:
            return ValidationResult(
                valid=False,
                message=f"Cannot query terrain height at ({spawn_x:.0f}, {spawn_z:.0f}): {e}"
            )
        
        # Check if height is valid
        if spawn_y < self.tc.min_height or spawn_y > self.tc.max_height + 50:
            return ValidationResult(
                valid=False,
                message=f"Spawn location has invalid height: {spawn_y:.1f}m (range: {self.tc.min_height:.1f} to {self.tc.max_height:.1f})"
            )
        
        # Ground units shouldn't spawn in water
        if "Aircraft" not in unit_type and "Sea" not in unit_type:
            if spawn_y <= self.tc.min_height + 2.0:
                return ValidationResult(
                    valid=False,
                    message=f"Ground unit {unit_type} would spawn in water at ({spawn_x:.0f}, {spawn_z:.0f}, y={spawn_y:.1f}m)"
                )
        
        return ValidationResult(valid=True)
    
    def validate_waypoint_spacing(
        self,
        waypoints: list,
        min_spacing: float = 500.0
    ) -> ValidationResult:
        """
        Validate that waypoints are reasonably spaced.
        
        Args:
            waypoints: List of (x, y, z) waypoint coordinates
            min_spacing: Minimum distance between waypoints in meters
            
        Returns:
            ValidationResult indicating if spacing is valid
        """
        if len(waypoints) < 2:
            return ValidationResult(valid=True)  # Can't check spacing with < 2 waypoints
        
        import math
        for i in range(len(waypoints) - 1):
            x1, _, z1 = waypoints[i]
            x2, _, z2 = waypoints[i + 1]
            dist = math.sqrt((x2 - x1)**2 + (z2 - z1)**2)
            
            if dist < min_spacing:
                return ValidationResult(
                    valid=False,
                    message=f"Waypoints {i} and {i+1} are too close: {dist:.0f}m (minimum {min_spacing:.0f}m)"
                )
        
        return ValidationResult(valid=True)
