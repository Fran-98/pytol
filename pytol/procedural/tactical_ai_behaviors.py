"""
Tactical AI Behaviors System for realistic unit coordination and movement.

This system creates intelligent AI behaviors that:
- Generate realistic patrol patterns based on military doctrine
- Coordinate between different unit types (air, ground, naval)
- Respond dynamically to threats and changing situations
- Use terrain-aware movement and positioning
- Implement proper military tactics and formations
- Create believable engagement patterns and ROE
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any
from enum import Enum
import time

from pytol.misc.math_utils import calculate_3d_distance

from pytol.terrain.mission_terrain_helper import MissionTerrainHelper
# Import consolidated utilities
from ..misc.math_utils import generate_random_angle


class UnitType(Enum):
    """Types of military units."""
    FIGHTER = "fighter"                    # Air superiority fighters
    ATTACK_AIRCRAFT = "attack_aircraft"    # Ground attack aircraft
    BOMBER = "bomber"                      # Strategic bombers
    HELICOPTER = "helicopter"              # Rotary wing aircraft
    TRANSPORT = "transport"                # Transport aircraft
    AWACS = "awacs"                       # Airborne early warning
    TANKER = "tanker"                     # Air refueling
    GROUND_VEHICLE = "ground_vehicle"      # Armored vehicles
    INFANTRY = "infantry"                  # Ground troops
    SAM_SITE = "sam_site"                 # Surface-to-air missiles
    RADAR = "radar"                       # Radar installations
    SHIP = "ship"                         # Naval vessels
    SUBMARINE = "submarine"               # Underwater vessels


class BehaviorState(Enum):
    """AI behavior states."""
    PATROL = "patrol"           # Normal patrol operations
    INVESTIGATE = "investigate" # Investigating unknown contact
    ENGAGE = "engage"          # Actively engaging targets
    EVADE = "evade"           # Evading threats
    RTB = "rtb"               # Return to base
    REARM = "rearm"           # Rearming/refueling
    FORMATION = "formation"    # Maintaining formation
    ESCORT = "escort"         # Escorting other units
    INTERCEPT = "intercept"   # Intercepting targets
    SEARCH = "search"         # Search and rescue/destroy
    DEFEND = "defend"         # Defensive operations
    SUPPORT = "support"       # Supporting other units


class ThreatLevel(Enum):
    """Threat assessment levels."""
    NONE = "none"           # No threats detected
    LOW = "low"            # Minor threats, maintain alertness
    MEDIUM = "medium"      # Moderate threats, increase readiness
    HIGH = "high"          # Significant threats, combat ready
    CRITICAL = "critical"   # Immediate danger, evasive action


class Formation(Enum):
    """Military formations."""
    LINE_ABREAST = "line_abreast"     # Side by side
    LINE_ASTERN = "line_astern"       # One behind the other
    VIC = "vic"                       # V formation
    FINGER_FOUR = "finger_four"       # Fighter finger-four
    DIAMOND = "diamond"               # Diamond formation
    ECHELON_LEFT = "echelon_left"     # Echelon left
    ECHELON_RIGHT = "echelon_right"   # Echelon right
    TRAIL = "trail"                   # Trail formation
    WEDGE = "wedge"                   # Wedge formation
    COMBAT_SPREAD = "combat_spread"   # Combat spread


@dataclass
class AIUnit:
    """An AI-controlled unit with behavioral parameters."""
    unit_id: str
    unit_type: UnitType
    position: Tuple[float, float, float]
    heading: float  # Degrees
    speed: float    # m/s
    altitude: float # AGL for aircraft
    
    # Behavioral state
    current_behavior: BehaviorState = BehaviorState.PATROL
    threat_level: ThreatLevel = ThreatLevel.NONE
    formation: Optional[Formation] = None
    formation_position: int = 0  # Position in formation
    
    # Waypoints and navigation
    waypoints: List[Tuple[float, float, float]] = field(default_factory=list)
    current_waypoint: int = 0
    patrol_area: Optional[Tuple[Tuple[float, float], float]] = None  # Center and radius
    
    # Tactical parameters
    engagement_range: float = 10000   # Maximum engagement range
    detection_range: float = 15000    # Maximum detection range
    comfort_altitude: float = 1000    # Preferred altitude AGL
    min_altitude: float = 100         # Minimum safe altitude
    max_altitude: float = 10000       # Service ceiling
    
    # Combat parameters
    fuel_level: float = 1.0          # 0-1 fuel remaining
    ammunition: Dict[str, int] = field(default_factory=dict)
    damage_level: float = 0.0        # 0-1 damage taken
    
    # AI behavior parameters
    aggressiveness: float = 0.5      # 0-1 how aggressive
    skill_level: float = 0.7         # 0-1 pilot skill
    reaction_time: float = 2.0       # Seconds to react
    communication_range: float = 50000  # Radio range
    
    # Relationships
    wing_leader: Optional[str] = None      # Leader unit ID
    wing_members: List[str] = field(default_factory=list)  # Wingman IDs
    escort_target: Optional[str] = None    # Unit being escorted
    
    # Mission parameters
    mission_time: float = 0.0        # Time on current mission
    last_contact_time: float = 0.0   # Last enemy contact
    home_base: Optional[Tuple[float, float, float]] = None
    
    # Internal state
    last_position_update: float = field(default_factory=time.time)
    behavior_timer: float = 0.0      # Time in current behavior
    decision_cooldown: float = 0.0   # Cooldown for major decisions


@dataclass
class TacticalSituation:
    """Current tactical situation assessment."""
    friendly_units: List[AIUnit]
    enemy_contacts: List[Dict[str, Any]]
    neutral_contacts: List[Dict[str, Any]]
    threats: List[Dict[str, Any]]
    no_fly_zones: List[Tuple[Tuple[float, float], float]]
    objectives: List[Dict[str, Any]]
    time_of_day: float = 12.0  # Hours (24-hour format)
    weather_conditions: Dict[str, Any] = field(default_factory=dict)


class TacticalAISystem:
    """
    Advanced tactical AI system for realistic military unit behaviors.
    
    Provides:
    - Realistic patrol patterns based on military doctrine
    - Dynamic threat response and engagement tactics
    - Formation flying and unit coordination
    - Terrain-aware movement and positioning
    - Multi-unit tactical decision making
    - Communication and coordination between units
    """
    
    def __init__(self, terrain_helper: MissionTerrainHelper):
        self.terrain_helper = terrain_helper
        self.units: Dict[str, AIUnit] = {}
        self.situation: TacticalSituation = TacticalSituation([], [], [], [], [], [])
        self.last_update_time = time.time()
        
        # Tactical parameters
        self.engagement_rules = self._initialize_engagement_rules()
        self.formation_definitions = self._initialize_formations()
        self.patrol_patterns = self._initialize_patrol_patterns()
        
    def add_unit(self, unit: AIUnit) -> None:
        """Add a unit to the tactical system."""
        self.units[unit.unit_id] = unit
        self.situation.friendly_units.append(unit)
        
        # Initialize unit with appropriate behavior
        self._initialize_unit_behavior(unit)
    
    def update_tactical_situation(self, delta_time: float) -> None:
        """Update the tactical situation and all unit behaviors."""
        
        current_time = time.time()
        
        # Update each unit
        for unit in self.units.values():
            self._update_unit_behavior(unit, delta_time)
            self._update_unit_position(unit, delta_time)
            self._update_unit_sensors(unit)
            self._update_unit_status(unit, delta_time)
        
        # Update formations
        self._update_formations(delta_time)
        
        # Process tactical decisions
        self._process_tactical_decisions()
        
        # Update threat assessment
        self._update_threat_assessment()
        
        self.last_update_time = current_time
    
    def _initialize_unit_behavior(self, unit: AIUnit) -> None:
        """Initialize appropriate behavior for unit type."""
        
        if unit.unit_type in [UnitType.FIGHTER, UnitType.ATTACK_AIRCRAFT]:
            # Fighters start with patrol behavior
            unit.current_behavior = BehaviorState.PATROL
            self._assign_patrol_area(unit)
            
        elif unit.unit_type == UnitType.AWACS:
            # AWACS maintains orbit patterns
            unit.current_behavior = BehaviorState.PATROL
            self._assign_orbit_pattern(unit)
            
        elif unit.unit_type == UnitType.TRANSPORT:
            # Transports follow flight plans
            unit.current_behavior = BehaviorState.FORMATION
            
        elif unit.unit_type in [UnitType.SAM_SITE, UnitType.RADAR]:
            # Ground units maintain defensive positions
            unit.current_behavior = BehaviorState.DEFEND
            
        # Set initial waypoints
        self._generate_initial_waypoints(unit)
    
    def _assign_patrol_area(self, unit: AIUnit) -> None:
        """Assign patrol area based on unit type and mission."""
        
        # For now, create a patrol area around the unit's starting position
        center = (unit.position[0], unit.position[2])
        
        if unit.unit_type == UnitType.FIGHTER:
            radius = 20000  # 20km patrol radius
        elif unit.unit_type == UnitType.ATTACK_AIRCRAFT:
            radius = 15000  # 15km patrol radius
        else:
            radius = 10000  # Default 10km radius
            
        unit.patrol_area = (center, radius)
    
    def _assign_orbit_pattern(self, unit: AIUnit) -> None:
        """Assign orbit pattern for AWACS and similar units."""
        
        # Create racetrack orbit pattern
        center = (unit.position[0], unit.position[2])
        radius = 25000  # 25km orbit radius
        unit.patrol_area = (center, radius)
        
        # Generate orbit waypoints
        orbit_waypoints = []
        for i in range(8):  # 8-point orbit
            angle = (2 * math.pi * i) / 8
            x = center[0] + radius * math.cos(angle)
            z = center[1] + radius * math.sin(angle)
            y = unit.comfort_altitude
            orbit_waypoints.append((x, y, z))
        
        unit.waypoints = orbit_waypoints
    
    def _generate_initial_waypoints(self, unit: AIUnit) -> None:
        """Generate initial waypoints for unit based on behavior."""
        
        if unit.current_behavior == BehaviorState.PATROL and unit.patrol_area:
            self._generate_patrol_waypoints(unit)
        elif unit.current_behavior == BehaviorState.DEFEND:
            # Defensive units stay in position
            unit.waypoints = [unit.position]
    
    def _generate_patrol_waypoints(self, unit: AIUnit) -> None:
        """Generate patrol waypoints within assigned area."""
        
        if not unit.patrol_area:
            return
            
        center, radius = unit.patrol_area
        waypoints = []
        
        # Generate 4-6 waypoints in patrol area
        num_waypoints = random.randint(4, 6)
        
        from ..misc.math_utils import generate_random_position_in_circle
        for i in range(num_waypoints):
            # Random position within patrol area (30-90% radius)
            x, z = generate_random_position_in_circle(center, radius * 0.9, radius * 0.3)
            
            # Get terrain-appropriate altitude
            y = self._get_safe_altitude(unit, x, z)
            
            waypoints.append((x, y, z))
        
        unit.waypoints = waypoints
        unit.current_waypoint = 0
    
    def _get_safe_altitude(self, unit: AIUnit, x: float, z: float) -> float:
        """Get safe altitude for unit at position."""
        
        try:
            terrain_height = self.terrain_helper.tc.get_terrain_height(x, z)
            
            if unit.unit_type in [UnitType.GROUND_VEHICLE, UnitType.INFANTRY]:
                return terrain_height + 2  # Just above ground
            elif unit.unit_type == UnitType.HELICOPTER:
                return terrain_height + random.uniform(50, 200)  # Low altitude
            else:
                # Fixed wing aircraft
                min_safe = terrain_height + unit.min_altitude
                return max(min_safe, unit.comfort_altitude)
                
        except Exception:
            return unit.comfort_altitude  # Fallback
    
    def _update_unit_behavior(self, unit: AIUnit, delta_time: float) -> None:
        """Update unit's behavioral state machine."""
        
        unit.behavior_timer += delta_time
        unit.decision_cooldown = max(0, unit.decision_cooldown - delta_time)
        
        # Check for behavior transitions
        if unit.decision_cooldown <= 0:
            new_behavior = self._evaluate_behavior_transition(unit)
            
            if new_behavior != unit.current_behavior:
                self._transition_to_behavior(unit, new_behavior)
                unit.decision_cooldown = unit.reaction_time
        
        # Execute current behavior
        self._execute_behavior(unit, delta_time)
    
    def _evaluate_behavior_transition(self, unit: AIUnit) -> BehaviorState:
        """Evaluate if unit should transition to new behavior."""
        
        current = unit.current_behavior
        
        # Critical situations override everything
        if unit.threat_level == ThreatLevel.CRITICAL:
            if unit.unit_type in [UnitType.FIGHTER, UnitType.ATTACK_AIRCRAFT]:
                return BehaviorState.EVADE
            else:
                return BehaviorState.RTB
        
        # Fuel/damage considerations
        if unit.fuel_level < 0.2 or unit.damage_level > 0.7:
            return BehaviorState.RTB
        
        # Threat-based transitions
        if unit.threat_level >= ThreatLevel.MEDIUM:
            if current == BehaviorState.PATROL:
                return BehaviorState.INVESTIGATE
            elif current == BehaviorState.INVESTIGATE:
                if unit.threat_level >= ThreatLevel.HIGH:
                    return BehaviorState.ENGAGE
        
        # Formation requirements
        if unit.wing_leader and current != BehaviorState.FORMATION:
            leader = self.units.get(unit.wing_leader)
            if leader and self._should_maintain_formation(unit, leader):
                return BehaviorState.FORMATION
        
        # Return to patrol if no other priorities
        if current in [BehaviorState.INVESTIGATE, BehaviorState.ENGAGE]:
            if unit.threat_level <= ThreatLevel.LOW and unit.behavior_timer > 30:
                return BehaviorState.PATROL
        
        return current  # No change
    
    def _transition_to_behavior(self, unit: AIUnit, new_behavior: BehaviorState) -> None:
        """Transition unit to new behavior state."""
        
        unit.current_behavior = new_behavior
        unit.behavior_timer = 0.0
        
        # Behavior-specific initialization
        if new_behavior == BehaviorState.PATROL:
            self._generate_patrol_waypoints(unit)
            
        elif new_behavior == BehaviorState.RTB:
            if unit.home_base:
                unit.waypoints = [unit.home_base]
                unit.current_waypoint = 0
                
        elif new_behavior == BehaviorState.INTERCEPT:
            # Generate intercept course
            self._generate_intercept_waypoints(unit)
            
        elif new_behavior == BehaviorState.FORMATION:
            # Clear individual waypoints, follow leader
            unit.waypoints = []
    
    def _execute_behavior(self, unit: AIUnit, delta_time: float) -> None:
        """Execute current behavior logic."""
        
        behavior = unit.current_behavior
        
        if behavior == BehaviorState.PATROL:
            self._execute_patrol_behavior(unit, delta_time)
            
        elif behavior == BehaviorState.INVESTIGATE:
            self._execute_investigate_behavior(unit, delta_time)
            
        elif behavior == BehaviorState.ENGAGE:
            self._execute_engage_behavior(unit, delta_time)
            
        elif behavior == BehaviorState.EVADE:
            self._execute_evade_behavior(unit, delta_time)
            
        elif behavior == BehaviorState.FORMATION:
            self._execute_formation_behavior(unit, delta_time)
            
        elif behavior == BehaviorState.INTERCEPT:
            self._execute_intercept_behavior(unit, delta_time)
            
        elif behavior == BehaviorState.RTB:
            self._execute_rtb_behavior(unit, delta_time)
            
        elif behavior == BehaviorState.DEFEND:
            self._execute_defend_behavior(unit, delta_time)
    
    def _execute_patrol_behavior(self, unit: AIUnit, delta_time: float) -> None:
        """Execute patrol behavior - follow waypoints and scan for threats."""
        
        # Navigate to waypoints
        if unit.waypoints and len(unit.waypoints) > 0:
            target_waypoint = unit.waypoints[unit.current_waypoint]
            
            # Check if reached current waypoint
            distance_to_waypoint = calculate_3d_distance(unit.position, target_waypoint)
            
            if distance_to_waypoint < 500:  # 500m tolerance
                # Move to next waypoint
                unit.current_waypoint = (unit.current_waypoint + 1) % len(unit.waypoints)
                
                # Occasionally generate new patrol waypoints
                if random.random() < 0.1:  # 10% chance per waypoint
                    self._generate_patrol_waypoints(unit)
        
        # Patrol-specific behaviors
        if unit.unit_type == UnitType.AWACS:
            # Maintain constant altitude and speed
            unit.speed = 200  # Typical AWACS cruise speed
        elif unit.unit_type == UnitType.FIGHTER:
            # Vary speed and altitude slightly
            unit.speed = 250 + random.uniform(-50, 50)
            altitude_variation = random.uniform(-100, 100)
            unit.altitude = max(unit.min_altitude, unit.comfort_altitude + altitude_variation)
    
    def _execute_investigate_behavior(self, unit: AIUnit, delta_time: float) -> None:
        """Execute investigate behavior - move toward unknown contacts."""
        
        # Find nearest unknown contact
        nearest_contact = self._find_nearest_unknown_contact(unit)
        
        if nearest_contact:
            # Generate waypoint toward contact
            contact_pos = (nearest_contact['x'], nearest_contact['y'], nearest_contact['z'])
            unit.waypoints = [contact_pos]
            unit.current_waypoint = 0
            
            # Increase speed
            unit.speed = min(unit.speed * 1.2, 400)  # 20% speed increase, max 400 m/s
            
            # Check if close enough to identify
            distance = calculate_3d_distance(unit.position, contact_pos)
            if distance < 2000:  # 2km identification range
                # Contact identified, update threat assessment
                self._identify_contact(unit, nearest_contact)
    
    def _execute_engage_behavior(self, unit: AIUnit, delta_time: float) -> None:
        """Execute engage behavior - attack hostile targets."""
        
        # Find highest priority target
        target = self._find_priority_target(unit)
        
        if target:
            target_pos = (target['x'], target['y'], target['z'])
            
            # Calculate engagement geometry
            distance = calculate_3d_distance(unit.position, target_pos)
            
            if distance <= unit.engagement_range:
                # In range - execute attack
                self._execute_attack(unit, target)
            else:
                # Close distance
                approach_point = self._calculate_approach_point(unit, target)
                unit.waypoints = [approach_point]
                unit.current_waypoint = 0
                
                # Increase speed for intercept
                unit.speed = min(unit.speed * 1.5, 500)
        else:
            # No targets, return to patrol
            unit.current_behavior = BehaviorState.PATROL
    
    def _execute_evade_behavior(self, unit: AIUnit, delta_time: float) -> None:
        """Execute evasive behavior - avoid threats."""
        
        # Find immediate threats
        threats = self._find_immediate_threats(unit)
        
        if threats:
            # Calculate evasive maneuver
            evasion_point = self._calculate_evasion_point(unit, threats)
            unit.waypoints = [evasion_point]
            unit.current_waypoint = 0
            
            # Maximum speed
            unit.speed = 600  # Emergency speed
            
            # Deploy countermeasures
            self._deploy_countermeasures(unit)
        else:
            # Threats cleared, assess situation
            if unit.fuel_level > 0.3 and unit.damage_level < 0.5:
                unit.current_behavior = BehaviorState.PATROL
            else:
                unit.current_behavior = BehaviorState.RTB
    
    def _execute_formation_behavior(self, unit: AIUnit, delta_time: float) -> None:
        """Execute formation flying behavior."""
        
        if not unit.wing_leader:
            return
            
        leader = self.units.get(unit.wing_leader)
        if not leader:
            return
        
        # Calculate formation position
        formation_pos = self._calculate_formation_position(unit, leader)
        
        # Set waypoint to formation position
        unit.waypoints = [formation_pos]
        unit.current_waypoint = 0
        
        # Match leader's speed and altitude
        unit.speed = leader.speed * random.uniform(0.95, 1.05)
        unit.altitude = leader.altitude + self._get_formation_altitude_offset(unit)
    
    def _execute_intercept_behavior(self, unit: AIUnit, delta_time: float) -> None:
        """Execute intercept behavior - intercept specific targets."""
        
        # Similar to engage but with different geometry calculations
        target = self._find_intercept_target(unit)
        
        if target:
            intercept_point = self._calculate_intercept_point(unit, target)
            unit.waypoints = [intercept_point]
            unit.current_waypoint = 0
            
            # High speed intercept
            unit.speed = 500
    
    def _execute_rtb_behavior(self, unit: AIUnit, delta_time: float) -> None:
        """Execute return to base behavior."""
        
        if unit.home_base:
            distance_to_base = calculate_3d_distance(unit.position, unit.home_base)
            
            if distance_to_base < 1000:  # Reached base
                # Land/dock procedure
                unit.current_behavior = BehaviorState.REARM
                unit.fuel_level = 1.0
                unit.damage_level = 0.0
                # Restock ammunition
                unit.ammunition = {"missiles": 4, "cannon": 500}
            else:
                # Navigate to base
                unit.waypoints = [unit.home_base]
                unit.current_waypoint = 0
                
                # Efficient cruise speed
                unit.speed = 300
    
    def _execute_defend_behavior(self, unit: AIUnit, delta_time: float) -> None:
        """Execute defensive behavior for static units."""
        
        # Scan for threats
        threats = self._scan_for_threats(unit)
        
        if threats and unit.unit_type == UnitType.SAM_SITE:
            # Engage threats within range
            for threat in threats:
                distance = calculate_3d_distance(unit.position, 
                                                     (threat['x'], threat['y'], threat['z']))
                if distance <= unit.engagement_range:
                    self._execute_sam_attack(unit, threat)
    
    def _update_unit_position(self, unit: AIUnit, delta_time: float) -> None:
        """Update unit position based on movement."""
        
        if not unit.waypoints:
            return
            
        current_time = time.time()
        actual_delta = current_time - unit.last_position_update
        unit.last_position_update = current_time
        
        # Get target waypoint
        if unit.current_waypoint < len(unit.waypoints):
            target = unit.waypoints[unit.current_waypoint]
            
            # Calculate movement vector
            dx = target[0] - unit.position[0]
            dy = target[1] - unit.position[1]
            dz = target[2] - unit.position[2]
            
            distance = math.sqrt(dx*dx + dy*dy + dz*dz)
            
            if distance > 1.0:  # Avoid division by zero
                # Normalize direction
                dx /= distance
                dy /= distance
                dz /= distance
                
                # Apply movement
                movement_distance = unit.speed * actual_delta
                movement_distance = min(movement_distance, distance)
                
                new_x = unit.position[0] + dx * movement_distance
                new_y = unit.position[1] + dy * movement_distance
                new_z = unit.position[2] + dz * movement_distance
                
                # Terrain collision avoidance for aircraft
                if unit.unit_type not in [UnitType.GROUND_VEHICLE, UnitType.INFANTRY]:
                    try:
                        terrain_height = self.terrain_helper.tc.get_terrain_height(new_x, new_z)
                        min_safe_altitude = terrain_height + unit.min_altitude
                        if new_y < min_safe_altitude:
                            new_y = min_safe_altitude
                    except Exception:
                        pass
                
                unit.position = (new_x, new_y, new_z)
                
                # Update heading
                from ..misc.math_utils import calculate_bearing
                unit.heading = calculate_bearing(unit.position, target)
    
    def _update_unit_sensors(self, unit: AIUnit) -> None:
        """Update unit's sensor contacts and threat detection."""
        
        # Simplified sensor simulation
        detected_contacts = []
        
        # Check all other units in detection range
        for other_unit in self.units.values():
            if other_unit.unit_id == unit.unit_id:
                continue
                
            distance = calculate_3d_distance(unit.position, other_unit.position)
            
            if distance <= unit.detection_range:
                # Detection probability based on various factors
                detection_prob = self._calculate_detection_probability(unit, other_unit, distance)
                
                if random.random() < detection_prob:
                    contact = {
                        'id': other_unit.unit_id,
                        'x': other_unit.position[0],
                        'y': other_unit.position[1],
                        'z': other_unit.position[2],
                        'type': other_unit.unit_type.value,
                        'heading': other_unit.heading,
                        'speed': other_unit.speed,
                        'confidence': detection_prob,
                        'time': time.time()
                    }
                    detected_contacts.append(contact)
        
        # Update threat level based on contacts
        self._update_unit_threat_level(unit, detected_contacts)
    
    def _update_unit_status(self, unit: AIUnit, delta_time: float) -> None:
        """Update unit status (fuel, ammunition, etc.)."""
        
        # Fuel consumption
        if unit.unit_type not in [UnitType.GROUND_VEHICLE, UnitType.SAM_SITE, UnitType.RADAR]:
            fuel_consumption_rate = self._calculate_fuel_consumption(unit)
            unit.fuel_level = max(0, unit.fuel_level - fuel_consumption_rate * delta_time)
        
        # Mission time
        unit.mission_time += delta_time
    
    def _calculate_fuel_consumption(self, unit: AIUnit) -> float:
        """Calculate fuel consumption rate per second."""
        
        base_consumption = {
            UnitType.FIGHTER: 0.0001,      # 0.01% per second at cruise
            UnitType.ATTACK_AIRCRAFT: 0.00008,
            UnitType.BOMBER: 0.00005,
            UnitType.HELICOPTER: 0.00015,
            UnitType.TRANSPORT: 0.00006,
            UnitType.AWACS: 0.00004,
            UnitType.TANKER: 0.00005
        }.get(unit.unit_type, 0.0001)
        
        # Speed affects consumption
        speed_factor = (unit.speed / 300) ** 1.5  # Nonlinear relationship
        
        # Behavior affects consumption
        behavior_multiplier = {
            BehaviorState.PATROL: 1.0,
            BehaviorState.ENGAGE: 2.0,     # Combat power settings
            BehaviorState.EVADE: 3.0,      # Afterburner
            BehaviorState.INTERCEPT: 2.5,
            BehaviorState.RTB: 0.8         # Economy cruise
        }.get(unit.current_behavior, 1.0)
        
        return base_consumption * speed_factor * behavior_multiplier
    
    # Formation management methods
    def create_formation(
        self,
        leader_id: str,
        wingman_ids: List[str],
        formation_type: Formation
    ) -> bool:
        """Create a formation with specified leader and wingmen."""
        
        leader = self.units.get(leader_id)
        if not leader:
            return False
        
        # Set up formation relationships
        leader.wing_members = wingman_ids
        leader.formation = formation_type
        
        for i, wingman_id in enumerate(wingman_ids):
            wingman = self.units.get(wingman_id)
            if wingman:
                wingman.wing_leader = leader_id
                wingman.formation = formation_type
                wingman.formation_position = i + 1
                wingman.current_behavior = BehaviorState.FORMATION
        
        return True
    
    def _update_formations(self, delta_time: float) -> None:
        """Update all formations."""
        
        # Find all formation leaders
        leaders = [unit for unit in self.units.values() if unit.wing_members]
        
        for leader in leaders:
            # Update formation cohesion
            self._maintain_formation_cohesion(leader)
    
    def _calculate_formation_position(self, wingman: AIUnit, leader: AIUnit) -> Tuple[float, float, float]:
        """Calculate wingman's position in formation."""
        
        if not wingman.formation:
            return leader.position
        
        # Formation-specific positioning
        if wingman.formation == Formation.FINGER_FOUR:
            return self._calculate_finger_four_position(wingman, leader)
        elif wingman.formation == Formation.VIC:
            return self._calculate_vic_position(wingman, leader)
        elif wingman.formation == Formation.LINE_ABREAST:
            return self._calculate_line_abreast_position(wingman, leader)
        else:
            # Default trail formation
            return self._calculate_trail_position(wingman, leader)
    
    def _calculate_finger_four_position(self, wingman: AIUnit, leader: AIUnit) -> Tuple[float, float, float]:
        """Calculate position for finger-four formation."""
        
        # Standard finger-four spacing
        lateral_spacing = 500  # meters
        longitudinal_spacing = 300  # meters
        
        leader_heading_rad = math.radians(leader.heading)
        
        # Position based on formation position
        if wingman.formation_position == 1:  # #2, right wing
            offset_x = lateral_spacing * math.cos(leader_heading_rad + math.pi/2)
            offset_z = lateral_spacing * math.sin(leader_heading_rad + math.pi/2)
            offset_y = -50  # Slightly lower
        elif wingman.formation_position == 2:  # #3, left wing
            offset_x = lateral_spacing * math.cos(leader_heading_rad - math.pi/2)
            offset_z = lateral_spacing * math.sin(leader_heading_rad - math.pi/2)
            offset_y = -50
        elif wingman.formation_position == 3:  # #4, tail-end charlie
            offset_x = -longitudinal_spacing * math.cos(leader_heading_rad)
            offset_z = -longitudinal_spacing * math.sin(leader_heading_rad)
            offset_y = 0
        else:
            offset_x = offset_z = offset_y = 0
        
        return (
            leader.position[0] + offset_x,
            leader.position[1] + offset_y,
            leader.position[2] + offset_z
        )
    
    def _calculate_vic_position(self, wingman: AIUnit, leader: AIUnit) -> Tuple[float, float, float]:
        """Calculate position for V formation."""
        
        spacing = 400  # meters
        leader_heading_rad = math.radians(leader.heading)
        
        # V formation positions
        if wingman.formation_position == 1:  # Right wing
            angle_offset = math.pi/6  # 30 degrees
            offset_x = spacing * math.cos(leader_heading_rad + angle_offset)
            offset_z = spacing * math.sin(leader_heading_rad + angle_offset)
        elif wingman.formation_position == 2:  # Left wing
            angle_offset = -math.pi/6  # -30 degrees
            offset_x = spacing * math.cos(leader_heading_rad + angle_offset)
            offset_z = spacing * math.sin(leader_heading_rad + angle_offset)
        else:
            offset_x = offset_z = 0
        
        return (
            leader.position[0] + offset_x,
            leader.position[1] + 0,  # Same altitude
            leader.position[2] + offset_z
        )
    
    def _calculate_line_abreast_position(self, wingman: AIUnit, leader: AIUnit) -> Tuple[float, float, float]:
        """Calculate position for line abreast formation."""
        
        spacing = 600  # meters
        leader_heading_rad = math.radians(leader.heading)
        
        # Line abreast - perpendicular to heading
        perpendicular_angle = leader_heading_rad + math.pi/2
        
        # Alternate left and right
        side = 1 if wingman.formation_position % 2 == 1 else -1
        position_multiplier = (wingman.formation_position + 1) // 2
        
        offset_x = side * spacing * position_multiplier * math.cos(perpendicular_angle)
        offset_z = side * spacing * position_multiplier * math.sin(perpendicular_angle)
        
        return (
            leader.position[0] + offset_x,
            leader.position[1] + 0,
            leader.position[2] + offset_z
        )
    
    def _calculate_trail_position(self, wingman: AIUnit, leader: AIUnit) -> Tuple[float, float, float]:
        """Calculate position for trail formation."""
        
        spacing = 500  # meters
        leader_heading_rad = math.radians(leader.heading)
        
        # Trail behind leader
        trail_distance = spacing * wingman.formation_position
        
        offset_x = -trail_distance * math.cos(leader_heading_rad)
        offset_z = -trail_distance * math.sin(leader_heading_rad)
        
        return (
            leader.position[0] + offset_x,
            leader.position[1] + random.uniform(-20, 20),  # Slight altitude variation
            leader.position[2] + offset_z
        )
    
    # Utility methods
    def _calculate_detection_probability(self, observer: AIUnit, target: AIUnit, distance: float) -> float:
        """Calculate probability of detecting target."""
        
        base_prob = 1.0 - (distance / observer.detection_range)
        
        # Observer skill affects detection
        skill_factor = 0.5 + (observer.skill_level * 0.5)
        
        # Target type affects detection
        stealth_factor = {
            UnitType.FIGHTER: 0.8,
            UnitType.BOMBER: 1.2,
            UnitType.HELICOPTER: 0.6,
            UnitType.TRANSPORT: 1.0
        }.get(target.unit_type, 1.0)
        
        return max(0, min(1, base_prob * skill_factor * stealth_factor))
    
    # Placeholder methods for complex behaviors
    def _initialize_engagement_rules(self) -> Dict[str, Any]:
        """Initialize rules of engagement."""
        return {
            "weapons_free": True,
            "identify_before_engage": True,
            "minimum_range": 1000,
            "maximum_range": 10000
        }
    
    def _initialize_formations(self) -> Dict[Formation, Dict[str, Any]]:
        """Initialize formation definitions."""
        return {
            Formation.FINGER_FOUR: {"max_members": 4, "spacing": 500},
            Formation.VIC: {"max_members": 3, "spacing": 400},
            Formation.LINE_ABREAST: {"max_members": 6, "spacing": 600}
        }
    
    def _initialize_patrol_patterns(self) -> Dict[str, Any]:
        """Initialize patrol pattern definitions."""
        return {
            "cap": {"altitude": 8000, "speed": 250, "pattern": "orbit"},
            "cas": {"altitude": 2000, "speed": 200, "pattern": "racetrack"},
            "recce": {"altitude": 5000, "speed": 300, "pattern": "line"}
        }
    
    # Additional helper methods (simplified implementations)
    def _should_maintain_formation(self, unit: AIUnit, leader: AIUnit) -> bool:
        """Check if unit should maintain formation."""
        distance = calculate_3d_distance(unit.position, leader.position)
        return distance < 2000 and leader.current_behavior != BehaviorState.ENGAGE
    
    def _find_nearest_unknown_contact(self, unit: AIUnit) -> Optional[Dict[str, Any]]:
        """Find nearest unknown contact."""
        # Simplified - would integrate with actual sensor system
        return None
    
    def _identify_contact(self, unit: AIUnit, contact: Dict[str, Any]) -> None:
        """Identify a contact as friend, foe, or neutral."""
        # Simplified identification logic
        pass
    
    def _find_priority_target(self, unit: AIUnit) -> Optional[Dict[str, Any]]:
        """Find highest priority target for engagement."""
        # Simplified target prioritization
        return None
    
    def _execute_attack(self, unit: AIUnit, target: Dict[str, Any]) -> None:
        """Execute attack on target."""
        # Simplified attack execution
        if "missiles" in unit.ammunition and unit.ammunition["missiles"] > 0:
            unit.ammunition["missiles"] -= 1
    
    def _calculate_approach_point(self, unit: AIUnit, target: Dict[str, Any]) -> Tuple[float, float, float]:
        """Calculate optimal approach point for attack."""
        # Simplified approach calculation
        return (target['x'], target['y'], target['z'])
    
    def _find_immediate_threats(self, unit: AIUnit) -> List[Dict[str, Any]]:
        """Find immediate threats to unit."""
        return []
    
    def _calculate_evasion_point(self, unit: AIUnit, threats: List[Dict[str, Any]]) -> Tuple[float, float, float]:
        """Calculate evasion point."""
        # Simple evasion - move perpendicular to threats
        if threats:
            threat = threats[0]
            # Move 90 degrees from threat bearing
            threat_bearing = math.atan2(
                threat['z'] - unit.position[2],
                threat['x'] - unit.position[0]
            )
            evasion_bearing = threat_bearing + math.pi/2
            evasion_distance = 5000
            
            return (
                unit.position[0] + evasion_distance * math.cos(evasion_bearing),
                unit.position[1] + 500,  # Climb
                unit.position[2] + evasion_distance * math.sin(evasion_bearing)
            )
        return unit.position
    
    def _deploy_countermeasures(self, unit: AIUnit) -> None:
        """Deploy countermeasures."""
        # Simplified countermeasure deployment
        pass
    
    def _get_formation_altitude_offset(self, unit: AIUnit) -> float:
        """Get altitude offset for formation position."""
        return unit.formation_position * 50  # 50m per position
    
    def _find_intercept_target(self, unit: AIUnit) -> Optional[Dict[str, Any]]:
        """Find target for intercept."""
        return None
    
    def _calculate_intercept_point(self, unit: AIUnit, target: Dict[str, Any]) -> Tuple[float, float, float]:
        """Calculate intercept point."""
        return (target['x'], target['y'], target['z'])
    
    def _scan_for_threats(self, unit: AIUnit) -> List[Dict[str, Any]]:
        """Scan for threats."""
        return []
    
    def _execute_sam_attack(self, unit: AIUnit, threat: Dict[str, Any]) -> None:
        """Execute SAM attack."""
        if "missiles" in unit.ammunition and unit.ammunition["missiles"] > 0:
            unit.ammunition["missiles"] -= 1
    
    def _generate_intercept_waypoints(self, unit: AIUnit) -> None:
        """Generate waypoints for intercept mission."""
        # Simplified intercept waypoint generation
        pass
    
    def _update_unit_threat_level(self, unit: AIUnit, contacts: List[Dict[str, Any]]) -> None:
        """Update unit's threat level based on contacts."""
        if not contacts:
            unit.threat_level = ThreatLevel.NONE
        elif len(contacts) == 1:
            unit.threat_level = ThreatLevel.LOW
        elif len(contacts) <= 3:
            unit.threat_level = ThreatLevel.MEDIUM
        else:
            unit.threat_level = ThreatLevel.HIGH
    
    def _maintain_formation_cohesion(self, leader: AIUnit) -> None:
        """Maintain formation cohesion."""
        # Check if wingmen are maintaining position
        for wingman_id in leader.wing_members:
            wingman = self.units.get(wingman_id)
            if wingman:
                distance = calculate_3d_distance(wingman.position, leader.position)
                if distance > 1500:  # Formation is breaking up
                    wingman.current_behavior = BehaviorState.FORMATION
    
    def _process_tactical_decisions(self) -> None:
        """Process high-level tactical decisions."""
        # Simplified tactical decision making
        pass
    
    def _update_threat_assessment(self) -> None:
        """Update overall threat assessment."""
        # Simplified threat assessment
        pass
    
    def get_unit_status_report(self, unit_id: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive status report for unit."""
        
        unit = self.units.get(unit_id)
        if not unit:
            return None
        
        return {
            "unit_id": unit.unit_id,
            "unit_type": unit.unit_type.value,
            "position": unit.position,
            "heading": unit.heading,
            "speed": unit.speed,
            "altitude": unit.altitude,
            "behavior": unit.current_behavior.value,
            "threat_level": unit.threat_level.value,
            "formation": unit.formation.value if unit.formation else None,
            "fuel_level": unit.fuel_level,
            "damage_level": unit.damage_level,
            "mission_time": unit.mission_time,
            "waypoints_remaining": len(unit.waypoints) - unit.current_waypoint,
            "wing_leader": unit.wing_leader,
            "wing_members": unit.wing_members
        }
    
    def get_tactical_overview(self) -> Dict[str, Any]:
        """Get overview of tactical situation."""
        
        behavior_counts = {}
        threat_counts = {}
        formation_counts = {}
        
        for unit in self.units.values():
            # Count behaviors
            behavior = unit.current_behavior.value
            behavior_counts[behavior] = behavior_counts.get(behavior, 0) + 1
            
            # Count threat levels
            threat = unit.threat_level.value
            threat_counts[threat] = threat_counts.get(threat, 0) + 1
            
            # Count formations
            if unit.formation:
                formation = unit.formation.value
                formation_counts[formation] = formation_counts.get(formation, 0) + 1
        
        return {
            "total_units": len(self.units),
            "behavior_distribution": behavior_counts,
            "threat_distribution": threat_counts,
            "formation_distribution": formation_counts,
            "active_formations": len([u for u in self.units.values() if u.wing_members])
        }
