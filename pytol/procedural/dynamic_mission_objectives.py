"""
Dynamic Mission Objectives System for multi-phase, adaptive missions.

This system creates rich, evolving missions with:
- Multi-phase objectives that unlock based on mission progress
- Time-sensitive targets with realistic windows
- Adaptive mission flow based on player actions and enemy response
- Intelligence updates that change mission parameters
- Emergency objectives that can appear during mission execution
- Realistic mission success/failure cascading effects
"""
from __future__ import annotations

import time
import math
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any, Callable
from enum import Enum

from pytol.terrain.mission_terrain_helper import MissionTerrainHelper


class ObjectiveType(Enum):
    """Types of mission objectives."""
    PRIMARY = "primary"              # Mission-critical objectives
    SECONDARY = "secondary"          # Bonus objectives
    OPPORTUNITY = "opportunity"      # Time-limited bonus targets
    EMERGENCY = "emergency"          # Urgent objectives that appear during mission
    CONDITIONAL = "conditional"      # Unlocked by completing other objectives
    TIME_SENSITIVE = "time_sensitive" # Must be completed within time window


class ObjectiveState(Enum):
    """Current state of an objective."""
    LOCKED = "locked"          # Not yet available
    ACTIVE = "active"          # Available for completion
    IN_PROGRESS = "in_progress" # Player is engaging
    COMPLETED = "completed"    # Successfully completed
    FAILED = "failed"          # Failed or time expired
    OBSOLETE = "obsolete"      # No longer relevant


class TriggerCondition(Enum):
    """Conditions that can trigger objective state changes."""
    TIME_ELAPSED = "time_elapsed"
    OBJECTIVE_COMPLETED = "objective_completed"
    UNIT_DESTROYED = "unit_destroyed"
    AREA_ENTERED = "area_entered"
    THREAT_LEVEL_CHANGED = "threat_level_changed"
    PLAYER_DAMAGED = "player_damaged"
    INTEL_UPDATED = "intel_updated"


@dataclass
class ObjectiveTrigger:
    """Trigger condition for objective state changes."""
    condition: TriggerCondition
    parameters: Dict[str, Any]  # Condition-specific parameters
    action: str  # What to do when triggered ("activate", "complete", "fail", "update")
    target_objective_id: Optional[str] = None  # Which objective to affect


@dataclass
class DynamicObjective:
    """A dynamic mission objective with conditional logic."""
    objective_id: str
    name: str
    description: str
    objective_type: ObjectiveType
    state: ObjectiveState = ObjectiveState.LOCKED
    
    # Position and targeting
    position: Optional[Tuple[float, float, float]] = None
    target_units: List[str] = field(default_factory=list)  # Unit IDs to destroy/interact with
    target_area: Optional[Tuple[Tuple[float, float], float]] = None  # (center, radius)
    
    # Timing
    time_limit: Optional[float] = None  # Seconds to complete once active
    activation_time: Optional[float] = None  # Mission time when this becomes available
    completion_time: Optional[float] = None  # When objective was completed
    
    # Conditions and triggers
    unlock_conditions: List[ObjectiveTrigger] = field(default_factory=list)
    failure_conditions: List[ObjectiveTrigger] = field(default_factory=list)
    success_conditions: List[ObjectiveTrigger] = field(default_factory=list)
    
    # Mission impact
    success_reward: int = 100  # Points for completion
    failure_penalty: int = 0   # Points lost for failure
    required_for_mission_success: bool = False
    
    # Dynamic properties
    intel_level: float = 1.0   # 0-1, how much intel we have about this objective
    threat_level: float = 0.5  # 0-1, assessed threat level at objective
    priority: int = 0          # Higher numbers = higher priority
    
    # Narrative
    briefing_text: Optional[str] = None
    completion_text: Optional[str] = None
    failure_text: Optional[str] = None
    
    def is_available(self, mission_time: float) -> bool:
        """Check if objective is available for activation."""
        if self.state != ObjectiveState.LOCKED:
            return self.state == ObjectiveState.ACTIVE
            
        if self.activation_time and mission_time >= self.activation_time:
            return True
            
        return False
    
    def is_expired(self, mission_time: float) -> bool:
        """Check if time-limited objective has expired."""
        if not self.time_limit or self.state != ObjectiveState.ACTIVE:
            return False
            
        if self.activation_time:
            elapsed = mission_time - self.activation_time
            return elapsed > self.time_limit
            
        return False
    
    def get_time_remaining(self, mission_time: float) -> Optional[float]:
        """Get time remaining for completion."""
        if not self.time_limit or self.state != ObjectiveState.ACTIVE:
            return None
            
        if self.activation_time:
            elapsed = mission_time - self.activation_time
            return max(0, self.time_limit - elapsed)
            
        return self.time_limit


class DynamicMissionObjectiveSystem:
    """
    Manages dynamic, multi-phase mission objectives with adaptive logic.
    
    Creates engaging missions that evolve based on:
    - Player actions and performance
    - Enemy threat response
    - Time progression and windows of opportunity
    - Intelligence updates and new information
    - Mission phase transitions
    """
    
    def __init__(self, terrain_helper: MissionTerrainHelper):
        self.terrain_helper = terrain_helper
        self.objectives: Dict[str, DynamicObjective] = {}
        self.mission_start_time = time.time()
        self.mission_phase = 1
        self.total_score = 0
        self.events_log: List[Dict[str, Any]] = []
        
        # Callbacks for external systems
        self.objective_callbacks: Dict[str, List[Callable]] = {
            "objective_activated": [],
            "objective_completed": [],
            "objective_failed": [],
            "mission_phase_changed": [],
            "emergency_objective": []
        }
    
    def create_multi_phase_strike_mission(
        self,
        primary_targets: List[Tuple[float, float, float]],
        mission_type: str = "strike",
        difficulty: str = "normal"
    ) -> List[DynamicObjective]:
        """
        Create a complex multi-phase strike mission.
        
        Phases:
        1. SEAD - Suppress air defenses
        2. Strike - Attack primary targets  
        3. BDA - Battle damage assessment
        4. Exfiltration - Safe return
        """
        objectives = []
        
        # Phase 1: SEAD Operations
        sead_objectives = self._create_sead_phase(primary_targets[0], difficulty)
        objectives.extend(sead_objectives)
        
        # Phase 2: Primary Strike
        strike_objectives = self._create_strike_phase(primary_targets, difficulty)
        objectives.extend(strike_objectives)
        
        # Phase 3: Battle Damage Assessment (conditional)
        bda_objective = self._create_bda_phase(primary_targets, difficulty)
        objectives.append(bda_objective)
        
        # Phase 4: Emergency/Opportunity objectives
        emergency_objectives = self._create_emergency_objectives(primary_targets, difficulty)
        objectives.extend(emergency_objectives)
        
        # Add all objectives to system
        for obj in objectives:
            self.add_objective(obj)
        
        return objectives
    
    def _create_sead_phase(
        self,
        target_area: Tuple[float, float, float],
        difficulty: str
    ) -> List[DynamicObjective]:
        """Create SEAD (Suppression of Enemy Air Defenses) objectives."""
        objectives = []
        
        # Primary SEAD objective - destroy SAM sites
        sead_primary = DynamicObjective(
            objective_id="sead_primary",
            name="Suppress Enemy Air Defenses",
            description="Destroy or suppress SAM sites protecting the target area",
            objective_type=ObjectiveType.PRIMARY,
            state=ObjectiveState.ACTIVE,  # Available immediately
            position=target_area,
            time_limit=600 if difficulty == "hard" else None,  # 10 min time limit on hard
            success_reward=200,
            required_for_mission_success=True,
            briefing_text="Intelligence indicates multiple SAM sites defending the target area. "
                         "Neutralize these threats before proceeding to primary targets.",
            completion_text="Air defenses suppressed. Strike package cleared for primary targets."
        )
        
        # Add unlock condition for strike phase
        strike_unlock = ObjectiveTrigger(
            condition=TriggerCondition.OBJECTIVE_COMPLETED,
            parameters={"objective_id": "sead_primary"},
            action="activate",
            target_objective_id="strike_primary"
        )
        sead_primary.success_conditions.append(strike_unlock)
        
        objectives.append(sead_primary)
        
        # Secondary SEAD - destroy radar sites
        if difficulty in ["normal", "hard"]:
            sead_secondary = DynamicObjective(
                objective_id="sead_radar",
                name="Destroy Early Warning Radars",
                description="Eliminate radar sites to blind enemy air defense network",
                objective_type=ObjectiveType.SECONDARY,
                state=ObjectiveState.ACTIVE,
                position=target_area,
                success_reward=100,
                briefing_text="Early warning radars are coordinating the air defense network. "
                             "Destroying them will degrade enemy response capability."
            )
            objectives.append(sead_secondary)
        
        return objectives
    
    def _create_strike_phase(
        self,
        targets: List[Tuple[float, float, float]],
        difficulty: str
    ) -> List[DynamicObjective]:
        """Create primary strike objectives."""
        objectives = []
        
        for i, target_pos in enumerate(targets):
            obj = DynamicObjective(
                objective_id=f"strike_primary_{i+1}",
                name=f"Destroy Primary Target {i+1}",
                description=f"Eliminate high-value target at grid {target_pos[0]:.0f},{target_pos[2]:.0f}",
                objective_type=ObjectiveType.PRIMARY,
                state=ObjectiveState.LOCKED,  # Unlocked by SEAD completion
                position=target_pos,
                success_reward=300,
                required_for_mission_success=True,
                briefing_text=f"Primary target {i+1} is a critical enemy asset. Complete destruction required.",
                completion_text=f"Primary target {i+1} destroyed. Excellent work!"
            )
            
            # Add time pressure on hard difficulty
            if difficulty == "hard":
                obj.time_limit = 300  # 5 minutes per target
                obj.failure_text = "Time expired. Target may have been evacuated or reinforced."
            
            objectives.append(obj)
        
        return objectives
    
    def _create_bda_phase(
        self,
        targets: List[Tuple[float, float, float]],
        difficulty: str
    ) -> DynamicObjective:
        """Create Battle Damage Assessment objective."""
        
        # BDA unlocks when all primary strikes complete
        unlock_triggers = []
        for i, _ in enumerate(targets):
            trigger = ObjectiveTrigger(
                condition=TriggerCondition.OBJECTIVE_COMPLETED,
                parameters={"objective_id": f"strike_primary_{i+1}"},
                action="activate"
            )
            unlock_triggers.append(trigger)
        
        bda_obj = DynamicObjective(
            objective_id="bda_assessment",
            name="Battle Damage Assessment",
            description="Overfly targets to assess damage and confirm destruction",
            objective_type=ObjectiveType.SECONDARY,
            state=ObjectiveState.LOCKED,
            position=targets[0] if targets else None,
            unlock_conditions=unlock_triggers,
            success_reward=150,
            briefing_text="After strikes, conduct low-level BDA pass to confirm target destruction.",
            completion_text="BDA complete. All targets confirmed destroyed."
        )
        
        return bda_obj
    
    def _create_emergency_objectives(
        self,
        area: List[Tuple[float, float, float]],
        difficulty: str
    ) -> List[DynamicObjective]:
        """Create emergency/opportunity objectives that can appear during mission."""
        objectives = []
        
        # Time-sensitive opportunity target
        opportunity = DynamicObjective(
            objective_id="opportunity_convoy",
            name="Destroy Enemy Convoy",
            description="High-value enemy convoy detected. Limited window for engagement.",
            objective_type=ObjectiveType.OPPORTUNITY,
            state=ObjectiveState.LOCKED,
            activation_time=300,  # Appears 5 minutes into mission
            time_limit=180,       # 3 minutes to complete
            success_reward=250,
            briefing_text="FLASH: Enemy convoy with high-value personnel detected. "
                         "Window for engagement is limited.",
            completion_text="Convoy destroyed. Excellent opportunistic strike!",
            failure_text="Convoy escaped. Opportunity lost."
        )
        objectives.append(opportunity)
        
        # Emergency CSAR (Combat Search and Rescue)
        if difficulty in ["normal", "hard"]:
            csar = DynamicObjective(
                objective_id="emergency_csar",
                name="Combat Search and Rescue",
                description="Friendly pilot down. Provide cover for rescue operation.",
                objective_type=ObjectiveType.EMERGENCY,
                state=ObjectiveState.LOCKED,
                time_limit=900,  # 15 minutes before pilot captured
                success_reward=400,
                failure_penalty=200,
                briefing_text="MAYDAY! Friendly pilot down in enemy territory. "
                             "Provide cover for SAR helicopter.",
                completion_text="Pilot recovered successfully. Outstanding airmanship!",
                failure_text="Pilot captured or KIA. Mission failure."
            )
            
            # This can be triggered by player damage
            damage_trigger = ObjectiveTrigger(
                condition=TriggerCondition.PLAYER_DAMAGED,
                parameters={"damage_threshold": 0.5},
                action="activate",
                target_objective_id="emergency_csar"
            )
            csar.unlock_conditions.append(damage_trigger)
            
            objectives.append(csar)
        
        return objectives
    
    def add_objective(self, objective: DynamicObjective) -> None:
        """Add objective to the mission."""
        self.objectives[objective.objective_id] = objective
        
        # Log the addition
        self._log_event("objective_added", {
            "objective_id": objective.objective_id,
            "name": objective.name,
            "type": objective.objective_type.value
        })
    
    def update_mission_state(self, mission_time: float, game_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Update mission state and return any events/changes.
        
        Args:
            mission_time: Current mission time in seconds
            game_state: Current game state (player position, unit states, etc.)
            
        Returns:
            List of events/changes that occurred
        """
        events = []
        
        # Check for objective state changes
        for obj in self.objectives.values():
            # Check unlock conditions
            if obj.state == ObjectiveState.LOCKED:
                if self._check_unlock_conditions(obj, mission_time, game_state):
                    self._activate_objective(obj, mission_time)
                    events.append({
                        "type": "objective_activated",
                        "objective": obj,
                        "message": f"New objective: {obj.name}"
                    })
            
            # Check time expiration
            elif obj.state == ObjectiveState.ACTIVE:
                if obj.is_expired(mission_time):
                    self._fail_objective(obj, mission_time, "Time expired")
                    events.append({
                        "type": "objective_failed",
                        "objective": obj,
                        "reason": "time_expired",
                        "message": f"Objective failed: {obj.name} - Time expired"
                    })
            
            # Check success conditions
            if obj.state == ObjectiveState.ACTIVE:
                if self._check_success_conditions(obj, mission_time, game_state):
                    self._complete_objective(obj, mission_time)
                    events.append({
                        "type": "objective_completed",
                        "objective": obj,
                        "message": f"Objective completed: {obj.name}"
                    })
            
            # Check failure conditions
            if obj.state == ObjectiveState.ACTIVE:
                failure_reason = self._check_failure_conditions(obj, mission_time, game_state)
                if failure_reason:
                    self._fail_objective(obj, mission_time, failure_reason)
                    events.append({
                        "type": "objective_failed",
                        "objective": obj,
                        "reason": failure_reason,
                        "message": f"Objective failed: {obj.name} - {failure_reason}"
                    })
        
        # Check for mission phase transitions
        phase_change = self._check_phase_transition(mission_time, game_state)
        if phase_change:
            events.append(phase_change)
        
        return events
    
    def _check_unlock_conditions(
        self,
        objective: DynamicObjective,
        mission_time: float,
        game_state: Dict[str, Any]
    ) -> bool:
        """Check if objective unlock conditions are met."""
        
        # Time-based activation
        if objective.activation_time and mission_time >= objective.activation_time:
            return True
        
        # Condition-based activation
        for condition in objective.unlock_conditions:
            if self._evaluate_trigger_condition(condition, mission_time, game_state):
                return True
        
        return False
    
    def _check_success_conditions(
        self,
        objective: DynamicObjective,
        mission_time: float,
        game_state: Dict[str, Any]
    ) -> bool:
        """Check if objective success conditions are met."""
        
        # Simple success conditions based on objective type
        if objective.objective_type in [ObjectiveType.PRIMARY, ObjectiveType.SECONDARY]:
            # Check if target units are destroyed
            if objective.target_units:
                destroyed_units = game_state.get("destroyed_units", [])
                return all(unit_id in destroyed_units for unit_id in objective.target_units)
            
            # Check if player entered target area
            if objective.target_area:
                player_pos = game_state.get("player_position")
                if player_pos:
                    area_center, area_radius = objective.target_area
                    distance = math.sqrt(
                        (player_pos[0] - area_center[0])**2 + 
                        (player_pos[1] - area_center[1])**2
                    )
                    return distance <= area_radius
        
        # Custom success conditions
        for condition in objective.success_conditions:
            if self._evaluate_trigger_condition(condition, mission_time, game_state):
                return True
        
        return False
    
    def _check_failure_conditions(
        self,
        objective: DynamicObjective,
        mission_time: float,
        game_state: Dict[str, Any]
    ) -> Optional[str]:
        """Check if objective failure conditions are met."""
        
        for condition in objective.failure_conditions:
            if self._evaluate_trigger_condition(condition, mission_time, game_state):
                return condition.parameters.get("reason", "Failure condition met")
        
        return None
    
    def _evaluate_trigger_condition(
        self,
        trigger: ObjectiveTrigger,
        mission_time: float,
        game_state: Dict[str, Any]
    ) -> bool:
        """Evaluate a specific trigger condition."""
        
        if trigger.condition == TriggerCondition.TIME_ELAPSED:
            threshold = trigger.parameters.get("time", 0)
            return mission_time >= threshold
        
        elif trigger.condition == TriggerCondition.OBJECTIVE_COMPLETED:
            target_id = trigger.parameters.get("objective_id")
            if target_id and target_id in self.objectives:
                return self.objectives[target_id].state == ObjectiveState.COMPLETED
        
        elif trigger.condition == TriggerCondition.UNIT_DESTROYED:
            unit_id = trigger.parameters.get("unit_id")
            destroyed_units = game_state.get("destroyed_units", [])
            return unit_id in destroyed_units
        
        elif trigger.condition == TriggerCondition.AREA_ENTERED:
            area_center = trigger.parameters.get("center")
            area_radius = trigger.parameters.get("radius", 1000)
            player_pos = game_state.get("player_position")
            
            if player_pos and area_center:
                distance = math.sqrt(
                    (player_pos[0] - area_center[0])**2 + 
                    (player_pos[1] - area_center[1])**2
                )
                return distance <= area_radius
        
        elif trigger.condition == TriggerCondition.PLAYER_DAMAGED:
            damage_threshold = trigger.parameters.get("damage_threshold", 0.5)
            player_damage = game_state.get("player_damage", 0.0)
            return player_damage >= damage_threshold
        
        return False
    
    def _activate_objective(self, objective: DynamicObjective, mission_time: float) -> None:
        """Activate an objective."""
        objective.state = ObjectiveState.ACTIVE
        objective.activation_time = mission_time
        
        self._log_event("objective_activated", {
            "objective_id": objective.objective_id,
            "mission_time": mission_time
        })
        
        # Execute callbacks
        for callback in self.objective_callbacks["objective_activated"]:
            callback(objective)
    
    def _complete_objective(self, objective: DynamicObjective, mission_time: float) -> None:
        """Complete an objective."""
        objective.state = ObjectiveState.COMPLETED
        objective.completion_time = mission_time
        self.total_score += objective.success_reward
        
        self._log_event("objective_completed", {
            "objective_id": objective.objective_id,
            "mission_time": mission_time,
            "reward": objective.success_reward
        })
        
        # Process any triggered objectives
        self._process_objective_triggers(objective, mission_time)
        
        # Execute callbacks
        for callback in self.objective_callbacks["objective_completed"]:
            callback(objective)
    
    def _fail_objective(self, objective: DynamicObjective, mission_time: float, reason: str) -> None:
        """Fail an objective."""
        objective.state = ObjectiveState.FAILED
        self.total_score -= objective.failure_penalty
        
        self._log_event("objective_failed", {
            "objective_id": objective.objective_id,
            "mission_time": mission_time,
            "reason": reason,
            "penalty": objective.failure_penalty
        })
        
        # Execute callbacks
        for callback in self.objective_callbacks["objective_failed"]:
            callback(objective, reason)
    
    def _process_objective_triggers(self, completed_objective: DynamicObjective, mission_time: float) -> None:
        """Process triggers from completed objective."""
        
        for trigger in completed_objective.success_conditions:
            if trigger.action == "activate" and trigger.target_objective_id:
                target_obj = self.objectives.get(trigger.target_objective_id)
                if target_obj and target_obj.state == ObjectiveState.LOCKED:
                    self._activate_objective(target_obj, mission_time)
    
    def _check_phase_transition(self, mission_time: float, game_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check if mission should transition to next phase."""
        
        # Simple phase logic based on completed primaries
        primary_objectives = [obj for obj in self.objectives.values() 
                            if obj.objective_type == ObjectiveType.PRIMARY]
        completed_primaries = [obj for obj in primary_objectives 
                             if obj.state == ObjectiveState.COMPLETED]
        
        new_phase = len(completed_primaries) + 1
        
        if new_phase > self.mission_phase:
            old_phase = self.mission_phase
            self.mission_phase = new_phase
            
            return {
                "type": "phase_transition",
                "old_phase": old_phase,
                "new_phase": new_phase,
                "message": f"Mission entering Phase {new_phase}"
            }
        
        return None
    
    def _log_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Log mission event."""
        self.events_log.append({
            "timestamp": time.time(),
            "event_type": event_type,
            "data": data
        })
    
    def get_mission_status(self) -> Dict[str, Any]:
        """Get comprehensive mission status."""
        
        status_counts = {}
        for state in ObjectiveState:
            status_counts[state.value] = sum(
                1 for obj in self.objectives.values() if obj.state == state
            )
        
        active_objectives = [obj for obj in self.objectives.values() 
                           if obj.state == ObjectiveState.ACTIVE]
        
        time_critical = [obj for obj in active_objectives 
                        if obj.time_limit and obj.get_time_remaining(time.time() - self.mission_start_time)]
        
        return {
            "mission_phase": self.mission_phase,
            "total_score": self.total_score,
            "objective_counts": status_counts,
            "active_objectives": len(active_objectives),
            "time_critical_objectives": len(time_critical),
            "mission_success_possible": any(
                obj.required_for_mission_success and obj.state != ObjectiveState.FAILED
                for obj in self.objectives.values()
            )
        }
    
    def generate_mission_briefing(self) -> str:
        """Generate dynamic mission briefing based on current objectives."""
        
        briefing_parts = []
        
        # Mission overview
        primary_count = sum(1 for obj in self.objectives.values() 
                          if obj.objective_type == ObjectiveType.PRIMARY)
        briefing_parts.append(f"MISSION BRIEF: Multi-phase operation with {primary_count} primary objectives.")
        
        # Active objectives
        active_objs = [obj for obj in self.objectives.values() 
                      if obj.state == ObjectiveState.ACTIVE]
        
        if active_objs:
            briefing_parts.append("\nCURRENT OBJECTIVES:")
            for obj in sorted(active_objs, key=lambda x: x.priority, reverse=True):
                priority_text = "HIGH" if obj.objective_type == ObjectiveType.PRIMARY else "MEDIUM"
                briefing_parts.append(f"  • {obj.name} ({priority_text} PRIORITY)")
                if obj.briefing_text:
                    briefing_parts.append(f"    {obj.briefing_text}")
                
                if obj.time_limit:
                    remaining = obj.get_time_remaining(time.time() - self.mission_start_time)
                    if remaining:
                        briefing_parts.append(f"    TIME LIMIT: {remaining:.0f} seconds")
        
        # Intel updates
        briefing_parts.append("\nINTELLIGENCE UPDATES:")
        briefing_parts.append("  • Enemy air defenses active in target area")
        briefing_parts.append("  • Weather conditions favorable")
        briefing_parts.append("  • Additional objectives may become available during mission")
        
        return "\n".join(briefing_parts)
    
    def add_callback(self, event_type: str, callback: Callable) -> None:
        """Add callback for mission events."""
        if event_type in self.objective_callbacks:
            self.objective_callbacks[event_type].append(callback)