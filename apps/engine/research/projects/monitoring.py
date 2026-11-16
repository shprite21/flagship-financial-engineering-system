"""Separate descriptive evidence and explicit limits; never infer a forward track record."""
from datetime import datetime, timezone
import numpy as np


def standard_metrics(raw):
    """Map stored engine names; annualized_return is geometric (CAGR)."""
    return {**raw, 'cagr': raw.get('cagr', raw.get('annualized_return')),
            'volatility': raw.get('volatility', raw.get('annualized_volatility'))}


def compare(frozen, evidence, oos, registrations):
    result = evidence['result']
    historical = standard_metrics(result['metrics'])
    historical['gross_exposure'] = result.get('risk', {}).get('current_gross')
    walk = standard_metrics(result['validation']['metrics'])
    reserved = standard_metrics(oos[-1]['metrics']) if oos else {}
    names = ['total_return', 'cagr', 'volatility', 'sharpe', 'sortino', 'max_drawdown',
             'annual_turnover', 'hit_rate', 'transaction_costs', 'gross_exposure',
             'signal_decay', 'implementation_shortfall']
    forward, alerts = [], []
    for link in registrations:
        record = link['evidence']
        metrics = dict(record.get('performance') or {})
        values = record.get('returns', [])
        if values:
            path = np.r_[1.0, np.cumprod(1 + np.asarray(values))]
            metrics.update(total_return=float(path[-1] - 1), max_drawdown=float(np.min(path / np.maximum.accumulate(path) - 1)),
                           hit_rate=float(np.mean(np.asarray(values) > 0)))
        # Cadence is deliberately not inferred from irregular manual marks.
        for key in ('cagr', 'sharpe', 'sortino', 'volatility', 'annual_turnover'):
            metrics[key] = None
        limits = frozen['kill']
        if values and -metrics['max_drawdown'] > limits['max_drawdown']:
            alerts.append({'kind': 'drawdown', 'value': -metrics['max_drawdown'], 'limit': limits['max_drawdown'], 'forward_id': link['id']})
        cost = record.get('mean_cost_drift_bps')
        if cost is not None and limits['max_cost_drift_bps'] is not None and cost > limits['max_cost_drift_bps']:
            alerts.append({'kind': 'cost_drift', 'value': cost, 'limit': limits['max_cost_drift_bps'], 'forward_id': link['id']})
        marks = [e for e in record.get('events', []) if e.get('kind') == 'observation']
        gross = sum(abs(w) for w in marks[-1].get('weights', {}).values()) if marks else None
        deployment = record.get('deployment')
        if deployment and deployment.get('last_bar') and deployment.get('nav', 0) > 0:
            gross = sum(abs(p['quantity'] * a['marks'].get(symbol, 0))
                        for a in deployment['accounts'].values()
                        for symbol, p in a['positions'].items()) / deployment['nav']
        metrics['gross_exposure'] = gross
        if gross is not None and gross > limits['max_gross']:
            alerts.append({'kind': 'gross_exposure', 'value': gross, 'limit': limits['max_gross'], 'forward_id': link['id']})
        at = record.get('as_of') or record.get('created_at') or link['created_at']
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(at.replace('Z', '+00:00'))).total_seconds() / 86400
        if age > limits['max_stale_days']:
            alerts.append({'kind': 'stale_evidence', 'value': age, 'limit': limits['max_stale_days'], 'forward_id': link['id']})
        if deployment and deployment.get('exceptions'):
            alerts.append({'kind': 'pipeline_exception', 'details': deployment['exceptions'], 'forward_id': link['id']})
        forward.append({'id': link['id'], 'record_id': link['record_id'], 'mode': link['mode'],
            'observations': record.get('observations', 0), 'metrics': metrics, 'source': record['source'],
            'broker_verified': False, 'as_of': record.get('as_of'), 'cost_drift_bps': cost,
            'minimum_observations_met': record.get('observations', 0) >= limits['minimum_observations'],
            'deployment': deployment, 'events': record.get('events', []), 'recorded_fills': record.get('recorded_fills', 0)})
    return {'strategy_version_id': frozen.get('id'), 'expected': frozen['expected_metrics'],
        'expectation_basis': frozen['expectation_basis'],
        'table': [{'metric': name, 'historical': historical.get(name), 'walk_forward': walk.get(name),
                   'reserved_oos': reserved.get(name),
                   'prospective': forward[0]['metrics'].get(name) if len(forward) == 1 else None} for name in names],
        'historical_period': {k: result['data'].get(k) for k in ('evaluation_start', 'end_date', 'observations')},
        'oos': oos, 'forward': forward, 'alerts': alerts, 'automatic_control': False,
        'limitations': ['Periods and accounting conventions differ; columns are not interchangeable estimates.',
            'Gross exposure is the last marked exposure in each supplied account, not an average across its evaluation period.',
            'No prospective annualization or significance is inferred without verified cadence and adequate observations.',
            'Volatility kill thresholds cannot be evaluated without verified observation cadence; no volatility pass is implied.',
            'Signal distribution drift, signal decay and empirical implementation shortfall are NOT SUPPORTED by these records.',
            'Historical bootstrap intervals remain historical uncertainty, not prospective forecast bands.',
            'Project alerts require review; existing paper-account risk halts retain their own deterministic semantics.']}
