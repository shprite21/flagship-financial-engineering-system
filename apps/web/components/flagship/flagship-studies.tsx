'use client';

import { useState } from 'react';
import type { ReactNode } from 'react';
import { flagshipModules } from '@/lib/flagship/modules';
import { performanceTone } from '@/lib/performance-colors';
import strategies from '../../../../research/validation/results/summary.json';
import models from '../../../../research/execution/model-results.json';
import audit from '../../../../research/execution/paper-store-audit.json';

const costs = [
  { label: '0 bp', result: 'zero_bps_reexecuted' },
  { label: '5 bp', result: 'net' },
  { label: '10 bp', result: 'ten_bps_reexecuted' },
] as const;
const percent = (value: number) => (100 * value).toFixed(2) + '%';
const dollars = (value: number) => value.toLocaleString('en-US', {
  style: 'currency', currency: 'USD', maximumFractionDigits: 0,
});
const project = 'https://github.com/shprite21/flagship-financial-engineering-system/blob/main/';

function ReturnValue({ value }: { value: number }) {
  return <span className={performanceTone('return', value)}>{percent(value)}</span>;
}

export default function ResearchEvidence({ navigate }: { navigate: (page: string) => void }) {
  const [cost, setCost] = useState<(typeof costs)[number]['result']>('net');
  const hedge = models.derivatives.market_making;
  const paths = hedge.mean_across_paths;
  const risk = models.risk.holdout_one_session;
  const interval = strategies.regime.paired_inference.bonferroni_97_5_percent_interval;
  const paper = audit.terminal_v2['flagship/survival/registry.sqlite'];

  function section(index: number, children: ReactNode) {
    const module = flagshipModules[index];
    return <section className="flagship-panel space-y-3">
      <h2>{module.name}</h2>
      {children}
      <div className="flex flex-wrap items-center gap-4">
        <button className="button secondary" onClick={() => navigate(module.name)}>Open workbench</button>
        <a className="underline" href={project + 'docs/modules/' + module.document + '.md'}>Methods and source</a>
      </div>
    </section>;
  }

  return <div className="flagship-workspace">
    <h1>Research evidence</h1>
    {section(0, <>
      <p>Can a three-state HMM allocate between equity signals more effectively than equal strategy budgets?</p>
      <p>{strategies.input.oos_first} through {strategies.input.oos_last} · {strategies.sessions.toLocaleString('en-US')} historical sessions</p>
      <fieldset className="flex flex-wrap items-center gap-2">
        <legend>Execution cost per dollar traded</legend>
        {costs.map(option => <button key={option.result} type="button" aria-pressed={cost === option.result}
          className={cost === option.result ? 'button primary' : 'button secondary'} onClick={() => setCost(option.result)}>{option.label}</button>)}
      </fieldset>
      <div className="overflow-x-auto"><table className="w-full text-left text-sm">
        <thead><tr>{['Allocation', 'Sharpe', 'CAGR', 'Max drawdown'].map(title => <th scope="col" className="p-2" key={title}>{title}</th>)}</tr></thead>
        <tbody>{(['baseline', 'candidate'] as const).map(policy => {
          const row = strategies.regime[policy][cost];
          return <tr key={policy} className="border-t"><th scope="row" className="p-2">{policy === 'baseline' ? 'Static budgets' : 'HMM budgets'}</th>
            <td className="p-2">{row.sharpe.toFixed(2)}</td><td className="p-2"><ReturnValue value={row.cagr}/></td>
            <td className="p-2"><ReturnValue value={row.max_drawdown}/></td></tr>;
        })}</tbody></table></div>
      <p>At 5 bp, HMM annual traded notional was {strategies.regime.candidate.annual_traded_notional_over_equity.toFixed(2)}× equity.
        The paired 97.5% block-bootstrap interval for the Sharpe difference was [{interval.map(v => v.toFixed(2)).join(', ')}].</p>
    </>)}
    {section(1, <p>KO and PEP failed the formation-period cointegration screen in all ten folds. Both accounts stayed in cash throughout the same {strategies.sessions.toLocaleString('en-US')} sessions. Turnover and return were zero. Sharpe is undefined.</p>)}
    {section(2, <p>Across {hedge.seed_pairs} pairs of synthetic paths, delta hedging reduced mean residual delta RMSE from {paths.unhedged.delta_rmse_shares.toFixed(1)} to {paths.delta_hedged.delta_rmse_shares.toFixed(1)} shares.
      Mean marked net P&amp;L moved from <span className={performanceTone('pnl', paths.unhedged.net_pnl)}>{dollars(paths.unhedged.net_pnl)}</span> to <span className={performanceTone('pnl', paths.delta_hedged.net_pnl)}>{dollars(paths.delta_hedged.net_pnl)}</span>.</p>)}
    {section(3, <p>From {risk.first} to {risk.last}, realized one-day losses exceeded 95% VaR on {risk.var_exceedances} of {risk.observations.toLocaleString('en-US')} sessions ({percent(risk.exceedance_rate)}).
      On breach days, losses averaged {dollars(risk.mean_loss_on_var_breaches_usd)} against forecast ES of {dollars(risk.mean_forecast_es_on_var_breaches_usd)} per $100,000.</p>)}
    <section className="flagship-panel space-y-3"><h2>Forward execution evidence</h2>
      <p>The {audit.inspected_utc.slice(0, 10)} audit found {paper.demo_registrations} demo registrations, {paper.manual_signals} forward signals and {paper.manual_observations} recorded observations. A verified strategy fill history is still pending.</p>
      <div className="flex flex-wrap items-center gap-4"><button className="button secondary" onClick={() => navigate('Deployments')}>Paper deployments</button>
        <a className="underline" href={project + 'research/execution/README.md'}>Execution evidence and replay</a></div>
    </section>
  </div>;
}
