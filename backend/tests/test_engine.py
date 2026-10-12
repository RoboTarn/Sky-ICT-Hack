import pytest
from backend.engine import Engine, DomainError
from backend.routing import route

@pytest.fixture
def engine():
    e = Engine(':memory:')
    yield e
    e.db.close()

def plan_for(e, kind='flight_delay', zone='B6'):
    incident = e.incident(kind, zone)
    plans, _, _ = e.proposals(incident['id'])
    assert plans
    return incident, plans[0]

def travel_all(e, missions):
    for m in missions:
        e.mission_action(m['id'], 'accept')
    for m in [m for m in missions if m['kind'] == 'handoff']:
        e.mission_action(m['id'], 'depart')
        e.advance(max(1, m['route']['seconds']))
    for m in [m for m in missions if m['kind'] == 'response']:
        e.mission_action(m['id'], 'depart')
    e.advance(max([m['route']['seconds'] for m in missions] + [1]))

def test_seed_and_delay_recovery_are_computed(engine):
    state = engine.snapshot()
    assert (len(state['gates']), len(state['flights']), len(state['crew']), len(state['gse'])) == (6, 8, 24, 8)
    assert state['forecast']['lateTasks'] == 0
    _, plan = plan_for(engine)
    assert plan['after']['lateTasks'] < plan['before']['lateTasks']
    assert set(plan['assignments'][0]['crewIds']) == {'A09', 'A17'}
    member = next(m for m in plan['assignments'][0]['members'] if m['crewId'] == 'A17')
    assert member['backfill']['crewId'] == 'A21'
    assert member['previousTaskId'] == 'T515'

def test_full_handoff_and_mission_lifecycle(engine):
    incident, plan = plan_for(engine)
    ids = engine.approve(plan['id'])
    missions = [m for m in engine.state['missions'] if m['id'] in ids]
    source = next(m for m in missions if m['crewId'] == 'A17')
    engine.mission_action(source['id'], 'accept')
    with pytest.raises(DomainError, match='รับช่วง'): engine.mission_action(source['id'], 'depart')
    # Work through the relief crew and then the complete response team.
    for m in missions:
        if m['status'] == 'assigned': engine.mission_action(m['id'], 'accept')
    relief = next(m for m in missions if m['kind'] == 'handoff')
    engine.mission_action(relief['id'], 'depart'); engine.advance(1)
    assert relief['status'] == 'completed'
    assert engine._get('tasks', 'T515')['assignedCrew'] == ['A21']
    for m in missions:
        if m['kind'] == 'response': engine.mission_action(m['id'], 'depart')
    engine.advance(300)
    for m in missions:
        if m['kind'] == 'response': engine.mission_action(m['id'], 'start')
    with pytest.raises(DomainError, match='checklist'): engine.mission_action(source['id'], 'complete')
    for m in missions:
        if m['kind'] == 'response': engine.mission_action(m['id'], 'check', checked=list(range(len(m['checklist']))))
    with pytest.raises(DomainError, match='ระยะเวลา'): engine.mission_action(source['id'], 'complete')
    engine.advance(480)
    for m in missions:
        if m['kind'] == 'response': engine.mission_action(m['id'], 'complete')
    assert engine._get('incidents', incident['id'])['status'] == 'resolved'
    assert engine._get('tasks', 'T421')['status'] == 'completed'

def test_stale_and_duplicate_approval_are_rejected(engine):
    _, plan = plan_for(engine)
    engine.incident('gse_failure')
    with pytest.raises(DomainError, match='ล้าสมัย'): engine.approve(plan['id'])
    fresh, _, _ = engine.proposals(plan['incidentId'])
    engine.approve(fresh[0]['id'])
    with pytest.raises(DomainError, match='ล้าสมัย'): engine.approve(fresh[0]['id'])
    reservations = [m['crewId'] for m in engine.state['missions'] if m['status'] == 'assigned']
    assert len(reservations) == len(set(reservations))

@pytest.mark.parametrize('kind', ['gate_change', 'staff_absence', 'gse_failure', 'injury', 'fire'])
def test_all_scenarios_generate_qualified_plans(engine, kind):
    _, plan = plan_for(engine, kind)
    for assignment in plan['assignments']:
        task = engine._get('tasks', assignment['taskId'])
        assert len(assignment['crewIds']) == task['minStaff']
        for member in assignment['members']:
            assert set(task['requiredSkills']) <= set(member['skills'])
            if task['zone'] == 'B3' and kind == 'fire': assert 'fire_response' in member['skills']
        assert all(engine._get('gse', gid)['status'] != 'broken' for gid in assignment['gseIds'])
    engine.approve(plan['id'])

def test_fire_closure_blocks_general_crew_and_allows_responders(engine):
    engine.incident('fire')
    assert route(engine.state, 'HUB', 'B3') is None
    assert route(engine.state, 'MED', 'B3', True)
    assert route(engine.state, 'B1', 'B6')['nodes'].count('B3') == 0
    assert engine._get('tasks', 'T219')['status'] == 'suspended'

def test_no_feasible_plan_does_not_issue_unsafe_missions(engine):
    i = engine.incident('injury')
    for c in engine.state['crew']: c['certValidUntil'] = -1
    plans, _, _ = engine.proposals(i['id'])
    assert not plans and not engine.state['missions']
    assert engine.state['ai']['status'] == 'no_plan'

def test_rejection_releases_resource_and_can_be_replanned(engine):
    incident, plan = plan_for(engine)
    engine.approve(plan['id'])
    m = next(m for m in engine.state['missions'] if m['crewId'] == 'A09')
    with pytest.raises(DomainError, match='เหตุผล'): engine.mission_action(m['id'], 'reject')
    engine.mission_action(m['id'], 'reject', 'ไม่พร้อมทำงาน')
    assert engine._get('crew', 'A09')['status'] != 'reserved'
    plans, _, _ = engine.proposals(incident['id'])
    assert plans
    assert 'A09' not in plans[0]['assignments'][0]['crewIds']
    engine.approve(plans[0]['id'])

def test_scheduled_what_if_does_not_mutate_live_world(engine):
    i = engine.incident('fire', delay=300)
    before = engine._get('gates', 'B3')['closed']
    snapshot = engine.snapshot(10)
    assert snapshot['forecast']['scheduledIncidents'] == 1
    assert snapshot['forecast']['blockedTasks'] > 0
    assert engine._get('gates', 'B3')['closed'] == before == False
    with pytest.raises(DomainError, match='ยังไม่เกิด'): engine.proposals(i['id'])
    engine.advance(300)
    assert engine._get('gates', 'B3')['closed']
    assert engine._get('incidents', i['id'])['status'] == 'active'

def test_state_and_events_survive_restart(tmp_path):
    path = tmp_path / 'state.db'
    e = Engine(path); i, p = plan_for(e); e.approve(p['id']); e.simulation('play')
    original = e.snapshot(); e.db.close()
    restored = Engine(path).snapshot()
    assert restored['runId'] == original['runId']
    assert restored['missions'] == original['missions']
    assert restored['eventSeq'] == original['eventSeq']
    assert restored['playing'] is False

def test_normal_roster_tasks_make_progress(engine):
    engine.advance(1200)
    assert engine._get('tasks', 'T421')['status'] == 'completed'
    assert engine._get('tasks', 'C421')['status'] == 'completed'

def test_optimizer_never_double_books_resources_across_incidents(engine):
    _, plan = plan_for(engine, 'injury')
    engine.approve(plan['id'])
    reserved = {m['crewId'] for m in engine.state['missions']}
    incident = engine.incident('fire')
    plans, _, _ = engine.proposals(incident['id'])
    assert plans
    assert not reserved.intersection(cid for a in plans[0]['assignments'] for cid in a['crewIds'])
