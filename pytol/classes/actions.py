from dataclasses import dataclass, field
from typing import List, Optional, Union, Dict, Any, cast, Literal

from .mission_objects import EventTarget, ParamInfo, GlobalValue


# This file contains helper classes to generate EventTarget objects

# for use in TriggerEvent.event_targets, based on [VTEvent] attributes.


class AIAWACSSpawnActions:
    """Actions callable on AIAWACSSpawn."""
    def __init__(self, target_id: Any):
        self.target_id = target_id
        self.target_type = "AIAWACSSpawn" # TODO: This may need adjustment depending on VTS format

    def add_designated_targets(self, targets: List[str]) -> EventTarget:
        """Adds units to the AI pilot's designated targets, which it will attack at highest priority, immediately, whether or not these targets have been detected."""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Designated Targets", params=params)

    def add_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Non-Targets", params=params)

    def add_priority_targets(self, targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Priority Targets", params=params)

    def attack_target(self) -> EventTarget:
        """Attack a specific target, regardless of detection or other threats."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Attack Target")

    def bomb_waypoint(self, wpt: str) -> EventTarget:
        """Bomb a waypoint. Aircraft must have unguided bombs equipped."""
        params = [ParamInfo(name="wpt", type="string", value=wpt)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Bomb Waypoint", params=params)

    def cancel_attack_target(self) -> EventTarget:
        """Cancel the override attack target and return to normal behavior."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Cancel Attack Tgt")

    def clear_designated_targets(self) -> EventTarget:
        """Clears the AI pilot's designated targets."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Designated Targets")

    def clear_non_targets(self) -> EventTarget:
        """Clear the list of units that this unit will not attack."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Non-Targets")

    def clear_priority_targets(self) -> EventTarget:
        """Clear the list of units that this unit will prioritize when finding a target"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Priority Targets")

    def destroy_self(self) -> EventTarget:
        """This event destroys the unit immediately."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Destroy")

    def fire_a_s_m_on_path(self, asm_path: str, t_mode: Literal["Direct", "SeaSkim", "SSEvasive", "Popup"]) -> EventTarget:
        """Command the aircraft to fire an anti-ship missile on the given path if available."""
        params = [ParamInfo(name="asmPath", type="string", value=asm_path), ParamInfo(name="tMode", type="string", value=t_mode)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Fire ASM", params=params)

    def countermeasure_program(self, flares: bool, chaff: bool) -> EventTarget:
        """Fires a set amount of chaff and/or flares."""
        params = [ParamInfo(name="flares", type="bool", value=flares), ParamInfo(name="chaff", type="bool", value=chaff)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Fire Countermeasures", params=params)

    def force_alt_spawn(self) -> EventTarget:
        """Force a specific alternate spawn, overriding the random roll. This must be called BEFORE the unit spawns. If the unit is in a group with synced alternates, the other units will be forced as well."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Force Alt Spawn")

    def form_on_pilot(self) -> EventTarget:
        """Command the aircraft to form up on a particular air unit."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Form On Pilot")

    def land(self) -> EventTarget:
        """Land at a specified airfield."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Land")

    def land_at_wpt(self, wpt: str) -> EventTarget:
        """Vertically land on a specified waypoint if capable."""
        params = [ParamInfo(name="wpt", type="string", value=wpt)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Land At Wpt", params=params)

    def land_at_wpt_hdg_fcg(self, wpt: str) -> EventTarget:
        """Vertically land on a specified waypoint with the specified heading, if capable."""
        params = [ParamInfo(name="wpt", type="string", value=wpt)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Land At Wpt w/ Dir Facing", params=params)

    def land_at_wpt_hdg(self, wpt: str) -> EventTarget:
        """Vertically land on a specified waypoint with the specified heading, if capable."""
        params = [ParamInfo(name="wpt", type="string", value=wpt)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Land At Wpt w/ Direction", params=params)

    def lase_target(self) -> EventTarget:
        """Command the pilot to laser designate a specific target, if able. It will continue on its current orbit or path. After the target is destroyed or the pilot receives another combat command, the pilot will stop laser designating."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Laser Designate Target")

    def lase_target_orbit(self) -> EventTarget:
        """Command the pilot to laser designate a specific target, if able. Set a custom orbit. After the target is destroyed or the pilot receives another combat command, the pilot will stop laser designating."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Laser Designate With Obit")

    def load_passengers(self) -> EventTarget:
        """Command the selected units to board this aircraft."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Load Passengers")

    def load_passenger_group(self) -> EventTarget:
        """Command the selected unit group to board this aircraft."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Load Unit Group")

    def set_orbit_now(self, wpt: str) -> EventTarget:
        """Command the aircraft to orbit a waypoint."""
        params = [ParamInfo(name="wpt", type="string", value=wpt)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Orbit Waypoint", params=params)

    def set_to_lasing_mode(self) -> EventTarget:
        """Set whether the pilot should only find and laser designate targets instead of attacking. It will continue on its current orbit or path. It will only designate ground units or slow moving aircraft. If it's in this state, commanding it to attack or engage/disengage will revert it to ordinary behavior."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Order Laser Designating")

    def randomize_alt_spawn(self) -> EventTarget:
        """Set a new random alternate spawn for this unit. Useful for respawning units in random places.  If the unit is in a group with synced alternates, the other units will have the same new alternate."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Randomize Alt Spawn")

    def rearm_at(self) -> EventTarget:
        """Land, rearm/refuel, and take off again from specified airfield."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Rearm")

    def refuel_with_unit(self) -> EventTarget:
        """Command the aircraft to refuel from a particular tanker."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Refuel From Tanker")

    def remove_designated_targets(self, targets: List[str]) -> EventTarget:
        """Remove a particular set of units from the designated targets."""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Designated Targets", params=params)

    def remove_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Non-Targets", params=params)

    def remove_priority_targets(self, targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Priority Targets", params=params)

    def set_report_to_groups(self, selection: List[str]) -> EventTarget:
        """Select unit groups to allow this AWACS to report targets to friendlies outside of its own group."""
        params = [ParamInfo(name="selection", type="string", value=selection)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Report Contacts To Groups", params=params)

    def set_awacs_comms(self, enabled: bool) -> EventTarget:
        """Set whether the AWACS can be contacted for support."""
        params = [ParamInfo(name="enabled", type="bool", value=enabled)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set AWACS Comms", params=params)

    def set_altitude(self) -> EventTarget:
        """Set the aircraft's default altitude."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Altitude")

    def set_designated_targets(self, targets: List[str]) -> EventTarget:
        """Sets or replaces the AI pilot's designated targets, which it will attack at highest priority, immediately, whether or not these targets have been detected."""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Designated Targets", params=params)

    def set_engage_enemies(self, engage: bool) -> EventTarget:
        """Set whether the unit should engage enemies."""
        params = [ParamInfo(name="engage", type="bool", value=engage)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Engage Enemies", params=params)

    def set_formation_distance(self, dist: Literal["Close", "Medium", "Far", "Airshow"]) -> EventTarget:
        """Set the formation distance of AI aircraft when they follow this unit."""
        params = [ParamInfo(name="dist", type="string", value=dist)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Formation Distance", params=params)

    def set_invincible(self, i: bool) -> EventTarget:
        """Sets whether the unit can take damage."""
        params = [ParamInfo(name="i", type="bool", value=i)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Invincible", params=params)

    def set_jamming_at_will(self, j: bool) -> EventTarget:
        """Set whether the unit can jam targets of opportunity without being told to (if equipped)."""
        params = [ParamInfo(name="j", type="bool", value=j)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Jamming at Will", params=params)

    def set_nav_speed(self) -> EventTarget:
        """Set the aircraft's default navigation airspeed (when not in combat)."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Nav Speed")

    def set_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will not attack. (Overwrites existing list)"""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Non-Targets", params=params)

    def set_path(self, path: str) -> EventTarget:
        """Set the aircraft to fly along a path."""
        params = [ParamInfo(name="path", type="string", value=path)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Path", params=params)

    def set_player_commands(self, mode: Literal["Unit_Group_Only", "Force_Allow", "Force_Disallow"]) -> EventTarget:
        """Set whether the unit can be commanded by the player."""
        params = [ParamInfo(name="mode", type="string", value=mode)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Player Commands", params=params)

    def set_priority_targets(self, targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will prioritize when finding a target. (Overwrites existing list)"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Priority Targets", params=params)

    def set_radar(self, radar_on: bool) -> EventTarget:
        """Set's the unit's radar on or off, if it has one."""
        params = [ParamInfo(name="radarOn", type="bool", value=radar_on)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Radar", params=params)

    def set_radio_comms(self, radio_enabled: bool) -> EventTarget:
        """Set whether the AI pilot will communicate with the player via radio."""
        params = [ParamInfo(name="radioEnabled", type="bool", value=radio_enabled)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Radio Comms", params=params)

    def spawn_unit(self) -> EventTarget:
        """Spawn the unit if it hasn't already been spawned"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Spawn Unit")

    def take_off(self) -> EventTarget:
        """Command the pilot to take off."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Take Off")

    def taxi_path(self, path: str) -> EventTarget:
        """Command the aircraft to taxi on a certain path."""
        params = [ParamInfo(name="path", type="string", value=path)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Taxi Path", params=params)

    def taxi_path_speed(self, path: str) -> EventTarget:
        """Command the aircraft to taxi on a certain path at a certain speed."""
        params = [ParamInfo(name="path", type="string", value=path)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Taxi Path Speed", params=params)

    def unload_all_passengers(self, rally_wp: str) -> EventTarget:
        """Unload all passengers when available."""
        params = [ParamInfo(name="rallyWp", type="string", value=rally_wp)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Unload Passengers", params=params)



class AIAirTankerSpawnActions:
    """Actions callable on AIAirTankerSpawn."""
    def __init__(self, target_id: Any):
        self.target_id = target_id
        self.target_type = "AIAirTankerSpawn" # TODO: This may need adjustment depending on VTS format

    def add_designated_targets(self, targets: List[str]) -> EventTarget:
        """Adds units to the AI pilot's designated targets, which it will attack at highest priority, immediately, whether or not these targets have been detected."""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Designated Targets", params=params)

    def add_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Non-Targets", params=params)

    def add_priority_targets(self, targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Priority Targets", params=params)

    def attack_target(self) -> EventTarget:
        """Attack a specific target, regardless of detection or other threats."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Attack Target")

    def bomb_waypoint(self, wpt: str) -> EventTarget:
        """Bomb a waypoint. Aircraft must have unguided bombs equipped."""
        params = [ParamInfo(name="wpt", type="string", value=wpt)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Bomb Waypoint", params=params)

    def cancel_attack_target(self) -> EventTarget:
        """Cancel the override attack target and return to normal behavior."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Cancel Attack Tgt")

    def clear_designated_targets(self) -> EventTarget:
        """Clears the AI pilot's designated targets."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Designated Targets")

    def clear_non_targets(self) -> EventTarget:
        """Clear the list of units that this unit will not attack."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Non-Targets")

    def clear_priority_targets(self) -> EventTarget:
        """Clear the list of units that this unit will prioritize when finding a target"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Priority Targets")

    def destroy_self(self) -> EventTarget:
        """This event destroys the unit immediately."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Destroy")

    def fire_a_s_m_on_path(self, asm_path: str, t_mode: Literal["Direct", "SeaSkim", "SSEvasive", "Popup"]) -> EventTarget:
        """Command the aircraft to fire an anti-ship missile on the given path if available."""
        params = [ParamInfo(name="asmPath", type="string", value=asm_path), ParamInfo(name="tMode", type="string", value=t_mode)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Fire ASM", params=params)

    def countermeasure_program(self, flares: bool, chaff: bool) -> EventTarget:
        """Fires a set amount of chaff and/or flares."""
        params = [ParamInfo(name="flares", type="bool", value=flares), ParamInfo(name="chaff", type="bool", value=chaff)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Fire Countermeasures", params=params)

    def force_alt_spawn(self) -> EventTarget:
        """Force a specific alternate spawn, overriding the random roll. This must be called BEFORE the unit spawns. If the unit is in a group with synced alternates, the other units will be forced as well."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Force Alt Spawn")

    def form_on_pilot(self) -> EventTarget:
        """Command the aircraft to form up on a particular air unit."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Form On Pilot")

    def land(self) -> EventTarget:
        """Land at a specified airfield."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Land")

    def land_at_wpt(self, wpt: str) -> EventTarget:
        """Vertically land on a specified waypoint if capable."""
        params = [ParamInfo(name="wpt", type="string", value=wpt)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Land At Wpt", params=params)

    def land_at_wpt_hdg_fcg(self, wpt: str) -> EventTarget:
        """Vertically land on a specified waypoint with the specified heading, if capable."""
        params = [ParamInfo(name="wpt", type="string", value=wpt)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Land At Wpt w/ Dir Facing", params=params)

    def land_at_wpt_hdg(self, wpt: str) -> EventTarget:
        """Vertically land on a specified waypoint with the specified heading, if capable."""
        params = [ParamInfo(name="wpt", type="string", value=wpt)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Land At Wpt w/ Direction", params=params)

    def lase_target(self) -> EventTarget:
        """Command the pilot to laser designate a specific target, if able. It will continue on its current orbit or path. After the target is destroyed or the pilot receives another combat command, the pilot will stop laser designating."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Laser Designate Target")

    def lase_target_orbit(self) -> EventTarget:
        """Command the pilot to laser designate a specific target, if able. Set a custom orbit. After the target is destroyed or the pilot receives another combat command, the pilot will stop laser designating."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Laser Designate With Obit")

    def load_passengers(self) -> EventTarget:
        """Command the selected units to board this aircraft."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Load Passengers")

    def load_passenger_group(self) -> EventTarget:
        """Command the selected unit group to board this aircraft."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Load Unit Group")

    def set_orbit_now(self, wpt: str) -> EventTarget:
        """Command the aircraft to orbit a waypoint."""
        params = [ParamInfo(name="wpt", type="string", value=wpt)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Orbit Waypoint", params=params)

    def set_to_lasing_mode(self) -> EventTarget:
        """Set whether the pilot should only find and laser designate targets instead of attacking. It will continue on its current orbit or path. It will only designate ground units or slow moving aircraft. If it's in this state, commanding it to attack or engage/disengage will revert it to ordinary behavior."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Order Laser Designating")

    def randomize_alt_spawn(self) -> EventTarget:
        """Set a new random alternate spawn for this unit. Useful for respawning units in random places.  If the unit is in a group with synced alternates, the other units will have the same new alternate."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Randomize Alt Spawn")

    def rearm_at(self) -> EventTarget:
        """Land, rearm/refuel, and take off again from specified airfield."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Rearm")

    def refuel_with_unit(self) -> EventTarget:
        """Command the aircraft to refuel from a particular tanker."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Refuel From Tanker")

    def remove_designated_targets(self, targets: List[str]) -> EventTarget:
        """Remove a particular set of units from the designated targets."""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Designated Targets", params=params)

    def remove_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Non-Targets", params=params)

    def remove_priority_targets(self, targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Priority Targets", params=params)

    def set_altitude(self) -> EventTarget:
        """Set the aircraft's default altitude."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Altitude")

    def set_designated_targets(self, targets: List[str]) -> EventTarget:
        """Sets or replaces the AI pilot's designated targets, which it will attack at highest priority, immediately, whether or not these targets have been detected."""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Designated Targets", params=params)

    def set_engage_enemies(self, engage: bool) -> EventTarget:
        """Set whether the unit should engage enemies."""
        params = [ParamInfo(name="engage", type="bool", value=engage)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Engage Enemies", params=params)

    def set_formation_distance(self, dist: Literal["Close", "Medium", "Far", "Airshow"]) -> EventTarget:
        """Set the formation distance of AI aircraft when they follow this unit."""
        params = [ParamInfo(name="dist", type="string", value=dist)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Formation Distance", params=params)

    def set_invincible(self, i: bool) -> EventTarget:
        """Sets whether the unit can take damage."""
        params = [ParamInfo(name="i", type="bool", value=i)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Invincible", params=params)

    def set_jamming_at_will(self, j: bool) -> EventTarget:
        """Set whether the unit can jam targets of opportunity without being told to (if equipped)."""
        params = [ParamInfo(name="j", type="bool", value=j)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Jamming at Will", params=params)

    def set_nav_speed(self) -> EventTarget:
        """Set the aircraft's default navigation airspeed (when not in combat)."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Nav Speed")

    def set_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will not attack. (Overwrites existing list)"""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Non-Targets", params=params)

    def set_path(self, path: str) -> EventTarget:
        """Set the aircraft to fly along a path."""
        params = [ParamInfo(name="path", type="string", value=path)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Path", params=params)

    def set_player_commands(self, mode: Literal["Unit_Group_Only", "Force_Allow", "Force_Disallow"]) -> EventTarget:
        """Set whether the unit can be commanded by the player."""
        params = [ParamInfo(name="mode", type="string", value=mode)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Player Commands", params=params)

    def set_priority_targets(self, targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will prioritize when finding a target. (Overwrites existing list)"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Priority Targets", params=params)

    def set_radar(self, radar_on: bool) -> EventTarget:
        """Set's the unit's radar on or off, if it has one."""
        params = [ParamInfo(name="radarOn", type="bool", value=radar_on)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Radar", params=params)

    def set_radio_comms(self, radio_enabled: bool) -> EventTarget:
        """Set whether the AI pilot will communicate with the player via radio."""
        params = [ParamInfo(name="radioEnabled", type="bool", value=radio_enabled)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Radio Comms", params=params)

    def spawn_unit(self) -> EventTarget:
        """Spawn the unit if it hasn't already been spawned"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Spawn Unit")

    def take_off(self) -> EventTarget:
        """Command the pilot to take off."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Take Off")

    def taxi_path(self, path: str) -> EventTarget:
        """Command the aircraft to taxi on a certain path."""
        params = [ParamInfo(name="path", type="string", value=path)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Taxi Path", params=params)

    def taxi_path_speed(self, path: str) -> EventTarget:
        """Command the aircraft to taxi on a certain path at a certain speed."""
        params = [ParamInfo(name="path", type="string", value=path)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Taxi Path Speed", params=params)

    def unload_all_passengers(self, rally_wp: str) -> EventTarget:
        """Unload all passengers when available."""
        params = [ParamInfo(name="rallyWp", type="string", value=rally_wp)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Unload Passengers", params=params)



class AIAircraftSpawnActions:
    """Actions callable on AIAircraftSpawn."""
    def __init__(self, target_id: Any):
        self.target_id = target_id
        self.target_type = "AIAircraftSpawn" # TODO: This may need adjustment depending on VTS format

    def add_designated_targets(self, targets: List[str]) -> EventTarget:
        """Adds units to the AI pilot's designated targets, which it will attack at highest priority, immediately, whether or not these targets have been detected."""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Designated Targets", params=params)

    def add_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Non-Targets", params=params)

    def add_priority_targets(self, targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Priority Targets", params=params)

    def attack_target(self) -> EventTarget:
        """Attack a specific target, regardless of detection or other threats."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Attack Target")

    def bomb_waypoint(self, wpt: str) -> EventTarget:
        """Bomb a waypoint. Aircraft must have unguided bombs equipped."""
        params = [ParamInfo(name="wpt", type="string", value=wpt)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Bomb Waypoint", params=params)

    def cancel_attack_target(self) -> EventTarget:
        """Cancel the override attack target and return to normal behavior."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Cancel Attack Tgt")

    def clear_designated_targets(self) -> EventTarget:
        """Clears the AI pilot's designated targets."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Designated Targets")

    def clear_non_targets(self) -> EventTarget:
        """Clear the list of units that this unit will not attack."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Non-Targets")

    def clear_priority_targets(self) -> EventTarget:
        """Clear the list of units that this unit will prioritize when finding a target"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Priority Targets")

    def destroy_self(self) -> EventTarget:
        """This event destroys the unit immediately."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Destroy")

    def fire_a_s_m_on_path(self, asm_path: str, t_mode: Literal["Direct", "SeaSkim", "SSEvasive", "Popup"]) -> EventTarget:
        """Command the aircraft to fire an anti-ship missile on the given path if available."""
        params = [ParamInfo(name="asmPath", type="string", value=asm_path), ParamInfo(name="tMode", type="string", value=t_mode)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Fire ASM", params=params)

    def countermeasure_program(self, flares: bool, chaff: bool) -> EventTarget:
        """Fires a set amount of chaff and/or flares."""
        params = [ParamInfo(name="flares", type="bool", value=flares), ParamInfo(name="chaff", type="bool", value=chaff)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Fire Countermeasures", params=params)

    def force_alt_spawn(self) -> EventTarget:
        """Force a specific alternate spawn, overriding the random roll. This must be called BEFORE the unit spawns. If the unit is in a group with synced alternates, the other units will be forced as well."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Force Alt Spawn")

    def form_on_pilot(self) -> EventTarget:
        """Command the aircraft to form up on a particular air unit."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Form On Pilot")

    def land(self) -> EventTarget:
        """Land at a specified airfield."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Land")

    def land_at_wpt(self, wpt: str) -> EventTarget:
        """Vertically land on a specified waypoint if capable."""
        params = [ParamInfo(name="wpt", type="string", value=wpt)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Land At Wpt", params=params)

    def land_at_wpt_hdg_fcg(self, wpt: str) -> EventTarget:
        """Vertically land on a specified waypoint with the specified heading, if capable."""
        params = [ParamInfo(name="wpt", type="string", value=wpt)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Land At Wpt w/ Dir Facing", params=params)

    def land_at_wpt_hdg(self, wpt: str) -> EventTarget:
        """Vertically land on a specified waypoint with the specified heading, if capable."""
        params = [ParamInfo(name="wpt", type="string", value=wpt)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Land At Wpt w/ Direction", params=params)

    def lase_target(self) -> EventTarget:
        """Command the pilot to laser designate a specific target, if able. It will continue on its current orbit or path. After the target is destroyed or the pilot receives another combat command, the pilot will stop laser designating."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Laser Designate Target")

    def lase_target_orbit(self) -> EventTarget:
        """Command the pilot to laser designate a specific target, if able. Set a custom orbit. After the target is destroyed or the pilot receives another combat command, the pilot will stop laser designating."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Laser Designate With Obit")

    def load_passengers(self) -> EventTarget:
        """Command the selected units to board this aircraft."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Load Passengers")

    def load_passenger_group(self) -> EventTarget:
        """Command the selected unit group to board this aircraft."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Load Unit Group")

    def set_orbit_now(self, wpt: str) -> EventTarget:
        """Command the aircraft to orbit a waypoint."""
        params = [ParamInfo(name="wpt", type="string", value=wpt)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Orbit Waypoint", params=params)

    def set_to_lasing_mode(self) -> EventTarget:
        """Set whether the pilot should only find and laser designate targets instead of attacking. It will continue on its current orbit or path. It will only designate ground units or slow moving aircraft. If it's in this state, commanding it to attack or engage/disengage will revert it to ordinary behavior."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Order Laser Designating")

    def randomize_alt_spawn(self) -> EventTarget:
        """Set a new random alternate spawn for this unit. Useful for respawning units in random places.  If the unit is in a group with synced alternates, the other units will have the same new alternate."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Randomize Alt Spawn")

    def rearm_at(self) -> EventTarget:
        """Land, rearm/refuel, and take off again from specified airfield."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Rearm")

    def refuel_with_unit(self) -> EventTarget:
        """Command the aircraft to refuel from a particular tanker."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Refuel From Tanker")

    def remove_designated_targets(self, targets: List[str]) -> EventTarget:
        """Remove a particular set of units from the designated targets."""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Designated Targets", params=params)

    def remove_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Non-Targets", params=params)

    def remove_priority_targets(self, targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Priority Targets", params=params)

    def set_altitude(self) -> EventTarget:
        """Set the aircraft's default altitude."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Altitude")

    def set_designated_targets(self, targets: List[str]) -> EventTarget:
        """Sets or replaces the AI pilot's designated targets, which it will attack at highest priority, immediately, whether or not these targets have been detected."""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Designated Targets", params=params)

    def set_engage_enemies(self, engage: bool) -> EventTarget:
        """Set whether the unit should engage enemies."""
        params = [ParamInfo(name="engage", type="bool", value=engage)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Engage Enemies", params=params)

    def set_formation_distance(self, dist: Literal["Close", "Medium", "Far", "Airshow"]) -> EventTarget:
        """Set the formation distance of AI aircraft when they follow this unit."""
        params = [ParamInfo(name="dist", type="string", value=dist)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Formation Distance", params=params)

    def set_invincible(self, i: bool) -> EventTarget:
        """Sets whether the unit can take damage."""
        params = [ParamInfo(name="i", type="bool", value=i)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Invincible", params=params)

    def set_jamming_at_will(self, j: bool) -> EventTarget:
        """Set whether the unit can jam targets of opportunity without being told to (if equipped)."""
        params = [ParamInfo(name="j", type="bool", value=j)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Jamming at Will", params=params)

    def set_nav_speed(self) -> EventTarget:
        """Set the aircraft's default navigation airspeed (when not in combat)."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Nav Speed")

    def set_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will not attack. (Overwrites existing list)"""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Non-Targets", params=params)

    def set_path(self, path: str) -> EventTarget:
        """Set the aircraft to fly along a path."""
        params = [ParamInfo(name="path", type="string", value=path)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Path", params=params)

    def set_player_commands(self, mode: Literal["Unit_Group_Only", "Force_Allow", "Force_Disallow"]) -> EventTarget:
        """Set whether the unit can be commanded by the player."""
        params = [ParamInfo(name="mode", type="string", value=mode)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Player Commands", params=params)

    def set_priority_targets(self, targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will prioritize when finding a target. (Overwrites existing list)"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Priority Targets", params=params)

    def set_radar(self, radar_on: bool) -> EventTarget:
        """Set's the unit's radar on or off, if it has one."""
        params = [ParamInfo(name="radarOn", type="bool", value=radar_on)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Radar", params=params)

    def set_radio_comms(self, radio_enabled: bool) -> EventTarget:
        """Set whether the AI pilot will communicate with the player via radio."""
        params = [ParamInfo(name="radioEnabled", type="bool", value=radio_enabled)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Radio Comms", params=params)

    def spawn_unit(self) -> EventTarget:
        """Spawn the unit if it hasn't already been spawned"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Spawn Unit")

    def take_off(self) -> EventTarget:
        """Command the pilot to take off."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Take Off")

    def taxi_path(self, path: str) -> EventTarget:
        """Command the aircraft to taxi on a certain path."""
        params = [ParamInfo(name="path", type="string", value=path)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Taxi Path", params=params)

    def taxi_path_speed(self, path: str) -> EventTarget:
        """Command the aircraft to taxi on a certain path at a certain speed."""
        params = [ParamInfo(name="path", type="string", value=path)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Taxi Path Speed", params=params)

    def unload_all_passengers(self, rally_wp: str) -> EventTarget:
        """Unload all passengers when available."""
        params = [ParamInfo(name="rallyWp", type="string", value=rally_wp)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Unload Passengers", params=params)



class AICarrierSpawnActions:
    """Actions callable on AICarrierSpawn."""
    def __init__(self, target_id: Any):
        self.target_id = target_id
        self.target_type = "AICarrierSpawn" # TODO: This may need adjustment depending on VTS format

    def add_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Non-Targets", params=params)

    def add_priority_targets(self, targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Priority Targets", params=params)

    def clear_non_targets(self) -> EventTarget:
        """Clear the list of units that this unit will not attack."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Non-Targets")

    def clear_priority_targets(self) -> EventTarget:
        """Clear the list of units that this unit will prioritize when finding a target"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Priority Targets")

    def destroy_self(self) -> EventTarget:
        """This event destroys the unit immediately."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Destroy")

    def force_alt_spawn(self) -> EventTarget:
        """Force a specific alternate spawn, overriding the random roll. This must be called BEFORE the unit spawns. If the unit is in a group with synced alternates, the other units will be forced as well."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Force Alt Spawn")

    def launch_all_aircraft(self) -> EventTarget:
        """Command all onboard aircraft to take off."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Launch All")

    def move_path(self, path: str) -> EventTarget:
        """Command the vessel to move along a path."""
        params = [ParamInfo(name="path", type="string", value=path)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Move Path", params=params)

    def move_to(self, target: str) -> EventTarget:
        """Command the vessel to move to a waypoint."""
        params = [ParamInfo(name="target", type="string", value=target)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Move To", params=params)

    def randomize_alt_spawn(self) -> EventTarget:
        """Set a new random alternate spawn for this unit. Useful for respawning units in random places.  If the unit is in a group with synced alternates, the other units will have the same new alternate."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Randomize Alt Spawn")

    def remove_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Non-Targets", params=params)

    def remove_priority_targets(self, targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Priority Targets", params=params)

    def set_engage_enemies(self, engage: bool) -> EventTarget:
        """Set whether the unit should engage enemies."""
        params = [ParamInfo(name="engage", type="bool", value=engage)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Engage Enemies", params=params)

    def set_invincible(self, i: bool) -> EventTarget:
        """Sets whether the unit can take damage."""
        params = [ParamInfo(name="i", type="bool", value=i)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Invincible", params=params)

    def set_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will not attack. (Overwrites existing list)"""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Non-Targets", params=params)

    def set_priority_targets(self, targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will prioritize when finding a target. (Overwrites existing list)"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Priority Targets", params=params)

    def spawn_unit(self) -> EventTarget:
        """Spawn the unit if it hasn't already been spawned"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Spawn Unit")

    def stop(self) -> EventTarget:
        """Command the vessel to stop where it is."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Stop")



class AIDecoyLauncherSpawnActions:
    """Actions callable on AIDecoyLauncherSpawn."""
    def __init__(self, target_id: Any):
        self.target_id = target_id
        self.target_type = "AIDecoyLauncherSpawn" # TODO: This may need adjustment depending on VTS format

    def add_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Non-Targets", params=params)

    def add_priority_targets(self, targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Priority Targets", params=params)

    def clear_non_targets(self) -> EventTarget:
        """Clear the list of units that this unit will not attack."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Non-Targets")

    def clear_priority_targets(self) -> EventTarget:
        """Clear the list of units that this unit will prioritize when finding a target"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Priority Targets")

    def destroy_self(self) -> EventTarget:
        """This event destroys the unit immediately."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Destroy")

    def force_alt_spawn(self) -> EventTarget:
        """Force a specific alternate spawn, overriding the random roll. This must be called BEFORE the unit spawns. If the unit is in a group with synced alternates, the other units will be forced as well."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Force Alt Spawn")

    def fire_decoy_path_a(self, model: Literal["B_11", "AV_42", "E_4", "F_45A", "FA_26B", "KC_49", "MQ_31", "T_55", "AEW_50", "Manta_UCAV", "ASF_30", "ASF_33", "ASF_58", "GAV_25", "T_55_E", "HB_106"], path: str) -> EventTarget:
        """Launches the decoy with the specified radar signature to follow a path"""
        params = [ParamInfo(name="model", type="string", value=model), ParamInfo(name="path", type="string", value=path)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Launch Decoy On Path", params=params)

    def fire_jammer_path(self, path: str) -> EventTarget:
        """Launches the decoy in jammer mode to follow a path."""
        params = [ParamInfo(name="path", type="string", value=path)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Launch Jammer On Path", params=params)

    def fire_decoy_path_a_random(self, path: str) -> EventTarget:
        """Launches the decoy with a random radar signature to follow a path."""
        params = [ParamInfo(name="path", type="string", value=path)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Launch Random Decoy On Path", params=params)

    def randomize_alt_spawn(self) -> EventTarget:
        """Set a new random alternate spawn for this unit. Useful for respawning units in random places.  If the unit is in a group with synced alternates, the other units will have the same new alternate."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Randomize Alt Spawn")

    def remove_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Non-Targets", params=params)

    def remove_priority_targets(self, targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Priority Targets", params=params)

    def set_engage_enemies(self, engage: bool) -> EventTarget:
        """Set whether the unit should engage enemies."""
        params = [ParamInfo(name="engage", type="bool", value=engage)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Engage Enemies", params=params)

    def set_invincible(self, i: bool) -> EventTarget:
        """Sets whether the unit can take damage."""
        params = [ParamInfo(name="i", type="bool", value=i)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Invincible", params=params)

    def set_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will not attack. (Overwrites existing list)"""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Non-Targets", params=params)

    def set_priority_targets(self, targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will prioritize when finding a target. (Overwrites existing list)"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Priority Targets", params=params)

    def spawn_unit(self) -> EventTarget:
        """Spawn the unit if it hasn't already been spawned"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Spawn Unit")



class AIDecoyRadarSpawnActions:
    """Actions callable on AIDecoyRadarSpawn."""
    def __init__(self, target_id: Any):
        self.target_id = target_id
        self.target_type = "AIDecoyRadarSpawn" # TODO: This may need adjustment depending on VTS format

    def add_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Non-Targets", params=params)

    def add_priority_targets(self, targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Priority Targets", params=params)

    def clear_non_targets(self) -> EventTarget:
        """Clear the list of units that this unit will not attack."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Non-Targets")

    def clear_priority_targets(self) -> EventTarget:
        """Clear the list of units that this unit will prioritize when finding a target"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Priority Targets")

    def destroy_self(self) -> EventTarget:
        """This event destroys the unit immediately."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Destroy")

    def force_alt_spawn(self) -> EventTarget:
        """Force a specific alternate spawn, overriding the random roll. This must be called BEFORE the unit spawns. If the unit is in a group with synced alternates, the other units will be forced as well."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Force Alt Spawn")

    def randomize_alt_spawn(self) -> EventTarget:
        """Set a new random alternate spawn for this unit. Useful for respawning units in random places.  If the unit is in a group with synced alternates, the other units will have the same new alternate."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Randomize Alt Spawn")

    def remove_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Non-Targets", params=params)

    def remove_priority_targets(self, targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Priority Targets", params=params)

    def set_engage_enemies(self, engage: bool) -> EventTarget:
        """Set whether the unit should engage enemies."""
        params = [ParamInfo(name="engage", type="bool", value=engage)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Engage Enemies", params=params)

    def set_invincible(self, i: bool) -> EventTarget:
        """Sets whether the unit can take damage."""
        params = [ParamInfo(name="i", type="bool", value=i)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Invincible", params=params)

    def set_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will not attack. (Overwrites existing list)"""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Non-Targets", params=params)

    def set_priority_targets(self, targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will prioritize when finding a target. (Overwrites existing list)"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Priority Targets", params=params)

    def spawn_unit(self) -> EventTarget:
        """Spawn the unit if it hasn't already been spawned"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Spawn Unit")



class AIDroneCarrierSpawnActions:
    """Actions callable on AIDroneCarrierSpawn."""
    def __init__(self, target_id: Any):
        self.target_id = target_id
        self.target_type = "AIDroneCarrierSpawn" # TODO: This may need adjustment depending on VTS format

    def add_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Non-Targets", params=params)

    def add_priority_targets(self, targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Priority Targets", params=params)

    def clear_non_targets(self) -> EventTarget:
        """Clear the list of units that this unit will not attack."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Non-Targets")

    def clear_priority_targets(self) -> EventTarget:
        """Clear the list of units that this unit will prioritize when finding a target"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Priority Targets")

    def destroy_self(self) -> EventTarget:
        """This event destroys the unit immediately."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Destroy")

    def force_alt_spawn(self) -> EventTarget:
        """Force a specific alternate spawn, overriding the random roll. This must be called BEFORE the unit spawns. If the unit is in a group with synced alternates, the other units will be forced as well."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Force Alt Spawn")

    def launch_drones(self) -> EventTarget:
        """Launch all drones from the carrier."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Launch Drones")

    def move_path(self, path: str) -> EventTarget:
        """Command the vessel to move along a path."""
        params = [ParamInfo(name="path", type="string", value=path)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Move Path", params=params)

    def move_to(self, target: str) -> EventTarget:
        """Command the vessel to move to a waypoint."""
        params = [ParamInfo(name="target", type="string", value=target)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Move To", params=params)

    def randomize_alt_spawn(self) -> EventTarget:
        """Set a new random alternate spawn for this unit. Useful for respawning units in random places.  If the unit is in a group with synced alternates, the other units will have the same new alternate."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Randomize Alt Spawn")

    def remove_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Non-Targets", params=params)

    def remove_priority_targets(self, targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Priority Targets", params=params)

    def set_engage_enemies(self, engage: bool) -> EventTarget:
        """Set whether the unit should engage enemies."""
        params = [ParamInfo(name="engage", type="bool", value=engage)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Engage Enemies", params=params)

    def set_invincible(self, i: bool) -> EventTarget:
        """Sets whether the unit can take damage."""
        params = [ParamInfo(name="i", type="bool", value=i)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Invincible", params=params)

    def set_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will not attack. (Overwrites existing list)"""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Non-Targets", params=params)

    def set_priority_targets(self, targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will prioritize when finding a target. (Overwrites existing list)"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Priority Targets", params=params)

    def spawn_unit(self) -> EventTarget:
        """Spawn the unit if it hasn't already been spawned"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Spawn Unit")

    def stop(self) -> EventTarget:
        """Command the vessel to stop where it is."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Stop")



class AIFixedSAMSpawnActions:
    """Actions callable on AIFixedSAMSpawn."""
    def __init__(self, target_id: Any):
        self.target_id = target_id
        self.target_type = "AIFixedSAMSpawn" # TODO: This may need adjustment depending on VTS format

    def add_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Non-Targets", params=params)

    def add_priority_targets(self, targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Priority Targets", params=params)

    def board_a_i_bay(self) -> EventTarget:
        """Command the unit to board an AI vehicle's passenger bay."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Board Vehicle")

    def clear_non_targets(self) -> EventTarget:
        """Clear the list of units that this unit will not attack."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Non-Targets")

    def clear_priority_targets(self) -> EventTarget:
        """Clear the list of units that this unit will prioritize when finding a target"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Priority Targets")

    def destroy_self(self) -> EventTarget:
        """This event destroys the unit immediately."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Destroy")

    def dismount_a_i_bay(self, wp: str) -> EventTarget:
        """Command the unit to dismount the vehicle it's riding when available. It will move towards Rally Point once dismounted."""
        params = [ParamInfo(name="wp", type="string", value=wp)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Dismount Vehicle", params=params)

    def force_alt_spawn(self) -> EventTarget:
        """Force a specific alternate spawn, overriding the random roll. This must be called BEFORE the unit spawns. If the unit is in a group with synced alternates, the other units will be forced as well."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Force Alt Spawn")

    def move_to(self, wpt: str) -> EventTarget:
        """Command the unit to move directly to a waypoint."""
        params = [ParamInfo(name="wpt", type="string", value=wpt)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Move To", params=params)

    def move_to_point(self, point: str) -> EventTarget:
        """Command the unit to move directly to an arbitrary point."""
        params = [ParamInfo(name="point", type="string", value=point)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Move To Point", params=params)

    def park_now(self) -> EventTarget:
        """Command the unit to park where it stands."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Park Now")

    def randomize_alt_spawn(self) -> EventTarget:
        """Set a new random alternate spawn for this unit. Useful for respawning units in random places.  If the unit is in a group with synced alternates, the other units will have the same new alternate."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Randomize Alt Spawn")

    def reload_now(self) -> EventTarget:
        """Force the launcher to reload now."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Reload")

    def remove_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Non-Targets", params=params)

    def remove_priority_targets(self, targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Priority Targets", params=params)

    def set_allow_reload(self, allowed: bool) -> EventTarget:
        """Set whether the launcher is allowed to reload."""
        params = [ParamInfo(name="allowed", type="bool", value=allowed)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Allow Reloads", params=params)

    def set_engage_enemies(self, engage: bool) -> EventTarget:
        """Set whether the unit should engage enemies."""
        params = [ParamInfo(name="engage", type="bool", value=engage)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Engage Enemies", params=params)

    def set_i_r_strobe_enabled(self, e: bool) -> EventTarget:
        """Toggle an infrared strobe signal that can only be seen in nightvision."""
        params = [ParamInfo(name="e", type="bool", value=e)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set IR Strobe", params=params)

    def set_invincible(self, i: bool) -> EventTarget:
        """Sets whether the unit can take damage."""
        params = [ParamInfo(name="i", type="bool", value=i)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Invincible", params=params)

    def set_movement_speed(self, s: Literal["Slow_10", "Medium_20", "Fast_30"]) -> EventTarget:
        """Set the movement speed of this ground vehicle."""
        params = [ParamInfo(name="s", type="string", value=s)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Movement Speed", params=params)

    def set_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will not attack. (Overwrites existing list)"""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Non-Targets", params=params)

    def set_path(self, path: str) -> EventTarget:
        """Command the unit to move along a path (if able)."""
        params = [ParamInfo(name="path", type="string", value=path)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Path", params=params)

    def set_priority_targets(self, targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will prioritize when finding a target. (Overwrites existing list)"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Priority Targets", params=params)

    def set_reload_time(self) -> EventTarget:
        """Set the reload time for the launcher."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Reload Time")

    def spawn_unit(self) -> EventTarget:
        """Spawn the unit if it hasn't already been spawned"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Spawn Unit")



class AIGroundECMSpawnActions:
    """Actions callable on AIGroundECMSpawn."""
    def __init__(self, target_id: Any):
        self.target_id = target_id
        self.target_type = "AIGroundECMSpawn" # TODO: This may need adjustment depending on VTS format

    def add_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Non-Targets", params=params)

    def add_priority_targets(self, targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Priority Targets", params=params)

    def v_t__auto_mode(self) -> EventTarget:
        """Set to the default auto mode -- the unit will find and jam any detected radar emissions."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Auto Mode")

    def v_t__auto_target_band(self, band: Literal["Low", "Mid", "High"]) -> EventTarget:
        """Automatically find and engage targets but use a specific band. Useful for GPS/Comms jamming in low band."""
        params = [ParamInfo(name="band", type="string", value=band)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Auto-target on Band", params=params)

    def board_a_i_bay(self) -> EventTarget:
        """Command the unit to board an AI vehicle's passenger bay."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Board Vehicle")

    def clear_non_targets(self) -> EventTarget:
        """Clear the list of units that this unit will not attack."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Non-Targets")

    def clear_priority_targets(self) -> EventTarget:
        """Clear the list of units that this unit will prioritize when finding a target"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Priority Targets")

    def destroy_self(self) -> EventTarget:
        """This event destroys the unit immediately."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Destroy")

    def dismount_a_i_bay(self, wp: str) -> EventTarget:
        """Command the unit to dismount the vehicle it's riding when available. It will move towards Rally Point once dismounted."""
        params = [ParamInfo(name="wp", type="string", value=wp)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Dismount Vehicle", params=params)

    def force_alt_spawn(self) -> EventTarget:
        """Force a specific alternate spawn, overriding the random roll. This must be called BEFORE the unit spawns. If the unit is in a group with synced alternates, the other units will be forced as well."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Force Alt Spawn")

    def v_t__manual_direction(self) -> EventTarget:
        """Set the unit to transmit noise at the specified direction and frequency. Use for defending a general area."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Manual Direction")

    def v_t__manual_target(self) -> EventTarget:
        """Set the unit to only target this specific target at the specified frequency band, if able, otherwise remain inactive."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Manual Target")

    def move_to(self, wpt: str) -> EventTarget:
        """Command the unit to move directly to a waypoint."""
        params = [ParamInfo(name="wpt", type="string", value=wpt)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Move To", params=params)

    def move_to_point(self, point: str) -> EventTarget:
        """Command the unit to move directly to an arbitrary point."""
        params = [ParamInfo(name="point", type="string", value=point)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Move To Point", params=params)

    def park_now(self) -> EventTarget:
        """Command the unit to park where it stands."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Park Now")

    def randomize_alt_spawn(self) -> EventTarget:
        """Set a new random alternate spawn for this unit. Useful for respawning units in random places.  If the unit is in a group with synced alternates, the other units will have the same new alternate."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Randomize Alt Spawn")

    def remove_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Non-Targets", params=params)

    def remove_priority_targets(self, targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Priority Targets", params=params)

    def set_engage_enemies(self, engage: bool) -> EventTarget:
        """Set whether the unit should engage enemies."""
        params = [ParamInfo(name="engage", type="bool", value=engage)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Engage Enemies", params=params)

    def set_i_r_strobe_enabled(self, e: bool) -> EventTarget:
        """Toggle an infrared strobe signal that can only be seen in nightvision."""
        params = [ParamInfo(name="e", type="bool", value=e)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set IR Strobe", params=params)

    def set_invincible(self, i: bool) -> EventTarget:
        """Sets whether the unit can take damage."""
        params = [ParamInfo(name="i", type="bool", value=i)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Invincible", params=params)

    def set_movement_speed(self, s: Literal["Slow_10", "Medium_20", "Fast_30"]) -> EventTarget:
        """Set the movement speed of this ground vehicle."""
        params = [ParamInfo(name="s", type="string", value=s)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Movement Speed", params=params)

    def set_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will not attack. (Overwrites existing list)"""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Non-Targets", params=params)

    def set_path(self, path: str) -> EventTarget:
        """Command the unit to move along a path (if able)."""
        params = [ParamInfo(name="path", type="string", value=path)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Path", params=params)

    def set_priority_targets(self, targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will prioritize when finding a target. (Overwrites existing list)"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Priority Targets", params=params)

    def spawn_unit(self) -> EventTarget:
        """Spawn the unit if it hasn't already been spawned"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Spawn Unit")



class AIGroundMWSSpawnActions:
    """Actions callable on AIGroundMWSSpawn."""
    def __init__(self, target_id: Any):
        self.target_id = target_id
        self.target_type = "AIGroundMWSSpawn" # TODO: This may need adjustment depending on VTS format

    def add_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Non-Targets", params=params)

    def add_priority_targets(self, targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Priority Targets", params=params)

    def board_a_i_bay(self) -> EventTarget:
        """Command the unit to board an AI vehicle's passenger bay."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Board Vehicle")

    def clear_non_targets(self) -> EventTarget:
        """Clear the list of units that this unit will not attack."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Non-Targets")

    def clear_priority_targets(self) -> EventTarget:
        """Clear the list of units that this unit will prioritize when finding a target"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Priority Targets")

    def destroy_self(self) -> EventTarget:
        """This event destroys the unit immediately."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Destroy")

    def dismount_a_i_bay(self, wp: str) -> EventTarget:
        """Command the unit to dismount the vehicle it's riding when available. It will move towards Rally Point once dismounted."""
        params = [ParamInfo(name="wp", type="string", value=wp)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Dismount Vehicle", params=params)

    def force_alt_spawn(self) -> EventTarget:
        """Force a specific alternate spawn, overriding the random roll. This must be called BEFORE the unit spawns. If the unit is in a group with synced alternates, the other units will be forced as well."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Force Alt Spawn")

    def move_to(self, wpt: str) -> EventTarget:
        """Command the unit to move directly to a waypoint."""
        params = [ParamInfo(name="wpt", type="string", value=wpt)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Move To", params=params)

    def move_to_point(self, point: str) -> EventTarget:
        """Command the unit to move directly to an arbitrary point."""
        params = [ParamInfo(name="point", type="string", value=point)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Move To Point", params=params)

    def park_now(self) -> EventTarget:
        """Command the unit to park where it stands."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Park Now")

    def randomize_alt_spawn(self) -> EventTarget:
        """Set a new random alternate spawn for this unit. Useful for respawning units in random places.  If the unit is in a group with synced alternates, the other units will have the same new alternate."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Randomize Alt Spawn")

    def remove_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Non-Targets", params=params)

    def remove_priority_targets(self, targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Priority Targets", params=params)

    def set_engage_enemies(self, engage: bool) -> EventTarget:
        """Set whether the unit should engage enemies."""
        params = [ParamInfo(name="engage", type="bool", value=engage)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Engage Enemies", params=params)

    def set_i_r_strobe_enabled(self, e: bool) -> EventTarget:
        """Toggle an infrared strobe signal that can only be seen in nightvision."""
        params = [ParamInfo(name="e", type="bool", value=e)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set IR Strobe", params=params)

    def set_invincible(self, i: bool) -> EventTarget:
        """Sets whether the unit can take damage."""
        params = [ParamInfo(name="i", type="bool", value=i)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Invincible", params=params)

    def set_movement_speed(self, s: Literal["Slow_10", "Medium_20", "Fast_30"]) -> EventTarget:
        """Set the movement speed of this ground vehicle."""
        params = [ParamInfo(name="s", type="string", value=s)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Movement Speed", params=params)

    def set_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will not attack. (Overwrites existing list)"""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Non-Targets", params=params)

    def set_path(self, path: str) -> EventTarget:
        """Command the unit to move along a path (if able)."""
        params = [ParamInfo(name="path", type="string", value=path)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Path", params=params)

    def set_priority_targets(self, targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will prioritize when finding a target. (Overwrites existing list)"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Priority Targets", params=params)

    def spawn_unit(self) -> EventTarget:
        """Spawn the unit if it hasn't already been spawned"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Spawn Unit")



class AIJTACSpawnActions:
    """Actions callable on AIJTACSpawn."""
    def __init__(self, target_id: Any):
        self.target_id = target_id
        self.target_type = "AIJTACSpawn" # TODO: This may need adjustment depending on VTS format

    def add_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Non-Targets", params=params)

    def add_priority_targets(self, targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Priority Targets", params=params)

    def board_a_i_bay(self) -> EventTarget:
        """Command the unit to board an AI vehicle's passenger bay."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Board Vehicle")

    def clear_non_targets(self) -> EventTarget:
        """Clear the list of units that this unit will not attack."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Non-Targets")

    def clear_priority_targets(self) -> EventTarget:
        """Clear the list of units that this unit will prioritize when finding a target"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Priority Targets")

    def destroy_self(self) -> EventTarget:
        """This event destroys the unit immediately."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Destroy")

    def dismount_a_i_bay(self, wp: str) -> EventTarget:
        """Command the unit to dismount the vehicle it's riding when available. It will move towards Rally Point once dismounted."""
        params = [ParamInfo(name="wp", type="string", value=wp)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Dismount Vehicle", params=params)

    def force_alt_spawn(self) -> EventTarget:
        """Force a specific alternate spawn, overriding the random roll. This must be called BEFORE the unit spawns. If the unit is in a group with synced alternates, the other units will be forced as well."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Force Alt Spawn")

    def j_t_a_c_lase_position(self) -> EventTarget:
        """Command this soldier to laser designate a target position for airstrike. The soldier will stop moving and attacking. Max range: 20km."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="JTAC Lase Position")

    def j_t_a_c_lase_unit(self) -> EventTarget:
        """Command this soldier to laser designate a target unit for airstrike. The target should be slow moving or stationary. The soldier will stop moving and attacking. Max range: 20km."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="JTAC Lase Unit")

    def j_t_a_c_lase_units(self) -> EventTarget:
        """Command this soldier to laser designate any target in this list until all targets are destroyed. The soldier will find a new target if the current one is hidden or destroyed. The soldier will stop moving and attacking. Max range: 20km."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="JTAC Lase Units")

    def j_t_a_c_lase_waypoint(self) -> EventTarget:
        """Command this soldier to laser designate a target waypoint for airstrike. The soldier will stop moving and attacking. Max range: 20km."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="JTAC Lase Waypoint")

    def move_to(self, wpt: str) -> EventTarget:
        """Command the unit to move directly to a waypoint."""
        params = [ParamInfo(name="wpt", type="string", value=wpt)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Move To", params=params)

    def move_to_point(self, point: str) -> EventTarget:
        """Command the unit to move directly to an arbitrary point."""
        params = [ParamInfo(name="point", type="string", value=point)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Move To Point", params=params)

    def park_now(self) -> EventTarget:
        """Command the unit to park where it stands."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Park Now")

    def randomize_alt_spawn(self) -> EventTarget:
        """Set a new random alternate spawn for this unit. Useful for respawning units in random places.  If the unit is in a group with synced alternates, the other units will have the same new alternate."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Randomize Alt Spawn")

    def remove_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Non-Targets", params=params)

    def remove_priority_targets(self, targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Priority Targets", params=params)

    def set_engage_enemies(self, engage: bool) -> EventTarget:
        """Set whether the unit should engage enemies."""
        params = [ParamInfo(name="engage", type="bool", value=engage)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Engage Enemies", params=params)

    def set_i_r_strobe_enabled(self, e: bool) -> EventTarget:
        """Toggle an infrared strobe signal that can only be seen in nightvision."""
        params = [ParamInfo(name="e", type="bool", value=e)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set IR Strobe", params=params)

    def set_invincible(self, i: bool) -> EventTarget:
        """Sets whether the unit can take damage."""
        params = [ParamInfo(name="i", type="bool", value=i)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Invincible", params=params)

    def set_movement_speed(self, s: Literal["Slow_10", "Medium_20", "Fast_30"]) -> EventTarget:
        """Set the movement speed of this ground vehicle."""
        params = [ParamInfo(name="s", type="string", value=s)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Movement Speed", params=params)

    def set_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will not attack. (Overwrites existing list)"""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Non-Targets", params=params)

    def set_path(self, path: str) -> EventTarget:
        """Command the unit to move along a path (if able)."""
        params = [ParamInfo(name="path", type="string", value=path)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Path", params=params)

    def set_priority_targets(self, targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will prioritize when finding a target. (Overwrites existing list)"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Priority Targets", params=params)

    def spawn_unit(self) -> EventTarget:
        """Spawn the unit if it hasn't already been spawned"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Spawn Unit")

    def stop_j_t_a_c_laser(self) -> EventTarget:
        """Command this soldier to stop lasing the target."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Stop JTAC Laser")



class AILockingRadarSpawnActions:
    """Actions callable on AILockingRadarSpawn."""
    def __init__(self, target_id: Any):
        self.target_id = target_id
        self.target_type = "AILockingRadarSpawn" # TODO: This may need adjustment depending on VTS format

    def add_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Non-Targets", params=params)

    def add_priority_targets(self, targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Priority Targets", params=params)

    def board_a_i_bay(self) -> EventTarget:
        """Command the unit to board an AI vehicle's passenger bay."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Board Vehicle")

    def clear_non_targets(self) -> EventTarget:
        """Clear the list of units that this unit will not attack."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Non-Targets")

    def clear_priority_targets(self) -> EventTarget:
        """Clear the list of units that this unit will prioritize when finding a target"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Priority Targets")

    def destroy_self(self) -> EventTarget:
        """This event destroys the unit immediately."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Destroy")

    def dismount_a_i_bay(self, wp: str) -> EventTarget:
        """Command the unit to dismount the vehicle it's riding when available. It will move towards Rally Point once dismounted."""
        params = [ParamInfo(name="wp", type="string", value=wp)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Dismount Vehicle", params=params)

    def force_alt_spawn(self) -> EventTarget:
        """Force a specific alternate spawn, overriding the random roll. This must be called BEFORE the unit spawns. If the unit is in a group with synced alternates, the other units will be forced as well."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Force Alt Spawn")

    def move_to(self, wpt: str) -> EventTarget:
        """Command the unit to move directly to a waypoint."""
        params = [ParamInfo(name="wpt", type="string", value=wpt)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Move To", params=params)

    def move_to_point(self, point: str) -> EventTarget:
        """Command the unit to move directly to an arbitrary point."""
        params = [ParamInfo(name="point", type="string", value=point)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Move To Point", params=params)

    def park_now(self) -> EventTarget:
        """Command the unit to park where it stands."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Park Now")

    def randomize_alt_spawn(self) -> EventTarget:
        """Set a new random alternate spawn for this unit. Useful for respawning units in random places.  If the unit is in a group with synced alternates, the other units will have the same new alternate."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Randomize Alt Spawn")

    def remove_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Non-Targets", params=params)

    def remove_priority_targets(self, targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Priority Targets", params=params)

    def set_engage_enemies(self, engage: bool) -> EventTarget:
        """Set whether the unit should engage enemies."""
        params = [ParamInfo(name="engage", type="bool", value=engage)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Engage Enemies", params=params)

    def set_i_r_strobe_enabled(self, e: bool) -> EventTarget:
        """Toggle an infrared strobe signal that can only be seen in nightvision."""
        params = [ParamInfo(name="e", type="bool", value=e)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set IR Strobe", params=params)

    def set_invincible(self, i: bool) -> EventTarget:
        """Sets whether the unit can take damage."""
        params = [ParamInfo(name="i", type="bool", value=i)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Invincible", params=params)

    def set_movement_speed(self, s: Literal["Slow_10", "Medium_20", "Fast_30"]) -> EventTarget:
        """Set the movement speed of this ground vehicle."""
        params = [ParamInfo(name="s", type="string", value=s)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Movement Speed", params=params)

    def set_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will not attack. (Overwrites existing list)"""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Non-Targets", params=params)

    def set_path(self, path: str) -> EventTarget:
        """Command the unit to move along a path (if able)."""
        params = [ParamInfo(name="path", type="string", value=path)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Path", params=params)

    def set_priority_targets(self, targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will prioritize when finding a target. (Overwrites existing list)"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Priority Targets", params=params)

    def spawn_unit(self) -> EventTarget:
        """Spawn the unit if it hasn't already been spawned"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Spawn Unit")



class AIMissileSiloActions:
    """Actions callable on AIMissileSilo."""
    def __init__(self, target_id: Any):
        self.target_id = target_id
        self.target_type = "AIMissileSilo" # TODO: This may need adjustment depending on VTS format

    def add_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Non-Targets", params=params)

    def add_priority_targets(self, targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Priority Targets", params=params)

    def v_t__begin_launch(self) -> EventTarget:
        """Begin a launch countdown."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Begin Launch")

    def clear_non_targets(self) -> EventTarget:
        """Clear the list of units that this unit will not attack."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Non-Targets")

    def clear_priority_targets(self) -> EventTarget:
        """Clear the list of units that this unit will prioritize when finding a target"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Priority Targets")

    def destroy_self(self) -> EventTarget:
        """This event destroys the unit immediately."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Destroy")

    def force_alt_spawn(self) -> EventTarget:
        """Force a specific alternate spawn, overriding the random roll. This must be called BEFORE the unit spawns. If the unit is in a group with synced alternates, the other units will be forced as well."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Force Alt Spawn")

    def randomize_alt_spawn(self) -> EventTarget:
        """Set a new random alternate spawn for this unit. Useful for respawning units in random places.  If the unit is in a group with synced alternates, the other units will have the same new alternate."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Randomize Alt Spawn")

    def remove_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Non-Targets", params=params)

    def remove_priority_targets(self, targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Priority Targets", params=params)

    def set_engage_enemies(self, engage: bool) -> EventTarget:
        """Set whether the unit should engage enemies."""
        params = [ParamInfo(name="engage", type="bool", value=engage)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Engage Enemies", params=params)

    def set_invincible(self, i: bool) -> EventTarget:
        """Sets whether the unit can take damage."""
        params = [ParamInfo(name="i", type="bool", value=i)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Invincible", params=params)

    def set_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will not attack. (Overwrites existing list)"""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Non-Targets", params=params)

    def set_priority_targets(self, targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will prioritize when finding a target. (Overwrites existing list)"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Priority Targets", params=params)

    def spawn_unit(self) -> EventTarget:
        """Spawn the unit if it hasn't already been spawned"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Spawn Unit")



class AISeaUnitSpawnActions:
    """Actions callable on AISeaUnitSpawn."""
    def __init__(self, target_id: Any):
        self.target_id = target_id
        self.target_type = "AISeaUnitSpawn" # TODO: This may need adjustment depending on VTS format

    def add_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Non-Targets", params=params)

    def add_priority_targets(self, targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Priority Targets", params=params)

    def clear_non_targets(self) -> EventTarget:
        """Clear the list of units that this unit will not attack."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Non-Targets")

    def clear_priority_targets(self) -> EventTarget:
        """Clear the list of units that this unit will prioritize when finding a target"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Priority Targets")

    def destroy_self(self) -> EventTarget:
        """This event destroys the unit immediately."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Destroy")

    def force_alt_spawn(self) -> EventTarget:
        """Force a specific alternate spawn, overriding the random roll. This must be called BEFORE the unit spawns. If the unit is in a group with synced alternates, the other units will be forced as well."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Force Alt Spawn")

    def move_path(self, path: str) -> EventTarget:
        """Command the vessel to move along a path."""
        params = [ParamInfo(name="path", type="string", value=path)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Move Path", params=params)

    def move_to(self, target: str) -> EventTarget:
        """Command the vessel to move to a waypoint."""
        params = [ParamInfo(name="target", type="string", value=target)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Move To", params=params)

    def randomize_alt_spawn(self) -> EventTarget:
        """Set a new random alternate spawn for this unit. Useful for respawning units in random places.  If the unit is in a group with synced alternates, the other units will have the same new alternate."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Randomize Alt Spawn")

    def remove_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Non-Targets", params=params)

    def remove_priority_targets(self, targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Priority Targets", params=params)

    def set_engage_enemies(self, engage: bool) -> EventTarget:
        """Set whether the unit should engage enemies."""
        params = [ParamInfo(name="engage", type="bool", value=engage)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Engage Enemies", params=params)

    def set_invincible(self, i: bool) -> EventTarget:
        """Sets whether the unit can take damage."""
        params = [ParamInfo(name="i", type="bool", value=i)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Invincible", params=params)

    def set_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will not attack. (Overwrites existing list)"""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Non-Targets", params=params)

    def set_priority_targets(self, targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will prioritize when finding a target. (Overwrites existing list)"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Priority Targets", params=params)

    def spawn_unit(self) -> EventTarget:
        """Spawn the unit if it hasn't already been spawned"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Spawn Unit")

    def stop(self) -> EventTarget:
        """Command the vessel to stop where it is."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Stop")



class AIUnitSpawnActions:
    """Actions callable on AIUnitSpawn."""
    def __init__(self, target_id: Any):
        self.target_id = target_id
        self.target_type = "AIUnitSpawn" # TODO: This may need adjustment depending on VTS format

    def add_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Non-Targets", params=params)

    def add_priority_targets(self, targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Priority Targets", params=params)

    def clear_non_targets(self) -> EventTarget:
        """Clear the list of units that this unit will not attack."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Non-Targets")

    def clear_priority_targets(self) -> EventTarget:
        """Clear the list of units that this unit will prioritize when finding a target"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Priority Targets")

    def destroy_self(self) -> EventTarget:
        """This event destroys the unit immediately."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Destroy")

    def force_alt_spawn(self) -> EventTarget:
        """Force a specific alternate spawn, overriding the random roll. This must be called BEFORE the unit spawns. If the unit is in a group with synced alternates, the other units will be forced as well."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Force Alt Spawn")

    def randomize_alt_spawn(self) -> EventTarget:
        """Set a new random alternate spawn for this unit. Useful for respawning units in random places.  If the unit is in a group with synced alternates, the other units will have the same new alternate."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Randomize Alt Spawn")

    def remove_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Non-Targets", params=params)

    def remove_priority_targets(self, targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Priority Targets", params=params)

    def set_engage_enemies(self, engage: bool) -> EventTarget:
        """Set whether the unit should engage enemies."""
        params = [ParamInfo(name="engage", type="bool", value=engage)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Engage Enemies", params=params)

    def set_invincible(self, i: bool) -> EventTarget:
        """Sets whether the unit can take damage."""
        params = [ParamInfo(name="i", type="bool", value=i)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Invincible", params=params)

    def set_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will not attack. (Overwrites existing list)"""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Non-Targets", params=params)

    def set_priority_targets(self, targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will prioritize when finding a target. (Overwrites existing list)"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Priority Targets", params=params)

    def spawn_unit(self) -> EventTarget:
        """Spawn the unit if it hasn't already been spawned"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Spawn Unit")



class AIUnitSpawnEquippableActions:
    """Actions callable on AIUnitSpawnEquippable."""
    def __init__(self, target_id: Any):
        self.target_id = target_id
        self.target_type = "AIUnitSpawnEquippable" # TODO: This may need adjustment depending on VTS format

    def add_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Non-Targets", params=params)

    def add_priority_targets(self, targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Priority Targets", params=params)

    def clear_non_targets(self) -> EventTarget:
        """Clear the list of units that this unit will not attack."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Non-Targets")

    def clear_priority_targets(self) -> EventTarget:
        """Clear the list of units that this unit will prioritize when finding a target"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Priority Targets")

    def destroy_self(self) -> EventTarget:
        """This event destroys the unit immediately."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Destroy")

    def force_alt_spawn(self) -> EventTarget:
        """Force a specific alternate spawn, overriding the random roll. This must be called BEFORE the unit spawns. If the unit is in a group with synced alternates, the other units will be forced as well."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Force Alt Spawn")

    def randomize_alt_spawn(self) -> EventTarget:
        """Set a new random alternate spawn for this unit. Useful for respawning units in random places.  If the unit is in a group with synced alternates, the other units will have the same new alternate."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Randomize Alt Spawn")

    def remove_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Non-Targets", params=params)

    def remove_priority_targets(self, targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Priority Targets", params=params)

    def set_engage_enemies(self, engage: bool) -> EventTarget:
        """Set whether the unit should engage enemies."""
        params = [ParamInfo(name="engage", type="bool", value=engage)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Engage Enemies", params=params)

    def set_invincible(self, i: bool) -> EventTarget:
        """Sets whether the unit can take damage."""
        params = [ParamInfo(name="i", type="bool", value=i)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Invincible", params=params)

    def set_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will not attack. (Overwrites existing list)"""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Non-Targets", params=params)

    def set_priority_targets(self, targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will prioritize when finding a target. (Overwrites existing list)"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Priority Targets", params=params)

    def spawn_unit(self) -> EventTarget:
        """Spawn the unit if it hasn't already been spawned"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Spawn Unit")



class APCUnitSpawnActions:
    """Actions callable on APCUnitSpawn."""
    def __init__(self, target_id: Any):
        self.target_id = target_id
        self.target_type = "APCUnitSpawn" # TODO: This may need adjustment depending on VTS format

    def add_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Non-Targets", params=params)

    def add_priority_targets(self, targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Priority Targets", params=params)

    def board_a_i_bay(self) -> EventTarget:
        """Command the unit to board an AI vehicle's passenger bay."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Board Vehicle")

    def clear_non_targets(self) -> EventTarget:
        """Clear the list of units that this unit will not attack."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Non-Targets")

    def clear_priority_targets(self) -> EventTarget:
        """Clear the list of units that this unit will prioritize when finding a target"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Priority Targets")

    def destroy_self(self) -> EventTarget:
        """This event destroys the unit immediately."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Destroy")

    def dismount_a_i_bay(self, wp: str) -> EventTarget:
        """Command the unit to dismount the vehicle it's riding when available. It will move towards Rally Point once dismounted."""
        params = [ParamInfo(name="wp", type="string", value=wp)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Dismount Vehicle", params=params)

    def force_alt_spawn(self) -> EventTarget:
        """Force a specific alternate spawn, overriding the random roll. This must be called BEFORE the unit spawns. If the unit is in a group with synced alternates, the other units will be forced as well."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Force Alt Spawn")

    def load_passengers(self) -> EventTarget:
        """Command the selected units to board this aircraft."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Load Passengers")

    def load_passenger_group(self) -> EventTarget:
        """Command the selected unit group to board this aircraft."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Load Unit Group")

    def move_to(self, wpt: str) -> EventTarget:
        """Command the unit to move directly to a waypoint."""
        params = [ParamInfo(name="wpt", type="string", value=wpt)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Move To", params=params)

    def move_to_point(self, point: str) -> EventTarget:
        """Command the unit to move directly to an arbitrary point."""
        params = [ParamInfo(name="point", type="string", value=point)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Move To Point", params=params)

    def park_now(self) -> EventTarget:
        """Command the unit to park where it stands."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Park Now")

    def randomize_alt_spawn(self) -> EventTarget:
        """Set a new random alternate spawn for this unit. Useful for respawning units in random places.  If the unit is in a group with synced alternates, the other units will have the same new alternate."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Randomize Alt Spawn")

    def remove_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Non-Targets", params=params)

    def remove_priority_targets(self, targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Priority Targets", params=params)

    def set_engage_enemies(self, engage: bool) -> EventTarget:
        """Set whether the unit should engage enemies."""
        params = [ParamInfo(name="engage", type="bool", value=engage)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Engage Enemies", params=params)

    def set_i_r_strobe_enabled(self, e: bool) -> EventTarget:
        """Toggle an infrared strobe signal that can only be seen in nightvision."""
        params = [ParamInfo(name="e", type="bool", value=e)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set IR Strobe", params=params)

    def set_invincible(self, i: bool) -> EventTarget:
        """Sets whether the unit can take damage."""
        params = [ParamInfo(name="i", type="bool", value=i)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Invincible", params=params)

    def set_movement_speed(self, s: Literal["Slow_10", "Medium_20", "Fast_30"]) -> EventTarget:
        """Set the movement speed of this ground vehicle."""
        params = [ParamInfo(name="s", type="string", value=s)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Movement Speed", params=params)

    def set_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will not attack. (Overwrites existing list)"""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Non-Targets", params=params)

    def set_path(self, path: str) -> EventTarget:
        """Command the unit to move along a path (if able)."""
        params = [ParamInfo(name="path", type="string", value=path)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Path", params=params)

    def set_priority_targets(self, targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will prioritize when finding a target. (Overwrites existing list)"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Priority Targets", params=params)

    def spawn_unit(self) -> EventTarget:
        """Spawn the unit if it hasn't already been spawned"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Spawn Unit")

    def unload_all_passengers(self, rally_wp: str) -> EventTarget:
        """Unload all passengers when available."""
        params = [ParamInfo(name="rallyWp", type="string", value=rally_wp)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Unload Passengers", params=params)



class ArtilleryUnitSpawnActions:
    """Actions callable on ArtilleryUnitSpawn."""
    def __init__(self, target_id: Any):
        self.target_id = target_id
        self.target_type = "ArtilleryUnitSpawn" # TODO: This may need adjustment depending on VTS format

    def add_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Non-Targets", params=params)

    def add_priority_targets(self, targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Priority Targets", params=params)

    def board_a_i_bay(self) -> EventTarget:
        """Command the unit to board an AI vehicle's passenger bay."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Board Vehicle")

    def clear_fire_orders(self) -> EventTarget:
        """Clears any existing fire orders for the artillery unit."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Fire Orders")

    def clear_non_targets(self) -> EventTarget:
        """Clear the list of units that this unit will not attack."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Non-Targets")

    def clear_priority_targets(self) -> EventTarget:
        """Clear the list of units that this unit will prioritize when finding a target"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Priority Targets")

    def destroy_self(self) -> EventTarget:
        """This event destroys the unit immediately."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Destroy")

    def dismount_a_i_bay(self, wp: str) -> EventTarget:
        """Command the unit to dismount the vehicle it's riding when available. It will move towards Rally Point once dismounted."""
        params = [ParamInfo(name="wp", type="string", value=wp)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Dismount Vehicle", params=params)

    def fire_on_unit(self) -> EventTarget:
        """Commands the artillery unit to fire on a specific unit if it's in range."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Fire On Unit")

    def fire_on_waypoint(self, wpt: str) -> EventTarget:
        """Commands the artillery unit to fire a single salvo on a waypoint position if it's in range."""
        params = [ParamInfo(name="wpt", type="string", value=wpt)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Fire On Waypoint", params=params)

    def fire_multi_on_waypoint(self, wpt: str) -> EventTarget:
        """Commands the artillery unit to fire a number of salvos on a waypoint position if it's in range."""
        params = [ParamInfo(name="wpt", type="string", value=wpt)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Fire Salvos On Waypoint", params=params)

    def fire_multi_on_waypoint_radius(self, wpt: str) -> EventTarget:
        """Commands the artillery unit to fire a number of salvos spread out over an area around a position if it's in range."""
        params = [ParamInfo(name="wpt", type="string", value=wpt)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Fire Salvos On Waypoint Radius", params=params)

    def force_alt_spawn(self) -> EventTarget:
        """Force a specific alternate spawn, overriding the random roll. This must be called BEFORE the unit spawns. If the unit is in a group with synced alternates, the other units will be forced as well."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Force Alt Spawn")

    def move_to(self, wpt: str) -> EventTarget:
        """Command the unit to move directly to a waypoint."""
        params = [ParamInfo(name="wpt", type="string", value=wpt)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Move To", params=params)

    def move_to_point(self, point: str) -> EventTarget:
        """Command the unit to move directly to an arbitrary point."""
        params = [ParamInfo(name="point", type="string", value=point)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Move To Point", params=params)

    def park_now(self) -> EventTarget:
        """Command the unit to park where it stands."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Park Now")

    def randomize_alt_spawn(self) -> EventTarget:
        """Set a new random alternate spawn for this unit. Useful for respawning units in random places.  If the unit is in a group with synced alternates, the other units will have the same new alternate."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Randomize Alt Spawn")

    def remove_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Non-Targets", params=params)

    def remove_priority_targets(self, targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Priority Targets", params=params)

    def set_engage_enemies(self, engage: bool) -> EventTarget:
        """Set whether the unit should engage enemies."""
        params = [ParamInfo(name="engage", type="bool", value=engage)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Engage Enemies", params=params)

    def set_i_r_strobe_enabled(self, e: bool) -> EventTarget:
        """Toggle an infrared strobe signal that can only be seen in nightvision."""
        params = [ParamInfo(name="e", type="bool", value=e)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set IR Strobe", params=params)

    def set_invincible(self, i: bool) -> EventTarget:
        """Sets whether the unit can take damage."""
        params = [ParamInfo(name="i", type="bool", value=i)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Invincible", params=params)

    def set_movement_speed(self, s: Literal["Slow_10", "Medium_20", "Fast_30"]) -> EventTarget:
        """Set the movement speed of this ground vehicle."""
        params = [ParamInfo(name="s", type="string", value=s)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Movement Speed", params=params)

    def set_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will not attack. (Overwrites existing list)"""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Non-Targets", params=params)

    def set_path(self, path: str) -> EventTarget:
        """Command the unit to move along a path (if able)."""
        params = [ParamInfo(name="path", type="string", value=path)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Path", params=params)

    def set_priority_targets(self, targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will prioritize when finding a target. (Overwrites existing list)"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Priority Targets", params=params)

    def spawn_unit(self) -> EventTarget:
        """Spawn the unit if it hasn't already been spawned"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Spawn Unit")



class GroundUnitSpawnActions:
    """Actions callable on GroundUnitSpawn."""
    def __init__(self, target_id: Any):
        self.target_id = target_id
        self.target_type = "GroundUnitSpawn" # TODO: This may need adjustment depending on VTS format

    def add_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Non-Targets", params=params)

    def add_priority_targets(self, targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Priority Targets", params=params)

    def board_a_i_bay(self) -> EventTarget:
        """Command the unit to board an AI vehicle's passenger bay."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Board Vehicle")

    def clear_non_targets(self) -> EventTarget:
        """Clear the list of units that this unit will not attack."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Non-Targets")

    def clear_priority_targets(self) -> EventTarget:
        """Clear the list of units that this unit will prioritize when finding a target"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Priority Targets")

    def destroy_self(self) -> EventTarget:
        """This event destroys the unit immediately."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Destroy")

    def dismount_a_i_bay(self, wp: str) -> EventTarget:
        """Command the unit to dismount the vehicle it's riding when available. It will move towards Rally Point once dismounted."""
        params = [ParamInfo(name="wp", type="string", value=wp)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Dismount Vehicle", params=params)

    def force_alt_spawn(self) -> EventTarget:
        """Force a specific alternate spawn, overriding the random roll. This must be called BEFORE the unit spawns. If the unit is in a group with synced alternates, the other units will be forced as well."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Force Alt Spawn")

    def move_to(self, wpt: str) -> EventTarget:
        """Command the unit to move directly to a waypoint."""
        params = [ParamInfo(name="wpt", type="string", value=wpt)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Move To", params=params)

    def move_to_point(self, point: str) -> EventTarget:
        """Command the unit to move directly to an arbitrary point."""
        params = [ParamInfo(name="point", type="string", value=point)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Move To Point", params=params)

    def park_now(self) -> EventTarget:
        """Command the unit to park where it stands."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Park Now")

    def randomize_alt_spawn(self) -> EventTarget:
        """Set a new random alternate spawn for this unit. Useful for respawning units in random places.  If the unit is in a group with synced alternates, the other units will have the same new alternate."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Randomize Alt Spawn")

    def remove_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Non-Targets", params=params)

    def remove_priority_targets(self, targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Priority Targets", params=params)

    def set_engage_enemies(self, engage: bool) -> EventTarget:
        """Set whether the unit should engage enemies."""
        params = [ParamInfo(name="engage", type="bool", value=engage)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Engage Enemies", params=params)

    def set_i_r_strobe_enabled(self, e: bool) -> EventTarget:
        """Toggle an infrared strobe signal that can only be seen in nightvision."""
        params = [ParamInfo(name="e", type="bool", value=e)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set IR Strobe", params=params)

    def set_invincible(self, i: bool) -> EventTarget:
        """Sets whether the unit can take damage."""
        params = [ParamInfo(name="i", type="bool", value=i)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Invincible", params=params)

    def set_movement_speed(self, s: Literal["Slow_10", "Medium_20", "Fast_30"]) -> EventTarget:
        """Set the movement speed of this ground vehicle."""
        params = [ParamInfo(name="s", type="string", value=s)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Movement Speed", params=params)

    def set_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will not attack. (Overwrites existing list)"""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Non-Targets", params=params)

    def set_path(self, path: str) -> EventTarget:
        """Command the unit to move along a path (if able)."""
        params = [ParamInfo(name="path", type="string", value=path)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Path", params=params)

    def set_priority_targets(self, targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will prioritize when finding a target. (Overwrites existing list)"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Priority Targets", params=params)

    def spawn_unit(self) -> EventTarget:
        """Spawn the unit if it hasn't already been spawned"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Spawn Unit")



class IFVSpawnActions:
    """Actions callable on IFVSpawn."""
    def __init__(self, target_id: Any):
        self.target_id = target_id
        self.target_type = "IFVSpawn" # TODO: This may need adjustment depending on VTS format

    def add_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Non-Targets", params=params)

    def add_priority_targets(self, targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Priority Targets", params=params)

    def board_a_i_bay(self) -> EventTarget:
        """Command the unit to board an AI vehicle's passenger bay."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Board Vehicle")

    def clear_non_targets(self) -> EventTarget:
        """Clear the list of units that this unit will not attack."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Non-Targets")

    def clear_priority_targets(self) -> EventTarget:
        """Clear the list of units that this unit will prioritize when finding a target"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Priority Targets")

    def destroy_self(self) -> EventTarget:
        """This event destroys the unit immediately."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Destroy")

    def dismount_a_i_bay(self, wp: str) -> EventTarget:
        """Command the unit to dismount the vehicle it's riding when available. It will move towards Rally Point once dismounted."""
        params = [ParamInfo(name="wp", type="string", value=wp)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Dismount Vehicle", params=params)

    def force_alt_spawn(self) -> EventTarget:
        """Force a specific alternate spawn, overriding the random roll. This must be called BEFORE the unit spawns. If the unit is in a group with synced alternates, the other units will be forced as well."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Force Alt Spawn")

    def load_passengers(self) -> EventTarget:
        """Command the selected units to board this aircraft."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Load Passengers")

    def load_passenger_group(self) -> EventTarget:
        """Command the selected unit group to board this aircraft."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Load Unit Group")

    def move_to(self, wpt: str) -> EventTarget:
        """Command the unit to move directly to a waypoint."""
        params = [ParamInfo(name="wpt", type="string", value=wpt)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Move To", params=params)

    def move_to_point(self, point: str) -> EventTarget:
        """Command the unit to move directly to an arbitrary point."""
        params = [ParamInfo(name="point", type="string", value=point)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Move To Point", params=params)

    def park_now(self) -> EventTarget:
        """Command the unit to park where it stands."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Park Now")

    def randomize_alt_spawn(self) -> EventTarget:
        """Set a new random alternate spawn for this unit. Useful for respawning units in random places.  If the unit is in a group with synced alternates, the other units will have the same new alternate."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Randomize Alt Spawn")

    def remove_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Non-Targets", params=params)

    def remove_priority_targets(self, targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Priority Targets", params=params)

    def set_allow_reload(self, r: bool) -> EventTarget:
        """Set whether the unit can reload ammo/missiles when empty."""
        params = [ParamInfo(name="r", type="bool", value=r)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Allow Reload", params=params)

    def set_engage_enemies(self, engage: bool) -> EventTarget:
        """Set whether the unit should engage enemies."""
        params = [ParamInfo(name="engage", type="bool", value=engage)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Engage Enemies", params=params)

    def set_i_r_strobe_enabled(self, e: bool) -> EventTarget:
        """Toggle an infrared strobe signal that can only be seen in nightvision."""
        params = [ParamInfo(name="e", type="bool", value=e)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set IR Strobe", params=params)

    def set_invincible(self, i: bool) -> EventTarget:
        """Sets whether the unit can take damage."""
        params = [ParamInfo(name="i", type="bool", value=i)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Invincible", params=params)

    def set_movement_speed(self, s: Literal["Slow_10", "Medium_20", "Fast_30"]) -> EventTarget:
        """Set the movement speed of this ground vehicle."""
        params = [ParamInfo(name="s", type="string", value=s)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Movement Speed", params=params)

    def set_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will not attack. (Overwrites existing list)"""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Non-Targets", params=params)

    def set_path(self, path: str) -> EventTarget:
        """Command the unit to move along a path (if able)."""
        params = [ParamInfo(name="path", type="string", value=path)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Path", params=params)

    def set_priority_targets(self, targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will prioritize when finding a target. (Overwrites existing list)"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Priority Targets", params=params)

    def spawn_unit(self) -> EventTarget:
        """Spawn the unit if it hasn't already been spawned"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Spawn Unit")

    def unload_all_passengers(self, rally_wp: str) -> EventTarget:
        """Unload all passengers when available."""
        params = [ParamInfo(name="rallyWp", type="string", value=rally_wp)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Unload Passengers", params=params)



class MultiplayerSpawnActions:
    """Actions callable on MultiplayerSpawn."""
    def __init__(self, target_id: Any):
        self.target_id = target_id
        self.target_type = "MultiplayerSpawn" # TODO: This may need adjustment depending on VTS format

    def add_funds(self) -> EventTarget:
        """Add funds to this slot's equipment budget.  If budget mode is Team, funds apply to whole team."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Funds")

    def add_lives(self) -> EventTarget:
        """Use this to add/remove lives if the slot has limited respawns."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Lives")

    def destroy_vehicle(self) -> EventTarget:
        """Use this to destroy the player's vehicle."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Destroy Vehicle")

    def force_alt_spawn(self) -> EventTarget:
        """Force a specific alternate spawn, overriding the random roll. If the unit is in a group with synced alternates, the other units will be forced as well."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Force Alt Spawn")

    def move_spawn(self, point: str) -> EventTarget:
        """Move the spawn to a different location"""
        params = [ParamInfo(name="point", type="string", value=point)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Move Spawn", params=params)

    def remove_funds(self) -> EventTarget:
        """Remove funds from this slot's equipment budget.  If budget mode is Team, funds apply to whole team. Budget has a floor of $0."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Funds")

    def set_alt_spawn_available(self, available: bool, alt_spawn_idx: int) -> EventTarget:
        """Set whether the selectable alt spawn can be chosen by the player."""
        params = [ParamInfo(name="available", type="bool", value=available), ParamInfo(name="altSpawnIdx", type="int", value=alt_spawn_idx)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set AltSpawn Available", params=params)

    def set_fuel_unit(self) -> EventTarget:
        """Set this slot's Fuel waypoint unit (carrier or tanker)."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Fuel Unit")

    def set_fuel_w_p(self, wp: str, alt_spawn_idx: int) -> EventTarget:
        """Set this slot's Fuel waypoint"""
        params = [ParamInfo(name="wp", type="string", value=wp), ParamInfo(name="altSpawnIdx", type="int", value=alt_spawn_idx)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Fuel Waypoint", params=params)

    def set_invincible(self, i: bool) -> EventTarget:
        """Set whether the player from this slot is invincible."""
        params = [ParamInfo(name="i", type="bool", value=i)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Invincible", params=params)

    def set_lives(self) -> EventTarget:
        """Use this to set lives to a certain number the slot has limited respawns."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Lives")

    def set_r_t_b_to_spawn(self, alt_spawn_idx: int) -> EventTarget:
        """Set the RTB waypoint to the spawn point."""
        params = [ParamInfo(name="altSpawnIdx", type="int", value=alt_spawn_idx)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set RTB To Spawn", params=params)

    def set_r_t_b_unit(self) -> EventTarget:
        """Set this slot's RTB unit (carrier)"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set RTB Unit")

    def set_r_t_b_w_p(self, wp: str, alt_spawn_idx: int) -> EventTarget:
        """Set this slot's RTB waypoint"""
        params = [ParamInfo(name="wp", type="string", value=wp), ParamInfo(name="altSpawnIdx", type="int", value=alt_spawn_idx)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set RTB Waypoint", params=params)



class PlayerSpawnActions:
    """Actions callable on PlayerSpawn."""
    def __init__(self, target_id: Any):
        self.target_id = target_id
        self.target_type = "PlayerSpawn" # TODO: This may need adjustment depending on VTS format

    def destroy_vehicle(self) -> EventTarget:
        """Destroy the player's aircraft without killing the pilot."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Destroy Vehicle")

    def kill_pilot(self) -> EventTarget:
        """Kill the pilot instantaneously (as if killed by g-forces or impact)"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Kill Pilot")

    def repair_vehicle(self) -> EventTarget:
        """Fully repair the vehicle."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Repair Vehicle")

    def reset_vehicle(self, wp: str) -> EventTarget:
        """Recover the vehicle and return it to this state."""
        params = [ParamInfo(name="wp", type="string", value=wp)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Reset Vehicle", params=params)

    def set_waypoint(self, wpt: str) -> EventTarget:
        """Set the player's current waypoint."""
        params = [ParamInfo(name="wpt", type="string", value=wpt)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Waypoint", params=params)



class RearmingUnitSpawnActions:
    """Actions callable on RearmingUnitSpawn."""
    def __init__(self, target_id: Any):
        self.target_id = target_id
        self.target_type = "RearmingUnitSpawn" # TODO: This may need adjustment depending on VTS format

    def set_enabled(self, e: bool) -> EventTarget:
        """Enable or disable the rearming point."""
        params = [ParamInfo(name="e", type="bool", value=e)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Enabled", params=params)

    def spawn_unit(self) -> EventTarget:
        """Spawn the unit if it hasn't already been spawned"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Spawn Unit")



class RocketArtilleryUnitSpawnActions:
    """Actions callable on RocketArtilleryUnitSpawn."""
    def __init__(self, target_id: Any):
        self.target_id = target_id
        self.target_type = "RocketArtilleryUnitSpawn" # TODO: This may need adjustment depending on VTS format

    def add_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Non-Targets", params=params)

    def add_priority_targets(self, targets: List[str]) -> EventTarget:
        """Add units to the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Add Priority Targets", params=params)

    def board_a_i_bay(self) -> EventTarget:
        """Command the unit to board an AI vehicle's passenger bay."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Board Vehicle")

    def clear_fire_orders(self) -> EventTarget:
        """Clears any existing fire orders for the artillery unit."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Fire Orders")

    def clear_non_targets(self) -> EventTarget:
        """Clear the list of units that this unit will not attack."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Non-Targets")

    def clear_priority_targets(self) -> EventTarget:
        """Clear the list of units that this unit will prioritize when finding a target"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Clear Priority Targets")

    def destroy_self(self) -> EventTarget:
        """This event destroys the unit immediately."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Destroy")

    def dismount_a_i_bay(self, wp: str) -> EventTarget:
        """Command the unit to dismount the vehicle it's riding when available. It will move towards Rally Point once dismounted."""
        params = [ParamInfo(name="wp", type="string", value=wp)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Dismount Vehicle", params=params)

    def fire_on_unit(self) -> EventTarget:
        """Commands the artillery unit to fire on a specific unit if it's in range."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Fire On Unit")

    def fire_on_waypoint(self, wpt: str) -> EventTarget:
        """Commands the artillery unit to fire a single salvo on a waypoint position if it's in range."""
        params = [ParamInfo(name="wpt", type="string", value=wpt)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Fire On Waypoint", params=params)

    def fire_multi_on_waypoint(self, wpt: str) -> EventTarget:
        """Commands the artillery unit to fire a number of salvos on a waypoint position if it's in range."""
        params = [ParamInfo(name="wpt", type="string", value=wpt)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Fire Salvos On Waypoint", params=params)

    def fire_multi_on_waypoint_radius(self, wpt: str) -> EventTarget:
        """Commands the artillery unit to fire a number of salvos spread out over an area around a position if it's in range."""
        params = [ParamInfo(name="wpt", type="string", value=wpt)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Fire Salvos On Waypoint Radius", params=params)

    def force_alt_spawn(self) -> EventTarget:
        """Force a specific alternate spawn, overriding the random roll. This must be called BEFORE the unit spawns. If the unit is in a group with synced alternates, the other units will be forced as well."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Force Alt Spawn")

    def move_to(self, wpt: str) -> EventTarget:
        """Command the unit to move directly to a waypoint."""
        params = [ParamInfo(name="wpt", type="string", value=wpt)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Move To", params=params)

    def move_to_point(self, point: str) -> EventTarget:
        """Command the unit to move directly to an arbitrary point."""
        params = [ParamInfo(name="point", type="string", value=point)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Move To Point", params=params)

    def park_now(self) -> EventTarget:
        """Command the unit to park where it stands."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Park Now")

    def randomize_alt_spawn(self) -> EventTarget:
        """Set a new random alternate spawn for this unit. Useful for respawning units in random places.  If the unit is in a group with synced alternates, the other units will have the same new alternate."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Randomize Alt Spawn")

    def remove_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will not attack."""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Non-Targets", params=params)

    def remove_priority_targets(self, targets: List[str]) -> EventTarget:
        """Remove units from the list of units that this unit will prioritize when finding a target"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Remove Priority Targets", params=params)

    def set_allow_reload(self, allow: bool) -> EventTarget:
        """Set whether this unit is allowed to reload rockets after emptying."""
        params = [ParamInfo(name="allow", type="bool", value=allow)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Allow Reload", params=params)

    def set_engage_enemies(self, engage: bool) -> EventTarget:
        """Set whether the unit should engage enemies."""
        params = [ParamInfo(name="engage", type="bool", value=engage)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Engage Enemies", params=params)

    def set_i_r_strobe_enabled(self, e: bool) -> EventTarget:
        """Toggle an infrared strobe signal that can only be seen in nightvision."""
        params = [ParamInfo(name="e", type="bool", value=e)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set IR Strobe", params=params)

    def set_invincible(self, i: bool) -> EventTarget:
        """Sets whether the unit can take damage."""
        params = [ParamInfo(name="i", type="bool", value=i)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Invincible", params=params)

    def set_movement_speed(self, s: Literal["Slow_10", "Medium_20", "Fast_30"]) -> EventTarget:
        """Set the movement speed of this ground vehicle."""
        params = [ParamInfo(name="s", type="string", value=s)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Movement Speed", params=params)

    def set_non_targets(self, non_targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will not attack. (Overwrites existing list)"""
        params = [ParamInfo(name="nonTargets", type="string", value=non_targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Non-Targets", params=params)

    def set_path(self, path: str) -> EventTarget:
        """Command the unit to move along a path (if able)."""
        params = [ParamInfo(name="path", type="string", value=path)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Path", params=params)

    def set_priority_targets(self, targets: List[str]) -> EventTarget:
        """Set the list of units that this unit will prioritize when finding a target. (Overwrites existing list)"""
        params = [ParamInfo(name="targets", type="string", value=targets)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Priority Targets", params=params)

    def set_reload_time(self, time: float) -> EventTarget:
        """Change the time it takes for this unit to reload, if allowed."""
        params = [ParamInfo(name="time", type="float", value=time)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Reload Time", params=params)

    def set_ripple_rate(self) -> EventTarget:
        """Set the rate of fire when launching salvos at targets."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Ripple Rate")

    def set_shots_per_salvo(self) -> EventTarget:
        """Set the number of rockets the unit will fire on each salvo when automatically engaging visible targets."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Set Shots Per Salvo")

    def spawn_unit(self) -> EventTarget:
        """Spawn the unit if it hasn't already been spawned"""
        return EventTarget(target_type=self.target_type, target_id=self.target_id, event_name="Spawn Unit")


class GlobalValueActions:
    """
    Helper class to generate EventTarget objects for manipulating GlobalValues.

    Note: The 'target_id' should be the *name* (string) of the GlobalValue.
    """
    def __init__(self, target_id: str):
        if not isinstance(target_id, str):
            raise TypeError("target_id for GlobalValueActions must be the string name of the GlobalValue.")
        self.target_id = target_id
        self.target_type = "GlobalValue" # VTS targetType for global values

    def set_value(self, value: Union[int, float]) -> EventTarget:
        """Sets the global value to a specific amount."""
        params = [ParamInfo(name="value", type="System.Single", value=value)] # Assuming float/int uses System.Single
        return EventTarget(target_type=self.target_type, target_id=self.target_id,
                           event_name="Set Value", method_name="SetValue", params=params)

    def increment_value(self) -> EventTarget:
        """Adds 1 to the global value (increment)."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id,
                           event_name="Increment Value", method_name="IncrementValue") # No params needed

    def decrement_value(self) -> EventTarget:
        """Subtracts 1 from the global value (decrement)."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id,
                           event_name="Decrement Value", method_name="DecrementValue") # No params needed

    def reset_value(self) -> EventTarget:
        """Resets the global value to its initial value."""
        return EventTarget(target_type=self.target_type, target_id=self.target_id,
                           event_name="Reset Value", method_name="ResetValue") # No params needed

    def multiply_value(self, value: Union[int, float]) -> EventTarget:
        """Multiplies the global value by a specific amount."""
        params = [ParamInfo(name="value", type="System.Single", value=value)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id,
                           event_name="Multiply Value", method_name="MultiplyValue", params=params)

    def copy_value(self, source_gv_name: str) -> EventTarget:
        """Copies the value from another global value into this one."""
        params = [ParamInfo(name="sourceValue", type="GlobalValue", value=source_gv_name)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id,
                           event_name="Copy Value", method_name="CopyValue", params=params)

    def add_values(self, source_gv_name: str) -> EventTarget:
        """Adds the value of another global value to this one."""
        params = [ParamInfo(name="sourceValue", type="GlobalValue", value=source_gv_name)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id,
                           event_name="Add Values", method_name="AddValues", params=params)

    def subtract_values(self, source_gv_name: str) -> EventTarget:
        """Subtracts the value of another global value from this one."""
        params = [ParamInfo(name="sourceValue", type="GlobalValue", value=source_gv_name)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id,
                           event_name="Subtract Values", method_name="SubtractValues", params=params)

    def multiply_values(self, source_gv_name: str) -> EventTarget:
        """Multiplies this global value by the value of another global value."""
        params = [ParamInfo(name="sourceValue", type="GlobalValue", value=source_gv_name)]
        return EventTarget(target_type=self.target_type, target_id=self.target_id,
                           event_name="Multiply Values", method_name="MultiplyValues", params=params)