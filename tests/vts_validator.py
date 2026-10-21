"""
Checks a .vts the way VTOL VR loads it.

`parse_game` mirrors ConfigNode.ParseNode: indentation is ignored and only the values written BEFORE the
first child node of a block are read. `validate` reports anything the game would ignore or fail on.

Run on files: python tests/vts_validator.py path/to/mission.vts [...]
"""
import sys

from pytol.resources.resources import load_json_data

VT_EVENTS = load_json_data('vt_events.json')['classes']
TARGET_CLASS = {'Objective': 'VTObjective', 'UnitGroup': 'VTUnitGroup', 'Timed_Events': 'VTTimedEventGroup',
                'Trigger_Events': 'ScenarioTriggerEvents', 'Event_Sequences': 'VTSequencedEvent',
                'System': 'VTScenario', 'Base': 'VTMapEdScenarioBasePrefab', 'Static_Object': 'VTSODestructible'}
UNIT_CLASS_OF = {}


def parse_game(text):
    """ConfigNode.ParseNode port -> (name, values dict, children list, ignored value lines)."""
    lines = [ln for ln in text.splitlines() if ln]
    ignored = []

    def node(start, end):
        name = lines[start].replace(' ', '').replace('\t', '')
        values, children = {}, []
        num = start
        for i in range(start + 2, end + 1):
            if '=' in lines[i]:
                k, v = lines[i].split('=', 1)
                values[k.strip()] = v.strip()
                continue
            num = i
            break
        if '}' in lines[num]:
            return name, values, children
        depth, child_start = 0, -1
        for j in range(num, end + 1):
            if '=' in lines[j]:
                if depth == 0:
                    ignored.append(f"{name}: '{lines[j].strip()}' comes after a child node and is ignored")
                continue
            if '{' in lines[j]:
                depth += 1
                if depth == 1:
                    child_start = j - 1
            elif '}' in lines[j]:
                if depth == 1 and child_start >= 0:
                    children.append(node(child_start, j + 1))
                    child_start = -1
                depth -= 1
        return name, values, children

    return node(0, len(lines) - 1), ignored


def _walk(n, path=()):
    name, values, children = n
    yield path + (name,), values, children
    for c in children:
        yield from _walk(c, path + (name,))


def _event(class_name, display):
    while class_name in VT_EVENTS:
        e = VT_EVENTS[class_name]['events'].get(display)
        if e:
            return e
        class_name = VT_EVENTS[class_name]['base']
    return None


def validate(text, unit_classes=None):
    """List of problems. unit_classes: {unitInstanceID: C# class} to check unit actions (optional)."""
    root, problems = parse_game(text)
    problems = list(problems)
    _, top, _ = root
    for key in ('rtbWptID', 'refuelWptID'):
        v = top.get(key, '')
        if v and not v.startswith(('wpt:', 'unit:')):
            problems.append(f"{key} = {v}: must be 'wpt:<id>' or 'unit:<id>'")
    if not top.get('allowedEquips'):
        problems.append("allowedEquips is empty: the player spawns with no weapons")
    for path, values, children in _walk(root):
        if path[-1] != 'EventTarget':
            continue
        ttype, display, method = values.get('targetType'), values.get('eventName'), values.get('methodName')
        if not method:
            problems.append(f"EventTarget '{display}' has no methodName")
            continue
        cls = (unit_classes or {}).get(int(values.get('targetID', -1))) if ttype == 'Unit' else TARGET_CLASS.get(ttype)
        if ttype not in TARGET_CLASS and ttype != 'Unit':
            problems.append(f"EventTarget '{display}': targetType {ttype} does not exist")
        event = _event(cls, display) if cls else None
        if cls and not event:
            problems.append(f"EventTarget '{display}': no such action on {cls}")
        if event and event['method'] != method:
            problems.append(f"EventTarget '{display}': methodName {method} should be {event['method']}")
        params = [c for c in children if c[0] == 'ParamInfo']
        for i, (_, pv, _) in enumerate(params):
            t = pv.get('type', '')
            if t in ('string', 'bool', 'float', 'int', ''):
                problems.append(f"EventTarget '{display}': ParamInfo type '{t}' is not a .NET type name")
            elif event and i < len(event['params']) and event['params'][i]['type'] != t:
                problems.append(f"EventTarget '{display}': param {i} type {t} should be {event['params'][i]['type']}")
        if event and len(params) != len(event['params']):
            problems.append(f"EventTarget '{display}': {len(params)} params, method takes {len(event['params'])}")
    return problems


if __name__ == '__main__':
    bad = 0
    for f in sys.argv[1:]:
        issues = validate(open(f, encoding='utf-8').read())
        bad += bool(issues)
        print(f"{'FAIL' if issues else 'ok  '} {f}")
        for i in issues:
            print(f"     - {i}")
    sys.exit(1 if bad else 0)
