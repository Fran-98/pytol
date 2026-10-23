"""
Objective patterns that follow from how the game scores a mission. Each takes the Mission first.

- `conditional_objective`: completes when a condition holds, fails when another does.
- `counter_objective` / `tally`: "destroy 6 of 10" with the game's Global_Value objective (completes on equality, so the
  counter must step by one).
- `contingency`: a mission aim with a plan B. A required objective that fails ends the mission, so plan A and plan B are
  optional objectives and the required one is a conditional that completes when either succeeded.
- `capture_base`: flip a map base to our team and make it the new return and refuel point.
"""
from .classes.actions import BaseActions, ObjectiveActions, SystemActions
from .classes.objectives import create_objective
from .logic import Counter, Logic, Units


def _add(mission, obj, on_complete=None, on_fail=None):
    if on_complete:
        obj.complete_event_targets = list(on_complete)
    if on_fail:
        obj.fail_event_targets = list(on_fail)
    mission.add_objective(obj)
    return obj


def conditional_objective(mission, name, info, success, fail=None, prereqs=None, required=True, start_mode=None,
                          on_complete=None, on_fail=None, waypoint=None):
    """Objective completed when `success` (a pytol.logic.Cond or ConditionalTree) holds and failed when `fail` does."""
    reg = lambda c: mission.add_conditional(c.tree() if hasattr(c, 'tree') else c)
    obj = create_objective("Conditional", mission.next_objective_id(), name, info, required=required, prereqs=prereqs,
                           start_mode=start_mode, waypoint=waypoint, success_conditional=reg(success),
                           fail_conditional=reg(fail) if fail is not None else None)
    return _add(mission, obj, on_complete, on_fail)


def counter_objective(mission, name, info, counter: Counter, target: int, prereqs=None, required=True, on_complete=None,
                      start_mode=None):
    """Objective completed when `counter` reaches `target`: fire counter.inc() as each one is done."""
    goal = Logic(mission).counter(f"{counter.name} goal", initial=target)
    obj = create_objective("Global_Value", mission.next_objective_id(), name, info, required=required, prereqs=prereqs,
                           start_mode=start_mode, current_value=counter.name, target_value=goal.name)
    return _add(mission, obj, on_complete)


def tally(mission, counter: Counter, unit_groups):
    """One trigger per group of units that raises the counter when that group is wiped out. Returns the trigger ids."""
    return [mission.on_condition(f"{counter.name} {i + 1}", Units(g).all_dead(), [counter.inc()])
            for i, g in enumerate(unit_groups)]


def contingency(mission, name, info, primary, plan_b, on_switch=(), on_lost=(), prereqs=None):
    """A mission aim with a plan B. `primary` and `plan_b` are optional objectives (plan_b with start_mode 'Triggered').
    When the primary fails, `on_switch` runs and plan B begins; if plan B fails too, `on_lost` runs and the mission is
    lost. Returns (goal objective, flag raised when either plan succeeded)."""
    logic = Logic(mission)
    won = logic.flag(f"{name} done")
    primary.complete_event_targets = list(primary.complete_event_targets) + [won.raise_()]
    plan_b.complete_event_targets = list(plan_b.complete_event_targets) + [won.raise_()]
    primary.fail_event_targets = list(primary.fail_event_targets) + [
        ObjectiveActions(plan_b.objective_id).begin_objective(), *on_switch]
    goal = conditional_objective(mission, name, info, won.is_set, prereqs=prereqs)
    plan_b.fail_event_targets = list(plan_b.fail_event_targets) + [
        ObjectiveActions(goal.objective_id).fail_objective(), *on_lost]
    return goal, won


def capture_base(mission, base_id, cond, rearm_waypoint=None, actions=()):
    """When `cond` holds the base becomes ours and, with `rearm_waypoint`, the player's return and fuel point."""
    todo = [BaseActions(base_id).set_team("Allied")]
    if rearm_waypoint is not None:
        todo += [SystemActions().s_p__set_r_t_b(rearm_waypoint), SystemActions().s_p__set_fuel_w_p(rearm_waypoint)]
    return mission.on_condition("Base captured", cond, todo + list(actions))
