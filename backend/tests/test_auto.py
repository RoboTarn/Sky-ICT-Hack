import asyncio
from fastapi.testclient import TestClient
from backend.engine import Engine
from backend import main

def ready(plans):
    return {'status':'ready','source':'typhoon','planId':plans[0]['id'],'message':'ตรวจแผนแล้ว','tradeoffs':'ข้อมูลจำลอง'}

def test_incident_automatically_drafts_once_across_clients(monkeypatch):
    engine = Engine(':memory:')
    monkeypatch.setattr(main,'engine',engine)
    calls=[]
    async def model(plans,incident):
        calls.append(incident['id'])
        return ready(plans)
    monkeypatch.setattr(main.typhoon,'recommend',model)
    one,two=TestClient(main.app),TestClient(main.app)
    incident=one.post('/api/incidents',json={'type':'injury'}).json()
    world=two.get('/api/state').json()
    assert world['incidents'][0]['analysis']['status']=='ready'
    assert any(p['incidentId']==incident['id'] and p.get('recommended') for p in world['plans'])
    one.get('/api/state'); two.get('/api/state')
    assert len(calls)==1

def test_scheduled_emergency_only_alerts_and_plans_when_due(monkeypatch):
    engine=Engine(':memory:'); monkeypatch.setattr(main,'engine',engine)
    async def model(plans,incident): return ready(plans)
    monkeypatch.setattr(main.typhoon,'recommend',model)
    client=TestClient(main.app)
    client.post('/api/incidents',json={'type':'fire','delay':300})
    assert engine.state['incidents'][0]['status']=='scheduled' and not engine.state['plans']
    client.post('/api/simulation/actions',json={'action':'advance','seconds':300})
    assert engine.state['incidents'][0]['analysis']['status']=='ready'
    assert next(g for g in engine.state['gates'] if g['id']=='B3')['closed']

def test_refusal_automatically_replans_without_double_booking(monkeypatch):
    engine=Engine(':memory:'); monkeypatch.setattr(main,'engine',engine)
    async def model(plans,incident): return ready(plans)
    monkeypatch.setattr(main.typhoon,'recommend',model)
    client=TestClient(main.app)
    client.post('/api/incidents',json={'type':'flight_delay'})
    old=engine.state['plans'][0]
    ids=engine.approve(old['id'])
    mission=next(m for m in engine.state['missions'] if m['id'] in ids and m['crewId']=='A17')
    client.post('/api/missions/'+mission['id']+'/actions',json={'action':'reject','reason':'ไม่พร้อมรับงาน'})
    proposed=[p for p in engine.state['plans'] if p['status']=='proposed']
    assert proposed and all(p['revision']==engine.state['revision'] for p in proposed)
    assert engine.state['incidents'][0]['analysis']['status']=='ready'

def test_stale_model_result_requeues_and_old_run_is_ignored():
    engine=Engine(':memory:'); engine.incident('flight_delay')
    plans,_,revision=engine.claim_recovery()
    engine.incident('injury')
    engine.ai_result(ready(plans),plans,revision)
    assert engine.state['incidents'][0]['analysis']['status']=='stale'
    assert engine.claim_recovery() is not None
    engine.simulation('reset')
    engine.ai_result(ready(plans),plans,revision)
    assert engine.state['ai']['status']!='ready' and not engine.state['plans']

def test_no_feasible_plan_is_reported_without_provider_loop():
    engine=Engine(':memory:')
    for c in engine.state['crew']: c['status']='unavailable'
    engine.incident('injury')
    plans,incident,_=engine.claim_recovery()
    assert not plans and incident['analysis']['status']=='no_plan'
    assert engine.claim_recovery() is None

def test_analysis_lease_blocks_concurrent_jobs_and_recovers_after_expiry():
    engine=Engine(':memory:'); engine.incident('flight_delay')
    first=engine.claim_recovery()
    assert first and engine.claim_recovery() is None
    engine.state['incidents'][0]['analysis']['leaseUntil']=0
    second=engine.claim_recovery()
    assert second and second[0][0]['id']!=first[0][0]['id']
