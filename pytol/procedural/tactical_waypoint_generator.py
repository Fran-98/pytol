"""
Tactical waypoint generation with terrain awareness for realistic military flight profiles.

This module implements waypoint generation that considers:
- Terrain clearance and masking
- Nap-of-Earth (NOE) flight profiles  
- Threat avoidance through low-level routing
- Valley following for concealment
- Minimum safe altitudes
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List, Tuple, Optional

from pytol.terrain.mission_terrain_helper import MissionTerrainHelper


@dataclass 
class FlightProfile:
    """Defines altitude and routing characteristics for different mission types."""
    mission_type: str
    min_agl: float  # Minimum altitude AGL
    max_agl: float  # Maximum altitude AGL  
    terrain_following: bool  # Whether to follow terrain contours
    threat_avoidance: bool  # Whether to use low-level routing
    valley_preference: float  # 0-1, preference for lower terrain
    
    @classmethod
    def get_profile(cls, mission_type: str) -> 'FlightProfile':
        """Get tactical flight profile for mission type."""
        profiles = {
            "strike": cls("strike", 50, 300, True, True, 0.8),  # Low-level attack
            "cas": cls("cas", 100, 500, True, True, 0.6),       # Close Air Support
            "sead": cls("sead", 150, 400, True, True, 0.7),     # SEAD/DEAD
            "transport": cls("transport", 200, 800, False, True, 0.4),  # Transport
            "intercept": cls("intercept", 1500, 8000, False, False, 0.1), # Air-to-air
            "reconnaissance": cls("reconnaissance", 300, 1000, True, True, 0.5),
        }
        return profiles.get(mission_type, cls("default", 300, 1000, False, False, 0.3))


class TacticalWaypointGenerator:
    """
    Generates terrain-aware waypoints for tactical military flight operations.
    
    Implements realistic flight profiles based on mission type, threat environment,
    and terrain characteristics. Follows military aviation doctrine for different
    mission types.
    """
    
    def __init__(self, terrain_helper: MissionTerrainHelper):
        self.helper = terrain_helper
        self.tc = terrain_helper.tc
        
    def generate_tactical_route(
        self,
        start_pos: Tuple[float, float, float],
        target_pos: Tuple[float, float, float], 
        mission_type: str,
        waypoint_count: int = 5,
        threat_positions: Optional[List[Tuple[float, float]]] = None
    ) -> List[Tuple[float, float, float]]:
        """
        Generate a tactical flight route with terrain-aware waypoints.
        
        Args:
            start_pos: Starting position (x, y, z)
            target_pos: Target position (x, y, z)
            mission_type: Type of mission (affects flight profile)
            waypoint_count: Number of waypoints to generate
            threat_positions: Known threat locations to avoid
            
        Returns:
            List of waypoint positions (x, y, z)
        """
        profile = FlightProfile.get_profile(mission_type)
        
        if profile.terrain_following and profile.threat_avoidance:
            return self._generate_noe_route(start_pos, target_pos, profile, waypoint_count, threat_positions)
        elif profile.terrain_following:
            return self._generate_terrain_following_route(start_pos, target_pos, profile, waypoint_count)
        else:
            return self._generate_high_altitude_route(start_pos, target_pos, profile, waypoint_count)
    
    def _generate_noe_route(
        self,
        start_pos: Tuple[float, float, float],
        target_pos: Tuple[float, float, float],
        profile: FlightProfile,
        waypoint_count: int,
        threat_positions: Optional[List[Tuple[float, float]]]
    ) -> List[Tuple[float, float, float]]:
        """Generate Nap-of-Earth route following valleys and avoiding threats."""
        
        # Use the existing riverbed/valley following algorithm as base
        valley_path = self.helper.find_riverbed_path(
            (start_pos[0], start_pos[2]), 
            (target_pos[0], target_pos[2]),
            steps=waypoint_count * 2  # Generate more points for smoothing
        )
        
        # Convert to tactical waypoints with proper altitude management
        tactical_waypoints = []
        
        for i, (x, terrain_y, z) in enumerate(valley_path):
            # Calculate terrain clearance altitude
            base_altitude = max(profile.min_agl, 50)  # Minimum 50m safety margin
            
            # Add variation based on terrain type and mission phase
            if i < len(valley_path) * 0.3:  # Ingress phase - stay low
                altitude_agl = base_altitude + random.uniform(0, 50)
            elif i > len(valley_path) * 0.7:  # Egress phase - can climb slightly
                altitude_agl = base_altitude + random.uniform(20, 100)
            else:  # Target area - very low
                altitude_agl = base_altitude
                
            # Apply threat avoidance adjustments
            if threat_positions:
                altitude_agl = self._adjust_for_threats(
                    (x, z), altitude_agl, threat_positions, profile
                )
            
            final_y = terrain_y + altitude_agl
            tactical_waypoints.append((x, final_y, z))
        
        # Thin out waypoints to requested count
        return self._thin_waypoints(tactical_waypoints, waypoint_count)
    
    def _generate_terrain_following_route(
        self,
        start_pos: Tuple[float, float, float],
        target_pos: Tuple[float, float, float],
        profile: FlightProfile,
        waypoint_count: int
    ) -> List[Tuple[float, float, float]]:
        """Generate terrain-following route at moderate altitude."""
        
        # Use existing terrain following with tactical considerations
        path = self.helper.get_terrain_following_path(
            (start_pos[0], start_pos[2]),
            (target_pos[0], target_pos[2]),
            steps=waypoint_count,
            altitude_agl=profile.min_agl + (profile.max_agl - profile.min_agl) * 0.3
        )
        
        # Add tactical altitude variations
        tactical_waypoints = []
        for i, (x, y, z) in enumerate(path):
            # Vary altitude based on terrain roughness and mission phase
            terrain_roughness = self._get_terrain_roughness(x, z)
            altitude_modifier = terrain_roughness * 100  # More altitude over rough terrain
            
            # Mission phase considerations
            if i == 0 or i == len(path) - 1:  # Start/end points
                final_y = y  # Use provided altitude
            else:
                final_y = y + altitude_modifier
                
            tactical_waypoints.append((x, final_y, z))
            
        return tactical_waypoints
    
    def _generate_high_altitude_route(
        self,
        start_pos: Tuple[float, float, float],
        target_pos: Tuple[float, float, float],
        profile: FlightProfile,
        waypoint_count: int
    ) -> List[Tuple[float, float, float]]:
        """Generate high-altitude route for intercept/transport missions."""
        
        # Simple linear interpolation at cruise altitude
        waypoints = []
        
        for i in range(waypoint_count):
            t = i / (waypoint_count - 1)
            
            x = start_pos[0] + t * (target_pos[0] - start_pos[0])
            z = start_pos[2] + t * (target_pos[2] - start_pos[2])
            
            # Get terrain height and add safe altitude
            terrain_y = self.tc.get_terrain_height(x, z)
            safe_altitude = profile.min_agl + random.uniform(0, profile.max_agl - profile.min_agl)
            
            # Ensure minimum clearance over terrain
            final_y = max(terrain_y + safe_altitude, terrain_y + 300)  # Minimum 300m AGL
            
            waypoints.append((x, final_y, z))
            
        return waypoints
    
    def _adjust_for_threats(
        self,
        position: Tuple[float, float],
        current_altitude: float,
        threat_positions: List[Tuple[float, float]],
        profile: FlightProfile
    ) -> float:
        """Adjust altitude based on proximity to threats."""
        
        min_threat_distance = float('inf')
        x, z = position
        
        for tx, tz in threat_positions:
            from pytol.misc.math_utils import calculate_2d_distance
            distance = calculate_2d_distance((x, z), (tx, tz))
            min_threat_distance = min(min_threat_distance, distance)
        
        # If within threat range, try to stay lower for terrain masking
        threat_radius = 8000  # 8km typical SAM range
        if min_threat_distance < threat_radius:
            # The closer to threat, the lower we fly (within limits)
            threat_factor = 1.0 - (min_threat_distance / threat_radius)
            altitude_reduction = threat_factor * (current_altitude * 0.5)  # Up to 50% reduction
            return max(current_altitude - altitude_reduction, profile.min_agl)
        
        return current_altitude
    
    def _get_terrain_roughness(self, x: float, z: float, sample_radius: float = 500) -> float:
        """Calculate terrain roughness in area around position."""
        
        try:
            # Sample heights in a grid around the position
            samples = []
            for dx in [-sample_radius, 0, sample_radius]:
                for dz in [-sample_radius, 0, sample_radius]:
                    sample_x = x + dx
                    sample_z = z + dz
                    height = self.tc.get_terrain_height(sample_x, sample_z)
                    samples.append(height)
            
            # Calculate standard deviation as roughness measure
            if len(samples) > 1:
                mean_height = sum(samples) / len(samples)
                variance = sum((h - mean_height)**2 for h in samples) / len(samples)
                return math.sqrt(variance) / 100.0  # Normalize to 0-1 range roughly
            
        except Exception:
            pass
            
        return 0.0  # Default to smooth terrain
    
    def _thin_waypoints(
        self, 
        waypoints: List[Tuple[float, float, float]], 
        target_count: int
    ) -> List[Tuple[float, float, float]]:
        """Reduce waypoint list to target count while preserving important points."""
        
        if len(waypoints) <= target_count:
            return waypoints
            
        # Always keep first and last waypoints
        if target_count < 2:
            return [waypoints[0], waypoints[-1]]
            
        result = [waypoints[0]]  # Always include start
        
        # Calculate indices for intermediate waypoints
        available_slots = target_count - 2  # Minus start and end
        if available_slots > 0:
            step = (len(waypoints) - 2) / available_slots
            for i in range(available_slots):
                index = int(1 + i * step)  # Skip first waypoint
                result.append(waypoints[index])
        
        result.append(waypoints[-1])  # Always include end
        return result
    
    def validate_waypoint_clearance(
        self,
        waypoints: List[Tuple[float, float, float]],
        min_clearance: float = 100.0
    ) -> List[Tuple[str, Tuple[float, float, float]]]:
        """
        Validate that waypoints have adequate terrain clearance.
        
        Returns list of (warning_message, waypoint_position) for issues found.
        """
        warnings = []
        
        for i, (x, y, z) in enumerate(waypoints):
            try:
                terrain_height = self.tc.get_terrain_height(x, z)
                clearance = y - terrain_height
                
                if clearance < min_clearance:
                    warnings.append((
                        f"Waypoint {i+1} has insufficient terrain clearance: {clearance:.1f}m "
                        f"(minimum {min_clearance:.1f}m)",
                        (x, y, z)
                    ))
                    
            except Exception as e:
                warnings.append((
                    f"Waypoint {i+1} terrain validation failed: {e}",
                    (x, y, z)
                ))
        
        return warnings
    
    def generate_combat_air_patrol(
        self,
        center_pos: Tuple[float, float, float],
        patrol_radius: float = 5000,
        altitude_agl: float = 2000,
        num_waypoints: int = 4
    ) -> List[Tuple[float, float, float]]:
        """Generate circular CAP (Combat Air Patrol) waypoints."""
        
        waypoints = []
        cx, cy, cz = center_pos
        
        for i in range(num_waypoints):
            angle = (2 * math.pi * i) / num_waypoints
            
            x = cx + patrol_radius * math.cos(angle)
            z = cz + patrol_radius * math.sin(angle)
            
            # Get terrain height and add patrol altitude
            terrain_height = self.tc.get_terrain_height(x, z)
            y = terrain_height + altitude_agl
            
            waypoints.append((x, y, z))
            
        return waypoints