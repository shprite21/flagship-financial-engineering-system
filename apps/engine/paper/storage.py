"""Atomic checkpoints and immutable, hash-linked forward events."""
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def changes(before, after, path=()):
    if before == after: return []
    if isinstance(before, dict) and isinstance(after, dict):
        result = []
        for key in before.keys() - after.keys(): result.append({'op': 'delete', 'path': [*path, key]})
        for key, value in after.items():
            if key not in before: result.append({'op': 'set', 'path': [*path, key], 'value': value})
            else: result.extend(changes(before[key], value, (*path, key)))
        return result
    if isinstance(before, list) and isinstance(after, list) and len(after) >= len(before) and after[:len(before)] == before:
        return [{'op': 'append', 'path': list(path), 'value': after[len(before):]}]
    return [{'op': 'set', 'path': list(path), 'value': after}]


def apply_changes(state, operations):
    for operation in operations:
        path = operation['path']
        target = state
        for key in path[:-1]: target = target[key]
        if operation['op'] == 'delete': del target[path[-1]]
        elif operation['op'] == 'append': target[path[-1]].extend(json.loads(canonical(operation['value'])))
        else: target[path[-1]] = json.loads(canonical(operation['value']))
    return state


class Ledger:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / 'paper.sqlite'
        with self.transaction() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS deployments(id TEXT PRIMARY KEY, config TEXT NOT NULL, state TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY, deployment TEXT NOT NULL, key TEXT NOT NULL,
                    body TEXT NOT NULL, previous TEXT NOT NULL, hash TEXT NOT NULL, UNIQUE(deployment,key));
                CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT,'immutable paper event'); END;
                CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT,'immutable paper event'); END;
                CREATE TRIGGER IF NOT EXISTS config_no_update BEFORE UPDATE OF config ON deployments BEGIN SELECT RAISE(ABORT,'frozen deployment'); END;
            ''')

    @contextmanager
    def transaction(self):
        with sqlite3.connect(self.path, timeout=30) as db:
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('BEGIN IMMEDIATE')
            yield db

    def rows(self):
        with self.transaction() as db:
            return [{'id': r['id'], 'config': json.loads(r['config']), **json.loads(r['state'])}
                    for r in db.execute('SELECT * FROM deployments ORDER BY rowid DESC')]

    def read(self, db, key):
        row = db.execute('SELECT * FROM deployments WHERE id=?', (key,)).fetchone()
        if row is None:
            raise ValueError('Paper deployment not found')
        return json.loads(row['config']), json.loads(row['state'])

    def exists(self, db, deployment, key):
        return db.execute('SELECT 1 FROM events WHERE deployment=? AND key=?', (deployment, key)).fetchone() is not None

    def append(self, db, deployment, key, kind, at, state, detail=None):
        previous = db.execute('SELECT hash FROM events WHERE deployment=? ORDER BY seq DESC LIMIT 1', (deployment,)).fetchone()
        previous = previous[0] if previous else ''
        old = self.read(db, deployment)[1] if previous else {}
        body = {'kind': kind, 'recorded_at': at, 'detail': detail or {}, 'changes': changes(old, state)}
        hashed = digest({'previous': previous, 'key': key, 'body': body})
        db.execute('INSERT INTO events(deployment,key,body,previous,hash) VALUES(?,?,?,?,?)',
                   (deployment, key, canonical(body), previous, hashed))
        db.execute('UPDATE deployments SET state=? WHERE id=?', (canonical(state), deployment))

    def export(self, deployment):
        with self.transaction() as db:
            config, state = self.read(db, deployment)
            events = [dict(r) for r in db.execute('SELECT key,body,previous,hash FROM events WHERE deployment=? ORDER BY seq', (deployment,))]
        previous = ''
        replayed = {}
        for event in events:
            event['body'] = json.loads(event['body'])
            if event['previous'] != previous or event['hash'] != digest({'previous': previous, 'key': event['key'], 'body': event['body']}):
                raise ValueError('Paper event integrity verification failed')
            previous = event['hash']
            apply_changes(replayed, event['body']['changes'])
        if events and events[0]['body']['detail'].get('config_hash') != digest(config):
            raise ValueError('Frozen deployment configuration integrity check failed')
        if events and replayed != state:
            raise ValueError('Checkpoint does not match immutable ledger')
        inputs = {}
        source = config.get('engine_source_hash')
        if source:
            data = json.loads((self.root / 'inputs' / (source + '.json')).read_text(encoding='utf-8'))
            if digest(data) != source: raise ValueError('Frozen engine source integrity check failed')
            inputs[source] = data
        for event in events:
            key = event['body']['detail'].get('input_hash')
            if key and key not in inputs:
                data = json.loads((self.root / 'inputs' / (key + '.json')).read_text(encoding='utf-8'))
                if digest(data) != key: raise ValueError('Paper input integrity verification failed')
                inputs[key] = data
        return {'schema_version': 1, 'id': deployment, 'config': config, 'state': state,
                'events': events, 'inputs': inputs, 'source': 'q_simulated', 'broker_verified': False}

    def save_input(self, data):
        key = digest(data)
        directory = self.root / 'inputs'
        directory.mkdir(exist_ok=True)
        path = directory / (key + '.json')
        try:
            with path.open('x', encoding='utf-8') as f: f.write(canonical(data))
        except FileExistsError:
            if digest(json.loads(path.read_text(encoding='utf-8'))) != key:
                raise ValueError('Paper input snapshot was altered')
        return key
