from dataclasses import dataclass, field
from typing import List, Optional, Union, Dict, Any, cast, Literal
from ..classes.mission_objects import Waypoint, EventTarget
@dataclass
class Objective:
    """Base class for all mission objectives."""
    objective_id: int
    name: str
    info: str
    type: str # This is the ObjectiveTypes enum string (e.g., "Destroy")
    required: bool = True
    waypoint: Optional[Waypoint] = None
    prereqs: Optional[List[int]] = None
    auto_set_waypoint: bool = True
    orderID: int = 0
    completionReward: int = 0
    start_event_targets: List[EventTarget] = field(default_factory=list) # <-- ADD
    fail_event_targets: List[EventTarget] = field(default_factory=list)  # <-- ADD
    complete_event_targets: List[EventTarget] = field(default_factory=list) # <-- ADD
    fields: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Called after __init__ to populate fields from child attributes."""
        all_field_names = set()
        cls_to_check = self.__class__
        while cls_to_check is not Objective: # Iterate up the inheritance chain
            all_field_names.update(field_names.get(cls_to_check.__name__, []))
            if not cls_to_check.__mro__[1] or cls_to_check.__mro__[1] is object:
                break
            cls_to_check = cls_to_check.__mro__[1] # Get parent class
        
        for f in all_field_names:
            if hasattr(self, f):
                val = getattr(self, f)
                if val is not None:
                    if f == 'targets' and isinstance(val, list):
                        # Format list [id1, id2] into "id1;id2;" string
                        formatted_targets = ";".join(map(str, val)) + ";"
                        self.fields[f] = formatted_targets
                    else: # Default handling for other fields
                        self.fields[f] = val
                    delattr(self, f)

# This helper dict stores the field names for each class,
# used by the base class's __post_init__
field_names: Dict[str, List[str]] = {}

@dataclass(unsafe_hash=True)
class VTObjectiveModule(Objective):
    """Dataclass for objective VTObjectiveModule"""
    pass


@dataclass(unsafe_hash=True)
class VTOMRefuel(Objective):
    """Dataclass for objective VTOMRefuel"""
    targets: Optional[List[str]] = None
    # (C#: Refuel Target - string)
    #     Format: A semi-colon (;) separated list of Unit IDs.
    fuel_level: Optional[float] = None
    # (C#: Fuel Level - float)


@dataclass(unsafe_hash=True)
class VTOMDefendUnit(VTObjectiveModule):
    """Dataclass for objective VTOMDefendUnit"""
    target: Optional[str] = None
    # (C#: Target - string)
    #     Format: A single Unit ID.
    radius: Optional[float] = None
    # (C#: Radius - float)
    completion_mode: Optional[Literal["Waypoint", "Trigger"]] = None
    # (C#: Completion Mode - string)
    #     Format: Unknown complex type: DefendCompletionModes


@dataclass(unsafe_hash=True)
class VTOMConditional(VTObjectiveModule):
    """Dataclass for objective VTOMConditional"""
    success_conditional: Optional[str] = None
    # (C#: Success Condition - string)
    #     Format: The ID of a Conditional.
    fail_conditional: Optional[str] = None
    # (C#: Fail Condition - string)
    #     Format: The ID of a Conditional.


@dataclass(unsafe_hash=True)
class VTOMPickUp(VTObjectiveModule):
    """Dataclass for objective VTOMPickUp"""
    targets: Optional[str] = None
    # (C#: Pickup Targets - string)
    #     Format: Unknown complex type: UnitReferenceListPickup
    min_required: Optional[float] = None
    # (C#: Min Required - float)
    per_unit_reward: Optional[float] = None
    # (C#: Per Unit Reward - float)
    full_complete_bonus: Optional[float] = None
    # (C#: Full Completion Bonus - float)


@dataclass(unsafe_hash=True)
class VTOMFlyTo(VTObjectiveModule):
    """Dataclass for objective VTOMFlyTo"""
    trigger_radius: Optional[float] = None
    # (C#: Radius - float)
    spherical_radius: Optional[bool] = None
    # (C#: Spherical Radius - bool)


@dataclass(unsafe_hash=True)
class VTOMJoinUnit(VTObjectiveModule):
    """Dataclass for objective VTOMJoinUnit"""
    target_unit: Optional[str] = None
    # (C#: Target Unit - string)
    #     Format: A single Unit ID.
    radius: Optional[float] = None
    # (C#: Radius - float)


@dataclass(unsafe_hash=True)
class VTOMDropOff(VTObjectiveModule):
    """Dataclass for objective VTOMDropOff"""
    targets: Optional[str] = None
    # (C#: Drop Off Targets - string)
    #     Format: Unknown complex type: UnitReferenceListPickup
    min_required: Optional[float] = None
    # (C#: Min Required - float)
    per_unit_reward: Optional[float] = None
    # (C#: Per Unit Reward - float)
    full_complete_bonus: Optional[float] = None
    # (C#: Full Completion Bonus - float)
    unload_radius: Optional[float] = None
    # (C#: Unload Radius - float)
    dropoff_rally_pt: Optional[str] = None
    # (C#: Dropoff Rally Point - string)
    #     Format: The ID of a Waypoint.


@dataclass(unsafe_hash=True)
class VTOMGlobalValue(VTObjectiveModule):
    """Dataclass for objective VTOMGlobalValue"""
    current_value: Optional[str] = None
    # (C#: Current Value - string)
    #     Format: The ID of a Global Value.
    target_value: Optional[str] = None
    # (C#: Target Value - string)
    #     Format: The ID of a Global Value.


@dataclass(unsafe_hash=True)
class VTOMLandAt(VTObjectiveModule):
    """Dataclass for objective VTOMLandAt"""
    radius: Optional[float] = None
    # (C#: Radius - float)


@dataclass(unsafe_hash=True)
class VTOMKillMission(VTObjectiveModule):
    """Dataclass for objective VTOMKillMission"""
    targets: Optional[List[str]] = None
    # (C#: Destroy Targets - string)
    #     Format: A semi-colon (;) separated list of Unit IDs.
    min_required: Optional[float] = None
    # (C#: Min Required - float)
    per_unit_reward: Optional[float] = None
    # (C#: Per Kill Reward - float)
    full_complete_bonus: Optional[float] = None
    # (C#: Full Completion Bonus - float)


# Populate the helper dict
field_names.update({
    "VTOMRefuel": [
        "targets",
        "fuel_level"
    ],
    "VTObjectiveModule": [],
    "VTOMDefendUnit": [
        "target",
        "radius",
        "completion_mode"
    ],
    "VTOMConditional": [
        "success_conditional",
        "fail_conditional"
    ],
    "VTOMPickUp": [
        "targets",
        "min_required",
        "per_unit_reward",
        "full_complete_bonus"
    ],
    "VTOMFlyTo": [
        "trigger_radius",
        "spherical_radius"
    ],
    "VTOMJoinUnit": [
        "target_unit",
        "radius"
    ],
    "VTOMDropOff": [
        "targets",
        "min_required",
        "per_unit_reward",
        "full_complete_bonus",
        "unload_radius",
        "dropoff_rally_pt"
    ],
    "VTOMGlobalValue": [
        "current_value",
        "target_value"
    ],
    "VTOMLandAt": [
        "radius"
    ],
    "VTOMKillMission": [
        "targets",
        "min_required",
        "per_unit_reward",
        "full_complete_bonus"
    ]
})

# --- FACTORY ---

# This maps the ID to the correct Python class
ID_TO_CLASS = {
    "Destroy": VTOMKillMission,
    "Fly_To": VTOMFlyTo,
    "Join": VTOMJoinUnit,
    "Pick_Up": VTOMPickUp,
    "Drop_Off": VTOMDropOff,
    "Land": VTOMLandAt,
    "Refuel": VTOMRefuel,
    "Protect": VTOMDefendUnit,
    "Conditional": VTOMConditional,
    "Global_Value": VTOMGlobalValue,

}

def create_objective(
    # Base args are defined in the template

    id_name: str, # This is the 'ObjectiveTypes' enum string, e.g., "Destroy"
    objective_id: int,
    name: str,
    info: str,
    required: bool = True,
    waypoint: Optional[str] = None,
    prereqs: Optional[List[int]] = None,
    auto_set_waypoint: bool = True,

    **kwargs
) -> "Objective":
    """

    Factory function to create a new objective instance.
    
    Args:
        id_name (str): The type of objective (e.g., "Destroy", "Fly_To").
        objective_id (int): A unique integer ID for this objective.
        name (str): The in-game display name for the objective.
        info (str): The in-game description for the objective.
        required (bool): Whether the objective is required for mission success.
        waypoint (Optional[str]): The ID of a waypoint to associate with this.
        prereqs (Optional[List[int]]): List of objective IDs that must be completed first.
        auto_set_waypoint (bool): Automatically set the player's waypoint to this.
        **kwargs: Any additional objective-specific parameters (e.g., trigger_radius=1000).
    
    Returns:
        An Objective subclass instance with all parameters set.

    """
    id_name_str = str(id_name) # Ensure it's a string for lookup
    if id_name_str not in ID_TO_CLASS:
        raise KeyError(f"Objective ID '{id_name_str}' not found in database.")
    
    ClassToCreate = ID_TO_CLASS[id_name_str]
    
    # Get all allowed field names for this class and its parents
    allowed_field_names = set()
    cls_to_check = ClassToCreate
    while cls_to_check is not Objective:
        allowed_field_names.update(field_names.get(cls_to_check.__name__, []))
        if not cls_to_check.__mro__[1] or cls_to_check.__mro__[1] is object:
            break
        cls_to_check = cls_to_check.__mro__[1]

    # Validate kwargs
    for kwarg in kwargs:
        if kwarg not in allowed_field_names:
            raise TypeError(f"'{kwarg}' is not a valid parameter for Objective '{id_name_str}' (class '{ClassToCreate.__name__}').")

    base_args = {

        "type": id_name,
        "objective_id": objective_id,
        "name": name,
        "info": info,
        "required": required,
        "waypoint": waypoint,
        "prereqs": prereqs,
        "auto_set_waypoint": auto_set_waypoint,

    }
    
    return cast("Objective", ClassToCreate(**base_args, **kwargs))
