import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from pydantic import BaseModel, Field
from .engine import Engine, DomainError
from .ai import Typhoon

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / '.env')
database_url = os.getenv('DATABASE_URL') or os.getenv('POSTGRES_URL')
if os.getenv('VERCEL') and not database_url:
    raise RuntimeError('Hosted demo requires DATABASE_URL for shared persistent state')
engine = Engine(os.getenv('SWARM_DB', str(ROOT / '.runtime' / 'swarm.sqlite3')), database_url)
typhoon = Typhoon()

async def auto_recovery():
    # BackgroundTasks finishes within the serverless invocation. Leases prevent
    # commander + crew requests from calling the provider for the same event twice.
    for _ in range(1):
        job = await asyncio.to_thread(engine.claim_recovery)
        if not job: return
        plans, incident, revision = job
        if plans:
            result = await typhoon.recommend(plans, incident)
            await asyncio.to_thread(engine.ai_result, result, plans, revision)

@asynccontextmanager
async def lifespan(app):
    async def clock():
        while True:
            await asyncio.sleep(1)
            with engine.lock:
                if engine.state['playing']: engine.advance(engine.state['speed'])
    async def analyst():
        while True:
            await auto_recovery()
            await asyncio.sleep(1)
    tasks = [] if os.getenv('VERCEL') else [asyncio.create_task(clock()), asyncio.create_task(analyst())]
    yield
    for task in tasks: task.cancel()
    for task in tasks:
        try: await task
        except asyncio.CancelledError: pass

app = FastAPI(title='SKY SWARM OPS', version='1.0.0', lifespan=lifespan)

@app.exception_handler(DomainError)
async def domain_error(request, exc):
    return JSONResponse(status_code=exc.status, content={'detail': exc.message})

class IncidentInput(BaseModel):
    type: Literal['flight_delay', 'gate_change', 'staff_absence', 'gse_failure', 'injury', 'fire']
    zone: str = 'B6'
    delay: int = Field(default=0, ge=0, le=1800)

class ProposalInput(BaseModel):
    incidentId: str

class MissionInput(BaseModel):
    action: Literal['accept', 'depart', 'arrive', 'start', 'complete', 'reject', 'blocked', 'check']
    reason: str = Field(default='', max_length=500)
    checked: list[int] | None = None

class SimulationInput(BaseModel):
    action: Literal['play', 'pause', 'advance', 'reset', 'speed']
    seconds: int = Field(default=60, ge=1, le=1800)
    speed: Literal[1, 4] = 1

class ChatInput(BaseModel):
    message: str = Field(min_length=1, max_length=1200)

@app.get('/api/health')
def health():
    return {'ok': True, 'typhoonConfigured': bool(typhoon.key), 'model': typhoon.model, 'simulated': True}

@app.get('/api/state')
def state(background_tasks: BackgroundTasks, horizon: int = 30):
    if horizon not in (10, 20, 30): raise DomainError('ช่วง Forecast ต้องเป็น 10, 20 หรือ 30 นาที', 422)
    engine.sync_clock()
    snapshot = engine.snapshot(horizon)
    snapshot['aiConfig'] = {'configured': bool(typhoon.key), 'model': typhoon.model}
    background_tasks.add_task(auto_recovery)
    return snapshot

@app.get('/api/events')
async def events(request: Request):
    async def stream():
        previous = None
        heartbeat = 0
        started = asyncio.get_running_loop().time()
        while not await request.is_disconnected():
            if os.getenv('VERCEL') and asyncio.get_running_loop().time() - started > 20: return
            with engine.lock:
                stamp = (engine.state['runId'], engine.state['revision'], engine.state['now'], engine.state['events'][-1]['seq'] if engine.state['events'] else 0)
            if stamp != previous:
                previous = stamp
                yield 'event: state\ndata: ' + json.dumps({'runId': stamp[0], 'revision': stamp[1], 'now': stamp[2], 'seq': stamp[3]}) + '\n\n'
            heartbeat += 1
            if heartbeat % 15 == 0: yield ': keepalive\n\n'
            await asyncio.sleep(0.5)
    return StreamingResponse(stream(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

@app.post('/api/incidents')
def create_incident(body: IncidentInput, background_tasks: BackgroundTasks):
    background_tasks.add_task(auto_recovery)
    return engine.incident(body.type, body.zone, body.delay)

@app.post('/api/recovery/proposals')
async def proposals(body: ProposalInput):
    plans, incident, revision = await asyncio.to_thread(engine.proposals, body.incidentId)
    if plans:
        result = await typhoon.recommend(plans, incident)
        engine.ai_result(result, plans, revision)
    return {'plans': engine.snapshot()['plans'], 'ai': engine.snapshot()['ai']}

@app.post('/api/recovery/{plan_id}/approve')
def approve(plan_id: str):
    return {'missionIds': engine.approve(plan_id)}

@app.post('/api/recovery/{plan_id}/reject')
def reject(plan_id: str):
    engine.reject_plan(plan_id)
    return {'ok': True}

@app.post('/api/missions/{mission_id}/actions')
def mission_action(mission_id: str, body: MissionInput, background_tasks: BackgroundTasks):
    background_tasks.add_task(auto_recovery)
    return engine.mission_action(mission_id, body.action, body.reason, body.checked)

@app.post('/api/simulation/actions')
def simulation(body: SimulationInput, background_tasks: BackgroundTasks):
    background_tasks.add_task(auto_recovery)
    engine.simulation(body.action, body.seconds, body.speed)
    return {'ok': True}

@app.post('/api/copilot/chat')
async def copilot(body: ChatInput):
    return await typhoon.chat(body.message, engine.snapshot())

@app.get('/{path:path}', include_in_schema=False)
def spa(path: str):
    if path.startswith('api/'): return JSONResponse(status_code=404, content={'detail': 'Unknown endpoint'})
    dist = (ROOT / 'dist').resolve()
    candidate = (dist / path).resolve()
    if candidate.is_relative_to(dist) and candidate.is_file(): return FileResponse(candidate)
    if (dist / 'index.html').is_file(): return FileResponse(dist / 'index.html')
    return JSONResponse(status_code=404, content={'detail': 'Start the Vite frontend on port 5173, or run npm run build first.'})
