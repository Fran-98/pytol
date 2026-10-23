"""The static graph analyzer and the abstract flight simulator work on a saved .vts."""
import os

import pytest

from pytol import Mission, Waypoint, create_objective, create_unit
from pytol.analysis.simulate import simulate, sparkline
from pytol.classes.actions import SystemActions
from pytol.logic import Counter, Logic, Unit, Units
from pytol.parsers.vts_analyzer import analyze


@pytest.fixture
def build():
    vtol = os.getenv('VTOL_VR_DIR', '').strip().strip('"')
    path = os.getenv('PYTOL_TEST_MAP') or os.path.join(vtol, 'CustomMaps', 'hMap2')
    if not os.path.isdir(path):
        pytest.skip("hMap2 not available (set VTOL_VR_DIR or PYTOL_TEST_MAP)")

    def make(tmp_path, sid, break_it=False, far=60000.0):
        m = Mission(scenario_name=sid, scenario_id=sid, description="", vehicle="F/A-26B", map_id="hMap2", map_path=path,
                    vtol_directory="", verbose=False)
        home = Waypoint(name="Home", global_point=[100000.0, 300.0, 100000.0])
        goal = Waypoint(name="Goal", global_point=[100000.0 + far, 300.0, 100000.0])
        m.add_waypoint(home), m.add_waypoint(goal)
        m.rtb_wpt_id = home
        player = m.add_unit(create_unit("PlayerSpawn", "P", "Allied", [100000.0, 300.0, 100000.0], [0, 90, 0]), placement="airborne")
        fly = create_objective("Fly_To", 0, "Go", "Go.", waypoint=goal, trigger_radius=3000)
        land = create_objective("Land", 1, "Land", "Land.", waypoint=home, prereqs=[fly], radius=2500)
        m.add_objective(fly), m.add_objective(land)
        say = lambda *t: [SystemActions().display_message(x, 3.0) for x in t]
        m.on_enter("mid", goal, 20000, say("OVERLORD: halfway."))
        m.timer("check", [(30.0, say("OVERLORD: radar contact."))])
        if break_it:
            L = Logic(m)
            m.on_condition("never", L.counter('ghost') >= 1, [])                       # read, never written
            sleeper = m.add_unit(create_unit("SAAW", "Sleeper", "Enemy", [105000.0, 0, 100000.0], [0, 0, 0]),
                                 placement="ground")
            m.on_condition("dead", Units([sleeper]).all_dead(), [])
            m.when(Unit(player).faster(300), say("fast"))                              # fired by nothing
            m.on_enter("two lines", home, 3000, say("OVERLORD: one.", "OVERLORD: two."))
        m.save_mission(str(tmp_path), copy_map=False)
        return open(os.path.join(str(tmp_path), sid, f"{sid}.vts"), encoding='utf-8').read()
    return make


def test_clean_mission_has_no_findings(build, tmp_path):
    assert analyze(build(tmp_path, 'clean')) == []


def test_broken_graph_is_found(build, tmp_path):
    problems = " | ".join(analyze(build(tmp_path, 'broken', break_it=True)))
    for expect in ("'ghost' is read but never written", "is never fired", "radio lines at once"):
        assert expect in problems, (expect, problems)


def test_simulation_timeline(build, tmp_path):
    r = simulate(build(tmp_path, 'sim', far=80000.0), 'F/A-26B')
    assert [n for n, *_ in r.legs] == ['Go', 'Land']
    assert 5 * 60 < r.duration < 30 * 60 and len(r.curve) == int(r.duration // 60) + 1
    assert len(sparkline(r.curve)) == len(r.curve)
    assert any("without an event" in p or "too short" in p for p in r.problems()) or r.problems() == []
