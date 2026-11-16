"""Routes reuse Q's authentication and bounded research queue. No broker orders."""
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Path as ApiPath
from pydantic import BaseModel, ConfigDict, Field

from .service import Service
from .data import SYMBOLS, ingest

router=APIRouter(prefix='/api/research/india',tags=['India manual workflow'])


class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)


class IngestRequest(Strict):
    provider: Literal['groww','yahoo']='yahoo'
    start: str=Field(default='2021-01-01',pattern=r'^\d{4}-\d{2}-\d{2}$')
    end: str=Field(default='2026-10-17',pattern=r'^\d{4}-\d{2}-\d{2}$')


class ResearchRequest(Strict):
    dataset: str=Field(pattern=r'^[a-f0-9]{64}$')
    device: Literal['cuda','cpu']='cuda'


class TicketRequest(Strict):
    symbol: str=Field(pattern=r'^[A-Z0-9&-]{1,25}$')


class Fill(Strict):
    event_id: str=Field(min_length=8,max_length=120)
    ticket_id: str=Field(pattern=r'^[a-f0-9]{32}$')
    side: Literal['buy','sell']
    quantity: int=Field(strict=True,gt=0,le=10000)
    price: float=Field(gt=0)
    fees: float=Field(ge=0)
    timestamp: str
    broker_reference: str=Field(min_length=1,max_length=120)


class Cancel(Strict):
    ticket_id: str=Field(pattern=r'^[a-f0-9]{32}$')
    reason: str=Field(min_length=10,max_length=500)


class Reconcile(Strict):
    settled_cash: float=Field(ge=0,le=5000)
    reason: str=Field(min_length=10,max_length=500)


def service():
    return Service(Path(os.environ.get('Q_INDIA_DATA',Path(__file__).resolve().parents[3]/'.data/india')))


@router.get('')
def overview(): return service().overview()


@router.get('/signals')
def signals(): return service().signals()


@router.get('/datasets')
def datasets():
    return [{'id':p.parent.name,**{k:v for k,v in json.loads(p.read_text()).items() if k!='sources'}}
            for p in sorted((service().root/'datasets').glob('*/manifest.json'))]


@router.get('/jobs/{key}')
def job_events(key: str=ApiPath(pattern=r'^[a-f0-9]{64}$')):
    from flagship_api import store
    store().get(key,'job')
    return store().events(key)


@router.post('/ingest',status_code=202)
def ingest_job(request: IngestRequest):
    from flagship_api import submit,store
    def work(cancelled,progress):
        key=ingest(service().root,request.provider,request.start,request.end)
        return store().put('india_dataset',{'id':key,'provider':request.provider})
    return submit('NSE observed data ingestion',work,request=request.model_dump())


@router.post('/research',status_code=202)
def research_job(request: ResearchRequest):
    from flagship_api import submit,store
    root=service().root
    if not (root/'datasets'/request.dataset/'manifest.json').is_file(): raise ValueError('Dataset unavailable')
    python=os.environ.get('Q_GPU_PYTHON',sys.executable)
    def work(cancelled,progress):
        # Fixed module/arguments; no user-supplied executable, source code or shell.
        env={k:v for k,v in os.environ.items() if not any(s in k.upper() for s in ('TOKEN','SECRET','API_KEY','PASSWORD'))}
        result=subprocess.run([python,'-m','india','research','--root',str(root),'--dataset',request.dataset,'--device',request.device],
                  cwd=Path(__file__).resolve().parents[1],env=env,capture_output=True,text=True,timeout=3600,
                  creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        if result.returncode: raise ValueError('Training failed. Check the local GPU environment and run the documented CLI diagnostic.')
        folder,report=service().latest()
        return store().put('india_research',{'run_id':report['id'],'dataset':request.dataset,'decision':report['decision']})
    return submit('India purged GPU candidate comparison',work,request=request.model_dump())


@router.post('/tickets')
def ticket(request:TicketRequest): return service().ticket(request.symbol)


@router.post('/fills')
def fill(request:Fill):
    return service().journal.append('fill',request.model_dump(exclude={'event_id'}),event_id=request.event_id)


@router.post('/release-ticket')
def cancel(request:Cancel): return service().journal.append('cancel',request.model_dump())


@router.post('/reconcile')
def reconcile(request:Reconcile): return service().journal.append('reconcile',request.model_dump())


@router.post('/halt')
def halt(): return service().journal.append('halt',{'reason':'User halted new manual tickets; existing broker positions require manual attention'})
