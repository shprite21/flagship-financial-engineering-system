"""Observed data only. Immutable downloads, explicit quality limitations, no fallback."""
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

import numpy as np
import pandas as pd

from .calendar import IST

SYMBOLS = ('RELIANCE', 'ICICIBANK', 'SBIN', 'ITC', 'INFY', 'HINDUNILVR', 'AXISBANK', 'LT')
FEATURES = ['ret1', 'ret5', 'ret20', 'vol20', 'range5', 'volume_ratio', 'trend', 'gap']


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, allow_nan=False, default=str), encoding='utf-8')


def symbol_ok(symbol):
    if not re.fullmatch(r'[A-Z0-9&-]{1,25}', symbol):
        raise ValueError('Invalid NSE cash symbol')
    return symbol


class GrowwReadOnly:
    """Allowlisted GET adapter. Credentials never leave the server or enter artifacts."""
    def get(self, endpoint, params):
        if endpoint not in ('historical/candles', 'live-data/quote'):
            raise ValueError('Only historical candles and quotes are supported')
        token = os.environ.get('GROWW_ACCESS_TOKEN')
        if not token:
            raise ValueError('GROWW_ACCESS_TOKEN is unavailable; configure it on the local server')
        request = Request('https://api.groww.in/v1/'+endpoint+'?'+urlencode(params),
                          headers={'Authorization': 'Bearer '+token, 'X-API-VERSION': '1.0', 'Accept': 'application/json'})
        try:
            with urlopen(request, timeout=30) as response:
                raw = response.read(20_000_001)
                if len(raw) > 20_000_000:
                    raise ValueError('Provider response too large')
                value = json.loads(raw)
        except (URLError, HTTPError, json.JSONDecodeError):
            raise ValueError('Groww read-only data request failed; verify token and subscription') from None
        if value.get('status') != 'SUCCESS':
            raise ValueError('Groww did not return SUCCESS')
        return value['payload']

    def history(self, symbol, start, end):
        symbol_ok(symbol)
        # Small chunks honor the conservative daily request bound and retain exact rows.
        parts = []
        for left in pd.date_range(start, end, freq='90D'):
            right = min(left+pd.Timedelta(days=89), pd.Timestamp(end))
            parts.extend(self.get('historical/candles', dict(exchange='NSE', segment='CASH', groww_symbol='NSE-'+symbol,
                         start_time=left.strftime('%Y-%m-%d 00:00:00'), end_time=right.strftime('%Y-%m-%d 23:59:59'), candle_interval='1day'))['candles'])
            time.sleep(.15)
        if not parts:
            raise ValueError('No observed Groww bars')
        frame = pd.DataFrame([r[:6] for r in parts], columns=['date','open','high','low','close','volume'])
        frame['date'] = pd.to_datetime(frame.date).dt.strftime('%Y-%m-%d')
        frame['symbol'], frame['split'] = symbol, 1.
        return frame, {'provider': 'groww', 'corporate_actions_verified': False,
                       'nominal_prices_verified': False, 'warning': 'Daily bars need corporate-action and nominal-price audit'}

    def quote(self, symbol):
        payload = self.get('live-data/quote', dict(exchange='NSE', segment='CASH', trading_symbol=symbol_ok(symbol)))
        required = ('bid_price','offer_price','bid_quantity','offer_quantity','last_trade_time','upper_circuit_limit','lower_circuit_limit')
        if any(k not in payload for k in required):
            raise ValueError('Quote missing timestamp, depth or circuit limits')
        return {'symbol': symbol, 'bid': float(payload['bid_price']), 'ask': float(payload['offer_price']),
                'bid_size': int(payload['bid_quantity']), 'ask_size': int(payload['offer_quantity']),
                'timestamp': datetime.fromtimestamp(payload['last_trade_time']/1000, timezone.utc).isoformat(),
                'upper': float(payload['upper_circuit_limit']), 'lower': float(payload['lower_circuit_limit']),
                'source': 'groww', 'timestamp_basis': 'last_trade_time; not a certified book timestamp'}


def yahoo_history(symbol, start, end):
    symbol_ok(symbol)
    params = dict(period1=int(pd.Timestamp(start, tz='UTC').timestamp()), period2=int(pd.Timestamp(end, tz='UTC').timestamp()),
                  interval='1d', events='div,splits')
    req = Request('https://query1.finance.yahoo.com/v8/finance/chart/'+symbol+'.NS?'+urlencode(params), headers={'User-Agent':'Mozilla/5.0'})
    try:
        with urlopen(req, timeout=30) as response:
            raw = response.read(10_000_000)
        value = json.loads(raw)['chart']['result'][0]
    except (URLError, HTTPError, TypeError, KeyError, json.JSONDecodeError):
        raise ValueError('Yahoo observed history unavailable for '+symbol) from None
    q = value['indicators']['quote'][0]
    frame = pd.DataFrame({k:q[k] for k in ('open','high','low','close','volume')})
    frame['volume'] = frame['volume'].astype(float)
    frame['date'] = pd.to_datetime(value['timestamp'], unit='s', utc=True).tz_convert(IST).strftime('%Y-%m-%d')
    frame['symbol'], frame['split'] = symbol, 1.
    # Yahoo OHLC are split-adjusted even without dividend adjustment. Reconstruct
    # historical nominal units; never claim exchange-certified execution prices.
    for event in sorted(value.get('events',{}).get('splits',{}).values(), key=lambda v:v['date']):
        day = datetime.fromtimestamp(event['date'], IST).date().isoformat()
        ratio = event['numerator']/event['denominator']
        earlier = frame.date < day
        frame.loc[earlier, ['open','high','low','close']] *= ratio
        frame.loc[earlier, 'volume'] /= ratio
        frame.loc[frame.date == day, 'split'] = ratio
    return frame, {'provider':'yahoo', 'raw_response_sha256':sha(raw), 'raw_response':json.loads(raw),
                   'corporate_actions_verified':False, 'nominal_prices_verified':False,
                   'warning':'Reconstructed nominal units; selected survivors; revisions and actions unaudited'}


def validate(frame):
    frame = frame.copy()
    required = ['date','symbol','open','high','low','close','volume','split']
    if any(c not in frame for c in required) or frame.empty:
        raise ValueError('Observed daily OHLCV schema is incomplete')
    if frame.duplicated(['symbol','date']).any():
        raise ValueError('Duplicate symbol/session bars')
    pd.to_datetime(frame.date, format='%Y-%m-%d', errors='raise')
    numbers = frame[['open','high','low','close','volume','split']].to_numpy(float)
    if not np.isfinite(numbers).all() or (numbers <= 0).any():
        raise ValueError('Nonfinite, nonpositive or zero-volume observations; inspect source')
    if ((frame.high < frame[['open','close','low']].max(axis=1)) | (frame.low > frame[['open','close','high']].min(axis=1))).any():
        raise ValueError('Invalid OHLC bounds')
    return frame.sort_values(['symbol','date']).reset_index(drop=True)


def ingest(root, provider='yahoo', start='2021-01-01', end='2026-10-17', symbols=SYMBOLS):
    frames, metadata = [], []
    for symbol in symbols:
        frame, meta = (yahoo_history(symbol,start,end) if provider == 'yahoo' else GrowwReadOnly().history(symbol,start,end))
        columns=['open','high','low','close','volume','split']
        bad=(~np.isfinite(frame[columns].to_numpy(float))).any(axis=1)|(frame[columns]<=0).any(axis=1)
        # Quarantine source omissions explicitly. Never manufacture or forward-fill bars.
        meta['quarantined_rows']=json.loads(frame.loc[bad].to_json(orient='records'))
        frame=frame.loc[~bad].copy()
        frames.append(validate(frame))
        metadata.append({'symbol':symbol, **meta})
        print(json.dumps({'symbol':symbol,'rows':len(frame),'quarantined':int(bad.sum()),'last':frame.date.max()}),flush=True)
    frame = validate(pd.concat(frames, ignore_index=True))
    raw = frame.to_csv(index=False).encode()
    key = sha(raw)
    dest = Path(root)/'datasets'/key
    if dest.exists():
        if (dest/'bars.csv').read_bytes()!=raw or not (dest/'manifest.json').is_file():
            raise ValueError('Existing dataset is incomplete or corrupted')
        return key  # Never replace provenance of an existing immutable snapshot.
    dest.mkdir(parents=True, exist_ok=True)
    (dest/'bars.csv').write_bytes(raw)
    save_json(dest/'manifest.json', {'id':key,'provider':provider,'captured_at':datetime.now(timezone.utc).isoformat(),
        'start':start,'end_exclusive':end,'symbols':list(symbols),'rows':len(frame),'first':frame.date.min(),'last':frame.date.max(),
        'point_in_time_universe':False, 'execution_grade':False, 'intraday_execution_verified':False,
        'limitations':['Selected contemporary liquid equities; survivorship bias', 'No historical bid/ask or manual latency observations',
                        'Daily entry/exit proxy, not executable intraday replay', 'Corporate action and revision audit outstanding'], 'sources':metadata})
    return key


def features(frame):
    """Each row is known after that session close. No fit, fill or future adjustment."""
    parts=[]
    for symbol, g in validate(frame).groupby('symbol', sort=True):
        g=g.copy()
        r=g.close*g.split/g.close.shift(1)-1
        index=(1+r.fillna(0)).cumprod()
        g['ret1']=r
        g['ret5']=index/index.shift(5)-1
        g['ret20']=index/index.shift(20)-1
        g['vol20']=r.rolling(20).std()
        g['range5']=((g.high-g.low)/g.close).rolling(5).mean()
        g['volume_ratio']=(g.close*g.volume)/(g.close*g.volume).rolling(20).mean()-1
        g['trend']=index/index.rolling(50).mean()-1
        g['gap']=g.open*g.split/g.close.shift(1)-1
        g['adv20']=(g.close*g.volume).rolling(20).mean()
        g['stop_fraction']=np.clip(g['range5']*.75,.005,.025)
        for col in ('date','open','low','close'):
            g['next_'+col]=g[col].shift(-1)
        g['signal_time']=pd.to_datetime(g.date+' 15:30:00').dt.tz_localize(IST).dt.tz_convert('UTC')
        g['label_end']=pd.to_datetime(g.next_date+' 15:30:00').dt.tz_localize(IST).dt.tz_convert('UTC')
        parts.append(g)
    result=pd.concat(parts).sort_values(['date','symbol']).reset_index(drop=True)
    return result.dropna(subset=FEATURES+['adv20'])
