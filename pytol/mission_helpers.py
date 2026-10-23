"""
Convenience methods of Mission: event wiring with automatic ids.

Every method builds the same objects you would build by hand (Trigger, TimedEventGroup, EventSequence, RandomEvent,
ConditionalAction) and adds them to the mission. Ids are taken from what the mission already holds, so these can be
mixed freely with objects you add yourself.
"""
from typing import Iterable, List, Optional, Sequence, Tuple, Union

from .classes.actions import EventSequenceActions, SystemActions, TimedEventGroupActions
from .classes.mission_objects import (
    ConditionalAction, ConditionalBlock, EventSequence, EventTarget, RandomEvent, RandomEventAction, SequenceEvent,
    TimedEventGroup, TimedEventInfo, Trigger,
)

Actions = Sequence[EventTarget]
# A step of a sequence: (condition or None, seconds, actions). See MissionHelpers.sequence.
Step = Tuple[object, float, Actions]


def _as_condition(cond):
    """A ConditionalTree / Conditional, or an object with .tree() (pytol.logic.Cond), as something add_conditional takes."""
    return cond.tree() if hasattr(cond, 'tree') else cond


class MissionHelpers:
    """Mixed into Mission."""

    def _next_id(self, used: Iterable[int]) -> int:
        return max(used, default=-1) + 1

    def next_objective_id(self) -> int:
        """The next free objective id (one more than the highest in the mission)."""
        return self._next_id(o.objective_id for o in self.objectives)

    def on_enter(self, name: str, waypoint, radius: float, actions: Actions, mode: str = "Player", unit=None,
                 spherical: bool = False, enabled: bool = True) -> int:
        """Fires `actions` once when the player (or `unit`, with mode="Unit") enters `radius` of `waypoint`."""
        tid = self._next_id(self._triggers_map)
        self.add_trigger_event(Trigger(
            id=tid, name=name, trigger_type="Proximity", waypoint=waypoint, radius=radius, spherical_radius=spherical,
            trigger_mode=mode, enabled=enabled, unit=str(unit) if unit is not None else None, proxy_mode="OnEnter",
            event_targets=list(actions)))
        return tid

    def on_condition(self, name: str, cond, actions: Actions) -> int:
        """Fires `actions` once, the first time `cond` is true. `cond` is a ConditionalTree, a Conditional, an
        already registered conditional id, or a pytol.logic.Cond."""
        cond = _as_condition(cond)
        cid = cond if isinstance(cond, int) else self.add_conditional(cond)
        tid = self._next_id(self._triggers_map)
        self.add_trigger_event(Trigger(id=tid, name=name, trigger_type="Conditional", conditional=cid,
                                       event_targets=list(actions)))
        return tid

    def timer(self, name: str, events: Sequence[Tuple[float, Actions]], start_now: bool = True) -> EventTarget:
        """Timed events [(seconds, actions)]. Returns the action that begins the group (useful when start_now is False)."""
        gid = self._next_id(g.group_id for g in self.timed_event_groups) or 1  # id 0 is left free
        self.add_timed_event_group(TimedEventGroup(
            group_name=name, group_id=gid, begin_immediately=start_now,
            events=[TimedEventInfo(event_name=f"{name} {i}", time=t, event_targets=list(a))
                    for i, (t, a) in enumerate(events)]))
        return TimedEventGroupActions(gid).begin()

    def sequence(self, name: str, steps: Sequence[Step], start_now: bool = False, loop: bool = False
                 ) -> Tuple[EventTarget, EventTarget]:
        """
        Event sequence of [(condition or None, seconds, actions)]. Returns (begin, stop) actions.

        A step with a condition and a delay fires `seconds` AFTER the condition becomes true. (The game itself waits
        the delay first, then the condition; this method writes two nodes so the delay follows the condition.)
        loop=True starts over after the last step.
        """
        sid = self._next_id(s.id for s in self.event_sequences)
        nodes: List[tuple] = []
        for cond, delay, acts in steps:
            if cond is not None and delay > 0:
                nodes += [(cond, 0.0, []), (None, delay, acts)]
            else:
                nodes.append((cond, delay, acts))
        self.add_event_sequence(EventSequence(
            id=sid, sequence_name=name, start_immediately=start_now, while_loop=loop,
            events=[SequenceEvent(node_name=f"{name} {i}", delay=delay, actions=list(a),
                                  conditional=self._register_condition(cond))
                    for i, (cond, delay, a) in enumerate(nodes)]))
        return EventSequenceActions(sid).begin_event(), EventSequenceActions(sid).stop()

    def random_choice(self, name: str, options: Sequence[Tuple[int, Actions]]) -> EventTarget:
        """One of [(weight, actions)] chosen in-game each time it fires. Returns the action that fires it."""
        rid = self._next_id(r.id for r in self.random_events)
        self.add_random_event(RandomEvent(id=rid, name=name, action_options=[
            RandomEventAction(id=i, action_name=f"{name} {i}", fixed_weight=w, actions=list(a))
            for i, (w, a) in enumerate(options)]))
        return SystemActions().fire_random_event(rid)

    def when(self, cond, then: Actions, elif_: Sequence[Tuple[object, Actions]] = (), else_: Actions = (),
             name: str = "If") -> EventTarget:
        """IF cond THEN actions ELSE IF [(cond, actions)] ELSE actions. Returns the action that fires the statement."""
        cid = self._register_condition(cond)
        ca = ConditionalAction(
            id=self._next_id(c.id for c in self.conditional_actions), name=name, conditional_id=cid, actions=list(then),
            else_if=[ConditionalBlock(conditional_id=self._register_condition(c), actions=list(a), name=f"{name} elif {i}")
                     for i, (c, a) in enumerate(elif_)],
            else_actions=list(else_))
        self.add_conditional_action(ca)
        return SystemActions().fire_conditional_action(ca.id)

    def _register_condition(self, cond) -> Optional[int]:
        if cond is None:
            return None
        cond = _as_condition(cond)
        return cond if isinstance(cond, int) else self.add_conditional(cond)
