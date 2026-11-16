"""Fail-closed live signal checks and manually copied order-ticket preparation."""
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pandas as pd
import numpy as np

from .calendar import IST, entry_window, prior_session, target_week, SOURCE
from .costs import Costs, size_trade
from .data import GrowwReadOnly, features, sha, symbol_ok
from .journal import Journal, aware, iso_now
from .research import FEATURES, PROTOCOL, predict


def verified_report(folder):
    folder=Path(folder)
    checks=json.loads((folder/'checksums.json').read_text())
    for name,expected in checks.items():
        if Path(name).name!=name or sha((folder/name).read_bytes())!=expected:
            raise ValueError('Research checkpoint integrity failure')
    if 'report.json' not in checks: raise ValueError('Report checksum missing')
    report=json.loads((folder/'report.json').read_text())
    for name in report.get('model_files',[]):
        if Path(name).name!=name or name not in checks: raise ValueError('Selected model checksum missing')
    return report


class Service:
    def __init__(self,root):
        self.root=Path(root); self.journal=Journal(root)

    def latest(self):
        folders=sorted((self.root/'runs').glob('*'),reverse=True)
        for folder in folders:
            if (folder/'report.json').exists(): return folder,verified_report(folder)
        return None,None

    def overview(self):
        folder,report=self.latest()
        summary=None
        if report:
            summary={k:v for k,v in report.items() if k!='candidates'}
            summary['candidates']=[{k:v for k,v in c.items() if k not in ('trades','curve')} for c in report['candidates']]
            if summary.get('holdout'): summary['holdout']={k:v for k,v in summary['holdout'].items() if k not in ('trades','curve')}
        return {'mode':'manual_only','automatic_orders':False,'report':summary,'calendar':target_week(),'calendar_source':SOURCE,
                'calendar_verified':'2026-10-17','costs':Costs().snapshot(),'account':self.journal.snapshot(),
                'decision':'NO TRADE','reason':'No verified executable feed and approved forward evidence',
                'groww_data_configured':bool(__import__('os').environ.get('GROWW_ACCESS_TOKEN'))}

    def signals(self,now=None):
        now=now or datetime.now(timezone.utc)
        folder,report=self.latest()
        blockers=[]
        if not report: return {'decision':'NO TRADE','signals':[],'blockers':['No completed research run']}
        blockers.extend(report['blockers'])
        if not report.get('live_eligible'): blockers.append('Research artifact is not eligible for live manual tickets')
        if not entry_window(now): blockers.append('Outside verified NSE 09:15–09:20 IST entry window')
        if not report['selected_candidate']: return {'decision':'NO TRADE','signals':[],'blockers':blockers}
        dataset=self.root/'datasets'/report['dataset']
        raw=(dataset/'bars.csv').read_bytes()
        if sha(raw)!=report['dataset']: raise ValueError('Dataset checksum mismatch')
        f=features(pd.read_csv(dataset/'bars.csv'))
        expected=prior_session(now.astimezone(IST).date())
        latest=f[f.date==expected].copy()
        if latest.empty: return {'decision':'NO TRADE','signals':[],'blockers':blockers+['Prior-session feature data unavailable']}
        checkpoints=[json.loads((folder/name).read_text()) for name in report['model_files']]
        latest['probability']=np.mean([predict(cp,latest) for cp in checkpoints],axis=0)
        if report['selected_candidate']=='momentum': latest=latest[(latest.ret20>0)&(latest.trend>0)]
        else: latest=latest[latest.probability>=PROTOCOL['threshold']]
        latest=latest[latest.adv20>=PROTOCOL['min_adv_inr']].sort_values('probability',ascending=False)
        signals=latest[['symbol','date','probability','stop_fraction','adv20']].to_dict('records')
        return {'decision':'NO TRADE' if blockers or not signals else 'MANUAL REVIEW','signals':signals,'blockers':blockers,'run_id':report['id']}

    def ticket(self,symbol,now=None):
        now=now or datetime.now(timezone.utc)
        snapshot=self.signals(now)
        if snapshot['decision']!='MANUAL REVIEW':
            raise ValueError('NO TRADE: '+'; '.join(snapshot['blockers'][:3]))
        row=next((s for s in snapshot['signals'] if s['symbol']==symbol_ok(symbol)),None)
        if not row: raise ValueError('Symbol is not in the current eligible signal set')
        quote=GrowwReadOnly().quote(symbol)
        ticket=prepare_ticket(row,quote,self.journal.snapshot(now.isoformat()),now,snapshot['run_id'])
        self.journal.append('ticket',ticket,event_id=ticket['id'],now=now.isoformat())
        return ticket


def prepare_ticket(signal,quote,account,now,run_id):
    """Pure preflight, called only after server-owned research eligibility checks."""
    if not entry_window(now): raise ValueError('Outside entry window or NSE closed')
    if not account.get('opening_cash_reconciled'): raise ValueError('Actual settled cash has not been reconciled')
    if account['halted'] or account['active']: raise ValueError('Account is halted or has an active reservation/position')
    if signal['date']!=prior_session(now.astimezone(IST).date()): raise ValueError('Stale feature session')
    age=(now-aware(quote['timestamp'])).total_seconds()
    values=[quote[k] for k in ('bid','ask','upper','lower')]
    if not all(math.isfinite(v) for v in values) or not 0<=age<=10 or quote['source']!='groww': raise ValueError('Stale, future or invalid executable quote')
    if quote['symbol']!=signal['symbol'] or not 0<quote['lower']<quote['bid']<=quote['ask']<quote['upper']:
        raise ValueError('Crossed/invalid book, symbol mismatch or circuit restriction')
    if (quote['ask']/quote['bid']-1)*10000>10: raise ValueError('Spread exceeds 10 bps')
    # Price ticks require instrument metadata; use a conservative 0.05 multiple,
    # which is also valid for 0.01 tick instruments. Refresh actual master before promotion.
    entry=round(math.ceil(quote['ask']/0.05)*.05,2)
    stop=round(math.floor(entry*(1-signal['stop_fraction'])/.05)*.05,2)
    if entry>=quote['upper'] or stop<=quote['lower']: raise ValueError('Entry or protective stop too close to circuit limit')
    sized=size_trade(entry,stop,account['available_cash'],min(50,account['remaining_weekly_loss']))
    if not sized['quantity']: raise ValueError(sized['reason'])
    if min(quote['bid_size'],quote['ask_size'])<sized['quantity']*10: raise ValueError('Insufficient displayed depth')
    if sized['quantity']*entry>signal['adv20']*PROTOCOL['max_participation']: raise ValueError('Participation limit exceeded')
    return {**sized,'id':uuid4().hex,'created_at':now.isoformat(),'expires_at':(now+timedelta(seconds=10)).isoformat(),
            'run_id':run_id,'symbol':signal['symbol'],'exchange':'NSE','segment':'CASH','product':'intraday',
            'side':'BUY','order_type':'LIMIT','entry_limit':entry,'stop_trigger':stop,'exit_by':'15:15 Asia/Kolkata',
            'quote':quote,'fees_version':Costs().version,'automatic_submission':False,
            'instructions':['Recheck quote and available settled cash in Groww before manually placing the limit order.',
                            'Record each actual partial fill with contract-note fees; reconcile cash after exits.',
                            'Place and monitor protection manually. Stop execution and maximum loss are not guaranteed.',
                            'Cancel unfilled broker orders manually; release the local ticket only after confirming cancellation.',
                            'Exit before 15:15 IST; late exits may incur broker square-off charges or overnight delivery costs.']}
