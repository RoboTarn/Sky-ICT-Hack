from copy import deepcopy
from .routing import route

TERMINAL = {'completed', 'rejected', 'cancelled'}

def apply_projection(state, plan):
    world = deepcopy(state)
    for a in plan['assignments']:
        target = next(t for t in world['tasks'] if t['id'] == a['taskId'])
        target['assignedCrew'] = a['crewIds']
        target['gseIds'] = a['gseIds']
        for member in a['members']:
            if member.get('backfill'):
                old = next(t for t in world['tasks'] if t['id'] == member['previousTaskId'])
                old['assignedCrew'] = [member['backfill']['crewId'] if c == member['crewId'] else c for c in old['assignedCrew']]
                crew = next(c for c in world['crew'] if c['id'] == member['crewId'])
                crew['zone'] = member['origin']
                crew['currentTaskId'] = None
            target['earliest'] = max(target['earliest'], member['releaseAt'] + member['route']['seconds'])
    return world

def forecast(state, horizon=30, plan=None):
    if plan: state = apply_projection(state, plan)
    now = state['now']
    crew = {c['id']: c for c in state['crew']}
    gse = {g['id']: g for g in state['gse']}
    ready = {c: now for c in crew}
    positions = {c: data.get('routineTravel', {}).get('destination', data['zone']) for c, data in crew.items()}
    ready.update({c: max(now, data['routineTravel']['etaAt']) for c, data in crew.items() if data.get('routineTravel')})
    gready = {g: now for g in gse}
    gpositions = {g: data.get('destination', data['zone']) for g, data in gse.items()}
    gready.update({g: max(now, data['etaAt']) for g, data in gse.items() if data.get('destination')})
    ends = {t['id']: t['actualEnd'] or now for t in state['tasks'] if t['status'] == 'completed'}
    rows = []
    ordered = sorted(state['tasks'], key=lambda t: (t['status'] != 'in_progress', t['earliest']))
    pending = ordered[:]
    # Topological scheduling also handles multi-step turnaround tasks.
    for _ in range(len(ordered) + 1):
        progress = False
        for t in pending[:]:
            if t['status'] == 'completed': pending.remove(t); progress = True; continue
            if any(d not in ends for d in t['dependencies']): continue
            staff = t['assignedCrew']
            blocked = t['status'] in ('suspended', 'blocked') or len(staff) < t['minStaff']
            blocked |= any(c not in crew or crew[c]['status'] == 'unavailable' for c in staff)
            blocked |= any(g not in gse or gse[g]['status'] == 'broken' for g in t['gseIds'])
            if t['gseType'] and not t['gseIds']: blocked = True
            arrivals = []
            for cid in staff:
                r = route(state, positions[cid], t['zone'], 'fire_response' in t['requiredSkills'])
                if r is None: blocked = True
                else: arrivals.append(ready[cid] + r['seconds'])
            equipment_arrivals = []
            for gid in t['gseIds']:
                r = route(state, gpositions[gid], t['zone'], 'fire_response' in t['requiredSkills'])
                if r is None: blocked = True
                else: equipment_arrivals.append(gready[gid] + r['seconds'])
            start = max([now, t['earliest'], *arrivals, *equipment_arrivals, *(ends[d] for d in t['dependencies'])])
            if t['status'] == 'in_progress':
                start = t['actualStart'] if t['actualStart'] is not None else now
            # Active missions need ACK and handoff; their pending time is still part of the estimate.
            mission_members = [m for m in state['missions'] if m['taskId'] == t['id'] and m['kind'] == 'response' and m['status'] not in TERMINAL]
            if t['status'] != 'in_progress' and mission_members:
                start = max(start, *(max(now, m['releaseAt']) + (m['route']['seconds'] if m['status'] in ('assigned', 'accepted') else max(0, m.get('etaAt', now) - now)) for m in mission_members))
            end = max(now, start + t['duration'])
            if blocked: end = max(end, t['deadline'] + 600)
            slack = t['deadline'] - end
            ends[t['id']] = end
            for cid in staff: ready[cid], positions[cid] = end, t['zone']
            for gid in t['gseIds']: gready[gid], gpositions[gid] = end, t['zone']
            if t['earliest'] <= now + horizon * 60:
                rows.append({'taskId': t['id'], 'title': t['title'], 'flightId': t['flightId'], 'zone': t['zone'],
                             'start': start, 'end': end, 'deadline': t['deadline'], 'slack': slack,
                             'risk': 'blocked' if blocked else 'high' if slack < 0 else 'medium' if slack <= 300 else 'low',
                             'crewIds': staff, 'status': t['status'], 'priority': t['priority']})
            pending.remove(t); progress = True
        if not progress: break
    return {'horizon': horizon, 'rows': rows, 'lateTasks': sum(r['slack'] < 0 for r in rows),
            'riskFlights': len({r['flightId'] for r in rows if r['slack'] < 0 and r['flightId']}),
            'blockedTasks': sum(r['risk'] == 'blocked' for r in rows), 'simulated': True}
