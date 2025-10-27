"""
Mission Narrative System for dynamic briefings and adaptive storytelling.

This system creates immersive mission narratives that:
- Generate dynamic mission briefings based on current situation
- Adapt storytelling to mission progress and player actions  
- Create realistic military communications and reports
- Provide contextual background and intelligence updates
- Generate emergency situation reports and new objectives
- Maintain narrative consistency across multi-phase missions
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any
from enum import Enum

from pytol.terrain.mission_terrain_helper import MissionTerrainHelper


class NarrativeEvent(Enum):
    """Types of narrative events."""
    MISSION_START = "mission_start"
    OBJECTIVE_UPDATE = "objective_update"
    THREAT_DETECTED = "threat_detected"
    ENGAGEMENT = "engagement"
    CASUALTY = "casualty"
    SUCCESS = "success"
    FAILURE = "failure"
    INTEL_UPDATE = "intel_update"
    WEATHER_CHANGE = "weather_change"
    REINFORCEMENTS = "reinforcements"
    EMERGENCY = "emergency"
    EXTRACTION = "extraction"
    MISSION_COMPLETE = "mission_complete"


class BriefingSection(Enum):
    """Sections of mission briefing."""
    SITUATION = "situation"          # Current tactical situation
    MISSION = "mission"              # Mission objectives and tasks
    EXECUTION = "execution"          # How to execute the mission
    LOGISTICS = "logistics"          # Support and supply information
    COMMAND = "command"              # Command and control structure
    COMMUNICATIONS = "communications" # Radio frequencies and callsigns
    INTELLIGENCE = "intelligence"    # Enemy and friendly intel
    WEATHER = "weather"              # Environmental conditions
    THREATS = "threats"              # Known threats and countermeasures
    CONTINGENCIES = "contingencies"  # Alternative plans and emergencies


class CommunicationType(Enum):
    """Types of military communications."""
    BRIEFING = "briefing"           # Formal mission briefing
    SITREP = "sitrep"              # Situation report
    CONTACT_REPORT = "contact"      # Enemy contact report
    DAMAGE_REPORT = "damage"        # Damage assessment
    STATUS_UPDATE = "status"        # Unit status update
    INTEL_REPORT = "intel"         # Intelligence update
    WARNING = "warning"             # Threat warning
    EMERGENCY = "emergency"         # Emergency communication
    EXTRACTION = "extraction"       # Extraction request
    TASKING = "tasking"            # New task assignment


@dataclass
class NarrativeTemplate:
    """Template for generating narrative content."""
    event_type: NarrativeEvent
    priority: int  # 1-10, higher = more important
    templates: List[str]
    variables: List[str] = field(default_factory=list)
    conditions: Dict[str, Any] = field(default_factory=dict)
    cooldown: float = 0.0  # Minimum time between uses
    last_used: float = 0.0


@dataclass
class MissionBriefing:
    """Complete mission briefing with all sections."""
    mission_id: str
    mission_name: str
    classification: str = "CONFIDENTIAL"
    
    # Briefing sections
    situation: str = ""
    mission_statement: str = ""
    execution_summary: str = ""
    logistics_info: str = ""
    command_structure: str = ""
    communications: str = ""
    intelligence: str = ""
    weather_conditions: str = ""
    threat_assessment: str = ""
    contingencies: str = ""
    
    # Metadata
    briefing_time: float = field(default_factory=time.time)
    briefing_officer: str = "INTEL-01"
    operational_area: str = "UNKNOWN"
    estimated_duration: str = "2-4 HOURS"


@dataclass
class SituationReport:
    """Dynamic situation report."""
    report_id: str
    timestamp: float
    reporting_unit: str
    report_type: CommunicationType
    
    # Report content
    summary: str
    details: List[str] = field(default_factory=list)
    position: Optional[Tuple[float, float, float]] = None
    units_involved: List[str] = field(default_factory=list)
    casualties: Dict[str, int] = field(default_factory=dict)
    enemy_activity: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    
    # Classification and routing
    classification: str = "CONFIDENTIAL"
    recipients: List[str] = field(default_factory=list)
    urgency: str = "ROUTINE"  # FLASH, IMMEDIATE, PRIORITY, ROUTINE


class MissionNarrativeSystem:
    """
    Dynamic mission narrative system for immersive storytelling.
    
    Features:
    - Procedural mission briefing generation
    - Adaptive narrative based on mission progress
    - Realistic military communications
    - Dynamic situation reports
    - Emergency narrative updates
    - Multi-phase mission continuity
    """
    
    def __init__(self, terrain_helper: MissionTerrainHelper):
        self.terrain_helper = terrain_helper
        
        # Narrative state
        self.current_mission: Optional[MissionBriefing] = None
        self.narrative_events: List[Dict[str, Any]] = []
        self.situation_reports: List[SituationReport] = []
        self.active_narratives: List[str] = []
        
        # Templates and content
        self.narrative_templates = self._initialize_narrative_templates()
        self.callsign_generator = CallsignGenerator()
        self.military_vocabulary = self._initialize_military_vocabulary()
        
        # Story state tracking
        self.story_variables: Dict[str, Any] = {}
        self.character_relationships: Dict[str, Dict[str, float]] = {}
        self.ongoing_plots: List[Dict[str, Any]] = []
        
    def generate_mission_briefing(
        self,
        mission_data: Dict[str, Any],
        force_composition: Dict[str, Any],
        threat_assessment: Dict[str, Any],
        environmental_data: Dict[str, Any]
    ) -> MissionBriefing:
        """Generate comprehensive mission briefing."""
        
        mission_name = self._generate_mission_name(mission_data)
        briefing = MissionBriefing(
            mission_id=mission_data.get('mission_id', 'M001'),
            mission_name=mission_name,
            operational_area=self._get_operational_area_name(),
            briefing_officer=self.callsign_generator.get_intel_callsign()
        )
        
        # Generate each briefing section
        briefing.situation = self._generate_situation_section(
            mission_data, threat_assessment, environmental_data
        )
        
        briefing.mission_statement = self._generate_mission_section(
            mission_data, force_composition
        )
        
        briefing.execution_summary = self._generate_execution_section(
            mission_data, force_composition
        )
        
        briefing.logistics_info = self._generate_logistics_section(
            force_composition, mission_data
        )
        
        briefing.command_structure = self._generate_command_section(
            force_composition
        )
        
        briefing.communications = self._generate_communications_section(
            force_composition
        )
        
        briefing.intelligence = self._generate_intelligence_section(
            threat_assessment, mission_data
        )
        
        briefing.weather_conditions = self._generate_weather_section(
            environmental_data
        )
        
        briefing.threat_assessment = self._generate_threat_section(
            threat_assessment
        )
        
        briefing.contingencies = self._generate_contingencies_section(
            mission_data, threat_assessment
        )
        
        self.current_mission = briefing
        return briefing
    
    def _generate_mission_name(self, mission_data: Dict[str, Any]) -> str:
        """Generate mission name/codename."""
        
        mission_type = mission_data.get('type', 'patrol')
        
        # Operation name generators
        operation_adjectives = [
            "THUNDER", "LIGHTNING", "STORM", "STEEL", "IRON", "GOLDEN",
            "CRIMSON", "BLUE", "SILVER", "PHANTOM", "SHADOW", "EAGLE",
            "HAWK", "VIPER", "COBRA", "WOLF", "TIGER", "LION"
        ]
        
        operation_nouns = [
            "STRIKE", "SWEEP", "HAMMER", "SPEAR", "SHIELD", "SWORD",
            "ARROW", "BLADE", "STORM", "FURY", "REVENGE", "JUSTICE",
            "FREEDOM", "LIBERTY", "VICTORY", "TRIUMPH", "VALOR", "HONOR"
        ]
        
        # Mission-specific names
        if mission_type in ['cas', 'close_air_support']:
            return f"OPERATION {random.choice(['GUARDIAN', 'PROTECTOR', 'SHIELD'])} {random.choice(operation_nouns)}"
        elif mission_type in ['sead', 'wild_weasel']:
            return f"OPERATION {random.choice(['IRON', 'STEEL', 'THUNDER'])} {random.choice(['HAMMER', 'STORM', 'STRIKE'])}"
        elif mission_type in ['cap', 'air_superiority']:
            return f"OPERATION {random.choice(['EAGLE', 'HAWK', 'FALCON'])} {random.choice(['TALON', 'WING', 'STRIKE'])}"
        else:
            return f"OPERATION {random.choice(operation_adjectives)} {random.choice(operation_nouns)}"
    
    def _generate_situation_section(
        self,
        mission_data: Dict[str, Any],
        threat_assessment: Dict[str, Any],
        environmental_data: Dict[str, Any]
    ) -> str:
        """Generate situation section of briefing."""
        
        situation_templates = [
            "Intelligence reports indicate {enemy_activity} in the {operational_area}. "
            "Friendly forces are currently {friendly_status} with {force_posture}. "
            "Weather conditions are {weather_summary} with visibility {visibility}.",
            
            "The tactical situation has developed as follows: {enemy_forces} have been "
            "observed {enemy_activity} in grid squares {grid_references}. "
            "Our forces maintain {friendly_posture} while monitoring the situation.",
            
            "Current SITREP: Enemy strength estimated at {enemy_strength} with "
            "{enemy_capabilities}. Friendly forces report {friendly_status} and are "
            "prepared for {mission_type} operations."
        ]
        
        # Fill in variables
        variables = {
            'enemy_activity': self._get_enemy_activity_description(threat_assessment),
            'operational_area': self._get_operational_area_name(),
            'friendly_status': self._get_friendly_status_description(),
            'force_posture': self._get_force_posture_description(),
            'weather_summary': self._get_weather_summary(environmental_data),
            'visibility': self._get_visibility_description(environmental_data),
            'enemy_forces': self._get_enemy_force_description(threat_assessment),
            'grid_references': self._generate_grid_references(),
            'friendly_posture': self._get_friendly_posture_description(),
            'enemy_strength': self._get_enemy_strength_estimate(threat_assessment),
            'enemy_capabilities': self._get_enemy_capabilities(threat_assessment),
            'mission_type': mission_data.get('type', 'patrol').upper()
        }
        
        template = random.choice(situation_templates)
        return self._fill_template(template, variables)
    
    def _generate_mission_section(
        self,
        mission_data: Dict[str, Any],
        force_composition: Dict[str, Any]
    ) -> str:
        """Generate mission statement section."""
        
        mission_type = mission_data.get('type', 'patrol')
        
        mission_templates = {
            'patrol': [
                "Conduct combat air patrol in assigned sector {patrol_area}. "
                "Maintain air superiority and engage hostile aircraft per ROE. "
                "Report all enemy activity and maintain station until relieved."
            ],
            'cas': [
                "Provide close air support to ground forces in contact. "
                "Primary targets are {target_types} at grid {target_grid}. "
                "Coordinate with {ground_controller} for target designation."
            ],
            'sead': [
                "Conduct suppression of enemy air defenses in AO {area_name}. "
                "Primary targets include {sam_types} and early warning radars. "
                "Clear air corridors for follow-on strike packages."
            ],
            'strike': [
                "Execute precision strike against {target_description} at "
                "coordinates {target_coordinates}. Time-on-target {tot}. "
                "Minimize collateral damage and confirm target destruction."
            ]
        }
        
        templates = mission_templates.get(mission_type, mission_templates['patrol'])
        template = random.choice(templates)
        
        variables = {
            'patrol_area': self._generate_patrol_area_description(),
            'target_types': self._get_target_types_description(mission_data),
            'target_grid': self._generate_grid_reference(),
            'ground_controller': self.callsign_generator.get_jtac_callsign(),
            'area_name': self._get_operational_area_name(),
            'sam_types': self._get_sam_types_description(),
            'target_description': self._get_target_description(mission_data),
            'target_coordinates': self._generate_coordinates(),
            'tot': self._generate_time_on_target()
        }
        
        return self._fill_template(template, variables)
    
    def _generate_execution_section(
        self,
        mission_data: Dict[str, Any],
        force_composition: Dict[str, Any]
    ) -> str:
        """Generate execution section."""
        
        execution_template = (
            "Phase 1: {phase1_description}\n"
            "Phase 2: {phase2_description}\n"
            "Phase 3: {phase3_description}\n\n"
            "Formation: {formation_type}\n"
            "Ingress Route: {ingress_route}\n"
            "Egress Route: {egress_route}\n"
            "Alternate Landing Site: {alternate_base}"
        )
        
        variables = {
            'phase1_description': self._get_phase_description(1, mission_data),
            'phase2_description': self._get_phase_description(2, mission_data),
            'phase3_description': self._get_phase_description(3, mission_data),
            'formation_type': self._get_formation_description(force_composition),
            'ingress_route': self._generate_route_description('ingress'),
            'egress_route': self._generate_route_description('egress'),
            'alternate_base': self._get_alternate_base_name()
        }
        
        return self._fill_template(execution_template, variables)
    
    def _generate_logistics_section(
        self,
        force_composition: Dict[str, Any],
        mission_data: Dict[str, Any]
    ) -> str:
        """Generate logistics section."""
        
        logistics_template = (
            "Fuel State: Minimum {min_fuel}% for RTB\n"
            "Armament: {weapon_loadout}\n"
            "Tanker Support: {tanker_info}\n"
            "CSAR: {csar_info}\n"
            "Medical: {medical_info}\n"
            "Recovery: {recovery_info}"
        )
        
        variables = {
            'min_fuel': random.randint(20, 30),
            'weapon_loadout': self._generate_weapon_loadout(mission_data),
            'tanker_info': self._generate_tanker_info(),
            'csar_info': self._generate_csar_info(),
            'medical_info': self._generate_medical_info(),
            'recovery_info': self._generate_recovery_info()
        }
        
        return self._fill_template(logistics_template, variables)
    
    def _generate_communications_section(
        self,
        force_composition: Dict[str, Any]
    ) -> str:
        """Generate communications section."""
        
        comm_template = (
            "Primary Frequency: {primary_freq}\n"
            "Secondary Frequency: {secondary_freq}\n"
            "Guard Frequency: {guard_freq}\n"
            "Package Frequency: {package_freq}\n"
            "AWACS: {awacs_callsign} on {awacs_freq}\n"
            "Tanker: {tanker_callsign} on {tanker_freq}\n"
            "JTAC: {jtac_callsign} on {jtac_freq}"
        )
        
        variables = {
            'primary_freq': f"{random.randint(225, 399)}.{random.randint(10, 99):02d}",
            'secondary_freq': f"{random.randint(225, 399)}.{random.randint(10, 99):02d}",
            'guard_freq': "243.00",
            'package_freq': f"{random.randint(225, 399)}.{random.randint(10, 99):02d}",
            'awacs_callsign': self.callsign_generator.get_awacs_callsign(),
            'awacs_freq': f"{random.randint(225, 399)}.{random.randint(10, 99):02d}",
            'tanker_callsign': self.callsign_generator.get_tanker_callsign(),
            'tanker_freq': f"{random.randint(225, 399)}.{random.randint(10, 99):02d}",
            'jtac_callsign': self.callsign_generator.get_jtac_callsign(),
            'jtac_freq': f"{random.randint(225, 399)}.{random.randint(10, 99):02d}"
        }
        
        return self._fill_template(comm_template, variables)
    
    def generate_situation_report(
        self,
        event_data: Dict[str, Any],
        reporting_unit: str,
        report_type: CommunicationType
    ) -> SituationReport:
        """Generate dynamic situation report."""
        
        report_id = f"SITREP-{int(time.time())}"
        
        sitrep = SituationReport(
            report_id=report_id,
            timestamp=time.time(),
            reporting_unit=reporting_unit,
            report_type=report_type
        )
        
        # Generate report content based on type
        if report_type == CommunicationType.CONTACT_REPORT:
            sitrep.summary = self._generate_contact_report_summary(event_data)
            sitrep.details = self._generate_contact_report_details(event_data)
            sitrep.urgency = "IMMEDIATE"
            
        elif report_type == CommunicationType.DAMAGE_REPORT:
            sitrep.summary = self._generate_damage_report_summary(event_data)
            sitrep.details = self._generate_damage_report_details(event_data)
            sitrep.urgency = "PRIORITY"
            
        elif report_type == CommunicationType.STATUS_UPDATE:
            sitrep.summary = self._generate_status_update_summary(event_data)
            sitrep.details = self._generate_status_update_details(event_data)
            sitrep.urgency = "ROUTINE"
            
        elif report_type == CommunicationType.INTEL_REPORT:
            sitrep.summary = self._generate_intel_report_summary(event_data)
            sitrep.details = self._generate_intel_report_details(event_data)
            sitrep.urgency = "PRIORITY"
        
        # Add to report history
        self.situation_reports.append(sitrep)
        
        return sitrep
    
    def update_narrative_based_on_events(self, events: List[Dict[str, Any]]) -> List[str]:
        """Update ongoing narrative based on mission events."""
        
        narrative_updates = []
        
        for event in events:
            event_type = event.get('type')
            
            if event_type == 'enemy_contact':
                update = self._generate_contact_narrative(event)
                narrative_updates.append(update)
                
            elif event_type == 'objective_complete':
                update = self._generate_objective_complete_narrative(event)
                narrative_updates.append(update)
                
            elif event_type == 'unit_damaged':
                update = self._generate_damage_narrative(event)
                narrative_updates.append(update)
                
            elif event_type == 'weather_change':
                update = self._generate_weather_change_narrative(event)
                narrative_updates.append(update)
                
            elif event_type == 'reinforcements_available':
                update = self._generate_reinforcement_narrative(event)
                narrative_updates.append(update)
        
        # Update story variables based on events
        self._update_story_variables(events)
        
        return narrative_updates
    
    def generate_emergency_briefing(self, emergency_data: Dict[str, Any]) -> str:
        """Generate emergency briefing for critical situations."""
        
        emergency_templates = {
            'pilot_down': [
                "MAYDAY MAYDAY MAYDAY. {pilot_callsign} is down at grid {crash_grid}. "
                "CSAR package is being assembled. All units maintain overwatch and "
                "report any enemy activity in the vicinity."
            ],
            'sam_threat': [
                "THREAT WARNING. SA-{sam_number} system active at bearing {bearing} "
                "from {reference_point}. All aircraft maintain altitude above "
                "{safe_altitude} feet and use appropriate countermeasures."
            ],
            'weather_emergency': [
                "WEATHER EMERGENCY. Severe {weather_type} moving into AO. "
                "Visibility dropping to {visibility} with {wind_conditions}. "
                "All units prepare for emergency recovery procedures."
            ],
            'mission_abort': [
                "ABORT ABORT ABORT. Mission {mission_id} is aborted due to "
                "{abort_reason}. All units return to base immediately via "
                "emergency egress routes. Report status upon landing."
            ]
        }
        
        emergency_type = emergency_data.get('type', 'general')
        templates = emergency_templates.get(emergency_type, ["Emergency situation reported."])
        template = random.choice(templates)
        
        return self._fill_template(template, emergency_data)
    
    def _generate_contact_narrative(self, event: Dict[str, Any]) -> str:
        """Generate narrative for enemy contact."""
        
        contact_templates = [
            "{reporting_unit} reports contact with {enemy_type} at {position}. "
            "Enemy is heading {heading} at {altitude} feet. Threat level assessed as {threat_level}.",
            
            "CONTACT! {enemy_type} detected by {reporting_unit}. "
            "Range {range} nautical miles, bearing {bearing}. Attempting identification.",
            
            "{reporting_unit} has visual on {enemy_count} {enemy_type}. "
            "Target appears to be {enemy_activity}. Requesting permission to engage."
        ]
        
        template = random.choice(contact_templates)
        return self._fill_template(template, event)
    
    def _generate_objective_complete_narrative(self, event: Dict[str, Any]) -> str:
        """Generate narrative for completed objectives."""
        
        completion_templates = [
            "Objective {objective_id} completed successfully. {completion_details} "
            "BDA indicates {battle_damage_assessment}. Moving to next phase.",
            
            "MISSION SUCCESS. Target {target_id} has been neutralized. "
            "Secondary explosions observed. RTB for debrief.",
            
            "Phase {phase_number} complete. {success_details} "
            "All units report ready for next tasking."
        ]
        
        template = random.choice(completion_templates)
        return self._fill_template(template, event)
    
    # Helper methods for content generation
    def _get_operational_area_name(self) -> str:
        """Get operational area name."""
        area_names = [
            "SECTOR ALPHA", "SECTOR BRAVO", "SECTOR CHARLIE", "SECTOR DELTA",
            "AO THUNDER", "AO LIGHTNING", "AO STORM", "AO STEEL",
            "GRID TANGO", "GRID UNIFORM", "GRID VICTOR", "GRID WHISKEY"
        ]
        return random.choice(area_names)
    
    def _get_enemy_activity_description(self, threat_assessment: Dict[str, Any]) -> str:
        """Get enemy activity description."""
        activities = [
            "increased air patrols", "defensive positioning", "radar emissions",
            "communication intercepts", "troop movements", "equipment repositioning",
            "training exercises", "combat air patrols", "ground vehicle movement"
        ]
        return random.choice(activities)
    
    def _get_friendly_status_description(self) -> str:
        """Get friendly force status."""
        statuses = [
            "combat ready", "mission capable", "fully operational",
            "at high readiness", "prepared for operations", "standing by"
        ]
        return random.choice(statuses)
    
    def _get_weather_summary(self, environmental_data: Dict[str, Any]) -> str:
        """Get weather summary."""
        weather_conditions = [
            "clear with scattered clouds", "overcast with light precipitation",
            "partly cloudy with good visibility", "clear skies with unlimited visibility",
            "moderate turbulence expected", "calm conditions with light winds"
        ]
        return random.choice(weather_conditions)
    
    def _fill_template(self, template: str, variables: Dict[str, Any]) -> str:
        """Fill template with variables."""
        result = template
        for key, value in variables.items():
            placeholder = f"{{{key}}}"
            if placeholder in result:
                result = result.replace(placeholder, str(value))
        return result
    
    def _initialize_narrative_templates(self) -> Dict[NarrativeEvent, List[NarrativeTemplate]]:
        """Initialize narrative template library."""
        templates = {}
        
        # Mission start templates
        templates[NarrativeEvent.MISSION_START] = [
            NarrativeTemplate(
                event_type=NarrativeEvent.MISSION_START,
                priority=10,
                templates=[
                    "Mission {mission_name} is commencing. All units report ready.",
                    "EXECUTE EXECUTE EXECUTE. {mission_name} is now active.",
                    "Mission start time: {start_time}. Good hunting, {pilot_callsigns}."
                ]
            )
        ]
        
        # Threat detected templates
        templates[NarrativeEvent.THREAT_DETECTED] = [
            NarrativeTemplate(
                event_type=NarrativeEvent.THREAT_DETECTED,
                priority=8,
                templates=[
                    "THREAT WARNING: {threat_type} detected at {position}.",
                    "All units be advised: {threat_description} in your vicinity.",
                    "SPIKE! {threat_type} has locked onto friendly aircraft."
                ]
            )
        ]
        
        return templates
    
    def _initialize_military_vocabulary(self) -> Dict[str, List[str]]:
        """Initialize military vocabulary for realistic communications."""
        return {
            'acknowledgments': ["Roger", "Copy", "Wilco", "Affirmative", "Understood"],
            'negatives': ["Negative", "Unable", "Cannot comply", "Stand by"],
            'urgency': ["Immediate", "Priority", "Routine", "Flash"],
            'directions': ["North", "South", "East", "West", "Northwest", "Southeast"],
            'altitudes': ["Angels", "Cherubs", "Flight level", "Altitude"],
            'weapons': ["Fox 1", "Fox 2", "Fox 3", "Guns guns guns", "Rifle", "Magnum"]
        }
    
    # Additional helper methods (simplified implementations)
    def _get_force_posture_description(self) -> str:
        return random.choice(["defensive posture", "offensive stance", "combat readiness"])
    
    def _generate_grid_references(self) -> str:
        return f"Grid {random.randint(10,99)}{random.choice(['A','B','C','D'])}"
    
    def _get_friendly_posture_description(self) -> str:
        return random.choice(["high alert status", "normal readiness", "combat ready"])
    
    def _get_enemy_strength_estimate(self, threat_assessment: Dict[str, Any]) -> str:
        return random.choice(["company strength", "battalion strength", "reinforced platoon"])
    
    def _get_enemy_capabilities(self, threat_assessment: Dict[str, Any]) -> str:
        return random.choice(["anti-air capabilities", "armored vehicles", "infantry units"])
    
    def _generate_patrol_area_description(self) -> str:
        return f"CAP Station {random.choice(['Alpha', 'Bravo', 'Charlie'])}"
    
    def _get_target_types_description(self, mission_data: Dict[str, Any]) -> str:
        return random.choice(["armored vehicles", "infantry positions", "supply convoys"])
    
    def _generate_grid_reference(self) -> str:
        return f"{random.randint(10,99)}{random.choice(['A','B','C','D'])}{random.randint(100,999)}"
    
    def _get_sam_types_description(self) -> str:
        return random.choice(["SA-6 and SA-8 systems", "SA-2 and SA-3 sites", "MANPADS and AAA"])
    
    def _get_target_description(self, mission_data: Dict[str, Any]) -> str:
        return random.choice(["command bunker", "radar installation", "supply depot"])
    
    def _generate_coordinates(self) -> str:
        return f"{random.randint(35,45)}.{random.randint(100,999)} {random.randint(25,35)}.{random.randint(100,999)}"
    
    def _generate_time_on_target(self) -> str:
        hour = random.randint(10, 23)
        minute = random.randint(0, 59)
        return f"{hour:02d}{minute:02d}Z"
    
    def _get_phase_description(self, phase: int, mission_data: Dict[str, Any]) -> str:
        phases = {
            1: "Ingress and target area setup",
            2: "Primary mission execution", 
            3: "Egress and return to base"
        }
        return phases.get(phase, "Mission phase")
    
    def _get_formation_description(self, force_composition: Dict[str, Any]) -> str:
        return random.choice(["Finger Four", "Line Abreast", "Vic Formation"])
    
    def _generate_route_description(self, route_type: str) -> str:
        return f"Route {random.choice(['Alpha', 'Bravo', 'Charlie'])} via waypoint {random.randint(1,9)}"
    
    def _get_alternate_base_name(self) -> str:
        return random.choice(["AIRBASE DELTA", "FIELD ECHO", "STRIP FOXTROT"])
    
    def _generate_weapon_loadout(self, mission_data: Dict[str, Any]) -> str:
        return random.choice(["4x AIM-120C, 2x AIM-9X", "6x AGM-65D, 2x AIM-9X", "2x GBU-12, 4x AIM-120C"])
    
    def _generate_tanker_info(self) -> str:
        return f"{self.callsign_generator.get_tanker_callsign()} at FL250, Track {random.choice(['North', 'South'])}"
    
    def _generate_csar_info(self) -> str:
        return f"{self.callsign_generator.get_csar_callsign()} on standby at {self._get_alternate_base_name()}"
    
    def _generate_medical_info(self) -> str:
        return "Level 2 medical facility available at home base"
    
    def _generate_recovery_info(self) -> str:
        return "Primary: Home base. Secondary: Field ECHO"
    
    def _generate_command_section(self, force_composition: Dict[str, Any]) -> str:
        return f"Mission Commander: {self.callsign_generator.get_flight_lead_callsign()}\nPackage Commander: {self.callsign_generator.get_package_callsign()}"
    
    def _generate_intelligence_section(self, threat_assessment: Dict[str, Any], mission_data: Dict[str, Any]) -> str:
        return "Enemy forces assessed as company strength with anti-air capabilities. No significant changes to threat picture."
    
    def _generate_weather_section(self, environmental_data: Dict[str, Any]) -> str:
        return "Clear skies, visibility 10+ nm, winds 270/15, temperature 15°C"
    
    def _generate_threat_section(self, threat_assessment: Dict[str, Any]) -> str:
        return "Primary threats: SA-6/8 SAM systems, AAA concentrations, possible MANPADS"
    
    def _generate_contingencies_section(self, mission_data: Dict[str, Any], threat_assessment: Dict[str, Any]) -> str:
        return "ABORT: RTB immediately via emergency egress. EMERGENCY: Follow established SAR procedures."
    
    def _get_visibility_description(self, environmental_data: Dict[str, Any]) -> str:
        return random.choice(["10+ nautical miles", "5-10 nautical miles", "unlimited"])
    
    def _get_enemy_force_description(self, threat_assessment: Dict[str, Any]) -> str:
        return random.choice(["Enemy mechanized units", "Hostile air defense", "Unknown aircraft"])
    
    def _generate_contact_report_summary(self, event_data: Dict[str, Any]) -> str:
        return f"Contact with {event_data.get('enemy_type', 'unknown')} at {event_data.get('position', 'unknown location')}"
    
    def _generate_contact_report_details(self, event_data: Dict[str, Any]) -> List[str]:
        return [
            f"Contact type: {event_data.get('enemy_type', 'Unknown')}",
            f"Position: {event_data.get('position', 'Unknown')}",
            f"Heading: {event_data.get('heading', 'Unknown')}",
            f"Threat level: {event_data.get('threat_level', 'Unknown')}"
        ]
    
    def _generate_damage_report_summary(self, event_data: Dict[str, Any]) -> str:
        return f"Damage report from {event_data.get('unit', 'unknown unit')}"
    
    def _generate_damage_report_details(self, event_data: Dict[str, Any]) -> List[str]:
        return [
            f"Unit: {event_data.get('unit', 'Unknown')}",
            f"Damage level: {event_data.get('damage', 'Unknown')}",
            f"Systems affected: {event_data.get('systems', 'Unknown')}",
            f"Mission capability: {event_data.get('capability', 'Unknown')}"
        ]
    
    def _generate_status_update_summary(self, event_data: Dict[str, Any]) -> str:
        return f"Status update from {event_data.get('unit', 'unknown unit')}"
    
    def _generate_status_update_details(self, event_data: Dict[str, Any]) -> List[str]:
        return [
            f"Unit: {event_data.get('unit', 'Unknown')}",
            f"Position: {event_data.get('position', 'Unknown')}",
            f"Fuel: {event_data.get('fuel', 'Unknown')}%",
            f"Ammunition: {event_data.get('ammo', 'Unknown')}"
        ]
    
    def _generate_intel_report_summary(self, event_data: Dict[str, Any]) -> str:
        return f"Intelligence update: {event_data.get('intel_type', 'General update')}"
    
    def _generate_intel_report_details(self, event_data: Dict[str, Any]) -> List[str]:
        return [
            f"Source: {event_data.get('source', 'Unknown')}",
            f"Reliability: {event_data.get('reliability', 'Unknown')}",
            f"Information: {event_data.get('information', 'Unknown')}"
        ]
    
    def _generate_damage_narrative(self, event: Dict[str, Any]) -> str:
        return f"{event.get('unit', 'Unknown unit')} reports {event.get('damage_type', 'damage')}. Mission capability {event.get('capability_status', 'unknown')}."
    
    def _generate_weather_change_narrative(self, event: Dict[str, Any]) -> str:
        return f"Weather update: {event.get('weather_change', 'Conditions changing')}. All units advised."
    
    def _generate_reinforcement_narrative(self, event: Dict[str, Any]) -> str:
        return f"Reinforcements available: {event.get('reinforcement_type', 'Additional units')} standing by for tasking."
    
    def _update_story_variables(self, events: List[Dict[str, Any]]) -> None:
        """Update story variables based on events."""
        for event in events:
            if event.get('type') == 'enemy_contact':
                self.story_variables['enemy_contacts'] = self.story_variables.get('enemy_contacts', 0) + 1
            elif event.get('type') == 'objective_complete':
                self.story_variables['objectives_completed'] = self.story_variables.get('objectives_completed', 0) + 1


class CallsignGenerator:
    """Generate realistic military callsigns."""
    
    def __init__(self):
        self.flight_callsigns = [
            "VIPER", "EAGLE", "FALCON", "HAWK", "RAVEN", "PHOENIX",
            "THUNDER", "LIGHTNING", "STORM", "STEEL", "IRON", "GOLD"
        ]
        
        self.support_callsigns = {
            'awacs': ["MAGIC", "FOCUS", "OVERLORD", "DARKSTAR", "WIZARD"],
            'tanker': ["TEXACO", "SHELL", "ARCO", "EXXON", "CITGO"],
            'jtac': ["WARRIOR", "TITAN", "KNIGHT", "ANVIL", "HAMMER"],
            'csar': ["PEDRO", "JOLLY", "DUSTOFF", "GUARDIAN", "LIFELINE"]
        }
    
    def get_flight_callsign(self, flight_number: int = 1) -> str:
        """Get flight callsign with number."""
        return f"{random.choice(self.flight_callsigns)} {flight_number}"
    
    def get_awacs_callsign(self) -> str:
        """Get AWACS callsign."""
        return random.choice(self.support_callsigns['awacs'])
    
    def get_tanker_callsign(self) -> str:
        """Get tanker callsign."""
        return f"{random.choice(self.support_callsigns['tanker'])}-{random.randint(1,9)}"
    
    def get_jtac_callsign(self) -> str:
        """Get JTAC callsign."""
        return f"{random.choice(self.support_callsigns['jtac'])}-{random.randint(10,99)}"
    
    def get_csar_callsign(self) -> str:
        """Get CSAR callsign."""
        return f"{random.choice(self.support_callsigns['csar'])}-{random.randint(1,9)}"
    
    def get_intel_callsign(self) -> str:
        """Get intelligence officer callsign."""
        return f"INTEL-{random.randint(10,99)}"
    
    def get_flight_lead_callsign(self) -> str:
        """Get flight lead callsign."""
        return f"{random.choice(self.flight_callsigns)} LEAD"
    
    def get_package_callsign(self) -> str:
        """Get package commander callsign."""
        return f"PACKAGE {random.choice(['ALPHA', 'BRAVO', 'CHARLIE'])}"