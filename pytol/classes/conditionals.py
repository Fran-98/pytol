from dataclasses import dataclass, field
from typing import List, Optional, Union, Dict, Any, cast, Literal


@dataclass(unsafe_hash=True)
class Conditional:
    """
    Base class for all conditional components (SCC_...).
    This is a simple dataclass. The 'id' and 'type' will be
    managed by the ConditionalBuilder in your main script.
    """
    pass

@dataclass(unsafe_hash=True)
class Sccand(Conditional):
    factors: Optional[List[str]] = None


@dataclass(unsafe_hash=True)
class Sccchance(Conditional):
    chance: Optional[int] = None


@dataclass(unsafe_hash=True)
class Sccglobalvalue(Conditional):
    gv: Optional[str] = None
    comparison: Optional[Literal["Equals", "Greater_Than", "Less_Than"]] = None
    c_value: Optional[int] = None


@dataclass(unsafe_hash=True)
class Sccglobalvaluecompare(Conditional):
    gv_a: Optional[str] = None
    gv_b: Optional[str] = None
    comparison: Optional[Literal["Equals", "NotEquals", "Greater", "Greater_Or_Equal", "Less", "Less_Or_Equal"]] = None


@dataclass(unsafe_hash=True)
class Sccmpteamstats(Conditional):
    team: Optional[Literal["Allied", "Enemy"]] = None
    stat_type: Optional[Literal["Kills", "Deaths", "Score", "Lives_Left", "Team_Budget", "Player_Count"]] = None
    comparison: Optional[Literal["Equals", "Greater_Than", "Less_Than"]] = None
    count: Optional[int] = None


@dataclass(unsafe_hash=True)
class Sccor(Conditional):
    factors: Optional[List[str]] = None


@dataclass(unsafe_hash=True)
class Sccstaticobject(Conditional):
    object_reference: Optional[str] = None
    method_name: Optional[str] = None
    method_parameters: Optional[List[str]] = None
    is_not: Optional[bool] = None


@dataclass(unsafe_hash=True)
class Sccunit(Conditional):
    unit: Optional[str] = None
    method_name: Optional[str] = None
    method_parameters: Optional[List[str]] = None
    is_not: Optional[bool] = None


@dataclass(unsafe_hash=True)
class Sccunitalive(Conditional):
    unit_ref: Optional[str] = None


@dataclass(unsafe_hash=True)
class Sccunitgroup(Conditional):
    unit_group: Optional[str] = None
    method_name: Optional[str] = None
    method_parameters: Optional[List[str]] = None
    is_not: Optional[bool] = None


@dataclass(unsafe_hash=True)
class Sccunitlist(Conditional):
    unit_list: Optional[List[str]] = None
    method_name: Optional[str] = None
    method_parameters: Optional[List[str]] = None
    is_not: Optional[bool] = None


@dataclass(unsafe_hash=True)
class Sccvehiclecontrol(Conditional):
    vehicle_control: Optional[str] = None
    control_condition: Optional[Literal["Interacted", "EqualTo", "GreaterThan", "LessThan"]] = None
    control_value: Optional[float] = None
    is_not: Optional[bool] = None



# --- FACTORY ---

ID_TO_CLASS = {
    "SCCAnd": Sccand,
    "SCCChance": Sccchance,
    "SCCGlobalValue": Sccglobalvalue,
    "SCCGlobalValueCompare": Sccglobalvaluecompare,
    "SCCMPTeamStats": Sccmpteamstats,
    "SCCOr": Sccor,
    "SCCStaticObject": Sccstaticobject,
    "SCCUnit": Sccunit,
    "SCCUnitAlive": Sccunitalive,
    "SCCUnitGroup": Sccunitgroup,
    "SCCUnitList": Sccunitlist,
    "SCCVehicleControl": Sccvehiclecontrol,

}

def create_conditional(
    type_name: str,
    **kwargs
) -> "Conditional":
    """

    Factory function to create a new conditional component (SCC_...).
    
    Args:
        type_name (str): The type of conditional (e.g., "SCCAnd", "SCCUnitAlive").
        **kwargs: Any parameters for the conditional (e.g., unit_ref="my_unit").
    
    Returns:
        A Conditional subclass instance.

    """
    if type_name not in ID_TO_CLASS:
        raise KeyError(f"Conditional type '{type_name}' not found in database.")
    
    ClassToCreate = ID_TO_CLASS[type_name]
    
    # Validate kwargs
    allowed_fields = [f.name for f in ClassToCreate.__dataclass_fields__]
    for kwarg in kwargs:
        if kwarg not in allowed_fields:
            raise TypeError(f"'{kwarg}' is not a valid parameter for Conditional '{type_name}'.")
            
    return cast("Conditional", ClassToCreate(**kwargs))
