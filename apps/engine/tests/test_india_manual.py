"""Independent accounting, temporal integrity and execution-boundary tests."""
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from india.calendar import entry_window, prior_session, session, target_week
from india.costs import Costs, size_trade
from india.data import FEATURES, GrowwReadOnly, features, validate
from india.journal import Journal
from india.research import partitions, predict, prepare, simulate
from india.service import Service, prepare_ticket, verified_report


def fixture_bars(n=950):
    rng=np.random.default_rng(123)
    dates=pd.bdate_range('2021-01-01',periods=n).strftime('%Y-%m-%d')
    rows=[]
    for symbol in ['AAA','BBB']:
        close=100*np.exp(np.cumsum(rng.normal(.0002,.01,n)))
        for day,c in zip(dates,close):
            rows.append(dict(date=day,symbol=symbol,open=c*.999,high=c*1.02,low=c*.98,close=c,volume=2_000_000.,split=1.))
    return pd.DataFrame(rows)


def current(): return datetime.fromisoformat('2026-10-19T09:16:00+05:30')


def ticket_data():
    return dict(id='a'*32,symbol='AAA',quantity=10,entry_limit=100.,stop_trigger=98.,planned_loss=34.,reserved_cash=1006.,
                created_at=current().isoformat(),expires_at=(current()+timedelta(seconds=10)).isoformat())


def ready_journal(tmp_path):
    j=Journal(tmp_path)
    j.append('reconcile',{'settled_cash':5000.,'reason':'Actual opening Groww cash confirmed'},now=current().isoformat())
    return j


def test_calendar_and_unknown_year():
    assert [x['date'] for x in target_week() if x['open']]==['2026-10-19','2026-10-21','2026-10-22','2026-10-23']
    assert prior_session('2026-10-21')=='2026-10-19'
    assert entry_window(current())
    assert not entry_window(current().replace(hour=10))
    with pytest.raises(ValueError): session('2027-01-04')


def test_fee_components_independent_arithmetic():
    c=Costs(); buy=c.leg(1000,'buy'); sell=c.leg(1000,'sell')
    assert buy['brokerage']==5 and sell['brokerage']==5
    assert buy['stt']==0 and sell['stt']==1
    assert buy['stamp']==pytest.approx(.03)
    taxable=5+.0297+.001+.001
    assert buy['total']==pytest.approx(round(taxable*1.18+.03+.10,4))
    assert c.leg(1000,'sell','delivery')['dp']==20
    assert c.leg(100_000,'buy')['brokerage']==20
    assert c.leg(100,'buy')['brokerage']==2.5
    assert c.leg(50,'sell','delivery')['dp']==3.5
    with pytest.raises(ValueError): c.leg(float('nan'),'buy')


def test_whole_shares_and_fees_respect_cash_and_loss():
    c=Costs()
    for price in [15.,100.,499.,2500.,5000.,10000.]:
        for risk in [5.,20.,50.]:
            s=size_trade(price,price*.99,5000,risk,c)
            q=s['quantity']
            if q:
                exit_price=price*.99*.999
                assert q*price+c.leg(q*price,'buy')['total']<=5000
                assert q*(price-exit_price)+c.roundtrip(q,price,exit_price)<=risk+1e-9
    assert size_trade(100,99,5000,5)['quantity']==0
    assert size_trade(5000,4950)['quantity']==0


def test_future_changes_cannot_modify_past_features():
    bars=fixture_bars(160); cut='2021-06-01'
    before=features(bars); changed=bars.copy()
    changed.loc[changed.date>cut,['open','high','low','close']]*=3
    after=features(changed)
    pd.testing.assert_frame_equal(before.loc[before.date<=cut,FEATURES],after.loc[after.date<=cut,FEATURES])


def test_split_adjustment_is_causal_and_no_leak_into_previous_rows():
    bars=fixture_bars(100); sym=bars.symbol=='AAA'; day=sorted(bars.date.unique())[70]
    adjusted=bars.copy(); adjusted.loc[sym&(bars.date>=day),['open','high','low','close']]/=2
    adjusted.loc[sym&(bars.date>=day),'volume']*=2
    adjusted.loc[sym&(bars.date==day),'split']=2
    a=features(bars); b=features(adjusted)
    np.testing.assert_allclose(a[FEATURES].to_numpy(),b[FEATURES].to_numpy(),atol=1e-12)


def test_duplicate_and_missing_bars():
    bars=fixture_bars(100)
    with pytest.raises(ValueError): validate(pd.concat([bars,bars.iloc[:1]]))
    missing=sorted(bars.date.unique())[80]
    data=prepare(bars[~((bars.symbol=='AAA')&(bars.date==missing))])
    # The previous row must not jump over an absent source session.
    assert not ((data.symbol=='AAA')&(data.next_date==sorted(bars.date.unique())[81])&(data.date<missing)).any()


def test_purge_grouped_dates_and_final_holdout():
    f=prepare(fixture_bars()); folds,final,cutoff=partitions(f)
    assert len(folds)>=2
    for train,val,test in folds:
        assert train.label_end.max()<val.signal_time.min()
        assert val.label_end.max()<test.signal_time.min()
        assert set(train.date).isdisjoint(test.date)
        assert set(val.date).isdisjoint(test.date)
        assert test.label_end.max()<final.signal_time.min()
        assert test.groupby('date').symbol.nunique().eq(2).all()
    assert final.date.min()==cutoff


def test_cpu_inference_known_weights():
    cp={'kind':'linear','features':FEATURES,'mean':[0]*8,'scale':[1]*8,'layers':[{'weight':[[1]*8],'bias':[0]}],'temperature':1}
    f=pd.DataFrame(np.zeros((2,8)),columns=FEATURES); f.iloc[1,0]=np.log(3)
    np.testing.assert_allclose(predict(cp,f),[.5,.75])


def test_no_signal_preserves_cash_and_weekly_loss_ceiling():
    f=prepare(fixture_bars(100))
    empty=simulate(f,np.zeros(len(f)),'mlp')
    assert empty['net_inr']==0 and empty['trade_count']==0
    loss=simulate(f,np.ones(len(f)),'mlp')
    by_week={}
    for t in loss['trades']:
        week=str(pd.Timestamp(t['date']).isocalendar()[:2]); by_week[week]=by_week.get(week,0)+max(0,-t['net'])
        assert t['planned_loss']<=50
    assert all(x<=150.00001 for x in by_week.values())
    assert all(row['equity']>=0 for row in loss['curve'])
    assert all(row['available_cash']>=-1e-7 for row in loss['curve'])
    assert any(row['unsettled_proceeds']>0 for row in loss['curve'])
    assert loss['net_inr']==pytest.approx(sum(t['net'] for t in loss['trades']))


def test_get_only_adapter_and_missing_token(monkeypatch):
    monkeypatch.delenv('GROWW_ACCESS_TOKEN',raising=False)
    with pytest.raises(ValueError,match='Only'): GrowwReadOnly().get('order/create',{})
    with pytest.raises(ValueError,match='unavailable'): GrowwReadOnly().quote('SBIN')


def test_ticket_expiry_spread_depth_and_staleness(tmp_path):
    state=ready_journal(tmp_path).snapshot(current().isoformat())
    s={'symbol':'AAA','date':'2026-10-16','stop_fraction':.01,'adv20':1e9}
    q={'symbol':'AAA','bid':99.95,'ask':100.,'bid_size':10000,'ask_size':10000,'timestamp':current().isoformat(),'upper':110.,'lower':90.,'source':'groww'}
    ticket=prepare_ticket(s,q,state,current(),'test')
    assert ticket['quantity']>0 and ticket['automatic_submission'] is False
    for bad in [dict(q,timestamp=(current()-timedelta(seconds=11)).isoformat()),dict(q,bid=95),dict(q,ask_size=1),dict(q,ask=110)]:
        with pytest.raises(ValueError): prepare_ticket(s,bad,state,current(),'test')


def test_journal_atomic_reservation_and_immutability(tmp_path):
    j=ready_journal(tmp_path); t=ticket_data()
    def reserve(i):
        try: j.append('ticket',dict(t,id=str(i)*32),now=current().isoformat()); return True
        except ValueError: return False
    with ThreadPoolExecutor(max_workers=2) as pool: assert sum(pool.map(reserve,[1,2]))==1
    with j.connect() as con:
        with pytest.raises(sqlite3.IntegrityError): con.execute('DELETE FROM events')


def test_actual_fills_idempotency_cash_settlement_and_net_loss(tmp_path):
    j=ready_journal(tmp_path); t=ticket_data(); j.append('ticket',t,now=current().isoformat())
    b=dict(ticket_id=t['id'],side='buy',quantity=10,price=100.,fees=6.,timestamp=current().isoformat(),broker_reference='fill-1')
    j.append('fill',b,'fill-1',current().isoformat()); j.append('fill',b,'fill-1',current().isoformat())
    s=dict(b,side='sell',price=98.,fees=7.,broker_reference='fill-2')
    state=j.append('fill',s,'fill-2',current().isoformat())
    assert state['realized_net']==pytest.approx(-33)
    assert state['weekly_losses']==pytest.approx(33)
    assert state['settled_cash']==pytest.approx(3994)  # no implicit use of unsettled proceeds
    assert not state['active']
    with pytest.raises(ValueError): j.append('fill',dict(b,price=99),'fill-1',current().isoformat())
    with pytest.raises(ValueError): j.append('fill',s,'extra-sale',current().isoformat())


def test_gap_loss_is_recorded_and_halts_not_rejected(tmp_path):
    j=ready_journal(tmp_path); t=ticket_data(); j.append('ticket',t,now=current().isoformat())
    b=dict(ticket_id=t['id'],side='buy',quantity=10,price=100.,fees=6.,timestamp=current().isoformat(),broker_reference='entry')
    j.append('fill',b,now=current().isoformat())
    state=j.append('fill',dict(b,side='sell',price=70.,fees=7.,broker_reference='exit'),now=current().isoformat())
    assert state['realized_net']==-313 and state['halted']
    with pytest.raises(ValueError): j.append('ticket',dict(t,id='b'*32),now=current().isoformat())


def test_empty_service_fails_closed(tmp_path):
    service=Service(tmp_path)
    assert service.overview()['automatic_orders'] is False
    assert service.signals(current())['decision']=='NO TRADE'
    with pytest.raises(ValueError,match='NO TRADE'): service.ticket('SBIN',current())


def test_corrupted_research_is_rejected(tmp_path):
    (tmp_path/'report.json').write_text('{}')
    (tmp_path/'checksums.json').write_text(json.dumps({'report.json':'0'*64}))
    with pytest.raises(ValueError,match='integrity'): verified_report(tmp_path)


def test_api_authentication_and_manual_boundary(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from flagship_api import app
    monkeypatch.setenv('Q_ENGINE_TOKEN','india-test-token')
    monkeypatch.setenv('Q_INDIA_DATA',str(tmp_path))
    client=TestClient(app)
    assert client.get('/api/research/india').status_code==403
    headers={'x-q-engine-token':'india-test-token'}
    response=client.get('/api/research/india',headers=headers)
    assert response.status_code==200 and response.json()['automatic_orders'] is False
    assert client.post('/api/research/india/tickets',headers=headers,json={'symbol':'SBIN'}).status_code==422
    assert client.post('/api/research/india/tickets',headers=headers,json={'symbol':'SBIN','override':True}).status_code==422
    assert client.post('/api/research/india/orders',headers=headers,json={}).status_code==404
    assert client.post('/api/research/india/research',headers=headers,json={'dataset':'../../x'}).status_code==422
