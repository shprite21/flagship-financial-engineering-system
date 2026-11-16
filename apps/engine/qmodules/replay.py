"""Replay deterministic modules; never re-request news or generated AI responses."""
import json
from pathlib import Path
import sys
import tempfile

from evidence.storage import Store, canonical, digest
from .service import ACTIONS, PROVENANCE


def stable(result):
    result = json.loads(canonical(result))
    if 'native_code' in result:
        # Machine/compiler identity is retained separately; timers are not reproducible.
        result['native_code'].pop('binary_sha256')
        for section in result.get('results', {}).values():
            for key in ('total_ms', 'throughput'):
                section.get('metrics', {}).pop(key, None)
    return result


def replay(path, build_folder=None):
    record = json.loads(Path(path).read_text('utf-8'))
    action = record['action']
    if action not in {'economy-simulation', 'intelligence-search', 'intelligence-semantic-search'}:
        raise ValueError('Only native economy trajectories and report retrieval are deterministic replay actions. News, AI and benchmark timings remain recorded observations.')
    if record['code'] != PROVENANCE:
        raise ValueError('Source or dependency fingerprints differ; use the recorded environment')
    if {k: digest(v.encode()) for k, v in record['source_files'].items()} != record['code']['source_hashes']:
        raise ValueError('Embedded source integrity failure')
    schema, compute = ACTIONS[action]
    if action == 'intelligence-semantic-search':
        from .semantic import rank
        inputs = record['inputs']
        if digest({'kind': 'intelligence_index', 'body': inputs['index']}) != inputs['index_id']:
            raise ValueError('Frozen semantic index identity mismatch')
        if inputs['index_id'] != record['configuration']['index_id']:
            raise ValueError('Semantic index does not match the request')
        actual = rank(inputs['index'], inputs['query_vector'], schema.model_validate(record['configuration']).top_k)
        if actual != record['results']['Report evidence']['citations']:
            raise ValueError('Recomputed semantic ranking differs from saved evidence')
        return {'verified': True, 'action': action, 'embedding_generation_reproduced': False}
    with tempfile.TemporaryDirectory(prefix='q-module-replay-') as folder:
        db = Store(folder)
        if action == 'intelligence-search':
            for document in record['inputs']['documents']:
                if db.put('intelligence_document', document['artifact']) != document['id']:
                    raise ValueError('Frozen document integrity failure')
        if build_folder is not None and action == 'economy-simulation':
            # Reuse a compiler cache only via a caller-supplied local root, never artifact paths.
            db.root = Path(build_folder)
        actual = compute(schema.model_validate(record['configuration']), db)
        expected = {key: record[key] for key in actual}
        if stable(actual) != stable(expected):
            raise ValueError('Recomputed result differs from frozen evidence')
    return {'verified': True, 'action': action, 'timings_reproduced': False if action == 'economy-simulation' else None,
            'native_binary_identical': actual.get('native_code', {}).get('binary_sha256') == record.get('native_code', {}).get('binary_sha256') if action == 'economy-simulation' else None}


if __name__ == '__main__':
    print(json.dumps(replay(sys.argv[1])))
