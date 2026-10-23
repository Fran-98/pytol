"""
Static analysis of a generated .vts, because missions cannot be playtested yet. Checks the logic graph:

- every objective's prerequisites exist, have no cycle, and every Triggered objective is begun by some action;
- every trigger, timed group, sequence, conditional action and random event can actually fire;
- every global value that is read is written somewhere;
- no unit reference (action, condition, objective) points at a unit that does not exist or is never spawned;
- no event list plays two radio lines at once.

    python -m pytol.parsers.vts_analyzer mission.vts [...]
"""
import re
import sys

from pytol.parsers.vts_validator import parse_game

GV_WRITES = {'SetValue', 'IncrementValue', 'DecrementValue', 'AddValues', 'SubtractValues', 'MultiplyValue',
             'MultiplyValues', 'CopyValue', 'ResetValue'}
GV_READ_FIELDS = ('gv', 'gvA', 'gvB')
UNIT_COND_FIELDS = ('unitList', 'unit', 'unitRef')
UNIT_PARAM_TYPES = {'UnitReference', 'UnitReferenceList', 'UnitReferenceListAI', 'UnitReferenceListOtherSubs'}
RADIO_LINE = re.compile(r'^[A-Z][A-Z0-9 ]+: ')  # a radio line shown as a subtitle: "CALLSIGN: text"
LINE_END = re.compile(r'[.!?]\s*$')


def _kids(node, name):
    return [c for c in node[2] if c[0] == name]


def _first(node, name):
    return next(iter(_kids(node, name)), None)


def _walk(node):
    yield node
    for c in node[2]:
        yield from _walk(c)


def _ids(text):
    return [int(x) for x in re.split(r'[;,]', text or '') if x.strip().lstrip('-').isdigit() and int(x) >= 0]


def _targets(info):
    return _kids(info, 'EventTarget') if info else []


def analyze(text, radio_line=RADIO_LINE):
    """Returns a list of problems (empty when the graph holds together). `radio_line` matches the on-screen text of a
    radio message, to find two lines played by one event list at once."""
    root, _ = parse_game(text)
    problems = []

    def section(name):
        n = _first(root, name)
        return n[2] if n else []

    units = {int(v['unitInstanceID']): (v, kids) for _, v, kids in _kids(_first(root, 'UNITS'), 'UnitSpawner')}
    names = {uid: v.get('unitName', str(uid)) for uid, (v, _) in units.items()}
    spawn_on_start = {uid: next((c[1].get('spawnOnStart', 'True') for c in kids if c[0] == 'UnitFields'), 'True') == 'True'
                      for uid, (_, kids) in units.items()}
    gvs, constants = {}, set()
    for n in section('GlobalValues'):
        if n[0] == 'gv':
            gid, gname, _, initial = n[1]['data'].split(';')[:4]
            gvs[int(gid)] = gname
            if float(initial or 0) != 0:
                constants.add(int(gid))  # a non-zero start that nothing writes is a set value (a goal), not a bug

    # Every list of actions with where it lives.
    lists = []  # (owner label, [EventTarget nodes])
    for n in _kids(('', {}, section('TRIGGER_EVENTS')), 'TriggerEvent'):
        lists.append((f"trigger '{n[1].get('eventName')}'", _targets(_first(n, 'EventInfo'))))
    for n in _kids(('', {}, section('TimedEventGroups')), 'TimedEventGroup'):
        for ev in _kids(n, 'TimedEventInfo'):
            lists.append((f"timer '{n[1]['groupName']}' @{ev[1].get('time')}s", _kids(ev, 'EventTarget')))
    for n in _kids(('', {}, section('EventSequences')), 'SEQUENCE'):
        for ev in _kids(n, 'EVENT'):
            lists.append((f"sequence '{n[1]['sequenceName']}' {ev[1].get('nodeName')}", _targets(_first(ev, 'EventInfo'))))
    for n in _kids(('', {}, section('OBJECTIVES')), 'Objective'):
        for key in ('startEvent', 'failEvent', 'completeEvent'):
            blk = _first(n, key)
            lists.append((f"objective '{n[1]['objectiveName']}' {key}", _targets(_first(blk, 'EventInfo')) if blk else []))
    for n in _kids(('', {}, section('RandomEvents')), 'RANDOM_EVENT'):
        for act in _kids(n, 'ACTION'):
            lists.append((f"random '{n[1].get('note')}' {act[1].get('actionName')}", _targets(_first(act, 'EVENT_INFO'))))
    for n in _kids(('', {}, section('ConditionalActions')), 'ConditionalAction'):
        for blk in _walk(n):
            if blk[0] in ('BASE_BLOCK', 'ELSE_IF', 'NESTED_IF'):
                lists.append((f"conditional action '{n[1]['name']}'", _targets(_first(blk, 'ACTIONS'))))
            if blk[0] == 'ELSE_ACTIONS':
                lists.append((f"conditional action '{n[1]['name']}' else", _targets(blk)))

    def param(t, ptype):
        return [p[1].get('value') for p in _kids(t, 'ParamInfo') if p[1].get('type') == ptype]

    fired = {'Trigger': set(), 'Timed': set(), 'Sequence': set(), 'CA': set(), 'Random': set(), 'Objective': set()}
    gv_written, spawned = set(), set()
    for _, targets in lists:
        for t in targets:
            v, method, tid = t[1], t[1].get('methodName'), t[1].get('targetID', '0')
            if method == 'Enable' and v.get('targetType') == 'Trigger_Events':
                fired['Trigger'].add(int(tid))
            elif method in ('Begin',) and v.get('targetType') == 'Timed_Events':
                fired['Timed'].add(int(tid))
            elif method in ('BeginEvent', 'Restart') and v.get('targetType') == 'Event_Sequences':
                fired['Sequence'].add(int(tid))
            elif method == 'Trigger' and v.get('targetType') == 'Trigger_Events':
                fired['Trigger'].add(int(tid))
            elif method == 'FireConditionalAction':
                fired['CA'].update(_ids(param(t, 'ConditionalActionReference')[0] if param(t, 'ConditionalActionReference') else ''))
            elif method == 'FireRandomEvent':
                fired['Random'].update(_ids(param(t, 'RandomEventReference')[0] if param(t, 'RandomEventReference') else ''))
            elif method == 'BeginObjective' and v.get('targetType') == 'Objective':
                fired['Objective'].add(int(tid))
            if method in GV_WRITES:
                gv_written.update(_ids(';'.join(param(t, 'GlobalValue'))))
            if method == 'SpawnUnits':
                spawned.update(i for val in param(t, 'UnitReferenceListAI') for i in _ids(val))

    # Conditions: unit and global value references.
    cond_units, gv_read = set(), set()
    for n in _walk(('', {}, section('Conditionals'))):
        if n[0] != 'COMP':
            continue
        for f in UNIT_COND_FIELDS:
            cond_units.update(_ids(n[1].get(f, '')))
        for f in GV_READ_FIELDS:
            if f in n[1] and n[1]['type'].startswith('SCCGlobalValue'):
                gv_read.add(int(n[1][f]))
    objectives = {int(o[1]['objectiveID']): o for o in _kids(('', {}, section('OBJECTIVES')), 'Objective')}
    for o in objectives.values():  # a Global_Value objective reads two global values
        for _, v, _ in o[2]:
            if o[1].get('objectiveType') == 'Global_Value':
                gv_read.update(int(v[k]) for k in ('currentValue', 'targetValue') if v.get(k, '').lstrip('-').isdigit())

    # --- global values ---
    for g in sorted(gv_read - gv_written - constants):
        problems.append(f"global value '{gvs.get(g, g)}' is read but never written")

    # --- units ---
    def check_unit(uid, where):
        if uid not in units:
            problems.append(f"{where} references unit {uid}, which does not exist")
        elif not spawn_on_start[uid] and uid not in spawned:
            problems.append(f"{where} uses unit '{names[uid]}', which is never spawned")

    for uid in cond_units:
        check_unit(uid, "a condition")
    for owner, targets in lists:
        for t in targets:
            if t[1].get('targetType') == 'Unit':
                check_unit(int(t[1]['targetID']), owner)
            for p in _kids(t, 'ParamInfo'):
                if p[1].get('type') in UNIT_PARAM_TYPES:
                    for uid in _ids(p[1].get('value', '')):
                        if uid not in units:
                            problems.append(f"{owner} references unit {uid}, which does not exist")
    for o in objectives.values():
        for _, v, _ in (c for c in o[2] if c[0] not in ('startEvent', 'failEvent', 'completeEvent')):
            for key in ('target', 'targets'):
                for uid in _ids(v.get(key, '')):
                    check_unit(uid, f"objective '{o[1]['objectiveName']}'")

    # --- objectives ---
    for oid, o in objectives.items():
        for pre in _ids(o[1].get('preReqObjectives', '')):
            if pre not in objectives:
                problems.append(f"objective '{o[1]['objectiveName']}' needs missing objective {pre}")
    state = {}

    def visit(oid, path):
        if state.get(oid) == 2:
            return
        if state.get(oid) == 1:
            problems.append("objective prerequisites loop: " + " -> ".join(objectives[i][1]['objectiveName'] for i in path))
            return
        state[oid] = 1
        for pre in _ids(objectives[oid][1].get('preReqObjectives', '')):
            if pre in objectives:
                visit(pre, path + [pre])
        state[oid] = 2

    for oid in objectives:
        visit(oid, [oid])
    for oid, o in objectives.items():
        if o[1].get('startMode') == 'Triggered' and oid not in fired['Objective']:
            problems.append(f"objective '{o[1]['objectiveName']}' starts when triggered but nothing begins it")

    # --- things that can never fire ---
    for n in _kids(('', {}, section('TRIGGER_EVENTS')), 'TriggerEvent'):
        if n[1].get('enabled') == 'False' and int(n[1]['id']) not in fired['Trigger']:
            problems.append(f"trigger '{n[1].get('eventName')}' is disabled and nothing enables it")
    for n in _kids(('', {}, section('TimedEventGroups')), 'TimedEventGroup'):
        if n[1].get('beginImmediately') == 'False' and int(n[1]['groupID']) not in fired['Timed']:
            problems.append(f"timer '{n[1]['groupName']}' never begins")
    for n in _kids(('', {}, section('EventSequences')), 'SEQUENCE'):
        if n[1].get('startImmediately') == 'False' and int(n[1]['id']) not in fired['Sequence']:
            problems.append(f"sequence '{n[1]['sequenceName']}' never begins")
    for n in _kids(('', {}, section('ConditionalActions')), 'ConditionalAction'):
        if int(n[1]['id']) not in fired['CA']:
            problems.append(f"conditional action '{n[1]['name']}' is never fired")
    for n in _kids(('', {}, section('RandomEvents')), 'RANDOM_EVENT'):
        if int(n[1]['id']) not in fired['Random']:
            problems.append(f"random event '{n[1].get('note')}' is never fired")

    # --- radio ---
    for owner, targets in lists:
        lines = [p for t in targets if t[1].get('methodName') == 'DisplayMessage'
                 for p in param(t, 'System.String') if radio_line.match(p)]
        if len(lines) > 1 and not owner.startswith('random'):
            problems.append(f"{owner} plays {len(lines)} radio lines at once: {lines[0][:40]}... / {lines[1][:40]}...")
    return problems


if __name__ == '__main__':
    bad = 0
    for path in sys.argv[1:]:
        found = analyze(open(path, encoding='utf-8').read())
        bad += bool(found)
        print(path, *found, sep='\n  ' if found else ' ok')
    sys.exit(1 if bad else 0)
