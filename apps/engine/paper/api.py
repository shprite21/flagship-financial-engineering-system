"""Authenticated through Q's existing loopback gateway middleware."""
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError
from fastapi import APIRouter
from pydantic import Field
from .models import Deployment, Strict, Feed, OrderIntent
from .service import PaperService

router = APIRouter(prefix='/api/paper', tags=['paper'])
_service = None


def gateway_feed(cfg):
    base = os.environ.get('Q_MARKET_GATEWAY_URL', '')
    if not base:
        raise ValueError('Paper feed gateway is not connected')
    url = f'{base}/internal/paper-feed?provider={cfg.provider}&market={cfg.market}&interval={cfg.interval}'
    try:
        with urlopen(Request(url, headers={'x-q-engine-token': os.environ.get('Q_ENGINE_TOKEN', '')}), timeout=15) as response:
            data = response.read(32_000_001)
            if len(data) > 32_000_000: raise ValueError('Paper feed exceeds 32 MB')
            return json.loads(data)
    except (URLError, json.JSONDecodeError):
        raise ValueError('Paper feed unavailable. Configure a compatible provider adapter in the gateway.') from None


def service():
    global _service
    if _service is None:
        root = Path(os.environ.get('Q_PAPER_DATA', Path(__file__).resolve().parents[3] / '.data/paper'))
        _service = PaperService(root, gateway_feed)
    return _service


def freeze(cfg):
    """Resolve server-owned research snapshots. Never trust mutable editor values."""
    from apps.research_api import workspace
    from research.workspace import ResearchRequest
    snapshots = {}
    for spec in cfg.strategies:
        if spec.adapter == 'research':
            job = workspace().get(spec.reference)
            if job['status'] != 'completed': raise ValueError('Research must complete before paper registration')
            request = ResearchRequest.model_validate(job['request'])
            sleeve = spec.research_sleeve or spec.parameters.get('paper_sleeve')
            if sleeve:
                selected = [s for s in request.sleeves if s.strategy == sleeve]
                if len(selected) != 1: raise ValueError('Unknown saved research sleeve')
                request = request.model_copy(update={'sleeves': [selected[0].model_copy(update={'budget': 1.0})]})
                spec.research_sleeve = sleeve
            if not request.long_only or request.max_gross_exposure > 1:
                raise ValueError('Paper supports long-only cash strategies')
            if request.data_mode in ('synthetic', 'demo'):
                raise ValueError('Synthetic research cannot be promoted to forward market evidence')
            if sorted(request.symbols) != sorted(cfg.universe):
                raise ValueError('Frozen research universe must match deployment')
            if cfg.interval != '1d': raise ValueError('Daily research adapters require daily deployments')
            if cfg.rebalance != request.rebalance:
                raise ValueError('Schedule must match the saved research mandate')
            spec.parameters = request.model_dump()
            snapshots[spec.reference] = {'request': spec.parameters, 'source': job.get('result', {}).get('provenance', {}),
                                         'snapshot_sha256': job.get('snapshot_sha256')}
        elif spec.adapter == 'terminal':
            if cfg.interval != '1d': raise ValueError('Saved terminal strategies use daily bars; use a custom minute adapter for intraday rules')
            p = spec.parameters
            required = ('symbol', 'kind', 'lookback', 'slow', 'allocation')
            if any(k not in p for k in required) or p['symbol'] not in cfg.universe:
                raise ValueError('Terminal snapshot needs symbol, rule and parameters')
            if p['kind'] not in ('SMA crossover', 'RSI mean reversion', 'Bollinger mean reversion', 'Breakout', 'Time-series momentum'):
                raise ValueError('Unknown terminal strategy')
            if type(p['lookback']) is not int or not 2 <= p['lookback'] <= 100 or type(p['slow']) is not int or not 3 <= p['slow'] <= 200:
                raise ValueError('Invalid terminal windows')
            if p['kind'] == 'SMA crossover' and p['slow'] <= p['lookback']:
                raise ValueError('Slow window must exceed fast window')
            if not isinstance(p['allocation'], (float, int)) or not 0 < p['allocation'] <= 1:
                raise ValueError('Invalid allocation')
            snapshots[spec.reference] = dict(p)
        elif spec.adapter == 'allocation':
            weights = spec.parameters.get('weights', {})
            if not weights or set(weights) - set(cfg.universe) or any(not isinstance(w, (float, int)) or not 0 <= w <= cfg.max_asset_weight for w in weights.values()) or sum(weights.values()) > cfg.max_gross:
                raise ValueError('Invalid saved allocation')
            snapshots[spec.reference] = spec.parameters
        else:
            import re
            from .worker import validate_files
            if not re.fullmatch(r'[a-f0-9-]{36}:[a-f0-9]{64}', spec.reference):
                raise ValueError('Custom reference must identify a saved project and version')
            project, version = spec.reference.split(':')
            root = Path(__file__).resolve().parents[3] / '.data/codex-development'
            path = root / project / 'snapshots' / (version + '.json')
            if not path.is_file(): raise ValueError('Saved custom source version is unavailable')
            snapshot = json.loads(path.read_text(encoding='utf-8'))
            if snapshot.get('id') != version: raise ValueError('Custom version identity mismatch')
            # Input parameters and code are resolved from the saved version, not editor state.
            spec.parameters = {'snapshot': snapshot,
                               'parameters': json.loads(snapshot['files'].get('parameters.json', '{}')),
                               'worker_image': os.environ.get('Q_PAPER_PYTHON_IMAGE' if spec.adapter == 'custom_python' else 'Q_PAPER_JAVASCRIPT_IMAGE', '')}
            # Missing adapters can be saved for review, but readiness blocks activation.
            snapshots[spec.reference] = snapshot
    return snapshots


class Control(Strict):
    action: str = Field(pattern='^(activate|pause|resume|stop|liquidate)$')


@router.get('/deployments')
def listing():
    return {'deployments': service().list(), 'runner_running': bool(service().thread and service().thread.is_alive())}


@router.post('/deployments', status_code=201)
def create(cfg: Deployment):
    snapshots = freeze(cfg)
    return service().create(cfg, snapshots)


@router.get('/deployments/{key}')
def get(key: str):
    return service().get(key)


@router.get('/deployments/{key}/readiness')
def readiness(key: str):
    return service().readiness(key)


@router.post('/deployments/{key}/control')
def control(key: str, request: Control):
    return service().control(key, request.action)


@router.get('/deployments/{key}/export')
def export(key: str):
    return service().ledger.export(key)


@router.get('/deployments/{key}/events')
def events(key: str, after: int = 0, limit: int = 100):
    if after < 0 or not 1 <= limit <= 500: raise ValueError('Invalid event page')
    with service().ledger.transaction() as db:
        service().ledger.read(db, key)
        rows = db.execute('SELECT seq,key,body,hash FROM events WHERE deployment=? AND seq>? ORDER BY seq LIMIT ?', (key, after, limit)).fetchall()
    return {'events': [{'seq': r['seq'], 'key': r['key'], 'hash': r['hash'],
                        **{k: v for k, v in json.loads(r['body']).items() if k not in ('state', 'changes')}} for r in rows]}


@router.get('/catalog')
def catalog():
    return {'version': 1, 'deployment': Deployment.model_json_schema(), 'feed': Feed.model_json_schema(),
            'order': OrderIntent.model_json_schema(), 'source': 'q_simulated', 'broker_verified': False,
            'custom_entrypoints': {'python': 'paper_adapter.py:decide(context)', 'javascript': 'paper_adapter.mjs:decide(context)'},
            'feed_directory': '.data/paper-feeds', 'provider_status': 'External provider publisher must be configured explicitly'}


@router.get('/deployments/{key}/orders')
def orders(key: str):
    return {'orders': [{**o, 'sleeve': k} for k, a in service().get(key)['accounts'].items() for o in a['orders']]}


class CancelOrder(Strict):
    order_id: str = Field(min_length=1, max_length=300)


@router.post('/deployments/{key}/cancel-order')
def cancel_order(key: str, request: CancelOrder):
    return service().cancel_order(key, request.order_id)


@router.get('/deployments/{key}/evidence')
def evidence(key: str):
    return evidence_for(service(), key)


def evidence_for(paper, key: str):
    """Shared evidence adapter for the API and project-linked paper accounts."""
    from research.survival.forward import monitor
    record = paper.ledger.export(key)
    cfg = Deployment.model_validate(record['config']['spec'])
    observations, expected = [], {}
    from .storage import apply_changes
    state = {}
    for event in record['events']:
        body = event['body']
        apply_changes(state, body['changes'])
        if body['kind'] != 'bar_and_decision': continue
        nav = sum(a['nav'] for a in state['accounts'].values())
        weights = {s: sum(a['positions'].get(s, {}).get('quantity', 0) * a['marks'].get(s, 0) for a in state['accounts'].values()) / nav for s in cfg.universe} if nav else {}
        targets = {s: sum(a['targets'].get(s, 0) * a['nav'] for a in state['accounts'].values()) / nav for s in cfg.universe} if nav else {}
        event_id = event['hash']
        expected[event_id] = {'weights': targets}
        observations.append({'observed_at': state['last_bar'], 'nav': nav, 'weights': weights,
                             'cost_bps': 0, 'signal_id': event_id, 'fills': []})
    result = monitor(observations, expected, {'initial_nav': cfg.capital, 'gross': cfg.max_gross, 'net': cfg.max_gross, 'asset': cfg.max_asset_weight})
    # No independent realized-cost or expected-return evidence is inferred from a model.
    result['mean_cost_drift_bps'] = None
    result['recorded_fills'] = sum(len(a['fills']) for a in record['state']['accounts'].values())
    return {**result, 'id': key, 'source': 'q_automated_simulation', 'broker_verified': False,
            'config': record['config'], 'ledger_head': record['events'][-1]['hash'],
            'limitations': ['Modeled fills are not broker evidence', 'Annualized inference is suppressed; review cadence and sample size']}


@router.post('/runner/{action}')
def runner(action: str):
    if action == 'start': service().start()
    elif action == 'stop': service().stop()
    else: raise ValueError('Unknown runner control')
    return {'running': bool(service().thread and service().thread.is_alive())}
