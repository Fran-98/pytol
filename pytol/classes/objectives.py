from dataclasses import dataclass, field, fields
from typing import List, Optional, Union, Dict, Any, cast, Literal
from ..classes.mission_objects import Waypoint, EventTarget
from ..misc.logger import create_logger

_logger = create_logger(verbose=False, name="Objectives")

@dataclass
class Objective:
    """Base class for all mission objectives."""
    objective_id: int
    name: str
    info: str
    type: str # This is the ObjectiveTypes enum string (e.g., "Destroy")
    required: bool = True
    waypoint: Optional[Union[Waypoint, str, int]] = None # Allow object, str, or int
    prereqs: Optional[List[Union['Objective', int]]] = None # Allow object or int
    auto_set_waypoint: bool = True
    orderID: int = 0
    completionReward: int = 0
    start_mode: Optional[Literal["Immediate", "PreReqs", "Final"]] = None
    start_event_targets: List[EventTarget] = field(default_factory=list)
    fail_event_targets: List[EventTarget] = field(default_factory=list)
    complete_event_targets: List[EventTarget] = field(default_factory=list)
    fields: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """
        Called after standard dataclass __init__.
        Moves subclass-specific fields (defined in the 'field_names' dict)
        into the self.fields dictionary for VTS formatting, applying
        special formatting where needed (e.g., for 'targets' list).
        Base Objective fields are left untouched.
        """
        # Get the specific class name (e.g., "VTOMFlyTo")
        subclass_name = self.__class__.__name__

        # Get the list of field names specific to this subclass from our helper dict
        subclass_field_names = field_names.get(subclass_name, [])

        # Process ONLY these subclass-specific fields
        fields_to_delete = [] # Keep track of attributes to delete safely later
        for f_name in subclass_field_names:
            if hasattr(self, f_name):
                val = getattr(self, f_name)
                if val is not None:
                    # Apply special formatting if needed
                    if f_name == 'targets' and isinstance(val, list):
                        # Format list [id1, id2] into "id1;id2;" string for VTS
                        formatted_targets = ";".join(map(str, val)) + ";"
                        self.fields[f_name] = formatted_targets
                    else: # Default handling for other specific fields
                        self.fields[f_name] = val
                    # Mark the original attribute for deletion
                    fields_to_delete.append(f_name)

        # Safely delete the original attributes after processing
        for f_name in fields_to_delete:
            try:
                delattr(self, f_name)
            except AttributeError:
                # Should not happen if hasattr was true, but added for safety
                _logger.warning(f"Could not delete attribute '{f_name}' during __post_init__ for {subclass_name}.")

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
    "VTObjectiveModule": [
        # "start_event_targets",
        # "fail_event_targets",
        # "complete_event_targets"
    ],
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
    # --- Base args ---
    id_name: str, # Objective type
    objective_id: int,
    name: str,
    info: str,
    required: bool = True,
    waypoint: Optional[Union[Waypoint, str, int]] = None,
    prereqs: Optional[List[Union[Objective, int]]] = None,
    auto_set_waypoint: bool = True,
    start_mode: Optional[Literal["Immediate", "PreReqs", "Final"]] = None,
    start_event_targets: Optional[List[EventTarget]] = None,
    fail_event_targets: Optional[List[EventTarget]] = None,
    complete_event_targets: Optional[List[EventTarget]] = None,
    # --- Objective specific fields ---
    **kwargs
) -> "Objective":
    """
    Factory function to create a new objective instance.
    Includes support for event target lists.
    """
    id_name_str = str(id_name) # Ensure it's a string for lookup
    if id_name_str not in ID_TO_CLASS:
        raise KeyError(f"Objective ID '{id_name_str}' not found in database.")

    ClassToCreate = ID_TO_CLASS[id_name_str]

    # --- Validation Logic (Revised - separate base and specific fields) ---
    base_fields_names = {f.name for f in fields(Objective)}

    # Get names of fields specific to the target subclass using the field_names dict
    specific_fields_names = set(field_names.get(ClassToCreate.__name__, []))

    # Validate kwargs: they must either be a specific field or a base field
    objective_specific_fields = {} # Dict to hold validated specific fields from kwargs
    passed_kwargs_names = set(kwargs.keys())

    # Check for invalid kwargs (not base, not specific for this class)
    allowed_specific_kwargs = specific_fields_names # Kwargs should only contain specific fields
    invalid_kwargs = passed_kwargs_names - allowed_specific_kwargs
    if invalid_kwargs:
        # Check if the invalid kwarg is actually a base field (which shouldn't be in kwargs)
        actually_base_fields = invalid_kwargs.intersection(base_fields_names)
        if actually_base_fields:
             raise TypeError(f"Base objective field(s) '{actually_base_fields}' were passed as keyword arguments. Pass them as direct arguments.")
        else:
             # Truly invalid kwargs
             raise TypeError(f"Invalid keyword argument(s) for Objective '{id_name_str}': {invalid_kwargs}. Allowed specific fields for {ClassToCreate.__name__}: {allowed_specific_kwargs}")

    # Populate specific fields dict from valid kwargs
    for field_name in allowed_specific_kwargs:
        if field_name in kwargs:
            objective_specific_fields[field_name] = kwargs[field_name]
    # --- End Validation ---


    # --- Base Args Dictionary (Includes event targets passed directly) ---
    base_args = {
        "type": id_name,
        "objective_id": objective_id,
        "name": name,
        "info": info,
        "required": required,
        "waypoint": waypoint,
        "prereqs": prereqs,
        "auto_set_waypoint": auto_set_waypoint,
        "start_mode": start_mode,
        "start_event_targets": start_event_targets or [],
        "fail_event_targets": fail_event_targets or [],
        "complete_event_targets": complete_event_targets or [],
        # orderID and completionReward use defaults from dataclass
    }

    # Combine base args and specific fields for instantiation
    all_args = {**base_args, **objective_specific_fields}

    try:
        instance = ClassToCreate(**all_args)
        return cast("Objective", instance)

    except TypeError as e:
        _logger.error(f"Error during instance creation in create_objective: {e}")
        _logger.error(f"Class: {ClassToCreate.__name__}")
        _logger.error(f"All Args Passed: {all_args}")
        raise e
