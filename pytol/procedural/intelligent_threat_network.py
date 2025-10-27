"""
Intelligent Threat Network System for realistic air defense placement and coordination.

This system implements realistic military air defense doctrine:
- Layered defense with overlapping coverage zones
- Radar/SAM coordination and mutual support
- Realistic threat response patterns and alert states
- Terrain-aware placement for maximum effectiveness
- Dynamic threat escalation based on mission progression
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any, Set
from enum import Enum

from pytol.terrain.mission_terrain_helper import MissionTerrainHelper
from pytol.misc.math_utils import calculate_slope_from_normal, calculate_3d_distance


class ThreatType(Enum):
    """Types of threat systems."""
    EARLY_WARNING_RADAR = "early_warning_radar"  # Long-range detection
    FIRE_CONTROL_RADAR = "fire_control_radar"    # Target tracking/engagement
    SHORT_RANGE_SAM = "short_range_sam"          # 5-15km range (Tor, Pantsir)
    MEDIUM_RANGE_SAM = "medium_range_sam"        # 15-40km range (Buk, SA-11)
    LONG_RANGE_SAM = "long_range_sam"            # 40-150km range (S-300, SA-10)
    MANPADS = "manpads"                          # Shoulder-fired (2-8km range)
    AAA = "aaa"                                  # Anti-aircraft artillery
    FIGHTER_CAP = "fighter_cap"                  # Combat air patrol


class AlertState(Enum):
    """Air defense alert states."""
    PEACETIME = "peacetime"      # Minimal readiness
    HEIGHTENED = "heightened"    # Increased surveillance  
    HIGH_ALERT = "high_alert"    # Combat ready
    ACTIVE_DEFENSE = "active"    # Under attack, full response


@dataclass
class ThreatSystem:
    """Individual threat system with capabilities and state."""
    threat_id: str
    threat_type: ThreatType
    position: Tuple[float, float, float]  # x, y, z
    detection_range: float  # meters
    engagement_range: float  # meters
    min_engagement_altitude: float  # meters AGL
    max_engagement_altitude: float  # meters AGL
    sector_coverage: Tuple[float, float]  # start_angle, end_angle (degrees)
    alert_state: AlertState = AlertState.PEACETIME
    active: bool = True
    supporting_systems: List[str] = field(default_factory=list)  # IDs of supporting systems
    terrain_masking_factor: float = 1.0  # 0-1, how much terrain affects performance
    
    def can_detect(self, target_pos: Tuple[float, float, float], terrain_helper: MissionTerrainHelper) -> bool:
        """Check if this system can detect a target at given position."""
        if not self.active:
            return False
            
        distance = calculate_3d_distance(self.position, target_pos)
        if distance > self.detection_range:
            return False
            
        # Check altitude constraints
        target_agl = target_pos[1] - terrain_helper.tc.get_terrain_height(target_pos[0], target_pos[2])
        if target_agl < self.min_engagement_altitude or target_agl > self.max_engagement_altitude:
            return False
            
        # Check sector coverage
        bearing = self._calculate_bearing(target_pos)
        if not self._in_sector(bearing):
            return False
            
        # Check line of sight (simplified)
        if self._terrain_blocks_los(target_pos, terrain_helper):
            return False
            
        return True
    
    def can_engage(self, target_pos: Tuple[float, float, float], terrain_helper: MissionTerrainHelper) -> bool:
        """Check if this system can engage a target."""
        if not self.can_detect(target_pos, terrain_helper):
            return False
            
        distance = calculate_3d_distance(self.position, target_pos)
        return distance <= self.engagement_range
    
    def _calculate_bearing(self, target_pos: Tuple[float, float, float]) -> float:
        """Calculate bearing to target in degrees."""
        from ..misc.math_utils import calculate_bearing
        return calculate_bearing(self.position, target_pos)
    
    def _in_sector(self, bearing: float) -> bool:
        """Check if bearing is within sector coverage."""
        start_angle, end_angle = self.sector_coverage
        
        # Handle wrap-around (e.g., 350° to 10°)
        if start_angle <= end_angle:
            return start_angle <= bearing <= end_angle
        else:
            return bearing >= start_angle or bearing <= end_angle
    
    def _terrain_blocks_los(self, target_pos: Tuple[float, float, float], terrain_helper: MissionTerrainHelper) -> bool:
        """Simplified terrain masking check."""
        # This is a simplified implementation
        # Real implementation would trace ray through terrain
        
        distance = calculate_3d_distance(self.position, target_pos)
        
        # Longer distances more affected by terrain
        masking_effect = 1.0 - (distance / 50000)  # Reduced effectiveness at 50km+
        masking_effect = max(0.0, masking_effect * self.terrain_masking_factor)
        
        # Random chance based on terrain masking
        return random.random() < masking_effect * 0.3


class IntelligentThreatNetwork:
    """
    Creates and manages realistic air defense networks with coordinated coverage.
    
    Implements military air defense doctrine:
    - Layered defense with early warning -> tracking -> engagement
    - Overlapping coverage zones for mutual support  
    - Terrain-aware placement for maximum effectiveness
    - Realistic threat response and escalation patterns
    """
    
    def __init__(self, terrain_helper: MissionTerrainHelper):
        self.terrain_helper = terrain_helper
        self.threat_systems: Dict[str, ThreatSystem] = {}
        self.network_alert_state = AlertState.PEACETIME
        
    def create_layered_air_defense(
        self,
        center_pos: Tuple[float, float, float],
        defense_radius: float = 30000,  # 30km defense zone
        threat_density: str = "medium",  # low, medium, high, very_high
        primary_threat_axis: float = 0.0  # degrees, main expected attack direction
    ) -> List[ThreatSystem]:
        """
        Create a realistic layered air defense network.
        
        Args:
            center_pos: Center of defended area
            defense_radius: Radius of defense zone in meters
            threat_density: Density of threat systems
            primary_threat_axis: Main expected attack direction (degrees from north)
            
        Returns:
            List of placed threat systems
        """
        systems = []
        
        # Define threat densities
        density_configs = {
            "low": {"ew_radars": 1, "sam_sites": 2, "aaa": 2, "manpads": 3},
            "medium": {"ew_radars": 2, "sam_sites": 4, "aaa": 4, "manpads": 6},
            "high": {"ew_radars": 3, "sam_sites": 6, "aaa": 6, "manpads": 10},
            "very_high": {"ew_radars": 4, "sam_sites": 8, "aaa": 8, "manpads": 15}
        }
        
        config = density_configs.get(threat_density, density_configs["medium"])
        
        # 1. Place Early Warning Radars (outer perimeter)
        ew_positions = self._find_radar_positions(
            center_pos, defense_radius * 1.2, config["ew_radars"], primary_threat_axis
        )
        
        for i, pos in enumerate(ew_positions):
            system = ThreatSystem(
                threat_id=f"ew_radar_{i+1}",
                threat_type=ThreatType.EARLY_WARNING_RADAR,
                position=pos,
                detection_range=150000,  # 150km detection
                engagement_range=0,  # No engagement capability
                min_engagement_altitude=100,
                max_engagement_altitude=30000,
                sector_coverage=(0, 360),  # Full 360° coverage
                terrain_masking_factor=0.2  # Less affected by terrain (high tower)
            )
            systems.append(system)
            self.threat_systems[system.threat_id] = system
        
        # 2. Place SAM Sites (layered defense)
        sam_positions = self._find_sam_positions(
            center_pos, defense_radius, config["sam_sites"], primary_threat_axis
        )
        
        for i, (pos, sam_type) in enumerate(sam_positions):
            if sam_type == "long_range":
                system = ThreatSystem(
                    threat_id=f"sam_lr_{i+1}",
                    threat_type=ThreatType.LONG_RANGE_SAM,
                    position=pos,
                    detection_range=100000,  # 100km detection
                    engagement_range=80000,   # 80km engagement
                    min_engagement_altitude=200,
                    max_engagement_altitude=25000,
                    sector_coverage=self._calculate_optimal_sector(pos, center_pos, primary_threat_axis),
                    terrain_masking_factor=0.4
                )
            elif sam_type == "medium_range":
                system = ThreatSystem(
                    threat_id=f"sam_mr_{i+1}",
                    threat_type=ThreatType.MEDIUM_RANGE_SAM,
                    position=pos,
                    detection_range=40000,   # 40km detection
                    engagement_range=25000,  # 25km engagement
                    min_engagement_altitude=100,
                    max_engagement_altitude=15000,
                    sector_coverage=self._calculate_optimal_sector(pos, center_pos, primary_threat_axis),
                    terrain_masking_factor=0.6
                )
            else:  # short_range
                system = ThreatSystem(
                    threat_id=f"sam_sr_{i+1}",
                    threat_type=ThreatType.SHORT_RANGE_SAM,
                    position=pos,
                    detection_range=15000,   # 15km detection
                    engagement_range=10000,  # 10km engagement
                    min_engagement_altitude=50,
                    max_engagement_altitude=8000,
                    sector_coverage=self._calculate_optimal_sector(pos, center_pos, primary_threat_axis),
                    terrain_masking_factor=0.8
                )
            
            systems.append(system)
            self.threat_systems[system.threat_id] = system
        
        # 3. Place AAA systems (point defense)
        aaa_positions = self._find_aaa_positions(center_pos, defense_radius * 0.7, config["aaa"])
        
        for i, pos in enumerate(aaa_positions):
            system = ThreatSystem(
                threat_id=f"aaa_{i+1}",
                threat_type=ThreatType.AAA,
                position=pos,
                detection_range=8000,    # 8km detection
                engagement_range=5000,   # 5km engagement
                min_engagement_altitude=20,
                max_engagement_altitude=3000,
                sector_coverage=(0, 360),  # Full coverage
                terrain_masking_factor=0.9
            )
            systems.append(system)
            self.threat_systems[system.threat_id] = system
        
        # 4. Place MANPADS (distributed defense)
        manpads_positions = self._distribute_manpads(center_pos, defense_radius, config["manpads"])
        
        for i, pos in enumerate(manpads_positions):
            system = ThreatSystem(
                threat_id=f"manpads_{i+1}",
                threat_type=ThreatType.MANPADS,
                position=pos,
                detection_range=6000,    # 6km detection
                engagement_range=4000,   # 4km engagement
                min_engagement_altitude=20,
                max_engagement_altitude=3500,
                sector_coverage=(0, 360),  # Full coverage
                terrain_masking_factor=1.0  # Highly affected by terrain
            )
            systems.append(system)
            self.threat_systems[system.threat_id] = system
        
        # 5. Create support relationships
        self._establish_support_networks(systems)
        
        return systems
    
    def _find_radar_positions(
        self,
        center_pos: Tuple[float, float, float],
        radius: float,
        count: int,
        primary_axis: float
    ) -> List[Tuple[float, float, float]]:
        """Find optimal positions for early warning radars."""
        positions = []
        
        for i in range(count):
            # Distribute around perimeter with bias toward threat axis
            base_angle = (360 / count) * i
            # Bias toward primary threat axis
            angle_bias = 30 * math.sin(math.radians(base_angle - primary_axis))
            angle = math.radians(base_angle + angle_bias)
            
            # Find highest ground in sector
            best_pos = None
            best_elevation = -float('inf')
            
            from ..misc.math_utils import generate_random_position_in_circle
            for attempt in range(20):
                # Vary distance and angle slightly around the target position
                search_radius = radius * random.uniform(0.8, 1.2)
                angle_variation = math.radians(random.uniform(-30, 30))
                
                # Apply variation to the base angle
                varied_angle = angle + angle_variation
                x = center_pos[0] + search_radius * math.sin(varied_angle)
                z = center_pos[2] + search_radius * math.cos(varied_angle)
                
                try:
                    y = self.terrain_helper.tc.get_terrain_height(x, z)
                    
                    # Check slope (radars need relatively flat ground)
                    normal = self.terrain_helper.tc.get_terrain_normal(x, z)
                    slope = calculate_slope_from_normal(normal)
                    
                    if slope <= 15 and y > best_elevation:  # Max 15° slope
                        best_elevation = y
                        best_pos = (x, y, z)
                        
                except Exception:
                    continue
            
            if best_pos:
                positions.append(best_pos)
        
        return positions
    
    def _find_sam_positions(
        self,
        center_pos: Tuple[float, float, float],
        radius: float,
        count: int,
        primary_axis: float
    ) -> List[Tuple[Tuple[float, float, float], str]]:
        """Find optimal SAM positions with mixed types."""
        positions = []
        
        # Mix of SAM types based on count
        if count <= 2:
            sam_types = ["medium_range"] * count
        elif count <= 4:
            sam_types = ["long_range"] + ["medium_range"] * (count - 1)
        else:
            long_range_count = max(1, count // 3)
            medium_range_count = max(1, count // 2)
            short_range_count = count - long_range_count - medium_range_count
            sam_types = (["long_range"] * long_range_count + 
                        ["medium_range"] * medium_range_count + 
                        ["short_range"] * short_range_count)
        
        for i, sam_type in enumerate(sam_types):
            # Layer positions by range
            if sam_type == "long_range":
                position_radius = radius * 0.9  # Outer layer
            elif sam_type == "medium_range":
                position_radius = radius * 0.6  # Middle layer
            else:
                position_radius = radius * 0.4  # Inner layer
            
            # Find good position with terrain considerations
            best_pos = self._find_defensive_position(
                center_pos, position_radius, primary_axis + (i * 60), sam_type
            )
            
            if best_pos:
                positions.append((best_pos, sam_type))
        
        return positions
    
    def _find_defensive_position(
        self,
        center_pos: Tuple[float, float, float],
        radius: float,
        preferred_bearing: float,
        system_type: str
    ) -> Optional[Tuple[float, float, float]]:
        """Find tactically sound defensive position using mission helper."""
        
        # Use consolidated mission helper function
        result = self.terrain_helper.find_defensive_position(
            center_pos, radius, system_type, preferred_bearing
        )
        
        if result:
            return result['position']
        return None
    
    def _score_defensive_position(
        self,
        position: Tuple[float, float, float],
        center_pos: Tuple[float, float, float],
        system_type: str
    ) -> float:
        """Score defensive position based on tactical factors."""
        
        x, y, z = position
        score = 0.0
        
        try:
            # 1. Slope check (flatter is better for most systems)
            normal = self.terrain_helper.tc.get_terrain_normal(x, z)
            slope = calculate_slope_from_normal(normal)
            
            max_slope = {"long_range": 10, "medium_range": 15, "short_range": 20}.get(system_type, 15)
            if slope <= max_slope:
                score += 50 - slope  # Flatter is better
            else:
                score -= (slope - max_slope) * 5  # Penalty for excessive slope
            
            # 2. Elevation advantage
            center_elevation = self.terrain_helper.tc.get_terrain_height(center_pos[0], center_pos[2])
            elevation_advantage = y - center_elevation
            score += elevation_advantage * 0.1  # Small bonus for height
            
            # 3. Terrain type suitability
            terrain_type = self.terrain_helper.get_terrain_type((x, z))
            terrain_bonuses = {
                "Urban": -10,      # Urban areas are less ideal
                "Forest": -5,      # Trees can interfere
                "Mountainous": 10, # Good for long-range systems
                "Desert": 5,       # Open terrain is good
                "Flat": 15,        # Excellent for SAM sites
            }
            score += terrain_bonuses.get(terrain_type, 0)
            
            # 4. Distance from center (system-specific preferences)
            from pytol.misc.math_utils import calculate_2d_distance
            distance_to_center = calculate_2d_distance((x, z), (center_pos[0], center_pos[2]))
            if system_type == "long_range":
                # Long-range systems prefer some distance for wide coverage
                optimal_distance = 20000
            elif system_type == "medium_range":
                optimal_distance = 12000
            else:
                optimal_distance = 8000
            
            distance_score = max(0, 20 - abs(distance_to_center - optimal_distance) / 1000)
            score += distance_score
            
        except Exception:
            score = -1000  # Invalid position
        
        return score
    
    def _find_aaa_positions(
        self,
        center_pos: Tuple[float, float, float],
        radius: float,
        count: int
    ) -> List[Tuple[float, float, float]]:
        """Find positions for AAA systems (point defense)."""
        positions = []
        
        from ..misc.math_utils import generate_random_position_in_circle
        for i in range(count):
            # Distribute in inner defensive ring (30-80% radius)
            x, _, z = generate_random_position_in_circle(
                center_pos, radius * 0.8, radius * 0.3
            )
            
            # Apply angular distribution with variation
            cx, cz = center_pos[0], center_pos[2]
            dx, dz = x - cx, z - cz
            base_angle = math.radians((360 / count) * i)
            angle_variation = math.radians(random.uniform(-20, 20))
            total_angle = base_angle + angle_variation
            x = cx + math.sqrt(dx*dx + dz*dz) * math.sin(total_angle)
            z = cz + math.sqrt(dx*dx + dz*dz) * math.cos(total_angle)
            
            try:
                y = self.terrain_helper.tc.get_terrain_height(x, z)
                positions.append((x, y, z))
            except Exception:
                # Fallback position if terrain query fails
                positions.append((x, center_pos[1], z))
        
        return positions
    
    def _distribute_manpads(
        self,
        center_pos: Tuple[float, float, float],
        radius: float,
        count: int
    ) -> List[Tuple[float, float, float]]:
        """Distribute MANPADS throughout defended area."""
        positions = []
        
        for i in range(count):
            # Random distribution with some clustering
            from ..misc.math_utils import generate_random_position_in_circle
            if i < count // 2:
                # Inner cluster (10-50% radius)
                x, _, z = generate_random_position_in_circle(
                    center_pos, radius * 0.5, radius * 0.1
                )
            else:
                # Outer perimeter (60-90% radius)
                x, _, z = generate_random_position_in_circle(
                    center_pos, radius * 0.9, radius * 0.6
                )
            
            try:
                y = self.terrain_helper.tc.get_terrain_height(x, z)
                positions.append((x, y, z))
            except Exception:
                positions.append((x, center_pos[1], z))
        
        return positions
    
    def _calculate_optimal_sector(
        self,
        system_pos: Tuple[float, float, float],
        center_pos: Tuple[float, float, float],
        primary_axis: float
    ) -> Tuple[float, float]:
        """Calculate optimal sector coverage for SAM system."""
        
        # Calculate bearing from system to center
        from ..misc.math_utils import calculate_bearing
        bearing_to_center = calculate_bearing(system_pos, center_pos)
        
        # Orient sector to cover both center and primary threat axis
        threat_bearing = primary_axis
        
        # Find middle point between center bearing and threat bearing
        angle_diff = (threat_bearing - bearing_to_center + 180) % 360 - 180
        optimal_center = (bearing_to_center + angle_diff / 2) % 360
        
        # SAM systems typically have 120° sector coverage
        sector_width = 120
        start_angle = (optimal_center - sector_width / 2) % 360
        end_angle = (optimal_center + sector_width / 2) % 360
        
        return (start_angle, end_angle)
    
    def _establish_support_networks(self, systems: List[ThreatSystem]) -> None:
        """Establish support relationships between systems."""
        
        radars = [s for s in systems if s.threat_type == ThreatType.EARLY_WARNING_RADAR]
        sams = [s for s in systems if s.threat_type in [ThreatType.LONG_RANGE_SAM, ThreatType.MEDIUM_RANGE_SAM]]
        
        # Link SAMs to nearest radar for target cueing
        for sam in sams:
            nearest_radar = min(radars, 
                              key=lambda r: self._distance_2d(sam.position, r.position),
                              default=None)
            if nearest_radar:
                sam.supporting_systems.append(nearest_radar.threat_id)
                nearest_radar.supporting_systems.append(sam.threat_id)
    
    def _distance_2d(self, pos1: Tuple[float, float, float], pos2: Tuple[float, float, float]) -> float:
        """Calculate 2D distance between positions."""
        dx = pos1[0] - pos2[0]
        dz = pos1[2] - pos2[2]
        return math.sqrt(dx*dx + dz*dz)
    
    def assess_threat_coverage(
        self,
        route_waypoints: List[Tuple[float, float, float]]
    ) -> Dict[str, Any]:
        """
        Assess threat coverage for a given route.
        
        Returns threat analysis with danger zones, safe corridors, and recommendations.
        """
        analysis = {
            "total_threat_exposure": 0.0,
            "danger_zones": [],
            "safe_segments": [],
            "recommended_altitude_changes": [],
            "threat_timeline": []
        }
        
        for i, waypoint in enumerate(route_waypoints):
            # Find all systems that can detect/engage this waypoint
            detecting_systems = []
            engaging_systems = []
            
            for system in self.threat_systems.values():
                if system.can_detect(waypoint, self.terrain_helper):
                    detecting_systems.append(system.threat_id)
                if system.can_engage(waypoint, self.terrain_helper):
                    engaging_systems.append(system.threat_id)
            
            # Calculate threat level for this waypoint
            threat_level = len(engaging_systems) * 0.3 + len(detecting_systems) * 0.1
            analysis["total_threat_exposure"] += threat_level
            
            # Record threat timeline
            analysis["threat_timeline"].append({
                "waypoint_index": i,
                "position": waypoint,
                "threat_level": threat_level,
                "detecting_systems": detecting_systems,
                "engaging_systems": engaging_systems
            })
            
            # Identify danger zones (high threat areas)
            if threat_level > 0.5:
                analysis["danger_zones"].append({
                    "waypoint_index": i,
                    "threat_level": threat_level,
                    "primary_threats": engaging_systems[:3]  # Top 3 threats
                })
            elif threat_level < 0.2:
                analysis["safe_segments"].append(i)
        
        return analysis
    
    def generate_threat_response(
        self,
        trigger_event: str,
        event_position: Tuple[float, float, float]
    ) -> List[Dict[str, Any]]:
        """
        Generate realistic threat response to mission events.
        
        Args:
            trigger_event: Type of event ("aircraft_detected", "sam_destroyed", etc.)
            event_position: Where the event occurred
            
        Returns:
            List of threat response actions
        """
        responses = []
        
        if trigger_event == "aircraft_detected":
            # Escalate alert state
            self._escalate_alert_state(AlertState.HIGH_ALERT)
            responses.append({
                "action": "alert_escalation", 
                "new_state": "high_alert",
                "description": "Air defense network on high alert"
            })
            
            # Activate nearby systems
            nearby_systems = self._find_systems_in_range(event_position, 50000)  # 50km
            for system in nearby_systems:
                if not system.active:
                    system.active = True
                    responses.append({
                        "action": "system_activation",
                        "system_id": system.threat_id,
                        "description": f"{system.threat_type.value} activated"
                    })
        
        elif trigger_event == "sam_destroyed":
            # Reposition mobile assets
            responses.append({
                "action": "tactical_repositioning",
                "description": "Mobile SAM systems repositioning"
            })
            
            # Increase CAP activity
            responses.append({
                "action": "fighter_scramble",
                "description": "Fighter aircraft scrambled for CAP"
            })
        
        elif trigger_event == "radar_jammed":
            # Switch to backup systems
            responses.append({
                "action": "backup_activation",
                "description": "Backup radar systems coming online"
            })
        
        return responses
    
    def _escalate_alert_state(self, new_state: AlertState) -> None:
        """Escalate network alert state."""
        if new_state.value > self.network_alert_state.value:
            self.network_alert_state = new_state
            
            # Update all systems
            for system in self.threat_systems.values():
                system.alert_state = new_state
    
    def _find_systems_in_range(
        self,
        position: Tuple[float, float, float],
        range_meters: float
    ) -> List[ThreatSystem]:
        """Find all threat systems within range of position."""
        nearby = []
        
        for system in self.threat_systems.values():
            distance = self._distance_2d(position, system.position)
            if distance <= range_meters:
                nearby.append(system)
        
        return nearby
    
    def get_network_status(self) -> Dict[str, Any]:
        """Get comprehensive network status."""
        active_systems = sum(1 for s in self.threat_systems.values() if s.active)
        total_systems = len(self.threat_systems)
        
        system_counts = {}
        for system in self.threat_systems.values():
            sys_type = system.threat_type.value
            system_counts[sys_type] = system_counts.get(sys_type, 0) + 1
        
        return {
            "alert_state": self.network_alert_state.value,
            "active_systems": active_systems,
            "total_systems": total_systems,
            "readiness": active_systems / total_systems if total_systems > 0 else 0,
            "system_breakdown": system_counts,
            "coverage_assessment": self._assess_overall_coverage()
        }
    
    def _assess_overall_coverage(self) -> str:
        """Assess overall network coverage quality."""
        if not self.threat_systems:
            return "no_coverage"
        
        active_ratio = sum(1 for s in self.threat_systems.values() if s.active) / len(self.threat_systems)
        
        if active_ratio > 0.8:
            return "excellent"
        elif active_ratio > 0.6:
            return "good"
        elif active_ratio > 0.4:
            return "moderate"
        else:
            return "poor"