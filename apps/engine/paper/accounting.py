"""Pure, causal whole-share accounting. All fills are modeled, never broker fills."""
import math
from copy import deepcopy
from .models import OrderIntent, utc


def account(capital):
    return {'initial': capital, 'cash': capital, 'unsettled': [], 'receivables': [],
            'positions': {}, 'marks': {}, 'orders': [], 'fills': [], 'actions': [],
            'targets': {}, 'peak': capital, 'nav': capital, 'drawdown': 0, 'fees': 0}


def value(a):
    return (a['cash'] + sum(x['amount'] for x in a['unsettled']) +
            sum(x['amount'] for x in a['receivables']) +
            sum(p['quantity'] * a['marks'][s] for s, p in a['positions'].items()))


def mark(a):
    a['nav'] = value(a)
    a['peak'] = max(a['peak'], a['nav'])
    a['drawdown'] = a['nav'] / a['peak'] - 1
    if a['cash'] < -1e-7 or any(p['quantity'] < 0 for p in a['positions'].values()):
        raise ValueError('Paper cash/position invariant failed')


def pending(a):
    return [o for o in a['orders'] if o['status'] in ('pending', 'partial')]


def reserved(a):
    return sum(o['reserve'] for o in pending(a) if o['side'] == 'BUY')


def cancel(a):
    for o in pending(a):
        o.update(status='cancelled', reserve=0)


def submit(a, intents, cfg, decision_at, data_end, eligible_session, signal_id):
    """Validate a complete batch before any mutations; reserve known buying power."""
    draft = deepcopy(a)
    for index, intent in enumerate(intents):
        i = OrderIntent.model_validate(intent).model_dump()
        if i['symbol'] not in cfg.universe or i['symbol'] not in draft['marks']:
            raise ValueError('Order needs a marked instrument in the frozen universe')
        if cfg.interval == '1d' and i['type'] != 'market':
            raise ValueError('Limits and stops require one-minute execution data')
        px = i['limit'] or i['stop'] or draft['marks'][i['symbol']]
        notional = px * i['quantity']
        if notional > cfg.max_order_notional + 1e-8:
            raise ValueError('Order exceeds frozen notional limit')
        if i['side'] == 'SELL':
            held = draft['positions'].get(i['symbol'], {}).get('quantity', 0)
            selling = sum(o['remaining'] for o in pending(draft) if o['symbol'] == i['symbol'] and o['side'] == 'SELL')
            if i['quantity'] > held - selling:
                raise ValueError('Sell quantity exceeds unreserved holdings')
            reserve = 0
        else:
            reserve = notional * (1 + (cfg.commission_bps + cfg.slippage_bps) / 10000)
            if reserve > draft['cash'] - reserved(draft) + 1e-8:
                raise ValueError('Insufficient settled, unreserved cash')
            nav = value(draft)
            exposure = sum(p['quantity'] * draft['marks'][s] for s, p in draft['positions'].items())
            existing = draft['positions'].get(i['symbol'], {}).get('quantity', 0) * draft['marks'][i['symbol']]
            buys = sum(o['remaining'] * o['reference_price'] for o in pending(draft) if o['side'] == 'BUY')
            same = sum(o['remaining'] * o['reference_price'] for o in pending(draft) if o['side'] == 'BUY' and o['symbol'] == i['symbol'])
            if exposure + buys + notional > nav * cfg.max_gross + 1e-8 or existing + same + notional > nav * cfg.max_asset_weight + 1e-8:
                raise ValueError('Order exceeds frozen exposure limits')
        draft['orders'].append({**i, 'id': f'{signal_id}:{index}', 'signal_id': signal_id,
                                'remaining': i['quantity'], 'status': 'pending', 'reserve': reserve,
                                'filled_notional': 0,
                                'reference_price': px, 'decision_at': decision_at, 'data_end': data_end,
                                'eligible_session': eligible_session, 'triggered_at': None})
    a.update(draft)


def target_orders(a, weights, cfg):
    if set(weights) - set(cfg.universe) or any(not math.isfinite(w) or w < 0 or w > cfg.max_asset_weight for w in weights.values()) or sum(weights.values()) > cfg.max_gross + 1e-9:
        raise ValueError('Strategy targets breach frozen long-only limits')
    nav = value(a)
    orders = []
    cash = a['cash']
    gross_room = max(0, cfg.max_gross * nav - sum(p['quantity'] * a['marks'][s] for s, p in a['positions'].items()))
    for symbol in sorted(cfg.universe):
        px = a['marks'][symbol]
        held = a['positions'].get(symbol, {}).get('quantity', 0)
        quantity = math.floor(weights.get(symbol, 0) * nav / px) - held
        cap = math.floor(cfg.max_order_notional / px)
        if quantity > 0:
            unit = px * (1 + (cfg.commission_bps + cfg.slippage_bps) / 10000)
            asset_room = max(0, cfg.max_asset_weight * nav - held * px)
            quantity = min(quantity, cap, math.floor(max(0, cash) / unit), math.floor(min(gross_room, asset_room) / px))
            cash -= quantity * unit
            gross_room -= quantity * px
        else:
            quantity = max(quantity, -cap)
        if quantity:
            orders.append({'symbol': symbol, 'side': 'BUY' if quantity > 0 else 'SELL', 'quantity': abs(quantity)})
    return sorted(orders, key=lambda o: (o['side'] == 'BUY', o['symbol']))


def settle(a, at):
    for field in ('unsettled', 'receivables'):
        due = [x for x in a[field] if x.get('pay_at') and utc(x['pay_at']) <= utc(at)]
        a['cash'] += sum(x['amount'] for x in due)
        a[field] = [x for x in a[field] if x not in due]


def corporate_action(a, action, bar):
    if action.id in a['actions']:
        return
    p = a['positions'].get(action.symbol)
    if p:
        if action.kind == 'split':
            exact = p['quantity'] * action.amount
            whole = math.floor(exact + 1e-9)
            a['cash'] += (exact - whole) * bar.open
            p['cost'] *= whole / exact if exact else 0
            p['quantity'] = whole
            a['marks'][action.symbol] /= action.amount
            # Cancel working instructions in obsolete share/price units.
            for o in pending(a):
                if o['symbol'] == action.symbol:
                    o.update(status='cancelled', reserve=0)
        else:
            a['receivables'].append({'id': action.id, 'amount': p['quantity'] * action.amount, 'pay_at': action.pay_at})
    a['actions'].append(action.id)


def execution_price(o, b, cfg):
    buy = o['side'] == 'BUY'
    kind = o['type']
    base = b.open
    if kind in ('stop', 'stop_limit') and o['triggered_at'] is None:
        if not (b.high >= o['stop'] if buy else b.low <= o['stop']):
            return None
        o['triggered_at'] = b.end
        if kind == 'stop_limit':
            return None  # Intrabar ordering cannot be reconstructed from OHLC.
        base = max(b.open, o['stop']) if buy else min(b.open, o['stop'])
    if kind in ('limit', 'stop_limit'):
        if kind == 'stop_limit' and utc(b.start) < utc(o['triggered_at']):
            return None
        if not (b.low <= o['limit'] if buy else b.high >= o['limit']):
            return None
        base = min(b.open, o['limit']) if buy else max(b.open, o['limit'])
    px = base * (1 + cfg.slippage_bps / 10000 * (1 if buy else -1))
    if kind in ('limit', 'stop_limit'):
        px = min(px, o['limit']) if buy else max(px, o['limit'])
    return px


def process_bar(a, bar, previous_volume, session, cfg, received_at, mark_close=True, capacity_limit=None):
    settle(a, bar.start)
    capacity = math.floor(max(0, previous_volume) * cfg.participation)
    if capacity_limit is not None: capacity = min(capacity, capacity_limit)
    initial_capacity = capacity
    for o in pending(a):
        if o['symbol'] != bar.symbol:
            continue
        if o['tif'] == 'DAY' and o['eligible_session'] < bar.session:
            o.update(status='expired', reserve=0)
            continue
        if bar.session < o['eligible_session'] or utc(bar.start) <= utc(o['decision_at']) or utc(bar.start) < utc(o['data_end']):
            continue
        price = execution_price(o, bar, cfg)
        if price is None or not capacity:
            continue
        qty = min(o['remaining'], capacity)
        qty = min(qty, math.floor(max(0, cfg.max_order_notional - o.get('filled_notional', 0)) / price))
        p = a['positions'].setdefault(bar.symbol, {'quantity': 0, 'cost': 0})
        if o['side'] == 'BUY':
            other = reserved(a) - o['reserve']
            qty = min(qty, math.floor(max(0, a['cash'] - other) / (price * (1 + cfg.commission_bps / 10000))))
            # Recheck risk at the modeled execution price after an opening gap.
            exposure = sum(pos['quantity'] * a['marks'][s] for s, pos in a['positions'].items())
            nav = value(a)
            risk_room = min(cfg.max_gross * nav - exposure,
                            cfg.max_asset_weight * nav - p['quantity'] * a['marks'][bar.symbol],
                            cfg.max_order_notional)
            qty = min(qty, math.floor(max(0, risk_room) / price))
        else:
            qty = min(qty, p['quantity'])
        if qty <= 0:
            continue
        fee = qty * price * cfg.commission_bps / 10000
        pnl = None
        if o['side'] == 'BUY':
            a['cash'] -= qty * price + fee
            p['cost'] += qty * price + fee
            p['quantity'] += qty
        else:
            cost = p['cost'] * qty / p['quantity']
            pnl = qty * price - fee - cost
            p['cost'] -= cost
            p['quantity'] -= qty
            a['unsettled'].append({'amount': qty * price - fee, 'pay_at': session.settlement})
        a['fees'] += fee
        o['filled_notional'] = o.get('filled_notional', 0) + qty * price
        o['remaining'] -= qty
        o['status'] = 'filled' if not o['remaining'] else 'partial'
        o['reserve'] *= o['remaining'] / (o['remaining'] + qty)
        capacity -= qty
        a['fills'].append({'order_id': o['id'], 'symbol': bar.symbol, 'side': o['side'],
                           'quantity': qty, 'price': price, 'fee': fee, 'realized_pnl': pnl,
                           'market_at': bar.start if o['type'] == 'market' else bar.end,
                           'received_at': received_at, 'decision_at': o['decision_at'],
                           'source': 'q_simulated', 'broker_verified': False})
    if mark_close: a['marks'][bar.symbol] = bar.close
    if utc(bar.end) == utc(session.close):
        for o in pending(a):
            if o['symbol'] == bar.symbol and o['tif'] == 'DAY' and o['eligible_session'] <= bar.session:
                o.update(status='expired', reserve=0)
    settle(a, bar.end)
    if mark_close: mark(a)
    return initial_capacity - capacity
