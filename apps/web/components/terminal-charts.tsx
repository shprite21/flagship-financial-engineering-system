"use client";
import { useId } from 'react';
import { PerformancePlot } from './flagship/performance-plot';
import type { Bar } from '@/lib/quant';
export function Sparkline({values,color='#4c88ff',baseline}:{values:number[];color?:string;baseline?:number}) {
  const id=useId().replaceAll(':','');
  const max=Math.max(...values),minValue=Math.min(...values);
  const offset=baseline===undefined||max===minValue?0:(max-baseline)/(max-minValue);
  const stroke=baseline===undefined?color:minValue===baseline&&max===baseline?'#94a3b8':minValue>=baseline?'#4ade80':max<=baseline?'#f87171':`url(#${id})`;
  const min=Math.min(...values),range=Math.max(...values)-min||1;
  return <svg className="sparkline" viewBox="0 0 100 32" aria-hidden="true"><defs><linearGradient id={id} x1="0" y1="0" x2="0" y2="1"><stop offset={offset} stopColor="#4ade80"/><stop offset={offset} stopColor="#f87171"/></linearGradient></defs><path d={values.map((x,i)=>`${i?'L':'M'}${i/(values.length-1)*100},${29-(x-min)/range*26}`).join(' ')} fill="none" stroke={stroke} strokeWidth="1.7" /></svg>;
}
export function EquityChart({data,drawdown=false,baseline}:{data:{date:string;value:number;benchmark?:number}[];drawdown?:boolean;baseline?:number}) {
  return <PerformancePlot data={data.map(row=>({date:row.date,value:row.value,...(row.benchmark===undefined?{}:{benchmark:row.benchmark})}))}
    baseline={drawdown?0:baseline??data[0]?.value} percent={drawdown}
    series={[{key:'value',label:drawdown?'Drawdown':'Strategy',primary:true},...(!drawdown&&data.some(row=>row.benchmark!==undefined)?[{key:'benchmark',label:'Buy & hold'}]:[])]} />;
}
export function CandleChart({bars}:{bars:Bar[]}) {
  const data=bars.slice(-70), low=Math.min(...data.map(b=>b.low)),high=Math.max(...data.map(b=>b.high)),range=high-low||1;
  const y=(v:number)=>250-(v-low)/range*220;
  return <svg className="candle-chart" viewBox="0 0 900 320" role="img" aria-label="Historical daily candlestick chart">
    {[0,.25,.5,.75,1].map(t=><g key={t}><line x1="10" x2="822" y1={30+t*220} y2={30+t*220} stroke="#1b2433" strokeDasharray="3 5"/><text x="832" y={34+t*220} fill="#7c879a" fontSize="12">{(high-t*range).toFixed(2)}</text></g>)}
    {data.map((b,i)=>{const color=b.close>=b.open?'#4cad91':'#df6f7b';return <g key={b.date}><title>{b.date} · O {b.open.toFixed(2)} H {b.high.toFixed(2)} L {b.low.toFixed(2)} C {b.close.toFixed(2)}</title><line x1={i*11.5+14} x2={i*11.5+14} y1={y(b.high)} y2={y(b.low)} stroke={color}/><rect x={i*11.5+10.5} y={Math.min(y(b.open),y(b.close))} width="7" height={Math.max(1,Math.abs(y(b.open)-y(b.close)))} fill={color}/><rect x={i*11.5+10.5} y={295-b.volume/20000000*28} height={b.volume/20000000*28} width="7" fill={color} opacity=".3"/></g>;})}
    {[0,14,28,42,56,69].map(i=><text key={i} x={i*11.5+10} y="315" fill="#7c879a" fontSize="12" textAnchor={i===69?'end':'start'}>{data[i]?.date.slice(5)}</text>)}
  </svg>;
}
