"""Persistent prospective runner. Feed acquisition is a gateway responsibility."""
import json
import math
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import uuid4
from pydantic import ValidationError
from .models import Deployment, Feed, utc
from .storage import Ledger, canonical, digest
from . import accounting as ac
from .strategies import targets


def now():
    return datetime.now(timezone.utc).isoformat()


def safe_error(exc):
    if isinstance(exc, ValidationError):
        return '; '.join('.'.join(map(str, e['loc'])) + ': ' + e['msg'] for e in exc.errors())[:400]
    return str(exc)[:400] if isinstance(exc, (ValueError, OSError)) else 'Paper processing failed; no partial transaction committed'


def engine_sources():
    import sys
    from importlib.metadata import version, PackageNotFoundError
    root = Path(__file__).resolve().parents[1]
    paths = [root / 'requirements.lock.txt']
    for folder in ('paper', 'research', 'strategies', 'portfolio', 'risk', 'regime_detection', 'data'):
        paths.extend(sorted((root / folder).glob('**/*.py')))
    result = {str(p.relative_to(root)): p.read_text(encoding='utf-8') for p in paths if p.is_file()}
    dependencies = {}
    for package in ('numpy', 'pandas', 'scipy', 'pydantic', 'scikit-learn', 'hmmlearn'):
        try: dependencies[package] = version(package)
        except PackageNotFoundError: dependencies[package] = 'unavailable'
    result['runtime.json'] = canonical({'python': sys.version, 'dependencies': dependencies})
    return result


def engine_identity():
    return digest(engine_sources())


class PaperService:
    def __init__(self, root, feed_loader, clock=now):
        self.ledger = Ledger(root)
        self.feed_loader = feed_loader
        self.clock = clock
        self.identity = engine_identity()
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.thread = None

    def create(self, cfg: Deployment, snapshots=None):
        if self.identity != engine_identity():
            raise ValueError('Engine source changed; restart Q before freezing a deployment')
        at, key = self.clock(), uuid4().hex
        frozen = {'spec': cfg.model_dump(), 'engine': self.identity, 'snapshots': snapshots or {}, 'created_at': at}
        frozen['engine_source_hash'] = self.ledger.save_input(engine_sources())
        accounts = {str(i): ac.account(cfg.capital * s.budget) for i, s in enumerate(cfg.strategies)} if cfg.mode == 'funded' else {'0': ac.account(cfg.capital)}
        state = {'status': 'draft', 'created_at': at, 'accounts': accounts, 'last_bar': None,
                 'last_decision': None, 'last_poll': None, 'next_decision': None,
                 'exceptions': [], 'nav_history': [], 'strategy_state': {}, 'feed_receipts': {},
                 'source': 'q_simulated', 'broker_verified': False, 'live_order_submission': False}
        with self.lock, self.ledger.transaction() as db:
            db.execute('INSERT INTO deployments VALUES(?,?,?)', (key, canonical(frozen), canonical(state)))
            self.ledger.append(db, key, 'registration', 'registration', at, state, {'config_hash': digest(frozen)})
        return self.get(key)

    def get(self, key):
        with self.ledger.transaction() as db:
            config, state = self.ledger.read(db, key)
        return {'id': key, 'config': config, **self.summary(state)}

    def summary(self, state):
        state = json.loads(canonical(state))
        state['nav'] = sum(a['nav'] for a in state['accounts'].values())
        state['cash'] = sum(a['cash'] for a in state['accounts'].values())
        state['reserved'] = sum(ac.reserved(a) for a in state['accounts'].values())
        state['pnl'] = state['nav'] - sum(a['initial'] for a in state['accounts'].values())
        return state

    def list(self):
        return [{**r, **self.summary({k: v for k, v in r.items() if k not in ('id', 'config')})} for r in self.ledger.rows()]

    def feed(self, cfg):
        feed = Feed.model_validate(self.feed_loader(cfg))
        if (feed.provider, feed.market, feed.interval) != (cfg.provider, cfg.market, cfg.interval):
            raise ValueError('Feed does not match the frozen provider, market and interval')
        current = utc(self.clock())
        if utc(feed.generated_at) > current or current - utc(feed.generated_at) > timedelta(minutes=5):
            raise ValueError('Feed heartbeat is stale or future-dated')
        if any(utc(b.received_at) > current for b in feed.bars):
            raise ValueError('Feed includes future receipt timestamps')
        return feed

    def readiness(self, key):
        deployment = self.get(key)
        cfg = Deployment.model_validate(deployment['config']['spec'])
        errors = []
        if deployment['config']['engine'] != self.identity or self.identity != engine_identity():
            errors.append('Frozen engine differs from installed code; create a new deployment')
        for spec in cfg.strategies:
            if spec.adapter.startswith('custom_'):
                try:
                    from .worker import image_for, validate_files
                    _, image, _ = image_for(spec.adapter)
                    validate_files(spec)
                    if spec.parameters.get('worker_image') != image:
                        errors.append('Custom worker image differs from frozen deployment; register a new draft')
                except ValueError as exc:
                    errors.append(str(exc))
        if cfg.mode == 'combined' and any(s.output == 'orders' for s in cfg.strategies):
            errors.append('Combined allocation requires target output; use funded sleeves for explicit order strategies')
        if any(s.output == 'orders' and not s.adapter.startswith('custom_') for s in cfg.strategies):
            errors.append('This trusted strategy adapter produces targets, not explicit orders')
        try:
            feed = self.feed(cfg)
            current = utc(self.clock())
            future = [s for s in feed.sessions if utc(s.open) > current]
            if not future:
                errors.append('Calendar has no future session')
            if utc(feed.actions_complete_through) < current:
                errors.append('Corporate-action coverage is stale')
            for symbol in cfg.universe:
                if not any(b.symbol == symbol for b in feed.bars):
                    errors.append(f'{symbol}: no completed raw bars')
            past = [s for s in feed.sessions if utc(s.close) < current]
            if past:
                latest = max(past, key=lambda s: utc(s.close))
                if any(not any(b.symbol == symbol and utc(b.end) == utc(latest.close) for b in feed.bars) for symbol in cfg.universe):
                    errors.append('Latest completed session is missing instrument bars')
            # Fail before activation if the signal adapter cannot run on supplied history.
            if not errors:
                history = {s: sorted([b for b in feed.bars if b.symbol == s], key=lambda b: utc(b.end)) for s in cfg.universe}
                for i, spec in enumerate(cfg.strategies):
                    if spec.adapter.startswith('custom_'): continue
                    a = deployment['accounts'][str(i) if cfg.mode == 'funded' else '0']
                    weights = targets(spec, history, feed.actions, a)
                    if any(v < 0 for v in weights.values()):
                        raise ValueError('Long-only paper adapter returned a negative target')
        except (ValueError, OSError) as exc:
            errors.append(safe_error(exc))
        return {'ready': not errors, 'blockers': errors, 'live_order_submission': False}

    def control(self, key, action):
        activation_feed = None
        if action in ('activate', 'resume'):
            ready = self.readiness(key)
            if not ready['ready']:
                raise ValueError('; '.join(ready['blockers']))
            activation_feed = self.feed(Deployment.model_validate(self.get(key)['config']['spec']))
        with self.lock, self.ledger.transaction() as db:
            frozen, state = self.ledger.read(db, key)
            status = state['status']
            if action == 'activate' and status != 'draft' or action == 'resume' and status != 'paused':
                raise ValueError('Invalid paper lifecycle transition')
            if action in ('pause', 'stop', 'liquidate') and status not in ('active', 'paused'):
                raise ValueError('Control requires an active or paused deployment')
            at = self.clock()
            if action in ('activate', 'resume'):
                if state.get('calendar_version', activation_feed.calendar_version) != activation_feed.calendar_version or state.get('rules_version', activation_feed.rules_version) != activation_feed.rules_version:
                    raise ValueError('Calendar or market rules changed; create a new deployment')
                state['calendar_version'] = activation_feed.calendar_version
                state['rules_version'] = activation_feed.rules_version
                state.update(status='active', active_since=at, exceptions=[])
                state.pop('halt_reason', None)
                state.setdefault('first_active_at', at)
                state['liquidating'] = False
            elif action == 'pause':
                state['status'] = 'paused'
                for a in state['accounts'].values(): ac.cancel(a)
            elif action == 'stop':
                state['status'] = 'stopped'
                for a in state['accounts'].values(): ac.cancel(a)
            elif action == 'liquidate':
                cfg = Deployment.model_validate(frozen['spec'])
                feed = self.feed(cfg)
                at = self.clock()
                future = [s for s in feed.sessions if utc(s.open) > utc(at)]
                if not future: raise ValueError('No eligible future session')
                session = min(future, key=lambda s: utc(s.open))
                for index, a in state['accounts'].items():
                    ac.cancel(a)
                    intents = ac.target_orders(a, {}, cfg)
                    ac.submit(a, intents, cfg, at, state['last_bar'] or at, session.date, f'liquidation:{at}:{index}')
                state.update(status='paused', liquidating=True)
            else:
                raise ValueError('Unknown paper control')
            self.ledger.append(db, key, f'control:{uuid4().hex}', action, at, state)
        return self.get(key)

    def cancel_order(self, key, order_id):
        with self.lock, self.ledger.transaction() as db:
            _, state = self.ledger.read(db, key)
            found = False
            for account in state['accounts'].values():
                for order in ac.pending(account):
                    if order['id'] == order_id:
                        order.update(status='cancelled', reserve=0)
                        found = True
            if not found: raise ValueError('Pending order not found')
            self.ledger.append(db, key, 'cancel:' + uuid4().hex, 'cancel_order', self.clock(), state, {'order_id': order_id})
        return self.get(key)

    def process(self, key):
        deployment = self.get(key)
        if deployment['status'] not in ('active', 'paused'):
            return
        cfg = Deployment.model_validate(deployment['config']['spec'])
        if deployment['config']['engine'] != self.identity or self.identity != engine_identity():
            raise ValueError('Frozen engine changed; processing blocked')
        feed = self.feed(cfg)
        at = self.clock()
        sessions = {s.date: s for s in feed.sessions}
        bars = sorted([b for b in feed.bars if b.symbol in cfg.universe], key=lambda b: (utc(b.end), b.symbol))
        with self.lock, self.ledger.transaction() as db:
            _, state = self.ledger.read(db, key)
            if state['status'] not in ('active', 'paused'):
                return
            state['last_poll'] = at
            state['exceptions'] = []
            if state.get('halt_reason'): state['exceptions'].append(state['halt_reason'])
            state.setdefault('calendar_version', feed.calendar_version)
            state.setdefault('rules_version', feed.rules_version)
            if state['calendar_version'] != feed.calendar_version or state['rules_version'] != feed.rules_version:
                raise ValueError('Feed calendar/rules version changed; review a new deployment')
            for b in bars:
                receipt_key = b.symbol + ':' + b.end
                if receipt_key in state['feed_receipts'] and state['feed_receipts'][receipt_key] != digest(b.model_dump()):
                    raise ValueError('Previously consumed market data was revised; review before a new deployment')
            activation = utc(state.get('first_active_at', state['active_since']))
            groups = {}
            for b in bars:
                if utc(b.end) <= activation and state['last_bar'] is None:
                    continue
                if state['last_bar'] and utc(b.end) <= utc(state['last_bar']):
                    continue
                groups.setdefault(b.end, []).append(b)
            input_hash = self.ledger.save_input(feed.model_dump()) if groups else None
            for end, group in groups.items():
                if set(b.symbol for b in group) != set(cfg.universe):
                    state['exceptions'].append(f'Incomplete instrument coverage at {end}; processing stopped')
                    break
                if utc(feed.actions_complete_through) < utc(end):
                    state['exceptions'].append('Corporate actions are incomplete; processing stopped')
                    break
                session = sessions[group[0].session]
                # Verify no expected sessions/minutes were skipped between checkpoints.
                prior_end = utc(state['last_bar']) if state['last_bar'] else activation
                missing_sessions = [s for s in feed.sessions if prior_end < utc(s.close) < utc(end)]
                if missing_sessions:
                    state['exceptions'].append('Missing exchange session bars; processing stopped')
                    break
                if cfg.interval == '1m':
                    expected_start = max(utc(session.open), prior_end if state['last_bar'] else activation.replace(second=0, microsecond=0))
                    if utc(group[0].start) != expected_start:
                        state['exceptions'].append('Missing minute bars; processing stopped')
                        break
                prior_volumes = {}
                for b in group:
                    previous = [x for x in bars if x.symbol == b.symbol and utc(x.end) <= utc(b.start) and utc(x.received_at) < utc(b.start)]
                    prior_volumes[b.symbol] = previous[-1].volume if previous else 0
                remaining_capacity = {s: math.floor(v * cfg.participation) for s, v in prior_volumes.items()}
                for a in state['accounts'].values():
                    for b in group:
                        # Initialize valuation only, never historical holdings.
                        a['marks'].setdefault(b.symbol, b.open)
                        for action in sorted(feed.actions, key=lambda x: (utc(x.effective_at), x.kind != 'split')):
                            if action.symbol == b.symbol and activation < utc(action.effective_at) <= utc(b.start):
                                ac.corporate_action(a, action, b)
                    # Every fill in this group sees opening marks, never another
                    # instrument's later close from the same bar.
                    for b in group: a['marks'][b.symbol] = b.open
                    for b in group:
                        used = ac.process_bar(a, b, prior_volumes[b.symbol], session, cfg, at, mark_close=False, capacity_limit=remaining_capacity[b.symbol])
                        remaining_capacity[b.symbol] -= used
                    for b in group: a['marks'][b.symbol] = b.close
                    ac.mark(a)
                state['last_bar'] = end
                for b in group: state['feed_receipts'][b.symbol + ':' + b.end] = digest(b.model_dump())
                nav = sum(a['nav'] for a in state['accounts'].values())
                state['nav_history'].append({'date': end, 'value': nav,
                    'sleeves': {k: a['nav'] for k, a in state['accounts'].items()}})
                if any(a['drawdown'] <= -cfg.drawdown_limit for a in state['accounts'].values()):
                    state['status'] = 'paused'
                    state['halt_reason'] = 'Drawdown limit reached; pending orders cancelled'
                    state['exceptions'].append(state['halt_reason'])
                    for a in state['accounts'].values(): ac.cancel(a)
                future = sorted([s for s in feed.sessions if utc(s.open) > utc(at)], key=lambda s: utc(s.open))
                state['next_decision'] = future[0].close if future else None
                eligible = future[0].date if future else None
                is_close = utc(end) == utc(session.close)
                due = cfg.rebalance == 'every_bar' or is_close
                if cfg.rebalance == 'weekly' and future:
                    due = is_close and utc(session.close).isocalendar()[:2] != utc(future[0].close).isocalendar()[:2]
                if cfg.rebalance == 'monthly' and future:
                    due = is_close and session.date[:7] != future[0].date[:7]
                if cfg.rebalance == 'every_bar' and utc(at) < utc(session.close):
                    eligible = session.date
                    state['next_decision'] = (utc(end) + timedelta(minutes=1)).isoformat()
                delay = timedelta(minutes=2 if cfg.interval == '1m' else 60)
                timely = utc(at) - utc(end) <= delay
                if state.get('liquidating') and due and timely and eligible:
                    for index, a in state['accounts'].items():
                        ac.cancel(a)
                        ac.submit(a, ac.target_orders(a, {}, cfg), cfg, at, end, eligible, f'liquidation:{end}:{index}')
                    if all(not any(p['quantity'] for p in a['positions'].values()) for a in state['accounts'].values()):
                        state['liquidating'] = False
                if due and state['status'] == 'active' and utc(end) > utc(state['active_since']):
                    if not timely or not eligible:
                        state['exceptions'].append(f'Missed decision {end}; no signal backfilled')
                    else:
                        history = {s: [b for b in bars if b.symbol == s and utc(b.end) <= utc(end) and utc(b.received_at) <= utc(at)] for s in cfg.universe}
                        for h in history.values():
                            for b in h: state['feed_receipts'][b.symbol + ':' + b.end] = digest(b.model_dump())
                        known_actions = [a for a in feed.actions if utc(a.effective_at) <= utc(end)]
                        signal_id = f'signal:{end}'
                        before_signal = json.loads(canonical(state))
                        try:
                            calculated = []
                            for i, spec in enumerate(cfg.strategies):
                                account = state['accounts'][str(i) if cfg.mode == 'funded' else '0']
                                if spec.adapter.startswith('custom_'):
                                    from .worker import run
                                    result = run(spec, {'schema_version': 1, 'decision_at': at, 'data_end': end,
                                        'history': {s: [b.model_dump() for b in h] for s, h in history.items()},
                                        'corporate_actions': [a.model_dump() for a in known_actions],
                                        'account': account, 'parameters': spec.parameters.get('parameters', {}),
                                        'state': state['strategy_state'].get(str(i), {})}, cancelled=self.stop_event.is_set)
                                    state['strategy_state'][str(i)] = result.get('state', {})
                                    calculated.append(result)
                                else:
                                    calculated.append({'targets': targets(spec, history, known_actions, account)})
                            # Record the time the result actually exists, not the
                            # time a potentially slow custom calculation started.
                            signal_received_at = self.clock()
                            eligible_after_compute = sorted([s for s in feed.sessions if utc(s.open) > utc(signal_received_at)], key=lambda s: utc(s.open))
                            if cfg.rebalance == 'every_bar' and utc(signal_received_at) < utc(session.close):
                                execution_session = session.date
                            elif eligible_after_compute:
                                execution_session = eligible_after_compute[0].date
                            else:
                                raise ValueError('Calendar has no execution session after the computed signal')
                            for index, a in state['accounts'].items():
                                result = calculated[int(index)] if cfg.mode == 'funded' else calculated[0] if cfg.mode == 'strategy' else {'targets': {s: sum(spec.budget * w['targets'].get(s, 0) for spec, w in zip(cfg.strategies, calculated)) for s in cfg.universe}}
                                if 'targets' in result:
                                    ac.cancel(a)
                                    a['targets'] = result['targets']
                                    intents = ac.target_orders(a, result['targets'], cfg)
                                else:
                                    intents = result['orders']
                                    if not isinstance(intents, list) or len(intents) > 200: raise ValueError('Custom order batch exceeds 200 orders')
                                ac.submit(a, intents, cfg, signal_received_at, end, execution_session, signal_id + ':' + index)
                            state['last_decision'] = signal_received_at
                        except Exception as exc:
                            state = before_signal
                            state['status'] = 'paused'
                            for account in state['accounts'].values(): ac.cancel(account)
                            reason = safe_error(exc) if isinstance(exc, ValueError) else 'Strategy adapter failed'
                            state['halt_reason'] = 'Signal rejected; account paused: ' + reason
                            state['exceptions'].append(state['halt_reason'])

                self.ledger.append(db, key, 'bar:' + end, 'bar_and_decision', self.clock(), state,
                                   {'input_hash': input_hash, 'feed_hash': digest([b.model_dump() for b in group]), 'market_at': end,
                                    'provider_received_at': max(b.received_at for b in group)})
            # Keep heartbeat/status changes even when no new bar exists.
            if not groups:
                latest_closed = [s for s in feed.sessions if utc(s.close) < utc(at) - timedelta(minutes=5)]
                if latest_closed and (not state['last_bar'] or utc(state['last_bar']) < max(utc(s.close) for s in latest_closed)):
                    state['exceptions'].append('Waiting for completed market data; valuation may be stale')
            state['last_poll'] = self.clock()
            self.ledger.append(db, key, 'poll:' + uuid4().hex, 'heartbeat', state['last_poll'], state)

    def tick(self):
        for row in self.ledger.rows():
            if self.stop_event.is_set(): break
            if row['status'] not in ('active', 'paused'): continue
            try:
                self.process(row['id'])
            except Exception as exc:
                message = safe_error(exc)
                with self.lock, self.ledger.transaction() as db:
                    _, state = self.ledger.read(db, row['id'])
                    if state.get('exceptions') != [message]:
                        state['exceptions'] = [message]
                        self.ledger.append(db, row['id'], 'error:' + uuid4().hex, 'blocked', self.clock(), state)

    def start(self):
        if self.thread and self.thread.is_alive(): return
        self.stop_event.clear()
        def loop():
            while not self.stop_event.is_set():
                self.tick()
                self.stop_event.wait(30)
        self.thread = threading.Thread(target=loop, name='q-paper', daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread: self.thread.join(timeout=5)
