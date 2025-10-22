from dataclasses import dataclass, field
from typing import List, Optional, Union, Dict, Any, cast, Literal


@dataclass
class BasePytolObject:
    """Base class for simple mission objects."""
    def to_dict(self) -> Dict[str, Any]:
        """Converts the object to a dictionary for the mission builder."""
        # A simple converter that filters out None values
        return {{k: v for k, v in self.__dict__.items() if v is not None}}

@dataclass(unsafe_hash=True)
class Path(BasePytolObject):
    uniformly_partition: Optional[bool] = None
    loop: Optional[bool] = None
    scenario_path_i_d: Optional[int] = None
    path_mode: Optional[Literal["Smooth", "Linear", "Bezier"]] = None
    unity_action: Optional[str] = None
    get_closest_time_world: Optional[float] = None
    get_follow_point: Optional[str] = None
    get_follow_point: Optional[str] = None
    get_closest_time: Optional[float] = None


@dataclass(unsafe_hash=True)
class Trigger(BasePytolObject):
    void: Optional[str] = None
    string: Optional[str] = None
    id: Optional[int] = None
    event_name: Optional[str] = None
    enabled: Optional[bool] = None
    trigger_type: Optional[str] = None
    waypoint: Optional[str] = None
    radius: Optional[float] = None
    spherical_radius: Optional[bool] = None
    trigger_mode: Optional[str] = None
    unit: Optional[str] = None
    proxy_mode: Optional[str] = None
    conditional: Optional[str] = None
    string: Optional[str] = None
    list_folder_data: Optional[str] = None
    event_fired_delegate: Optional[str] = None

