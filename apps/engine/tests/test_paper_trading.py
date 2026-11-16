from copy import deepcopy
from datetime import datetime, timedelta, timezone
import sqlite3
import pytest
from paper.models import Deployment, Bar, Session, Action, Feed
from paper import accounting as ac
from paper.service import PaperService


def config(**changes):
    return Deployment.model_validate({'name': 'Fixture', 'market': 'US', 'currency': 'USD',
        'provider': 'fixture', 'universe': ['A'], 'capital': 1000,
        'commission_bps': 0, 'slippage_bps': 0, 'participation': 1,
        'strategies': [{'name': 'A', 'adapter': 'allocation', 'reference': 'fixture', 'parameters': {'weights': {'A': .5}}}], **changes})


def bar(day=2, **changes):
    return Bar.model_validate({'symbol': 'A', 'session': f'2026-09-{day:02}',
        'start': f'2026-09-{day:02}T13:30:00+00:00', 'end': f'2026-09-{day:02}T20:00:00+00:00',
        'received_at': f'2026-09-{day:02}T20:01:00+00:00',
        'open': 10, 'high': 12, 'low': 9, 'close': 11, 'volume': 10000, **changes})


def session(day=2):
    b = bar(day)
    return Session(date=b.session, open=b.start, close=b.end, settlement=f'2026-09-{day+1:02}T13:30:00+00:00')


def working_account():
    a = ac.account(1000)
    a['marks']['A'] = 10
    return a


def order(a, cfg, **changes):
    ac.submit(a, [{'symbol': 'A', 'side': 'BUY', 'quantity': 10, **changes}], cfg,
              '2026-09-01T20:01:00+00:00', '2026-09-01T20:00:00+00:00', '2026-09-02', 'signal')


def test_cash_fees_next_open_and_no_same_bar():
    a, cfg = working_account(), config(commission_bps=10, slippage_bps=10)
    order(a, cfg)
    ac.process_bar(a, bar(1), 1000, session(1), cfg, bar(1).received_at)
    assert not a['fills']
    ac.process_bar(a, bar(), 1000, session(), cfg, bar().received_at)
    expected_price = 10 * 1.001
    assert a['cash'] == pytest.approx(1000 - 10 * expected_price * 1.001)
    assert a['nav'] == pytest.approx(a['cash'] + 110)
    assert a['positions']['A']['quantity'] == 10
    assert ac.reserved(a) == 0


def test_gap_does_not_overdraw_and_day_remainder_expires():
    a, cfg = working_account(), config()
    order(a, cfg, quantity=100)
    b = bar(open=20, high=22, low=19, close=21)
    ac.process_bar(a, b, 1000, session(), cfg, b.received_at)
    assert a['cash'] >= 0
    assert a['positions']['A']['quantity'] == 50
    assert a['orders'][0]['status'] == 'expired'


def test_settlement_and_corporate_actions_reconcile():
    a, cfg = working_account(), config()
    order(a, cfg)
    ac.process_bar(a, bar(), 1000, session(), cfg, bar().received_at)
    dividend = Action(id='d', symbol='A', effective_at=bar(3).start, kind='dividend', amount=2, pay_at=bar(5).start)
    ac.corporate_action(a, dividend, bar(3))
    ac.corporate_action(a, dividend, bar(3))
    assert sum(x['amount'] for x in a['receivables']) == 20
    split = Action(id='s', symbol='A', effective_at=bar(3).start, kind='split', amount=.25)
    ac.corporate_action(a, split, bar(3, open=40, high=44, low=39, close=44))
    assert a['positions']['A']['quantity'] == 2
    assert a['cash'] == 920
    ac.submit(a, [{'symbol':'A','side':'SELL','quantity':2}], cfg, bar(3).received_at, bar(3).end, '2026-09-04', 'sell')
    ac.process_bar(a, bar(4), 1000, session(4), cfg, bar(4).received_at)
    assert a['cash'] == 920
    assert sum(x['amount'] for x in a['unsettled']) == 20
    ac.settle(a, bar(5).start)
    assert a['cash'] == 960
    assert not a['receivables'] and not a['unsettled']


def minute(n=0, **changes):
    start = datetime(2026,9,2,13,30,tzinfo=timezone.utc)+timedelta(minutes=n)
    return bar(start=start.isoformat(),end=(start+timedelta(minutes=1)).isoformat(),received_at=(start+timedelta(minutes=1,seconds=1)).isoformat(),**changes)


def test_limit_partial_fill_and_stop_limit_ambiguity():
    cfg = config(interval='1m', participation=.1)
    a = working_account()
    order(a, cfg, type='limit', limit=9.5, tif='GTC')
    ac.process_bar(a, minute(), 20, session(), cfg, minute().received_at)
    assert a['fills'][0]['quantity'] == 2
    assert a['fills'][0]['price'] <= 9.5
    assert a['orders'][0]['status'] == 'partial'
    b = working_account()
    order(b, cfg, type='stop_limit', stop=11, limit=11.5, tif='GTC')
    ac.process_bar(b, minute(), 1000, session(), cfg, minute().received_at)
    assert not b['fills'] and b['orders'][0]['triggered_at']
    ac.process_bar(b, minute(1), 1000, session(), cfg, minute(1).received_at)
    assert b['fills'][0]['price'] <= 11.5


def test_stop_gaps_and_sell_reservations():
    cfg, a = config(interval='1m'), working_account()
    order(a, cfg, type='stop', stop=11)
    ac.process_bar(a, minute(open=15,high=16,low=14,close=15),1000,session(),cfg,minute().received_at)
    assert a['fills'][0]['price'] == 15
    with pytest.raises(ValueError, match='unreserved holdings'):
        order(a, cfg, side='SELL', quantity=11)


def feed_at(at, last=1):
    return {'provider':'fixture','market':'US','interval':'1d','price_basis':'raw','source':'explicit deterministic test fixture',
            'generated_at':at,'calendar_version':'test-only','rules_version':'test-only',
            'actions_complete_through':'2026-09-10T00:00:00+00:00',
            'sessions':[session(i).model_dump() for i in range(1,8)],
            'bars':[bar(i).model_dump() for i in range(1,last+1)],'actions':[]}


def test_forward_runner_restart_dedup_and_immutable_export(tmp_path):
    clock = ['2026-09-01T20:02:00+00:00']
    data = [feed_at(clock[0])]
    service = PaperService(tmp_path, lambda cfg:data[0], lambda:clock[0])
    key = service.create(config())['id']
    assert service.readiness(key)['ready']
    service.control(key,'activate')
    clock[0] = '2026-09-02T20:02:00+00:00'; data[0] = feed_at(clock[0],2)
    service.process(key)
    assert not service.get(key)['accounts']['0']['fills']
    assert service.get(key)['accounts']['0']['orders']
    clock[0] = '2026-09-03T20:02:00+00:00'; data[0] = feed_at(clock[0],3)
    restarted = PaperService(tmp_path, lambda cfg:data[0], lambda:clock[0])
    restarted.process(key)
    first = restarted.get(key)['accounts']['0']
    restarted.process(key)
    assert restarted.get(key)['accounts']['0'] == first
    assert len(first['fills']) == 1
    assert restarted.ledger.export(key)['state']['accounts']['0'] == first
    with pytest.raises(sqlite3.IntegrityError):
        with restarted.ledger.transaction() as db: db.execute('DELETE FROM events')


def test_missed_decisions_no_backfill_funded_totals_and_pause(tmp_path):
    clock = ['2026-09-01T20:02:00+00:00']; data=[feed_at(clock[0])]
    strategies=[{'name':s,'adapter':'allocation','reference':s,'parameters':{'weights':{'A':.5}},'budget':.5} for s in ['one','two']]
    service=PaperService(tmp_path,lambda cfg:data[0],lambda:clock[0])
    key=service.create(config(mode='funded',strategies=strategies))['id']
    service.control(key,'activate')
    clock[0]='2026-09-03T20:02:00+00:00'; data[0]=feed_at(clock[0],3)
    service.process(key)
    state=service.get(key)
    assert any('Missed decision' in x for x in state['exceptions'])
    assert state['nav']==sum(a['nav'] for a in state['accounts'].values())==1000
    assert all(len(a['orders'])==1 for a in state['accounts'].values())
    service.control(key,'pause')
    assert all(not ac.pending(a) for a in service.get(key)['accounts'].values())
    service.control(key,'stop')
    assert service.get(key)['status']=='stopped'


def test_feed_future_and_calendar_guards():
    raw=feed_at('2026-09-01T20:02:00+00:00')
    raw['bars'][0]['start']='2026-09-01T12:00:00+00:00'
    with pytest.raises(ValueError,match='session'): Feed.model_validate(raw)
    with pytest.raises(ValueError,match='separate'): config(currency='INR')


def test_custom_activation_blocked_and_frozen_config(tmp_path):
    service=PaperService(tmp_path,lambda cfg:feed_at('2026-09-01T20:02:00+00:00'),lambda:'2026-09-01T20:02:00+00:00')
    cfg=config(strategies=[{'name':'custom','adapter':'custom_python','reference':'version','parameters':{}}])
    key=service.create(cfg)['id']; cfg.name='Edited'
    assert service.get(key)['config']['spec']['name']=='Fixture'
    with pytest.raises(ValueError,match='isolated'): service.control(key,'activate')


def test_future_data_cannot_change_terminal_signal():
    from paper.models import StrategySpec
    from paper.strategies import terminal
    spec=StrategySpec(name='trend',adapter='terminal',reference='f',parameters={'symbol':'A','kind':'Time-series momentum','lookback':2,'slow':3,'allocation':.5})
    history={'A':[bar(i,close=10+i,high=20) for i in range(1,5)]}
    past={'A':history['A'][:3]}
    before=terminal(spec,past,[],False)
    history['A'][3]=bar(4,close=999,high=1000)
    assert terminal(spec,past,[],False)==before


def test_explicit_calendar_missing_sessions_and_revised_history_block(tmp_path):
    clock=['2026-09-01T20:02:00+00:00']; data=[feed_at(clock[0])]
    s=PaperService(tmp_path,lambda cfg:data[0],lambda:clock[0])
    key=s.create(config())['id'];s.control(key,'activate')
    clock[0]='2026-09-03T20:02:00+00:00';data[0]=feed_at(clock[0],3)
    data[0]['bars']=[b for b in data[0]['bars'] if b['session']!='2026-09-02']
    s.process(key)
    assert 'Missing exchange session' in s.get(key)['exceptions'][0]
    assert not s.get(key)['accounts']['0']['orders']
    data[0]=feed_at(clock[0],3);s.process(key)
    data[0]['bars'][0]['close']=10.5
    with pytest.raises(ValueError,match='revised'):s.process(key)


def test_paused_account_keeps_corporate_actions_through_resume(tmp_path):
    clock=['2026-09-01T20:02:00+00:00'];data=[feed_at(clock[0])]
    s=PaperService(tmp_path,lambda cfg:data[0],lambda:clock[0])
    key=s.create(config())['id'];s.control(key,'activate')
    for day in (2,3):
        clock[0]=f'2026-09-{day:02}T20:02:00+00:00';data[0]=feed_at(clock[0],day);s.process(key)
    held=s.get(key)['accounts']['0']['positions']['A']['quantity']
    s.control(key,'pause')
    clock[0]='2026-09-04T20:02:00+00:00';data[0]=feed_at(clock[0],4)
    data[0]['actions']=[{'id':'div','symbol':'A','effective_at':bar(4).start,'kind':'dividend','amount':1}]
    s.control(key,'resume');s.process(key)
    assert sum(x['amount'] for x in s.get(key)['accounts']['0']['receivables'])==held


def test_gross_risk_target_clips_buys_without_spending_unsettled_proceeds():
    a=working_account();cfg=config(max_gross=.8)
    a['cash']=100;a['positions']['A']={'quantity':90,'cost':900}
    ac.mark(a)
    intents=ac.target_orders(a,{'A':.8},cfg)
    assert intents==[{'symbol':'A','side':'SELL','quantity':10}]
    ac.submit(a,intents,cfg,bar(1).received_at,bar(1).end,'2026-09-02','rebalance')
    assert a['cash']==100


def test_multi_instrument_open_fill_does_not_see_same_bar_close():
    cfg=config(universe=['A','B'])
    a=working_account();a['marks']['B']=10
    ac.submit(a,[{'symbol':'A','side':'BUY','quantity':50},{'symbol':'B','side':'BUY','quantity':50}],cfg,bar(1).received_at,bar(1).end,'2026-09-02','multi')
    ac.process_bar(a,bar(close=100,high=100),1000,session(),cfg,bar().received_at,mark_close=False)
    ac.process_bar(a,bar(symbol='B'),1000,session(),cfg,bar().received_at,mark_close=False)
    assert a['marks']=={'A':10,'B':10}
    assert a['positions']['A']['quantity']==a['positions']['B']['quantity']==50
    assert a['cash']==0


def test_api_activation_controls_export_and_separate_evidence(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from flagship_api import app
    from paper import api
    clock=['2026-09-01T20:02:00+00:00'];data=[feed_at(clock[0])]
    service=PaperService(tmp_path,lambda cfg:data[0],lambda:clock[0])
    monkeypatch.setattr(api,'_service',service)
    monkeypatch.setenv('Q_ENGINE_TOKEN','test-paper-token')
    client=TestClient(app,headers={'x-q-engine-token':'test-paper-token'})
    assert TestClient(app).get('/api/paper/deployments').status_code==403
    response=client.post('/api/paper/deployments',json=config().model_dump())
    assert response.status_code==201,response.text
    key=response.json()['id']
    assert client.post(f'/api/paper/deployments/{key}/control',json={'action':'activate'}).status_code==200
    clock[0]='2026-09-02T20:02:00+00:00';data[0]=feed_at(clock[0],2);service.process(key)
    exported=client.get(f'/api/paper/deployments/{key}/export')
    assert exported.status_code==200 and exported.json()['inputs']
    evidence=client.get(f'/api/paper/deployments/{key}/evidence').json()
    assert evidence['source']=='q_automated_simulation' and evidence['broker_verified'] is False
    assert evidence['observations']==1
    assert evidence['mean_cost_drift_bps'] is None
    orders=client.get(f'/api/paper/deployments/{key}/orders').json()['orders']
    assert client.post(f'/api/paper/deployments/{key}/cancel-order',json={'order_id':orders[0]['id']}).status_code==200
    assert service.get(key)['accounts']['0']['orders'][0]['status']=='cancelled'


def test_custom_worker_source_paths_and_pinned_images(monkeypatch):
    from paper.worker import validate_files,image_for
    from paper.models import StrategySpec
    spec=StrategySpec(name='custom',adapter='custom_python',reference='x',parameters={'snapshot':{'files':{'paper_adapter.py':'def decide(context): return {"targets": {}}','../escape.py':'bad'}}})
    with pytest.raises(ValueError,match='path'): validate_files(spec)
    monkeypatch.delenv('Q_PAPER_PYTHON_IMAGE',raising=False)
    with pytest.raises(ValueError,match='pinned'): image_for('custom_python')


def test_funded_sleeves_share_instrument_liquidity_cap(tmp_path):
    clock=['2026-09-01T20:02:00+00:00'];data=[feed_at(clock[0])]
    strategies=[{'name':s,'adapter':'allocation','reference':s,'parameters':{'weights':{'A':.5}},'budget':.5} for s in ['one','two']]
    service=PaperService(tmp_path,lambda cfg:data[0],lambda:clock[0])
    key=service.create(config(mode='funded',strategies=strategies,participation=.1))['id']
    service.control(key,'activate')
    for day in (2,3):
        clock[0]=f'2026-09-{day:02}T20:02:00+00:00';data[0]=feed_at(clock[0],day)
        for b in data[0]['bars']: b['volume']=100
        service.process(key)
    state=service.get(key)
    assert sum(f['quantity'] for a in state['accounts'].values() for f in a['fills'])==10
    assert all(a['cash']>=0 for a in state['accounts'].values())
    assert state['nav']==sum(ac.value(a) for a in state['accounts'].values())


def test_combined_allocation_uses_one_account_with_weighted_targets(tmp_path):
    clock=['2026-09-01T20:02:00+00:00'];data=[feed_at(clock[0])]
    def include_b():
        data[0]['bars'] += [{**b,'symbol':'B'} for b in data[0]['bars']]
    include_b()
    specs=[{'name':s,'adapter':'allocation','reference':s,'parameters':{'weights':{s:w}},'budget':.5} for s,w in [('A',.8),('B',.6)]]
    service=PaperService(tmp_path,lambda cfg:data[0],lambda:clock[0])
    key=service.create(config(mode='combined',universe=['A','B'],strategies=specs))['id'];service.control(key,'activate')
    clock[0]='2026-09-02T20:02:00+00:00';data[0]=feed_at(clock[0],2);include_b();service.process(key)
    account=service.get(key)['accounts']
    assert list(account)==['0']
    assert account['0']['targets']=={'A':.4,'B':.3}
    assert ac.reserved(account['0'])<=account['0']['cash']


def test_one_missing_minute_blocks_progression(tmp_path):
    clock=['2026-09-01T20:02:00+00:00'];data=[feed_at(clock[0])]
    data[0]['interval']='1m'
    data[0]['bars']=[bar(1,start='2026-09-01T19:59:00+00:00').model_dump()]
    service=PaperService(tmp_path,lambda cfg:data[0],lambda:clock[0])
    key=service.create(config(interval='1m',rebalance='every_bar'))['id'];service.control(key,'activate')
    clock[0]='2026-09-02T13:34:00+00:00'
    data[0]['generated_at']=clock[0]
    data[0]['bars'] += [minute(0).model_dump(),minute(2).model_dump()]
    service.process(key)
    state=service.get(key)
    assert state['last_bar']==minute(0).end
    assert 'Missing minute bars' in state['exceptions'][-1]


def test_signal_failure_preserves_fills_then_pauses(tmp_path,monkeypatch):
    clock=['2026-09-01T20:02:00+00:00'];data=[feed_at(clock[0])]
    service=PaperService(tmp_path,lambda cfg:data[0],lambda:clock[0])
    key=service.create(config())['id'];service.control(key,'activate')
    clock[0]='2026-09-02T20:02:00+00:00';data[0]=feed_at(clock[0],2);service.process(key)
    def broken(*args): raise ValueError('Fixture strategy failed')
    monkeypatch.setattr('paper.service.targets',broken)
    clock[0]='2026-09-03T20:02:00+00:00';data[0]=feed_at(clock[0],3);service.process(key)
    state=service.get(key)
    assert state['status']=='paused'
    assert len(state['accounts']['0']['fills'])==1
    assert 'Fixture strategy failed' in state['halt_reason']
    assert service.ledger.export(key)['state']['status']=='paused'


def test_background_runner_processes_without_browser_and_survives_restart(tmp_path):
    import time
    clock=['2026-09-01T20:02:00+00:00'];data=[feed_at(clock[0])]
    service=PaperService(tmp_path,lambda cfg:data[0],lambda:clock[0])
    key=service.create(config())['id'];service.control(key,'activate')
    for day in (2,3):
        clock[0]=f'2026-09-{day:02}T20:02:00+00:00';data[0]=feed_at(clock[0],day)
        service=PaperService(tmp_path,lambda cfg:data[0],lambda:clock[0])
        service.start()
        try:
            deadline=time.monotonic()+5
            while service.get(key)['last_bar']!=bar(day).end and time.monotonic()<deadline:time.sleep(.02)
            assert service.get(key)['last_bar']==bar(day).end
        finally:service.stop()
    assert len(service.get(key)['accounts']['0']['fills'])==1


def test_equivalent_utc_instants_cannot_duplicate_bars_and_errors_redact_inputs(tmp_path):
    raw=feed_at('2026-09-01T20:02:00+00:00')
    duplicate={**raw['bars'][0],'start':'2026-09-01T09:30:00-04:00','end':'2026-09-01T16:00:00-04:00'}
    raw['bars'].append(duplicate)
    with pytest.raises(ValueError,match='Duplicate'):Feed.model_validate(raw)
    raw=feed_at('2026-09-01T20:02:00+00:00');raw['credential']='DO_NOT_EXPOSE_THIS'
    service=PaperService(tmp_path,lambda cfg:raw,lambda:'2026-09-01T20:02:00+00:00')
    key=service.create(config())['id'];ready=service.readiness(key)
    assert not ready['ready'] and 'DO_NOT_EXPOSE_THIS' not in str(ready)
