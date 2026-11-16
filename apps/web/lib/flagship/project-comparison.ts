import type { Project, Trial } from './projects';

const fingerprint = (value: unknown) => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);

/** Project GET supplies sealed evidence. This adapter only presents it; no reruns or ranking. */
export function projectComparison(project: Project, ids: string[]) {
  const selected = ids.map(id => project.trials.find(trial => trial.id === id));
  const trials = selected.filter((trial): trial is Trial => !!trial);
  const issues = new Set<string>();
  if (ids.length < 2 || ids.length > 4 || new Set(ids).size !== ids.length) {
    issues.add('Select two to four distinct trials.');
  }
  if (trials.length !== ids.length) issues.add('A selected trial is unavailable in this project.');
  const first = trials[0]?.result;
  const firstDataset = project.datasets.find(data => data.id === trials[0]?.dataset_id);
  const firstDates = first?.equity_curve.map(row => row.date);
  for (const trial of trials) {
    const result = trial.result;
    if (trial.status !== 'completed' || !result) {
      issues.add('Every selected trial needs completed evidence for a curve overlay; failed and pending attempts remain in the table.');
      continue;
    }
    const dataset = project.datasets.find(data => data.id === trial.dataset_id);
    if (!fingerprint(dataset?.dataset_hash) || dataset?.dataset_hash !== firstDataset?.dataset_hash ||
        !fingerprint(result.data.snapshot_sha256) || result.data.snapshot_sha256 !== first?.data.snapshot_sha256) {
      issues.add('Dataset fingerprints differ or are missing.');
    }
    if (!fingerprint(result.provenance.source_sha256) || result.provenance.source_sha256 !== first?.provenance.source_sha256) {
      issues.add('Engine source fingerprints differ or are missing.');
    }
    if (!result.data.evaluation_start || !result.data.end_date || result.data.evaluation_start !== first?.data.evaluation_start ||
        result.data.end_date !== first?.data.end_date || result.request.train_window !== first?.request.train_window ||
        result.request.test_window !== first?.request.test_window) {
      issues.add('Evaluation dates or walk-forward windows differ or are missing.');
    }
    const execution = result.provenance.execution;
    if (!execution || !Number.isInteger(execution.execution_lag) || execution.execution_lag < 1 ||
        typeof execution.drift_between_rebalances !== 'boolean' ||
        execution.execution_lag !== first?.provenance.execution?.execution_lag ||
        execution.drift_between_rebalances !== first?.provenance.execution?.drift_between_rebalances) {
      issues.add('Execution lag or account conventions differ or are missing.');
    }
    if (!result.data.currency || result.data.currency !== first?.data.currency ||
        result.request.data_mode !== first?.request.data_mode || result.request.benchmark !== first?.request.benchmark) {
      issues.add('Currency, provider or benchmark differs or is missing.');
    }
    const curve = result.equity_curve;
    const capital = result.request.initial_capital;
    if (!Number.isFinite(capital) || capital <= 0 || curve.length < 2 ||
        curve.length !== firstDates?.length || curve.some((row, i) =>
          row.date !== firstDates?.[i] || !/^\d{4}-\d{2}-\d{2}$/.test(row.date) ||
          (i > 0 && row.date <= curve[i - 1].date) || !Number.isFinite(row.portfolio) || row.portfolio <= 0) ||
        curve[0]?.portfolio !== capital || curve[1]?.date !== result.data.evaluation_start ||
        curve.at(-1)?.date !== result.data.end_date) {
      issues.add('Curves need identical chronological dates, finite NAV and an explicit initial-capital baseline. No alignment or filling is performed.');
    }
  }
  const rows = trials.map(trial => ({
    trial,
    decision: [...project.journal].reverse().find(event =>
      event.action === 'experiment_decision_recorded' && event.body.trial_id === trial.id)?.body.status as string | undefined,
    validation: [...project.validations].reverse().find(run => run.trial_id === trial.id),
  }));
  const series = trials.map(trial => ({ key: trial.id, label: `${trial.request.sleeves[0].lookback} bars · ${trial.id.slice(0, 8)}` }));
  const curve: Record<string, string | number | null>[] = issues.size || !first ? [] : first.equity_curve.map((point, i) => ({
    date: point.date,
    ...Object.fromEntries(trials.map(trial => [trial.id, trial.result!.equity_curve[i].portfolio / trial.result!.request.initial_capital - 1])),
  }));
  return { rows, series, curve, issues: [...issues] };
}
