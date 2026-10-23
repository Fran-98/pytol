"""
Abstract simulator: walks a generated .vts the way a typical player would and estimates how the mission plays,
without the game. The player flies straight legs at the aircraft's typical speed through the objectives in
dependency order; triggers, timers and sequences fire when that path reaches them. The result is a timeline of
beats (radio, spawns, objectives, threat exposure), a duration and an intensity curve, so boring (long quiet
stretches) or unplayable (too long, too short) seeds can be rejected.

    python -m pytol.analysis.simulate mission.vts [--vehicle F/A-26B]
"""
import math
import re
import sys
from dataclasses import dataclass, field

from pytol.parsers.vts_validator import parse_game

from pytol.parsers.vts_analyzer import RADIO_LINE, _first, _ids, _kids, _walk

SPEED = {'F/A-26B': 230.0, 'F-45A': 240.0, 'EF-24G': 230.0, 'T-55': 190.0, 'AV-42C': 75.0, 'AH-94': 70.0}  # m/s typical
DWELL = {'Destroy': 150.0, 'Fly_To': 0.0, 'Land': 40.0, 'Conditional': 45.0, 'Global_Value': 120.0, 'Pick_Up': 120.0,
         'Drop_Off': 120.0, 'Join': 60.0, 'Protect': 0.0, 'Refuel': 150.0}
WEIGHT = {'radio': 1.0, 'spawn': 3.0, 'wake': 2.0, 'objective': 2.0, 'exposure': 1.0, 'misc': 0.5}
MIN_MIN, MAX_MIN, MAX_QUIET_S = 8.0, 60.0, 600.0  # accepted duration (minutes) and longest stretch without a beat
THREAT_RANGE = 14000.0
BUCKET = 60.0


@dataclass
class Report:
    duration: float
    beats: list = field(default_factory=list)     # (time, weight, kind, label)
    curve: list = field(default_factory=list)     # intensity per minute
    longest_quiet: float = 0.0
    legs: list = field(default_factory=list)      # (objective name, arrival, done)
    spawns: dict = field(default_factory=dict)    # unit id -> earliest time something spawns it

    def problems(self):
        out = []
        if self.duration / 60 < MIN_MIN:
            out.append(f"too short: {self.duration / 60:.0f} min")
        if self.duration / 60 > MAX_MIN:
            out.append(f"too long: {self.duration / 60:.0f} min")
        if self.longest_quiet > MAX_QUIET_S:
            out.append(f"{self.longest_quiet / 60:.0f} minutes without an event")
        return out


def _pt(text):
    return tuple(float(c) for c in text.strip('()').split(','))


def _d(a, b):
    return math.hypot(a[0] - b[0], a[2] - b[2])


class _Path:
    """Piecewise straight legs flown at constant speed."""

    def __init__(self, start, speed):
        self.pts, self.t, self.speed = [(0.0, start)], 0.0, speed

    def go(self, to):
        self.t += _d(self.pts[-1][1], to) / self.speed
        self.pts.append((self.t, to))
        return self.t

    def wait(self, seconds):
        self.t += seconds
        self.pts.append((self.t, self.pts[-1][1]))

    def at(self, t):
        for (t0, p0), (t1, p1) in zip(self.pts, self.pts[1:]):
            if t0 <= t <= t1:
                f = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
                return tuple(a + (b - a) * f for a, b in zip(p0, p1))
        return self.pts[-1][1]

    def first_within(self, point, radius, step=10.0):
        for k in range(int(self.t / step) + 1):
            if _d(self.at(k * step), point) <= radius:
                return k * step
        return None


def simulate(text, vehicle='F/A-26B', spawn_at=None):
    """Estimate how the mission plays. Two passes: the first finds when units spawn, the second makes the player wait
    for targets that are not there yet (a raid on the base arrives when it arrives)."""
    if spawn_at is None:
        spawn_at = simulate(text, vehicle, spawn_at={}).spawns
    root, _ = parse_game(text)
    sect = lambda n: (_first(root, n) or ('', {}, []))[2]
    units = {}
    for _, v, kids in _kids(_first(root, 'UNITS'), 'UnitSpawner'):
        f = next((c[1] for c in kids if c[0] == 'UnitFields'), {})
        units[int(v['unitInstanceID'])] = {'pos': _pt(v['globalPosition']), 'id': v['unitID'], 'name': v.get('unitName', ''),
                                           'team': f.get('unitGroup', 'Allied').split(':')[0],
                                           'start': f.get('spawnOnStart', 'True') == 'True'}
    waypoints = {int(w[1]['id']): _pt(w[1]['globalPoint']) for w in _kids(('', {}, sect('WAYPOINTS')), 'WAYPOINT')}
    objectives = {int(o[1]['objectiveID']): o for o in _kids(('', {}, sect('OBJECTIVES')), 'Objective')}
    player = next((u for u in units.values() if u['id'] in ('PlayerSpawn', 'MultiplayerSpawn')), None)
    start = player['pos'] if player else (0.0, 0.0, 0.0)
    path = _Path(start, SPEED.get(vehicle, 220.0))
    threats = [u['pos'] for u in units.values() if u['team'] == 'Enemy' and u['start']
               and u['id'] in ('SamBattery1', 'slmrmLauncher', 'MAD-4Launcher', 'SAAW', 'staticAAA-20x2')]

    # --- player route: objectives in dependency order ---
    def objective_point(o):
        v = o[1]
        if v.get('waypoint', 'null').lstrip('-').isdigit() and int(v['waypoint']) in waypoints:
            return waypoints[int(v['waypoint'])]
        tg = [i for c in o[2] if c[0] not in ('startEvent', 'failEvent', 'completeEvent')
              for i in _ids(c[1].get('targets', '') or c[1].get('target', ''))]
        pts = [units[i]['pos'] for i in tg if i in units]
        return (sum(p[0] for p in pts) / len(pts), 0.0, sum(p[2] for p in pts) / len(pts)) if pts else None

    done, order = set(), []
    pending = [i for i, o in objectives.items() if o[1].get('required') == 'True']  # optional tasks are not on the typical path
    while pending:
        ready = [i for i in pending if all(p in done or p not in objectives for p in _ids(objectives[i][1].get('preReqObjectives', '')))]
        if not ready:
            break
        pick = min(ready, key=lambda i: (objectives[i][1].get('required') != 'True', int(objectives[i][1].get('orderID', 0)), i))
        pending.remove(pick)
        done.add(pick)
        order.append(pick)
    timed_complete = {}  # objective id -> time a timer completes it (hold-out missions)
    for g in _kids(('', {}, sect('TimedEventGroups')), 'TimedEventGroup'):
        for ev in _kids(g, 'TimedEventInfo'):
            for t in _kids(ev, 'EventTarget'):
                if t[1].get('methodName') == 'CompleteObjective':
                    timed_complete[int(t[1]['targetID'])] = float(g[1].get('initialDelay', 0)) + float(ev[1].get('time', 0))
    obj_time, legs = {}, []
    for i in order:
        o = objectives[i]
        p = objective_point(o)
        arrive = path.go(p) if p else path.t
        dwell = DWELL.get(o[1].get('objectiveType'), 60.0)
        path.wait(dwell)
        late = [spawn_at[u] for c in o[2] if c[0] not in ('startEvent', 'failEvent', 'completeEvent')
                for u in _ids(c[1].get('targets', '') or c[1].get('target', '')) if u in spawn_at and not units[u]['start']]
        if late and o[1].get('objectiveType') == 'Destroy':
            # Targets that show up later come to the player: spawn time plus the part of their flight outside 30 km.
            far = [spawn_at[u] + max(0.0, _d(units[u]['pos'], p or start) - 30000.0) / 150.0 for c in o[2]
                   if c[0] not in ('startEvent', 'failEvent', 'completeEvent')
                   for u in _ids(c[1].get('targets', '') or c[1].get('target', '')) if u in spawn_at and not units[u]['start']]
            if max(far) + dwell > path.t:
                path.wait(max(far) + dwell - path.t)  # loiter until they arrive
        if i in timed_complete and timed_complete[i] > path.t:
            path.wait(timed_complete[i] - path.t)
        obj_time[i] = (arrive, path.t)
        legs.append((o[1]['objectiveName'], arrive, path.t))
    total = path.t

    # --- beats ---
    beats, seen, spawns = [], set(), {}

    def beat(t, kind, label):
        beats.append((t, WEIGHT[kind], kind, label))

    def actions(targets, t, owner):
        """Beats of one action list at time t; actions that start other events cascade."""
        for tg in targets:
            v, m = tg[1], tg[1].get('methodName')
            params = {p[1].get('name'): p[1].get('value', '') for p in _kids(tg, 'ParamInfo')}
            if m == 'DisplayMessage' and RADIO_LINE.match(params.get('s', '')):
                beat(t, 'radio', params['s'][:30])
            elif m == 'SpawnUnits':
                beat(t, 'spawn', f"{owner}: {len(_ids(params.get('unitList', '')))} units")
                for u in _ids(params.get('unitList', '')):
                    spawns[u] = min(t, spawns.get(u, t))
            elif m == 'SetEngageEnemies' and params.get('engage') == 'True':
                beat(t, 'wake', owner)
            elif m in ('BeginObjective', 'CompleteObjective', 'FailObjective'):
                beat(t, 'objective', f"{m} {owner}")
            elif m in ('SendWaypointToGPS', 'SetPath', 'TransitionWeather', 'TransitionTime', 'LightFlareAtPos'):
                beat(t, 'misc', m)
            elif m in ('Begin', 'BeginEvent', 'Restart') and v.get('targetType') in ('Timed_Events', 'Event_Sequences'):
                cascade(v['targetType'], int(v['targetID']), t)
            elif m == 'Enable' and v.get('targetType') == 'Trigger_Events':
                cascade('Trigger', int(v['targetID']), t)
            elif m == 'FireConditionalAction':
                cascade('CA', next(iter(_ids(params.get('action', ''))), -1), t)
            elif m == 'FireRandomEvent':
                cascade('Random', next(iter(_ids(params.get('r_event', params.get('rEvent', '')))), -1), t)

    def cascade(kind, ident, t):
        if (kind, ident) in seen:
            return
        seen.add((kind, ident))
        if kind == 'Timed':
            g = next((g for g in _kids(('', {}, sect('TimedEventGroups')), 'TimedEventGroup') if int(g[1]['groupID']) == ident), None)
            for ev in (_kids(g, 'TimedEventInfo') if g else []):
                actions(_kids(ev, 'EventTarget'), t + float(g[1].get('initialDelay', 0)) + float(ev[1].get('time', 0)), g[1]['groupName'])
        elif kind == 'Event_Sequences':
            s = next((s for s in _kids(('', {}, sect('EventSequences')), 'SEQUENCE') if int(s[1]['id']) == ident), None)
            clock = t
            for ev in (_kids(s, 'EVENT') if s else []):
                when = cond_time(ev[1].get('conditional'), clock)
                if when is None:
                    break  # waits for something that is not on the typical path
                clock = when + float(ev[1].get('delay', 0))
                actions(_kids(_first(ev, 'EventInfo') or ('', {}, []), 'EventTarget'), clock, s[1]['sequenceName'])
        elif kind == 'Trigger':
            n = next((n for n in _kids(('', {}, sect('TRIGGER_EVENTS')), 'TriggerEvent') if int(n[1]['id']) == ident), None)
            if n:
                fire_trigger(n, t)
        elif kind == 'CA':
            n = next((n for n in _kids(('', {}, sect('ConditionalActions')), 'ConditionalAction') if int(n[1]['id']) == ident), None)
            for blk in (_walk(n) if n else []):
                if blk[0] in ('BASE_BLOCK', 'ELSE_IF', 'NESTED_IF'):
                    actions(_kids(_first(blk, 'ACTIONS') or ('', {}, []), 'EventTarget'), t, n[1]['name'])
        elif kind == 'Random':
            r = next((r for r in _kids(('', {}, sect('RandomEvents')), 'RANDOM_EVENT') if int(r[1]['id']) == ident), None)
            acts = _kids(r, 'ACTION') if r else []
            if acts:  # the options are alternatives: take the first as typical
                actions(_kids(_first(acts[0], 'EVENT_INFO') or ('', {}, []), 'EventTarget'), t, r[1].get('note', 'random'))

    cond_cache = {}

    def cond_time(cid, floor):
        """When a conditional becomes true on the typical path: by the units/waypoints it names, else 'soon'."""
        if cid in (None, 'null', ''):
            return floor
        if cond_cache.get(cid, 0) is None:
            return None
        if cid not in cond_cache:
            c = next((c for c in _kids(('', {}, sect('Conditionals')), 'CONDITIONAL') if c[1]['id'] == str(cid)), None)
            times, skip = [], False
            for comp in (_kids(c, 'COMP') if c else []):
                f = comp[1]
                ids = _ids(f.get('unitList', '') or f.get('unit', '') or f.get('unitRef', ''))
                if player and any(units.get(i) is player for i in ids):
                    times.append(0.0)
                    continue
                if ids and all(units.get(i, {}).get('team') == 'Allied' for i in ids):
                    skip = True  # something bad happening to our side is not on the typical path
                    break
                hit = [obj_time[o][0] + (obj_time[o][1] - obj_time[o][0]) * 0.5 for o, ob in objectives.items()
                       if o in obj_time and set(ids) & {i for c2 in ob[2] if c2[0] not in ('startEvent', 'failEvent', 'completeEvent')
                                                       for i in _ids(c2[1].get('targets', '') or c2[1].get('target', ''))}]
                if hit:
                    times.append(min(hit))
                elif ids:
                    near = [path.first_within(units[i]['pos'], 30000.0) for i in ids if i in units]
                    times.append(min([x for x in near if x is not None], default=total * 0.5))
                elif f.get('type', '').startswith('SCCGlobalValue'):
                    times.append(total * 0.4)
            cond_cache[cid] = None if skip else max(times) if times else total * 0.4
            if skip:
                return None
        return max(floor, cond_cache[cid])

    def fire_trigger(n, base=0.0):
        v, kind = n[1], n[1].get('triggerType')
        t = base
        if kind == 'Proximity':
            wp = waypoints.get(int(v.get('waypoint', -1)))
            hit = path.first_within(wp, float(v.get('radius', 1000))) if wp else None
            if hit is None:
                return
            t = max(base, hit)
        elif kind == 'Conditional':
            t = cond_time(v.get('conditional'), base)
            if t is None:
                return
        actions(_kids(_first(n, 'EventInfo') or ('', {}, []), 'EventTarget'), t, v.get('eventName', 'trigger'))

    for g in _kids(('', {}, sect('TimedEventGroups')), 'TimedEventGroup'):
        if g[1].get('beginImmediately') == 'True':
            cascade('Timed', int(g[1]['groupID']), 0.0)
    for s in _kids(('', {}, sect('EventSequences')), 'SEQUENCE'):
        if s[1].get('startImmediately') == 'True':
            cascade('Event_Sequences', int(s[1]['id']), 0.0)
    for n in _kids(('', {}, sect('TRIGGER_EVENTS')), 'TriggerEvent'):
        if n[1].get('enabled') == 'True':
            seen.add(('Trigger', int(n[1]['id'])))
            fire_trigger(n)
    for i, (arrive, finish) in obj_time.items():  # objective events at the moments the player reaches them
        o = objectives[i]
        for key, when in (('startEvent', arrive), ('completeEvent', finish)):
            blk = _first(o, key)
            actions(_kids(_first(blk, 'EventInfo') or ('', {}, []), 'EventTarget') if blk else [], when, o[1]['objectiveName'])
        beat(arrive, 'objective', f"reach {o[1]['objectiveName']}")
    # threat exposure: every 30 s inside a SAM / AAA envelope
    for k in range(int(total / 30) + 1):
        if any(_d(path.at(k * 30.0), th) <= THREAT_RANGE for th in threats):
            beat(k * 30.0, 'exposure', 'threat envelope')

    beats = [b for b in beats if b[0] <= total + 1] or beats
    n = int(total // BUCKET) + 1
    curve = [0.0] * n
    for t, w, *_ in beats:
        curve[min(n - 1, int(t // BUCKET))] += w
    times = sorted({0.0, total, *[b[0] for b in beats]})
    quiet = max((b - a for a, b in zip(times, times[1:])), default=total)
    return Report(duration=total, beats=sorted(beats), curve=curve, longest_quiet=quiet, legs=legs, spawns=spawns)


def sparkline(curve):
    bars = " .:-=+*#%@"
    top = max(curve) or 1
    return "".join(bars[min(len(bars) - 1, int(c / top * (len(bars) - 1)))] for c in curve)


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    vehicle = sys.argv[sys.argv.index('--vehicle') + 1] if '--vehicle' in sys.argv else 'F/A-26B'
    for path_ in (a for a in args if a.endswith('.vts')):
        r = simulate(open(path_, encoding='utf-8').read(), vehicle)
        print(f"{path_}: {r.duration / 60:.0f} min, longest quiet {r.longest_quiet / 60:.1f} min, "
              f"problems: {r.problems() or 'none'}\n  [{sparkline(r.curve)}]")
