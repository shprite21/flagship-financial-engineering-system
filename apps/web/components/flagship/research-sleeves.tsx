'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select';
import { DataTable, Field, Panel, Pnl, Stat } from './research-primitives';
import { PerformancePlot as Plot } from './performance-plot';
import { num, pct, sleeveComparison, skewDescription, type Evidence } from '@/lib/flagship/research';

export function ResearchSleeves({ result }: { result: Evidence }) {
  const [strategy, setStrategy] = useState(result.sleeves[0]?.strategy ?? '');
  const [instrument, setInstrument] = useState('all');
  const [from, setFrom] = useState('');
  const [through, setThrough] = useState('');
  const [page, setPage] = useState(0);
  const sleeve = result.sleeves.find(s => s.strategy === strategy) ?? result.sleeves[0];
  const details = sleeve?.diagnostics;
  const available = result.sleeves.filter(s => s.diagnostics);
  const comparison = sleeveComparison(result);
  const holdings = details?.holdings.filter(h => instrument === 'all' || h.symbol === instrument) ?? [];
  const trades = details?.trades.filter(t => (instrument === 'all' || t.symbol === instrument) && (!from || t.date >= from) && (!through || t.date <= through)).slice().reverse() ?? [];
  const pageCount = Math.max(1, Math.ceil(trades.length / 50));
  const currentPage = Math.min(page, pageCount - 1);
  const allocation = details?.allocation_history.map(row => ({ date: row.date, cash: row.cash,
    ...Object.fromEntries(holdings.map((h, i) => [`a${i}`, row.weights[h.symbol]])),
  })) ?? [];

  function exportTrades() {
    if (!details) return;
    const columns = ['date', 'symbol', 'side', 'before_weight', 'after_weight', 'weight_change', 'notional', 'trading_cost'] as const;
    const csv = [columns.join(','), ...trades.map(row => columns.map(key => JSON.stringify(row[key])).join(','))].join('\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url; link.download = `${sleeve.strategy}-simulated-trades.csv`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return <>
    <Panel title="Compare alpha sleeves and total portfolio" detail={`Net cumulative returns from ${result.data.evaluation_start}, including training and test history. Each sleeve starts from the same capital. The total portfolio includes blending, regime scaling, risk constraints and costs; it is not the sum of standalone sleeves.`}>
      {comparison.length > 0 && <Plot data={comparison} series={[...available.map((s, i) => ({ key: `s${i}`, label: s.name })), { key: 'portfolio', label: 'Total portfolio', primary: true }]} percent baseline={0} />}
      <div className="my-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Stat label="Total portfolio ending NAV" value={num(result.equity_curve.at(-1)?.portfolio)} detail={result.data.currency} />
        <Stat label="Total portfolio net return" value={pct(result.metrics.total_return)} performanceValue={result.metrics.total_return} />
        <Stat label="Portfolio daily return skewness" value={num(result.metrics.skew)} detail={skewDescription(result.metrics.skew)} />
        <Stat label="Portfolio max drawdown" value={pct(result.metrics.max_drawdown)} performanceValue={result.metrics.max_drawdown} />
      </div>
      <DataTable rows={result.sleeves} columns={[
        { label: 'Sleeve', value: s => <button className="text-blue-300 underline" onClick={() => { setStrategy(s.strategy); setPage(0); }}>{s.name}</button> },
        { label: 'Signal budget', value: s => `${s.budget}%` },
        { label: 'Net return', value: s => <Pnl value={s.total_return} /> },
        { label: `Ending NAV · ${result.data.currency}`, value: s => num(s.diagnostics?.ending_nav ?? result.request.initial_capital * (1 + s.total_return)) },
        { label: 'Sharpe', value: s => num(s.sharpe) },
        { label: 'Daily return skewness', value: s => <span title={skewDescription(s.skew)}>{num(s.skew)}</span> },
        { label: 'Max drawdown', value: s => <Pnl value={s.max_drawdown} /> },
      ]} />
      <p className="mt-3 text-xs text-muted-foreground">Skewness is the adjusted Fisher–Pearson sample coefficient of daily net returns over the evaluation window, without annualization. Negative means downside asymmetry; positive means upside asymmetry. It is descriptive, not a forecast. Missing saved metrics or fewer than three varying observations display —.</p>
    </Panel>
    <Panel title="Sleeve analysis">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Alpha sleeve"><NativeSelect aria-label="Alpha sleeve" value={sleeve?.strategy} onChange={e => { setStrategy(e.target.value); setPage(0); }}>
          {result.sleeves.map(s => <NativeSelectOption key={s.strategy} value={s.strategy}>{s.name}</NativeSelectOption>)}
        </NativeSelect></Field>
        <Field label="Instrument · holdings, allocations and trades"><NativeSelect aria-label="Instrument · holdings, allocations and trades" value={instrument} onChange={e => { setInstrument(e.target.value); setPage(0); }}>
          <NativeSelectOption value="all">All instruments</NativeSelectOption>
          {result.data.symbols.map(s => <NativeSelectOption key={s} value={s}>{s}</NativeSelectOption>)}
        </NativeSelect></Field>
      </div>
      <p className="mt-4 text-sm text-muted-foreground">{details?.basis ?? 'This saved experiment predates detailed sleeve analysis. Clone its configuration and run a new study to generate diagnostics; the original result remains unchanged.'}</p>
    </Panel>
    {details && <>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Stat label="Standalone ending NAV" value={num(details.ending_nav)} detail={result.data.currency} />
        <Stat label="Cash / financing weight" value={pct(details.cash_weight)} detail={`${num(details.cash_value)} ${result.data.currency}`} />
        <Stat label="Cost contribution" value={pct(details.cost_contribution)} performanceValue={details.cost_contribution} detail="Commission, slippage and borrow" />
        <Stat label="Annual traded notional" value={`${num(details.annual_turnover)}×`} />
        <Stat label="Sleeve daily return skewness" value={num(sleeve.skew)} detail={skewDescription(sleeve.skew)} />
      </div>
      <Panel title={`${sleeve.name} · performance`} detail={`Standalone NAV in ${result.data.currency}; rebased to ${num(result.request.initial_capital)} at evaluation start. Instrument filters do not change sleeve performance.`}>
        <Plot data={details.equity_curve} series={[{ key: 'net', label: 'Net sleeve', primary: true }, { key: 'gross', label: 'Gross sleeve' }]} baseline={result.request.initial_capital} />
        <Plot data={details.equity_curve} series={[{ key: 'drawdown', label: 'Drawdown' }]} percent baseline={0} />
      </Panel>
      <Panel title="Sleeve portfolio by instrument" detail={`End-of-day simulated holdings as of ${result.data.end_date}. Latest targets are unexecuted signals. Gross instrument contributions plus total cost contribution reconcile to the sleeve's net return.`}>
        <DataTable rows={holdings} columns={[
          { label: 'Instrument', value: h => h.symbol },
          { label: 'Held weight', value: h => pct(h.current_weight) },
          { label: 'Latest target', value: h => pct(h.target_weight) },
          { label: 'Budget × target¹', value: h => pct(h.target_weight * sleeve.budget / 100) },
          { label: `Value · ${result.data.currency}`, value: h => num(h.ending_value) },
          { label: 'Average gross weight', value: h => pct(h.average_gross_weight) },
          { label: 'Gross return contribution', value: h => <Pnl value={h.return_contribution} /> },
        ]} />
        <p className="mt-3 text-xs text-muted-foreground">¹ Input to signal blending, before netting, normalization, regime scaling and risk constraints. It is not the sleeve’s realized allocation in the combined portfolio. Cash is shown separately above; negative cash represents modeled financing.</p>
      </Panel>
      <Panel title="Instrument allocation history" detail="Weights held for each session’s return, after scheduled rebalancing. Between rebalances, holdings drift with prices and costs. Cash includes any modeled financing balance.">
        <Plot data={allocation} series={[...holdings.map((h, i) => ({ key: `a${i}`, label: h.symbol })), { key: 'cash', label: 'Cash / financing' }]} percent />
      </Panel>
      <Panel title="Simulated sleeve trades" detail="Signed fractional-weight rebalance notionals, using evaluation-rebased NAV. Buy increases exposure; sell reduces it, including short positions. These are not whole-share fills. Trading costs exclude daily borrow, which is included in net performance.">
        <div className="mb-4 flex flex-wrap items-end gap-3">
          <Field label="From"><Input type="date" value={from} onChange={e => { setFrom(e.target.value); setPage(0); }} /></Field>
          <Field label="Through"><Input type="date" value={through} onChange={e => { setThrough(e.target.value); setPage(0); }} /></Field>
          <Button variant="outline" onClick={exportTrades} disabled={!trades.length}>Export filtered trades</Button>
        </div>
        {from && through && from > through && <p role="alert" className="mb-3 text-sm text-amber-200">From must be on or before Through.</p>}
        {trades.length ? <DataTable rows={trades.slice(currentPage * 50, (currentPage + 1) * 50)} columns={[
          { label: 'Date', value: t => t.date }, { label: 'Instrument', value: t => t.symbol },
          { label: 'Side', value: t => t.side }, { label: 'Before', value: t => pct(t.before_weight) },
          { label: 'After', value: t => pct(t.after_weight) }, { label: 'Change', value: t => pct(t.weight_change) },
          { label: `Notional · ${result.data.currency}`, value: t => num(t.notional) },
          { label: 'Trading cost', value: t => num(t.trading_cost) },
        ]} /> : <p className="text-sm text-muted-foreground">No simulated trades match these filters.</p>}
        <div className="mt-4 flex flex-wrap items-center gap-3 text-sm">
          <Button variant="outline" disabled={currentPage === 0} onClick={() => setPage(currentPage - 1)}>Previous</Button>
          <span>{trades.length} trades · page {currentPage + 1} of {pageCount}</span>
          <Button variant="outline" disabled={currentPage + 1 >= pageCount} onClick={() => setPage(currentPage + 1)}>Next</Button>
        </div>
      </Panel>
    </>}
  </>;
}
