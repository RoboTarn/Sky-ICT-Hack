import json
import sqlite3
import threading
import uuid
import time
from copy import deepcopy
from pathlib import Path
from .domain import seed, SCENARIOS
from .forecast import forecast, TERMINAL
from .optimizer import generate, eligible, reservations
from .routing import route

class DomainError(Exception):
    def __init__(self, message, status=409):
        self.message, self.status = message, status
        super().__init__(message)

def activate(world, incident):
    """Apply an incident to either the live world or a disposable what-if world."""
    kind, now, zone = incident['type'], world['now'], incident['zone']
    incident['status'] = 'active'
    target = next(t for t in world['tasks'] if t['id'] == 'T421')
    incident['taskIds'] = ['T421']
    if kind == 'flight_delay':
        f = next(f for f in world['flights'] if f['id'] == 'TG312'); f['delay'] += 1080; f['etd'] += 1080
        old = next(t for t in world['tasks'] if t['id'] == 'T312')
        if old['status'] != 'completed': old['duration'] += 1080
    elif kind == 'gate_change':
        incident['zone'] = 'B5'
        next(f for f in world['flights'] if f['id'] == 'TG421')['gate'] = 'B5'
        for t in world['tasks']:
            if t['flightId'] == 'TG421' and t['status'] != 'completed': t['zone'] = 'B5'
        for m in world['missions']:
            if m['taskId'] in ('T421', 'C421', 'D421') and m['status'] not in TERMINAL:
                m['status'] = 'blocked'; m['exception'] = 'Gate เปลี่ยน ต้องรอ commander ยืนยันเส้นทางใหม่'
    elif kind == 'staff_absence':
        next(c for c in world['crew'] if c['id'] == 'A08')['status'] = 'unavailable'
    elif kind == 'gse_failure':
        next(g for g in world['gse'] if g['id'] == 'BL01')['status'] = 'broken'
        for m in world['missions']:
            if 'BL01' in m['gseIds'] and m['status'] not in TERMINAL: m['status'] = 'blocked'; m['exception'] = 'อุปกรณ์ขัดข้อง'
    elif kind in ('injury', 'fire'):
        incident['taskIds'] = []
        definitions = [('coord', 'ประสานงานและรายงานจุดเกิดเหตุ', ['coordination'], 1, None, zone, 180),
                       ('aid', 'สนับสนุนทีมปฐมพยาบาล', ['first_aid'], 1, None, zone, 240),
                       ('med', 'ทีมตอบสนองเหตุบาดเจ็บ', ['medical'], 1, 'medical_vehicle', zone, 300)]
        if kind == 'fire':
            next(g for g in world['gates'] if g['id'] == zone)['closed'] = True
            for t in world['tasks']:
                if t['zone'] == zone and t['status'] != 'completed':
                    t['remainingDuration'] = max(30, t['duration'] - max(0, now - (t['actualStart'] or now)))
                    t['status'] = 'suspended'
                    for cid in t['assignedCrew']:
                        c = next(c for c in world['crew'] if c['id'] == cid)
                        c['zone'], c['currentTaskId'], c['status'] = 'HUB', None, 'available'
            for m in world['missions']:
                if m['zone'] == zone and m['status'] not in TERMINAL:
                    m['status'], m['exception'] = 'blocked', 'พื้นที่ปิด หยุดเดินทางและรอแผนใหม่'
            definitions = [('coord', 'ประสานงานจากจุดปลอดภัย', ['coordination'], 1, None, 'J' + zone[1:], 180),
                           ('fire', 'ทีมตอบสนองควัน / ไฟ', ['fire_response'], 2, 'fire_vehicle', zone, 300)]
        for code, title, skills, count, gtype, dest, duration in definitions:
            tid = f"E-{incident['id']}-{code}"
            incident['taskIds'].append(tid)
            world['tasks'].append({'id': tid, 'flightId': None, 'title': title, 'zone': dest, 'earliest': now,
                                   'duration': duration, 'deadline': now + 1200, 'requiredSkills': skills,
                                   'minStaff': count, 'assignedCrew': [], 'gseIds': [], 'gseType': gtype,
                                   'status': 'scheduled', 'actualStart': None, 'actualEnd': None,
                                   'interruptible': False, 'requiresCoverage': True, 'dependencies': [],
                                   'priority': 'critical', 'incidentId': incident['id']})
    target['incidentId'] = incident['id'] if kind not in ('injury', 'fire') else target['incidentId']

class Engine:
    def __init__(self, db_path, database_url=None):
        self.store = None
        if database_url:
            from .storage import PostgresState
            self.state = seed()
            self.store = PostgresState(self, database_url)
            self.lock = self.store
            self.db = None
            with self.lock: pass
            return
        self.lock = threading.RLock()
        if str(db_path) != ':memory:': Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(db_path), check_same_thread=False)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS snapshots (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, payload TEXT NOT NULL)')
        row = self.db.execute('SELECT payload FROM snapshots WHERE id=1').fetchone()
        self.state = json.loads(row[0]) if row else seed()
        self.state['playing'] = False
        if self.state['ai']['status'] == 'analyzing':
            self.state['ai'] = {'status': 'error', 'source': 'optimizer', 'message': 'คำขอเดิมถูกหยุดเมื่อ server ปิด กรุณาวิเคราะห์ใหม่'}
        self._save()

    def _save(self):
        if self.store:
            self.store.save(self.state)
            return
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO snapshots VALUES (1, ?)', (json.dumps(self.state, ensure_ascii=False),))

    def _event(self, title, kind='update', bump=True, **data):
        if bump: self.state['revision'] += 1
        event = {'title': title, 'type': kind, 'time': self.state['now'], 'runId': self.state['runId'], **data}
        if self.store:
            event['seq'] = self.store.event(event)
            self.state['events'] = (self.state['events'] + [event])[-60:]
            self._save()
            return
        with self.db:
            cursor = self.db.execute('INSERT INTO events(run_id,payload) VALUES (?,?)', (self.state['runId'], json.dumps(event, ensure_ascii=False)))
            event['seq'] = cursor.lastrowid
            self.state['events'] = (self.state['events'] + [event])[-60:]
            self.db.execute('INSERT OR REPLACE INTO snapshots VALUES (1, ?)', (json.dumps(self.state, ensure_ascii=False),))

    def _get(self, collection, id):
        obj = next((item for item in self.state[collection] if item['id'] == id), None)
        if not obj: raise DomainError('ไม่พบรายการนี้ในรอบจำลองปัจจุบัน', 404)
        return obj

    def snapshot(self, horizon=30):
        with self.lock:
            view = deepcopy(self.state)
            scheduled = [i for i in view['incidents'] if i['status'] == 'scheduled' and i['scheduledAt'] <= view['now'] + horizon * 60]
            prediction = forecast(view, horizon)
            if scheduled:
                # Replay the same simulator in an isolated, in-memory world so future
                # incidents occur at their specified time, after intervening work.
                projection = Engine(':memory:')
                try:
                    projection.state = deepcopy(view)
                    elapsed = max(i['scheduledAt'] for i in scheduled) - view['now']
                    projection.advance(elapsed)
                    later = forecast(projection.state, max(0, horizon - elapsed / 60))
                    rows = {r['taskId']: r for r in prediction['rows']}
                    rows.update({r['taskId']: r for r in later['rows']})
                    prediction['rows'] = list(rows.values())
                    prediction['lateTasks'] = sum(r['slack'] < 0 for r in rows.values())
                    prediction['riskFlights'] = len({r['flightId'] for r in rows.values() if r['slack'] < 0 and r['flightId']})
                    prediction['blockedTasks'] = sum(r['risk'] == 'blocked' for r in rows.values())
                finally: projection.db.close()
            view['forecast'] = prediction
            view['forecast']['scheduledIncidents'] = len(scheduled)
            view['scenarios'] = [{'id': k, **v} for k, v in SCENARIOS.items()]
            view['eventSeq'] = (view['events'][-1]['seq'] if view['events'] else 0) if self.store else self.db.execute('SELECT COALESCE(MAX(seq),0) FROM events').fetchone()[0]
            for p in view['plans']:
                if p['status'] == 'proposed' and p['revision'] != view['revision']: p['status'] = 'stale'
            return view

    def incident(self, type, zone='B6', delay=0):
        with self.lock:
            if type not in SCENARIOS: raise DomainError('ไม่รองรับสถานการณ์นี้', 422)
            if zone not in {g['id'] for g in self.state['gates']}: raise DomainError('Gate ไม่ถูกต้อง', 422)
            if any(i['type'] == type and i['status'] in ('active', 'scheduled', 'dispatched') for i in self.state['incidents']):
                raise DomainError('มีสถานการณ์ชนิดนี้อยู่แล้ว กรุณาจัดการหรือเริ่มรอบใหม่')
            incident = {'id': uuid.uuid4().hex[:8], 'type': type, 'label': SCENARIOS[type]['label'],
                        'description': SCENARIOS[type]['description'], 'severity': SCENARIOS[type]['severity'],
                        'zone': 'B3' if type == 'fire' else zone, 'createdAt': self.state['now'],
                        'scheduledAt': self.state['now'] + delay, 'status': 'scheduled' if delay else 'active', 'taskIds': [], 'rejectedCandidates': []}
            self.state['incidents'].append(incident)
            if not delay: activate(self.state, incident)
            self._event(f"{incident['label']} · {incident['zone']}" + (' (กำหนดล่วงหน้า)' if delay else ''), 'incident')
            return deepcopy(incident)

    def proposals(self, incident_id):
        with self.lock:
            i = self._get('incidents', incident_id)
            if i['status'] == 'scheduled': raise DomainError('เหตุการณ์ยังไม่เกิด ดูผล What-if ใน Forecast หรือเดินเวลาไปถึงเหตุการณ์')
            if i['status'] == 'resolved': raise DomainError('เหตุการณ์นี้จัดการเสร็จแล้ว')
            plans, rejected = generate(self.state, i)
            i['rejectedCandidates'] = rejected
            self.state['plans'] = [p for p in self.state['plans'] if p['incidentId'] != i['id'] or p['status'] not in ('proposed', 'rejected')][-20:] + plans
            self.state['ai'] = {'status': 'analyzing' if plans else 'no_plan', 'source': 'optimizer',
                                'message': 'กำลังส่งแผนที่ผ่านข้อจำกัดให้ Typhoon' if plans else 'ไม่พบแผนที่ผ่านข้อจำกัด กรุณาปรับทรัพยากรหรือเริ่มรอบใหม่'}
            i['analysis'] = {**self.state['ai'], 'revision': self.state['revision'], 'leaseUntil': time.time() + 65}
            self._event('สร้างแผน CP-SAT ' + str(len(plans)) + ' ทางเลือก', 'proposal', False)
            return deepcopy(plans), deepcopy(i), self.state['revision']

    def claim_recovery(self):
        """One durable lease per active incident; no analysis calls from browser state effects."""
        with self.lock:
            active = sorted((i for i in self.state['incidents'] if i['status'] == 'active'),
                            key=lambda i: i['severity'] != 'critical')
            for i in active:
                analysis = i.get('analysis', {})
                if analysis.get('status') == 'analyzing' and analysis.get('leaseUntil', 0) > time.time():
                    continue
                if analysis.get('revision') == self.state['revision'] and analysis.get('status') in ('ready', 'error', 'no_plan', 'declined'):
                    continue
                return self.proposals(i['id'])
            return None

    def ai_result(self, result, plans, revision):
        with self.lock:
            ids = {p['id'] for p in plans}
            if not ids.intersection(p['id'] for p in self.state['plans']): return
            incident = self._get('incidents', plans[0]['incidentId'])
            if self.state['revision'] != revision:
                self.state['ai'] = {'status': 'stale', 'source': 'optimizer', 'message': 'สถานะเปลี่ยนระหว่างวิเคราะห์ กรุณาสร้างแผนใหม่'}
                incident['analysis'] = {**self.state['ai'], 'revision': revision, 'leaseUntil': 0}
                self._event('แผนต้องตรวจสอบใหม่หลังสถานะเปลี่ยน', 'ai', False)
                return
            self.state['ai'] = result
            incident['analysis'] = {**result, 'revision': revision, 'leaseUntil': 0}
            for p in self.state['plans']:
                if p['id'] in ids and p['id'] == result.get('planId'):
                    p.update(source=result['source'], rationale=result['message'], tradeoffs=result.get('tradeoffs', ''), explanationSource=result.get('explanationSource', 'optimizer'), recommended=True)
            self._event('Typhoon วิเคราะห์แผนแล้ว' if result['status'] == 'ready' else 'ใช้แผนจาก optimizer: Typhoon ไม่พร้อมใช้งาน', 'ai', False)

    def reject_plan(self, plan_id):
        with self.lock:
            plan = self._get('plans', plan_id)
            if plan['status'] != 'proposed': raise DomainError('แผนนี้ไม่อยู่ในสถานะรออนุมัติ')
            plan['status'] = 'rejected'; self._event('Commander ปฏิเสธแผน ' + plan_id, 'plan', False)
            if not any(p['incidentId'] == plan['incidentId'] and p['status'] == 'proposed' for p in self.state['plans']):
                self._get('incidents', plan['incidentId'])['analysis'] = {'status': 'declined', 'revision': self.state['revision'], 'source': 'optimizer', 'message': 'ปฏิเสธทุกแผนแล้ว เลือกลองใหม่เมื่อต้องการ'}
                self._save()

    def approve(self, plan_id):
        with self.lock:
            p = self._get('plans', plan_id)
            if p['status'] != 'proposed' or p['revision'] != self.state['revision']: raise DomainError('แผนล้าสมัยหรือถูกใช้แล้ว กรุณาวิเคราะห์ใหม่')
            targets = [a['taskId'] for a in p['assignments']]
            occupied, goccupied = reservations(self.state)
            own = [m for m in self.state['missions'] if m['taskId'] in targets and m['kind'] == 'response' and m['status'] not in TERMINAL]
            occupied -= {m['crewId'] for m in own}; goccupied -= {g for m in own for g in m['gseIds']}
            fresh = {}
            for a in p['assignments']:
                task = self._get('tasks', a['taskId'])
                for member in a['members']:
                    new, reason = eligible(self.state, self._get('crew', member['crewId']), task, occupied, targets)
                    if reason: raise DomainError('แผนไม่ผ่านการตรวจล่าสุด: ' + reason)
                    if (new['backfill'] or {}).get('crewId') != (member['backfill'] or {}).get('crewId'):
                        raise DomainError('ผู้รับช่วงงานเดิมเปลี่ยนไป กรุณาสร้างแผนใหม่')
                    fresh[member['crewId']] = new
                for gid in a['gseIds']:
                    gear = self._get('gse', gid)
                    if gear['status'] == 'broken' or gid in goccupied: raise DomainError('อุปกรณ์ถูกใช้หรือไม่พร้อมแล้ว')
                    r = route(self.state, gear['zone'], task['zone'], 'fire_response' in task['requiredSkills'])
                    if not r or self.state['now'] + r['seconds'] + task['duration'] > task['deadline']: raise DomainError('อุปกรณ์เดินทางไม่ทัน deadline')
                joint_start = max([self.state['now'], task['earliest'],
                                   *(fresh[cid]['releaseAt'] + fresh[cid]['route']['seconds'] for cid in a['crewIds']),
                                   *(self.state['now'] + route(self.state, self._get('gse', gid)['zone'], task['zone'], 'fire_response' in task['requiredSkills'])['seconds'] for gid in a['gseIds'])])
                if joint_start + task['duration'] > task['deadline']: raise DomainError('ทีมและอุปกรณ์พร้อมไม่ทัน deadline')
                for cid in a['crewIds']:
                    c = self._get('crew', cid)
                    if joint_start + task['duration'] > min(c['shiftEnd'], c['certValidUntil']): raise DomainError('กะหรือคุณสมบัติไม่ครอบคลุมงานทั้งทีม')
                    for commitment in self.state['tasks']:
                        if commitment['id'] not in targets and commitment['status'] == 'scheduled' and cid in commitment['assignedCrew']:
                            onward = route(self.state, task['zone'], commitment['zone'])
                            if not onward or joint_start + task['duration'] + onward['seconds'] > commitment['earliest']: raise DomainError('แผนชนกับงานที่นัดไว้ถัดไป')
            # All validations finish before mutations: the lock and one save reserve the plan atomically.
            mission_ids = []
            for a in p['assignments']:
                task = self._get('tasks', a['taskId'])
                task['assignedCrew'], task['gseIds'] = a['crewIds'][:], a['gseIds'][:]
                if task['status'] == 'blocked': task['status'] = 'scheduled'
                for existing in own:
                    if existing['taskId'] == task['id'] and (existing['crewId'] not in a['crewIds'] or existing['gseIds'] != a['gseIds'] or existing['status'] == 'blocked'):
                        existing['status'] = 'cancelled'
                        if existing['releaseDependencyId']:
                            dependency = self._get('missions', existing['releaseDependencyId'])
                            if dependency['status'] not in TERMINAL:
                                dependency['status'] = 'cancelled'
                                backup = self._get('crew', dependency['crewId'])
                                backup['status'] = 'busy' if backup['currentTaskId'] else 'available'
                        c = self._get('crew', existing['crewId'])
                        if c['currentTaskId'] == task['id']: c['currentTaskId'] = None
                        c['status'] = 'available' if not c['currentTaskId'] else 'busy'
                for cid in a['crewIds']:
                    member = fresh[cid]
                    existing = next((m for m in own if m['taskId'] == task['id'] and m['crewId'] == cid and m['status'] not in TERMINAL), None)
                    if existing: mission_ids.append(existing['id']); continue
                    dependency = None
                    if member['backfill']:
                        backup = member['backfill']
                        relief = self._mission(backup['crewId'], self._get('tasks', backup['taskId']), p, backup['route'], backup['origin'], self.state['now'], 'handoff', [], None)
                        relief['relievesCrewId'] = cid
                        self.state['missions'].append(relief); dependency = relief['id']; mission_ids.append(relief['id'])
                        self._get('crew', backup['crewId'])['status'] = 'reserved'
                    mission = self._mission(cid, task, p, member['route'], member['origin'], member['releaseAt'], 'response', a['gseIds'], dependency)
                    mission['previousTask'], mission['previousTaskId'] = member['previousTask'], member['previousTaskId']
                    self.state['missions'].append(mission); mission_ids.append(mission['id'])
                    self._get('crew', cid)['status'] = 'reserved'
                for item in a['equipmentRoutes']:
                    gear = self._get('gse', item['gseId'])
                    gear.update(status='reserved', destination=task['zone'], etaAt=self.state['now'] + item['route']['seconds'])
            p['status'] = 'approved'; self._get('incidents', p['incidentId'])['status'] = 'dispatched'
            self._event('Commander อนุมัติแผน · ส่ง ' + str(len(mission_ids)) + ' missions', 'dispatch', planId=p['id'])
            return mission_ids

    def _mission(self, cid, task, plan, r, origin, release, kind, gse, dependency):
        instructions = ['ยืนยันตำแหน่งและรายงานตัว', 'ทำงานตามขอบเขตที่ได้รับมอบหมาย', 'รายงานผลให้ commander']
        if kind == 'handoff': instructions = ['ไปยังจุดส่งต่องาน', 'ยืนยันรับช่วงงานเดิมก่อนปล่อย crew ออกเดินทาง']
        elif task['priority'] == 'critical':
            instructions = ['รายงานตัวตามจุดที่ได้รับมอบหมาย', 'ประสานงานตาม role และคุณสมบัติของตน', 'รายงานสถานะกลับศูนย์ควบคุม']
        return {'id': uuid.uuid4().hex[:10], 'crewId': cid, 'taskId': task['id'], 'incidentId': plan['incidentId'],
                'planId': plan['id'], 'kind': kind, 'title': 'รับช่วง: ' + task['title'] if kind == 'handoff' else task['title'],
                'zone': task['zone'], 'origin': origin, 'route': r, 'releaseAt': release,
                'releaseDependencyId': dependency, 'gseIds': gse[:], 'deadline': task['deadline'],
                'status': 'assigned', 'createdAt': self.state['now'], 'checklist': instructions, 'checked': [],
                'previousTask': None, 'previousTaskId': None, 'exception': None}

    def mission_action(self, id, action, reason='', checked=None):
        with self.lock:
            m = self._get('missions', id); c = self._get('crew', m['crewId']); t = self._get('tasks', m['taskId'])
            status = m['status']; now = self.state['now']
            if status in TERMINAL: raise DomainError('Mission สิ้นสุดแล้ว')
            if action == 'check':
                if status != 'in_progress': raise DomainError('เริ่มงานก่อนยืนยัน checklist')
                if checked is None or any(i < 0 or i >= len(m['checklist']) for i in checked): raise DomainError('Checklist ไม่ถูกต้อง', 422)
                m['checked'] = sorted(set(checked)); self._event('อัปเดต checklist ' + c['id'], 'checklist', False); return deepcopy(m)
            transitions = {'accept': ('assigned', 'accepted'), 'depart': ('accepted', 'en_route'), 'arrive': ('en_route', 'arrived'), 'start': ('arrived', 'in_progress'), 'complete': ('in_progress', 'completed')}
            if action in ('reject', 'blocked'):
                if not reason.strip(): raise DomainError('กรุณาระบุเหตุผล', 422)
                if action == 'reject' and status not in ('assigned', 'accepted'): raise DomainError('เริ่มเดินทางแล้ว ใช้รายงานอุปสรรคแทน')
                m['status'], m['exception'] = ('rejected' if action == 'reject' else 'blocked'), reason.strip()[:500]
                if action == 'reject':
                    t['assignedCrew'] = [x for x in t['assignedCrew'] if x != c['id']]
                    c['status'] = 'busy' if c['currentTaskId'] else 'available'
                    dependency = next((x for x in self.state['missions'] if x['id'] == m['releaseDependencyId']), None)
                    if dependency and dependency['status'] not in TERMINAL:
                        dependency['status'] = 'cancelled'; self._get('crew', dependency['crewId'])['status'] = 'available'
                else: t['status'] = 'blocked'
                self._get('incidents', m['incidentId'])['status'] = 'active'
                self._event(c['id'] + (' ปฏิเสธ mission' if action == 'reject' else ' รายงานอุปสรรค'), 'exception', missionId=m['id'])
                return deepcopy(m)
            if action not in transitions or status != transitions[action][0]: raise DomainError('ลำดับการทำงานไม่ถูกต้อง')
            if action == 'depart':
                if now < m['releaseAt']: raise DomainError('ยังไม่ถึงเวลาที่ออกจากงานเดิมได้')
                if m['releaseDependencyId'] and self._get('missions', m['releaseDependencyId'])['status'] != 'completed': raise DomainError('ต้องรอผู้รับช่วงงานเดิมมาถึงก่อน')
                if c['currentTaskId'] and c['currentTaskId'] != t['id']:
                    old = self._get('tasks', c['currentTaskId'])
                    if old['status'] == 'in_progress': raise DomainError('งานเดิมยังไม่จบหรือยังไม่ได้ส่งต่อ')
                r = route(self.state, c['zone'], m['zone'], 'fire_response' in t['requiredSkills'])
                if not r: raise DomainError('เส้นทางถูกปิด กรุณารายงานอุปสรรค')
                m['route'], m['origin'], m['departedAt'], m['etaAt'] = r, c['zone'], now, now + r['seconds']
            if action == 'arrive':
                if now < m['etaAt']: raise DomainError('ยังเดินทางไม่ถึงจุดหมาย กรุณาเดินเวลาจำลอง')
                self._arrival(m)
                self._event(c['id'] + ' ถึง ' + m['zone'], 'mission'); return deepcopy(m)
            if action == 'start':
                if not set(t['requiredSkills']) <= set(c['skills']) or now + t['duration'] > min(c['certValidUntil'], c['shiftEnd']): raise DomainError('คุณสมบัติหรือกะทำงานไม่ครอบคลุมงานแล้ว กรุณารายงานอุปสรรค')
                if not route(self.state, c['zone'], t['zone'], 'fire_response' in t['requiredSkills']): raise DomainError('พื้นที่ปิด ไม่สามารถเริ่มงานได้')
                group = [x for x in self.state['missions'] if x['taskId'] == t['id'] and x['kind'] == 'response' and x['status'] not in TERMINAL]
                if len(group) < t['minStaff'] or any(x['status'] not in ('arrived', 'in_progress') for x in group): raise DomainError('ต้องรอทีมครบและรายงานตัวก่อนเริ่มงาน')
                if any(now + t['duration'] > min(self._get('crew', x['crewId'])['certValidUntil'], self._get('crew', x['crewId'])['shiftEnd']) for x in group): raise DomainError('คุณสมบัติหรือกะของสมาชิกในทีมไม่ครอบคลุมงาน')
                if any(self._get('tasks', d)['status'] != 'completed' for d in t['dependencies']): raise DomainError('งานก่อนหน้ายังไม่เสร็จ')
                if any(self._get('gse', g)['zone'] != t['zone'] or self._get('gse', g)['status'] == 'broken' for g in m['gseIds']): raise DomainError('อุปกรณ์ยังมาไม่ถึงหรือไม่พร้อม')
                if now < t['earliest']: raise DomainError('ยังไม่ถึงเวลาเริ่มงาน')
                if t['status'] != 'in_progress': t['actualStart'], t['status'] = now, 'in_progress'
                c['currentTaskId'] = t['id']
            if action == 'complete':
                if len(m['checked']) != len(m['checklist']): raise DomainError('ยืนยัน checklist ให้ครบก่อนจบงาน')
                if now < t['actualStart'] + t['duration']: raise DomainError('ระยะเวลางานยังไม่ครบ กรุณาเดินเวลาจำลอง')
                c['currentTaskId'], c['status'] = None, 'available'; c['workload'] = min(100, c['workload'] + 8)
            m['status'] = transitions[action][1]
            if action != 'complete': c['status'] = 'mission'
            if action == 'complete':
                group = [x for x in self.state['missions'] if x['taskId'] == t['id'] and x['kind'] == 'response' and x['status'] not in ('cancelled', 'rejected')]
                if all(x['status'] == 'completed' for x in group):
                    t['status'], t['actualEnd'] = 'completed', now
                    for gid in t['gseIds']: self._get('gse', gid)['status'] = 'available'
                self._resolve(m['incidentId'])
            self._event(c['id'] + ' · ' + {'accept': 'รับ mission', 'depart': 'ออกเดินทาง', 'start': 'เริ่มงาน', 'complete': 'เสร็จงาน'}[action], 'mission', missionId=m['id'])
            return deepcopy(m)

    def _arrival(self, m):
        c = self._get('crew', m['crewId']); c['zone'] = m['zone']; m['status'] = 'arrived'
        if m['kind'] == 'handoff':
            old = self._get('tasks', m['taskId']); source = self._get('crew', m['relievesCrewId'])
            if old['status'] == 'in_progress':
                old['assignedCrew'] = [c['id'] if cid == source['id'] else cid for cid in old['assignedCrew']]
                c['currentTaskId'], c['status'] = old['id'], 'busy'
            else: c['currentTaskId'], c['status'] = None, 'available'
            if source['currentTaskId'] == old['id']: source['currentTaskId'] = None
            m['status'] = 'completed'
        else: c['currentTaskId'], c['status'] = m['taskId'], 'mission'

    def _resolve(self, incident_id):
        i = self._get('incidents', incident_id)
        if all(self._get('tasks', tid)['status'] == 'completed' for tid in i['taskIds']):
            i['status'] = 'resolved'
            if i['type'] == 'fire':
                self._get('gates', i['zone'])['closed'] = False
                for t in self.state['tasks']:
                    if t['zone'] == i['zone'] and t['status'] == 'suspended':
                        t.update(status='scheduled', earliest=self.state['now'], actualStart=None, duration=t.get('remainingDuration', t['duration']))

    def simulation(self, action, seconds=60, speed=1):
        with self.lock:
            self._wall_clock()
            if action == 'reset':
                self.state = seed(); self.state['wallClock'] = time.time(); self._event('เริ่มรอบจำลองใหม่', 'simulation'); return
            if action in ('play', 'pause'):
                self.state['playing'] = action == 'play'; self._event('เริ่มเวลา' if action == 'play' else 'หยุดเวลา', 'simulation', False); return
            if action == 'speed':
                if speed not in (1, 4): raise DomainError('รองรับความเร็ว 1x และ 4x', 422)
                self.state['speed'] = speed; self._save(); return
            if action != 'advance' or seconds < 1 or seconds > 1800: raise DomainError('เวลาเดินจำลองต้องอยู่ในช่วง 1-1800 วินาที', 422)
            self.advance(seconds)

    def sync_clock(self):
        with self.lock: self._wall_clock()

    def _wall_clock(self):
        if not self.store: return
        now = time.time()
        last = self.state.get('wallClock', now)
        if self.state['playing']:
            elapsed = max(0, min(1800, int(now - last)))
            if elapsed:
                self.advance(elapsed * self.state['speed'])
                self.state['wallClock'] = last + elapsed
                self._save()
        else:
            self.state['wallClock'] = now
            self._save()

    def advance(self, seconds):
        with self.lock:
            remaining = seconds
            while remaining:
                step = min(remaining, 15); remaining -= step; self.state['now'] += step
                for i in self.state['incidents']:
                    if i['status'] == 'scheduled' and i['scheduledAt'] <= self.state['now']:
                        activate(self.state, i); self._event('เหตุการณ์ล่วงหน้าเริ่ม: ' + i['label'], 'incident')
                for gear in self.state['gse']:
                    if gear.get('destination') and gear.get('etaAt', 10**9) <= self.state['now'] and gear['status'] != 'broken':
                        gear['zone'] = gear.pop('destination'); gear.pop('etaAt', None)
                for c in self.state['crew']:
                    travel = c.get('routineTravel')
                    if travel and travel['etaAt'] <= self.state['now']:
                        c['zone'] = travel['destination']; c.pop('routineTravel', None)
                        if c['status'] == 'transit': c['status'] = 'available'
                for m in self.state['missions']:
                    if m['status'] == 'en_route' and m['etaAt'] <= self.state['now']:
                        self._arrival(m); self._event(m['crewId'] + ' ถึง ' + m['zone'] + (' · ส่งต่องานแล้ว' if m['kind'] == 'handoff' else ''), 'mission')
                response_tasks = {m['taskId'] for m in self.state['missions'] if m['kind'] == 'response' and m['status'] not in TERMINAL}
                occupied, _ = reservations(self.state)
                for t in self.state['tasks']:
                    if t['status'] == 'in_progress' and t['id'] not in response_tasks and t['actualStart'] + t['duration'] <= self.state['now']:
                        t['status'], t['actualEnd'] = 'completed', self.state['now']
                        for cid in t['assignedCrew']:
                            c = self._get('crew', cid)
                            if c['currentTaskId'] == t['id']:
                                c['currentTaskId'] = None; c['status'] = 'reserved' if cid in occupied else 'available'
                        self._event('งานประจำเสร็จ: ' + t['title'], 'task')
                # Normal roster travel also consumes time; it is not re-started every forecast refresh.
                for t in sorted(self.state['tasks'], key=lambda t: t['earliest']):
                    if t['status'] != 'scheduled' or t['priority'] == 'critical' or t['id'] in response_tasks: continue
                    for cid in t['assignedCrew']:
                        c = self._get('crew', cid)
                        if c['currentTaskId'] or c.get('routineTravel') or c['status'] == 'unavailable' or cid in occupied: continue
                        r = route(self.state, c['zone'], t['zone'])
                        if r and r['seconds'] and t['earliest'] - r['seconds'] <= self.state['now']:
                            c['routineTravel'] = {'destination': t['zone'], 'etaAt': self.state['now'] + r['seconds']}
                            c['status'] = 'transit'
                    for gid in t['gseIds']:
                        g = self._get('gse', gid)
                        if g['status'] == 'broken' or g.get('destination'): continue
                        r = route(self.state, g['zone'], t['zone'])
                        if r and r['seconds'] and t['earliest'] - r['seconds'] <= self.state['now']:
                            g.update(destination=t['zone'], etaAt=self.state['now'] + r['seconds'])
                prediction = forecast(self.state)
                for row in prediction['rows']:
                    t = self._get('tasks', row['taskId'])
                    if t['status'] != 'scheduled' or t['priority'] == 'critical' or t['id'] in response_tasks or row['start'] > self.state['now'] or row['risk'] == 'blocked': continue
                    if any(cid in occupied or self._get('crew', cid)['currentTaskId'] for cid in t['assignedCrew']): continue
                    if any(self._get('tasks', d)['status'] != 'completed' for d in t['dependencies']): continue
                    # Scheduled baseline resources are assumed to travel as planned; response travel is explicit.
                    t['status'], t['actualStart'] = 'in_progress', self.state['now']
                    for cid in t['assignedCrew']:
                        c = self._get('crew', cid); c.update(status='busy', currentTaskId=t['id'], zone=t['zone'])
                    for gid in t['gseIds']: self._get('gse', gid)['zone'] = t['zone']
                    self._event('เริ่มงานประจำ: ' + t['title'], 'task')
            self._save()
