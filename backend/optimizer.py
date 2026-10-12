"""CP-SAT allocation on a finite horizon; all recommendations remain advisory."""
import uuid
from ortools.sat.python import cp_model
from .routing import route
from .forecast import forecast, TERMINAL

def reservations(state, exclude_tasks=()):
    missions = [m for m in state['missions'] if m['status'] not in TERMINAL and not (m['taskId'] in exclude_tasks and m['kind'] == 'response')]
    return {m['crewId'] for m in missions}, {g for m in missions for g in m['gseIds']}

def eligible(state, crew, task, occupied, targets):
    now = state['now']
    if crew.get('routineTravel'): return None, 'กำลังเดินทางไปงานประจำ'
    if any(m['crewId'] == crew['id'] and m['status'] == 'rejected' and m['taskId'] == task['id'] for m in state['missions']): return None, 'ปฏิเสธ mission ในเหตุการณ์นี้'
    if crew['status'] == 'unavailable': return None, 'ไม่พร้อมทำงาน'
    if crew['id'] in occupied: return None, 'มี mission ที่ถูกจองไว้แล้ว'
    if not set(task['requiredSkills']) <= set(crew['skills']): return None, 'ทักษะ / คุณสมบัติไม่ตรง'
    if crew['certValidUntil'] <= now: return None, 'คุณสมบัติหมดอายุ'
    if task['zone'].startswith('B') and task['zone'] not in crew['allowedZones']: return None, 'ไม่มีสิทธิ์เข้าพื้นที่'
    r = route(state, crew['zone'], task['zone'], 'fire_response' in task['requiredSkills'])
    if r is None: return None, 'ไม่มีเส้นทางที่อนุญาต'
    release, backfill = now, None
    old = next((t for t in state['tasks'] if t['id'] == crew['currentTaskId'] and t['status'] == 'in_progress'), None)
    if old and old['id'] not in targets:
        if not old['interruptible']:
            release = max(now, old['actualStart'] + old['duration'])
        else:
            available = []
            for b in state['crew']:
                if b['id'] == crew['id'] or b['id'] in occupied or b['status'] != 'available' or b['currentTaskId']: continue
                if not set(old['requiredSkills']) <= set(b['skills']): continue
                if b['certValidUntil'] < now + old['duration'] or b['shiftEnd'] < now + old['duration']: continue
                if old['zone'].startswith('B') and old['zone'] not in b['allowedZones']: continue
                br = route(state, b['zone'], old['zone'])
                if not br: continue
                if any(t['id'] not in targets and t['status'] == 'scheduled' and b['id'] in t['assignedCrew'] and t['earliest'] < now + br['seconds'] + max(0, old['actualStart'] + old['duration'] - now) + 240 for t in state['tasks']): continue
                available.append((br['seconds'], b['workload'], b['id'], br))
            if not available: return None, 'งานเดิมยังไม่มีผู้รับช่วงที่เหมาะสม'
            _, _, bid, br = min(available)
            release = now + br['seconds']
            backfill = {'crewId': bid, 'taskId': old['id'], 'route': br, 'origin': next(c['zone'] for c in state['crew'] if c['id'] == bid)}
    finish = max(task['earliest'], release + r['seconds']) + task['duration']
    if finish > task['deadline']: return None, 'งานเดิม / เวลาเดินทางทำให้ไม่ทัน deadline'
    if finish > min(crew['shiftEnd'], crew['certValidUntil']): return None, 'เกินกะหรืออายุคุณสมบัติ'
    for nxt in state['tasks']:
        if nxt['id'] in targets or nxt['status'] != 'scheduled' or crew['id'] not in nxt['assignedCrew']: continue
        onward = route(state, task['zone'], nxt['zone'])
        if not onward or finish + onward['seconds'] > nxt['earliest']: return None, 'ชนกับงานที่นัดไว้ถัดไป'
    member = {'crewId': crew['id'], 'name': crew['name'], 'role': crew['role'], 'skills': crew['skills'],
              'origin': crew['zone'], 'previousTaskId': old['id'] if old else None,
              'previousTask': old['title'] if old else 'พร้อมรับงาน / ไม่มีงานที่ต้องส่งต่อ',
              'releaseAt': release, 'route': r, 'backfill': backfill, 'workload': crew['workload']}
    return member, None

def generate(state, incident):
    task_ids = incident['taskIds']
    tasks = [t for t in state['tasks'] if t['id'] in task_ids and t['status'] != 'completed']
    if not tasks: return [], []
    occupied, goccupied = reservations(state, task_ids)
    model, xs, members, costs, rejected = cp_model.CpModel(), {}, {}, [], []
    starts = {t['id']: model.new_int_var(state['now'], max(state['now'], t['deadline']), 'start_' + t['id']) for t in tasks}
    for t in tasks:
        model.add(starts[t['id']] >= t['earliest'])
        model.add(starts[t['id']] + t['duration'] <= t['deadline'])
        ids = []
        for c in state['crew']:
            member, reason = eligible(state, c, t, occupied, task_ids)
            if reason:
                rejected.append({'crewId': c['id'], 'name': c['name'], 'taskId': t['id'], 'reason': reason})
                continue
            var = model.new_bool_var(f"{t['id']}_{c['id']}")
            xs[(t['id'], c['id'])], members[(t['id'], c['id'])] = var, member
            model.add(starts[t['id']] >= member['releaseAt'] + member['route']['seconds']).only_enforce_if(var)
            model.add(starts[t['id']] + t['duration'] <= min(c['shiftEnd'], c['certValidUntil'])).only_enforce_if(var)
            for commitment in state['tasks']:
                if commitment['id'] not in task_ids and commitment['status'] == 'scheduled' and c['id'] in commitment['assignedCrew']:
                    onward = route(state, t['zone'], commitment['zone'])
                    if onward: model.add(starts[t['id']] + t['duration'] + onward['seconds'] <= commitment['earliest']).only_enforce_if(var)
            ids.append(var)
            cost = member['route']['seconds'] + c['workload'] * 2 + (80 if c['id'] not in t['assignedCrew'] else 0) + (40 if member['backfill'] else 0)
            costs.append(cost * var)
        if len(ids) < t['minStaff']: return [], rejected
        model.add(sum(ids) == t['minStaff'])
    for c in state['crew']:
        model.add(sum(v for (tid, cid), v in xs.items() if cid == c['id']) <= 1)
        needs = [v for key, v in xs.items() if members[key]['backfill'] and members[key]['backfill']['crewId'] == c['id']]
        # The relief crew cannot also be sent on the incident, or relieve two people.
        if needs: model.add(sum(needs) + sum(v for (tid, cid), v in xs.items() if cid == c['id']) <= 1)
    ys, goptions = {}, {}
    for t in tasks:
        if not t['gseType']: continue
        valid = []
        for g in state['gse']:
            if g['type'] != t['gseType'] or g['status'] == 'broken' or g['id'] in goccupied: continue
            r = route(state, g['zone'], t['zone'], 'fire_response' in t['requiredSkills'])
            if not r or max(t['earliest'], state['now'] + r['seconds']) + t['duration'] > t['deadline']: continue
            # Equipment already needed by another running or overlapping task is unavailable.
            if any(other['id'] not in task_ids and other['status'] not in ('completed', 'suspended', 'blocked') and g['id'] in other['gseIds'] and max(other['earliest'], state['now']) < t['deadline'] and other['earliest'] + other['duration'] > state['now'] for other in state['tasks']): continue
            var = model.new_bool_var(f"g_{t['id']}_{g['id']}")
            ys[(t['id'], g['id'])] = var; goptions[(t['id'], g['id'])] = r
            model.add(starts[t['id']] >= state['now'] + r['seconds']).only_enforce_if(var)
            valid.append(var); costs.append((r['seconds'] + (0 if g['id'] in t['gseIds'] else 30)) * var)
        if not valid: return [], rejected
        model.add(sum(valid) == 1)
    for g in state['gse']: model.add(sum(v for (tid, gid), v in ys.items() if gid == g['id']) <= 1)
    model.minimize(sum(costs))
    baseline, plans = forecast(state), []
    for index in range(3):
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 1
        solver.parameters.num_search_workers = 1
        solver.parameters.random_seed = 7
        if solver.solve(model) not in (cp_model.OPTIMAL, cp_model.FEASIBLE): break
        assignments, selected = [], []
        for t in tasks:
            chosen = [key for key, var in xs.items() if key[0] == t['id'] and solver.value(var)]
            gear = [key for key, var in ys.items() if key[0] == t['id'] and solver.value(var)]
            assignments.append({'taskId': t['id'], 'title': t['title'], 'zone': t['zone'], 'originalCrewIds': t['assignedCrew'][:], 'crewIds': [key[1] for key in chosen],
                                'members': [members[key] for key in chosen], 'gseIds': [key[1] for key in gear],
                                'equipmentRoutes': [{'gseId': key[1], 'route': goptions[key]} for key in gear]})
            selected += [xs[k] for k in chosen] + [ys[k] for k in gear]
        plan = {'id': uuid.uuid4().hex[:12], 'incidentId': incident['id'], 'revision': state['revision'], 'status': 'proposed',
                'rank': index + 1, 'assignments': assignments, 'cost': round(solver.objective_value),
                'source': 'optimizer', 'rationale': 'ผ่านข้อจำกัดทักษะ เวลา ทรัพยากร และผู้รับช่วงงานเดิม',
                'tradeoffs': 'ตรวจสอบผลต่อ timeline ก่อนอนุมัติ', 'before': baseline, 'after': None}
        plan['after'] = forecast(state, plan=plan)
        plans.append(plan)
        model.add(sum(selected) <= len(selected) - 1)
    return plans, rejected
