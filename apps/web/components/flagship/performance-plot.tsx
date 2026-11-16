'use client';

import { useId } from 'react';
import { CartesianGrid, ComposedChart, Line, ReferenceLine, XAxis, YAxis } from 'recharts';
import { ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart';
import { num, pct } from '@/lib/flagship/research';
import { comparisonColor, performanceTone } from '@/lib/performance-colors';

const patterns = ['4 3', '9 3', '2 3', '12 3 2 3', '6 3 2 3', '10 5', '2 5', '14 3 4 3'];
export function PerformancePlot({ data, series, percent = false, baseline }: {
  data: Record<string, string | number | null>[];
  series: { key: string; label: string; primary?: boolean }[];
  percent?: boolean;
  /** Single performance curves use gain/loss colors; comparisons use fixed colors. */
  baseline?: number;
}) {
  const id = useId().replaceAll(':', '');
  const signedCurve = series.length === 1 && baseline !== undefined;
  const styled = series.map((s, i) => {
    const values = data.flatMap(row => typeof row[s.key] === 'number' && Number.isFinite(row[s.key]) ? [Number(row[s.key])] : []);
    const min = values.length ? Math.min(...values) : 0;
    const max = values.length ? Math.max(...values) : 0;
    const gradient = `${id}-${i}`;
    const color = !signedCurve ? comparisonColor(i)
      : min === baseline && max === baseline ? '#94a3b8'
      : min >= baseline ? '#4ade80' : max <= baseline ? '#f87171' : `url(#${gradient})`;
    return { ...s, color, gradient, offset: baseline === undefined || max === min ? 0 : (max - baseline) / (max - min), pattern: s.primary || series.length === 1 ? undefined : patterns[i % patterns.length] };
  });
  return <>
    <ChartContainer className="h-[280px] w-full" config={Object.fromEntries(styled.map(s => [s.key, { label: s.label, color: s.color }]))}>
      <ComposedChart data={data} accessibilityLayer>
        <defs>{styled.filter(s => s.color.startsWith('url')).map(s => <linearGradient key={s.key} id={s.gradient} x1="0" y1="0" x2="0" y2="1"><stop offset={s.offset} stopColor="#4ade80" /><stop offset={s.offset} stopColor="#f87171" /></linearGradient>)}</defs>
        <CartesianGrid vertical={false} strokeDasharray="3 5" />
        <XAxis dataKey="date" minTickGap={60} tickFormatter={v => String(v).slice(0, 7)} />
        <YAxis width={70} domain={['auto', 'auto']} tickFormatter={v => percent ? pct(Number(v), 0) : num(Number(v), 0)} />
        {baseline !== undefined && <ReferenceLine y={baseline} stroke="#64748b" strokeDasharray="3 5" />}
        <ChartTooltip content={<ChartTooltipContent formatter={(v, name) => <span><span style={{ color: signedCurve ? undefined : styled.find(s => s.label === name)?.color }}>{name}: </span><span className={baseline === undefined ? undefined : performanceTone('return', Number(v) - baseline)}>{percent ? pct(Number(v)) : num(Number(v))}</span></span>} />} />
        {styled.map(s => <Line key={s.key} name={s.label} dataKey={s.key} stroke={s.color} strokeWidth={s.primary ? 3 : 1.6} strokeDasharray={s.pattern} connectNulls={false} dot={false} isAnimationActive={false} />)}
      </ComposedChart>
    </ChartContainer>
    <div className="mt-2 flex flex-wrap gap-x-5 gap-y-2 text-xs">{styled.map(s => <span key={s.key} className="inline-flex items-center gap-2" style={{ color: signedCurve ? undefined : s.color }}><svg width="32" height="10" aria-hidden="true"><line x1="0" y1="5" x2="32" y2="5" stroke={signedCurve ? 'currentColor' : s.color} strokeWidth={s.primary ? 3 : 1.6} strokeDasharray={s.pattern} /></svg>{s.label}</span>)}</div>
    {signedCurve && <p className="mt-2 text-xs text-muted-foreground">Green above {percent ? pct(baseline!, 0) : num(baseline!, 0)} · red below.</p>}
  </>;
}
