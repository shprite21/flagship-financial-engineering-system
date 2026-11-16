"""Verify the running Q gateway, exports and new-module reproduction locally."""
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen

from qmodules.replay import replay
from qmodules.service import PROVENANCE

ROOT = Path(__file__).resolve().parents[3]
BASE = 'http://127.0.0.1:5273/integrations/engine/api'
OUTPUT = ROOT/'outputs/consolidation/live'


def request(path, payload=None):
    req = Request(BASE + path, data=json.dumps({'payload': payload}).encode() if payload is not None else None,
                  headers={'Content-Type': 'application/json', 'Origin': 'http://127.0.0.1:5273'})
    with urlopen(req, timeout=60) as response:
        return json.load(response)


def action(name, payload):
    job = request('/evidence/actions/' + name, payload)['id']
    for _ in range(240):
        result = request('/evidence/artifacts/job/' + job)
        event = result['events'][-1]
        if event['action'] in {'completed', 'failed', 'cancelled', 'interrupted'}:
            if event['action'] != 'completed':
                raise RuntimeError(event)
            return event['body']['artifact_id']
        time.sleep(1)
    raise RuntimeError('Observation timed out; inspect the existing job ' + job + ' before retrying')


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    health = request('/health')
    assert health['mode'] == 'research_only' and health['liveOrderSubmission'] is False
    catalogue = request('/evidence/catalog')
    assert all(name in catalogue['quant'] for name in ('economy-simulation', 'economy-benchmark', 'intelligence-import',
               'intelligence-search', 'intelligence-answer', 'intelligence-news', 'intelligence-index', 'intelligence-semantic-search'))
    listing = request('/evidence/artifacts/module_result?limit=100')['items']
    verified = []
    for name in ('SYNTHETIC native economy', 'Company report search · Swiggy'):
        key = next(row['id'] for row in listing if row['name'] == name)
        record = request('/evidence/artifacts/module_result/' + key + '/export')
        assert record['code'] == PROVENANCE, 'Running service does not match the checked source'
        file = OUTPUT / (record['action'] + '.json')
        file.write_text(json.dumps(record, ensure_ascii=False), encoding='utf-8')
        check = replay(file, ROOT/'.data/flagship/evidence')
        verified.append({'id': key, 'action': record['action'], 'replay': check})
    benchmark = action('economy-benchmark', {'households': 1000, 'firms': 10, 'steps': 20, 'populations': [100, 1000], 'repeats': 2})
    record = request('/evidence/artifacts/module_result/' + benchmark + '/export')
    assert record['code'] == PROVENANCE and len(record['attempts']) == 6
    assert all(attempt['checks']['cash_conservation'] for attempt in record['attempts'])
    for attempt in record['attempts']:
        observation = request('/evidence/artifacts/economy_observation/' + attempt['artifact_id'])['artifact']
        parent = request('/evidence/artifacts/job/' + observation['job_id'])['artifact']
        assert parent['request']['action'] == 'economy-benchmark'
        assert observation['configuration'] == attempt['configuration']
        assert request('/evidence/artifacts/module_source/' + parent['request']['source_id'])['artifact']['code'] == PROVENANCE
    (OUTPUT/'economy-benchmark.json').write_text(json.dumps(record), encoding='utf-8')
    verified.append({'id': benchmark, 'action': 'economy-benchmark', 'attempts': 6, 'warmups': 2, 'retained_child_observations': 6})
    summary = {'health': health, 'catalogue_actions': sorted(catalogue['quant']), 'verified': verified,
               'limitations': ['This verification does not call optional AI or news providers; their contracts are tested separately with deterministic fixtures.']}
    (OUTPUT/'verification.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
