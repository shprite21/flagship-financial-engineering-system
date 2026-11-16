"""Project endpoints through the existing authenticated Q research gateway."""
from fastapi import APIRouter
from fastapi.responses import Response
from apps.research_api import Decision
from paper.api import Control
from research.survival.forward import PaperEvent
from .models import (CreateProject, Revision, Reason, DatasetRequest, TrialRequest,
                     Reference, FreezeRequest, ForwardRequest, Specification)
from .service import ProjectService

router = APIRouter(prefix='/api/research/projects', tags=['research projects'])


def service():
    from apps.research_api import workspace, survival_service
    ws = workspace()
    with ws.lock:
        if ws.project_service is None:
            ws.project_service = ProjectService(ws, survival_service())
        return ws.project_service


@router.get('/catalog')
def catalog():
    from research.workspace import strategy_catalog
    return {'schema_version': 1, 'specification': Specification.model_json_schema(),
        'strategies': strategy_catalog()['strategies'], 'portfolio_methods': ['signal', 'equal', 'inverse_volatility', 'risk_parity', 'minimum_variance'],
        'unsupported': ['Maximum-Sharpe, sector and turnover constraint adapters', 'Certified genuinely unseen historical OOS',
                        'Authenticated feed publisher', 'Live orders', 'Signal-distribution drift and calibrated implementation shortfall']}


@router.get('')
def listing():
    return {'projects': service().list()}


@router.post('', status_code=201)
def create(request: CreateProject):
    return service().create(request.spec)


@router.get('/{key}')
def get(key: str):
    return service().get(key, inspect=True)


@router.post('/{key}/revisions', status_code=201)
def revise(key: str, request: Revision):
    return service().revise(key, request)


@router.post('/{key}/references', status_code=201)
def reference(key: str, request: Reference):
    return service().reference(key, request)


@router.post('/{key}/notes', status_code=201)
def note(key: str, request: Reason):
    return service().note(key, request.reason)


@router.post('/{key}/datasets', status_code=202)
def dataset(key: str, request: DatasetRequest):
    return service().capture(key, request)


@router.post('/{key}/trials', status_code=202)
def trials(key: str, request: TrialRequest):
    return service().trials(key, request)


@router.post('/{key}/trials/{trial}/validate', status_code=202)
def validate(key: str, trial: str):
    return service().validate(key, trial)


@router.post('/{key}/trials/{trial}/decision', status_code=201)
def decision(key: str, trial: str, request: Decision):
    return service().decide(key, trial, request)


@router.post('/{key}/trials/{trial}/reveal', status_code=202)
def reveal(key: str, trial: str, request: Reason):
    return service().reveal(key, trial, request.reason)


@router.post('/{key}/freezes', status_code=201)
def freeze(key: str, request: FreezeRequest):
    return service().freeze(key, request)


@router.get('/{key}/versions/{version}/comparison')
def comparison(key: str, version: str):
    return service().comparison(key, version)


@router.post('/{key}/forward', status_code=201)
def forward(key: str, request: ForwardRequest):
    return service().forward(key, request)


@router.post('/{key}/forward/{record}/events', status_code=201)
def forward_event(key: str, record: str, event: PaperEvent):
    return service().forward_event(key, record, event)


@router.post('/{key}/forward/{record}/control')
def control(key: str, record: str, request: Control):
    return service().forward_control(key, record, request.action)


@router.get('/{key}/report')
def report(key: str):
    from .report import export
    return Response(export(service(), key), media_type='text/markdown',
                    headers={'Content-Disposition': f'attachment; filename="q-project-{key[:12]}.md"'})


@router.get('/{key}/export')
def export_project(key: str):
    from .report import export
    return Response(export(service(), key, packed=True), media_type='application/zip',
                    headers={'Content-Disposition': f'attachment; filename="q-project-{key[:12]}.zip"'})
