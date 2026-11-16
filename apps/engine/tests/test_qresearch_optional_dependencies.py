"""A blocked forecasting DLL must not take unrelated research actions offline."""
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest


@pytest.mark.parametrize('failure_type', ['ImportError', 'OSError'])
def test_blocked_arima_keeps_catalogue_and_frontier_available(tmp_path, failure_type):
    # A fresh process catches eager imports even when another test has already
    # imported qresearch or statsmodels. The blocker runs before either service.
    script = textwrap.dedent('''
        import builtins
        import os
        from pathlib import Path
        import sys
        import time

        original_import = builtins.__import__
        attempts = []
        error_type = getattr(builtins, sys.argv[2])

        def blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == 'statsmodels.tsa.arima.model':
                attempts.append(name)
                raise error_type('DLL load failed: application control blocked _univariate_diffuse')
            return original_import(name, globals, locals, fromlist, level)

        builtins.__import__ = blocked_import
        os.environ['Q_ENGINE_TOKEN'] = 'optional-dependency-test-token'

        from fastapi.testclient import TestClient
        import flagship_api as api
        from qresearch.history import ScenarioConfig
        from qresearch.modeling import FrontierConfig
        from qresearch.service import catalog, run

        api.ROOT = Path(sys.argv[1])
        client = TestClient(api.app, headers={'x-q-engine-token': 'optional-dependency-test-token'})
        try:
            assert {'arima-forecast', 'efficient-frontier'} <= catalog().keys()
            response = client.get('/api/evidence/catalog')
            assert response.status_code == 200, response.text
            assert 'efficient-frontier' in response.json()['quant']
            assert attempts == [], 'Catalogue loading must not import ARIMA'

            db = api.store()
            history = run(db, 'history-scenario', ScenarioConfig(observations=100, assets=2), lambda: False, lambda *_: None)
            result = run(db, 'efficient-frontier', FrontierConfig(history_id=history, points=3), lambda: False, lambda *_: None)
            saved = db.get(result, 'quant_result')
            weights = saved['allocation']['weights'].values()
            assert abs(sum(weights) - 1) < 1e-8
            assert all(0 <= weight <= 1 for weight in weights)
            assert attempts == [], 'Efficient frontier must not import ARIMA'

            response = client.post('/api/evidence/actions/arima-forecast', json={'payload': {
                'history_id': history, 'test_observations': 10, 'p': 1, 'd': 0, 'q': 0,
            }})
            assert response.status_code == 200, response.text
            key = response.json()['id']
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                response = client.get('/api/evidence/artifacts/job/' + key)
                assert response.status_code == 200, response.text
                event = response.json()['events'][-1]
                if event['action'] in {'completed', 'failed', 'cancelled'}:
                    break
                time.sleep(.01)
            else:
                raise AssertionError('Unavailable ARIMA job did not report failure')
            assert event['action'] == 'failed', event
            assert event['body']['reason'].startswith('ARIMA forecasting is unavailable:')
            assert 'statsmodels dependency could not be loaded' in event['body']['reason']
            assert '_univariate_diffuse' not in event['body']['reason']
            assert len(attempts) == 1
            assert [record['id'] for record in db.list('quant_result')] == [result]
            assert client.get('/api/evidence/catalog').status_code == 200
        finally:
            client.close()
            if api.research_api._workspace is not None:
                api.research_api._workspace.executor.shutdown(wait=True)
    ''')
    result = subprocess.run(
        [sys.executable, '-c', script, str(tmp_path), failure_type],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
