from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, Dict, Set
import random


def _infer_team_from_unit_id(unit_id: str) -> Set[str]:
    """
    Intelligently infer allowed teams from unit ID naming conventions.
    
    VTOL VR unit naming patterns:
    - Enemy-only: 'enemy*', 'E*' prefix (e.g., enemyMBT1, ELogisticsTruck, EnemyCarrier)
    - Allied-only: 'allied*', 'A*' prefix (e.g., alliedMBT1, ALogisticTruck, AlliedCarrier)
    - Multi-team: Generic names, AI aircraft, neutral units (e.g., Artillery, F-45A AI, bunker1)
    
    Args:
        unit_id: The unit's ID string from ID_TO_CLASS
        
    Returns:
        Set of allowed team names ("Allied", "Enemy", or both)
    """
    lower_id = unit_id.lower()
    
    # Enemy-specific patterns (but not EscortCruiser, E-4, EF-24, etc.)
    if lower_id.startswith('enemy') or (
        lower_id.startswith('e') and 
        not lower_id.startswith(('esc', 'e-', 'ef-', 'ew'))
    ):
        return {"Enemy"}
    
    # Allied-specific patterns (but not Aircraft: AV-42, ASF-*, AEW-*)
    if lower_id.startswith('allied') or (
        lower_id.startswith('a') and 
        not lower_id.startswith(('av-', 'asf', 'aew', 'abomber', 'aiucav', 'artillery'))
    ):
        return {"Allied"}
    
    # Everything else is multi-team (generic units, AI aircraft, static objects)
    return {"Allied", "Enemy"}


# Auto-generate unit team database from complete unit registry
# This provides full coverage of all ~100 VTOL VR units
def _generate_unit_team_database() -> Dict[str, Set[str]]:
    """Generate complete unit team database from ID_TO_CLASS registry."""
    from pytol.classes.units import ID_TO_CLASS
    
    return {
        unit_id: _infer_team_from_unit_id(unit_id)
        for unit_id in ID_TO_CLASS.keys()
    }


# Unit database: maps unitID -> allowed teams based on VTOL VR naming conventions
# Auto-generated from complete unit registry with intelligent team inference
UNIT_TEAM_DATABASE: Dict[str, Set[str]] = _generate_unit_team_database()


@dataclass
class UnitTemplate:
    """Simple unit template for procedural spawning."""
    unit_type: str
    name: str
    team: str
    behavior: str = "Parked"
    engage_enemies: bool = True
    
    def __post_init__(self):
        """Validate that this unit can be assigned to the specified team."""
        # All units should be in database now (auto-generated from ID_TO_CLASS)
        if self.unit_type not in UNIT_TEAM_DATABASE:
            # This should rarely happen now, but allow with warning
            import warnings
            warnings.warn(
                f"Unit '{self.unit_type}' not in UNIT_TEAM_DATABASE. "
                f"Team assignment cannot be validated.",
                UserWarning
            )
            return
        
        allowed_teams = UNIT_TEAM_DATABASE[self.unit_type]
        if self.team not in allowed_teams:
            raise ValueError(
                f"Unit '{self.unit_type}' cannot be assigned to team '{self.team}'. "
                f"Allowed teams: {allowed_teams}"
            )


class UnitLibrary:
    """Minimal unit template library organized by faction and role.
    
    All units are validated against UNIT_TEAM_DATABASE to ensure
    they can only be assigned to appropriate teams.
    """
    
    # Enemy ground vehicles (faction-specific)
    ENEMY_VEHICLES = [
        UnitTemplate("enemyMBT1", "MBT2-E Tank", "Enemy", behavior="Parked"),
        UnitTemplate("ELogisticsTruck", "Supply Truck", "Enemy", behavior="Parked"),
        UnitTemplate("EnemyAPC", "APC", "Enemy", behavior="Parked"),
    ]
    
    # Enemy air defense (mix of faction-specific and generic)
    ENEMY_SAMS = [
        UnitTemplate("SamBattery1", "SAM Launcher", "Enemy", behavior="Parked"),
        UnitTemplate("ewRadarPyramid", "Early Warning Radar", "Enemy", behavior="Parked"),
        UnitTemplate("staticAAA-20x2", "Z20x2 Anti-Air", "Enemy", behavior="Parked"),
    ]
    
    # Enemy aircraft (generic units used by enemy team)
    ENEMY_AIR = [
        UnitTemplate("F-45A AI", "Hostile F-45", "Enemy", behavior="Patrol"),
        UnitTemplate("ASF-30", "Hostile ASF-30", "Enemy", behavior="Patrol"),
    ]
    
    # Enemy infantry (faction-specific)
    ENEMY_INFANTRY = [
        UnitTemplate("EnemySoldier", "Infantry", "Enemy", behavior="Parked"),
        UnitTemplate("EnemySoldierMANPAD", "Infantry MANPADS", "Enemy", behavior="Parked"),
    ]
    
    # Allied ground vehicles (faction-specific)
    ALLIED_VEHICLES = [
        UnitTemplate("alliedMBT1", "M1 Tank", "Allied", behavior="Parked"),
        UnitTemplate("ALogisticTruck", "Logistics Truck", "Allied", behavior="Parked"),
        UnitTemplate("AlliedIFV", "Boxer IFV", "Allied", behavior="Parked"),
    ]
    
    # Allied air defense (faction-specific)
    ALLIED_SAMS = [
        UnitTemplate("ewRadarPyramid", "Early Warning Radar", "Allied", behavior="Parked"),
        UnitTemplate("staticAAA-20x2", "Z20x2 Anti-Air", "Allied", behavior="Parked"),
    ]
    
    # Allied infantry (faction-specific)
    ALLIED_INFANTRY = [
        UnitTemplate("AlliedSoldier", "Infantry", "Allied", behavior="Parked"),
        UnitTemplate("AlliedSoldierMANPAD", "Infantry MANPADS", "Allied", behavior="Parked"),
    ]
    
    @staticmethod
    def pick_enemy_set(mission_type: str, difficulty: str, rng: random.Random) -> List[UnitTemplate]:
        """
        Select enemy units based on mission type and difficulty.
        
        All returned units are validated to ensure they can be assigned to Enemy team.
        
        Returns list of templates to spawn.
        """
        templates = []
        
        # Base spawn count by difficulty
        count_mult = {"easy": 1, "normal": 2, "hard": 3}.get(difficulty, 2)
        
        if mission_type == "strike":
            # Ground vehicles/structures
            templates.extend(rng.choices(UnitLibrary.ENEMY_VEHICLES, k=2 * count_mult))
            # Add light infantry for defense
            templates.extend(rng.choices(UnitLibrary.ENEMY_INFANTRY, k=count_mult))
        
        elif mission_type == "sead":
            # SAM sites and radars - primary targets
            templates.extend(rng.choices(UnitLibrary.ENEMY_SAMS, k=2 * count_mult))
            # Supporting ground forces
            templates.extend(rng.choices(UnitLibrary.ENEMY_VEHICLES, k=count_mult))
        
        elif mission_type == "cas":
            # Mobile ground targets
            templates.extend(rng.choices(UnitLibrary.ENEMY_VEHICLES, k=2 * count_mult))
            templates.extend(rng.choices(UnitLibrary.ENEMY_INFANTRY, k=2 * count_mult))
        
        elif mission_type == "intercept":
            # Hostile air patrol
            templates.extend(rng.choices(UnitLibrary.ENEMY_AIR, k=count_mult))
            # Add ground radar support
            if difficulty in ["normal", "hard"]:
                templates.append(UnitTemplate("ewRadarPyramid", "Early Warning Radar", "Enemy"))
        
        elif mission_type == "transport":
            # Light ground threats near LZ
            templates.extend(rng.choices(UnitLibrary.ENEMY_INFANTRY, k=count_mult))
            # Add vehicle threats for harder difficulties
            if difficulty == "hard":
                templates.extend(rng.choices(UnitLibrary.ENEMY_VEHICLES, k=1))
        
        return templates
    
    @staticmethod
    def pick_allied_set(mission_type: str, difficulty: str, rng: random.Random) -> List[UnitTemplate]:
        """
        Pick allied units for transport/escort missions.
        
        All returned units are validated to ensure they can be assigned to Allied team.
        """
        templates = []
        
        if mission_type == "transport":
            # Units to pick up/escort
            count = {"easy": 1, "normal": 2, "hard": 3}.get(difficulty, 2)
            templates.extend(rng.choices(UnitLibrary.ALLIED_INFANTRY, k=count))
            
            # Add vehicles for harder difficulties
            if difficulty in ["normal", "hard"]:
                templates.extend(rng.choices(UnitLibrary.ALLIED_VEHICLES, k=1))
        
        return templates
    
    @staticmethod
    def validate_unit_team(unit_id: str, team: str) -> bool:
        """
        Check if a unit can be assigned to a specific team.
        
        Args:
            unit_id: The unit's ID from the game database
            team: The team to assign ("Allied", "Enemy", "Neutral")
            
        Returns:
            True if the unit can be used by this team, False otherwise
        """
        if unit_id not in UNIT_TEAM_DATABASE:
            # Unknown unit - could be new/modded content
            return True
        
        allowed_teams = UNIT_TEAM_DATABASE[unit_id]
        return team in allowed_teams
    
    @staticmethod
    def get_available_units_for_team(team: str) -> List[str]:
        """
        Get all unit IDs that can be assigned to a specific team.
        
        Args:
            team: The team name ("Allied", "Enemy", "Neutral")
            
        Returns:
            List of unit IDs that can be used by this team
        """
        return [
            unit_id for unit_id, allowed_teams in UNIT_TEAM_DATABASE.items()
            if team in allowed_teams
        ]


@dataclass
class SpawnPlan:
    """Plan for spawning units at a location."""
    templates: List[UnitTemplate]
    spawn_center: Tuple[float, float, float]
    spread_radius: float = 500.0
