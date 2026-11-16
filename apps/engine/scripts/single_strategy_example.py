"""Fixed synthetic lifecycle example; no parameter selection or invented forward marks."""
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from apps.research_api import ResearchWorkspace
from research.projects.models import (Specification, DatasetRequest, TrialRequest,
                                      FreezeRequest, ForwardRequest)
from research.projects.service import ProjectService
from research.projects.report import export
from research.survival.service import SurvivalService


def example_spec():
    hypothesis = 'Positive trailing own-price returns persist sufficiently to survive predefined costs and chronological validation.'
    return Specification.model_validate({
        'thesis': {'title': 'SYNTHETIC single-strategy momentum lifecycle',
            'research_question': 'Does a fixed momentum rule survive costs and chronological validation?',
            'economic_hypothesis': hypothesis, 'mechanism': 'Gradual information diffusion may generate persistent price trends.',
            'holding_period': 'Weekly rebalance; variable position duration', 'alpha_source': 'Delayed information adjustment',
            'failure_conditions': 'Rapid reversals, trading costs and concentrated exposures may eliminate the effect.',
            'acceptance_criteria': 'Require integrity and review net walk-forward uncertainty before any empirical claim.',
            'rejection_criteria': 'Reject empirical promotion of synthetic data regardless of modeled performance.',
            'limitations': 'Seeded synthetic data tests mechanics only; it establishes no empirical market effect.'},
        'research': {'name': 'SYNTHETIC fixed momentum lifecycle', 'hypothesis': hypothesis, 'data_mode': 'demo',
            'symbols': ['AAPL', 'MSFT', 'AMZN', 'GOOGL', 'META', 'JPM', 'XOM', 'UNH'],
            'sleeves': [{'strategy': 'time_series_momentum', 'budget': 100, 'lookback': 63}], 'regime_enabled': False},
        'validation': {'bootstrap_samples': 100, 'cscv_blocks': 4, 'max_folds': 4},
        'signal_notes': 'Existing Q time-series momentum; fixed lookback 63. Source is archived with every trial.',
        'portfolio_notes': 'Signal weights with volatility targeting and position/gross/net limits.'})


def wait_for(predicate, timeout=180):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = predicate()
        if value:
            return value
        time.sleep(.05)
    raise RuntimeError('Lifecycle job did not complete within the example timeout')


def run_example(root):
    root.mkdir(parents=True, exist_ok=False)
    ws = ResearchWorkspace(root / 'experiments')
    survival = SurvivalService(ws)
    ws.survival_service = survival
    projects = ProjectService(ws, survival)
    ws.project_service = projects
    try:
        project = projects.create(example_spec())
        key = project['id']
        task = projects.capture(key, DatasetRequest(reason='Freeze the fixed seeded dataset before inspecting strategy outcomes.'))
        wait_for(lambda: projects._last(task['id'], 'completed') or projects._last(task['id'], 'failed'))
        data = projects.get(key)['datasets'][0]
        submitted = projects.trials(key, TrialRequest(revision_id=project['revision_id'], dataset_id=data['id'], reason='Run the prespecified 63-bar candidate without selecting a winning neighbor.'))
        trial_id = submitted['trial_ids'][0]
        wait_for(lambda: projects.trial(key, trial_id)['status'] in ('completed', 'failed'))
        trial = projects.trial(key, trial_id, inspect=True)
        if trial['status'] != 'completed':
            raise RuntimeError(trial['error'])
        validation = projects.validate(key, trial_id)
        wait_for(lambda: survival.get(validation['id'])['status'] in ('completed', 'failed'))
        task = projects.reveal(key, trial_id, 'Record one irreversible reveal of the reserved synthetic final segment.')
        wait_for(lambda: projects._last(task['id'], 'completed') or projects._last(task['id'], 'failed'))
        if projects._last(task['id'], 'failed'):
            raise RuntimeError(projects._last(task['id'], 'failed')['error'])
        frozen = projects.freeze(key, FreezeRequest(trial_id=trial_id, validation_id=validation['id'],
            reason='Freeze the fixed candidate as a mechanics demonstration, not an investment approval.',
            expectation_basis='No empirical return expectation is defensible from synthetic prices.'))
        projects.forward(key, ForwardRequest(strategy_version_id=frozen['strategy_version_id'],
            reason='Register an empty prospective protocol; no synthetic returns may be backfilled.'))
        paper = export(projects, key)
        (root / 'research-paper.md').write_text(paper, encoding='utf-8')
        (root / 'research-project.zip').write_bytes(export(projects, key, packed=True))
        state = projects.get(key)
        comparison = projects.comparison(key, frozen['strategy_version_id'])
        checks = {'single_strategy': len(state['spec']['research']['sleeves']) == 1,
            'reserved_data_excluded': trial['result']['data']['observations'] == data['partition']['development_observations'],
            'eighteen_layers': len(survival.get(validation['id'])['result']['layers']) == 18,
            'oos_reveal_recorded': state['integrity']['oos_reveals'] == 1,
            'immutable_freeze': projects.store.get(frozen['strategy_version_id'], 'project_freeze')['trial_id'] == trial_id,
            'prospective_empty': comparison['forward'][0]['observations'] == 0,
            'report_21_sections': paper.count('\n## ') == 21, 'live_disabled': not frozen['live_eligible']}
        assert all(checks.values()), checks
        summary = {'label': 'SYNTHETIC WORKFLOW DEMONSTRATION; NOT MARKET PERFORMANCE', 'project_id': key,
            'trial_id': trial_id, 'validation_id': validation['id'], 'strategy_version_id': frozen['strategy_version_id'],
            'checks': checks, 'validation': survival.get(validation['id'])['result']['summary'], 'comparison': comparison}
        (root / 'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False), encoding='utf-8')
        return summary
    finally:
        ws.executor.shutdown(wait=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    destination = args.output or Path(__file__).resolve().parents[3] / 'outputs/project-example' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    outcome = run_example(destination)
    print(json.dumps({'output': str(destination), 'project_id': outcome['project_id'], 'checks': outcome['checks']}, indent=2))
