"""Append-only actual manual-fill journal; never submits, changes or cancels orders.

SQLite BEGIN IMMEDIATE serializes cash/risk reservations. Recorded fills are facts,
including unfavorable/late fills; a risk breach halts new tickets rather than hiding it.
Sale proceeds require an explicit Groww settled-cash reconciliation before reuse.
"""
import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .calendar import IST


def iso_now():
    return datetime.now(timezone.utc).isoformat()


def aware(value):
    stamp=datetime.fromisoformat(value.replace('Z','+00:00'))
    if stamp.tzinfo is None: raise ValueError('Timestamp must include timezone')
    return stamp


def week(value):
    stamp=aware(value).astimezone(IST).date().isocalendar()
    return f'{stamp.year}-{stamp.week}'


class Journal:
    def __init__(self,root):
        self.path=Path(root)/'manual-journal.sqlite'
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as con:
            con.executescript('''CREATE TABLE IF NOT EXISTS events(
                seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL,
                kind TEXT NOT NULL, body TEXT NOT NULL, recorded_at TEXT NOT NULL);
                CREATE TRIGGER IF NOT EXISTS no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT,'append only'); END;
                CREATE TRIGGER IF NOT EXISTS no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT,'append only'); END;''')

    def connect(self):
        con=sqlite3.connect(self.path,timeout=30)
        con.execute('PRAGMA journal_mode=WAL')
        return con

    def events(self,con):
        return [{'seq':r[0],'id':r[1],'kind':r[2],'body':json.loads(r[3]),'recorded_at':r[4]}
                for r in con.execute('SELECT seq,id,kind,body,recorded_at FROM events ORDER BY seq')]

    def state(self,events,now=None):
        now=now or iso_now(); tickets={}; cash=5000.; realized=0.; loss=0.; halted=False; reasons=[]; reconciled=False
        for event in events:
            b=event['body']; kind=event['kind']
            if kind=='ticket': tickets[b['id']]={**b,'bought':0,'sold':0,'buy_value':0.,'buy_fees':0.,'open_cost':0.,'cancelled':False}
            elif kind=='cancel': tickets[b['ticket_id']]['cancelled']=True
            elif kind=='halt': halted=True; reasons.append(b['reason'])
            elif kind=='reconcile':
                cash=b['settled_cash']
                reconciled=True
                # Reconciliation never silently clears an existing risk halt.
            elif kind=='fill':
                t=tickets[b['ticket_id']]; value=b['quantity']*b['price']; fees=b['fees']
                if b['side']=='buy':
                    t['bought']+=b['quantity']; t['buy_value']+=value; t['buy_fees']+=fees; cash-=value+fees
                    t['open_cost']+=value+fees
                    if b['price']>t['entry_limit'] or t['bought']>t['quantity'] or t['cancelled']:
                        halted=True; reasons.append('Actual entry exceeded or followed the cancelled ticket')
                else:
                    unit_cost=t['open_cost']/(t['bought']-t['sold'])
                    pnl=value-fees-b['quantity']*unit_cost
                    t['open_cost']-=b['quantity']*unit_cost
                    realized+=pnl
                    if week(b['timestamp'])==week(now): loss+=max(0.,-pnl)
                    t['sold']+=b['quantity']
                t['last_fill']=b['timestamp']
                if aware(b['timestamp'])>aware(t['expires_at']) and b['side']=='buy':
                    halted=True; reasons.append('Actual entry occurred after ticket expiry')
        active=[t for t in tickets.values() if t['bought']>t['sold'] or (not t['cancelled'] and t['bought']<t['quantity'])]
        reserved=sum(max(0,t['quantity']-t['bought'])*t['entry_limit'] for t in active if not t['cancelled'])
        risk=sum(t['planned_loss'] for t in active)
        if cash<0 or loss>=150: halted=True; reasons.append('Cash or weekly realized loss limit breached')
        return {'settled_cash':round(cash,4),'available_cash':round(max(0,min(5000.,cash)-reserved),4),
                'realized_net':round(realized,4),'weekly_losses':round(loss,4),'reserved_risk':round(risk,4),
                'remaining_weekly_loss':round(max(0,150-loss-risk),4),'opening_cash_reconciled':reconciled,'halted':halted,'halt_reasons':reasons,
                'active':active,'tickets':list(tickets.values()),'events':events}

    def snapshot(self,now=None):
        with self.connect() as con: return self.state(self.events(con),now)

    def append(self,kind,body,event_id=None,now=None):
        now=now or iso_now(); event_id=event_id or uuid4().hex
        with self.connect() as con:
            con.execute('BEGIN IMMEDIATE')
            old=con.execute('SELECT kind,body FROM events WHERE id=?',(event_id,)).fetchone()
            serialized=json.dumps(body,sort_keys=True,allow_nan=False)
            if old:
                if old!=(kind,serialized): raise ValueError('Idempotency key reused with different content')
                return self.state(self.events(con),now)
            state=self.state(self.events(con),now)
            if kind=='ticket':
                if not state['opening_cash_reconciled']: raise ValueError('Confirm actual Groww settled cash before reserving a ticket')
                if state['halted'] or state['active']: raise ValueError('Halted or an existing ticket/position is open')
                if not 0<body['planned_loss']<=min(50,state['remaining_weekly_loss']) or body['reserved_cash']>state['available_cash']:
                    raise ValueError('Ticket exceeds cash or remaining risk budget')
            elif kind in ('fill','cancel'):
                matches=[t for t in state['tickets'] if t['id']==body['ticket_id']]
                if not matches: raise ValueError('Unknown journal ticket')
                t=matches[0]
                if kind=='fill':
                    if body['side'] not in ('buy','sell') or type(body['quantity']) is not int or not 0<body['quantity']<=10000:
                        raise ValueError('Invalid actual fill side or whole-share quantity')
                    if not all(math.isfinite(body[k]) for k in ('price','fees')) or body['price']<=0 or body['fees']<0:
                        raise ValueError('Actual finite price and nonnegative contract-note fees required')
                    stamp=aware(body['timestamp'])
                    if stamp>aware(now) or stamp<aware(t['created_at']): raise ValueError('Fill timestamp outside ticket lifetime')
                    if t.get('last_fill') and stamp<aware(t['last_fill']): raise ValueError('Record fills chronologically')
                    if body['side']=='sell' and body['quantity']>t['bought']-t['sold']: raise ValueError('Sell exceeds recorded holdings')
                    if not body.get('broker_reference','').strip(): raise ValueError('Actual broker fill reference required')
            elif kind=='reconcile':
                if state['active']: raise ValueError('Reconcile settled cash only after all local tickets/positions are closed')
                if not math.isfinite(body['settled_cash']) or not 0<=body['settled_cash']<=5000: raise ValueError('Settled cash must be within INR 0–5000')
                if len(body.get('reason','').strip())<10: raise ValueError('Record evidence for the Groww settled-cash reconciliation')
            elif kind!='halt': raise ValueError('Unsupported journal action')
            con.execute('INSERT INTO events(id,kind,body,recorded_at) VALUES(?,?,?,?)',(event_id,kind,serialized,now))
            return self.state(self.events(con),now)
