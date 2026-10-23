"""pytol.logic (condition algebra, variables, phases) and the Mission event helpers."""
import os

import pytest

from pytol import Mission, Waypoint
from pytol.classes.actions import SystemActions
from pytol.logic import Counter, Logic, Unit, Units, chance
from pytol.parsers.vts_validator import validate, parse_game


def test_algebra():
    low = Unit(1).radar_alt_below(150)
    hid = ~Unit(1).detected_by('Enemy')
    assert hid.leaves()[0].fields['is_not'] is True
    tree = (low & hid & (Units([2, 3]).alive() < 2)).tree()
    root = tree.components[tree.root]
    assert root.__class__.__name__ == 'Sccand' and len(root.factors) == 3  # flattened, not nested
    neg = ~(low & hid)  # De Morgan: SCCAnd/SCCOr have no isNot in the game
    assert neg.op == 'or' and [p.fields['is_not'] for p in neg.parts] == [True, False]
    gv = Counter('alarm')
    assert (~(gv >= 2)).fields == {'gv': 'alarm', 'comparison': 'Less_Than', 'c_value': 2}
    assert (gv >= 2).fields['comparison'] == 'Greater_Than' and (gv >= 2).fields['c_value'] == 1
    assert chance(30).tree().components[0].chance == 30


def test_airspeed_is_metres_per_second():
    assert Unit(1).slower(280).fields['method_parameters'] == ['Less_Than', '144.0']


@pytest.fixture(scope='module')
def mission():
    vtol = os.getenv('VTOL_VR_DIR', '').strip().strip('"')
    path = os.getenv('PYTOL_TEST_MAP') or os.path.join(vtol, 'CustomMaps', 'hMap2')
    if not os.path.isdir(path):
        pytest.skip("hMap2 not available (set VTOL_VR_DIR or PYTOL_TEST_MAP)")
    return lambda sid: Mission(scenario_name=sid, scenario_id=sid, description="", vehicle="F/A-26B", map_id="hMap2",
                               map_path=path, vtol_directory="", verbose=False)


def test_sequence_delay_follows_condition(mission):
    m = mission('seq_test')
    L = Logic(m)
    flag = L.flag('go')
    m.sequence("s", [(flag.is_set, 10.0, [SystemActions().display_message("after", 3.0)])])
    nodes = m.event_sequences[0].events
    assert [(n.delay, n.conditional is not None) for n in nodes] == [(0.0, True), (10.0, False)]  # wait, then delay


def test_helpers_assign_ids_and_save(mission, tmp_path):
    m = mission('helpers_test')
    L = Logic(m)
    wp = Waypoint(name="A", global_point=[100000.0, 0.0, 100000.0])
    m.add_waypoint(wp)
    alarm = L.counter('alarm')
    say = lambda s: [SystemActions().display_message(s, 3.0)]
    assert (m.on_enter("a", wp, 1000, say("in")), m.on_condition("b", alarm >= 1, say("c"))) == (0, 1)
    begin = m.timer("t", [(5.0, say("tick"))])
    assert begin.target_id == 1
    fire = m.when(alarm >= 2, say("y"), elif_=[(alarm >= 1, say("e"))], else_=say("n"))
    m.random_choice("r", [(1, say("one")), (1, say("two"))])
    ph = L.phases()
    ph.add('one'); ph.add('two', checkpoint=True)
    ph.goto(0, alarm >= 1, 1)
    ph.build()
    m.on_enter("fire", wp, 1000, [fire])
    out = m.save_mission(str(tmp_path), copy_map=False)
    text = open(os.path.join(str(tmp_path), 'helpers_test', 'helpers_test.vts'), encoding='utf-8').read()
    assert validate(text) == []
    root, _ = parse_game(text)
    assert [c[0] for c in next(c for c in root[2] if c[0] == 'ConditionalActions')[2][0][2][0][2]] == [
        'CONDITIONAL', 'ACTIONS', 'ELSE_IF', 'ELSE_ACTIONS']


def test_dead_end_phase_fails_at_build(mission):
    m = mission('phase_test')
    ph = Logic(m).phases()
    ph.add('a'); ph.add('b'); ph.add('c')
    ph.goto(0, Counter('x') >= 1, 1)  # b has no exit and c is unreachable
    with pytest.raises(ValueError, match="dead ends"):
        ph.build()


def test_condition_catalog_flags_methods_the_class_lacks(mission, tmp_path):
    """SCC_DetectedBy exists on PlayerSpawn only: on a co-op slot the game logs 'Missing method' and the condition is false."""
    from pytol import create_unit
    from pytol.classes.conditionals import ConditionalTree, create_conditional
    m = mission('catalog_test')
    p = create_unit("PlayerSpawn", "P", "Allied", [100000.0, 300.0, 100000.0], [0, 0, 0])
    mp = create_unit("MultiplayerSpawn", "M", "Allied", [100100.0, 300.0, 100000.0], [0, 0, 0], vehicle="F/A-26B")
    ids = [m.add_unit(p, placement="airborne"), m.add_unit(mp, placement="airborne")]

    def check(uid, method, params):
        tree = ConditionalTree()
        tree.add_comp(0, create_conditional("SCCUnit", unit=str(uid), method_name=method, method_parameters=params))
        tree.set_root(0)
        m.add_conditional(tree)

    check(ids[0], "SCC_DetectedBy", ["Enemy"])        # fine on PlayerSpawn
    check(ids[1], "SCC_DetectedBy", ["Enemy"])        # not on MultiplayerSpawn
    check(ids[0], "SCC_AltitudeRadar", ["Less_Than"])  # one parameter missing
    m.save_mission(str(tmp_path), copy_map=False)
    problems = validate(open(os.path.join(str(tmp_path), 'catalog_test', 'catalog_test.vts'), encoding='utf-8').read())
    assert any("MultiplayerSpawn.SCC_DetectedBy" in p for p in problems), problems
    assert any("SCC_AltitudeRadar takes 2 parameters" in p for p in problems), problems
    assert not any("PlayerSpawn.SCC_DetectedBy" in p for p in problems)


def test_contingency_pattern(mission, tmp_path):
    from pytol import create_objective
    from pytol.patterns import conditional_objective, contingency, counter_objective, tally
    m = mission('pattern_test')
    L = Logic(m)
    wp = Waypoint(name="A", global_point=[100000.0, 0.0, 100000.0])
    m.add_waypoint(wp)
    plan_a = create_objective("Fly_To", m.next_objective_id(), "A", "a", waypoint=wp, required=False, trigger_radius=1000)
    m.add_objective(plan_a)
    plan_b = create_objective("Fly_To", m.next_objective_id(), "B", "b", waypoint=wp, required=False,
                              start_mode="Triggered", trigger_radius=1000)
    m.add_objective(plan_b)
    goal, won = contingency(m, "Aim", "reach it", plan_a, plan_b)
    kills = L.counter('kills')
    counter_objective(m, "Kills", "two", kills, 2)
    assert goal.required and not plan_a.required and goal.objective_id == 2
    ids = [o.objective_id for o in m.objectives]
    assert len(ids) == len(set(ids))
    m.save_mission(str(tmp_path), copy_map=False)
    text = open(os.path.join(str(tmp_path), 'pattern_test', 'pattern_test.vts'), encoding='utf-8').read()
    assert validate(text) == [] and "Aim done" in text


def test_catalog_covers_older_sc_methods():
    from pytol.parsers.vts_validator import VT_CONDITIONS
    assert 'SC_MissileLaunched' in VT_CONDITIONS['AIMissileSilo'] and 'SCC_AnyNearWaypoint' in VT_CONDITIONS['SCCUnitList']
