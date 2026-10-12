from fastapi.testclient import TestClient
from backend.engine import Engine
from backend import main

def test_forecast_query_validation_and_public_snapshot(monkeypatch):
    engine = Engine(':memory:')
    monkeypatch.setattr(main, 'engine', engine)
    client = TestClient(main.app)
    for horizon in (10, 20, 30):
        response = client.get('/api/state', params={'horizon': horizon})
        assert response.status_code == 200
        assert response.json()['forecast']['horizon'] == horizon
        assert 'TYPHOON_API_KEY' not in response.text
        if main.typhoon.key: assert main.typhoon.key not in response.text
    assert client.get('/api/state?horizon=11').status_code == 422
    assert client.post('/api/incidents', json={'type': 'unsupported'}).status_code == 422
    assert client.post('/api/simulation/actions', json={'action': 'advance', 'seconds': -1}).status_code == 422

def test_command_endpoints_and_recommendation_contract(monkeypatch):
    engine = Engine(':memory:')
    monkeypatch.setattr(main, 'engine', engine)
    async def fake(plans, incident):
        return {'status': 'ready', 'source': 'typhoon', 'planId': plans[0]['id'], 'message': 'แผนที่ผ่านข้อจำกัดแล้ว', 'tradeoffs': 'ข้อมูลจำลอง'}
    monkeypatch.setattr(main.typhoon, 'recommend', fake)
    client = TestClient(main.app)
    incident = client.post('/api/incidents', json={'type': 'flight_delay'}).json()
    response = client.post('/api/recovery/proposals', json={'incidentId': incident['id']})
    assert response.status_code == 200 and response.json()['ai']['source'] == 'typhoon'
    plan = response.json()['plans'][0]
    approval = client.post('/api/recovery/' + plan['id'] + '/approve')
    assert approval.status_code == 200
    assert client.post('/api/recovery/' + plan['id'] + '/approve').status_code == 409
    mid = approval.json()['missionIds'][0]
    assert client.post('/api/missions/' + mid + '/actions', json={'action': 'accept'}).status_code == 200
    assert client.post('/api/missions/' + mid + '/actions', json={'action': 'complete'}).status_code == 409
