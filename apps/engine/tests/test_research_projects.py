"""Lifecycle boundaries, not mirrored implementation or fabricated strategy success."""
import copy
import io
import json
import sqlite3
import zipfile
from datetime import datetime, timezone

import numpy as np
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from apps.research_api import ResearchWorkspace
from evidence.storage import Store, digest
from research.projects import api
from research.projects.models import (DatasetRequest, TrialRequest, Revision, ForwardRequest,
                                     FreezeRequest, Specification)
from research.projects.monitoring import compare
from research.projects.report import export
from research.projects.service import ProjectService, decode_bundle, encode_bundle
from research.survival.service import SurvivalService
from research.survival.forward import PaperEvent
from scripts.single_strategy_example import example_spec, run_example, wait_for


@pytest.fixture
def projects(tmp_path):
    ws = ResearchWorkspace(tmp_path / 'experiments')
    survival = SurvivalService(ws)
    service = ProjectService(ws, survival)
    yield service
    ws.executor.shutdown(wait=True)


@pytest.fixture(scope='module')
def completed(tmp_path_factory):
    root = tmp_path_factory.mktemp('projects') / 'example'
    summary = run_example(root)
    ws = ResearchWorkspace(root / 'experiments')
    service = ProjectService(ws, SurvivalService(ws))
    yield service, summary, root
    ws.executor.shutdown(wait=True)


def capture(service, project):
    task = service.capture(project, DatasetRequest(reason='Freeze inputs before any parameter trial is inspected.'))
    wait_for(lambda: service._last(task['id'], 'completed') or service._last(task['id'], 'failed'))
    assert not service._last(task['id'], 'failed')
    return service.get(project)['datasets'][0]


def test_hypothesis_versions_preserve_original_and_reject_stale_edits(projects):
    original = projects.create(example_spec())
    spec = example_spec()
    spec.thesis.mechanism = 'A revised economic mechanism with explicit falsification conditions.'
    revised = projects.revise(original['id'], Revision(parent_revision=original['revision_id'], spec=spec, reason='Refine the mechanism before evaluating another candidate.'))
    assert revised['revision_id'] != original['revision_id']
    assert projects.store.get(original['revision_id'], 'project_revision')['spec'] == original['spec']
    with pytest.raises(HTTPException) as error:
        projects.revise(original['id'], Revision(parent_revision=original['revision_id'], spec=spec, reason='This editor has an obsolete parent revision.'))
    assert error.value.status_code == 409


def test_one_strategy_and_hypothesis_contracts_fail_closed():
    spec = example_spec().model_dump()
    spec['research']['sleeves'][0]['budget'] = 90
    spec['research']['sleeves'].append({'strategy': 'mean_reversion', 'budget': 10, 'lookback': 20})
    with pytest.raises(ValueError, match='exactly one'):
        Specification.model_validate(spec)
    spec = example_spec().model_dump()
    spec['research']['hypothesis'] = 'An inconsistent executable hypothesis in the request.'
    with pytest.raises(ValueError, match='must match'):
        Specification.model_validate(spec)


def test_dataset_roundtrip_preserves_metadata_and_detects_changed_bytes(projects):
    project = projects.create(example_spec())
    data = capture(projects, project['id'])
    raw = projects.store.get(data['id'], 'project_dataset')['snapshot']
    bundle = decode_bundle(raw)
    assert bundle.metadata['data_mode'] == 'demo'
    assert encode_bundle(bundle)['dataset_hash'] == raw['dataset_hash']
    altered = copy.deepcopy(raw)
    altered['prices_csv'] += '\n'
    with pytest.raises(ValueError, match='fingerprint'):
        decode_bundle(altered)
    assert data['partition']['development_observations'] == 720
    assert data['partition']['holdout_observations'] == 180


@pytest.mark.parametrize('fraction', [.1, .3])
@pytest.mark.parametrize('revealed', [False, True])
def test_recapture_cannot_repartition_reserved_observations(projects, fraction, revealed):
    project = projects.create(example_spec())
    original = capture(projects, project['id'])
    if revealed:
        projects.store.event(project['id'], 'oos_revealed', {
            'dataset_id': original['id'], 'dataset_hash': original['dataset_hash'],
            'reason': 'Explicit prior access fixture; never reset this boundary.'})
    spec = example_spec()
    spec.holdout_fraction = fraction
    projects.revise(project['id'], Revision(parent_revision=project['revision_id'], spec=spec,
        reason='Attempt to change the partition of previously captured observations.'))
    task = projects.capture(project['id'], DatasetRequest(reason='Recapture identical bytes under an incompatible partition.'))
    outcome = wait_for(lambda: projects._last(task['id'], 'completed') or projects._last(task['id'], 'failed'))
    assert 'Reserved boundary is fixed' in outcome.get('error', '')
    state = projects.get(project['id'])
    assert len(state['datasets']) == 1
    assert state['datasets'][0]['partition'] == original['partition']
    assert any(e['action'] == 'task_failed' and e['body']['task_id'] == task['id'] for e in state['journal'])


def test_unchanged_recapture_retains_identical_reserved_boundary(projects):
    project = projects.create(example_spec())
    first = capture(projects, project['id'])
    second = capture(projects, project['id'])
    assert first['id'] != second['id']
    assert first['dataset_hash'] == second['dataset_hash']
    assert first['partition'] == second['partition']


def test_legacy_conflicting_partitions_block_new_trials_without_rewriting_history(projects):
    project = projects.create(example_spec())
    original = capture(projects, project['id'])
    legacy = copy.deepcopy(projects.store.get(original['id'], 'project_dataset'))
    legacy['partition']['development_observations'] = 810
    conflicting_id = projects.store.put('project_dataset', legacy)
    with pytest.raises(ValueError, match='Reserved boundary is fixed'):
        projects.trials(project['id'], TrialRequest(revision_id=project['revision_id'], dataset_id=original['id'],
            reason='Attempt reuse of historical conflicting partitions must fail closed.'))
    assert projects.store.get(conflicting_id, 'project_dataset') == legacy
    assert len(projects.get(project['id'])['datasets']) == 2


def test_failed_trials_and_queue_rejections_remain_in_the_journal(projects):
    project = projects.create(example_spec())
    data = capture(projects, project['id'])
    projects.ws.pending = 3
    attempted = projects.trials(project['id'], TrialRequest(revision_id=project['revision_id'], dataset_id=data['id'],
        lookbacks=[40, 63, 90], reason='Record every configuration even when queue admission is unavailable.'))
    projects.ws.pending = 0
    state = projects.get(project['id'])
    assert len(attempted['trial_ids']) == state['integrity']['failed_trials'] == state['integrity']['trial_count'] == 3
    assert all(t['error'] for t in state['trials'])
    assert len([e for e in state['journal'] if e['action'] == 'experiment_failed']) == 3


def test_runtime_failure_is_automatically_preserved(projects):
    project = projects.create(example_spec())
    data = capture(projects, project['id'])
    def broken(*args, **kwargs):
        raise ValueError('Deliberate unavailable research input')
    projects.ws.runner = broken
    trial = projects.trials(project['id'], TrialRequest(revision_id=project['revision_id'], dataset_id=data['id'], reason='Exercise visible failure without manufacturing returns.'))['trial_ids'][0]
    wait_for(lambda: projects.trial(project['id'], trial)['status'] == 'failed')
    state = projects.get(project['id'])
    assert state['trials'][0]['result'] is None
    assert 'Deliberate' in state['trials'][0]['error']
    assert any(e['action'] == 'experiment_failed' for e in state['journal'])


def test_cross_project_dataset_and_freeze_links_are_rejected(projects):
    first, other = projects.create(example_spec()), projects.create(example_spec())
    data = capture(projects, first['id'])
    with pytest.raises(ValueError, match='another project'):
        projects.trials(other['id'], TrialRequest(revision_id=other['revision_id'], dataset_id=data['id'], reason='Attempt a mismatched lineage reference for this test.'))


def test_complete_lifecycle_has_reserved_oos_and_empty_forward_record(completed):
    service, summary, _ = completed
    assert all(summary['checks'].values())
    project = service.get(summary['project_id'])
    trial = project['trials'][0]
    assert trial['result']['data']['observations'] == 720
    assert trial['result']['data']['end_date'] < project['datasets'][0]['partition']['holdout_start'][:10]
    assert project['oos'][0]['observations'] == 180
    assert project['oos'][0]['genuinely_unseen'] == 'UNKNOWN'
    assert summary['comparison']['forward'][0]['observations'] == 0
    assert all(r['prospective'] is None for r in summary['comparison']['table'])


def test_reveal_cannot_be_repeated_and_later_revisions_are_flagged(completed):
    service, summary, _ = completed
    with pytest.raises(HTTPException) as error:
        service.reveal(summary['project_id'], summary['trial_id'], 'Attempt repeated access to an already consumed final segment.')
    assert error.value.status_code == 409
    original = service.get(summary['project_id'])
    spec = Specification.model_validate(original['spec'])
    spec.thesis.notes = 'A later note after observed OOS is recorded as a new revision.'
    new = service.revise(original['id'], Revision(parent_revision=original['revision_id'], spec=spec, reason='Document a post-OOS interpretation without rewriting the original freeze.'))
    assert new['integrity']['post_oos_revisions'] >= 1
    assert service.store.get(summary['strategy_version_id'], 'project_freeze')['revision_id'] == original['revision_id']
    with pytest.raises(ValueError, match='current hypothesis'):
        service.freeze(original['id'], FreezeRequest(trial_id=summary['trial_id'], validation_id=summary['validation_id'],
            reason='Old candidate cannot stand in for a new research revision.', expectation_basis='Explicit expected metrics require a valid current candidate.'))


def test_frozen_artifacts_and_events_have_database_immutability(completed):
    service, summary, _ = completed
    with service.store.db() as db:
        with pytest.raises(sqlite3.IntegrityError, match='immutable'):
            db.execute('UPDATE artifacts SET body=? WHERE id=?', ('{}', summary['strategy_version_id']))
        with pytest.raises(sqlite3.IntegrityError, match='immutable'):
            db.execute('DELETE FROM events WHERE artifact=?', (summary['project_id'],))


def test_forward_cannot_reset_existing_evidence_or_promote_synthetic(completed):
    service, summary, _ = completed
    with pytest.raises(ValueError, match='already has'):
        service.forward(summary['project_id'], ForwardRequest(strategy_version_id=summary['strategy_version_id'], reason='Duplicate registration must not reset prospective evidence.'))
    with pytest.raises(ValueError, match='synthetic promotion'):
        service.forward(summary['project_id'], ForwardRequest(strategy_version_id=summary['strategy_version_id'], mode='automated', reason='Synthetic prices must not become a market paper deployment.'))
    forward = service.get(summary['project_id'])['forward'][0]
    with pytest.raises(ValueError, match='synthetic demonstration stays empty'):
        service.forward_event(summary['project_id'], forward['id'], PaperEvent(kind='signal', observed_at=datetime.now(timezone.utc), weights={'AAPL': .1}))


def test_snapshot_corruption_cannot_change_frozen_result(completed):
    service, summary, _ = completed
    trial = service.trial(summary['project_id'], summary['trial_id'])
    path = service.ws.directory(trial['run_id']) / 'result.json'
    before = path.read_bytes()
    try:
        damaged = json.loads(before)
        damaged['metrics']['total_return'] = 999
        path.write_text(json.dumps(damaged), encoding='utf-8')
        with pytest.raises(ValueError, match='experiment changed'):
            service.verify_trial_files(trial)
        assert service.trial(summary['project_id'], summary['trial_id'])['result']['metrics']['total_return'] != 999
    finally:
        path.write_bytes(before)


def test_reproducibility_pack_hashes_sections_and_existing_replay(completed, tmp_path):
    service, summary, root = completed
    with zipfile.ZipFile(root / 'research-project.zip') as archive:
        manifest = json.loads(archive.read('manifest.json'))
        assert all(digest(archive.read(name)) == fingerprint for name, fingerprint in manifest['files'].items())
        assert archive.read('report.md').decode().count('\n## ') == 21
        nested = archive.read('validation/' + summary['validation_id'] + '.zip')
    path = tmp_path / 'survival.zip'
    path.write_bytes(nested)
    from research.projects.replay import replay
    replayed = replay(root / 'research-project.zip')
    assert replayed['verified']
    assert replayed['development_trials'] == replayed['reserved_oos_results'] == replayed['survival_replays'] == 1


def test_export_never_exposes_reserved_bars_before_reveal(projects):
    project = projects.create(example_spec())
    data = capture(projects, project['id'])
    with zipfile.ZipFile(io.BytesIO(export(projects, project['id'], packed=True))) as archive:
        assert not any(name.startswith('datasets/') for name in archive.namelist())
        assert b'prices_csv' not in archive.read('project.json')
        assert b'benchmark_csv' not in archive.read('project.json')


def test_additive_migration_preserves_existing_artifacts(tmp_path):
    old = Store(tmp_path / 'survival')
    key = old.put('survival_result', {'legacy': True})
    ws = ResearchWorkspace(tmp_path / 'experiments')
    try:
        ProjectService(ws, SurvivalService(ws))
        assert old.get(key, 'survival_result') == {'legacy': True}
        with old.db() as db:
            assert db.execute('SELECT version FROM research_project_migrations').fetchall() == [(1,)]
    finally:
        ws.executor.shutdown(wait=True)


def test_rejected_candidate_requires_an_explicit_review_before_freeze(completed, monkeypatch):
    from apps.research_api import Decision
    service, summary, _ = completed
    frozen = service.store.get(summary['strategy_version_id'], 'project_freeze')
    revision = service.store.get(frozen['revision_id'], 'project_revision')
    # Scope this decision test to its original revision; another test records a later revision.
    monkeypatch.setattr(service, 'current', lambda project: (frozen['revision_id'], revision))
    service.decide(summary['project_id'], summary['trial_id'], Decision(status='rejected', rationale='Reject this fixture candidate pending a documented review.'))
    request = FreezeRequest(trial_id=summary['trial_id'], validation_id=summary['validation_id'],
                            reason='Exercise candidate decision requirements independently.', expectation_basis='No empirical expectation from fixture data.')
    with pytest.raises(ValueError, match='Candidate was rejected'):
        service.freeze(summary['project_id'], request)
    service.decide(summary['project_id'], summary['trial_id'], Decision(status='watchlist', rationale='Record an explicit reviewed decision for this contract test.'))
    assert service.freeze(summary['project_id'], request)['trial_id'] == summary['trial_id']


def test_project_paper_draft_persists_and_requires_feed_readiness(completed, tmp_path, monkeypatch):
    from paper.service import PaperService
    service, summary, _ = completed
    def disconnected(_):
        raise ValueError('Explicit test fixture has no configured feed')
    paper = PaperService(tmp_path / 'paper', disconnected)
    monkeypatch.setattr(service, 'paper_service', paper)
    # This fixture isolates post-eligibility wiring. Actual synthetic eligibility is
    # independently rejected above; no test price series is presented as market evidence.
    body = copy.deepcopy(service.store.get(summary['strategy_version_id'], 'project_freeze'))
    body.update(synthetic=False, paper_candidate_eligible=True, reason='Post-eligibility wiring fixture only')
    key = service.store.put('project_freeze', body)
    registered = service.forward(summary['project_id'], ForwardRequest(strategy_version_id=key, mode='automated',
        provider='fixture', reason='Test persistent draft integration with an unavailable feed.'))
    record = registered['record']
    assert record['status'] == 'draft'
    run_id = service.trial(summary['project_id'], summary['trial_id'])['run_id']
    assert record['config']['snapshots'][run_id]['strategy_version_id'] == key
    with pytest.raises(ValueError, match='no configured feed'):
        service.forward_control(summary['project_id'], registered['id'], 'activate')
    restarted = PaperService(tmp_path / 'paper', disconnected)
    assert restarted.get(record['id'])['config'] == record['config']
    assert restarted.get(record['id'])['accounts'] == record['accounts']
    comparison = service.comparison(summary['project_id'], key)
    assert comparison['forward'][0]['observations'] == 0
    assert comparison['forward'][0]['source'] == 'q_automated_simulation'
    assert all(row['prospective'] is None for row in comparison['table'])


def test_unavailable_executor_retains_failed_task_without_leaking_a_slot(projects):
    project = projects.create(example_spec())
    projects.ws.executor.shutdown(wait=True)
    with pytest.raises(RuntimeError):
        projects.capture(project['id'], DatasetRequest(reason='Retain an attempt rejected by a stopped executor.'))
    assert projects.ws.pending == 0
    assert projects.get(project['id'])['tasks'][0]['status'] == 'failed'


def test_independent_forward_comparison_and_alerts():
    frozen = {'expected_metrics': {'sharpe': .5}, 'expectation_basis': 'Predeclared expectation, not a forecast guarantee.',
              'kill': {'max_drawdown': .1, 'max_gross': .8, 'max_cost_drift_bps': 3, 'max_stale_days': 365, 'minimum_observations': 60}}
    record = {'source': 'user_recorded_paper', 'observations': 2, 'returns': [-.1, -.1], 'performance': None,
              'mean_cost_drift_bps': 4, 'as_of': datetime.now(timezone.utc).isoformat(),
              'events': [{'kind': 'observation', 'weights': {'A': .9}}]}
    evidence = {'result': {'metrics': {'total_return': .9, 'annualized_return': .12, 'annualized_volatility': .16},
                'validation': {'metrics': {'total_return': .2, 'annualized_return': .08, 'annualized_volatility': .2}},
                'risk': {'current_gross': .75}, 'data': {}}}
    result = compare(frozen, evidence, [{'metrics': {'annualized_return': -.04, 'annualized_volatility': .21}}],
                     [{'id': 'f', 'record_id': 'r', 'mode': 'manual', 'created_at': record['as_of'], 'evidence': record}])
    metrics = result['forward'][0]['metrics']
    assert metrics['total_return'] == pytest.approx(-.19)
    assert metrics['max_drawdown'] == pytest.approx(-.19)
    assert metrics['sharpe'] is metrics['volatility'] is None
    table = {row['metric']: row for row in result['table']}
    assert [table['cagr'][k] for k in ['historical', 'walk_forward', 'reserved_oos', 'prospective']] == [.12, .08, -.04, None]
    assert table['volatility']['historical'] == .16
    assert table['volatility']['reserved_oos'] == .21
    assert table['gross_exposure']['historical'] == .75
    assert metrics['hit_rate'] == 0
    assert {a['kind'] for a in result['alerts']} == {'drawdown', 'gross_exposure', 'cost_drift'}
    assert result['automatic_control'] is False


def test_project_api_contracts_use_existing_service(projects, monkeypatch):
    monkeypatch.setattr(api, 'service', lambda: projects)
    app = FastAPI()
    app.include_router(api.router)
    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=422)
    with TestClient(app) as client:
        assert client.post('/api/research/projects', json={'unrecognized': True}).status_code == 422
        response = client.post('/api/research/projects', json={'spec': example_spec().model_dump()})
        assert response.status_code == 201
        key = response.json()['id']
        assert client.get('/api/research/projects').json()['projects'][0]['id'] == key
        assert client.post(f'/api/research/projects/{key}/notes', json={'reason': 'Recorded rationale with explicit rejection considerations.'}).status_code == 201
        assert client.get(f'/api/research/projects/{key}/report').status_code == 200
        assert client.get('/api/research/projects/catalog').json()['schema_version'] == 1
