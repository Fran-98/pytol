from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Any


@dataclass
class ObjectiveSpec:
    """Specification for creating a mission objective."""
    id_name: str
    name: str
    info: str = ""
    required: bool = True
    # Optional specifics for different objective types
    trigger_radius: Optional[float] = None
    spherical_radius: Optional[bool] = None
    # For Destroy objectives - list of unit IDs to destroy
    target_units: List[int] = field(default_factory=list)
    # Minimum completion count for Destroy objectives
    min_required: Optional[int] = None
    # Waypoint ID if objective is location-based
    waypoint_id: Optional[int] = None


@dataclass
class ObjectivePlan:
    """Complete plan of objectives for a mission."""
    objectives: List[ObjectiveSpec] = field(default_factory=list)
    # Additional context for objective creation
    context: dict = field(default_factory=dict)


class ObjectiveManager:
    """Plans primary/secondary objectives based on mission type and spawned units."""

    def plan(
        self, 
        mission_type: str,
        difficulty: str = "normal",
        spawned_units: Optional[List[Any]] = None
    ) -> ObjectivePlan:
        """
        Create objectives appropriate for the mission type.
        
        Args:
            mission_type: Type of mission (strike, cas, sead, etc.)
            difficulty: Difficulty level affecting objective requirements
            spawned_units: List of units spawned in the mission (for Destroy objectives)
            
        Returns:
            ObjectivePlan with primary and optional secondary objectives
        """
        objectives = []
        context = {}
        
        if mission_type == "strike":
            # Strike: Primary is navigate to target, Secondary is destroy ground units
            objectives.append(
                ObjectiveSpec(
                    id_name="Fly_To",
                    name="Proceed to Strike Zone",
                    info="Navigate to the designated strike coordinates",
                    trigger_radius=800.0,
                    spherical_radius=False,
                    required=True
                )
            )
            
            # If we have ground units, add destroy objective
            if spawned_units:
                unit_ids = [u.id for u in spawned_units if hasattr(u, 'id') and u.team == "Enemy"]
                if unit_ids:
                    min_kills = max(1, len(unit_ids) // 2) if difficulty == "easy" else len(unit_ids)
                    objectives.append(
                        ObjectiveSpec(
                            id_name="Destroy",
                            name="Destroy Enemy Forces",
                            info=f"Eliminate at least {min_kills} enemy units in the area",
                            target_units=unit_ids,
                            min_required=min_kills,
                            required=True
                        )
                    )
        
        elif mission_type == "sead":
            # SEAD: Destroy SAM sites and radars
            objectives.append(
                ObjectiveSpec(
                    id_name="Fly_To",
                    name="Approach SEAD Zone",
                    info="Navigate to the air defense suppression area",
                    trigger_radius=1000.0,
                    spherical_radius=False,
                    required=True
                )
            )
            
            if spawned_units:
                # Find SAM and radar units
                sam_radar_ids = [
                    u.id for u in spawned_units 
                    if hasattr(u, 'id') and u.team == "Enemy" 
                    and any(kw in u.unit_type.lower() for kw in ['sam', 'radar', 'ewradar'])
                ]
                if sam_radar_ids:
                    objectives.append(
                        ObjectiveSpec(
                            id_name="Destroy",
                            name="Suppress Air Defenses",
                            info="Destroy enemy SAM sites and radar installations",
                            target_units=sam_radar_ids,
                            min_required=len(sam_radar_ids),
                            required=True
                        )
                    )
        
        elif mission_type == "cas":
            # CAS: Destroy ground targets (vehicles and infantry)
            objectives.append(
                ObjectiveSpec(
                    id_name="Fly_To",
                    name="Enter CAS Area",
                    info="Navigate to the close air support zone",
                    trigger_radius=1200.0,
                    spherical_radius=False,
                    required=True
                )
            )
            
            if spawned_units:
                ground_unit_ids = [
                    u.id for u in spawned_units 
                    if hasattr(u, 'id') and u.team == "Enemy"
                ]
                if ground_unit_ids:
                    # CAS typically requires destroying more targets
                    min_kills = max(2, len(ground_unit_ids) * 2 // 3)
                    objectives.append(
                        ObjectiveSpec(
                            id_name="Destroy",
                            name="Eliminate Ground Threats",
                            info=f"Destroy at least {min_kills} enemy ground units",
                            target_units=ground_unit_ids,
                            min_required=min_kills,
                            required=True
                        )
                    )
        
        elif mission_type == "intercept":
            # Intercept: Navigate and destroy enemy aircraft
            objectives.append(
                ObjectiveSpec(
                    id_name="Fly_To",
                    name="Intercept Zone",
                    info="Navigate to the intercept coordinates",
                    trigger_radius=2000.0,  # Larger radius for air-to-air
                    spherical_radius=True,   # Spherical for 3D air combat
                    required=True
                )
            )
            
            if spawned_units:
                air_unit_ids = [
                    u.id for u in spawned_units 
                    if hasattr(u, 'id') and u.team == "Enemy"
                    and "AI" in u.unit_type  # Aircraft units typically have "AI" in type
                ]
                if air_unit_ids:
                    objectives.append(
                        ObjectiveSpec(
                            id_name="Destroy",
                            name="Destroy Enemy Aircraft",
                            info="Eliminate hostile aircraft in the area",
                            target_units=air_unit_ids,
                            min_required=len(air_unit_ids),
                            required=True
                        )
                    )
        
        elif mission_type == "transport":
            # Transport: Navigate to pickup, then to dropoff
            objectives.append(
                ObjectiveSpec(
                    id_name="Fly_To",
                    name="Pickup Zone",
                    info="Navigate to the pickup location",
                    trigger_radius=500.0,
                    spherical_radius=False,
                    required=True
                )
            )
            # Note: Would need second waypoint for dropoff zone in future
            context["requires_dropoff"] = True
        
        else:
            # Default: simple navigation objective
            objectives.append(
                ObjectiveSpec(
                    id_name="Fly_To",
                    name="Proceed to Target",
                    info="Navigate to the designated coordinates",
                    trigger_radius=600.0,
                    spherical_radius=False,
                    required=True
                )
            )
        
        return ObjectivePlan(objectives=objectives, context=context)
