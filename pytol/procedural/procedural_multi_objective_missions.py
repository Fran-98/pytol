"""
Procedural Multi-Objective Mission Generator for living battlefield scenarios.

This system creates complex, multi-layered missions that:
- Generate interconnected primary and secondary objectives
- Create coordinated allied operations running simultaneously
- Populate the battlefield with background activities and traffic
- Generate dynamic mission flow with branching possibilities
- Create realistic military operations with multiple moving parts
- Ensure objectives complement each other strategically
- Generate appropriate force packages for each objective
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any
from enum import Enum

from pytol.terrain.mission_terrain_helper import MissionTerrainHelper
# Import consolidated utilities
from ..misc.math_utils import generate_random_angle


class ObjectivePriority(Enum):
    """Objective priority levels."""
    PRIMARY = "primary"       # Must complete for mission success
    SECONDARY = "secondary"   # Important but optional
    TERTIARY = "tertiary"     # Nice to have
    BACKGROUND = "background" # Ongoing allied operations
    EMERGENT = "emergent"     # Dynamically generated during mission


class ObjectiveType(Enum):
    """Types of mission objectives."""
    # Combat Objectives
    CAP = "cap"                           # Combat Air Patrol
    STRIKE = "strike"                     # Precision strike
    CAS = "cas"                          # Close Air Support
    SEAD = "sead"                        # Suppression of Enemy Air Defenses
    INTERDICTION = "interdiction"         # Air interdiction
    OCA = "oca"                          # Offensive Counter Air
    DCA = "dca"                          # Defensive Counter Air
    
    # Support Objectives
    ESCORT = "escort"                     # Escort friendly aircraft
    TANKER_SUPPORT = "tanker_support"     # Air refueling operations
    AWACS_SUPPORT = "awacs_support"       # Airborne early warning
    TRANSPORT = "transport"               # Transport/cargo missions
    MEDEVAC = "medevac"                  # Medical evacuation
    CSAR = "csar"                        # Combat Search and Rescue
    
    # Reconnaissance
    RECCE = "recce"                      # Reconnaissance
    SURVEILLANCE = "surveillance"         # Area surveillance
    BDA = "bda"                          # Battle Damage Assessment
    
    # Specialized
    ANTI_SHIP = "anti_ship"              # Anti-ship warfare
    MINE_LAYING = "mine_laying"          # Naval mining
    EW = "electronic_warfare"            # Electronic warfare
    TRAINING = "training"                # Training exercise


class OperationPhase(Enum):
    """Phases of complex operations."""
    PREPARATION = "preparation"       # Pre-mission setup
    INGRESS = "ingress"              # Entry into target area
    EXECUTION = "execution"          # Primary mission execution  
    EGRESS = "egress"               # Exit from target area
    RECOVERY = "recovery"           # Post-mission recovery
    CONTINGENCY = "contingency"     # Emergency procedures


class AlliedActivity(Enum):
    """Types of allied background activities."""
    ROUTINE_PATROL = "routine_patrol"         # Normal patrol operations
    LOGISTICS_CONVOY = "logistics_convoy"     # Supply convoys
    TRAINING_FLIGHT = "training_flight"       # Training operations
    MAINTENANCE_TEST = "maintenance_test"     # Aircraft test flights
    DIPLOMATIC_FLIGHT = "diplomatic_flight"   # VIP transport
    CARGO_DELIVERY = "cargo_delivery"        # Cargo operations
    MEDEVAC_STANDBY = "medevac_standby"      # Medical standby
    TANKER_ORBIT = "tanker_orbit"            # Refueling orbit
    AWACS_ORBIT = "awacs_orbit"              # AWACS patrol
    FERRY_FLIGHT = "ferry_flight"            # Aircraft repositioning
    BORDER_PATROL = "border_patrol"          # Border security
    FISHERY_PATROL = "fishery_patrol"        # Maritime patrol


@dataclass
class MissionObjective:
    """A single mission objective with all parameters."""
    objective_id: str
    objective_type: ObjectiveType
    priority: ObjectivePriority
    
    # Location and target information
    target_position: Tuple[float, float, float]
    target_area_radius: float = 1000  # meters
    target_description: str = ""
    target_type: str = "unknown"
    
    # Timing
    start_time: float = 0.0           # Mission time to start (minutes)
    duration: float = 30.0            # Duration in minutes
    deadline: Optional[float] = None  # Hard deadline
    window_start: Optional[float] = None  # Time window start
    window_end: Optional[float] = None    # Time window end
    
    # Requirements and constraints
    required_aircraft_types: List[str] = field(default_factory=list)
    minimum_aircraft: int = 1
    maximum_aircraft: int = 4
    required_weapons: List[str] = field(default_factory=list)
    required_equipment: List[str] = field(default_factory=list)
    
    # Dependencies
    prerequisite_objectives: List[str] = field(default_factory=list)
    unlocks_objectives: List[str] = field(default_factory=list)
    conflicts_with: List[str] = field(default_factory=list)
    
    # Success criteria
    success_conditions: List[Dict[str, Any]] = field(default_factory=list)
    failure_conditions: List[Dict[str, Any]] = field(default_factory=list)
    
    # Allied coordination
    coordinated_activities: List[str] = field(default_factory=list)
    supporting_units: List[str] = field(default_factory=list)
    
    # Status
    status: str = "pending"  # pending, active, completed, failed, cancelled
    completion_percentage: float = 0.0
    assigned_units: List[str] = field(default_factory=list)


@dataclass
class AlliedOperation:
    """Background allied operation to populate the battlefield."""
    operation_id: str
    activity_type: AlliedActivity
    
    # Route and timing
    waypoints: List[Tuple[float, float, float]]
    start_time: float
    duration: float
    
    # Units involved
    unit_types: List[str]
    unit_count: int
    repeat_interval: Optional[float] = None  # For recurring activities
    formation: str = "loose"
    
    # Behavior
    speed: float = 200  # m/s
    altitude: float = 1000  # AGL
    radio_chatter: bool = True
    visible_to_player: bool = True
    
    # Mission interaction
    can_be_tasked: bool = False      # Can be given emergency tasks
    priority_level: int = 1          # 1-10, higher = more important
    emergency_response: bool = False  # Can respond to emergencies
    
    # Status
    current_waypoint: int = 0
    active: bool = True
    completion_status: float = 0.0


@dataclass
class DynamicEncounter:
    """Dynamic military encounters and events."""
    encounter_id: str
    encounter_type: str  # enemy_patrol, unknown_contact, distress_call, etc.
    
    # Trigger conditions
    trigger_conditions: List[Dict[str, Any]] = field(default_factory=list)
    trigger_time: Optional[float] = None  # Specific time trigger
    trigger_area: Optional[Tuple[Tuple[float, float], float]] = None  # Area trigger
    
    # Encounter details
    enemy_units: List[Dict[str, Any]] = field(default_factory=list)
    encounter_position: Optional[Tuple[float, float, float]] = None
    threat_level: str = "medium"  # low, medium, high, critical
    
    # Event progression
    event_phases: List[Dict[str, Any]] = field(default_factory=list)
    current_phase: int = 0
    
    # Response options
    player_response_options: List[str] = field(default_factory=list)
    escalation_triggers: List[Dict[str, Any]] = field(default_factory=list)
    
    # Status
    active: bool = False
    triggered: bool = False
    resolved: bool = False
    player_response: Optional[str] = None


class ProceduralMissionGenerator:
    """
    Generates complex, multi-objective missions with living battlefield atmosphere.
    
    Features:
    - Interconnected objective networks with dependencies
    - Coordinated allied operations running in background
    - Dynamic mission evolution based on success/failure
    - Realistic force allocation and timing
    - Background traffic and activities for immersion
    - Emergency and contingency objective generation
    """
    
    def __init__(self, terrain_helper: MissionTerrainHelper):
        self.terrain_helper = terrain_helper
        
        # Mission state
        self.objectives: Dict[str, MissionObjective] = {}
        self.allied_operations: Dict[str, AlliedOperation] = {}
        self.dynamic_encounters: Dict[str, DynamicEncounter] = {}
        
        # Generation parameters
        self.objective_templates = self._initialize_objective_templates()
        self.allied_activity_templates = self._initialize_allied_templates()
        self.mission_complexity_factors = self._initialize_complexity_factors()
        
        # Strategic considerations
        self.available_assets = self._initialize_available_assets()
        self.operational_constraints = {}
        self.current_threat_level = "medium"
        
    def generate_multi_objective_mission(
        self,
        mission_parameters: Dict[str, Any],
        force_composition: Dict[str, Any],
        threat_environment: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate a comprehensive multi-objective mission."""
        
        operation_duration = mission_parameters.get('duration_hours', 2.0)
        
        # 1. Generate primary objectives
        primary_objectives = self._generate_primary_objectives(
            mission_parameters, force_composition, threat_environment
        )
        
        # 2. Generate supporting secondary objectives
        secondary_objectives = self._generate_secondary_objectives(
            primary_objectives, mission_parameters, force_composition
        )
        
        # 3. Create objective dependencies and timing
        self._establish_objective_relationships(
            primary_objectives + secondary_objectives
        )
        
        # 4. Generate coordinated allied operations
        allied_operations = self._generate_allied_operations(
            primary_objectives + secondary_objectives,
            operation_duration,
            mission_parameters
        )
        
        # 5. Create dynamic encounters and background military activities
        background_activities = self._generate_background_activities(
            operation_duration, mission_parameters
        )
        
        # 6. Plan contingency objectives
        contingency_objectives = self._generate_contingency_objectives(
            primary_objectives, threat_environment
        )
        
        # 7. Allocate forces and resources
        force_allocation = self._allocate_forces_to_objectives(
            primary_objectives + secondary_objectives,
            force_composition
        )
        
        # 8. Generate mission timeline
        mission_timeline = self._generate_mission_timeline(
            primary_objectives + secondary_objectives + contingency_objectives,
            allied_operations,
            operation_duration
        )
        
        return {
            'mission_id': mission_parameters.get('mission_id', f'M{int(time.time())}'),
            'primary_objectives': primary_objectives,
            'secondary_objectives': secondary_objectives,
            'contingency_objectives': contingency_objectives,
            'allied_operations': allied_operations,
            'background_activities': background_activities,
            'force_allocation': force_allocation,
            'mission_timeline': mission_timeline,
            'estimated_duration': operation_duration,
            'complexity_rating': self._calculate_complexity_rating(
                primary_objectives + secondary_objectives
            )
        }
    
    def _generate_primary_objectives(
        self,
        mission_parameters: Dict[str, Any],
        force_composition: Dict[str, Any],
        threat_environment: Dict[str, Any]
    ) -> List[MissionObjective]:
        """Generate primary mission objectives."""
        
        mission_type = mission_parameters.get('type', 'mixed')
        complexity = mission_parameters.get('complexity', 'medium')
        
        primary_objectives = []
        
        # Determine number of primary objectives based on complexity
        objective_counts = {
            'simple': random.randint(1, 2),
            'medium': random.randint(2, 3), 
            'complex': random.randint(3, 5),
            'campaign': random.randint(4, 6)
        }
        
        num_objectives = objective_counts.get(complexity, 2)
        
        # Generate diverse primary objectives
        for i in range(num_objectives):
            if mission_type == 'mixed':
                # Mixed mission - varied objective types
                objective_type = self._select_random_objective_type()
            else:
                # Focused mission - related objective types
                objective_type = self._select_focused_objective_type(mission_type, i)
            
            objective = self._create_objective(
                f"PRIMARY_{i+1}",
                objective_type,
                ObjectivePriority.PRIMARY,
                mission_parameters,
                threat_environment
            )
            
            primary_objectives.append(objective)
            self.objectives[objective.objective_id] = objective
        
        return primary_objectives
    
    def _generate_secondary_objectives(
        self,
        primary_objectives: List[MissionObjective],
        mission_parameters: Dict[str, Any],
        force_composition: Dict[str, Any]
    ) -> List[MissionObjective]:
        """Generate secondary objectives that support primary ones."""
        
        secondary_objectives = []
        
        for i, primary_obj in enumerate(primary_objectives):
            # Generate 1-2 supporting secondary objectives per primary
            num_secondary = random.randint(1, 2)
            
            for j in range(num_secondary):
                # Select secondary objective type that supports primary
                secondary_type = self._select_supporting_objective_type(primary_obj.objective_type)
                
                secondary_obj = self._create_objective(
                    f"SECONDARY_{i+1}_{j+1}",
                    secondary_type,
                    ObjectivePriority.SECONDARY,
                    mission_parameters,
                    {}  # Reduced threat for secondary objectives
                )
                
                # Link to primary objective
                secondary_obj.prerequisite_objectives = []  # Can start immediately
                secondary_obj.unlocks_objectives = [primary_obj.objective_id]
                
                secondary_objectives.append(secondary_obj)
                self.objectives[secondary_obj.objective_id] = secondary_obj
        
        # Add some independent secondary objectives
        num_independent = random.randint(1, 3)
        for i in range(num_independent):
            independent_type = self._select_independent_secondary_type()
            
            independent_obj = self._create_objective(
                f"SECONDARY_IND_{i+1}",
                independent_type,
                ObjectivePriority.SECONDARY,
                mission_parameters,
                {}
            )
            
            secondary_objectives.append(independent_obj)
            self.objectives[independent_obj.objective_id] = independent_obj
        
        return secondary_objectives
    
    def _create_objective(
        self,
        objective_id: str,
        objective_type: ObjectiveType,
        priority: ObjectivePriority,
        mission_parameters: Dict[str, Any],
        threat_environment: Dict[str, Any]
    ) -> MissionObjective:
        """Create a single mission objective with appropriate parameters."""
        
        # Get objective template
        template = self.objective_templates.get(objective_type, {})
        
        # Generate target position
        target_position = self._generate_target_position(objective_type, mission_parameters)
        
        # Create base objective
        objective = MissionObjective(
            objective_id=objective_id,
            objective_type=objective_type,
            priority=priority,
            target_position=target_position,
            target_area_radius=template.get('area_radius', 1000),
            target_description=self._generate_target_description(objective_type),
            target_type=template.get('target_type', 'unknown')
        )
        
        # Set timing based on objective type and priority
        if priority == ObjectivePriority.PRIMARY:
            objective.start_time = random.uniform(10, 30)  # 10-30 minutes after mission start
            objective.duration = template.get('duration', 45)
            objective.deadline = objective.start_time + objective.duration + 15  # 15 min buffer
        else:
            objective.start_time = random.uniform(5, 60)
            objective.duration = template.get('duration', 30)
        
        # Set requirements
        objective.required_aircraft_types = template.get('aircraft_types', ['fighter'])
        objective.minimum_aircraft = template.get('min_aircraft', 1)
        objective.maximum_aircraft = template.get('max_aircraft', 2)
        objective.required_weapons = template.get('weapons', [])
        objective.required_equipment = template.get('equipment', [])
        
        # Generate success/failure conditions
        objective.success_conditions = self._generate_success_conditions(objective_type)
        objective.failure_conditions = self._generate_failure_conditions(objective_type)
        
        return objective
    
    def _establish_objective_relationships(self, objectives: List[MissionObjective]) -> None:
        """Establish dependencies and relationships between objectives."""
        
        # Sort objectives by priority and start time
        sorted_objectives = sorted(objectives, key=lambda obj: (
            obj.priority.value, obj.start_time
        ))
        
        for i, objective in enumerate(sorted_objectives):
            # SEAD objectives should precede strike objectives
            if objective.objective_type == ObjectiveType.STRIKE:
                sead_objectives = [obj for obj in sorted_objectives 
                                 if obj.objective_type == ObjectiveType.SEAD 
                                 and obj.start_time < objective.start_time]
                if sead_objectives:
                    objective.prerequisite_objectives.extend([obj.objective_id for obj in sead_objectives])
            
            # Escort objectives should coordinate with protected missions
            elif objective.objective_type == ObjectiveType.ESCORT:
                # Find objectives that need escort
                protected_objectives = [obj for obj in sorted_objectives
                                      if obj.objective_type in [ObjectiveType.STRIKE, ObjectiveType.TRANSPORT]
                                      and abs(obj.start_time - objective.start_time) < 20]
                if protected_objectives:
                    objective.coordinated_activities.extend([obj.objective_id for obj in protected_objectives])
            
            # CAS objectives should follow reconnaissance
            elif objective.objective_type == ObjectiveType.CAS:
                recce_objectives = [obj for obj in sorted_objectives
                                  if obj.objective_type == ObjectiveType.RECCE
                                  and obj.start_time < objective.start_time]
                if recce_objectives:
                    objective.prerequisite_objectives.extend([obj.objective_id for obj in recce_objectives[:1]])
    
    def _generate_allied_operations(
        self,
        mission_objectives: List[MissionObjective],
        operation_duration: float,
        mission_parameters: Dict[str, Any]
    ) -> List[AlliedOperation]:
        """Generate coordinated allied operations."""
        
        allied_operations = []
        
        # 1. Generate support operations for each major objective
        for objective in mission_objectives:
            if objective.priority == ObjectivePriority.PRIMARY:
                # AWACS support for complex operations
                if objective.objective_type in [ObjectiveType.STRIKE, ObjectiveType.SEAD, ObjectiveType.OCA]:
                    awacs_op = self._create_awacs_support_operation(objective, operation_duration)
                    allied_operations.append(awacs_op)
                
                # Tanker support for long-range operations
                if self._requires_tanker_support(objective):
                    tanker_op = self._create_tanker_support_operation(objective, operation_duration)
                    allied_operations.append(tanker_op)
                
                # CSAR standby for high-risk operations
                if self._is_high_risk_operation(objective):
                    csar_op = self._create_csar_standby_operation(objective, operation_duration)
                    allied_operations.append(csar_op)
        
        # 2. Generate routine background operations
        num_routine_ops = random.randint(3, 8)
        for i in range(num_routine_ops):
            routine_op = self._create_routine_allied_operation(operation_duration, i)
            allied_operations.append(routine_op)
        
        # 3. Generate logistics operations
        num_logistics_ops = random.randint(2, 4)
        for i in range(num_logistics_ops):
            logistics_op = self._create_logistics_operation(operation_duration, i)
            allied_operations.append(logistics_op)
        
        # 4. Generate training/test flights
        if random.random() < 0.6:  # 60% chance
            training_op = self._create_training_operation(operation_duration)
            allied_operations.append(training_op)
        
        # Store operations
        for operation in allied_operations:
            self.allied_operations[operation.operation_id] = operation
        
        return allied_operations
    
    def _generate_background_activities(
        self,
        operation_duration: float,
        mission_parameters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate background military activities and dynamic encounters."""
        
        background_activities = []
        
        # Enemy air activity (creates dynamic encounters)
        num_enemy_patrols = random.randint(2, 5)
        for i in range(num_enemy_patrols):
            enemy_patrol = self._create_enemy_patrol_activity(operation_duration, i)
            background_activities.append(enemy_patrol)
        
        # Neutral/unknown aircraft (creates investigation opportunities)
        num_unknown_contacts = random.randint(1, 3)
        for i in range(num_unknown_contacts):
            unknown_contact = self._create_unknown_contact_activity(operation_duration, i)
            background_activities.append(unknown_contact)
        
        # Dynamic encounter triggers
        encounter_triggers = self._create_dynamic_encounter_triggers(operation_duration)
        background_activities.extend(encounter_triggers)
        
        # Radio chatter and intelligence updates
        radio_activities = self._create_radio_chatter_activities(operation_duration)
        background_activities.extend(radio_activities)
        
        return background_activities
    
    def _generate_contingency_objectives(
        self,
        primary_objectives: List[MissionObjective],
        threat_environment: Dict[str, Any]
    ) -> List[MissionObjective]:
        """Generate contingency objectives that may emerge during mission."""
        
        contingency_objectives = []
        
        # Pilot down contingency
        if any(obj.objective_type in [ObjectiveType.STRIKE, ObjectiveType.CAS, ObjectiveType.SEAD] 
               for obj in primary_objectives):
            csar_contingency = self._create_csar_contingency_objective()
            contingency_objectives.append(csar_contingency)
        
        # Pop-up SAM threat
        if any(obj.objective_type in [ObjectiveType.STRIKE, ObjectiveType.CAS] 
               for obj in primary_objectives):
            sam_suppression = self._create_popup_sam_objective()
            contingency_objectives.append(sam_suppression)
        
        # Friendly aircraft in distress
        if random.random() < 0.4:  # 40% chance
            assistance_objective = self._create_aircraft_assistance_objective()
            contingency_objectives.append(assistance_objective)
        
        # Opportunity targets
        num_opportunity = random.randint(1, 3)
        for i in range(num_opportunity):
            opportunity_obj = self._create_opportunity_target_objective(i)
            contingency_objectives.append(opportunity_obj)
        
        return contingency_objectives
    
    # Allied operation creation methods
    def _create_awacs_support_operation(
        self,
        supported_objective: MissionObjective,
        duration: float
    ) -> AlliedOperation:
        """Create AWACS support operation."""
        
        # AWACS orbit position - standoff from target area
        target_x, target_y, target_z = supported_objective.target_position
        
        # Position AWACS 50-80km from target area
        angle = generate_random_angle(radians=True)
        distance = random.uniform(50000, 80000)
        
        orbit_x = target_x + distance * math.cos(angle)
        orbit_z = target_z + distance * math.sin(angle)
        orbit_y = 8000  # 8000m altitude
        
        # Create racetrack orbit
        orbit_length = 20000  # 20km racetrack
        waypoints = [
            (orbit_x - orbit_length/2, orbit_y, orbit_z),
            (orbit_x + orbit_length/2, orbit_y, orbit_z),
            (orbit_x + orbit_length/2, orbit_y, orbit_z),
            (orbit_x - orbit_length/2, orbit_y, orbit_z)
        ]
        
        return AlliedOperation(
            operation_id=f"AWACS_SUPPORT_{supported_objective.objective_id}",
            activity_type=AlliedActivity.AWACS_ORBIT,
            waypoints=waypoints,
            start_time=max(0, supported_objective.start_time - 30),  # 30 min early
            duration=duration + 60,  # Stay longer than mission
            unit_types=["E-3 Sentry"],
            unit_count=1,
            speed=250,
            altitude=8000,
            radio_chatter=True,
            can_be_tasked=True,
            emergency_response=True,
            priority_level=8
        )
    
    def _create_tanker_support_operation(
        self,
        supported_objective: MissionObjective,
        duration: float
    ) -> AlliedOperation:
        """Create tanker support operation."""
        
        # Tanker track - parallel to ingress route
        target_x, target_y, target_z = supported_objective.target_position
        
        # Position tanker on safer side of operation
        track_distance = 60000  # 60km from target
        angle = generate_random_angle(min_angle=180, max_angle=360, radians=True)  # Behind friendly lines
        
        track_center_x = target_x + track_distance * math.cos(angle)
        track_center_z = target_z + track_distance * math.sin(angle)
        track_altitude = 7000  # 7000m altitude
        
        # Create tanker track
        track_length = 40000  # 40km track
        perpendicular_angle = angle + math.pi/2
        
        waypoints = [
            (track_center_x + (track_length/2) * math.cos(perpendicular_angle),
             track_altitude,
             track_center_z + (track_length/2) * math.sin(perpendicular_angle)),
            (track_center_x - (track_length/2) * math.cos(perpendicular_angle),
             track_altitude,
             track_center_z - (track_length/2) * math.sin(perpendicular_angle))
        ]
        
        return AlliedOperation(
            operation_id=f"TANKER_SUPPORT_{supported_objective.objective_id}",
            activity_type=AlliedActivity.TANKER_ORBIT,
            waypoints=waypoints,
            start_time=max(0, supported_objective.start_time - 45),  # 45 min early
            duration=duration + 90,  # Stay much longer
            repeat_interval=15,  # 15 minute orbit
            unit_types=["KC-135 Stratotanker"],
            unit_count=1,
            speed=230,
            altitude=7000,
            radio_chatter=True,
            can_be_tasked=True,
            priority_level=7
        )
    
    def _create_routine_allied_operation(self, duration: float, index: int) -> AlliedOperation:
        """Create routine allied operation for background activity."""
        
        activity_types = [
            AlliedActivity.ROUTINE_PATROL,
            AlliedActivity.TRAINING_FLIGHT,
            AlliedActivity.MAINTENANCE_TEST,
            AlliedActivity.FERRY_FLIGHT,
            AlliedActivity.BORDER_PATROL
        ]
        
        activity_type = random.choice(activity_types)
        
        # Generate random route across map
        map_size = getattr(self.terrain_helper.tc, 'map_size_m', 200000)
        
        start_x = random.uniform(0.1 * map_size, 0.9 * map_size)
        start_z = random.uniform(0.1 * map_size, 0.9 * map_size)
        end_x = random.uniform(0.1 * map_size, 0.9 * map_size)
        end_z = random.uniform(0.1 * map_size, 0.9 * map_size)
        
        altitude = random.uniform(1000, 8000)
        
        waypoints = [
            (start_x, altitude, start_z),
            (end_x, altitude, end_z)
        ]
        
        # Add intermediate waypoints for longer routes
        from ..misc.math_utils import calculate_2d_distance
        if calculate_2d_distance((start_x, start_z), (end_x, end_z)) > 50000:
            mid_x = (start_x + end_x) / 2 + random.uniform(-10000, 10000)
            mid_z = (start_z + end_z) / 2 + random.uniform(-10000, 10000)
            waypoints.insert(1, (mid_x, altitude, mid_z))
        
        # Select appropriate aircraft for activity
        aircraft_types = self._get_aircraft_for_activity(activity_type)
        
        return AlliedOperation(
            operation_id=f"ROUTINE_{activity_type.value.upper()}_{index}",
            activity_type=activity_type,
            waypoints=waypoints,
            start_time=random.uniform(0, duration * 60),  # Random start during mission
            duration=random.uniform(30, 120),  # 30-120 minutes
            unit_types=aircraft_types,
            unit_count=random.randint(1, 2),
            speed=random.uniform(200, 350),
            altitude=altitude,
            radio_chatter=random.random() < 0.7,  # 70% chance of radio chatter
            priority_level=random.randint(1, 3)
        )
    
    # Helper methods for content generation
    def _select_random_objective_type(self) -> ObjectiveType:
        """Select random objective type for mixed missions."""
        combat_objectives = [
            ObjectiveType.CAP, ObjectiveType.STRIKE, ObjectiveType.CAS,
            ObjectiveType.SEAD, ObjectiveType.INTERDICTION, ObjectiveType.OCA
        ]
        return random.choice(combat_objectives)
    
    def _select_focused_objective_type(self, mission_type: str, index: int) -> ObjectiveType:
        """Select objective type for focused mission."""
        mission_type_map = {
            'air_superiority': [ObjectiveType.CAP, ObjectiveType.OCA, ObjectiveType.DCA],
            'ground_attack': [ObjectiveType.STRIKE, ObjectiveType.CAS, ObjectiveType.INTERDICTION],
            'support': [ObjectiveType.ESCORT, ObjectiveType.TRANSPORT, ObjectiveType.TANKER_SUPPORT],
            'reconnaissance': [ObjectiveType.RECCE, ObjectiveType.SURVEILLANCE, ObjectiveType.BDA]
        }
        
        available_types = mission_type_map.get(mission_type, [ObjectiveType.CAP])
        return available_types[index % len(available_types)]
    
    def _select_supporting_objective_type(self, primary_type: ObjectiveType) -> ObjectiveType:
        """Select secondary objective type that supports primary."""
        support_map = {
            ObjectiveType.STRIKE: [ObjectiveType.SEAD, ObjectiveType.RECCE, ObjectiveType.ESCORT],
            ObjectiveType.CAS: [ObjectiveType.RECCE, ObjectiveType.CAP, ObjectiveType.MEDEVAC],
            ObjectiveType.CAP: [ObjectiveType.AWACS_SUPPORT, ObjectiveType.TANKER_SUPPORT],
            ObjectiveType.SEAD: [ObjectiveType.RECCE, ObjectiveType.EW, ObjectiveType.ESCORT],
            ObjectiveType.OCA: [ObjectiveType.RECCE, ObjectiveType.CAP, ObjectiveType.ESCORT]
        }
        
        supporting_types = support_map.get(primary_type, [ObjectiveType.RECCE])
        return random.choice(supporting_types)
    
    def _select_independent_secondary_type(self) -> ObjectiveType:
        """Select independent secondary objective type."""
        independent_types = [
            ObjectiveType.RECCE, ObjectiveType.SURVEILLANCE, ObjectiveType.BDA,
            ObjectiveType.TRANSPORT, ObjectiveType.TRAINING
        ]
        return random.choice(independent_types)
    
    def _generate_target_position(
        self,
        objective_type: ObjectiveType,
        mission_parameters: Dict[str, Any]
    ) -> Tuple[float, float, float]:
        """Generate appropriate target position for objective type."""
        
        # Get operational area bounds
        area_center = mission_parameters.get('area_center', (100000, 1000, 100000))
        area_radius = mission_parameters.get('area_radius', 50000)
        
        # Generate position within operational area
        angle = generate_random_angle(radians=True)
        distance = random.uniform(0.3 * area_radius, 0.9 * area_radius)
        
        x = area_center[0] + distance * math.cos(angle)
        z = area_center[2] + distance * math.sin(angle)
        
        try:
            y = self.terrain_helper.tc.get_terrain_height(x, z)
            
            # Adjust altitude based on objective type
            if objective_type in [ObjectiveType.CAP, ObjectiveType.AWACS_SUPPORT]:
                y += random.uniform(3000, 8000)  # High altitude
            elif objective_type == ObjectiveType.CAS:
                y += random.uniform(500, 2000)   # Low altitude
            else:
                y += random.uniform(100, 1000)   # Variable altitude
                
        except Exception:
            y = area_center[1]  # Fallback altitude
        
        return (x, y, z)
    
    def _generate_target_description(self, objective_type: ObjectiveType) -> str:
        """Generate target description for objective type."""
        
        descriptions = {
            ObjectiveType.STRIKE: [
                "Command bunker complex", "Radar installation", "Communication facility",
                "Supply depot", "Vehicle maintenance facility", "Fuel storage tanks"
            ],
            ObjectiveType.CAS: [
                "Enemy infantry positions", "Armored vehicle concentration",  
                "Artillery battery", "Supply convoy", "Forward operating base"
            ],
            ObjectiveType.SEAD: [
                "SA-6 SAM site", "Early warning radar", "SA-8 mobile SAM",
                "AAA battery", "Integrated air defense network"
            ],
            ObjectiveType.CAP: [
                "Patrol sector Alpha", "Air superiority zone", "Combat air patrol area"
            ],
            ObjectiveType.RECCE: [
                "Suspected enemy positions", "Unknown installation",
                "Area of interest", "Potential target complex"
            ]
        }
        
        type_descriptions = descriptions.get(objective_type, ["Unknown target"])
        return random.choice(type_descriptions)
    
    # Initialize template and configuration methods
    def _initialize_objective_templates(self) -> Dict[ObjectiveType, Dict[str, Any]]:
        """Initialize objective templates with parameters."""
        return {
            ObjectiveType.CAP: {
                'area_radius': 5000,
                'duration': 60,
                'aircraft_types': ['fighter'],
                'min_aircraft': 2,
                'max_aircraft': 4,
                'weapons': ['aim-120', 'aim-9'],
                'target_type': 'airspace'
            },
            ObjectiveType.STRIKE: {
                'area_radius': 1000,
                'duration': 30,
                'aircraft_types': ['attack', 'multirole'],
                'min_aircraft': 2,
                'max_aircraft': 6,
                'weapons': ['gbu-12', 'gbu-31', 'agm-65'],
                'target_type': 'ground_target'
            },
            ObjectiveType.CAS: {
                'area_radius': 2000,
                'duration': 45,
                'aircraft_types': ['attack', 'multirole'],
                'min_aircraft': 2,
                'max_aircraft': 4,
                'weapons': ['gbu-12', 'agm-65', 'cannon'],
                'equipment': ['targeting_pod'],
                'target_type': 'ground_forces'
            },
            ObjectiveType.SEAD: {
                'area_radius': 3000,
                'duration': 40,
                'aircraft_types': ['multirole', 'ew'],
                'min_aircraft': 2,
                'max_aircraft': 4,
                'weapons': ['agm-88', 'agm-158'],
                'equipment': ['ew_pod'],
                'target_type': 'air_defense'
            },
            ObjectiveType.ESCORT: {
                'area_radius': 10000,
                'duration': 90,
                'aircraft_types': ['fighter'],
                'min_aircraft': 2,
                'max_aircraft': 4,
                'weapons': ['aim-120', 'aim-9'],
                'target_type': 'protection'
            }
        }
    
    def _initialize_allied_templates(self) -> Dict[AlliedActivity, Dict[str, Any]]:
        """Initialize allied activity templates."""
        return {
            AlliedActivity.ROUTINE_PATROL: {
                'aircraft_types': ['fighter', 'multirole'],
                'duration_range': (60, 120),
                'altitude_range': (3000, 8000),
                'speed_range': (250, 350)
            },
            AlliedActivity.TRAINING_FLIGHT: {
                'aircraft_types': ['trainer', 'fighter'],
                'duration_range': (45, 90),
                'altitude_range': (1000, 5000),
                'speed_range': (200, 300)
            },
            AlliedActivity.LOGISTICS_CONVOY: {
                'aircraft_types': ['transport', 'cargo'],
                'duration_range': (90, 180),
                'altitude_range': (5000, 9000),
                'speed_range': (220, 280)
            }
        }
    
    def _initialize_complexity_factors(self) -> Dict[str, float]:
        """Initialize mission complexity factors."""
        return {
            'simple': 1.0,
            'medium': 1.5,
            'complex': 2.0,
            'campaign': 2.5
        }
    
    def _initialize_available_assets(self) -> Dict[str, List[str]]:
        """Initialize available military assets."""
        return {
            'fighter': ['F-16C', 'F/A-18C', 'F-15C', 'F-14'],
            'multirole': ['F/A-18C', 'F-16C', 'AV-8B'],
            'attack': ['A-10C', 'AV-8B'],
            'transport': ['C-130', 'C-17'],
            'tanker': ['KC-135', 'KC-10'],
            'awacs': ['E-3'],
            'trainer': ['T-45C', 'L-39']
        }
    
    # Additional helper methods (simplified implementations)
    def _generate_success_conditions(self, objective_type: ObjectiveType) -> List[Dict[str, Any]]:
        """Generate success conditions for objective."""
        return [{'type': 'target_destroyed', 'percentage': 80}]
    
    def _generate_failure_conditions(self, objective_type: ObjectiveType) -> List[Dict[str, Any]]:
        """Generate failure conditions for objective."""
        return [{'type': 'time_expired'}, {'type': 'excessive_casualties'}]
    
    def _requires_tanker_support(self, objective: MissionObjective) -> bool:
        """Check if objective requires tanker support."""
        return objective.objective_type in [ObjectiveType.STRIKE, ObjectiveType.INTERDICTION, ObjectiveType.OCA]
    
    def _is_high_risk_operation(self, objective: MissionObjective) -> bool:
        """Check if operation is high-risk."""
        return objective.objective_type in [ObjectiveType.SEAD, ObjectiveType.STRIKE, ObjectiveType.CAS]
    
    def _create_csar_standby_operation(self, objective: MissionObjective, duration: float) -> AlliedOperation:
        """Create CSAR standby operation."""
        # Position CSAR near friendly territory
        safe_position = self._get_safe_position_for_csar()
        
        return AlliedOperation(
            operation_id=f"CSAR_STANDBY_{objective.objective_id}",
            activity_type=AlliedActivity.MEDEVAC_STANDBY,
            waypoints=[safe_position],
            start_time=0,
            duration=duration,
            unit_types=["HH-60"],
            unit_count=1,
            speed=150,
            altitude=500,
            can_be_tasked=True,
            emergency_response=True,
            priority_level=9
        )
    
    def _create_logistics_operation(self, duration: float, index: int) -> AlliedOperation:
        """Create logistics operation."""
        # Generate supply route
        waypoints = self._generate_supply_route()
        
        return AlliedOperation(
            operation_id=f"LOGISTICS_{index}",
            activity_type=AlliedActivity.LOGISTICS_CONVOY,
            waypoints=waypoints,
            start_time=random.uniform(0, duration * 60),
            duration=random.uniform(90, 180),
            unit_types=["C-130"],
            unit_count=1,
            speed=250,
            altitude=6000,
            priority_level=4
        )
    
    def _create_training_operation(self, duration: float) -> AlliedOperation:
        """Create training operation."""
        # Generate training area
        training_waypoints = self._generate_training_pattern()
        
        return AlliedOperation(
            operation_id="TRAINING_FLIGHT",
            activity_type=AlliedActivity.TRAINING_FLIGHT,
            waypoints=training_waypoints,
            start_time=random.uniform(0, 60),
            duration=90,
            unit_types=["T-45C"],
            unit_count=2,
            speed=200,
            altitude=3000,
            radio_chatter=True,
            priority_level=2
        )
    
    def _create_enemy_patrol_activity(self, duration: float, index: int) -> Dict[str, Any]:
        """Create enemy patrol encounter."""
        
        # Generate patrol route in enemy territory
        patrol_center = self._get_enemy_territory_position()
        patrol_radius = random.uniform(15000, 25000)
        
        # Create patrol waypoints
        num_waypoints = random.randint(3, 5)
        waypoints = []
        for i in range(num_waypoints):
            angle = (2 * math.pi * i) / num_waypoints
            x = patrol_center[0] + patrol_radius * math.cos(angle)
            z = patrol_center[2] + patrol_radius * math.sin(angle)
            y = random.uniform(3000, 8000)
            waypoints.append((x, y, z))
        
        enemy_aircraft = random.choice(["MiG-29", "Su-27", "F-5E", "Mirage F1"])
        
        return {
            'activity_id': f"ENEMY_PATROL_{index}",
            'activity_type': 'enemy_patrol',
            'waypoints': waypoints,
            'start_time': random.uniform(0, duration * 60),
            'duration': random.uniform(45, 90),
            'aircraft_type': enemy_aircraft,
            'unit_count': random.randint(1, 2),
            'threat_level': random.choice(['low', 'medium', 'high']),
            'patrol_pattern': 'cap',
            'engagement_rules': 'defensive',
            'detection_range': random.uniform(25000, 40000),
            'can_escalate': True
        }
    
    def _create_unknown_contact_activity(self, duration: float, index: int) -> Dict[str, Any]:
        """Create unknown contact that requires investigation."""
        
        # Position in neutral or contested area
        position = self._get_contested_territory_position()
        
        # Could be smuggler, lost aircraft, or probe
        contact_types = [
            {'type': 'smuggler', 'aircraft': 'Cessna 310', 'behavior': 'evasive'},
            {'type': 'lost_aircraft', 'aircraft': 'C-130', 'behavior': 'erratic'},
            {'type': 'probe_flight', 'aircraft': 'Tu-95', 'behavior': 'straight_line'},
            {'type': 'defector', 'aircraft': 'MiG-21', 'behavior': 'beacon'}
        ]
        
        contact_info = random.choice(contact_types)
        
        return {
            'activity_id': f"UNKNOWN_CONTACT_{index}",
            'activity_type': 'unknown_contact',
            'position': position,
            'start_time': random.uniform(20, duration * 60 - 30),
            'contact_type': contact_info['type'],
            'aircraft_type': contact_info['aircraft'],
            'behavior_pattern': contact_info['behavior'],
            'identification_required': True,
            'response_options': ['investigate', 'intercept', 'escort', 'ignore'],
            'escalation_potential': contact_info['type'] in ['probe_flight', 'smuggler']
        }
    
    # Simplified helper method implementations
    def _get_aircraft_for_activity(self, activity_type: AlliedActivity) -> List[str]:
        """Get appropriate aircraft types for activity."""
        activity_aircraft = {
            AlliedActivity.ROUTINE_PATROL: ["F-16C", "F/A-18C"],
            AlliedActivity.TRAINING_FLIGHT: ["T-45C", "F-16C"],
            AlliedActivity.LOGISTICS_CONVOY: ["C-130"],
            AlliedActivity.BORDER_PATROL: ["F-16C"],
            AlliedActivity.MAINTENANCE_TEST: ["F/A-18C"]
        }
        return activity_aircraft.get(activity_type, ["F-16C"])
    
    def _allocate_forces_to_objectives(
        self,
        objectives: List[MissionObjective],
        force_composition: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Allocate available forces to objectives."""
        # Simplified force allocation
        allocation = {}
        for obj in objectives:
            allocation[obj.objective_id] = {
                'aircraft_count': obj.minimum_aircraft,
                'aircraft_types': obj.required_aircraft_types[:1],
                'weapons': obj.required_weapons
            }
        return allocation
    
    def _generate_mission_timeline(
        self,
        objectives: List[MissionObjective],
        allied_ops: List[AlliedOperation],
        duration: float
    ) -> List[Dict[str, Any]]:
        """Generate mission timeline."""
        timeline = []
        
        # Add objective events
        for obj in objectives:
            timeline.append({
                'time': obj.start_time,
                'event': f"{obj.objective_id} begins",
                'type': 'objective_start'
            })
        
        # Add allied operation events
        for op in allied_ops:
            timeline.append({
                'time': op.start_time,
                'event': f"{op.operation_id} commences",
                'type': 'allied_operation'
            })
        
        # Sort by time
        timeline.sort(key=lambda x: x['time'])
        return timeline
    
    def _calculate_complexity_rating(self, objectives: List[MissionObjective]) -> str:
        """Calculate mission complexity rating."""
        primary_count = len([obj for obj in objectives if obj.priority == ObjectivePriority.PRIMARY])
        secondary_count = len([obj for obj in objectives if obj.priority == ObjectivePriority.SECONDARY])
        
        total_complexity = primary_count * 2 + secondary_count
        
        if total_complexity <= 4:
            return "Simple"
        elif total_complexity <= 8:
            return "Medium"
        elif total_complexity <= 12:
            return "Complex"
        else:
            return "Campaign"
    
    # Placeholder methods for position generation
    def _get_safe_position_for_csar(self) -> Tuple[float, float, float]:
        """Get safe position for CSAR standby."""
        return (50000, 1000, 50000)  # Simplified safe position
    
    def _generate_supply_route(self) -> List[Tuple[float, float, float]]:
        """Generate supply route waypoints."""
        return [(30000, 6000, 30000), (170000, 6000, 170000)]  # Simplified route
    
    def _generate_training_pattern(self) -> List[Tuple[float, float, float]]:
        """Generate training pattern waypoints."""
        return [(80000, 3000, 80000), (120000, 3000, 120000), (80000, 3000, 80000)]
    
    def _generate_airline_route(self) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
        """Generate airline route."""
        origin = (20000, 10000, 20000)
        destination = (180000, 10000, 180000)
        return origin, destination
    
    def _get_enemy_territory_position(self) -> Tuple[float, float, float]:
        """Get position in enemy-controlled territory."""
        # Assume enemy territory is in the eastern portion of map
        map_size = getattr(self.terrain_helper.tc, 'map_size_m', 200000)
        
        x = random.uniform(0.6 * map_size, 0.9 * map_size)  # Eastern 30%
        z = random.uniform(0.2 * map_size, 0.8 * map_size)
        y = random.uniform(2000, 6000)
        
        return (x, y, z)
    
    def _get_contested_territory_position(self) -> Tuple[float, float, float]:
        """Get position in contested/neutral territory."""
        # Middle portion of map
        map_size = getattr(self.terrain_helper.tc, 'map_size_m', 200000)
        
        x = random.uniform(0.4 * map_size, 0.6 * map_size)  # Middle 20%
        z = random.uniform(0.3 * map_size, 0.7 * map_size)
        y = random.uniform(1000, 4000)
        
        return (x, y, z)
    
    def _get_high_value_target_area(self) -> Tuple[Tuple[float, float], float]:
        """Get area around high-value targets for SAM placement."""
        # Area around primary objectives
        if self.objectives:
            primary_objectives = [obj for obj in self.objectives.values() 
                                if obj.priority == ObjectivePriority.PRIMARY]
            if primary_objectives:
                target_obj = random.choice(primary_objectives)
                center = (target_obj.target_position[0], target_obj.target_position[2])
                radius = 15000  # 15km radius
                return (center, radius)
        
        # Fallback to map center
        map_size = getattr(self.terrain_helper.tc, 'map_size_m', 200000)
        center = (map_size / 2, map_size / 2)
        return (center, 20000)
    
    def _create_dynamic_encounter_triggers(self, duration: float) -> List[Dict[str, Any]]:
        """Create dynamic encounter triggers using our event system."""
        
        triggers = []
        
        # Pilot down scenario trigger
        triggers.append({
            'trigger_id': 'PILOT_DOWN_TRIGGER',
            'trigger_type': 'conditional',
            'conditions': [
                {'type': 'aircraft_damaged', 'threshold': 0.8},
                {'type': 'in_enemy_territory', 'distance': 20000}
            ],
            'event_type': 'pilot_down',
            'response_time': 300,  # 5 minutes to trigger CSAR
            'escalation_events': ['enemy_search_party', 'time_pressure']
        })
        
        # Pop-up SAM threat
        triggers.append({
            'trigger_id': 'POPUP_SAM_TRIGGER', 
            'trigger_type': 'area_based',
            'trigger_area': self._get_high_value_target_area(),
            'conditions': [
                {'type': 'player_enters_area'},
                {'type': 'random_chance', 'probability': 0.4}
            ],
            'event_type': 'popup_sam_site',
            'threat_level': 'high',
            'sam_types': ['SA-6', 'SA-8', 'SA-11'],
            'response_options': ['engage', 'avoid', 'call_sead']
        })
        
        # Enemy reinforcements
        triggers.append({
            'trigger_id': 'ENEMY_REINFORCEMENTS',
            'trigger_type': 'conditional',
            'conditions': [
                {'type': 'primary_objective_failed'},
                {'type': 'high_enemy_losses', 'threshold': 3}
            ],
            'event_type': 'enemy_reinforcements',
            'reinforcement_types': ['fighters', 'sam_sites'],
            'escalation_timeline': [5, 15, 30]  # minutes
        })
        
        # Friendly aircraft in distress
        triggers.append({
            'trigger_id': 'FRIENDLY_DISTRESS',
            'trigger_type': 'time_based',
            'trigger_time': random.uniform(30, duration * 60 - 30),
            'event_type': 'friendly_in_distress',
            'distress_types': ['fuel_emergency', 'system_failure', 'combat_damage'],
            'assistance_required': True,
            'time_critical': True
        })
        
        return triggers
    
    def _create_radio_chatter_activities(self, duration: float) -> List[Dict[str, Any]]:
        """Create realistic radio chatter and intelligence updates."""
        
        radio_activities = []
        
        # Periodic intelligence updates
        for i in range(random.randint(3, 6)):
            radio_activities.append({
                'activity_id': f'INTEL_UPDATE_{i}',
                'activity_type': 'intel_update',
                'trigger_time': random.uniform(10, duration * 60 - 10),
                'intel_type': random.choice([
                    'threat_assessment_update',
                    'enemy_movement_report', 
                    'weather_change',
                    'friendly_status_update',
                    'target_verification'
                ]),
                'priority': random.choice(['routine', 'priority', 'immediate']),
                'affects_mission': random.random() < 0.3  # 30% chance
            })
        
        # Allied unit check-ins
        for i in range(random.randint(2, 4)):
            radio_activities.append({
                'activity_id': f'ALLIED_CHECKIN_{i}',
                'activity_type': 'allied_checkin',
                'trigger_time': random.uniform(5, duration * 60),
                'unit_type': random.choice(['awacs', 'tanker', 'csar', 'transport']),
                'status': random.choice(['on_station', 'delayed', 'early', 'diverted']),
                'affects_support': True
            })
        
        # Emergency communications
        if random.random() < 0.4:  # 40% chance
            radio_activities.append({
                'activity_id': 'EMERGENCY_COMM',
                'activity_type': 'emergency_communication',
                'trigger_time': random.uniform(20, duration * 60 - 20),
                'emergency_type': random.choice([
                    'mayday_call',
                    'threat_warning',
                    'abort_mission',
                    'change_of_mission'
                ]),
                'response_required': True,
                'time_sensitive': True
            })
        
        return radio_activities
    
    def _create_csar_contingency_objective(self) -> MissionObjective:
        """Create CSAR contingency objective."""
        return MissionObjective(
            objective_id="CONTINGENCY_CSAR",
            objective_type=ObjectiveType.CSAR,
            priority=ObjectivePriority.EMERGENT,
            target_position=(100000, 500, 100000),  # Will be updated when triggered
            target_description="Downed pilot rescue",
            start_time=0,  # Immediate when triggered
            duration=60,
            required_aircraft_types=["helicopter"],
            minimum_aircraft=2,
            status="contingency"
        )
    
    def _create_popup_sam_objective(self) -> MissionObjective:
        """Create pop-up SAM suppression objective."""
        return MissionObjective(
            objective_id="CONTINGENCY_SAM",
            objective_type=ObjectiveType.SEAD,
            priority=ObjectivePriority.EMERGENT,
            target_position=(120000, 800, 120000),  # Will be updated when triggered
            target_description="Pop-up SAM threat",
            start_time=0,  # Immediate when triggered
            duration=20,
            required_aircraft_types=["multirole"],
            minimum_aircraft=2,
            required_weapons=["agm-88"],
            status="contingency"
        )
    
    def _create_aircraft_assistance_objective(self) -> MissionObjective:
        """Create aircraft assistance objective."""
        return MissionObjective(
            objective_id="CONTINGENCY_ASSIST",
            objective_type=ObjectiveType.ESCORT,
            priority=ObjectivePriority.EMERGENT,
            target_position=(90000, 2000, 90000),
            target_description="Assist friendly aircraft in distress",
            start_time=0,
            duration=30,
            required_aircraft_types=["fighter"],
            minimum_aircraft=2,
            status="contingency"
        )
    
    def _create_opportunity_target_objective(self, index: int) -> MissionObjective:
        """Create opportunity target objective."""
        return MissionObjective(
            objective_id=f"OPPORTUNITY_{index}",
            objective_type=ObjectiveType.STRIKE,
            priority=ObjectivePriority.TERTIARY,
            target_position=(random.uniform(80000, 120000), 1000, random.uniform(80000, 120000)),
            target_description="Target of opportunity",
            start_time=random.uniform(20, 80),
            duration=15,
            required_aircraft_types=["multirole"],
            minimum_aircraft=1,
            status="contingency"
        )