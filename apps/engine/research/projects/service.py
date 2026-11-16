"""Project lineage and orchestration. Calculations belong to the existing engines."""
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pandas as pd
from fastapi import HTTPException

from data.models import MarketDataBundle
from data.research_source import load_research_bundle
from evidence.storage import canonical, digest, now
from research.workspace import (ResearchRequest, clean_json, code_provenance,
                                make_demo_bundle, pipeline_for, research_metrics, subset_bundle)
from research.survival.models import SurvivalSubmission
from research.survival.forward import PaperRegistration
from .models import Specification


DATA_KEYS = ('data_mode', 'symbols', 'benchmark', 'period')


def encode_bundle(bundle):
    prices = pd.concat(bundle.ohlcv, names=['symbol', 'date']).sort_index().to_csv(float_format='%.17g')
    benchmark = bundle.benchmark.to_csv(float_format='%.17g')
    return {'prices_csv': prices, 'benchmark_csv': benchmark,
            'dataset_hash': digest((prices + benchmark).encode()), 'metadata': clean_json(bundle.metadata)}


def decode_bundle(snapshot):
    if digest((snapshot['prices_csv'] + snapshot['benchmark_csv']).encode()) != snapshot['dataset_hash']:
        raise ValueError('Project dataset fingerprint mismatch')
    frame = pd.read_csv(io.StringIO(snapshot['prices_csv']), index_col=[0, 1], parse_dates=[1], float_precision='round_trip')
    benchmark = pd.read_csv(io.StringIO(snapshot['benchmark_csv']), index_col=0, parse_dates=[0], float_precision='round_trip')
    return MarketDataBundle({str(s): f.droplevel(0) for s, f in frame.groupby(level=0)},
                            benchmark=benchmark, metadata=snapshot['metadata'])


class ProjectService:
    def __init__(self, workspace, survival, paper=None):
        self.ws, self.survival, self.store = workspace, survival, survival.store
        self.paper_service = paper
        self.run_trials = {}
        # Additive migration: existing artifact/event rows and triggers are reused.
        with self.store.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS research_project_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)')
            newer = db.execute('SELECT MAX(version) FROM research_project_migrations').fetchone()[0]
            if newer and newer > 1:
                raise ValueError('Project database requires a newer Q version')
            db.execute('INSERT OR IGNORE INTO research_project_migrations VALUES(1,?)', (now(),))
        for trial in self.store.list('project_trial'):
            launched = self._last(trial['id'], 'launched')
            if launched:
                self.run_trials[launched['run_id']] = trial['id']
            elif not self._last(trial['id'], 'failed'):
                self.store.event(trial['id'], 'failed', {'error': 'Interrupted before queue admission; attempt retained'})
        self.ws.listeners.append(self._research_updated)
        for run_id in self.run_trials:
            self._research_updated(self.ws.get(run_id))
        for task in self.store.list('project_task'):
            if not self._last(task['id'], 'completed') and not self._last(task['id'], 'failed'):
                self.store.event(task['id'], 'failed', {'error': 'Engine restarted; task retained, submit a new attempt.'})
                self.store.event(task['project_id'], 'task_failed', {'task_id': task['id'], 'kind': task['kind'], 'reason': 'Engine restarted'})

    def _last(self, key, action):
        return next((e['body'] for e in reversed(self.store.events(key)) if e['action'] == action), None)

    def _owned(self, project, key, kind):
        body = self.store.get(key, kind)
        if body.get('project_id') != project:
            raise ValueError('Artifact belongs to another project')
        return body

    def _assert_partition(self, project, dataset_hash, cutoff):
        """Recapture cannot expose reserved bars or relabel development as unseen.

        Check all captures, including old conflicting records, without rewriting
        their history. This is local access discipline, not external certification.
        """
        for row in self.store.list('project_dataset'):
            if row['project_id'] != project or row['snapshot']['dataset_hash'] != dataset_hash:
                continue
            prior = self.store.get(row['id'], 'project_dataset')
            if prior['partition']['development_observations'] != cutoff:
                raise ValueError('Reserved boundary is fixed for identical dataset bytes in this project. '
                                 'Use the original partition; conflicting historical captures remain preserved '
                                 'and cannot support new trials, validation, reveal or promotion.')

    def _check_dataset_partition(self, project, dataset_id):
        data = self._owned(project, dataset_id, 'project_dataset')
        self._assert_partition(project, data['snapshot']['dataset_hash'],
                               data['partition']['development_observations'])
        return data

    def current(self, project):
        self.store.get(project, 'research_project')
        revision = self._last(project, 'hypothesis_versioned')['revision_id']
        return revision, self.store.get(revision, 'project_revision')

    def create(self, spec):
        with self.ws.lock:
            key = self.store.put('research_project', {'schema_version': 1, 'created_at': now(), 'nonce': uuid4().hex})
            self._revision(key, spec, None, 'Initial falsifiable research specification')
            return self.get(key)

    def _revision(self, project, spec, parent, reason):
        import inspect
        from research.workspace import CATALOG
        strategy = spec.research.sleeves[0].strategy
        if parent:
            prior = self.store.get(parent, 'project_revision')['spec']['research']['sleeves'][0]['strategy']
            if prior != spec.research.sleeves[0].strategy:
                raise ValueError('A different strategy belongs in a new research project')
        body = {'project_id': project, 'parent_revision': parent, 'created_at': now(),
                'spec': spec.model_dump(), 'reason': reason,
                'signal_contract': {'catalogue_id': strategy, 'definition': CATALOG[strategy][4],
                    'class': CATALOG[strategy][0].__module__ + '.' + CATALOG[strategy][0].__name__,
                    'algorithm_source': inspect.getsource(CATALOG[strategy][0]),
                    'lookback': spec.research.sleeves[0].lookback,
                    'warmup': max(126, spec.research.sleeves[0].lookback + 2),
                    'rebalance': spec.research.rebalance, 'missing_values': 'Existing catalogue implementation, archived below; project notes do not override code'},
                'post_oos': any(e['action'] == 'oos_revealed' for e in self.store.events(project))}
        key = self.store.put('project_revision', body)
        self.store.event(project, 'hypothesis_versioned', {'revision_id': key, 'parent_revision': parent, 'reason': reason, 'post_oos': body['post_oos']})
        return key

    def revise(self, project, request):
        with self.ws.lock:
            current, _ = self.current(project)
            if current != request.parent_revision:
                raise HTTPException(409, 'Specification changed; refresh before saving a new revision')
            self._revision(project, request.spec, current, request.reason)
            return self.get(project)

    def reference(self, project, reference):
        with self.ws.lock:
            revision, _ = self.current(project)
            if reference.related_trial:
                self._owned(project, reference.related_trial, 'project_trial')
            key = self.store.put('project_reference', {'project_id': project, 'revision_id': revision, 'created_at': now(), **reference.model_dump()})
            self.store.event(project, 'literature_added', {'reference_id': key})
            return {'id': key}

    def note(self, project, reason):
        with self.ws.lock:
            revision, _ = self.current(project)
            self.store.event(project, 'research_note', {'revision_id': revision, 'reason': reason})
            return {'recorded': True}

    def _queue(self, project, kind, payload, operation):
        if self.ws.pending >= 3:
            raise HTTPException(429, 'Three computations are already queued or running')
        task = self.store.put('project_task', {'project_id': project, 'kind': kind, 'payload': payload, 'created_at': now(), 'nonce': uuid4().hex})
        self.store.event(task, 'queued', {})
        self.store.event(project, kind + '_requested', {'task_id': task, **payload})
        self.ws.pending += 1

        def execute():
            try:
                self.store.event(task, 'running', {})
                result = operation()
                self.store.event(task, 'completed', result)
                self.store.event(project, kind + '_completed', {'task_id': task, **result})
            except Exception as exc:
                error = f'{type(exc).__name__}: {str(exc)[:700]}'
                self.store.event(task, 'failed', {'error': error})
                self.store.event(project, 'task_failed', {'task_id': task, 'kind': kind, 'reason': error})
            finally:
                with self.ws.lock:
                    self.ws.pending -= 1
        try:
            self.ws.executor.submit(execute)
        except RuntimeError as exc:
            self.ws.pending -= 1
            self.store.event(task, 'failed', {'error': str(exc)[:700]})
            self.store.event(project, 'task_failed', {'task_id': task, 'kind': kind, 'reason': 'Queue unavailable'})
            raise
        return {'id': task, 'status': 'queued'}

    def capture(self, project, request):
        with self.ws.lock:
            revision, body = self.current(project)
            spec = Specification.model_validate(body['spec'])

            def capture():
                research = spec.research
                if request.prior_run_id:
                    job, archived = self.survival._snapshot(request.prior_run_id)
                    if any(job['request'][k] != research.model_dump()[k] for k in DATA_KEYS):
                        raise ValueError('Prior dataset does not match the project mandate')
                    bundle = decode_bundle(archived)
                else:
                    bundle = make_demo_bundle() if research.data_mode == 'demo' else load_research_bundle(
                        research.symbols, research.benchmark, research.period, source=research.data_mode)
                    if research.data_mode == 'demo':
                        if set(research.symbols) - set(bundle.ohlcv):
                            raise ValueError('Seeded demo supports the documented demo universe only')
                        bundle = MarketDataBundle({s: bundle.ohlcv[s] for s in research.symbols}, bundle.benchmark, metadata=bundle.metadata)
                prices = bundle.close()
                if prices.empty or prices.index.has_duplicates or not prices.index.is_monotonic_increasing:
                    raise ValueError('Dataset must be nonempty, unique and chronological')
                cutoff = int(len(prices) * (1 - spec.holdout_fraction))
                if cutoff < research.train_window + 2 * research.test_window or len(prices) - cutoff < 20:
                    raise ValueError('Insufficient data for development walk-forward and a reserved final segment')
                snapshot = encode_bundle(bundle)
                self._assert_partition(project, snapshot['dataset_hash'], cutoff)
                key = self.store.put('project_dataset', {'project_id': project, 'revision_id': revision,
                    'created_at': now(), 'request': {k: research.model_dump()[k] for k in DATA_KEYS},
                    'snapshot': snapshot, 'reason': request.reason, 'prior_run_id': request.prior_run_id,
                    'lineage': {'source': bundle.metadata.get('source', research.data_mode), 'universe': list(bundle.ohlcv),
                        'start': str(prices.index[0]), 'end': str(prices.index[-1]), 'frequency': '1d',
                        'corporate_actions': bundle.metadata.get('adjustment', 'Provider convention; completeness not independently verified'),
                        'survivorship': 'Selected universe; point-in-time constituents/delistings not verified',
                        'missing_data': 'No implicit backfill; existing engine integrity checks apply',
                        'transformations': 'Archived provider/demo OHLCV; no project transformation',
                        'filters': 'Explicit universe only'},
                    'partition': {'development_observations': cutoff, 'development_end': str(prices.index[cutoff - 1]),
                        'holdout_start': str(prices.index[cutoff]), 'holdout_end': str(prices.index[-1]),
                        'holdout_observations': len(prices) - cutoff,
                        'label': 'Pseudo-OOS: history previously inspected' if request.prior_run_id or spec.prior_exposure == 'previously_inspected'
                                 else 'Reserved retrospective holdout; external prior exposure unknown'}})
                return {'dataset_id': key, 'revision_id': revision, 'dataset_hash': snapshot['dataset_hash']}
            return self._queue(project, 'dataset', {'revision_id': revision, 'reason': request.reason}, capture)

    def trials(self, project, request):
        with self.ws.lock:
            revision, body = self.current(project)
            if revision != request.revision_id:
                raise HTTPException(409, 'Use the current hypothesis revision')
            data = self._check_dataset_partition(project, request.dataset_id)
            spec = Specification.model_validate(body['spec'])
            if any(data['request'][k] != spec.research.model_dump()[k] for k in DATA_KEYS):
                raise ValueError('Dataset identity differs from the current mandate; capture another snapshot')
            if int(len(decode_bundle(data['snapshot']).close()) * (1 - spec.holdout_fraction)) != data['partition']['development_observations']:
                raise ValueError('Partition changed; capture a new version, prior reveals remain visible')
            lookbacks = request.lookbacks or [spec.research.sleeves[0].lookback]
            if len(set(lookbacks)) != len(lookbacks) or any(not 5 <= value <= 252 for value in lookbacks):
                raise ValueError('Use unique catalogue lookbacks between 5 and 252')
            created = []
            # Each attempted configuration is retained, including admission failures.
            for lookback in lookbacks:
                values = spec.research.model_dump()
                values['sleeves'][0]['lookback'] = lookback
                for name in ('rebalance', 'commission_bps', 'slippage_bps'):
                    if getattr(request, name) is not None:
                        values[name] = getattr(request, name)
                mandate = ResearchRequest.model_validate(values)
                trial = self.store.put('project_trial', {'project_id': project, 'revision_id': revision,
                    'dataset_id': request.dataset_id, 'created_at': now(), 'nonce': uuid4().hex,
                    'request': mandate.model_dump(), 'reason': request.reason,
                    'post_oos': any(e['action'] == 'oos_revealed' for e in self.store.events(project)),
                    'inspected_prior_trials': [e['body']['trial_id'] for e in self.store.events(project) if e['action'] == 'results_inspected']})
                self.store.event(project, 'trial_attempted', {'trial_id': trial, 'reason': request.reason, 'lookback': lookback})
                try:
                    bundle = decode_bundle(data['snapshot'])
                    bundle = subset_bundle(bundle, bundle.close().index[:data['partition']['development_observations']])
                    bundle.metadata = {**bundle.metadata, 'project_dataset_id': request.dataset_id,
                                       'project_partition': 'Development only; reserved final segment excluded'}
                    job = self.ws.submit(mandate, bundle=bundle)
                    self.run_trials[job['run_id']] = trial
                    self.store.event(trial, 'launched', {'run_id': job['run_id']})
                    self.store.event(project, 'experiment_launched', {'trial_id': trial, 'run_id': job['run_id']})
                except Exception as exc:
                    self.store.event(trial, 'failed', {'error': str(exc.detail if isinstance(exc, HTTPException) else exc)[:700]})
                    self.store.event(project, 'experiment_failed', {'trial_id': trial, 'reason': 'Submission failed; attempt retained'})
                created.append(trial)
            return {'trial_ids': created}

    def _research_updated(self, job):
        trial = self.run_trials.get(job['run_id'])
        if not trial or job['status'] not in ('completed', 'failed') or self._last(trial, 'completed') or self._last(trial, 'failed'):
            return
        body = self.store.get(trial, 'project_trial')
        if job['status'] == 'failed':
            self.store.event(trial, 'failed', {'error': job['error']})
            self.store.event(body['project_id'], 'experiment_failed', {'trial_id': trial, 'reason': job['error']})
            return
        complete = self.ws.get(job['run_id'])
        _, snapshot = self.survival._snapshot(job['run_id'])
        path = self.ws.directory(job['run_id'])
        source = self.store.put('survival_source', {'source_sha256': complete['result']['provenance']['source_sha256'], 'zip_hex': (path / 'source.zip').read_bytes().hex()})
        evidence = self.store.put('project_evidence', {'project_id': body['project_id'], 'trial_id': trial,
            'run_id': job['run_id'], 'result': complete['result'], 'snapshot': snapshot, 'source_id': source,
            'files': {name: (path / name).read_text(encoding='utf-8') for name in ('targets.csv', 'executed_weights.csv', 'returns.csv')}})
        self.store.event(trial, 'completed', {'evidence_id': evidence})
        self.store.event(body['project_id'], 'experiment_completed', {'trial_id': trial, 'evidence_id': evidence})

    def trial(self, project, key, inspect=False):
        body = self._owned(project, key, 'project_trial')
        events = self.store.events(key)
        latest = events[-1] if events else {'action': 'queued', 'body': {}}
        evidence = self.store.get(latest['body']['evidence_id'], 'project_evidence') if latest['action'] == 'completed' else None
        if inspect and evidence and not any(e['action'] == 'results_inspected' and e['body']['trial_id'] == key for e in self.store.events(project)):
            self.store.event(project, 'results_inspected', {'trial_id': key, 'scope': 'Development results exposed by Q project API'})
        launched = self._last(key, 'launched')
        status = latest['action']
        if status == 'launched':
            status = self.ws.get(launched['run_id'])['status']
        return {'id': key, **body, 'status': status, 'run_id': launched['run_id'] if launched else None,
                'error': latest['body'].get('error'), 'evidence_id': latest['body'].get('evidence_id'),
                'result': evidence['result'] if evidence else None}

    def validate(self, project, trial_id):
        with self.ws.lock:
            trial = self.trial(project, trial_id)
            if trial['status'] != 'completed':
                raise ValueError('Validation requires a completed project trial')
            self.verify_trial_files(trial)
            revision = self.store.get(trial['revision_id'], 'project_revision')
            submission = SurvivalSubmission(experiment_id=trial['run_id'], config=revision['spec']['validation'])
            run = self.survival.submit(submission)
            self.store.event(project, 'validation_launched', {'trial_id': trial_id, 'validation_id': run['id']})
            return run

    def decide(self, project, trial_id, decision):
        with self.ws.lock:
            trial = self.trial(project, trial_id)
            if decision.status == 'paper_candidate':
                raise ValueError('Use a validated project freeze and forward registration to select a paper candidate')
            result = self.ws.decide(trial['run_id'], decision)
            self.store.event(project, 'experiment_decision_recorded', {'trial_id': trial_id, **decision.model_dump()})
            return result

    def verify_trial_files(self, trial):
        self._check_dataset_partition(trial['project_id'], trial['dataset_id'])
        sealed = self.store.get(trial['evidence_id'], 'project_evidence')
        current = self.ws.get(trial['run_id'])
        if digest(current.get('result')) != digest(sealed['result']) or current['request'] != trial['request']:
            raise ValueError('Archived experiment changed; immutable project evidence is preserved')
        _, snapshot = self.survival._snapshot(trial['run_id'])
        if snapshot['dataset_hash'] != sealed['snapshot']['dataset_hash']:
            raise ValueError('Archived dataset no longer matches immutable project evidence')
        return sealed

    def reveal(self, project, trial_id, reason):
        with self.ws.lock:
            trial = self.trial(project, trial_id)
            if trial['status'] != 'completed':
                raise ValueError('Select a completed development trial')
            data = self._check_dataset_partition(project, trial['dataset_id'])
            if any(e['action'] == 'oos_revealed' and e['body']['dataset_hash'] == data['snapshot']['dataset_hash'] for e in self.store.events(project)):
                raise HTTPException(409, 'This dataset holdout has been consumed; inspect the retained result, do not relabel new tuning as unseen')
            if self.ws.pending >= 3:
                raise HTTPException(429, 'Wait for an available computation slot')
            self.store.event(project, 'oos_revealed', {'trial_id': trial_id, 'dataset_id': trial['dataset_id'],
                'dataset_hash': data['snapshot']['dataset_hash'], 'reason': reason, 'label': data['partition']['label']})

            def evaluate():
                bundle = decode_bundle(data['snapshot'])
                result = pipeline_for(ResearchRequest.model_validate(trial['request'])).run(bundle)
                cut = data['partition']['development_observations']
                series = result.backtest.returns.iloc[cut:]
                source_dir = Path(self.store.root) / 'sources' / uuid4().hex
                source_dir.mkdir(parents=True)
                provenance = code_provenance(source_dir)
                if provenance['source_sha256'] != trial['result']['provenance']['source_sha256']:
                    raise ValueError('Engine changed since the candidate trial; run a new development trial. Holdout access attempt remains recorded.')
                body = {'project_id': project, 'trial_id': trial_id, 'created_at': now(),
                    'dataset_id': trial['dataset_id'], 'partition': data['partition'], 'provenance': provenance,
                    'metrics': clean_json(research_metrics(series)), 'observations': len(series),
                    'returns': [{'date': str(date), 'return': float(value)} for date, value in series.items()],
                    'label': data['partition']['label'], 'genuinely_unseen': 'UNKNOWN'}
                return {'oos_id': self.store.put('project_oos', body), 'trial_id': trial_id}
            return self._queue(project, 'oos', {'trial_id': trial_id, 'reason': reason}, evaluate)

    def freeze(self, project, request):
        with self.ws.lock:
            revision, spec = self.current(project)
            trial = self.trial(project, request.trial_id)
            if trial['revision_id'] != revision or trial['status'] != 'completed':
                raise ValueError('Freeze requires a completed trial from the current hypothesis revision')
            if trial['request'] != spec['spec']['research']:
                raise ValueError('Candidate differs from the current signal/portfolio specification; revise it and rerun before freezing')
            evidence = self.verify_trial_files(trial)
            decisions = [e['body'] for e in self.store.events(project) if e['action'] == 'experiment_decision_recorded' and e['body']['trial_id'] == trial['id']]
            if decisions and decisions[-1]['status'] == 'rejected':
                raise ValueError('Candidate was rejected; record an explicit reviewed decision before freezing')
            validation = self.survival.get(request.validation_id)
            if validation['experiment_id'] != trial['run_id'] or validation['status'] != 'completed':
                raise ValueError('Freeze requires completed validation for this exact candidate')
            if validation['config'] != spec['spec']['validation']:
                raise ValueError('Validation must use the versioned project protocol')
            if not validation['result']['summary']['research_gates_satisfied']:
                raise ValueError('Resolve integrity failures, required unavailable evidence and configured failure gates before freezing')
            if validation['result']['provenance']['code']['source_sha256'] != evidence['result']['provenance']['source_sha256']:
                raise ValueError('Trial and validation used different engine sources; rerun the candidate')
            body = {'project_id': project, 'revision_id': revision, 'trial_id': trial['id'],
                'dataset_id': trial['dataset_id'], 'evidence_id': trial['evidence_id'], 'validation_id': request.validation_id,
                'validation_result_id': validation['result_id'], 'source_id': evidence['source_id'],
                'created_at': now(), 'specification': spec['spec'], 'candidate': trial['request'],
                'expected_metrics': request.expected_metrics, 'expectation_basis': request.expectation_basis,
                'kill': request.kill.model_dump(), 'reason': request.reason,
                'provenance': evidence['result']['provenance'], 'dataset_hash': evidence['snapshot']['dataset_hash'],
                'oos': [r['id'] for r in self.store.list('project_oos') if r['project_id'] == project and r['trial_id'] == trial['id']],
                'paper_candidate_eligible': bool(evidence['result']['paper_candidate_eligible']),
                'live_eligible': False, 'synthetic': trial['request']['data_mode'] in ('demo', 'synthetic')}
            key = self.store.put('project_freeze', body)
            self.store.event(project, 'specification_frozen', {'strategy_version_id': key, 'trial_id': trial['id'], 'reason': request.reason})
            return {'strategy_version_id': key, **body}

    def forward(self, project, request):
        with self.ws.lock:
            frozen = self._owned(project, request.strategy_version_id, 'project_freeze')
            if any(r['project_id'] == project and r['strategy_version_id'] == request.strategy_version_id and r['mode'] == request.mode for r in self.store.list('project_forward')):
                raise ValueError('This version already has that forward registration; retain its evidence instead of resetting it')
            trial = self.trial(project, frozen['trial_id'])
            self.verify_trial_files(trial)
            mandate = frozen['candidate']
            if request.mode == 'manual':
                record = self.survival.register_paper(PaperRegistration(experiment_id=trial['run_id'], initial_nav=mandate['initial_capital']))
            else:
                if frozen['synthetic'] or not frozen['paper_candidate_eligible']:
                    raise ValueError('Automated paper requires observed data and the original mandate gates; synthetic promotion remains blocked')
                from paper.models import Deployment
                from paper.api import service
                paper = self.paper_service or service()
                if not mandate['long_only'] or mandate['max_gross_exposure'] > 1:
                    raise ValueError('Existing paper accounting supports long-only cash accounts')
                source_dir = Path(self.store.root) / 'sources' / uuid4().hex
                source_dir.mkdir(parents=True)
                if code_provenance(source_dir)['source_sha256'] != frozen['provenance']['source_sha256']:
                    raise ValueError('Installed engine differs from the frozen research source; validate and freeze a new candidate before automated paper')
                cfg = Deployment(name=frozen['specification']['thesis']['title'], market=frozen['specification']['market'],
                    currency='INR' if frozen['specification']['market'] == 'IN' else 'USD', provider=request.provider,
                    universe=mandate['symbols'], capital=mandate['initial_capital'], rebalance=mandate['rebalance'],
                    commission_bps=mandate['commission_bps'], slippage_bps=mandate['slippage_bps'],
                    participation=frozen['specification']['validation']['participation_rate'],
                    max_asset_weight=mandate['max_asset_weight'], max_gross=mandate['max_gross_exposure'],
                    drawdown_limit=min(mandate['drawdown_limit'], frozen['kill']['max_drawdown']),
                    strategies=[{'name': mandate['name'], 'adapter': 'research', 'reference': trial['run_id'], 'parameters': mandate}])
                record = paper.create(cfg, {trial['run_id']: {'request': mandate, 'strategy_version_id': request.strategy_version_id,
                                                            'source': frozen['provenance']}})
            key = self.store.put('project_forward', {'project_id': project, 'strategy_version_id': request.strategy_version_id,
                'record_id': record['id'], 'mode': request.mode, 'created_at': now(), 'reason': request.reason})
            self.store.event(project, 'forward_registered', {'forward_id': key, 'strategy_version_id': request.strategy_version_id,
                                                          'mode': request.mode, 'record_id': record['id']})
            return {'id': key, 'record': record}

    def forward_event(self, project, forward_id, event):
        with self.ws.lock:
            link = self._owned(project, forward_id, 'project_forward')
            frozen = self.store.get(link['strategy_version_id'], 'project_freeze')
            if link['mode'] != 'manual' or frozen['synthetic']:
                raise ValueError('Only an observed-data manual protocol accepts user-recorded prospective events; synthetic demonstration stays empty')
            result = self.survival.append_paper(link['record_id'], event)
            self.store.event(project, 'forward_event_recorded', {'forward_id': forward_id, 'event_id': result['id'], 'kind': event.kind})
            return result

    def forward_control(self, project, forward_id, action):
        with self.ws.lock:
            link = self._owned(project, forward_id, 'project_forward')
            if link['mode'] != 'automated':
                raise ValueError('Manual records do not control a paper deployment')
            from paper.api import service
            result = (self.paper_service or service()).control(link['record_id'], action)
            self.store.event(project, 'deployment_' + action, {'forward_id': forward_id, 'record_id': link['record_id']})
            return result

    def comparison(self, project, version):
        from .monitoring import compare
        frozen = {'id': version, **self._owned(project, version, 'project_freeze')}
        records = []
        for link in self.store.list('project_forward'):
            if link['project_id'] != project or link['strategy_version_id'] != version:
                continue
            if link['mode'] == 'manual':
                record = self.survival.paper(link['record_id'])
            else:
                from paper.api import evidence_for, service
                paper = self.paper_service or service()
                record = evidence_for(paper, link['record_id'])
                record['deployment'] = paper.get(link['record_id'])
            records.append({**link, 'evidence': record})
        evidence = self.store.get(frozen['evidence_id'], 'project_evidence')
        oos = [self.store.get(key, 'project_oos') for key in frozen['oos']]
        return compare(frozen, evidence, oos, records)

    def get(self, project, inspect=False):
        with self.ws.lock:
            revision, current = self.current(project)
            select = lambda kind: [r for r in self.store.list(kind) if r.get('project_id') == project]
            trials = [self.trial(project, r['id'], inspect=inspect) for r in select('project_trial')]
            datasets = [{k: v for k, v in r.items() if k != 'snapshot'} | {'dataset_hash': r['snapshot']['dataset_hash']} for r in select('project_dataset')]
            tasks = [{**r, 'status': self.store.events(r['id'])[-1]['action'], 'outcome': self.store.events(r['id'])[-1]['body']} for r in select('project_task')]
            validation = []
            for entry in self.store.events(project):
                if entry['action'] != 'validation_launched':
                    continue
                run = self.survival.get(entry['body']['validation_id'])
                validation.append({'trial_id': entry['body']['trial_id'], **run})
                action = 'validation_' + run['status']
                if run['status'] in ('completed', 'failed') and not any(e['action'] == action and e['body'].get('validation_id') == run['id'] for e in self.store.events(project)):
                    self.store.event(project, action, {'validation_id': run['id'], 'summary': run['result']['summary'] if run['result'] else None, 'error': run['error']})
            events = self.store.events(project)
            validation_ids = {v['id'] for v in validation}
            diagnostic_trials = [t for t in self.store.list('survival_trial') if t['run_id'] in validation_ids]
            return {'id': project, 'revision_id': revision, 'spec': current['spec'], 'revisions': select('project_revision'),
                'datasets': datasets, 'trials': trials, 'references': select('project_reference'), 'tasks': tasks,
                'validations': validation, 'oos': select('project_oos'), 'freezes': select('project_freeze'),
                'forward': select('project_forward'), 'journal': events, 'diagnostic_trials': diagnostic_trials,
                'integrity': {'trial_count': len(trials), 'failed_trials': sum(t['status'] == 'failed' for t in trials),
                    'survival_parameter_attempts': len(diagnostic_trials),
                    'oos_reveals': sum(e['action'] == 'oos_revealed' for e in events),
                    'post_oos_revisions': sum(r['post_oos'] for r in select('project_revision')),
                    'genuinely_unseen_oos': 'UNKNOWN', 'live_execution': 'NOT SUPPORTED',
                    'data_lineage': 'VERIFIED: content hashes', 'lookahead': 'TESTED: existing Survival prefix checks; not a proof',
                    'survivorship': 'WARNING: selected universe', 'inference': 'WARNING: recorded trials do not capture external research'}}

    def list(self):
        return [{'id': row['id'], 'created_at': row['created_at'],
                 'title': self.current(row['id'])[1]['spec']['thesis']['title']} for row in self.store.list('research_project')]
