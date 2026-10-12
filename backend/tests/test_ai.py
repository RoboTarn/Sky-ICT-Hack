import asyncio
import json
import httpx
from backend.ai import Typhoon
from backend.engine import Engine

def plans():
    e = Engine(':memory:'); i = e.incident('flight_delay'); p, _, _ = e.proposals(i['id']); return p, i

def test_model_can_only_select_validated_plan(monkeypatch):
    p, i = plans(); ai = Typhoon()
    async def fake(_):
        return {'tool_calls': [{'function': {'name': 'recommend_plan', 'arguments': json.dumps({'planId': 'invented-plan', 'rationale': 'invented', 'tradeoffs': 'invented'})}}]}
    monkeypatch.setattr(ai, '_call', fake)
    result = asyncio.run(ai.recommend(p, i))
    assert result['source'] == 'optimizer' and result['planId'] == p[0]['id']

def test_valid_model_selection_is_marked_as_live(monkeypatch):
    p, i = plans(); ai = Typhoon()
    async def fake(_):
        return {'tool_calls': [{'function': {'name': 'recommend_plan', 'arguments': json.dumps({'planId': p[1]['id'], 'rationale': 'เลือกทีมที่ผ่านทักษะ', 'tradeoffs': 'เดินทางมากขึ้น'})}}]}
    monkeypatch.setattr(ai, '_call', fake)
    result = asyncio.run(ai.recommend(p, i))
    assert result['source'] == 'typhoon' and result['status'] == 'ready' and result['planId'] == p[1]['id']

def test_timeout_and_malformed_response_fall_back(monkeypatch):
    p, i = plans(); ai = Typhoon()
    for malformed in (True, False):
        async def fake(_):
            if malformed: return {'content': 'not a tool call'}
            raise httpx.ReadTimeout('upstream timeout')
        monkeypatch.setattr(ai, '_call', fake)
        assert asyncio.run(ai.recommend(p, i))['source'] == 'optimizer'

def test_ai_result_from_old_snapshot_is_not_applied():
    e = Engine(':memory:'); i = e.incident('flight_delay'); p, _, rev = e.proposals(i['id']); e.incident('gse_failure')
    e.ai_result({'status': 'ready', 'source': 'typhoon', 'planId': p[0]['id'], 'message': 'stale'}, p, rev)
    assert e.state['ai']['status'] == 'stale'

def test_unverified_statistics_are_replaced_without_faking_ai_selection(monkeypatch):
    p, i = plans(); ai = Typhoon()
    async def fake(_):
        return {'tool_calls': [{'function': {'name': 'recommend_plan', 'arguments': json.dumps({'planId': p[0]['id'], 'rationale': 'ลดเวลาล่าช้า 99 นาที', 'tradeoffs': 'ค่าใช้จ่าย 650 บาท'})}}]}
    monkeypatch.setattr(ai, '_call', fake)
    result = asyncio.run(ai.recommend(p, i))
    assert result['source'] == 'typhoon' and result['explanationSource'] == 'validated_template'
    assert '99' not in result['message'] and 'บาท' not in result['tradeoffs']
