"""Builds a mission with every kind of event wiring and checks it loads the way the game reads .vts files.

Needs VTOL_VR_DIR with CustomMaps/hMap2 (skipped otherwise).
"""
import os

import pytest

from pytol import Mission
from pytol.classes.units import create_unit
from pytol.classes.objectives import create_objective
from pytol.classes.conditionals import ConditionalTree, create_conditional
from pytol.classes.actions import SystemActions, GlobalValueActions, ObjectiveActions
from pytol.classes.mission_objects import (Trigger, Waypoint, GlobalValue, ConditionalAction, ConditionalBlock, ConditionalBlock,
                                           EventSequence, SequenceEvent)
from pytol.parsers.vts_validator import validate, parse_game


@pytest.fixture(scope='module')
def vts_text(tmp_path_factory):
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    vtol = os.getenv('VTOL_VR_DIR', '').strip().strip('"')
    if not os.path.isdir(os.path.join(vtol, 'CustomMaps', 'hMap2')):
        pytest.skip("hMap2 not available")

    m = Mission(scenario_name="Builder test", scenario_id="builder_test", description="", vehicle="F/A-26B",
                map_id="hMap2", vtol_directory=vtol, verbose=False)
    home = Waypoint(name="Home", global_point=[51831.2, 276.8, 118559.8])
    orbit = Waypoint(name="Orbit", global_point=[60000.0, 4000.0, 110000.0])
    m.add_waypoint(home)
    m.add_waypoint(orbit)
    m.rtb_wpt_id = home  # objects and ints are both accepted

    player = create_unit("PlayerSpawn", "Player", "Allied", [50747.1, 300.0, 118161.5], [0, 346.8, 0])
    tanker = create_unit("KC-49", "Texaco", "Allied", [53274.0, 4050.0, 95194.7], [0, 139.1, 0])
    sam = create_unit("SamBattery1", "SAM", "Enemy", [57036.0, 300.0, 115526.0], [0, 0, 0])
    m.add_unit(player, placement="ground")
    m.add_unit(tanker, placement="airborne")
    sam_id = m.add_unit(sam, placement="ground")

    m.add_global_value(GlobalValue(name="kills", initial_value=0))

    o1 = create_objective("Fly_To", 0, "Ingress", "Fly to the orbit point.", waypoint=orbit)
    o2 = create_objective("Destroy", 1, "Strike", "Kill the SAM.", prereqs=[o1], targets=[sam_id], min_required=1)
    o2.complete_event_targets = [SystemActions().display_message("SAM down", 5.0)]
    m.add_objective(o1)
    m.add_objective(o2)

    m.add_trigger_event(Trigger(id=0, name="Go", trigger_type="Proximity", waypoint=orbit, radius=20000,
                                spherical_radius=False, trigger_mode="Player", proxy_mode="OnEnter",
                                event_targets=[tanker.actions.set_orbit_now(orbit, 10000.0, 4000.0),
                                               GlobalValueActions("kills").increment_value(1.0),
                                               ObjectiveActions(1).begin_objective()]))

    tree = ConditionalTree()
    tree.add_comp(0, create_conditional("SCCUnitAlive", unit_ref=str(sam_id)))
    tree.set_root(0)
    cond_id = m.add_conditional(tree, conditional_id=0)
    m.add_conditional_action(ConditionalAction(id=0, name="While SAM alive", conditional_id=cond_id,
                                               actions=[SystemActions().display_message("SAM active", 3.0)],
                                               else_if=[ConditionalBlock(conditional_id=cond_id, name="elif",
                                                                         actions=[SystemActions().display_message("elif", 3.0)])],
                                               else_actions=[SystemActions().display_message("SAM dead", 3.0)]))
    m.add_event_sequence(EventSequence(id=0, sequence_name="Intro", start_immediately=True, events=[
        SequenceEvent(node_name="hello", delay=1.0, actions=[SystemActions().display_message("Go", 3.0)])]))

    out = m.save_mission(str(tmp_path_factory.mktemp("vts")))
    path = out if out.endswith('.vts') else os.path.join(out, 'builder_test.vts')
    return open(path, encoding='utf-8').read()


def test_game_loads_everything(vts_text):
    from pytol.classes.units import ID_TO_CLASS
    (_, _, children), _ = parse_game(vts_text)
    spawners = next(c for c in children if c[0] == 'UNITS')[2]
    unit_classes = {int(v['unitInstanceID']): ID_TO_CLASS[v['unitID']].__name__ for _, v, _ in spawners}
    assert validate(vts_text, unit_classes) == []


def test_specific_fields(vts_text):
    (_, top, children), _ = parse_game(vts_text)
    assert top['rtbWptID'] == 'wpt:0'
    assert top['allowedEquips'].startswith('af_')
    objectives = next(c for c in children if c[0] == 'OBJECTIVES')[2]
    strike = next(o for o in objectives if o[1]['objectiveName'] == 'Strike')
    assert strike[1]['preReqObjectives'] == '0;'
    ca = next(c for c in children if c[0] == 'ConditionalActions')[2][0]
    assert [c[0] for c in ca[2]] == ['BASE_BLOCK']
    assert [c[0] for c in ca[2][0][2]] == ['CONDITIONAL', 'ACTIONS', 'ELSE_IF', 'ELSE_ACTIONS']
    assert ca[2][0][2][2][1]['blockId'] != ca[2][0][1]['blockId']
    sequence = next(c for c in children if c[0] == 'EventSequences')[2][0]
    event = next(c for c in sequence[2] if c[0] == 'EVENT')
    assert 'conditional' not in event[1]
