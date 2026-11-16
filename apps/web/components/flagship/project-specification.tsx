'use client';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Field, Panel } from './research-primitives';
import type { ProjectSpec, Thesis } from '@/lib/flagship/projects';
import type { Catalog, ResearchRequest } from '@/lib/flagship/research';

const textFields: { key: keyof Thesis; label: string }[] = [
  { key: 'research_question', label: 'Research question' }, { key: 'economic_hypothesis', label: 'Falsifiable hypothesis' },
  { key: 'mechanism', label: 'Expected mechanism' }, { key: 'holding_period', label: 'Expected holding period' },
  { key: 'alpha_source', label: 'Expected source of alpha' }, { key: 'failure_conditions', label: 'Predicted failure conditions' },
  { key: 'acceptance_criteria', label: 'Acceptance criteria' }, { key: 'rejection_criteria', label: 'Rejection criteria' },
  { key: 'limitations', label: 'Limitations' }, { key: 'notes', label: 'Research notes' },
];

export default function ProjectSpecification({ value, onChange, catalog, stage }: { value: ProjectSpec; onChange: (next: ProjectSpec) => void; catalog: Catalog | null; stage: 'THESIS' | 'SIGNAL' }) {
  const thesis = (key: keyof Thesis, next: string | string[]) => onChange({ ...value, thesis: { ...value.thesis, [key]: next }, research: { ...value.research, ...(key === 'economic_hypothesis' ? { hypothesis: String(next) } : {}), ...(key === 'title' ? { name: String(next).slice(0, 80) } : {}) } });
  const research = (next: Partial<ResearchRequest>) => onChange({ ...value, research: { ...value.research, ...next } });
  return stage === 'THESIS' ? <Panel title="Research specification" detail="Every saved change creates a revision. Prior hypotheses and trials remain in the journal.">
    <div className="grid gap-4 md:grid-cols-2">
      <Field label="Project title"><Input aria-label="Project title" value={value.thesis.title} onChange={e => thesis('title', e.target.value)} /></Field>
      <Field label="Market"><select aria-label="Market" className="rounded border bg-background p-2" value={value.market} onChange={e => onChange({ ...value, market: e.target.value as 'US' | 'IN' })}><option>US</option><option>IN</option></select></Field>
      {textFields.map(({ key, label }) => <Field key={key} label={label}><Textarea aria-label={label} value={String(value.thesis[key])} onChange={e => thesis(key, e.target.value)} /></Field>)}
      <Field label="Primary metrics (comma separated)"><Input aria-label="Primary metrics (comma separated)" value={value.thesis.primary_metrics.join(', ')} onChange={e => thesis('primary_metrics', e.target.value.split(',').map(s => s.trim()))} /></Field>
      <Field label="Secondary metrics (comma separated)"><Input aria-label="Secondary metrics (comma separated)" value={value.thesis.secondary_metrics.join(', ')} onChange={e => thesis('secondary_metrics', e.target.value.split(',').map(s => s.trim()))} /></Field>
      <Field label="Prior historical exposure"><select aria-label="Prior historical exposure" className="rounded border bg-background p-2" value={value.prior_exposure} onChange={e => onChange({ ...value, prior_exposure: e.target.value as ProjectSpec['prior_exposure'] })}><option value="unknown">Unknown outside this project</option><option value="previously_inspected">Previously inspected</option></select></Field>
      <Field label="Exposure disclosure"><Textarea aria-label="Exposure disclosure" value={value.prior_exposure_note} onChange={e => onChange({ ...value, prior_exposure_note: e.target.value })} /></Field>
    </div>
  </Panel> : <Panel title="Signal, data mandate and portfolio" detail="Uses Flagship's catalogue strategy engine. Written signal notes describe the hypothesis; they do not execute custom rules.">
    <div className="grid gap-4 md:grid-cols-3">
      <Field label="Portfolio weighting"><select aria-label="Portfolio weighting" className="rounded border bg-background p-2" value={value.research.portfolio_method ?? 'signal'} onChange={e => research({portfolio_method: e.target.value as ResearchRequest['portfolio_method']})}>{['signal', 'equal', 'inverse_volatility', 'risk_parity', 'minimum_variance'].map(method => <option key={method} value={method}>{method.replaceAll('_', ' ')}</option>)}</select></Field>
      <Field label="Allocation estimation window"><Input aria-label="Allocation estimation window" type="number" min={20} max={126} value={value.research.portfolio_lookback ?? 63} onChange={e => research({portfolio_lookback: +e.target.value})} /></Field>
      <Field label="Strategy"><select aria-label="Strategy" className="rounded border bg-background p-2" value={value.research.sleeves[0].strategy} onChange={e => research({ sleeves: [{ ...value.research.sleeves[0], strategy: e.target.value }] })}>{catalog?.strategies.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></Field>
      <Field label="Lookback"><Input aria-label="Lookback" type="number" min={5} max={252} value={value.research.sleeves[0].lookback} onChange={e => research({ sleeves: [{ ...value.research.sleeves[0], lookback: +e.target.value }] })} /></Field>
      <Field label="Data source"><select aria-label="Data source" className="rounded border bg-background p-2" value={value.research.data_mode} onChange={e => research({ data_mode: e.target.value as ResearchRequest['data_mode'] })}><option value="demo">Seeded synthetic demonstration</option><option value="yahoo">Yahoo observed history</option><option value="massive">Massive observed history</option></select></Field>
      <Field label="Universe (comma separated)"><Input aria-label="Universe (comma separated)" value={value.research.symbols.join(', ')} onChange={e => research({ symbols: e.target.value.toUpperCase().split(',').map(s => s.trim()) })} /></Field>
      <Field label="Benchmark"><Input aria-label="Benchmark" value={value.research.benchmark} onChange={e => research({ benchmark: e.target.value.toUpperCase() })} /></Field>
      <Field label="History"><select aria-label="History" className="rounded border bg-background p-2" value={value.research.period} onChange={e => research({ period: e.target.value as ResearchRequest['period'] })}><option>2y</option><option>5y</option><option>10y</option></select></Field>
      <Field label="Rebalance"><select aria-label="Rebalance" className="rounded border bg-background p-2" value={value.research.rebalance} onChange={e => research({ rebalance: e.target.value as ResearchRequest['rebalance'] })}><option>daily</option><option>weekly</option><option>monthly</option></select></Field>
      {([['initial_capital', 'Initial capital'], ['volatility_target', 'Annual volatility target'], ['max_asset_weight', 'Maximum asset weight'], ['max_gross_exposure', 'Maximum gross exposure'], ['max_net_exposure', 'Maximum net exposure'], ['drawdown_limit', 'Drawdown limit'], ['commission_bps', 'Commission (bps)'], ['slippage_bps', 'Slippage (bps)'], ['annual_borrow_bps', 'Annual borrow (bps)'], ['train_window', 'Walk-forward training bars'], ['test_window', 'Walk-forward test bars'], ['min_oos_sharpe', 'Mandate minimum walk-forward Sharpe']] as const).map(([key, label]) => <Field key={key} label={label}><Input aria-label={label} type="number" step="any" value={value.research[key]} onChange={e => research({ [key]: +e.target.value })} /></Field>)}
      <Field label="Reserved final fraction"><Input aria-label="Reserved final fraction" type="number" min={.1} max={.3} step={.01} value={value.holdout_fraction} onChange={e => onChange({ ...value, holdout_fraction: +e.target.value })} /></Field>
      <Field label="Long-only"><input type="checkbox" checked={value.research.long_only} onChange={e => research({ long_only: e.target.checked })} /></Field>
      <Field label="Condition signals on regimes (new hypothesis)"><input type="checkbox" checked={value.research.regime_enabled} onChange={e => research({ regime_enabled: e.target.checked })} /></Field>
      <Field label="Signal definition, normalization, filters and missing values"><Textarea aria-label="Signal definition, normalization, filters and missing values" value={value.signal_notes} onChange={e => onChange({ ...value, signal_notes: e.target.value })} /></Field>
      <Field label="Portfolio assumptions"><Textarea aria-label="Portfolio assumptions" value={value.portfolio_notes} onChange={e => onChange({ ...value, portfolio_notes: e.target.value })} /></Field>
    </div>
    <p className="mt-4 text-sm text-muted-foreground">Weighting reuses Flagship's allocators with volatility scaling and exposure limits. Risk parity and minimum variance require long-only signals and use prior-bar covariance on eligible instruments; caps and risk scaling can change their ideal solutions. Maximum-Sharpe, sector and turnover constraints are not enabled here. Execution is a lagged fractional research proxy; Survival adds separate whole-share stress. Regimes remain diagnostic unless conditioning is explicitly selected.</p>
  </Panel>;
}
