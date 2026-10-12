from backend.engine import Engine

def test_certificates_cover_common_team_start_not_just_individual_arrival():
    e = Engine(':memory:')
    incident = e.incident('flight_delay')
    task = e._get('tasks', 'T421')
    task.update(earliest=0, duration=120, deadline=1000)
    fast = e._get('crew', 'A09')
    fast.update(zone='B6', certValidUntil=200)
    plans, _, _ = e.proposals(incident['id'])
    assert plans
    for plan in plans:
        assignment = plan['assignments'][0]
        end = max([task['earliest'], *(m['releaseAt'] + m['route']['seconds'] for m in assignment['members'])]) + task['duration']
        assert all(end <= e._get('crew', cid)['certValidUntil'] for cid in assignment['crewIds'])

def test_future_fire_does_not_suspend_work_finished_before_event():
    e = Engine(':memory:')
    e.incident('fire', delay=600)
    preview = e.snapshot(20)
    original = next(r for r in preview['forecast']['rows'] if r['taskId'] == 'T219')
    assert original['risk'] != 'blocked'
    assert e._get('tasks', 'T219')['status'] == 'in_progress'
    assert not e._get('gates', 'B3')['closed']
