"""
Mission logic: conditions you can combine (`&`, `|`, `~`), global-value variables, if/elif/else branches and a
phase machine, all compiled to what the game's editor writes (ConditionalTree, GlobalValue, ConditionalAction).

    L = Logic(mission)
    alarm = L.counter('alarm')
    low = Unit(player_id).radar_alt_below(150) & ~Unit(player_id).detected_by('Enemy')
    L.when(alarm >= 2, then=[...], elif_=[(low, [...])], else_=[...])   # returns the action that fires it

Conditions only offer methods that exist on the unit's game class. Player conditions come in two flavors: those both
PlayerSpawn and MultiplayerSpawn have (altitude, airspeed, fuel, near a waypoint, landed, engines) and the ones only
PlayerSpawn has (weapons, pitch/roll, tanker, sensors, detection). `Players` offers only the common ones, so it is
safe for co-op.
"""
from .classes.actions import GlobalValueActions, SystemActions
from .classes.conditionals import ConditionalTree, create_conditional
from .classes.mission_objects import GlobalValue

KT = 0.514444  # m/s per knot
# Component types whose is_not field flips them; And/Or/GlobalValue are negated by De Morgan / complement.
_NOTABLE = {'SCCUnit', 'SCCUnitList', 'SCCUnitGroup', 'SCCStaticObject', 'SCCVehicleControl'}


class Cond:
    """A boolean expression over mission state."""

    def __init__(self, op, kind=None, fields=None, parts=()):
        self.op, self.kind, self.fields, self.parts = op, kind, fields or {}, tuple(parts)

    @staticmethod
    def leaf(kind, **fields):
        return Cond('leaf', kind, fields)

    def __and__(self, other):
        return Cond._join('and', self, other)

    def __or__(self, other):
        return Cond._join('or', self, other)

    @staticmethod
    def _join(op, a, b):
        parts = [p for x in (a, b) for p in (x.parts if x.op == op else (x,))]  # flatten a & b & c
        return Cond(op, parts=parts)

    def __invert__(self):
        if self.op == 'and':
            return Cond('or', parts=[~p for p in self.parts])
        if self.op == 'or':
            return Cond('and', parts=[~p for p in self.parts])
        if self.kind in _NOTABLE:
            return Cond.leaf(self.kind, **{**self.fields, 'is_not': not self.fields.get('is_not', False)})
        if self.kind == 'SCCGlobalValue':  # integer complement: not(x == c) is x<c or x>c
            f, c = self.fields, self.fields['c_value']
            cmp = f['comparison']
            if cmp == 'Greater_Than':
                return Cond.leaf(self.kind, **{**f, 'comparison': 'Less_Than', 'c_value': c + 1})
            if cmp == 'Less_Than':
                return Cond.leaf(self.kind, **{**f, 'comparison': 'Greater_Than', 'c_value': c - 1})
            return Cond.leaf(self.kind, **{**f, 'comparison': 'Less_Than'}) | Cond.leaf(self.kind, **{**f, 'comparison': 'Greater_Than'})
        raise ValueError(f"{self.kind} cannot be negated")

    def tree(self) -> ConditionalTree:
        """Compile to a ConditionalTree (component ids allocated depth-first, root last)."""
        tree, ids = ConditionalTree(), iter(range(10_000))

        def emit(c):
            if c.op == 'leaf':
                cid = next(ids)
                tree.add_comp(cid, create_conditional(c.kind, **c.fields))
                return cid
            factors = [emit(p) for p in c.parts]
            cid = next(ids)
            tree.add_comp(cid, create_conditional('SCCAnd' if c.op == 'and' else 'SCCOr', factors=factors))
            return cid

        tree.set_root(emit(self))
        return tree

    def leaves(self):
        return [self] if self.op == 'leaf' else [x for p in self.parts for x in p.leaves()]


def _cmp(op, c_value):
    """Counter-style comparison with <, <=, >, >=, == on an integer count."""
    table = {'<': ('Less_Than', 0), '<=': ('Less_Than', 1), '>': ('Greater_Than', 0), '>=': ('Greater_Than', -1),
             '==': ('Equals', 0)}
    comparison, shift = table[op]
    return comparison, c_value + shift


# --- Variables -------------------------------------------------------------------------------------
class Counter:
    """A global value. Compare it with <, <=, >, >=, == to get a condition; use inc/dec/set for actions."""

    def __init__(self, name):
        self.name = name

    def _compare(self, op, value):
        comparison, c = _cmp(op, int(value))
        return Cond.leaf('SCCGlobalValue', gv=self.name, comparison=comparison, c_value=c)

    def __lt__(self, v): return self._compare('<', v)
    def __le__(self, v): return self._compare('<=', v)
    def __gt__(self, v): return self._compare('>', v)
    def __ge__(self, v): return self._compare('>=', v)
    def __eq__(self, v): return self._compare('==', v)
    __hash__ = object.__hash__

    def set(self, v): return GlobalValueActions(self.name).set_value(float(v))
    def inc(self, n=1): return GlobalValueActions(self.name).increment_value(float(n))
    def dec(self, n=1): return GlobalValueActions(self.name).decrement_value(float(n))
    def reset(self): return GlobalValueActions(self.name).reset_value()


class Flag(Counter):
    """A 0/1 counter."""

    def raise_(self): return self.set(1)
    def lower(self): return self.set(0)

    @property
    def is_set(self): return self == 1


# --- Conditions on units ---------------------------------------------------------------------------
def _unit(uid, method, *params, is_not=False):
    return Cond.leaf('SCCUnit', unit=str(uid), method_name=method, method_parameters=[str(p) for p in params],
                     is_not=is_not)


def _list(ids, method, *params):
    return Cond.leaf('SCCUnitList', unit_list=[str(i) for i in ids], method_name=method,
                     method_parameters=[str(p) for p in params], is_not=False)


class Unit:
    """Conditions on one unit (mostly the player: PlayerSpawn / MultiplayerSpawn methods)."""

    def __init__(self, uid):
        self.id = uid

    def radar_alt_below(self, m): return _unit(self.id, 'SCC_AltitudeRadar', 'Less_Than', m)
    def radar_alt_above(self, m): return _unit(self.id, 'SCC_AltitudeRadar', 'Greater_Than', m)
    def alt_below(self, m): return _unit(self.id, 'SCC_Altitude', 'Less_Than', m)
    def alt_above(self, m): return _unit(self.id, 'SCC_Altitude', 'Greater_Than', m)
    def faster(self, kts): return _unit(self.id, 'SCC_Airspeed', 'Greater_Than', round(kts * KT, 1))  # the game takes m/s
    def slower(self, kts): return _unit(self.id, 'SCC_Airspeed', 'Less_Than', round(kts * KT, 1))
    def fuel_below(self, pct): return _unit(self.id, 'SCC_FuelLevel', 'Less_Than', pct)
    def pitch_above(self, deg): return _unit(self.id, 'SCC_PitchComparison', 'Greater_Than', deg)
    def roll_above(self, deg): return _unit(self.id, 'SCC_RollComparison', 'Greater_Than', deg)
    def using_weapon(self, short_name): return _unit(self.id, 'SCC_UsingWeaponStr', short_name)
    def weapon_count(self, short_name, comparison, n): return _unit(self.id, 'SCC_WeaponCount', short_name, comparison, n)
    def locking(self, target_id, method='Radar'): return _unit(self.id, 'SCC_IsLockingTarget', target_id, method)
    def connected_to_tanker(self, tanker_id): return _unit(self.id, 'SCC_ConnectedToTanker', tanker_id)
    def sensor_enabled(self, sensor): return _unit(self.id, 'SCC_HasSensorEnabled', sensor)
    def detected_by(self, team): return _unit(self.id, 'SCC_DetectedBy', team)
    def near(self, waypoint, radius): return _unit(self.id, 'SCC_NearWaypoint', waypoint.id, radius)
    def landed(self): return _unit(self.id, 'SCC_Landed')
    def landed_at(self, waypoint, radius): return _unit(self.id, 'SCC_LandedAtWaypoint', waypoint.id, radius)
    def damaged(self): return _unit(self.id, 'SCC_GetsDamaged')
    def killed(self): return _unit(self.id, 'SCC_GetsKilled')
    def killed_by(self, killer_id): return _unit(self.id, 'SCC_GetsKilledBy', killer_id)
    def engines_on(self): return _unit(self.id, 'SCC_EnginesOn')


class Units:
    """Conditions on a list of units. `Units(ids).alive() < 3` counts the living."""

    def __init__(self, ids):
        self.ids = list(ids)

    class _Count:
        def __init__(self, units, method):
            self.units, self.method = units, method

        def _compare(self, op, value):
            comparison, c = _cmp(op, int(value))
            return _list(self.units.ids, self.method, comparison, c)

        def __lt__(self, v): return self._compare('<', v)
        def __le__(self, v): return self._compare('<=', v)
        def __gt__(self, v): return self._compare('>', v)
        def __ge__(self, v): return self._compare('>=', v)
        def __eq__(self, v): return self._compare('==', v)
        __hash__ = object.__hash__

    def alive(self): return Units._Count(self, 'SCC_NumAlive')
    def all_dead(self): return self.alive() < 1
    def any_damaged(self): return _list(self.ids, 'SCC_AnyGetsDamaged')
    def any_killed(self): return _list(self.ids, 'SCC_AnyGetsKilled')
    def any_killed_by(self, killer_ids): return _list(self.ids, 'SCC_AnyGetsKilledBy', ';'.join(str(k) for k in killer_ids))
    def any_detected(self, by_team): return _list(self.ids, 'SCC_AnyUnitDetected', by_team)
    def any_near(self, waypoint, radius): return _list(self.ids, 'SCC_AnyNearWaypoint', waypoint.id, radius)
    def any_landed_near(self, waypoint, radius): return _list(self.ids, 'SCC_AnyLandedNearWaypoint', waypoint.id, radius)
    def count_near(self, waypoint, radius, comparison, n): return _list(self.ids, 'SCC_NumNearWP', waypoint.id, radius, comparison, n)


class Players:
    """The player slot(s) as one actor: `any` of the slots near / above, `all` of them below. Only conditions that both
    PlayerSpawn and MultiplayerSpawn have are offered (checked against the game's classes); the rest raise in co-op."""

    def __init__(self, slots, mp=False):
        self.slots, self.mp = list(slots if isinstance(slots, (list, tuple)) else [slots]), mp

    def _any(self, make):
        out = make(Unit(self.slots[0]))
        for s in self.slots[1:]:
            out = out | make(Unit(s))
        return out

    def _all(self, make):
        out = make(Unit(self.slots[0]))
        for s in self.slots[1:]:
            out = out & make(Unit(s))
        return out

    def near(self, waypoint, radius): return Units(self.slots).any_near(waypoint, radius)
    def radar_alt_above(self, m): return self._any(lambda u: u.radar_alt_above(m))
    def radar_alt_below(self, m): return self._all(lambda u: u.radar_alt_below(m))
    def detected_by(self, team): return Units(self.slots).any_detected(team)  # SCC_DetectedBy exists only on PlayerSpawn
    def all_dead(self): return Units(self.slots).all_dead()
    def faster(self, kts): return self._any(lambda u: u.faster(kts))
    def slower(self, kts): return self._all(lambda u: u.slower(kts))
    def using_weapon(self, name):
        if self.mp:
            raise ValueError("SCC_UsingWeaponStr exists only on PlayerSpawn, not on co-op slots")
        return self._any(lambda u: u.using_weapon(name))


def chance(percent): return Cond.leaf('SCCChance', chance=int(percent))


# --- Logic: variables, branches, phases ------------------------------------------------------------
class Logic:
    """Variables, branches and phases on a Mission."""

    def __init__(self, mission):
        self.m = mission
        self.gvs = {}

    def counter(self, name, initial=0):
        return self._variable(Counter, name, initial)

    def flag(self, name, initial=0):
        return self._variable(Flag, name, initial)

    def _variable(self, cls, name, initial):
        if name in self.gvs:
            return self.gvs[name]
        self.m.add_global_value(GlobalValue(name=name, initial_value=initial))
        self.gvs[name] = cls(name)
        return self.gvs[name]

    def cond_id(self, cond):
        return self.m.add_conditional(cond.tree() if isinstance(cond, Cond) else cond)

    def when(self, cond, then, elif_=(), else_=(), name="If"):
        """IF cond THEN actions ELIF [(cond, actions)] ELSE actions; returns the action that fires the statement."""
        return self.m.when(cond, then, elif_, else_, name)

    def trigger_when(self, name, cond, actions):
        """Fires `actions` once, the first time cond is true."""
        return self.m.on_condition(name, cond, actions)

    def phases(self, name="phase"):
        return Phases(self, name)


class Phases:
    """A phase machine on one global value: phase k is active while it equals k.

    Transitions out of one phase share a single if/elif chain, so when several conditions hold at once the first
    declared wins. A phase is entered at most once (the trigger is one-shot). Phase 0 is active from the start.
    """

    def __init__(self, logic, name):
        self.logic, self.var = logic, logic.counter(name)
        self.names, self.enter, self.edges = [], {}, {}

    def add(self, name, on_enter=(), checkpoint=False):
        """Declare a phase (the first one is the start). `checkpoint` saves the game on entering it."""
        self.names.append(name)
        k = len(self.names) - 1
        self.enter[k] = list(on_enter) + ([SystemActions().force_quicksave()] if checkpoint and k else [])
        return k

    def goto(self, frm, cond, to, actions=()):
        """Move from phase `frm` to `to` when cond is true; `actions` run on the way."""
        self.edges.setdefault(frm, []).append((cond, to, list(actions)))

    def active(self, k):
        return self.var == k

    def check(self):
        """Every phase but the last has an exit and every phase can be reached from the first."""
        last = len(self.names) - 1
        dead = [self.names[k] for k in range(last) if k not in self.edges]
        reach, todo = {0}, [0]
        while todo:
            for _, to, _ in self.edges.get(todo.pop(), []):
                if to not in reach:
                    reach.add(to)
                    todo.append(to)
        lost = [n for k, n in enumerate(self.names) if k not in reach]
        if dead or lost:
            raise ValueError(f"phase machine '{self.var.name}': dead ends {dead}, unreachable {lost}")

    def build(self):
        self.check()
        for frm, edges in self.edges.items():
            def step(to, actions):
                return [self.var.set(to)] + actions + self.enter[to]
            in_phase = self.var == frm
            any_edge = edges[0][0]
            for c, _, _ in edges[1:]:
                any_edge = any_edge | c
            if len(edges) == 1:
                c, to, acts = edges[0]
                self.logic.trigger_when(f"{self.names[frm]} -> {self.names[to]}", in_phase & c, step(to, acts))
            else:
                fire = self.logic.when(edges[0][0], step(edges[0][1], edges[0][2]),
                                       elif_=[(c, step(to, acts)) for c, to, acts in edges[1:]],
                                       name=f"{self.names[frm]} exits")
                self.logic.trigger_when(f"{self.names[frm]} exits", in_phase & any_edge, [fire])
