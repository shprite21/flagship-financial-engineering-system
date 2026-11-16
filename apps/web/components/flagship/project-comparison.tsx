'use client';

import { useState } from 'react';
import type { ReactNode } from 'react';
import type { Project, Trial } from '@/lib/flagship/projects';
import { projectComparison } from '@/lib/flagship/project-comparison';
import { num, pct } from '@/lib/flagship/research';
import { PerformancePlot } from './performance-plot';
import { Panel, Pnl, Status } from './research-primitives';

export default function ProjectComparison({ project, candidateId }: { project: Project; candidateId: string }) {
  const [ids, setIds] = useState<string[]>([]);
  const comparison = projectComparison(project, ids);
  const metrics: { label: string; render: (trial: Trial) => ReactNode }[] = [
    { label: 'Historical net return', render: t => <Pnl value={t.result?.metrics.total_return} /> },
    { label: 'CAGR', render: t => <Pnl value={t.result?.metrics.annualized_return} /> },
    { label: 'Sharpe · daily / zero cash hurdle', render: t => num(t.result?.metrics.sharpe) },
    { label: 'Annualized volatility', render: t => pct(t.result?.metrics.annualized_volatility) },
    { label: 'Maximum drawdown', render: t => <Pnl value={t.result?.metrics.max_drawdown} /> },
    { label: 'Annual turnover · sum of absolute trades', render: t => num(t.result?.metrics.annual_turnover) },
    { label: 'Walk-forward net return', render: t => <Pnl value={t.result?.validation.metrics.total_return} /> },
    { label: 'Walk-forward Sharpe', render: t => num(t.result?.validation.metrics.sharpe) },
    { label: 'Last marked gross exposure', render: t => pct(t.result?.risk.current_gross) },
    { label: '3× cost stress · full history', render: t => <Pnl value={t.result?.cost_stress.find(s => s.multiplier === 3)?.total_return} /> },
  ];

  return <Panel title="Compare retained experiments" detail="Select two to four trials. Compare stored evidence and assumptions; no winner or promotion is inferred.">
    <fieldset className="grid gap-2 md:grid-cols-2">
      <legend className="mb-3 text-sm">Trials to compare · {ids.length}/4 selected</legend>
      {project.trials.map(trial => <label key={trial.id} className="flex items-start gap-3 rounded border p-3 text-sm">
        <input type="checkbox" className="mt-1 accent-blue-400" aria-label={`Compare trial ${trial.id.slice(0, 8)}`} checked={ids.includes(trial.id)}
          disabled={!ids.includes(trial.id) && ids.length >= 4}
          onChange={event => setIds(current => event.target.checked ? [...current, trial.id] : current.filter(id => id !== trial.id))} />
        <span>{trial.request.sleeves[0].lookback} bars · {trial.request.rebalance} · {trial.id.slice(0, 8)}<span className="mt-1 block text-xs text-muted-foreground">{trial.status} · {trial.request.data_mode === 'demo' || trial.request.data_mode === 'synthetic' ? 'SYNTHETIC' : trial.request.data_mode} · {trial.post_oos ? 'After OOS reveal' : 'Development attempt'}</span></span>
      </label>)}
    </fieldset>
    {!project.trials.length && <p className="mt-3 text-sm text-muted-foreground">Run development trials to populate the experiment book. Failed attempts are retained here too.</p>}
    <div className="my-4" role="status">{comparison.issues.length ? <><p className="text-sm font-medium">Curve overlay unavailable</p><ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-muted-foreground">{comparison.issues.map(issue => <li key={issue}>{issue}</li>)}</ul></> : <p className="text-sm text-blue-300">Matched data, dates, engine and account convention. Different parameters and costs remain explicit below.</p>}</div>
    {comparison.curve.length > 0 && <><PerformancePlot data={comparison.curve} series={comparison.series.map(series => ({ ...series, primary: series.key === candidateId }))} percent baseline={0} /><p className="mt-3 text-xs text-muted-foreground">Each curve is a total strategy portfolio, net of modeled costs, relative to its recorded initial capital. The selected candidate is emphasized. No dates are trimmed or filled.</p></>}
    {comparison.rows.length > 0 && <div className="mt-5 overflow-x-auto"><table className="w-full text-left text-sm"><caption className="mb-3 text-left font-medium">Stored experiment evidence · development only</caption><thead><tr><th scope="col" className="p-2">Assumption / evidence</th>{comparison.rows.map(({ trial }) => <th scope="col" key={trial.id} className="min-w-52 p-2">{trial.request.sleeves[0].lookback} bars · {trial.id.slice(0, 8)}</th>)}</tr></thead><tbody>
      <tr className="border-t"><th scope="row" className="p-2 font-normal">Outcome / decision</th>{comparison.rows.map(({ trial, decision }) => <td key={trial.id} className="p-2"><Status value={trial.status} /><p className="mt-1">{decision ?? 'Not reviewed'}</p>{trial.error && <p className="mt-1 text-red-300">{trial.error}</p>}</td>)}</tr>
      {[
        { label: 'Saved revision', render: (t: Trial) => t.revision_id.slice(0, 12) },
        { label: 'Development dates', render: (t: Trial) => t.result ? `${t.result.data.evaluation_start} → ${t.result.data.end_date}` : 'Unavailable' },
        { label: 'Source / quote currency', render: (t: Trial) => `${t.request.data_mode} / ${t.result?.data.currency ?? 'Unavailable'}` },
        { label: 'Universe / benchmark', render: (t: Trial) => `${t.request.symbols.join(', ')} / ${t.request.benchmark}` },
        { label: 'Weighting / rebalance', render: (t: Trial) => `${t.request.portfolio_method ?? 'signal'} / ${t.request.rebalance}` },
        { label: 'Commission / slippage · bps per side', render: (t: Trial) => `${t.request.commission_bps} / ${t.request.slippage_bps}` },
        { label: 'Borrow · annual bps', render: (t: Trial) => num(t.request.annual_borrow_bps) },
        ...metrics,
      ].map(row => <tr key={row.label} className="border-t"><th scope="row" className="p-2 font-normal">{row.label}</th>{comparison.rows.map(({ trial }) => <td key={trial.id} className="p-2 tabular-nums">{row.render(trial)}</td>)}</tr>)}
      <tr className="border-t"><th scope="row" className="p-2 font-normal">Survival evidence</th>{comparison.rows.map(({ trial, validation }) => <td key={trial.id} className="p-2">{validation?.result ? Object.entries(validation.result.summary.counts).map(([key, count]) => `${count} ${key}`).join(' · ') : validation?.status ?? 'Not run'}<p className="mt-1 text-xs text-muted-foreground">{validation?.result ? `Configured gates: ${validation.result.summary.research_gates_satisfied ? 'satisfied' : 'unresolved'}` : 'No validation approval implied'}</p></td>)}</tr>
      {(['dsr', 'pbo'] as const).map(metric => <tr key={metric} className="border-t"><th scope="row" className="p-2 font-normal">{metric === 'dsr' ? 'DSR · conditional on disclosed trial count' : 'PBO · recorded local candidate grid'}</th>{comparison.rows.map(({ trial, validation }) => {
        const value = validation?.result?.layers.find(layer => layer.id === 10)?.metrics[metric];
        return <td key={trial.id} className="p-2">{typeof value === 'number' ? num(value, 3) : 'Unavailable'}</td>;
      })}</tr>)}
      <tr className="border-t"><th scope="row" className="p-2 font-normal">Data / source fingerprints</th>{comparison.rows.map(({ trial }) => <td key={trial.id} className="p-2 text-xs"><p className="break-all">{trial.result?.data.snapshot_sha256 ?? 'Unavailable'}</p><p className="mt-1 break-all">{trial.result?.provenance.source_sha256 ?? 'Unavailable'}</p></td>)}</tr>
    </tbody></table></div>}
    <p className="mt-4 text-xs text-muted-foreground">Headline metrics exclude warmup; cost stress uses the full development history. Validation counts can use different saved policies. Incompatible columns are descriptive only. Recorded attempts do not account for undisclosed research or establish independent significance.</p>
  </Panel>;
}
