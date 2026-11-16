import assert from 'node:assert/strict';
import test from 'node:test';
import { projectComparison } from '../lib/flagship/project-comparison.ts';

const hash = letter => letter.repeat(64);
function fixture() {
  const request = { sleeves: [{ lookback: 63 }], initial_capital: 100, data_mode: 'demo', benchmark: 'SPY', train_window: 252, test_window: 63 };
  const result = { request, data: { snapshot_sha256: hash('b'), evaluation_start: '2024-01-02', end_date: '2024-01-03', currency: 'USD' },
    provenance: { source_sha256: hash('c'), execution: { execution_lag: 1, drift_between_rebalances: true } },
    equity_curve: [{ date: '2024-01-01', portfolio: 100 }, { date: '2024-01-02', portfolio: 90 }, { date: '2024-01-03', portfolio: 99 }] };
  const trial = { id: 'first', dataset_id: 'dataset', status: 'completed', request, result };
  return { trials: [trial, { ...structuredClone(trial), id: 'second' }], datasets: [{ id: 'dataset', dataset_hash: hash('a') }],
    validations: [{ id: 'prior', trial_id: 'second', status: 'completed' }, { id: 'latest', trial_id: 'second', status: 'failed' }],
    journal: [{ action: 'experiment_decision_recorded', body: { trial_id: 'second', status: 'rejected' } }] };
}

test('comparison preserves first-period losses, scale, negative decisions and immutable inputs', () => {
  const project = fixture();
  const other = project.trials[1].result;
  other.request.initial_capital = 1000;
  other.equity_curve.forEach(row => { row.portfolio *= 10; });
  const before = structuredClone(project);
  const view = projectComparison(project, ['first', 'second']);
  assert.deepEqual(view.issues, []);
  assert.deepEqual(view.curve.map(row => row.date), ['2024-01-01', '2024-01-02', '2024-01-03']);
  assert.equal(view.curve[0].first, 0);
  assert.ok(Math.abs(view.curve[1].first + .1) < 1e-12);
  assert.ok(Math.abs(view.curve[2].second + .01) < 1e-12);
  assert.equal(view.rows[1].decision, 'rejected');
  assert.equal(view.rows[1].validation.id, 'latest');
  assert.deepEqual(project, before);
});

for (const [label, change, expected] of [
  ['different data', r => { r.data.snapshot_sha256 = hash('d'); }, /Dataset/],
  ['missing data identity', r => { delete r.data.snapshot_sha256; }, /Dataset/],
  ['different source', r => { r.provenance.source_sha256 = hash('d'); }, /source/],
  ['unknown accounting', r => { delete r.provenance.execution; }, /account/],
  ['same-bar lag', r => { r.provenance.execution.execution_lag = 0; }, /Execution/],
  ['different timing', r => { r.provenance.execution.execution_lag = 2; }, /Execution/],
  ['different holdout window', r => { r.request.train_window = 300; }, /windows/],
  ['different currency', r => { r.data.currency = 'INR'; }, /Currency/],
  ['missing date', r => { r.equity_curve.splice(1, 1); }, /chronological/],
  ['duplicate date', r => { r.equity_curve[1].date = '2024-01-01'; }, /chronological/],
  ['unequal date', r => { r.equity_curve[1].date = '2024-01-04'; }, /chronological/],
  ['no initial NAV', r => { r.equity_curve[0].portfolio = 90; }, /baseline/],
  ['invalid NAV', r => { r.equity_curve[1].portfolio = NaN; }, /finite NAV/],
  ['zero capital', r => { r.request.initial_capital = 0; }, /initial-capital/],
]) test(`overlay refuses ${label} without dropping the evidence column`, () => {
  const project = fixture();
  change(project.trials[1].result);
  const view = projectComparison(project, ['first', 'second']);
  assert.equal(view.rows.length, 2);
  assert.equal(view.curve.length, 0);
  assert.match(view.issues.join(' '), expected);
});

test('failed trials remain visible without invented metrics or curves', () => {
  const project = fixture();
  Object.assign(project.trials[1], { status: 'failed', result: null, error: 'Preserved provider failure' });
  const view = projectComparison(project, ['first', 'second']);
  assert.equal(view.rows[1].trial.error, 'Preserved provider failure');
  assert.equal(view.rows[1].trial.result, null);
  assert.equal(view.curve.length, 0);
  assert.match(view.issues.join(' '), /completed evidence/);
});

test('comparison rejects duplicate, absent and oversized selections', () => {
  for (const ids of [[], ['first'], ['first', 'first'], ['first', 'absent'], ['first', 'second', 'a', 'b', 'c']]) {
    const view = projectComparison(fixture(), ids);
    assert.ok(view.issues.length);
    assert.equal(view.curve.length, 0);
  }
});

test('cost perturbations are comparable without recomputing or choosing a winner', () => {
  const project = fixture();
  project.trials[1].result.request.commission_bps = 10;
  const view = projectComparison(project, ['first', 'second']);
  assert.deepEqual(view.issues, []);
  assert.equal(view.rows[1].trial.result.request.commission_bps, 10);
  assert.equal(view.winner, undefined);
});
