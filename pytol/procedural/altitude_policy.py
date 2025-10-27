from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple, List


@dataclass
class ThreatEnvironment:
    """Represents the threat environment for altitude planning."""
    sam_sites: List[Tuple[float, float]] = None  # SAM positions (x, z)
    radar_sites: List[Tuple[float, float]] = None  # Radar positions (x, z)
    fighter_threats: bool = False  # Presence of enemy fighters
    manpads_density: float = 0.0  # 0-1, density of MANPADS in area
    
    def __post_init__(self):
        if self.sam_sites is None:
            self.sam_sites = []
        if self.radar_sites is None:
            self.radar_sites = []


@dataclass
class AltitudePolicy:
    """
    Advanced altitude selection based on mission type, threat environment, and terrain.
    
    Implements realistic military aviation altitude selection doctrine:
    - Low-level penetration for strike missions in high threat areas
    - Medium altitude for balance of survivability and effectiveness
    - High altitude for air-to-air and surveillance missions
    - Terrain masking considerations for threat avoidance
    """
    mission_type: str = "strike"

    def choose_agl(self, threat_level: float) -> float:
        """
        Return a suggested AGL (meters AGL). Enhanced heuristic considering:
        - Mission type and tactical requirements
        - Threat environment and survivability
        - Terrain masking opportunities
        """
        t = max(0.0, min(1.0, threat_level))
        
        if self.mission_type in {"strike", "cas", "sead"}:
            # Attack missions: Lower altitude in high threat
            # NOE: 50-200m, Low-level: 200-500m, Medium: 500-1000m
            if t > 0.7:  # High threat - NOE profile
                return 50 + (1.0 - t) * 150  # 50-200m AGL
            elif t > 0.4:  # Medium threat - Low level
                return 200 + (1.0 - t) * 300  # 200-500m AGL  
            else:  # Low threat - Medium altitude
                return 500 + (1.0 - t) * 500  # 500-1000m AGL
                
        elif self.mission_type in {"intercept", "cap"}:
            # Air-to-air missions: Higher altitude for energy advantage
            return 3000 + (1.0 - t) * 5000  # 3-8km AGL
            
        elif self.mission_type in {"transport", "medevac"}:
            # Transport: Balance between efficiency and survivability  
            if t > 0.6:  # High threat - stay low
                return 100 + (1.0 - t) * 200  # 100-300m AGL
            else:  # Low threat - cruise altitude
                return 300 + (1.0 - t) * 700  # 300-1000m AGL
                
        elif self.mission_type in {"reconnaissance", "surveillance"}:
            # Recon: Medium-high altitude for sensor performance
            return 800 + (1.0 - t) * 1200  # 800-2000m AGL
            
        else:  # Default
            return 400 + (1.0 - t) * 600  # 400-1000m AGL
    
    def calculate_tactical_altitude(
        self,
        position: Tuple[float, float, float],
        terrain_height: float,
        threat_env: Optional[ThreatEnvironment] = None,
        min_safe_altitude: float = 50.0
    ) -> float:
        """
        Calculate tactical altitude considering terrain and threats.
        
        Args:
            position: Current position (x, y, z)
            terrain_height: Terrain height at position
            threat_env: Threat environment data
            min_safe_altitude: Minimum safe altitude AGL
            
        Returns:
            Recommended altitude AGL
        """
        base_agl = self.choose_agl(0.0)  # Base altitude for mission type
        
        if threat_env is None:
            return max(base_agl, min_safe_altitude)
        
        # Calculate threat-based modifications
        threat_factor = self._assess_local_threats(position, threat_env)
        
        # High threat -> lower altitude for terrain masking
        if threat_factor > 0.6:
            # Aggressive terrain masking
            terrain_masking_alt = self._calculate_terrain_masking_altitude(
                position, terrain_height, threat_env
            )
            return max(terrain_masking_alt, min_safe_altitude)
        
        elif threat_factor > 0.3:
            # Moderate altitude reduction
            reduced_alt = base_agl * (1.0 - threat_factor * 0.4)
            return max(reduced_alt, min_safe_altitude)
        
        else:
            # Low threat - use standard altitude
            return max(base_agl, min_safe_altitude)
    
    def _assess_local_threats(
        self,
        position: Tuple[float, float, float],
        threat_env: ThreatEnvironment
    ) -> float:
        """Assess threat level at specific position."""
        x, y, z = position
        threat_score = 0.0
        
        # SAM threat assessment
        for sam_x, sam_z in threat_env.sam_sites:
            from pytol.misc.math_utils import calculate_2d_distance
            distance = calculate_2d_distance((x, z), (sam_x, sam_z))
            # SAM threat ranges: Short 15km, Medium 40km, Long 100km+
            if distance < 15000:  # Within short-range SAM envelope
                threat_score += 0.8
            elif distance < 40000:  # Within medium-range SAM envelope  
                threat_score += 0.5
            elif distance < 100000:  # Within long-range SAM envelope
                threat_score += 0.2
        
        # Radar threat assessment
        for radar_x, radar_z in threat_env.radar_sites:
            from pytol.misc.math_utils import calculate_2d_distance
            distance = calculate_2d_distance((x, z), (radar_x, radar_z))
            # Radar detection ranges vary, assume 150km max
            if distance < 50000:  # Close to radar
                threat_score += 0.3
            elif distance < 150000:  # Within radar coverage
                threat_score += 0.1
        
        # MANPADS density (area threat)
        threat_score += threat_env.manpads_density * 0.4
        
        # Fighter threat (increases with altitude preference)
        if threat_env.fighter_threats:
            if self.mission_type in {"intercept", "cap"}:
                threat_score += 0.2  # Less concerning for air-to-air
            else:
                threat_score += 0.5  # Major threat for attack missions
        
        return min(threat_score, 1.0)
    
    def _calculate_terrain_masking_altitude(
        self,
        position: Tuple[float, float, float],
        terrain_height: float,
        threat_env: ThreatEnvironment
    ) -> float:
        """Calculate altitude for terrain masking from threats."""
        
        # Find the closest significant threat
        x, y, z = position
        min_threat_distance = float('inf')
        closest_threat = None
        
        for sam_x, sam_z in threat_env.sam_sites:
            from pytol.misc.math_utils import calculate_2d_distance
            distance = calculate_2d_distance((x, z), (sam_x, sam_z))
            if distance < min_threat_distance:
                min_threat_distance = distance
                closest_threat = (sam_x, sam_z)
        
        if closest_threat is None:
            return 100.0  # Default low altitude
        
        # For terrain masking, we want to stay low enough that terrain
        # features can block line of sight to threats
        
        if min_threat_distance < 5000:  # Very close threat
            return 50.0  # NOE altitude
        elif min_threat_distance < 15000:  # Close threat
            return 100.0  # Low level
        elif min_threat_distance < 30000:  # Medium distance
            return 200.0  # Medium-low
        else:
            return 300.0  # Can afford slightly higher
    
    def get_mission_altitude_profile(self) -> Tuple[float, float, str]:
        """
        Get altitude profile characteristics for mission type.
        
        Returns:
            (min_altitude, max_altitude, flight_profile_description)
        """
        profiles = {
            "strike": (50, 1000, "Low-level penetration with terrain following"),
            "cas": (100, 800, "Medium altitude for target observation and engagement"),
            "sead": (100, 600, "Low-medium altitude for radar suppression"),
            "transport": (200, 1500, "Efficient cruise altitude with threat consideration"), 
            "intercept": (2000, 10000, "High altitude for energy advantage and radar coverage"),
            "cap": (3000, 8000, "Combat air patrol at medium-high altitude"),
            "reconnaissance": (500, 3000, "Medium altitude for sensor effectiveness"),
            "surveillance": (1000, 5000, "High altitude for wide area coverage"),
        }
        
        return profiles.get(self.mission_type, (300, 2000, "Standard cruise profile"))
    
    def validate_altitude_envelope(
        self,
        waypoints: List[Tuple[float, float, float]],
        terrain_calculator
    ) -> List[str]:
        """
        Validate that waypoints are within safe altitude envelope.
        
        Returns list of warning messages for altitude violations.
        """
        warnings = []
        min_alt, max_alt, profile_desc = self.get_mission_altitude_profile()
        
        for i, (x, y, z) in enumerate(waypoints):
            try:
                terrain_height = terrain_calculator.get_terrain_height(x, z)
                agl = y - terrain_height
                
                if agl < min_alt:
                    warnings.append(
                        f"Waypoint {i+1} altitude too low: {agl:.0f}m AGL "
                        f"(minimum {min_alt:.0f}m for {self.mission_type} mission)"
                    )
                elif agl > max_alt:
                    warnings.append(
                        f"Waypoint {i+1} altitude too high: {agl:.0f}m AGL "
                        f"(maximum {max_alt:.0f}m for {self.mission_type} mission)"
                    )
                    
            except Exception as e:
                warnings.append(f"Waypoint {i+1} altitude validation failed: {e}")
        
        return warnings
