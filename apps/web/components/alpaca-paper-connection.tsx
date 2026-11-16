'use client';
import {useEffect,useState} from 'react';
import {integrationRequest} from '@/hooks/use-integrations';
import {Dialog,DialogContent,DialogHeader,DialogTitle,DialogDescription} from '@/components/ui/dialog';
import {performanceTone} from '@/lib/performance-colors';

type Status={connected:boolean;configured:boolean;account?:string;checkedAt?:string};
type Snapshot={receivedAt:string;account:Record<string,string>;positions:{symbol:string;qty:string;side:string;market_value:string;unrealized_pl:string}[];orders:{id:string;symbol:string;side:string;qty:string;filled_qty:string;status:string}[];ordersScope:string};
const money=(value:string|undefined)=>value!==undefined&&Number.isFinite(Number(value))?new Intl.NumberFormat(undefined,{style:'currency',currency:'USD'}).format(Number(value)):'—';
export default function AlpacaPaperConnection(){
  const [status,setStatus]=useState<Status|null>(null),[snapshot,setSnapshot]=useState<Snapshot|null>(null),[open,setOpen]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const [key,setKey]=useState(''),[secret,setSecret]=useState('');
  useEffect(()=>{let active=true;const refresh=()=>integrationRequest('/alpaca-paper/status').then(v=>{if(active)setStatus(v as unknown as Status);}).catch(e=>{if(active){setStatus(null);setSnapshot(null);setError((e as Error).message);}});void refresh();const timer=setInterval(()=>void refresh(),30000);return()=>{active=false;clearInterval(timer);};},[]);
  async function action(fn:()=>Promise<void>){setBusy(true);setError('');try{await fn();}catch(e){setError((e as Error).message);setSnapshot(null);try{setStatus(await integrationRequest('/alpaca-paper/status') as unknown as Status);}catch{setStatus(null);}}finally{setBusy(false);}}
  async function connect(environment=false){const credentials=environment?{}:{apiKey:key,secretKey:secret};setKey('');setSecret('');setSnapshot(null);await action(async()=>{setStatus(await integrationRequest('/alpaca-paper/connect',credentials) as unknown as Status);setOpen(false);});}
  return <article className="connection-card space-y-3">
    <span className={`badge ${status?.connected?'demo':'neutral'}`}>{status?.connected?'PAPER ACCOUNT CONNECTED':'PAPER CONNECTION REQUIRED'}</span>
    <h2>Massive data → Alpaca paper</h2>
    <p>US stocks and ETFs · USD · Alpaca simulates execution</p>
    <p className="connection-help">Connect Massive under Connections for research data. This connection reads your Alpaca paper account. Automatic strategy order routing is not available yet; Flagship simulation accounts remain separate.</p>
    <div className="connection-actions">
      <button className="button primary" disabled={busy} onClick={()=>setOpen(true)}>{status?.connected?'Replace paper keys':'Connect Alpaca paper'}</button>
      {status?.configured&&!status.connected&&<button className="button secondary" disabled={busy} onClick={()=>void connect(true)}>Verify backend keys</button>}
      {status?.connected&&<><button className="button secondary" disabled={busy} onClick={()=>void action(async()=>setSnapshot(await integrationRequest('/alpaca-paper/account') as unknown as Snapshot))}>Refresh paper account</button><button className="text-button" disabled={busy} onClick={()=>void action(async()=>{setStatus(await integrationRequest('/alpaca-paper/disconnect',{}) as unknown as Status);setSnapshot(null);})}>Disconnect</button></>}
      <a className="text-button" href="https://app.alpaca.markets/paper/dashboard/overview" target="_blank" rel="noreferrer">Alpaca paper dashboard</a>
    </div>
    {status?.account&&<p className="text-sm text-muted-foreground">Paper account {status.account}</p>}
    {error&&<p role="alert" className="data-error">{error}</p>}
    {snapshot&&<div className="space-y-3"><p className="text-sm text-muted-foreground">Alpaca paper snapshot · {new Date(snapshot.receivedAt).toLocaleString()} · Broker marks shown here come from Alpaca.</p><div className="flex flex-wrap gap-5"><div>Equity <strong>{money(snapshot.account.equity)}</strong></div><div>Cash <strong>{money(snapshot.account.cash)}</strong></div></div><p className="text-sm">Balances belong to the entire Alpaca account. They are not added to Flagship simulation NAV.</p><div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr><th>Holding</th><th>Shares</th><th>Value</th><th>Unrealized P&amp;L</th></tr></thead><tbody>{snapshot.positions.map(p=><tr key={p.symbol}><td>{p.symbol} · {p.side}</td><td>{p.qty}</td><td>{money(p.market_value)}</td><td className={performanceTone('pnl', Number(p.unrealized_pl))}>{money(p.unrealized_pl)}</td></tr>)}</tbody></table>{!snapshot.positions.length&&<p>No positions reported.</p>}</div><details><summary>Alpaca paper orders ({snapshot.orders.length})</summary><p>{snapshot.ordersScope}</p><table className="w-full text-sm"><thead><tr><th>Symbol</th><th>Side</th><th>Quantity</th><th>Filled</th><th>Status</th></tr></thead><tbody>{snapshot.orders.map(o=><tr key={o.id}><td>{o.symbol}</td><td>{o.side}</td><td>{o.qty}</td><td>{o.filled_qty}</td><td>{o.status}</td></tr>)}</tbody></table></details></div>}
    <Dialog open={open} onOpenChange={value=>{setOpen(value);if(!value){setKey('');setSecret('');}}}><DialogContent><DialogHeader><DialogTitle>Connect Alpaca paper account</DialogTitle><DialogDescription>Use API keys from your Alpaca paper dashboard. Keys go only to Flagship’s local backend and Alpaca’s fixed paper endpoint. They stay in backend memory until disconnect or restart; no browser storage or Codex context.</DialogDescription></DialogHeader><form className="order-form" onSubmit={e=>{e.preventDefault();void connect();}}><label>Paper API key<input type="password" autoComplete="off" maxLength={200} required value={key} onChange={e=>setKey(e.target.value)}/></label><label>Paper secret key<input type="password" autoComplete="off" maxLength={200} required value={secret} onChange={e=>setSecret(e.target.value)}/></label><button className="button primary" disabled={busy}>{busy?'Verifying…':'Verify paper account'}</button>{error&&<p role="alert" className="data-error">{error}</p>}</form></DialogContent></Dialog>
  </article>;
}

