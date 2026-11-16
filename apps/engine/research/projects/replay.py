"""Replay a project export using installed, matching Q code; never execute ZIP code.

Usage: python -m research.projects.replay path/to/research-project.zip
"""
import hashlib
import io
import json
import zipfile
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd

from evidence.storage import digest
from research.workspace import PROJECT_ROOT, ResearchRequest, clean_json, pipeline_for, research_metrics
from research.survival.replay import replay as replay_survival
from .service import decode_bundle


def verify_source(source, provenance):
    fingerprint = hashlib.sha256()
    with zipfile.ZipFile(io.BytesIO(source)) as archive:
        for name in archive.namelist():
            path = (PROJECT_ROOT / name).resolve()
            if not path.is_relative_to(PROJECT_ROOT.resolve()) or not path.is_file():
                raise ValueError('Matching archived source is not installed')
            fingerprint.update(name.encode())
            fingerprint.update(path.read_bytes())
    if fingerprint.hexdigest() != provenance['source_sha256']:
        raise ValueError('Engine source differs; review and use the recorded source environment')
    for package, expected in provenance['dependencies'].items():
        if version(package) != expected:
            raise ValueError('Dependency differs: ' + package)


def replay(path):
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        if manifest['schema_version'] != 1:
            raise ValueError('Unsupported project export schema')
        if set(archive.namelist()) != set(manifest['files']) | {'manifest.json'}:
            raise ValueError('Export file inventory mismatch')
        for name, fingerprint in manifest['files'].items():
            if digest(archive.read(name)) != fingerprint:
                raise ValueError('Export fingerprint mismatch: ' + name)
        project = json.loads(archive.read('project.json'))
        completed = 0
        for trial in project['trials']:
            if trial['status'] != 'completed':
                continue
            prefix = 'experiments/' + trial['id'] + '/'
            verify_source(archive.read(prefix + 'source.zip'), trial['result']['provenance'])
            bundle = decode_bundle(json.loads(archive.read(prefix + 'snapshot.json')))
            request = ResearchRequest.model_validate(trial['request'])
            output = pipeline_for(request).run(bundle)
            for name, actual in [('targets.csv', output.weights), ('executed_weights.csv', output.backtest.weights)]:
                expected = pd.read_csv(io.BytesIO(archive.read(prefix + name)), index_col=0, parse_dates=[0], float_precision='round_trip')
                pd.testing.assert_frame_equal(actual, expected, check_names=False, check_freq=False, rtol=1e-12, atol=1e-12)
            curve = pd.read_csv(io.BytesIO(archive.read(prefix + 'returns.csv')))
            warmup = trial['result']['data']['warmup_observations']
            nav = np.r_[request.initial_capital, (1 + output.backtest.returns.iloc[warmup:]).cumprod().to_numpy() * request.initial_capital]
            np.testing.assert_allclose(curve['portfolio'], nav, rtol=1e-12, atol=1e-8)
            completed += 1
        oos_count = 0
        for reserved in project['oos']:
            trial = next(t for t in project['trials'] if t['id'] == reserved['trial_id'])
            dataset = json.loads(archive.read('datasets/' + reserved['dataset_id'] + '.json'))
            bundle = decode_bundle(dataset['snapshot'])
            result = pipeline_for(ResearchRequest.model_validate(trial['request'])).run(bundle)
            series = result.backtest.returns.iloc[reserved['partition']['development_observations']:]
            np.testing.assert_allclose(series.to_numpy(), [r['return'] for r in reserved['returns']], rtol=1e-12, atol=1e-12)
            if digest(clean_json(research_metrics(series))) != digest(reserved['metrics']):
                raise ValueError('Reserved OOS metric replay differs')
            oos_count += 1
        validations = [replay_survival(io.BytesIO(archive.read('validation/' + item['id'] + '.zip')))
                       for item in project['validations'] if item['status'] == 'completed']
    return {'verified': True, 'project_id': project['id'], 'development_trials': completed,
            'reserved_oos_results': oos_count, 'survival_replays': len(validations),
            'prospective_replayed': False, 'note': 'Forward observations are records, not recreated historical returns.'}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('export', type=Path)
    print(json.dumps(replay(parser.parse_args().export), indent=2))
